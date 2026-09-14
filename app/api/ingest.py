from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models import DocumentModel, ChunkModel
from app.models.schemas import DocumentIngestRequest, DocumentIngestResponse
from app.search.bm25_index import bm25_index
from app.search.dense_index import dense_index
import uuid
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory chunk store for testing/hybrid fallback
IN_MEMORY_CHUNKS = []

def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += (chunk_size - chunk_overlap)
    return chunks

@router.post("/ingest", response_model=DocumentIngestResponse)
async def ingest_document(
    request: DocumentIngestRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Ingests an unstructured document, chunks it, populates the BM25 index,
    computes dense vector embeddings, and persists to pgvector.
    """
    try:
        doc_id = request.doc_id or str(uuid.uuid4())
        raw_chunks = chunk_text(request.text_content, request.chunk_size, request.chunk_overlap)

        # 1. Create Document in DB
        doc_record = DocumentModel(
            id=doc_id,
            title=request.title,
            doc_metadata=request.metadata
        )

        chunk_records = []
        bm25_chunks = []

        for idx, content in enumerate(raw_chunks):
            chunk_id = str(uuid.uuid4())
            embedding = await dense_index.get_embedding(content)

            chunk_record = ChunkModel(
                id=chunk_id,
                doc_id=doc_id,
                chunk_index=idx,
                content=content,
                embedding=embedding,
                chunk_metadata={"title": request.title, **request.metadata}
            )
            chunk_records.append(chunk_record)
            bm25_chunks.append({"chunk_id": chunk_id, "content": content})

            IN_MEMORY_CHUNKS.append({
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "content": content,
                "embedding": embedding,
                "metadata": request.metadata
            })

        # 2. Add to BM25 sparse index
        bm25_index.add_documents(bm25_chunks)

        # 3. Persist to DB if connected
        try:
            session.add(doc_record)
            session.add_all(chunk_records)
            await session.commit()
        except Exception as e:
            logger.warning(f"Database persist skipped/fallback: {e}")

        return DocumentIngestResponse(
            doc_id=doc_id,
            chunks_created=len(raw_chunks),
            status="success"
        )
    except Exception as e:
        logger.error(f"Failed to ingest document: {e}")
        raise HTTPException(status_code=500, detail=str(e))
