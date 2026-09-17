import re
from typing import Dict, Any, List
from app.models.schemas import VerificationReport
from app.models.state import AgentState, AgentThoughtStep

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than",
    "that", "that's", "the", "their", "theirs", "them", "themselves", "then",
    "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what",
    "what's", "when", "when's", "where", "where's", "which", "while", "who",
    "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you",
    "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
}

from app.search.reranker import _stem, extract_discriminative_keywords, GENERIC_QUERY_WORDS, GENERIC_STEMS
import logging

logger = logging.getLogger(__name__)

_nli_model = None

def get_nli_model():
    """Lazily loads the local NLI CrossEncoder model with graceful fallback."""
    global _nli_model
    if _nli_model is None:
        try:
            from sentence_transformers import CrossEncoder
            _nli_model = CrossEncoder("cross-encoder/nli-deberta-v3-small")
            logger.info("Loaded NLI CrossEncoder model: cross-encoder/nli-deberta-v3-small")
        except Exception as e:
            logger.warning(f"Failed to load NLI model ({e}), falling back to keyword check.")
            _nli_model = "fallback"
    return _nli_model

COND_PATTERNS = [
    r'\bafter\s+\d+\s+days\b',
    r'\bcase-by-case\b',
    r'\bonly\s+if\b',
    r'\bunless\b',
    r'\bif\s+they\s+are\b',
    r'\bsubject\s+to\b',
    r'\bfor\s+disaster\s+recovery\b'
]

