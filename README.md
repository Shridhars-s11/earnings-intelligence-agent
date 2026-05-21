# 📈 Earnings Intelligence Agent

An AI-powered financial research agent that autonomously fetches SEC filings and live news, generates vector embeddings, and synthesizes professional earnings intelligence reports.

Built with LangGraph, Google Gemini, PostgreSQL + pgvector, and FastAPI.

---

## Architecture
User Request
│
▼
Streamlit UI / FastAPI Backend
│
▼
LangGraph Agent Pipeline
│
├── Node 1: Fetch SEC 10-K / 10-Q Filing (EDGAR API)
├── Node 2: Fetch Financial News (NewsAPI)
├── Node 3: Chunk + Embed + Store (pgvector)
├── Node 4: Synthesize (Gemini 2.5 Flash)
└── Node 5: Format Report
│
▼
PostgreSQL + pgvector
(embeddings + reports stored)

---

## Features

- Autonomous SEC EDGAR 10-K and 10-Q filing fetcher
- Live financial news aggregation via NewsAPI
- Vector embeddings stored in PostgreSQL with pgvector
- Semantic search — ask natural language questions about any company
- Embedding cache — skips re-embedding if company already analyzed
- Professional report generation via Gemini 2.5 Flash
- Retry logic on all API calls — handles rate limits and server overload
- Structured logging throughout the pipeline
- Full REST API with FastAPI
- Interactive Streamlit UI with 3 tabs

---

## Tech Stack

| Component | Technology |
|---|---|
| Agent Framework | LangGraph |
| LLM | Google Gemini 2.5 Flash |
| Embeddings | Google Gemini Embedding 001 |
| Database | PostgreSQL + pgvector |
| Backend | FastAPI |
| Frontend | Streamlit |
| Data Sources | SEC EDGAR API + NewsAPI |
| Containerization | Docker + docker-compose |

---

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/Shridhars-s11/earnings-intelligence-agent.git
cd earnings-agent
```

### 2. Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
cp .env.example .env
```

Fill in your API keys in `.env`:
- `GOOGLE_API_KEY` — from [Google AI Studio](https://aistudio.google.com)
- `NEWS_API_KEY` — from [NewsAPI](https://newsapi.org)
- `SEC_USER_AGENT` — your email address (required by SEC EDGAR)
- `POSTGRES_URL` — your PostgreSQL connection string

### 5. Start the database
```bash
docker-compose up -d
```

> Note: Database runs on port 5433 to avoid conflicts with local PostgreSQL installations.

### 6. Run the FastAPI server
```bash
python main.py
```

### 7. Run the Streamlit UI (new terminal)
```bash
streamlit run streamlit_app.py
```

Visit `http://localhost:8501` for the UI or `http://localhost:8000/docs` for API documentation.

---

## API Endpoints

### POST /analyze
Runs the full agent pipeline for a company.
```json
{
  "company": "Apple Inc",
  "form_type": "10-K"
}
```

### POST /search
Semantic search over stored embeddings.
```json
{
  "company": "Apple Inc",
  "question": "What are the main risks Apple faces?",
  "top_k": 5
}
```

### GET /reports
Returns all previously generated reports.

### GET /reports/{report_id}
Returns a specific report by ID.

---

## How It Works

1. You enter a company name in the UI or call `/analyze`
2. The LangGraph agent fetches the latest 10-K or 10-Q from SEC EDGAR
3. The document is chunked and embedded using Gemini Embedding 001
4. Embeddings are stored in PostgreSQL with pgvector for semantic search
5. Live news is fetched from NewsAPI for market context
6. Gemini 2.5 Flash synthesizes a structured analyst report
7. The report is saved to the database and returned via API and UI

---

## Project Structure
earnings-agent/
├── app/
│   ├── agents/
│   │   └── earnings_agent.py    # LangGraph pipeline
│   ├── api/
│   │   └── init.py          # FastAPI endpoints
│   ├── db/
│   │   └── init.py          # PostgreSQL + pgvector
│   ├── tools/
│   │   ├── init.py          # SEC EDGAR fetcher
│   │   ├── embeddings.py        # Gemini embeddings
│   │   └── news.py              # NewsAPI fetcher
│   └── logger.py                # Structured logging
├── streamlit_app.py             # Streamlit UI
├── docker-compose.yml           # Database container
├── main.py                      # Entry point
├── requirements.txt
├── .env.example
└── README.md

---

## Known Limitations

- Synthesis uses the first 6 chunks of the filing — financial tables deeper in the document may not be captured
- Free tier API rate limits may cause delays for large filings
- NewsAPI free tier returns articles up to 1 month old

---

## Future Improvements

- Semantic retrieval of financially dense chunks for more accurate numbers
- Support for multiple companies comparison in one report
- Scheduled background jobs to auto-refresh filings
- Deployment on cloud (Railway, Render, or AWS)