#!/usr/bin/env python3
"""
El Vigilante - BOE Scraper
Scrapes official BOE (Boletín Oficial del Estado) documents and extracts metadata
Author: El Vigilante Team
"""

import argparse
import hashlib
import json
import logging
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

import pdfplumber
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm

# === CONFIGURATION ===
BOE_BASE_URL = "https://www.boe.es"
USER_AGENT = "ElVigilante/1.0 (Transparencia Ciudadana; +https://github.com/elvigilante)"
TIMEOUT = 30
DATA_DIR = Path("../data")
JSONL_DIR = DATA_DIR / "jsonl"
PDF_DIR = DATA_DIR / "pdfs"
LOGS_DIR = Path("./logs")


# Document types we prioritize (Sección I - Disposiciones generales)
PRIORITY_TYPES = [
    "ley",
    "ley orgánica",
    "real decreto-ley",
    "real decreto legislativo",
    "real decreto",
    "orden ministerial",
    "orden",
]

# === LOGGING SETUP ===
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "boe_scraper.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# === UTILITY FUNCTIONS ===
def ensure_directories():
    """Create required directories if they don't exist"""
    for directory in [JSONL_DIR, LOGS_DIR, PDF_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
    logger.info("✓ Directories verified")



def normalize_document_type(raw_type: str) -> str:
    """
    Normalize BOE document type to our schema enum values
    """
    raw_type_lower = raw_type.lower().strip()
    
    type_mapping = {
        "ley orgánica": "ley_organica",
        "ley": "ley",
        "real decreto-ley": "real_decreto_ley",
        "real decreto legislativo": "real_decreto",
        "real decreto": "real_decreto",
        "orden ministerial": "orden_ministerial",
        "orden": "orden",
        "resolución": "resolucion",
        "circular": "circular",
        "instrucción": "instruccion",
        "acuerdo": "acuerdo",
    }
    
    for key, value in type_mapping.items():
        if key in raw_type_lower:
            return value
    
    return "otro"


def classify_topic(title: str, summary: str = "") -> str:
    """
    Simple heuristic classification of document topic
    Based on keywords in title and summary
    """
    text = (title + " " + summary).lower()
    
    # Topic keyword mapping
    topic_keywords = {
        "economía": ["económic", "financier", "fiscal", "impuesto", "tributari", "presupuest", "hacienda"],
        "empleo": ["empleo", "trabajo", "laboral", "trabajador", "desempleo", "salario", "salarial"],
        "sanidad": ["sanit", "salud", "hospit", "médic", "farmac", "covid", "pandemia"],
        "educación": ["educac", "escuela", "universidad", "estudi", "docent", "alumno"],
        "medio_ambiente": ["medio ambiente", "ambient", "ecológ", "sostenib", "clima", "emisiones", "renovable"],
        "justicia": ["justicia", "tribunal", "juez", "judicial", "penal", "civil", "procesal"],
        "vivienda": ["vivienda", "alquiler", "hipoteca", "inmobiliari", "edificación"],
        "tecnología": ["tecnológ", "digital", "telecomunicac", "internet", "ciberseguridad", "dato"],
        "transporte": ["transporte", "tráfico", "movilidad", "ferrocarril", "carretera"],
        "energía": ["energía", "eléctric", "gas", "petról", "energétic"],
        "agricultura": ["agric", "ganad", "pesca", "rural"],
    }
    
    for topic, keywords in topic_keywords.items():
        for keyword in keywords:
            if keyword in text:
                return topic
    
    return "otros"


def calculate_impact_heuristic(doc_type: str, title: str) -> Dict[str, any]:
    """
    Calculate impact index (0-100) based on heuristics
    - Document type (laws > decrees > orders)
    - Scope indicators in title (nacional, general, etc.)
    """
    score = 30  # Base score
    
    # Type-based scoring
    type_scores = {
        "ley": 25,
        "ley_organica": 30,
        "real_decreto_ley": 20,
        "real_decreto": 15,
        "orden_ministerial": 10,
        "orden": 10,
        "resolucion": 5,
    }
    score += type_scores.get(doc_type, 0)
    
    # Scope-based scoring
    title_lower = title.lower()
    if any(word in title_lower for word in ["general", "nacional", "básic", "marco"]):
        score += 20
    if any(word in title_lower for word in ["modifica", "deroga", "reforma"]):
        score += 15
    if "irpf" in title_lower or "impuesto" in title_lower:
        score += 10
    
    # Cap at 100
    score = min(score, 100)
    
    # Generate reason
    impact_level = "bajo" if score < 40 else "medio" if score < 70 else "alto"
    reason = f"Impacto {impact_level} estimado basado en tipo de norma ({doc_type}) y alcance"
    
    return {
        "score": score,
        "reason": reason
    }


# === PDF DOWNLOAD AND TEXT EXTRACTION ===
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def download_pdf(url: str, doc_id: str, date: datetime) -> Optional[Path]:
    """
    Download PDF from BOE
    Returns path to downloaded PDF or None if failed
    """
    try:
        # Create directory structure: data/pdfs/YYYY/MM/
        year = date.strftime("%Y")
        month = date.strftime("%m")
        pdf_dir = PDF_DIR / year / month
        pdf_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate safe filename
        filename = f"{doc_id}.pdf"
        filepath = pdf_dir / filename
        
        # Skip if already downloaded
        if filepath.exists():
            logger.debug(f"PDF already exists: {filepath}")
            return filepath
        
        # Download PDF
        logger.info(f"Downloading PDF: {url}")
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, stream=True)
        response.raise_for_status()
        
        # Save to file
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"✓ Downloaded: {filepath} ({filepath.stat().st_size / 1024:.1f} KB)")
        return filepath
        
    except Exception as e:
        logger.error(f"Failed to download PDF {url}: {e}")
        return None


