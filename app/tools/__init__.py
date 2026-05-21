import requests
import os
import re
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv()

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT")
HEADERS = {"User-Agent": SEC_USER_AGENT}

def get_cik(company_name: str) -> str:
    url = "https://efts.sec.gov/LATEST/search-index?q=\"{}\"&forms=10-K".format(company_name)
    response = requests.get(url, headers=HEADERS)
    data = response.json()
    hits = data.get("hits", {}).get("hits", [])
    if not hits:
        raise ValueError(f"No CIK found for {company_name}")
    cik = hits[0]["_source"]["ciks"][0]
    return cik.zfill(10)

def get_main_doc_url(index_url: str) -> str:
    response = requests.get(index_url, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")

    # Look for the main filing htm file by name pattern (company ticker)
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 3:
            link = cells[2].find("a")
            if link:
                href = link["href"]
                # Main filing usually matches ticker pattern and is not an exhibit
                if "/ix?doc=" in href and "exhibit" not in href.lower():
                    raw = href.replace("/ix?doc=", "")
                    return "https://www.sec.gov" + raw

    # Fallback — any htm not labeled exhibit
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) >= 3:
            doc_type = cells[1].text.strip()
            link = cells[2].find("a")
            if link and doc_type in ["10-K", "10-K/A"]:
                href = link["href"]
                if "exhibit" not in href.lower():
                    if "/ix?doc=" in href:
                        raw = href.replace("/ix?doc=", "")
                        return "https://www.sec.gov" + raw
                    return "https://www.sec.gov" + href

    return None

def extract_clean_text(url: str) -> str:
    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")

    # Remove script, style, and XBRL tags
    for tag in soup(["script", "style", "ix:header", "ix:nonnumeric", "ix:nonfraction"]):
        tag.decompose()

    # Get all paragraph and div text — richer than get_text alone
    chunks = []
    for tag in soup.find_all(["p", "div", "span", "td", "h1", "h2", "h3"]):
        text = tag.get_text(separator=" ").strip()
        if len(text) > 60:
            chunks.append(text)

    # Deduplicate while preserving order
    seen = set()
    clean_chunks = []
    for chunk in chunks:
        if chunk not in seen:
            seen.add(chunk)
            clean_chunks.append(chunk)

    full_text = "\n".join(clean_chunks)

    # Remove lines that look like XBRL URLs or metadata
    lines = full_text.splitlines()
    filtered = [l for l in lines if not l.strip().startswith("http") and len(l.strip()) > 40]

    return "\n".join(filtered)

def get_latest_filing_text(company_name: str, form_type: str = "10-K", retries: int = 3) -> dict:
    from app.logger import get_logger
    logger = get_logger("sec_fetcher")
    
    for attempt in range(retries):
        try:
            cik = get_cik(company_name)
            url = f"https://data.sec.gov/submissions/CIK{cik}.json"
            response = requests.get(url, headers=HEADERS, timeout=15)

            if response.status_code == 429:
                wait = 30 * (attempt + 1)
                logger.warning(f"SEC rate limited. Waiting {wait}s...")
                import time
                time.sleep(wait)
                continue

            if response.status_code != 200:
                raise ValueError(f"SEC API error: {response.status_code}")

            data = response.json()
            filings = data["filings"]["recent"]
            forms = filings["form"]
            accessions = filings["accessionNumber"]
            dates = filings["filingDate"]

            for i, form in enumerate(forms):
                if form == form_type:
                    accession_clean = accessions[i].replace("-", "")
                    date = dates[i]
                    index_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_clean}/{accessions[i]}-index.htm"
                    main_doc_url = get_main_doc_url(index_url)

                    if not main_doc_url:
                        raise ValueError("Could not find main document")

                    logger.info(f"Found main doc: {main_doc_url}")
                    content = extract_clean_text(main_doc_url)

                    return {
                        "company": company_name,
                        "cik": cik,
                        "form_type": form_type,
                        "date": date,
                        "accession": accessions[i],
                        "index_url": index_url,
                        "main_doc_url": main_doc_url,
                        "content": content
                    }

            raise ValueError(f"No {form_type} found for {company_name}")

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {str(e)}")
            if attempt == retries - 1:
                raise
    
    raise ValueError(f"Failed after {retries} attempts")

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks