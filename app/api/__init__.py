from fastapi import APIRouter
from .ingest import router as ingest_router
from .query import router as query_router
from .stream import router as stream_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(ingest_router, tags=["Ingestion"])
api_router.include_router(query_router, tags=["Query & Analysis"])
api_router.include_router(stream_router, tags=["Streaming"])

__all__ = ["api_router"]