def extract_text_from_pdf(pdf_path: Path, max_pages: int = 20) -> str:
    """
    Extract text from PDF using pdfplumber
    Limits to first max_pages to avoid processing huge documents
    Returns cleaned text
    """
    try:
        text_parts = []
        
        with pdfplumber.open(pdf_path) as pdf:
            # Limit pages to avoid huge documents
            num_pages = min(len(pdf.pages), max_pages)
            
            logger.info(f"Extracting text from {pdf_path.name} ({num_pages}/{len(pdf.pages)} pages)")
            
            for i, page in enumerate(pdf.pages[:num_pages]):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {i+1}: {e}")
                    continue
        
        # Join and clean text
        full_text = "\n\n".join(text_parts)
        
        # Basic cleaning: remove excessive whitespace
        full_text = re.sub(r'\n{3,}', '\n\n', full_text)  # Max 2 consecutive newlines
        full_text = re.sub(r' {2,}', ' ', full_text)       # Max 1 space
        full_text = full_text.strip()
        
        logger.info(f"✓ Extracted {len(full_text)} characters from {pdf_path.name}")
        return full_text
        
    except Exception as e:
        logger.error(f"Failed to extract text from {pdf_path}: {e}")
        return ""


# === BOE SCRAPING FUNCTIONS ===
def get_boe_summary_url(date: datetime) -> str:
    """
    Get BOE summary URL for a specific date
    Format: https://www.boe.es/boe/dias/YYYY/MM/DD/
    """
    year = date.strftime("%Y")
    month = date.strftime("%m")
    day = date.strftime("%d")
    return f"{BOE_BASE_URL}/boe/dias/{year}/{month}/{day}/"



@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_boe_summary(date: datetime) -> BeautifulSoup:
    """
    Fetch BOE summary page for a given date
    Returns BeautifulSoup object of the summary page
    """
    url = get_boe_summary_url(date)
    logger.info(f"Fetching BOE summary for {date.strftime('%Y-%m-%d')}: {url}")
    
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "lxml")
    return soup


