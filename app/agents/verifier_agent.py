from typing import Dict, Any, List
from app.models.schemas import VerificationReport
from app.models.state import AgentState, AgentThoughtStep

class VerifierAgent:
    """
    Adversarial verification agent that cross-checks draft claims
    against retrieved context to detect hallucinations and ensure faithfulness.
    """

    def verify(self, state: AgentState) -> AgentState:
        draft = state.draft_summary or {}
        chunks = state.retrieved_chunks
        context_text = " ".join([c.get("content", "").lower() for c in chunks])

        claims = draft.get("verifiable_claims", [])
        metrics = draft.get("key_metrics", [])

        verified_claims = []
        unsupported_claims = []

        # Check metrics against context
        for m in metrics:
            val = str(m.get("value", "")).lower()
            if val and val in context_text:
                verified_claims.append(f"Metric '{m.get('metric_name')}' ({val}) verified in context.")
            else:
                unsupported_claims.append(f"Metric '{m.get('metric_name')}' value {val} not found in retrieved chunks.")

        # Check claims
        for claim in claims:
            # Simple lexical overlap verification
            claim_tokens = [w for w in claim.lower().split() if len(w) > 3]
            matches = sum(1 for token in claim_tokens if token in context_text)
            ratio = matches / max(len(claim_tokens), 1)
            if ratio >= 0.3:
                verified_claims.append(claim)
            else:
                unsupported_claims.append(claim)

        is_faithful = len(unsupported_claims) == 0
        hallucination_score = len(unsupported_claims) / max((len(verified_claims) + len(unsupported_claims)), 1)

        report = VerificationReport(
            is_faithful=is_faithful,
            hallucination_score=round(hallucination_score, 3),
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
