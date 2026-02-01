#!/usr/bin/env python3
"""
El Vigilante - Batch LLM Processor
Reads documents from JSONL files and processes them with LLM
Useful for processing documents after scraping them separately
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from llm_processor import process_document_with_llm
from tqdm import tqdm

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def process_jsonl_file(input_file: Path, output_file: Path = None):
    """
    Process all documents in a JSONL file with LLM
    """
    if output_file is None:
        output_file = input_file  # Overwrite in place
    
    logger.info(f"Reading documents from: {input_file}")
    
    # Load documents
    documents = []
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                documents.append(json.loads(line))
    
    logger.info(f"Found {len(documents)} documents")
    
    # Filter only documents that have full_text and haven't been processed yet
    to_process = [doc for doc in documents if doc.get("full_text") and not doc.get("updated_at")]
    logger.info(f"Documents to process: {len(to_process)}")
    
    if not to_process:
        logger.info("No documents to process (all already processed or no text extracted)")
        return
    
    # Process each document
    processed = []
    for doc in tqdm(to_process, desc="Processing with LLM"):
        try:
            processed_doc = process_document_with_llm(doc)
            processed.append(processed_doc)
        except Exception as e:
            logger.error(f"Failed to process {doc.get('id')}: {e}")
            processed.append(doc)  # Keep original
    
    # Merge processed back into full document list
    processed_ids = {doc["id"] for doc in processed}
    for i, doc in enumerate(documents):
        if doc["id"] in processed_ids:
            documents[i] = next(d for d in processed if d["id"] == doc["id"])
    
    # Write updated documents
    logger.info(f"Writing {len(documents)} documents to: {output_file}")
    with open(output_file, "w", encoding="utf-8") as f:
        for doc in documents:
            # Remove full_text from output to save space (keep text_length)
            doc_copy = doc.copy()
            if "full_text" in doc_copy:
                del doc_copy["full_text"]
            f.write(json.dumps(doc_copy, ensure_ascii=False) + "\n")
    
    logger.info("✓ Processing complete")


def main():
    parser = argparse.ArgumentParser(description="El Vigilante - Batch LLM Processor")
    parser.add_argument("input_file", help="Input JSONL file")
    parser.add_argument("--output", "-o", help="Output JSONL file (defaults to overwriting input)")
    args = parser.parse_args()
    
    input_file = Path(args.input_file)
    output_file = Path(args.output) if args.output else input_file
    
    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        sys.exit(1)
    
    process_jsonl_file(input_file, output_file)


if __name__ == "__main__":
    main()
