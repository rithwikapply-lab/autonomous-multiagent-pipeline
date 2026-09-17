import pytest
import pytest_asyncio
import httpx
from app.main import app
from app.db.session import AsyncSessionLocal
from app.db.models import DocumentModel
from app.api.ingest import IN_MEMORY_CHUNKS
from sqlalchemy import delete
import logging

logger = logging.getLogger(__name__)

@pytest_asyncio.fixture(loop_scope="session")
async def async_client():
    """Asynchronous HTTP test client using ASGITransport bound to FastAPI app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest_asyncio.fixture(loop_scope="function")
async def test_doc_tracker():
    """
    Tracks document IDs created during tests and guarantees teardown cleanup
    from PostgreSQL and IN_MEMORY_CHUNKS to prevent test corpus growth.
    """
    created_doc_ids = []
    yield created_doc_ids

    # Teardown
    if created_doc_ids:
        try:
            async with AsyncSessionLocal() as session:
                for doc_id in created_doc_ids:
                    await session.execute(delete(DocumentModel).where(DocumentModel.id == doc_id))
                await session.commit()
        except Exception as e:
            logger.warning(f"Failed to clean up test docs from DB ({e})")

        # Clean in-memory chunk store
        IN_MEMORY_CHUNKS[:] = [c for c in IN_MEMORY_CHUNKS if c.get("doc_id") not in created_doc_ids]
