#!/usr/bin/env python3
"""
El Vigilante - Fase 1: PLACSP Atom Feed Scraper
Scrapes public procurement PDFs from PLACSP (Málaga focus)
Author: El Vigilante Team
"""

import argparse
import hashlib
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm

# === CONFIGURATION ===
PLACSP_FEED_URL = "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
USER_AGENT = "ElVigilante/1.0 (+https://github.com/elvigilante)"
TIMEOUT = 30
DATA_DIR = Path("./data")
RAW_PDFS_DIR = DATA_DIR / "raw_pdfs"
META_DIR = DATA_DIR / "meta"
LOGS_DIR = Path("./logs")
STATE_FILE = Path("./state.json")

# Default Málaga filter terms
DEFAULT_MALAGA_TERMS = [
    "málaga",
    "malaga",
    "ayuntamiento de málaga",
    "ayuntamiento de malaga",
    "junta de gobierno del ayuntamiento de málaga",
    "junta de gobierno del ayuntamiento de malaga",
]

# === LOGGING SETUP ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "vigilante_fetch.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# === UTILITY FUNCTIONS ===
def ensure_directories():
    """Create required directories if they don't exist"""
    for directory in [RAW_PDFS_DIR, META_DIR, LOGS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
    logger.info("✓ Directories verified")


def load_state() -> Dict[str, Set[str]]:
    """Load download state from state.json"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {"downloaded_urls": set(data.get("downloaded_urls", []))}
        except Exception as e:
            logger.warning(f"Could not load state.json: {e}. Starting fresh.")
    return {"downloaded_urls": set()}


def save_state(state: Dict[str, Set[str]]):
    """Save download state to state.json"""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"downloaded_urls": list(state["downloaded_urls"])},
                f,
                indent=2,
                ensure_ascii=False,
            )
        logger.debug("State saved")
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


def save_jsonl(data: dict, filepath: Path):
    """Append a JSON line to a JSONL file"""
    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Failed to write JSONL to {filepath}: {e}")


def generate_safe_filename(url: str, title: str = "") -> str:
    """
    Generate a safe filename for a PDF download
    Format: {sanitized_title}-{url_hash}.pdf
    """
    # Sanitize title
    safe_title = re.sub(r"[^\w\s-]", "", title.lower())
    safe_title = re.sub(r"[-\s]+", "_", safe_title)
    safe_title = safe_title[:50]  # Limit length

    # Generate short hash from URL
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

    if safe_title:
        return f"{safe_title}-{url_hash}.pdf"
    else:
        return f"document-{url_hash}.pdf"


# === ATOM FEED FUNCTIONS ===
def fetch_atom_feed(url: str) -> feedparser.FeedParserDict:
    """Fetch and parse PLACSP Atom feed"""
    logger.info(f"Fetching Atom feed: {url}")
    try:
        response = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        logger.info(f"✓ Fetched {len(feed.entries)} entries from feed")
        return feed
    except requests.RequestException as e:
        logger.error(f"Failed to fetch Atom feed: {e}")
        sys.exit(1)


def filter_malaga_entry(entry: dict, terms: List[str]) -> bool:
    """
    Check if an entry matches Málaga filter criteria
    Searches in: title, summary, content, and raw XML
    """
    # Collect searchable text
    searchable_text = []

    # Title and summary
    searchable_text.append(entry.get("title", ""))
    searchable_text.append(entry.get("summary", ""))

    # Content
    for content in entry.get("content", []):
        searchable_text.append(content.get("value", ""))

    # Combine and search (case-insensitive)
    full_text = " ".join(searchable_text).lower()

    for term in terms:
        if term.lower() in full_text:
            return True

    return False


def extract_pdf_urls(entry: dict) -> List[str]:
    """
    Extract PDF URLs from Atom entry
    Handles:
    1. Direct .pdf links
    2. GetDocumentByIdServlet links
    """
    pdf_urls = []

    # Check all links in entry
    for link in entry.get("links", []):
        href = link.get("href", "")
        if href:
            # Direct PDF links
            if href.lower().endswith(".pdf"):
                pdf_urls.append(href)
            # GetDocumentByIdServlet pattern
            elif "GetDocumentByIdServlet" in href or "documento" in href.lower():
                pdf_urls.append(href)

    # Parse raw XML content for <cbc:URI> elements (more robust)
    for content in entry.get("content", []):
        raw_xml = content.get("value", "")
        # Extract URLs from <cbc:URI> tags
        uri_matches = re.findall(r"<cbc:URI>(https?://[^<]+)</cbc:URI>", raw_xml)
        for uri in uri_matches:
            if uri not in pdf_urls:
                pdf_urls.append(uri)

    return pdf_urls


def fallback_scrape_entry_page(url: str) -> List[str]:
    """
    Fallback: Scrape entry HTML page for PDF links
    Used when Atom feed doesn't contain document URLs
    """
    logger.debug(f"Fallback HTML scraping: {url}")
    try:
        response = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        pdf_urls = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Make absolute URL
            abs_url = urljoin(url, href)
            # Check if it's a PDF
            if abs_url.lower().endswith(".pdf") or "documento" in abs_url.lower():
                pdf_urls.append(abs_url)

        logger.debug(f"Found {len(pdf_urls)} PDF links via HTML scraping")
        return pdf_urls

    except Exception as e:
        logger.warning(f"Fallback HTML scraping failed: {e}")
        return []


def extract_metadata(entry: dict, doc_urls: List[str], scope: str = "Málaga") -> dict:
    """
    Extract structured metadata from Atom entry
    """
    # Parse date
    date_published = entry.get("updated", entry.get("published", ""))
    try:
        date_published = date_parser.parse(date_published).isoformat()
    except:
        date_published = ""

    # Extract contract type from summary (if available)
    summary = entry.get("summary", "")
    contract_type = "unknown"
    type_match = re.search(r"Tipo:\s*(\w+)", summary)
    if type_match:
        contract_type = type_match.group(1)

    metadata = {
        "id": entry.get("id", ""),
        "source": "PLACSP",
        "scope": scope,
        "type": contract_type,
        "title_original": entry.get("title", ""),
        "url_entry": entry.get("link", entry.get("links", [{}])[0].get("href", "")),
        "date_published": date_published,
        "doc_urls": doc_urls,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
    }

    return metadata


# === PDF DOWNLOAD ===
@retry(
    stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10)
)
def download_pdf_with_retry(url: str, output_path: Path) -> bool:
    """
    Download PDF with retry logic and exponential backoff
    Returns True on success, raises exception on failure
    """
    logger.debug(f"Downloading: {url}")
    response = requests.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, stream=True
    )
    response.raise_for_status()

    # Check if content is actually a PDF
    content_type = response.headers.get("Content-Type", "")
    if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
        logger.warning(f"URL may not be a PDF (Content-Type: {content_type}): {url}")

    # Write to file
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return True


def download_pdfs(
    doc_urls: List[str], title: str, state: Dict[str, Set[str]], dry_run: bool = False
) -> List[Dict]:
    """
    Download PDFs from a list of URLs
    Returns list of download results (success/error dicts)
    """
    results = []

    for url in doc_urls:
        # Check if already downloaded
        if url in state["downloaded_urls"]:
            logger.debug(f"Skipping already downloaded: {url}")
            results.append({"url": url, "status": "skipped", "reason": "duplicate"})
            continue

        if dry_run:
            logger.info(f"[DRY-RUN] Would download: {url}")
            results.append({"url": url, "status": "dry_run"})
            continue

        # Generate filename
        filename = generate_safe_filename(url, title)
        output_path = RAW_PDFS_DIR / filename

        try:
            download_pdf_with_retry(url, output_path)
            state["downloaded_urls"].add(url)
            logger.info(f"✓ Downloaded: {filename}")

            result = {
                "url": url,
                "filename": filename,
                "status": "success",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            results.append(result)
            save_jsonl(result, META_DIR / "downloads.jsonl")

        except Exception as e:
            logger.error(f"✗ Failed to download {url}: {e}")
            error_result = {
                "url": url,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            results.append(error_result)
            save_jsonl(error_result, META_DIR / "errors.jsonl")

    return results


# === MAIN FLOW ===
def main():
    parser = argparse.ArgumentParser(
        description="El Vigilante - PLACSP Atom Feed Scraper (Fase 1)"
    )
    parser.add_argument(
        "--limit", type=int, default=50, help="Number of entries to process (default: 50)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate metadata only, skip PDF downloads",
    )
    parser.add_argument(
        "--terms",
        nargs="+",
        default=DEFAULT_MALAGA_TERMS,
        help="Custom Málaga filter terms (space-separated)",
    )
    args = parser.parse_args()

    logger.info("=== El Vigilante - Fase 1: PLACSP Scraper ===")
    logger.info(f"Mode: {'DRY-RUN' if args.dry_run else 'FULL EXECUTION'}")
    logger.info(f"Limit: {args.limit} entries")
    logger.info(f"Filter terms: {args.terms}")

    # Setup
    ensure_directories()
    state = load_state()

    # Fetch feed
    feed = fetch_atom_feed(PLACSP_FEED_URL)

    # Process entries
    processed = 0
    malaga_matches = 0
    total_pdfs_downloaded = 0

    entries_to_process = feed.entries[: args.limit]
    logger.info(f"Processing {len(entries_to_process)} entries...")

    for entry in tqdm(entries_to_process, desc="Processing entries"):
        processed += 1

        # Filter Málaga
        if not filter_malaga_entry(entry, args.terms):
            continue

        malaga_matches += 1
        logger.info(f"\n→ Málaga match: {entry.get('title', 'No title')[:60]}...")

        # Extract PDF URLs
        doc_urls = extract_pdf_urls(entry)

        # Fallback HTML scraping if no URLs found
        if not doc_urls:
            entry_url = entry.get("link", entry.get("links", [{}])[0].get("href", ""))
            if entry_url:
                doc_urls = fallback_scrape_entry_page(entry_url)

        # Extract and save metadata
        metadata = extract_metadata(entry, doc_urls)
        save_jsonl(metadata, META_DIR / "contracts_malaga.jsonl")

        # Download PDFs
        if doc_urls:
            logger.info(f"  Found {len(doc_urls)} document(s)")
            results = download_pdfs(
                doc_urls, entry.get("title", ""), state, dry_run=args.dry_run
            )
            total_pdfs_downloaded += sum(1 for r in results if r["status"] == "success")
        else:
            logger.warning("  No PDF URLs found")

    # Save state
    save_state(state)

    # Summary
    logger.info("\n=== SUMMARY ===")
    logger.info(f"Entries processed: {processed}")
    logger.info(f"Málaga matches: {malaga_matches}")
    logger.info(f"PDFs downloaded: {total_pdfs_downloaded}")
    logger.info(f"Total URLs in state: {len(state['downloaded_urls'])}")
    logger.info(
        f"\n✓ Metadata saved to: {META_DIR / 'contracts_malaga.jsonl'}"
    )
    if not args.dry_run:
        logger.info(f"✓ PDFs saved to: {RAW_PDFS_DIR}")
    logger.info("=== DONE ===")


if __name__ == "__main__":
    main()
