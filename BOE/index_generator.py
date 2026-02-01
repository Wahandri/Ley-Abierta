#!/usr/bin/env python3
"""
El Vigilante - Index Generator
Generates optimized JSON index files for web consumption from JSONL data
Author: El Vigilante Team
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

# === CONFIGURATION ===
DATA_DIR = Path("./data")
JSONL_DIR = DATA_DIR / "jsonl"
INDEX_DIR = DATA_DIR / "index"
LOGS_DIR = Path("./logs")

MAX_LATEST_SIZE_MB = 1  # Max size for latest.json

# === LOGGING SETUP ===
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "index_generator.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# === UTILITY FUNCTIONS ===
def load_jsonl_documents(jsonl_file: Path) -> List[Dict]:
    """Load all documents from a JSONL file"""
    documents = []
    
    if not jsonl_file.exists():
        logger.warning(f"JSONL file not found: {jsonl_file}")
        return documents
    
    with open(jsonl_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    doc = json.loads(line)
                    documents.append(doc)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON line in {jsonl_file}: {e}")
    
    return documents


def get_all_jsonl_files(base_dir: Path) -> List[Path]:
    """Get all JSONL files from the data directory"""
    return sorted(base_dir.rglob("*.jsonl"))


def load_documents_from_date_range(start_date: datetime, end_date: datetime) -> List[Dict]:
    """
    Load all documents within a date range from JSONL files
    """
    documents = []
    
    # Iterate through year/month directories
    current = start_date
    while current <= end_date:
        year = current.strftime("%Y")
        month = current.strftime("%m")
        
        jsonl_file = JSONL_DIR / year / month / f"boe-{year}-{month}.jsonl"
        
        if jsonl_file.exists():
            month_docs = load_jsonl_documents(jsonl_file)
            
            # Filter by date range
            for doc in month_docs:
                try:
                    pub_date = datetime.fromisoformat(doc["date_published"])
                    if start_date <= pub_date <= end_date:
                        documents.append(doc)
                except (KeyError, ValueError):
                    continue
        
        # Move to next month
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    
    return documents


# === INDEX GENERATION FUNCTIONS ===
def generate_latest_json(days: int = 30, output: Path = INDEX_DIR / "latest.json"):
    """
    Generate latest.json with documents from the last N days
    Sorted by date (descending), optimized for web (<1MB)
    """
    logger.info(f"Generating latest index for last {days} days...")
    
    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    # Load documents
    documents = load_documents_from_date_range(start_date, end_date)
    
    logger.info(f"Found {len(documents)} documents in last {days} days")
    
    # Sort by date (descending)
    documents.sort(key=lambda x: x.get("date_published", ""), reverse=True)
    
    # Create index structure
    index = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(documents),
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
        "documents": documents,
    }
    
    # Save to file
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    # Check size
    size_mb = output.stat().st_size / (1024 * 1024)
    logger.info(f"✓ Generated {output} ({size_mb:.2f} MB, {len(documents)} docs)")
    
    if size_mb > MAX_LATEST_SIZE_MB:
        logger.warning(f"latest.json exceeds {MAX_LATEST_SIZE_MB}MB limit. Consider reducing days or optimizing.")


def generate_monthly_index(year: int, month: int, output: Path = None):
    """
    Generate monthly index for a specific year/month
    Output: data/index/YYYY-MM.json
    """
    logger.info(f"Generating monthly index for {year}-{month:02d}...")
    
    # Load JSONL for that month
    jsonl_file = JSONL_DIR / str(year) / f"{month:02d}" / f"boe-{year}-{month:02d}.jsonl"
    documents = load_jsonl_documents(jsonl_file)
    
    if not documents:
        logger.warning(f"No documents found for {year}-{month:02d}")
        return
    
    # Sort by date (descending)
    documents.sort(key=lambda x: x.get("date_published", ""), reverse=True)
    
    # Create index
    index = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "year": year,
        "month": month,
        "count": len(documents),
        "documents": documents,
    }
    
    # Determine output path
    if output is None:
        output = INDEX_DIR / f"{year}-{month:02d}.json"
    
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✓ Generated {output} ({len(documents)} docs)")


def generate_topics_index(output: Path = INDEX_DIR / "topics.json"):
    """
    Generate topics index grouping all documents by topic_primary
    """
    logger.info("Generating topics index...")
    
    # Load all documents
    all_jsonl_files = get_all_jsonl_files(JSONL_DIR)
    
    topics_map = defaultdict(list)
    total_docs = 0
    
    for jsonl_file in all_jsonl_files:
        documents = load_jsonl_documents(jsonl_file)
        total_docs += len(documents)
        
        for doc in documents:
            topic = doc.get("topic_primary", "otros")
            # Store only essential fields to reduce size
            topics_map[topic].append({
                "id": doc.get("id"),
                "title": doc.get("title_original"),
                "date_published": doc.get("date_published"),
                "impact_score": doc.get("impact_index", {}).get("score", 0),
                "url": doc.get("url_oficial"),
            })
    
    # Sort each topic by impact_score (descending)
    for topic in topics_map:
        topics_map[topic].sort(key=lambda x: x.get("impact_score", 0), reverse=True)
    
    # Create index
    index = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_documents": total_docs,
        "topics": dict(topics_map),
        "topic_counts": {topic: len(docs) for topic, docs in topics_map.items()},
    }
    
    # Save
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    size_mb = output.stat().st_size / (1024 * 1024)
    logger.info(f"✓ Generated {output} ({size_mb:.2f} MB, {len(topics_map)} topics)")


# === MAIN ===
def main():
    parser = argparse.ArgumentParser(
        description="El Vigilante - Index Generator for Web Consumption"
    )
    parser.add_argument(
        "--generate-latest",
        action="store_true",
        help="Generate latest.json (last 30 days)",
    )
    parser.add_argument(
        "--generate-monthly",
        type=str,
        metavar="YYYY-MM",
        help="Generate monthly index for specific month (e.g., 2026-01)",
    )
    parser.add_argument(
        "--generate-topics",
        action="store_true",
        help="Generate topics.json (all documents grouped by topic)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all indexes (latest + topics)",
    )
    args = parser.parse_args()
    
    logger.info("=== El Vigilante - Index Generator ===")
    
    # If no args, show help
    if not (args.generate_latest or args.generate_monthly or args.generate_topics or args.all):
        parser.print_help()
        sys.exit(0)
    
    # Generate latest
    if args.generate_latest or args.all:
        generate_latest_json()
    
    # Generate monthly
    if args.generate_monthly:
        try:
            year, month = args.generate_monthly.split("-")
            generate_monthly_index(int(year), int(month))
        except ValueError:
            logger.error(f"Invalid month format: {args.generate_monthly}. Use YYYY-MM")
            sys.exit(1)
    
    # Generate topics
    if args.generate_topics or args.all:
        generate_topics_index()
    
    logger.info("=== DONE ===")


if __name__ == "__main__":
    main()
