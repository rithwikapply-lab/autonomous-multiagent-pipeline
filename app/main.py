from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.api import api_router
from app.db.session import init_db
import logging

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pipeline")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing Autonomous Multi-Agent Pipeline services...")
    await init_db()
    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models import ChunkModel
        from app.search.bm25_index import bm25_index
        from app.api.ingest import IN_MEMORY_CHUNKS
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            stmt = select(ChunkModel)
            res = await session.execute(stmt)
            chunks = res.scalars().all()
            if chunks:
                bm25_chunks = [{"chunk_id": c.id, "content": c.content} for c in chunks]
                bm25_index.add_documents(bm25_chunks)
                for c in chunks:
                    if not any(ic["chunk_id"] == c.id for ic in IN_MEMORY_CHUNKS):
                        IN_MEMORY_CHUNKS.append({
                            "chunk_id": c.id,
                            "doc_id": c.doc_id,
                            "chunk_index": c.chunk_index,
                            "content": c.content,
                            "embedding": c.embedding,
                            "metadata": c.chunk_metadata or {}
                        })
                logger.info(f"Synchronized {len(chunks)} chunks from database into BM25 index and memory cache.")
    except Exception as e:
        logger.warning(f"Startup chunk synchronization skipped: {e}")
    yield
    # Shutdown
    logger.info("Shutting down services.")

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Autonomous Multi-Agent Analysis Pipeline with Hybrid Search (BM25 + pgvector), Cross-Encoder Reranker, and DeepEval Verification.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "features": {
            "hybrid_search": True,
            "pgvector_support": True,
            "reranking": True,
            "multi_agent_workflow": True,
            "streaming_sse": True
        }
    }