class VerifierAgent:
    """
    Adversarial verification agent that cross-checks draft claims
    against retrieved context to detect hallucinations and ensure faithfulness.
    """

    def _is_topically_relevant(self, query: str, text: str, min_coverage: float = 0.50) -> bool:
        """
        Validates whether the answer or claim addresses the core subject matter of the query.
        Requires at least one discriminative keyword match and coverage exceeding min_coverage.
        """
        disc_q = extract_discriminative_keywords(query)
        if not disc_q:
            words = re.findall(r'\b[a-zA-Z0-9_]+\b', query.lower())
            substantive_q = [
                _stem(w) for w in words
                if w not in STOP_WORDS and _stem(w) not in STOP_WORDS
                and w not in GENERIC_QUERY_WORDS and _stem(w) not in GENERIC_STEMS
                and len(w) > 2
            ]
            if not substantive_q:
                return True
            disc_q = substantive_q

        text_words = set([_stem(w) for w in re.findall(r'\b[a-zA-Z0-9_]+\b', text.lower())])
        matched = [dk for dk in disc_q if dk in text_words]
        if not matched:
            return False
        coverage = len(matched) / len(disc_q)
        return coverage > min_coverage

    def _is_claim_supported(self, claim: str, context_text: str, chunks: List[Dict[str, Any]]) -> bool:
        """
        Validates whether a specific claim is grounded in the retrieved context.
        Checks for exact substring, numerical/metric consistency, and key content token overlap.
        """
        claim_lower = claim.lower().strip()
        # Direct match or exact substring match in context
        if claim_lower in context_text:
            return True

        # Check against individual chunk texts directly
        for c in chunks:
            chunk_content = c.get("content", "").lower()
            if claim_lower in chunk_content:
                return True

        # Extract numerical / quantitative tokens (numbers, percentages, metrics)
        num_tokens = re.findall(r'\b\d+(?:[\.,]\d+)*(?:%|[a-zA-Z]+)?\b', claim_lower)
        # If the claim contains specific numerical figures, all must be present in the context
        if num_tokens:
            for num in num_tokens:
                if num not in context_text:
                    return False

        # Extract substantive content words (excluding stopwords and short tokens)
        words = re.findall(r'\b[a-zA-Z0-9_\-\$]+\b', claim_lower)
        content_words = [w for w in words if w not in STOP_WORDS and len(w) > 2]

        if not content_words:
            # If no content words, fall back to checking if all non-empty words exist
            return all(w in context_text for w in words if len(w) > 1)

        # Check keyword presence in context
        matches = sum(1 for w in content_words if w in context_text)
        ratio = matches / len(content_words)

        # A claim is supported if at least 60% of substantive keywords are present in context
        return ratio >= 0.6

    def _check_claim_entailment(self, claim: str, chunks: List[Dict[str, Any]]) -> bool:
        """
        Tier 2 Semantic Verification:
        Evaluates whether candidate source sentences logically entail the claim,
        checking for contradiction, lack of entailment, and dropped condition qualifiers.
        Returns True if entailed and faithfully grounded; False if unfaithful/unsupported.
        Falls back gracefully to True on model/inference failure.
        """
        model = get_nli_model()
        if model is None or model == "fallback":
            return True

        try:
            all_sentences = []
            for c in chunks:
                text = c.get("content", "")
                sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 10]
                all_sentences.extend(sents)

            if not all_sentences:
                return True

            pairs = [[s, claim] for s in all_sentences]
            scores = model.predict(pairs, apply_softmax=True)

            best_entailment = 0.0
            best_idx = -1
            for idx, sc in enumerate(scores):
                ent = float(sc[1])
                if ent > best_entailment:
                    best_entailment = ent
                    best_idx = idx

            max_contradiction = max(float(sc[0]) for sc in scores)

            # Flag as unfaithful if high contradiction with negligible entailment
            if max_contradiction > 0.70 and best_entailment < 0.20:
                logger.info(f"Claim flagged unfaithful by NLI contradiction ({max_contradiction:.3f}): {claim}")
                return False

            # Flag as unfaithful if insufficient entailment across all context sentences
            if best_entailment < 0.50:
                logger.info(f"Claim flagged unfaithful by NLI insufficient entailment ({best_entailment:.3f}): {claim}")
                return False

            # If entailed, verify condition qualifier preservation
            if best_idx >= 0:
                matched_sent = all_sentences[best_idx]
                p_conds = [p for p in COND_PATTERNS if re.search(p, matched_sent, re.IGNORECASE)]
                c_conds = [p for p in COND_PATTERNS if re.search(p, claim, re.IGNORECASE)]
                if p_conds and not c_conds:
                    logger.info(f"Claim flagged unfaithful: dropped condition qualifier from '{matched_sent}' in claim '{claim}'")
                    return False

            return True
        except Exception as e:
            logger.warning(f"Error during NLI entailment inference ({e}), falling back to Tier 1 result.")
            return True

    def verify(self, state: AgentState) -> AgentState:
        query = state.query
        draft = state.draft_summary or {}
        chunks = state.retrieved_chunks
        context_text = " ".join([c.get("content", "").lower() for c in chunks])

        exec_summary = draft.get("executive_summary", "")

        # Check if the summary explicitly states lack of information in the knowledge base
        no_info_patterns = [
            r"don'?t have information",
            r"no information",
            r"not found in (?:the )?provided documents",
            r"does not contain information"
        ]
        is_no_info_summary = any(re.search(p, exec_summary, re.IGNORECASE) for p in no_info_patterns)
        if is_no_info_summary:
            is_topical_in_context = self._is_topically_relevant(query, context_text)
            if not chunks or not is_topical_in_context:
                report = VerificationReport(
                    is_faithful=True,
                    hallucination_score=0.0,
                    verified_claims=["Correctly confirmed that knowledge base lacks information for query."],
                    unsupported_claims=[],
                    suggested_corrections=None
                )
                state.is_verified = True
                state.final_output = {
                    **draft,
                    "verification_report": report.model_dump()
                }
                state.thought_history.append(AgentThoughtStep(
                    agent_name="VerifierAgent",
                    thought="Confirmed summary accurately states lack of information in knowledge base.",
                    action="verify_no_info_faithful",
                    observation="Faithfulness score: 1.0 (No hallucinated claims)."
                ))
                return state

        raw_claims = list(draft.get("verifiable_claims", []))
        metrics = draft.get("key_metrics", [])

        # Filter out generic placeholder strings
        clean_claims = [
            c.strip() for c in raw_claims
            if c and not c.lower().startswith("retrieved factual data points from source chunk")
        ]

        # If no specific verifiable claims, extract individual assertions from executive_summary
        if not clean_claims and exec_summary:
            cleaned_summary = re.sub(
                r"^analysis based on \d+ verified document chunks:\s*",
                "",
                exec_summary,
                flags=re.IGNORECASE
            )
            sentences = [
                s.strip() for s in re.split(r'(?<=[.!?])\s+', cleaned_summary)
                if len(s.strip()) > 10
            ]
            clean_claims.extend(sentences)

        verified_claims: List[str] = []
        unsupported_claims: List[str] = []

        is_context_topical = self._is_topically_relevant(query, context_text)

        # 1. Verify metrics against context and topic
        for m in metrics:
            val = str(m.get("value", "")).strip().lower()
            m_name = m.get("metric_name", "Metric")
            if not is_context_topical:
                unsupported_claims.append(f"Metric '{m_name}' ({val}) is from an unrelated topic for query '{query}'.")
            elif val and val in context_text:
                # Localized sentence-level entity binding check
                val_sentences = [
                    s for c in chunks
                    for s in re.split(r'(?<=[.!?])\s+', c.get("content", ""))
                    if val in s.lower()
                ]
                m_tokens = [
                    _stem(w) for w in re.findall(r'\b[a-zA-Z0-9_]+\b', m_name.lower())
                    if w not in STOP_WORDS and w not in GENERIC_QUERY_WORDS and len(w) > 2
                ]
                is_bound = True
                if m_tokens and val_sentences:
                    is_bound = any(
                        any(t in s.lower() for t in m_tokens)
                        for s in val_sentences
                    )
                if is_bound:
                    verified_claims.append(f"Metric '{m_name}' ({val}) verified in context.")
                else:
                    unsupported_claims.append(f"Metric '{m_name}' ({val}) is misattributed; entity not bound in context.")
            else:
                unsupported_claims.append(f"Metric '{m_name}' value ({val}) not found in retrieved chunks.")

        # 2. Verify discrete factual claims against context, topical relevance, and semantic entailment
        for claim in clean_claims:
            is_grounded = self._is_claim_supported(claim, context_text, chunks)
            claim_is_topical = self._is_topically_relevant(query, claim, min_coverage=0.0)

            if not is_grounded:
                unsupported_claims.append(claim)
            elif not (claim_is_topical and is_context_topical):
                unsupported_claims.append(f"Claim is grounded in context but off-topic for query '{query}': {claim}")
            else:
                # Tier 2: Semantic Entailment & Condition Guard (runs only on claims that pass Tier 1)
                is_entailed = self._check_claim_entailment(claim, chunks)
                if is_entailed:
                    verified_claims.append(claim)
                else:
                    unsupported_claims.append(f"Claim lacks semantic entailment or drops conditions: {claim}")

        # Deduplicate while preserving order
        verified_claims = list(dict.fromkeys(verified_claims))
        unsupported_claims = list(dict.fromkeys(unsupported_claims))

        total_claims = len(verified_claims) + len(unsupported_claims)
        if total_claims == 0:
            is_faithful = True
            hallucination_score = 0.0
        else:
            is_faithful = len(unsupported_claims) == 0
            hallucination_score = round(len(unsupported_claims) / total_claims, 3)

        report = VerificationReport(
            is_faithful=is_faithful,
            hallucination_score=hallucination_score,
            verified_claims=verified_claims,
            unsupported_claims=unsupported_claims,
            suggested_corrections="Ground all assertions strictly in relevant citations addressing the query." if not is_faithful else None
        )

        state.is_verified = is_faithful
        state.final_output = {
            **draft,
            "verification_report": report.model_dump()
        }

        state.thought_history.append(AgentThoughtStep(
            agent_name="VerifierAgent",
            thought=f"Verification complete. Faithfulness: {is_faithful}, Hallucination Score: {hallucination_score:.2f}.",
            action="audit_claims",
            observation=f"Verified {len(verified_claims)} items; {len(unsupported_claims)} unsupported items."
        ))
        return state

verifier_agent = VerifierAgent()
