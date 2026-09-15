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

MAX_TEXT_CONTENT_CHARS = 50000

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

@router.get("/documents")
async def list_documents(session: AsyncSession = Depends(get_db)):
    """
    Returns currently indexed documents and their chunk counts.
    """
    try:
        if session is not None:
            from sqlalchemy import select, func
            stmt = select(
                DocumentModel.id,
                DocumentModel.title,
                DocumentModel.created_at,
                func.count(ChunkModel.id).label("chunks_count")
            ).outerjoin(ChunkModel, DocumentModel.id == ChunkModel.doc_id).group_by(
                DocumentModel.id, DocumentModel.title, DocumentModel.created_at
            ).order_by(DocumentModel.created_at.desc())
            res = await session.execute(stmt)
            rows = res.all()
            if rows:
                return [
                    {
                        "doc_id": r.id,
                        "title": r.title,
                        "created_at": r.created_at.isoformat() if r.created_at else "",
                        "chunks_count": r.chunks_count
                    }
                    for r in rows
                ]
    except Exception as e:
        logger.warning(f"Database document listing failed: {e}")

    # Fallback to IN_MEMORY_CHUNKS aggregation
    docs_map = {}
    for c in IN_MEMORY_CHUNKS:
        d_id = c.get("doc_id", "unknown")
        t = c.get("metadata", {}).get("title") or "Document"
        if d_id not in docs_map:
            docs_map[d_id] = {"doc_id": d_id, "title": t, "chunks_count": 0}
        docs_map[d_id]["chunks_count"] += 1

    return list(docs_map.values())

@router.post("/ingest", response_model=DocumentIngestResponse)
async def ingest_document(
    request: DocumentIngestRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Ingests an unstructured document, chunks it, populates the BM25 index,
    computes dense vector embeddings, and persists to pgvector.
    Enforces a strict 50,000-character payload guardrail.
    """
    if not request.text_content or not request.text_content.strip():
        raise HTTPException(
            status_code=400,
            detail="Document text_content cannot be empty."
        )

    if len(request.text_content) > MAX_TEXT_CONTENT_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"Document payload too large: {len(request.text_content):,} characters exceeds the maximum allowed limit of {MAX_TEXT_CONTENT_CHARS:,} characters."
        )

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
                "chunk_index": idx,
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
