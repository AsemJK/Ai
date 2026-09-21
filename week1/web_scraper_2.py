import requests
from bs4 import BeautifulSoup
import io
import trafilatura
import random
import re
import time
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, urljoin
from typing import List, Optional, Dict

# --- Configuration ---
FASTAPI_URL = "http://localhost:8000"

# Email Configuration (set these or use env vars)
IMAP_SERVER = "outlook.office365.com"       # e.g., imap.gmail.com, outlook.office365.com
IMAP_PORT = 993
EMAIL_ACCOUNT = "[EMAIL_ADDRESS]"
EMAIL_PASSWORD = "[PASSWORD]"  # Use App Password, NOT your real password

# Crawl settings
MIN_CONTENT_LENGTH = 200
CRAWL_DELAY = 1.0  # seconds between requests (be polite)
MAX_CRAWL_DEPTH = 2
MAX_PAGES = 50

# --- Noise patterns to filter out ---
NOISE_URL_PATTERNS = [
    r"contact", r"about", r"terms", r"privacy", r"login",
    r"signin", r"signup", r"cart", r"account", r"checkout",
    r"faq", r"help", r"support", r"cookie", r"policy",
    r"unsubscribe", r"newsletter", r"sitemap", r"search\?",
    r"\.pdf$", r"\.jpg$", r"\.png$", r"\.gif$", r"\.zip$",
    r"javascript:", r"mailto:", r"tel:", r"#",
]

NOISE_HTML_TAGS = [
    "script", "style", "nav", "footer", "header",
    "aside", "noscript", "iframe", "form", "button",
    "svg", "meta", "link", "input", "select", "textarea",
]

NOISE_CSS_CLASSES = [
    "sidebar", "widget", "advertisement", "ad-", "social-share",
    "cookie-banner", "popup", "modal", "menu", "breadcrumb",
    "pagination", "comment", "related-post", "tag-cloud",
]


# ============================================================
# 1. SMART CONTENT EXTRACTION (replaces the old basic method)
# ============================================================

def is_noise_url(url: str) -> bool:
    """Check if a URL matches known noise patterns."""
    url_lower = url.lower()
    return any(re.search(pattern, url_lower) for pattern in NOISE_URL_PATTERNS)


def extract_text_smart(url: str) -> str:
    """
    Primary extractor using trafilatura — it already strips nav, ads,
    footers, sidebars, and boilerplate much better than raw BeautifulSoup.
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            include_links=False,
            include_images=False,
            include_formatting=False,
            no_fallback=False,
        )
        return text or ""
    except Exception as e:
        print(f"[extract_text_smart] Error for {url}: {e}")
        return ""


def extract_text_fallback(url: str) -> str:
    """
    Fallback extractor using BeautifulSoup + aggressive noise removal.
    Used only when trafilatura returns nothing.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # Remove noisy tags entirely
        for tag in soup(NOISE_HTML_TAGS):
            tag.decompose()

        # Remove elements with noisy CSS classes/ids
        for cls in NOISE_CSS_CLASSES:
            for el in soup.find_all(class_=re.compile(cls, re.I)):
                el.decompose()
            for el in soup.find_all(id=re.compile(cls, re.I)):
                el.decompose()

        text = soup.get_text(separator="\n", strip=True)

        # Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text
    except Exception as e:
        print(f"[extract_text_fallback] Error for {url}: {e}")
        return ""


def extract_clean_text(url: str) -> str:
    """
    Best-effort extraction: tries trafilatura first, falls back to BS4.
    Returns empty string if content is too short (likely rubbish).
    """
    text = extract_text_smart(url)
    if len(text) < MIN_CONTENT_LENGTH:
        text = extract_text_fallback(url)
    if len(text) < MIN_CONTENT_LENGTH:
        return ""
    return text


# ============================================================
# 2. LINK DISCOVERY & DEEP CRAWLING
# ============================================================

