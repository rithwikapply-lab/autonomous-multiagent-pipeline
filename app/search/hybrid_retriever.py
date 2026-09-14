from typing import List, Dict, Any, Optional
from app.config import settings
from app.search.bm25_index import bm25_index
from app.search.dense_index import dense_index
import logging

logger = logging.getLogger(__name__)

class HybridRetriever:
    """
    Executes Reciprocal Rank Fusion (RRF) combining:
    - Sparse BM25 lexical keyword ranking
    - Dense pgvector semantic embedding ranking

    RRF Formula: RRF_Score(d) = sum_{m in M} (1 / (k + rank_m(d)))
    where k is a smoothing constant (typically 60).
    """

    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k

    async def retrieve(
        self,
        query: str,
        session: Optional[Any] = None,
        top_k: int = 5,
        in_memory_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        # Auto-sync BM25 index from DB if session provided and index empty
        if session and not bm25_index.chunk_ids:
            try:
                from sqlalchemy import select
                from app.db.models import ChunkModel
                stmt = select(ChunkModel)
                db_res = await session.execute(stmt)
                db_chunks = db_res.scalars().all()
                if db_chunks:
                    bm25_index.add_documents([{"chunk_id": c.id, "content": c.content} for c in db_chunks])
            except Exception as e:
                logger.warning(f"BM25 index auto-sync from DB skipped: {e}")

        # 1. Sparse Search
        sparse_results = bm25_index.search(query, top_k=settings.TOP_K_SPARSE)

        # 2. Dense Search
        dense_results = await dense_index.search(
            query=query,
            session=session,
            top_k=settings.TOP_K_DENSE,
            in_memory_chunks=in_memory_chunks
        )

        # 3. Reciprocal Rank Fusion
        rrf_scores: Dict[str, float] = {}

        # Process Sparse Ranks
        for rank, (chunk_id, _) in enumerate(sparse_results, start=1):
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (self.rrf_k + rank))

        # Process Dense Ranks
        for rank, (chunk_id, _) in enumerate(dense_results, start=1):
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + (1.0 / (self.rrf_k + rank))

        # Sort by final RRF score descending
        sorted_ranks = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)[:top_k]

        # Hydrate chunk objects
        results = []
        chunk_map = {c["chunk_id"]: c for c in (in_memory_chunks or [])}

        if session:
            missing_ids = [cid for cid, _ in sorted_ranks if cid not in chunk_map]
            if missing_ids:
                try:
                    from sqlalchemy import select
                    from app.db.models import ChunkModel
                    stmt = select(ChunkModel).where(ChunkModel.id.in_(missing_ids))
                    db_res = await session.execute(stmt)
                    for cm in db_res.scalars().all():
                        chunk_map[cm.id] = {
                            "chunk_id": cm.id,
                            "doc_id": cm.doc_id,
                            "chunk_index": cm.chunk_index,
                            "content": cm.content,
                            "metadata": cm.chunk_metadata or {}
                        }
                except Exception as e:
                    logger.warning(f"Database chunk hydration fallback: {e}")
        
        for chunk_id, rrf_score in sorted_ranks:
            if chunk_id in chunk_map:
                chunk = dict(chunk_map[chunk_id])
                chunk["rrf_score"] = round(rrf_score, 5)
                results.append(chunk)
            else:
                results.append({
                    "chunk_id": chunk_id,
                    "doc_id": "unknown",
                    "chunk_index": 0,
                    "rrf_score": round(rrf_score, 5),
                    "content": f"[Content for chunk {chunk_id}]"
                })

        return results

hybrid_retriever = HybridRetriever(rrf_k=settings.RRF_K)
