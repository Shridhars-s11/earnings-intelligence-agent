from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.agents.earnings_agent import build_agent
from app.db import SessionLocal, Report
from app.db import SessionLocal, Report, semantic_search, company_exists
from app.tools.embeddings import get_single_embedding
from pydantic import BaseModel, field_validator
import uuid

app = FastAPI(title="Earnings Intelligence Agent", version="1.0")

class CompanyRequest(BaseModel):
    company: str
    form_type: str = "10-K"

    @field_validator("form_type")
    @classmethod
    def form_type_must_be_valid(cls, v):
        if v not in ["10-K", "10-Q"]:
            raise ValueError("form_type must be 10-K or 10-Q")
        return v

class ReportResponse(BaseModel):
    company: str
    report: str
    sec_date: str
    news_count: int

@app.get("/")
def root():
    return {"message": "Earnings Intelligence Agent is running"}

@app.post("/analyze", response_model=ReportResponse)
def analyze_company(request: CompanyRequest):
    try:
        agent = build_agent()
        result = agent.invoke({
            "company": request.company,
            "form_type": request.form_type,
            "error": ""
        })

        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])

        # Save report to database
        db = SessionLocal()
        report = Report(
            id=str(uuid.uuid4()),
            company=request.company,
            report_text=result["report"]
        )
        db.add(report)
        db.commit()
        db.close()

        return ReportResponse(
            company=request.company,
            report=result["report"],
            sec_date=result.get("sec_data", {}).get("date", "N/A"),
            news_count=len(result.get("news_articles", []))
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports")
def get_all_reports():
    db = SessionLocal()
    reports = db.query(Report).order_by(Report.created_at.desc()).all()
    db.close()
    return [
        {
            "id": r.id,
            "company": r.company,
            "created_at": str(r.created_at)
        }
        for r in reports
    ]

@app.get("/reports/{report_id}")
def get_report(report_id: str):
    db = SessionLocal()
    report = db.query(Report).filter(Report.id == report_id).first()
    db.close()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "id": report.id,
        "company": report.company,
        "report": report.report_text,
        "created_at": str(report.created_at)
    }

class SearchRequest(BaseModel):
    company: str
    question: str
    top_k: int = 5

    @field_validator("question")
    @classmethod
    def question_must_be_valid(cls, v):
        v = v.strip()
        if len(v) < 5:
            raise ValueError("Question too short")
        if len(v) > 500:
            raise ValueError("Question too long")
        return v

    @field_validator("top_k")
    @classmethod
    def top_k_must_be_valid(cls, v):
        if v < 1 or v > 10:
            raise ValueError("top_k must be between 1 and 10")
        return v

@app.post("/search")
def search_company(request: SearchRequest):
    if not company_exists(request.company):
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {request.company}. Run /analyze first."
        )
    try:
        # Embed the question
        query_embedding = get_single_embedding(request.question)
        
        # Find relevant chunks
        results = semantic_search(query_embedding, request.company, request.top_k)
        
        # Use Gemini to answer based on retrieved chunks
        from google import genai as g
        import os
        c = g.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        
        context = "\n\n".join([r["chunk_text"] for r in results])
        prompt = f"""
Based on the following excerpts from {request.company}'s SEC 10-K filing, answer this question:

Question: {request.question}

Excerpts:
{context}

Give a concise, factual answer based only on the provided excerpts.
"""
        response = c.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=prompt
        )
        
        return {
            "company": request.company,
            "question": request.question,
            "answer": response.text,
            "sources_used": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))