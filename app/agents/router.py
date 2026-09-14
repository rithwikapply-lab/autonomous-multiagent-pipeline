from typing import Dict, Any, List
import re
from app.models.state import AgentState, AgentThoughtStep

class ContextRouter:
    """
    Classifies user intent and formulates dynamic retrieval strategies
    (e.g., direct lookup, comparative analysis, multi-hop research).
    """

    INTENT_PATTERNS = {
        "quantitative_comparison": [r"compare", r"versus", r"vs", r"difference between", r"higher than", r"lower than"],
        "metric_extraction": [r"how many", r"percentage", r"ratio", r"revenue", r"cost", r"growth", r"rate", r"number of"],
        "root_cause_analysis": [r"why did", r"cause of", r"reason for", r"lead to", r"failure", r"incident"],
        "general_synthesis": [r"summarize", r"overview", r"explain", r"describe", r"what is"]
    }

    def route(self, state: AgentState) -> AgentState:
        query_lower = state.query.lower()
        detected_intent = "general_synthesis"

        for intent, patterns in self.INTENT_PATTERNS.items():
            if any(re.search(pat, query_lower) for pat in patterns):
                detected_intent = intent
                break

        state.intent = detected_intent

        # Generate sub-queries for multi-angle retrieval
        sub_queries = [state.query]
        if detected_intent == "quantitative_comparison":
            tokens = re.split(r'\b(?:vs|versus|and|compare)\b', state.query, flags=re.IGNORECASE)
            sub_queries.extend([t.strip() for t in tokens if len(t.strip()) > 3])
        elif detected_intent == "metric_extraction":
            sub_queries.append(f"{state.query} statistics numerical metrics data")

        state.search_queries = list(set(sub_queries))

        thought = AgentThoughtStep(
            agent_name="ContextRouter",
            thought=f"Classified query intent as '{detected_intent}'. Formulated {len(state.search_queries)} search strategies.",
            action="route_and_expand_queries",
            action_input={"intent": detected_intent, "sub_queries": state.search_queries},
            observation="Ready for hybrid retrieval."
        )
        state.thought_history.append(thought)
        return state

router = ContextRouter()
