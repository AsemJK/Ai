import requests
from bs4 import BeautifulSoup
import io
import trafilatura
import random

# --- Configuration ---
FASTAPI_URL = "http://localhost:8000"

def extract_text_from_url(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.content, "html.parser")
    
    # Remove scripts, styles, nav, footer noise
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    
    return soup.get_text(separator="\n", strip=True)

def scrape_and_ingest(url: str, source: str = "web_scrape",scan_links: bool = False) -> dict:
    # Get title of page 
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    #url validation
    if not url.startswith("http"):
        return {"status": "error", "message": "Invalid URL"}
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.content, "html.parser")
    title = soup.title.string
    source = "web_scrape - " + str(title)
    # scan the url and go through all the links and scrape them
    links = soup.find_all("a")
    total_chunks = 0
    if scan_links:
        for link in links:
            link_url = link.get("href")
            if link_url and link_url.startswith("http"):
                #avoid common web pages links like contact us, about us, terms and conditions, privacy policy
                if "contact" in link_url or "about" in link_url or "terms" in link_url or "privacy" in link_url or "login" in link_url or "signin" in link_url or "signup" in link_url or "cart" in link_url or "account" in link_url or "checkout" in link_url or "faq" in link_url or "help" in link_url or "support" in link_url or "mailto:" in link_url or "tel:" in link_url or "javascript:" in link_url:
                    continue
                link_text = extract_text_from_url(link_url)
                if len(link_text) < 200:
                    continue
                text_io = io.BytesIO(link_text.encode("utf-8"))
                doc_id = str(random.randint(1, 9_999_999))
                files = {
                    "file": (f"{doc_id}.txt", text_io, "text/plain")
                }
                data = {"doc_id": doc_id, "source": source}

                response = requests.post(
                    f"{FASTAPI_URL}/api/v1/ingest-file", files=files, data=data
                )

                if response.status_code != 200:
                    print("Failed to ingest link: ", link_url)
                else:
                    total_chunks += response.json()["chunks_added"]
    else:
        text = extract_text_from_url(url)
        text_io = io.BytesIO(text.encode("utf-8"))
        doc_id = str(random.randint(1, 9_999_999))
        files = {
            "file": (f"{doc_id}.txt", text_io, "text/plain")
        }
        data = {"doc_id": doc_id, "source": source}

        response = requests.post(
            f"{FASTAPI_URL}/api/v1/ingest-file", files=files, data=data
        )

        if response.status_code != 200:
            print("Failed to ingest link: ", url)
        else:
            total_chunks += response.json()["chunks_added"]
    return {"status": "success", "chunks_added": total_chunks}


def extract_text_smart(url: str) -> str:
    downloaded = trafilatura.fetch_url(url)
    text = trafilatura.extract(downloaded)
    return text or ""

def scrape_and_ingest_smart(url: str, source: str = "web_scrape") -> dict:
    text = extract_text_smart(url)
    text_io = io.BytesIO(text.encode("utf-8"))
    source = "web_scraper"
    print("length of text: ", len(text))
    print("source: ", source)
    doc_id = str(random.randint(1, 9_999_999))

    files = {"file": (f"{doc_id}.txt", text_io, "text/plain")}
    data = {"doc_id": doc_id, "source": source}

    response = requests.post(
        f"{FASTAPI_URL}/api/v1/ingest-file", files=files, data=data
    )

    if response.status_code == 200:
        return {"status": "success", "chunks_added": response.json()["chunks_added"]}
    else:
        return {"status": "error", "message": response.json().get("detail")}