def discover_links(url: str) -> List[str]:
    """Extract all valid, same-domain, non-noise links from a page."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, "html.parser")
        base_domain = urlparse(url).netloc

        clean_links = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            full_url = urljoin(url, href)

            # Keep only same-domain http(s) links
            if not full_url.startswith("http"):
                continue
            if urlparse(full_url).netloc != base_domain:
                continue
            if is_noise_url(full_url):
                continue

            # Strip fragments
            full_url = full_url.split("#")[0]
            clean_links.add(full_url)

        return list(clean_links)
    except Exception as e:
        print(f"[discover_links] Error: {e}")
        return []


# ============================================================
# 3. INGESTION HELPERS
# ============================================================

def ingest_text(text: str, source: str, doc_id: Optional[str] = None) -> int:
    """Send a chunk of text to the FastAPI ingestion endpoint. Returns chunks added."""
    if not doc_id:
        doc_id = str(random.randint(1, 9_999_999))
    text_io = io.BytesIO(text.encode("utf-8"))
    files = {"file": (f"{doc_id}.txt", text_io, "text/plain")}
    data = {"doc_id": doc_id, "source": source}
    try:
        response = requests.post(
            f"{FASTAPI_URL}/api/v1/ingest-file", files=files, data=data
        )
        if response.status_code == 200:
            return response.json().get("chunks_added", 0)
        else:
            print(f"[ingest_text] Failed ({response.status_code}): {response.text}")
            return 0
    except Exception as e:
        print(f"[ingest_text] Exception: {e}")
        return 0


# ============================================================
# 4. MAIN SCRAPE & INGEST (single page + optional deep crawl)
# ============================================================

def scrape_and_ingest(
    url: str,
    source: str = "web_scrape",
    scan_links: bool = False,
    max_depth: int = MAX_CRAWL_DEPTH,
    max_pages: int = MAX_PAGES,
) -> dict:
    """
    Scrape a URL (and optionally follow links) and ingest clean content.
    """
    if not url.startswith("http"):
        return {"status": "error", "message": "Invalid URL"}

    # --- Get page title for source labelling ---
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.content, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else url
        source_label = f"web_scrape - {title}"
    except Exception:
        source_label = source

    total_chunks = 0
    visited = set()

    def _crawl(current_url: str, depth: int):
        nonlocal total_chunks
        if depth > max_depth or len(visited) >= max_pages:
            return
        if current_url in visited:
            return
        visited.add(current_url)

        print(f"[crawl] depth={depth} | {current_url}")
        text = extract_clean_text(current_url)
        if not text:
            print(f"[crawl] Skipped (too short / empty): {current_url}")
            return

        chunks = ingest_text(text, source_label)
        total_chunks += chunks
        time.sleep(CRAWL_DELAY)

        if depth < max_depth and scan_links:
            child_links = discover_links(current_url)
            for link in child_links:
                _crawl(link, depth + 1)

    _crawl(url, depth=0)
    return {"status": "success", "chunks_added": total_chunks, "pages_crawled": len(visited)}


# ============================================================
# 5. EMAIL READER  (IMAP — Gmail, Outlook, etc.)
# ============================================================

def _decode_mime_header(header_value: str) -> str:
    """Decode an email header (Subject, From, etc.) into a plain string."""
    if not header_value:
        return ""
    parts = decode_header(header_value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _extract_email_body(msg: email.message.Message) -> str:
    """
    Walk through a multipart email and pull out the best text body.
    Prefers text/plain; falls back to stripped text/html.
    """
    plain_parts = []
    html_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            # Skip attachments
            if "attachment" in disposition:
                continue

            payload = part.get_payload(decode=True)
            if not payload:
                continue

            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except Exception:
                continue

            if content_type == "text/plain":
                plain_parts.append(text)
            elif content_type == "text/html":
                html_parts.append(text)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                html_parts.append(text)
            else:
                plain_parts.append(text)

    if plain_parts:
        return "\n".join(plain_parts)

    if html_parts:
        # Strip HTML tags for a clean plain-text version
        raw_html = "\n".join(html_parts)
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style", "head"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)

    return ""


def read_and_ingest_emails(
    folder: str = "INBOX",
    search_criteria: str = "ALL",
    max_emails: int = 50,
    source_prefix: str = "email",
) -> dict:
    """
    Connect to an IMAP mailbox, read conversations, and ingest them
    into the RAG pipeline.

    Parameters
    ----------
    folder : str
        Mailbox folder (e.g. "INBOX", "Sent", "Archive").
    search_criteria : str
        IMAP search string. Examples:
          - "ALL"
          - 'FROM "alice@example.com"'
          - 'SUBJECT "project update"'
          - 'SINCE "01-Jun-2025"'
          - '(FROM "alice@example.com" SUBJECT "invoice")'
    max_emails : int
        Maximum number of emails to process.
    source_prefix : str
        Label prefix for the RAG source metadata.

    Returns
    -------
    dict  with status, emails_read, chunks_added.
    """
    total_chunks = 0
    emails_read = 0

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail.select(folder, readonly=True)

        status, data = mail.search(None, search_criteria)
        if status != "OK":
            return {"status": "error", "message": "IMAP search failed"}

        email_ids = data[0].split()
        # Process newest first
        email_ids = list(reversed(email_ids[:max_emails]))

        for eid in email_ids:
            status, msg_data = mail.fetch(eid, "(RFC822)")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = _decode_mime_header(msg.get("Subject", ""))
            sender = _decode_mime_header(msg.get("From", ""))
            date_str = msg.get("Date", "")
            body = _extract_email_body(msg)

            if len(body.strip()) < 50:
                continue  # skip empty / signature-only emails

            # Build a clean document from the conversation
            document = (
                f"Email Conversation\n"
                f"From: {sender}\n"
                f"Date: {date_str}\n"
                f"Subject: {subject}\n"
                f"---\n"
                f"{body.strip()}"
            )

            source_label = f"{source_prefix} - {subject[:80]}"
            chunks = ingest_text(document, source=source_label)
            total_chunks += chunks
            emails_read += 1
            print(f"[email] Ingested: {subject[:60]}  ({chunks} chunks)")

        mail.logout()

    except imaplib.IMAP4.error as e:
        return {"status": "error", "message": f"IMAP error: {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

    return {
        "status": "success",
        "emails_read": emails_read,
        "chunks_added": total_chunks,
    }


# ============================================================
# 6. QUICK-START EXAMPLES
# ============================================================

if __name__ == "__main__":

    # --- Example 1: Scrape a single page ---
    # result = scrape_and_ingest("https://example.com/article")
    # print(result)

    # --- Example 2: Deep crawl a documentation site ---
    # result = scrape_and_ingest(
    #     "https://docs.example.com",
    #     scan_links=True,
    #     max_depth=2,
    #     max_pages=30,
    # )
    # print(result)

    # --- Example 3: Ingest all inbox emails ---
    result = read_and_ingest_emails(
        folder="INBOX",
        search_criteria="ALL",
        max_emails=20,
    )
    print(result)

    # --- Example 4: Ingest emails from a specific sender ---
    result = read_and_ingest_emails(
        search_criteria='FROM "boss@company.com"',
        max_emails=10,
    )
    print(result)

    # --- Example 5: Ingest recent emails about a topic ---
    result = read_and_ingest_emails(
        search_criteria='SINCE "01-Jun-2025" SUBJECT "project"',
        max_emails=15,
    )
    print(result)