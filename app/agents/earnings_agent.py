from langgraph.graph import StateGraph, END
from typing import TypedDict, List
from app.tools import get_latest_filing_text, chunk_text
from app.tools.embeddings import get_embeddings
from app.tools.news import get_financial_news
from app.db import store_filing_and_chunks
from app.logger import get_logger
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

logger = get_logger("earnings_agent")
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# State — this is what gets passed between every node
class AgentState(TypedDict, total=False):
    company: str
    sec_data: dict
    news_articles: list
    chunks: list
    embeddings: list
    synthesis: str
    report: str
    error: str
    form_type: str

# Node 1 — fetch SEC filing
def fetch_sec_node(state: AgentState) -> AgentState:
    logger.info(f"Fetching SEC filing for {state['company']}")
    try:
        result = get_latest_filing_text(state["company"], state.get("form_type", "10-K"))
        state["sec_data"] = result
        logger.info(f"SEC filing fetched. Date: {result['date']}")
    except Exception as e:
        logger.error(f"SEC fetch failed: {str(e)}")
        state["error"] = f"SEC fetch failed: {str(e)}. Try the exact company name e.g. 'JPMorgan Chase'"
    return state

# Node 2 — fetch news
def fetch_news_node(state: AgentState) -> AgentState:
    logger.info(f"\n[Agent] Fetching news for {state['company']}...")
    try:
        articles = get_financial_news(state["company"], max_articles=5)
        state["news_articles"] = articles
        logger.info(f"[Agent] Fetched {len(articles)} news articles.")
    except Exception as e:
        state["error"] = f"News fetch failed: {str(e)}"
    return state

# Node 3 — chunk and embed SEC filing
def embed_node(state: AgentState) -> AgentState:
    if state.get("error"):
        return state
    if not state.get("sec_data"):
        state["error"] = "No SEC data available to embed."
        return state
    logger.info("Checking if embeddings already exist...")
    try:
        from app.db import company_exists
        if company_exists(state["company"]):
            logger.info(f"Embeddings already exist for {state['company']}. Skipping.")
            chunks = chunk_text(state["sec_data"]["content"])
            state["chunks"] = chunks
            state["embeddings"] = []
            return state

        logger.info("Chunking and embedding SEC filing...")
        chunks = chunk_text(state["sec_data"]["content"])
        embeddings = get_embeddings(chunks)
        store_filing_and_chunks(
            company=state["company"],
            source="sec",
            doc_type=state["sec_data"]["form_type"],
            content=state["sec_data"]["content"],
            chunks=chunks,
            embeddings=embeddings
        )
        state["chunks"] = chunks
        state["embeddings"] = embeddings
        logger.info(f"Stored {len(chunks)} chunks.")
    except Exception as e:
        logger.error(f"Embed error: {str(e)}")
        state["error"] = f"Embedding failed: {str(e)}"
    return state

# Node 4 — synthesize everything with Gemini
def synthesize_node(state: AgentState) -> AgentState:
    if state.get("error"):
        return state
    if not state.get("chunks"):
        state["error"] = "No chunks available for synthesis."
        return state
    logger.info("Synthesizing findings...")
    try:
        sec_context = "\n".join(state["chunks"][:6])

        news_context = ""
        for a in state.get("news_articles", []):
            news_context += f"- {a['title']} ({a['source']}): {a['content'][:300]}\n"

        prompt = f"""
You are a senior financial analyst at a top investment bank.

Analyze {state['company']} based on their latest SEC 10-K filing and recent news.

SEC 10-K Filing Excerpts:
{sec_context}

Recent Market News:
{news_context}

Write a professional earnings intelligence brief with these exact sections:

## Company Overview
2-3 sentences on what the company does and its market position.

## Financial Highlights
Key revenue, profit, growth metrics mentioned in the filing. If specific numbers exist, include them.

## Risk Factors
Top 3-5 risks explicitly mentioned in the filing with brief explanation of each.

## News Sentiment
Summarize the market mood from recent news. Is coverage positive, negative or mixed?

## Investment Outlook
Bullish / Neutral / Bearish — with a 3-4 sentence justification based on the data above.

Be factual. Only use information from the provided sources. Do not hallucinate numbers.
"""
        # Retry logic for 503 and 429
        import time
        retries = 5
        for attempt in range(retries):
            try:
                response = client.models.generate_content(
                    model="models/gemini-2.5-flash",
                    contents=prompt
                )
                state["synthesis"] = response.text
                logger.info("Synthesis complete.")
                break
            except Exception as e:
                error_str = str(e)
                if "503" in error_str or "429" in error_str:
                    wait = 30 * (attempt + 1)
                    logger.warning(f"Gemini overloaded. Waiting {wait}s before retry {attempt+1}/{retries}...")
                    time.sleep(wait)
                    if attempt == retries - 1:
                        raise
                else:
                    raise

    except Exception as e:
        logger.error(f"Synthesis error: {str(e)}")
        state["error"] = f"Synthesis failed: {str(e)}"
    return state

# Node 5 — format final report
def report_node(state: AgentState) -> AgentState:
    logger.info(f"\n[Agent] Formatting final report...")
    synthesis = state.get("synthesis", "Synthesis not available.")
    sec_date = state.get("sec_data", {}).get("date", "N/A")
    sec_url = state.get("sec_data", {}).get("index_url", "N/A")

    report = f"""
====================================================
EARNINGS INTELLIGENCE REPORT
Company: {state['company']}
SEC Filing Date: {sec_date}
====================================================

{synthesis}

====================================================
SOURCES
====================================================
SEC Filing: {sec_url}
News Articles:
"""
    for a in state.get("news_articles", []):
        report += f"- {a['title']} ({a['published'][:10]})\n"

    state["report"] = report
    return state

# Edge condition — stop if error
def should_continue(state: AgentState) -> str:
    if state.get("error"):
        logger.info(f"[Agent] Error: {state['error']}")
        return END
    return "continue"

# Build the graph
def build_agent():
    graph = StateGraph(AgentState)

    graph.add_node("fetch_sec", fetch_sec_node)
    graph.add_node("fetch_news", fetch_news_node)
    graph.add_node("embed", embed_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("report", report_node)

    graph.set_entry_point("fetch_sec")
    graph.add_edge("fetch_sec", "fetch_news")
    graph.add_edge("fetch_news", "embed")
    graph.add_edge("embed", "synthesize")
    graph.add_edge("synthesize", "report")
    graph.add_edge("report", END)

    return graph.compile()