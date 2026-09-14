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

class VerifierAgent:
    """
    Adversarial verification agent that cross-checks draft claims
    against retrieved context to detect hallucinations and ensure faithfulness.
    """

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

    def verify(self, state: AgentState) -> AgentState:
        draft = state.draft_summary or {}
        chunks = state.retrieved_chunks
        context_text = " ".join([c.get("content", "").lower() for c in chunks])

        raw_claims = list(draft.get("verifiable_claims", []))
        metrics = draft.get("key_metrics", [])

        # Filter out generic placeholder strings
        clean_claims = [
            c.strip() for c in raw_claims
            if c and not c.lower().startswith("retrieved factual data points from source chunk")
        ]

        # If no specific verifiable claims, extract individual assertions from executive_summary
        exec_summary = draft.get("executive_summary", "")
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

        # 1. Verify metrics against context
        for m in metrics:
            val = str(m.get("value", "")).strip().lower()
            m_name = m.get("metric_name", "Metric")
            if val and val in context_text:
                verified_claims.append(f"Metric '{m_name}' ({val}) verified in context.")
            else:
                unsupported_claims.append(f"Metric '{m_name}' value ({val}) not found in retrieved chunks.")

        # 2. Verify discrete factual claims against context
        for claim in clean_claims:
            if self._is_claim_supported(claim, context_text, chunks):
                verified_claims.append(claim)
            else:
                unsupported_claims.append(claim)

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
            suggested_corrections="Ground all assertions strictly in provided citations." if not is_faithful else None
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
