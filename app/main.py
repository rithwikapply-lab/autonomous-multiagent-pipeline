from fastapi import FastAPI
from fastapi.middleware.cors import CORSMouter = None
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
