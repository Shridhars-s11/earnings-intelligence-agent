import os
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

def get_embeddings(chunks: list) -> list:
    embeddings = []
    for i, chunk in enumerate(chunks):
        retries = 0
        while retries < 5:
            try:
                result = client.models.embed_content(
                    model="models/gemini-embedding-001",
                    contents=chunk,
                )
                embeddings.append(result.embeddings[0].values)
                break
            except Exception as e:
                if "429" in str(e):
                    wait = 60 * (retries + 1)
                    print(f"Rate limited. Waiting {wait}s before retry...")
                    time.sleep(wait)
                    retries += 1
                else:
                    raise e
        if i % 5 == 0:
            print(f"Embedded {i+1}/{len(chunks)} chunks...")
        time.sleep(1)
    return embeddings

def get_single_embedding(text: str) -> list:
    retries = 0
    while retries < 5:
        try:
            result = client.models.embed_content(
                model="models/gemini-embedding-001",
                contents=text,
            )
            return result.embeddings[0].values
        except Exception as e:
            if "429" in str(e):
                wait = 60 * (retries + 1)
                print(f"Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                retries += 1
            else:
                raise e