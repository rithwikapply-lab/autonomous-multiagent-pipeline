from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey, Float
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
from pgvector.sqlalchemy import Vector
from app.config import settings
import uuid

Base = declarative_base()

class DocumentModel(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    doc_metadata = Column(JSON, default=dict)

    chunks = relationship("ChunkModel", back_populates="document", cascade="all, delete-orphan")

class ChunkModel(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    # Dense vector embedding column
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION), nullable=True)
    chunk_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("DocumentModel", back_populates="chunks")
