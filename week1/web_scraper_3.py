import requests
from bs4 import BeautifulSoup
import io
import trafilatura
import random
import time
import imaplib
import email
from email.header import decode_header
import re
import html2text
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional, Set
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
FASTAPI_URL = "http://localhost:8000"
REQUEST_DELAY = 1.0          # polite delay between requests (seconds)
MIN_CONTENT_LENGTH = 200     # ignore pages with less text than this
MAX_CRAWL_DEPTH = 2          # how deep to follow links (1 = only direct links)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

# HTML tags that are almost never useful content
NOISE_TAGS = [
    "script", "style", "nav", "footer", "header",
    "aside", "iframe", "noscript", "form", "button",
    "svg", "canvas", "video", "audio", "figure",
    "figcaption", "dialog", "menu", "menuitem",
]

# URL fragments that indicate non-content pages
SKIP_URL_PATTERNS = [
    "contact", "about-us", "about_us", "aboutus",
    "terms", "privacy", "cookie-policy", "cookie_policy",
    "login", "signin", "sign-in", "sign_in",
    "signup", "sign-up", "sign_up", "register",
    "cart", "checkout", "account", "profile",
    "faq", "help", "support", "disclaimer",
    "sitemap", "search", "tag/", "category/",
    "mailto:", "tel:", "javascript:", "#",
    # social / external platforms
    "facebook.com", "twitter.com", "x.com",
    "linkedin.com", "instagram.com", "youtube.com",
    "tiktok.com", "pinterest.com", "reddit.com",
    "whatsapp://", "t.me/", "github.com",
]

# Regex patterns for boilerplate text commonly found in scraped pages
BOILERPLATE_PATTERNS = [
    r"(?i)all rights reserved",
    r"(?i)©\s*\d{4}",
    r"(?i)powered by\s+\w+",
    r"(?i)cookie\s+(consent|policy|settings)",
    r"(?i)accept\s+(all\s+)?cookies",
    r"(?i)subscribe\s+to\s+(our\s+)?newsletter",
    r"(?i)follow\s+us\s+on",
    r"(?i)share\s+(this|on)",
    r"(?i)privacy\s+policy",
    r"(?i)terms\s+of\s+(service|use)",
    r"(?i)this site uses cookies",
    r"(?i)we use cookies to",
]

# ──────────────────────────────────────────────
# 1. Content Extraction
# ──────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Remove boilerplate lines and collapse whitespace."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # skip lines that match boilerplate patterns
        if any(re.search(pat, stripped) for pat in BOILERPLATE_PATTERNS):
            continue
        # skip very short lines that are likely nav items / labels
        if len(stripped) < 15 and not stripped.endswith("."):
            continue
        cleaned.append(stripped)
    return "\n".join(cleaned)


def extract_text_smart(url: str) -> str:
    """
    Primary extractor – uses trafilatura which is excellent at
    isolating main article/body content and discarding ads, nav, etc.
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_precision=True,
        )
        return _clean_text(text) if text else ""
    except Exception as e:
        logger.warning(f"trafilatura failed for {url}: {e}")
        return ""


def extract_text_fallback(url: str) -> str:
    """
    Fallback extractor – improved BeautifulSoup approach with
    aggressive noise removal.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # Remove noise tags
        for tag in soup(NOISE_TAGS):
            tag.decompose()

        # Remove elements with common ad/widget class or id names
        noise_selectors = [
            "[class*='ad-']", "[class*='ads']", "[class*='advert']",
            "[class*='cookie']", "[class*='consent']", "[class*='popup']",
            "[class*='modal']", "[class*='banner']", "[class*='social']",
            "[class*='share']", "[class*='widget']", "[class*='sidebar']",
            "[id*='ad-']", "[id*='cookie']", "[id*='popup']",
        ]
        for selector in noise_selectors:
            for el in soup.select(selector):
                el.decompose()

        text = soup.get_text(separator="\n", strip=True)
        return _clean_text(text)
    except Exception as e:
        logger.warning(f"BS4 fallback failed for {url}: {e}")
        return ""


def extract_text(url: str) -> str:
    """Try smart extraction first, fall back to BS4."""
    text = extract_text_smart(url)
    if len(text) >= MIN_CONTENT_LENGTH:
        return text
    logger.info(f"Smart extraction too short ({len(text)} chars), trying fallback for {url}")
    return extract_text_fallback(url)