def parse_boe_summary(soup: BeautifulSoup, target_date: datetime) -> List[Dict]:
    """
    Parse BOE summary page and extract document entries
    Returns list of document metadata dicts
    """
    documents = []
    
    # BOE structure: h3 sections followed by ul lists
    # Section I (Disposiciones generales) is our priority
    h3_sections = soup.find_all('h3')
    
    for h3 in h3_sections:
        section_name = h3.get_text(strip=True)
        
        # Filter: only process Sección I and select items from Sección II
        if not any(x in section_name for x in ["I. Disposiciones generales", "II. Autoridades y personal"]):
            continue
        
        # Get the UL that follows this H3
        next_ul = h3.find_next('ul')
        if not next_ul:
            continue
        
        # Find all li items in this section
        items = next_ul.find_all('li', recursive=False)
        
        for item in items:
            try:
                # Extract link
                link_tag = item.find('a')
                if not link_tag:
                    continue
                
                doc_url = urljoin(BOE_BASE_URL, link_tag.get("href", ""))
                link_text = link_tag.get_text(strip=True)
                
                # Get full text (before the link)
                full_text = item.get_text(separator=" ", strip=True)
                
                # The title is typically the text before the PDF link
                # Remove the link text from full text
                title = full_text.replace(link_text, "").strip()
                
                # Clean up common suffixes like "PDF (...)" and "Otros formatos"
                title = re.sub(r'\s*PDF\s*\(.*?\).*$', '', title, flags=re.IGNORECASE)
                title = re.sub(r'\s*Otros formatos.*$', '', title, flags=re.IGNORECASE)
                title = title.strip()
                
                # If title is empty or too short, skip
                if not title or len(title) < 10:
                    continue
                
                # Try to extract department/organism (usually after a period)
                # First, try to find if there's an organism after the main title
                parts = title.split(".", 2)  # Split max 2 times
                if len(parts) >= 2:
                    doc_type_raw = parts[0].strip()
                    remainder = ". ".join(parts[1:]).strip()
                else:
                    doc_type_raw = title.split()[0] if title else "Otro"
                    remainder = ""
                
                # Extract document type
                doc_type = normalize_document_type(doc_type_raw)
                
                # Skip if not priority type and from Section II
                if "II. Autoridades y personal" in section_name and \
                   doc_type not in ["orden", "orden_ministerial", "resolucion"]:
                    continue
                
                # Generate document ID
                date_str = target_date.strftime("%Y-%m-%d")
                title_hash = hashlib.md5(title.encode()).hexdigest()[:8]
                doc_id = f"boe-{date_str}-{doc_type}-{title_hash}"
                
                # Build basic metadata (without LLM-generated content yet)
                metadata = {
                    "id": doc_id,
                    "source": "BOE",
                    "type": doc_type,
                    "title_original": title,
                    "date_published": target_date.isoformat(),
                    "url_oficial": doc_url,
                    "approved_by": remainder if remainder else "No especificado",
                    "section": section_name,
                    "version": "1.0",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                
                documents.append(metadata)
                
            except Exception as e:
                logger.warning(f"Error parsing document entry: {e}")
                continue
    
    return documents


def enrich_metadata_basic(doc: Dict) -> Dict:
    """
    Enrich document metadata with basic heuristic data
    (topic classification, impact index)
    This runs WITHOUT LLM
    """
    # Classify topic
    doc["topic_primary"] = classify_topic(doc["title_original"])
    
    # Calculate impact index
    doc["impact_index"] = calculate_impact_heuristic(doc["type"], doc["title_original"])
    
    # Add placeholder keywords (will be replaced by LLM later)
    doc["keywords"] = ["boe", doc["type"], doc["topic_primary"]]
    
    # Placeholder summary (to be replaced by LLM)
    doc["summary_plain_es"] = f"[Pendiente de procesar] {doc['title_original']}"
    
    # Default affects_to (will be refined by LLM)
    doc["affects_to"] = ["todos_ciudadanos"]
    
    return doc


def save_to_jsonl(documents: List[Dict], date: datetime):
    """
    Save documents to JSONL file (one JSON per line)
    File path: data/jsonl/YYYY/MM/boe-YYYY-MM.jsonl
    """
    year = date.strftime("%Y")
    month = date.strftime("%m")
    
    output_dir = JSONL_DIR / year / month
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / f"boe-{year}-{month}.jsonl"
    
    # Append to JSONL
    with open(output_file, "a", encoding="utf-8") as f:
        for doc in documents:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    
    logger.info(f"✓ Saved {len(documents)} documents to {output_file}")


# === MAIN FLOW ===
def main():
    parser = argparse.ArgumentParser(
        description="El Vigilante - BOE Scraper (sin procesamiento LLM)"
    )
    parser.add_argument(
        "--date",
        type=str,
        default="today",
        help="Date to scrape (YYYY-MM-DD or 'today')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of documents to process (for testing)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print documents without saving to JSONL",
    )
    args = parser.parse_args()
    
    logger.info("=== El Vigilante - BOE Scraper ===")
    
    # Parse date
    if args.date == "today":
        target_date = datetime.now()
    else:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD or 'today'")
            sys.exit(1)
    
    logger.info(f"Target date: {target_date.strftime('%Y-%m-%d')}")
    logger.info(f"Mode: {'DRY-RUN' if args.dry_run else 'SAVE TO JSONL'}")
    
    # Setup
    ensure_directories()
    
    # Fetch BOE summary
    try:
        soup = fetch_boe_summary(target_date)
    except Exception as e:
        logger.error(f"Failed to fetch BOE summary: {e}")
        sys.exit(1)
    
    # Parse documents
    documents = parse_boe_summary(soup, target_date)
    logger.info(f"Found {len(documents)} documents in BOE summary")
    
    if args.limit:
        documents = documents[:args.limit]
        logger.info(f"Limited to {len(documents)} documents")
    
    # Process documents: download PDFs, extract text, enrich metadata
    enriched_docs = []
    for doc in tqdm(documents, desc="Processing documents"):
        # 1. Download PDF
        pdf_path = download_pdf(doc['url_oficial'], doc['id'], target_date)
        if pdf_path:
            doc['pdf_path'] = str(pdf_path.relative_to(DATA_DIR))
            
            # 2. Extract text from PDF
            full_text = extract_text_from_pdf(pdf_path)
            doc['full_text'] = full_text
            doc['text_length'] = len(full_text)
        else:
            doc['pdf_path'] = ""
            doc['full_text'] = ""
            doc['text_length'] = 0
            logger.warning(f"Skipping text extraction for {doc['id']} (PDF download failed)")
        
        # 3. Enrich with basic heuristic metadata
        enriched_doc = enrich_metadata_basic(doc)
        enriched_docs.append(enriched_doc)
    
    # Print or save
    if args.dry_run:
        logger.info("\n=== DRY-RUN: Documents (first 3) ===")
        for doc in enriched_docs[:3]:
            # Don't print full_text in dry run (too long)
            doc_copy = doc.copy()
            if 'full_text' in doc_copy:
                doc_copy['full_text'] = f"[{doc_copy['text_length']} characters]"
            print(json.dumps(doc_copy, indent=2, ensure_ascii=False))
    else:
        save_to_jsonl(enriched_docs, target_date)
    
    # Summary
    logger.info("\n=== SUMMARY ===")
    logger.info(f"Documents processed: {len(enriched_docs)}")
    logger.info(f"PDFs downloaded: {sum(1 for d in enriched_docs if d.get('pdf_path'))}")
    logger.info(f"Text extracted: {sum(1 for d in enriched_docs if d.get('text_length', 0) > 0)}")

    logger.info(f"Date: {target_date.strftime('%Y-%m-%d')}")
    
    # Topic distribution
    topics = {}
    for doc in enriched_docs:
        topic = doc.get("topic_primary", "otros")
        topics[topic] = topics.get(topic, 0) + 1
    
    logger.info(f"Topics: {topics}")
    logger.info("=== DONE ===")


if __name__ == "__main__":
    main()
