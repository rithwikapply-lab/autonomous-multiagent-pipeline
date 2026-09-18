from typing import Dict, Any, List
import re
import math

class AgentTools:
    """Tools available for agent execution during analysis."""

    @staticmethod
    def calculate(expression: str) -> Dict[str, Any]:
        """Safely evaluates basic arithmetic expressions for quantitative metrics."""
        # Sanitize input: allow only digits, operators, parens, decimal points
        clean_expr = re.sub(r'[^0-9\+\-\*\/\.\(\)\s]', '', expression)
        try:
            # Restricted safe evaluation
            result = eval(clean_expr, {"__builtins__": None, "math": math})
            return {"status": "success", "expression": clean_expr, "result": float(result)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def extract_numbers_and_percentages(text: str) -> List[Dict[str, str]]:
        """Extracts numerical quantities, magnitudes, dates, and percentages with surrounding context."""
        pattern = r'(\$?\b\d+(?:,\d{3})*(?:\.\d+)?%?(?:\s+(?:million|billion|trillion))?|\$\d+(?:\.\d+)?(?:\s?[kKmMbBtT])?)\s+([a-zA-Z\s\-]{2,30})'
        matches = re.findall(pattern, text)
        results = [{"value": m[0], "context": m[1].strip()} for m in matches]

        # Extract calendar dates (e.g. May 26, 2026)
        date_pattern = r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b'
        date_matches = re.findall(date_pattern, text, re.IGNORECASE)
        for dm in date_matches:
            results.append({"value": dm, "context": "effective date"})

        return results

    @staticmethod
    def inspect_chunk(chunk_id: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Inspects full content and metadata of a specific chunk ID."""
        for c in chunks:
            if c.get("chunk_id") == chunk_id:
                return {"found": True, "chunk": c}
        return {"found": False, "message": f"Chunk {chunk_id} not found."}
