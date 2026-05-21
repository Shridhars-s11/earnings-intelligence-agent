from sqlalchemy import create_engine, text, Column, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from pgvector.sqlalchemy import Vector
import os
from dotenv import load_dotenv
from datetime import datetime
import uuid

load_dotenv()

POSTGRES_URL = os.getenv("POSTGRES_URL")

engine = create_engine(POSTGRES_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Table 1 — stores raw filings fetched from SEC or News
class Filing(Base):
    __tablename__ = "filings"
    id = Column(String, primary_key=True)
    company = Column(String)
    source = Column(String)        # "sec" or "news"
    doc_type = Column(String)      # "10-K", "10-Q", "article"
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

# Table 2 — stores chunks + their vector embeddings
class EmbeddingChunk(Base):
    __tablename__ = "embedding_chunks"
    id = Column(String, primary_key=True)
    filing_id = Column(String)
    chunk_text = Column(Text)
    embedding = Column(Vector(3072))  # 3072 dims for Gemini embeddings
    created_at = Column(DateTime, default=datetime.utcnow)

# Table 3 — stores final generated reports
class Report(Base):
    __tablename__ = "reports"
    id = Column(String, primary_key=True)
    company = Column(String)
    report_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(engine)
    print("Tables created successfully.")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_connection():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        print("DB connected:", result.fetchone())

def store_filing_and_chunks(company, source, doc_type, content, chunks, embeddings):
    db = SessionLocal()
    try:
        # Store the raw filing
        filing_id = str(uuid.uuid4())
        filing = Filing(
            id=filing_id,
            company=company,
            source=source,
            doc_type=doc_type,
            content=content[:10000]  # store first 10k chars
        )
        db.add(filing)

        # Store each chunk with its embedding
        for chunk_text, embedding in zip(chunks, embeddings):
            chunk = EmbeddingChunk(
                id=str(uuid.uuid4()),
                filing_id=filing_id,
                chunk_text=chunk_text,
                embedding=embedding
            )
            db.add(chunk)

        db.commit()
        print(f"Stored {len(chunks)} chunks for {company}")
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def semantic_search(query_embedding: list, company: str, top_k: int = 5) -> list:
    db = SessionLocal()
    try:
        # Get filing IDs for this company
        filings = db.query(Filing).filter(Filing.company == company).all()
        if not filings:
            return []
        
        filing_ids = [f.id for f in filings]
        
        # pgvector cosine similarity search
        results = db.query(EmbeddingChunk).filter(
            EmbeddingChunk.filing_id.in_(filing_ids)
        ).order_by(
            EmbeddingChunk.embedding.cosine_distance(query_embedding)
        ).limit(top_k).all()
        
        return [
            {
                "chunk_text": r.chunk_text,
                "filing_id": r.filing_id
            }
            for r in results
        ]
    finally:
        db.close()

def company_exists(company: str) -> bool:
    db = SessionLocal()
    try:
        filing = db.query(Filing).filter(Filing.company == company).first()
        return filing is not None
    finally:
        db.close()