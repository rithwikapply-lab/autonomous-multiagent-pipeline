import hashlib
import math
import random
from typing import List, Dict, Tuple, Optional
from app.config import settings
import logging

try:
    import numpy as np
except ImportError:
    np = None

logger = logging.getLogger(__name__)

class DenseIndex:
    """Manages dense vector embeddings and pgvector similarity search."""

    def __init__(self):
        self.dimension = settings.EMBEDDING_DIMENSION

    async def get_embedding(self, text_input: str) -> List[float]:
        """
        Generates dense embedding via OpenAI API if key available,
        or deterministic normalized vector fallback for offline execution.
        """
        if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_openai_api_key_here":
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/embeddings",
                        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                        json={"input": text_input, "model": settings.EMBEDDING_MODEL}
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return data["data"][0]["embedding"]
            except Exception as e:
                logger.warning(f"OpenAI embedding failed, using local deterministic fallback: {e}")

        # Deterministic pseudo-embedding for testing / offline execution
        seed = int(hashlib.md5(text_input.encode('utf-8')).hexdigest(), 16) % (2**32)
        random.seed(seed)
        vec = [random.gauss(0, 1) for _ in range(self.dimension)]
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / (norm if norm != 0 else 1.0) for x in vec]

    @staticmethod
    def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    async def search(
        self,
        query: str,
        session: Optional[any] = None,
        top_k: int = 10,
        in_memory_chunks: Optional[List[Dict[str, any]]] = None
    ) -> List[Tuple[str, float]]:
        """
        Queries pgvector database using cosine distance,
        or falls back to in-memory cosine similarity.
        """
        query_vector = await self.get_embedding(query)

        # 1. Database-backed search if session provided
        if session:
            try:
                from sqlalchemy import select
                from app.db.models import ChunkModel
                stmt = (
                    select(ChunkModel.id, ChunkModel.embedding.cosine_distance(query_vector).label("distance"))
                    .order_by("distance")
                    .limit(top_k)
                )
                result = await session.execute(stmt)
                rows = result.all()
                if rows:
                    if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_openai_api_key_here":
                        return [(str(row[0]), float(1.0 - row[1])) for row in rows if (1.0 - float(row[1])) >= 0.25]
                    return [(str(row[0]), float(1.0 - row[1])) for row in rows]
            except Exception as e:
                logger.warning(f"Database pgvector query failed: {e}. Falling back to in-memory.")

        # 2. In-memory search
        if in_memory_chunks:
            scores = []
            for c in in_memory_chunks:
                c_vec = c.get("embedding")
                if c_vec is None:
                    c_vec = await self.get_embedding(c["content"])
                    c["embedding"] = c_vec
                sim = self._cosine_similarity(query_vector, c_vec)
                scores.append((c["chunk_id"], float(sim)))
            scores.sort(key=lambda x: x[1], reverse=True)
            if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_openai_api_key_here":
                filtered = [(cid, sim) for cid, sim in scores if sim >= 0.25]
                return filtered[:top_k]
            return scores[:top_k]

        return []

dense_index = DenseIndex()