def get_page_title(url: str) -> str:
    """Fetch just the <title> of a page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "html.parser")
        return soup.title.string.strip() if soup.title and soup.title.string else url
    except Exception:
        return url


# ──────────────────────────────────────────────
# 2. Link Discovery & Filtering
# ──────────────────────────────────────────────

def _should_skip_url(href: str) -> bool:
    """Return True if the URL matches any skip pattern."""
    href_lower = href.lower()
    return any(pat in href_lower for pat in SKIP_URL_PATTERNS)


def discover_links(url: str) -> List[str]:
    """Fetch a page and return a deduplicated list of valid, same-domain content links."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.content, "html.parser")
    except Exception as e:
        logger.error(f"Failed to fetch {url} for link discovery: {e}")
        return []

    base_domain = urlparse(url).netloc
    seen: Set[str] = set()
    links: List[str] = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        # resolve relative URLs
        full_url = urljoin(url, href)
        # normalise
        parsed = urlparse(full_url)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        if clean_url in seen:
            continue
        if not clean_url.startswith("http"):
            continue
        if _should_skip_url(clean_url):
            continue
        # stay on same domain (optional – remove this check to crawl externally)
        if urlparse(clean_url).netloc != base_domain:
            continue

        seen.add(clean_url)
        links.append(clean_url)

    logger.info(f"Discovered {len(links)} candidate links on {url}")
    return links


# ──────────────────────────────────────────────
# 3. Ingestion Helpers
# ──────────────────────────────────────────────

def _ingest_text(text: str, doc_id: str, source: str) -> Optional[int]:
    """Send a text blob to the FastAPI ingest endpoint. Returns chunks_added or None."""
    text_io = io.BytesIO(text.encode("utf-8"))
    files = {"file": (f"{doc_id}.txt", text_io, "text/plain")}
    data = {"doc_id": doc_id, "source": source}
    try:
        resp = requests.post(
            f"{FASTAPI_URL}/api/v1/ingest-file", files=files, data=data
        )
        if resp.status_code == 200:
            return resp.json().get("chunks_added", 0)
        else:
            logger.error(f"Ingest failed ({resp.status_code}): {resp.text}")
            return None
    except Exception as e:
        logger.error(f"Ingest request error: {e}")
        return None


# ──────────────────────────────────────────────
# 4. Web Scraping & Ingestion (Enhanced)
# ──────────────────────────────────────────────

def scrape_and_ingest(
    url: str,
    source: str = "web_scrape",
    scan_links: bool = False,
    max_depth: int = MAX_CRAWL_DEPTH,
) -> dict:
    """
    Scrape a URL (and optionally its linked pages) and ingest into the RAG store.

    - Uses trafilatura-first extraction for clean main content
    - Deduplicates links, skips junk URLs, stays on same domain
    - Polite delays between requests
    """
    if not url.startswith("http"):
        return {"status": "error", "message": "Invalid URL – must start with http(s)"}

    title = get_page_title(url)
    source_label = f"{title} - {url}"
    total_chunks = 0
    pages_ingested = 0

    # --- Ingest the main URL ---
    text = extract_text(url)
    if len(text) >= MIN_CONTENT_LENGTH:
        doc_id = str(random.randint(1, 9_999_999))
        chunks = _ingest_text(text, doc_id, source_label)
        if chunks is not None:
            total_chunks += chunks
            pages_ingested += 1
            logger.info(f"Ingested main page: {url} | doc_id: {doc_id} | source: {source_label} | ({chunks} chunks)")
    else:
        logger.warning(f"Main page content too short ({len(text)} chars): {url}")

    # --- Optionally crawl linked pages ---
    if scan_links and max_depth >= 1:
        links = discover_links(url)
        for i, link_url in enumerate(links):
            logger.info(f"[{i+1}/{len(links)}] Crawling: {link_url}")
            time.sleep(REQUEST_DELAY)

            link_text = extract_text(link_url)
            if len(link_text) < MIN_CONTENT_LENGTH:
                logger.debug(f"Skipping (too short): {link_url}")
                continue

            doc_id = str(random.randint(1, 9_999_999))
            chunks = _ingest_text(link_text, doc_id, source_label)
            if chunks is not None:
                total_chunks += chunks
                pages_ingested += 1
                logger.info(f"Ingested: {link_url} | doc_id: {doc_id} | source: {source_label} | ({chunks} chunks)")

            # Recursive depth (if max_depth > 1)
            if max_depth > 1:
                sub_result = scrape_and_ingest(
                    link_url,
                    source=source_label,
                    scan_links=True,
                    max_depth=max_depth - 1,
                )
                total_chunks += sub_result.get("chunks_added", 0)
                pages_ingested += sub_result.get("pages_ingested", 0)

    return {
        "status": "success",
        "chunks_added": total_chunks,
        "pages_ingested": pages_ingested,
    }


# ──────────────────────────────────────────────
# 5. Email Reader (NEW)
# ──────────────────────────────────────────────

class EmailReader:
    """
    Reads emails via IMAP and ingests conversations into the RAG store.

    Usage:
        reader = EmailReader("imap.gmail.com", "you@gmail.com", "app-password")
        reader.ingest_folder("INBOX", search_criteria='SINCE "01-Jun-2025"')
    """

    def __init__(self, imap_server: str, email_address: str, password: str):
        self.imap_server = imap_server
        self.email_address = email_address
        self.password = password
        self._h2t = html2text.HTML2Text()
        self._h2t.ignore_links = False
        self._h2t.ignore_images = True
        self._h2t.body_width = 0  # don't wrap

    # ---- connection helpers ----

    def _connect(self) -> imaplib.IMAP4_SSL:
        mail = imaplib.IMAP4_SSL(self.imap_server)
        mail.login(self.email_address, self.password)
        return mail

    # ---- decoding helpers ----

    @staticmethod
    def _decode_header_value(raw: str) -> str:
        if not raw:
            return ""
        parts = decode_header(raw)
        decoded = []
        for content, charset in parts:
            if isinstance(content, bytes):
                decoded.append(content.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(content)
        return " ".join(decoded)

    def _extract_body(self, msg: email.message.Message) -> str:
        """Extract the best text body from an email message."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))
                if "attachment" in disposition:
                    continue
                if ctype == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="replace")
                        break  # prefer plain text
                elif ctype == "text/html" and not body:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        html_str = payload.decode(charset, errors="replace")
                        body = self._h2t.handle(html_str)
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                raw = payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    body = self._h2t.handle(raw)
                else:
                    body = raw
        return body

    # ---- email cleaning ----

    @staticmethod
    def _strip_quoted_text(text: str) -> str:
        """Remove quoted reply chains (lines starting with >, 'On ... wrote:', etc.)."""
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            # stop at common reply markers
            if re.match(r"^(>|\s*>|On\s+.{10,50}\s+wrote:)", line):
                break
            # stop at "---------- Forwarded message ---------"
            if "Forwarded message" in line and "----" in line:
                break
            cleaned.append(line)
        return "\n".join(cleaned).strip()

    @staticmethod
    def _strip_signature(text: str) -> str:
        """Remove email signatures (everything after '-- ' on its own line)."""
        parts = re.split(r"\n--\s*\n", text, maxsplit=1)
        return parts[0].strip()

    @staticmethod
    def _strip_disclaimers(text: str) -> str:
        """Remove common legal disclaimers at the bottom of emails."""
        disclaimer_markers = [
            r"(?i)this\s+(message|email)\s+is\s+(confidential|intended)",
            r"(?i)this\s+communication\s+is\s+(confidential|privileged)",
            r"(?i)disclaimer:",
            r"(?i)confidentiality\s+notice",
            r"(?i)if\s+you\s+have\s+received\s+this\s+(message|email)\s+in\s+error",
            r"(?i)please\s+do\s+not\s+(copy|distribute|forward)",
            r"(?i)the\s+information\s+contained\s+in\s+this",
        ]
        lines = text.split("\n")
        cleaned = []
        for line in lines:
            if any(re.search(pat, line) for pat in disclaimer_markers):
                break  # discard everything from here down
            cleaned.append(line)
        return "\n".join(cleaned).strip()

    def _clean_email_body(self, text: str) -> str:
        """Full cleaning pipeline for email body text."""
        text = self._strip_quoted_text(text)
        text = self._strip_signature(text)
        text = self._strip_disclaimers(text)
        # collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    # ---- thread grouping ----

    def _group_by_thread(self, emails: List[dict]) -> Dict[str, List[dict]]:
        """Group emails by their conversation thread (using subject + references)."""
        threads: Dict[str, List[dict]] = {}
        for em in emails:
            # normalise subject: strip Re:, Fwd:, etc.
            subj = re.sub(r"^(Re|Fw|Fwd):\s*", "", em["subject"], flags=re.IGNORECASE).strip()
            if subj not in threads:
                threads[subj] = []
            threads[subj].append(em)
        # sort each thread chronologically
        for subj in threads:
            threads[subj].sort(key=lambda x: x["date"])
        return threads

    # ---- main ingestion ----

    def ingest_folder(
        self,
        folder: str = "INBOX",
        search_criteria: str = "ALL",
        max_emails: int = 500,
    ) -> dict:
        """
        Connect to IMAP, fetch emails matching `search_criteria`,
        clean & group them by thread, and ingest into the RAG store.

        Common search_criteria examples:
            'ALL'
            'SINCE "01-Jun-2025"'
            'FROM "alice@example.com"'
            'SUBJECT "project update"'
            'UNSEEN'
        """
        mail = self._connect()
        mail.select(folder, readonly=True)

        status, data = mail.search(None, search_criteria)
        if status != "OK":
            return {"status": "error", "message": "IMAP search failed"}

        msg_ids = data[0].split()
        if not msg_ids:
            mail.logout()
            return {"status": "success", "chunks_added": 0, "emails_processed": 0}

        # limit
        msg_ids = msg_ids[-max_emails:]
        logger.info(f"Fetching {len(msg_ids)} emails from {folder}...")

        raw_emails = []
        for mid in msg_ids:
            status, msg_data = mail.fetch(mid, "(RFC822)")
            if status != "OK":
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            subject = self._decode_header_value(msg.get("Subject", ""))
            sender = self._decode_header_value(msg.get("From", ""))
            date_str = msg.get("Date", "")
            body = self._extract_body(msg)
            body = self._clean_email_body(body)

            if len(body) < 50:  # skip nearly-empty emails
                continue

            raw_emails.append({
                "subject": subject,
                "from": sender,
                "date": date_str,
                "body": body,
                "message_id": msg.get("Message-ID", ""),
            })

        mail.logout()

        # Group into threads
        threads = self._group_by_thread(raw_emails)
        total_chunks = 0
        threads_ingested = 0

        for subj, msgs in threads.items():
            # Build a single document per thread
            thread_text_parts = [f"Email Thread: {subj}\n"]
            for m in msgs:
                thread_text_parts.append(
                    f"---\nFrom: {m['from']}\nDate: {m['date']}\n\n{m['body']}\n"
                )
            thread_text = "\n".join(thread_text_parts)

            doc_id = str(random.randint(1, 9_999_999))
            source = f"email - {subj[:80]}"
            chunks = _ingest_text(thread_text, doc_id, source)
            if chunks is not None:
                total_chunks += chunks
                threads_ingested += 1
                logger.info(f"Ingested thread: '{subj}' ({chunks} chunks, {len(msgs)} messages)")

        return {
            "status": "success",
            "chunks_added": total_chunks,
            "emails_processed": len(raw_emails),
            "threads_ingested": threads_ingested,
        }


# ──────────────────────────────────────────────
# 6. Quick CLI / Test
# ──────────────────────────────────────────────
if __name__ == "__main__":
    # --- Example: scrape a website ---
    # result = scrape_and_ingest(
    #     "https://en.wikipedia.org/wiki/Wikipedia:Artificial_intelligence",
    #     scan_links=True,
    #     max_depth=1,
    # )
    # print("Scrape result:", result)

    # --- Example: ingest emails ---
    reader = EmailReader(
        imap_server="outlook.office365.com",
        email_address="[EMAIL_ADDRESS]",
        password="[PASSWORD]",   # use an App Password, not your real password
    )
    email_result = reader.ingest_folder(
        folder="INBOX",
        search_criteria='SINCE "01-Jun-2026"',
    )
    print("Email result:", email_result)