#!/usr/bin/env python3
"""
El Vigilante - Parallel Batch LLM Processor
Processes JSONL files with LLM in parallel to maximize throughput
"""

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict

from llm_processor import process_document_with_llm
from tqdm import tqdm

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/parallel_process.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

def process_single_doc(doc: Dict) -> Dict:
    """Wrapper to handle exceptions for a single doc"""
    try:
        return process_document_with_llm(doc)
    except Exception as e:
        logger.error(f"Error processing {doc.get('id')}: {e}")
        return doc

def process_jsonl_file_parallel(input_file: Path, output_file: Path = None, workers: int = 10):
    """
    Process all documents in a JSONL file with LLM in parallel
    """
    if output_file is None:
        output_file = input_file
    
    logger.info(f"Reading documents from: {input_file}")
    
    documents = []
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    documents.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    
    logger.info(f"Found {len(documents)} documents")
    
    # Filter only documents that have full_text and haven't been processed
    to_process = []
    skipped = []
    
    for doc in documents:
        if doc.get("full_text") and not doc.get("updated_at"):
            to_process.append(doc)
        else:
            skipped.append(doc)
            
    logger.info(f"Documents to process: {len(to_process)} (Skipped: {len(skipped)})")
    
    if not to_process:
        logger.info("No documents to process in this file.")
        return

    processed_results = []
    
    logger.info(f"Starting parallel processing with {workers} workers...")
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Map tasks
        future_to_doc = {executor.submit(process_single_doc, doc): doc for doc in to_process}
        
        # Progress bar
        for future in tqdm(as_completed(future_to_doc), total=len(to_process), desc=f"Processing {input_file.name}"):
            try:
                result = future.result()
                processed_results.append(result)
            except Exception as e:
                doc = future_to_doc[future]
                logger.error(f"Generated exception for {doc.get('id')}: {e}")
                processed_results.append(doc) # Keep original on catastrophe

    # Merge results preserving order
    # Map updated docs by ID for easy lookup
    processed_map = {doc["id"]: doc for doc in processed_results}
    
    final_docs = []
    for doc in documents:
        if doc["id"] in processed_map:
            final_docs.append(processed_map[doc["id"]])
        else:
            final_docs.append(doc)
            
    # Save output
    logger.info(f"Writing {len(final_docs)} documents to: {output_file}")
    with open(output_file, "w", encoding="utf-8") as f:
        for doc in final_docs:
            # Clean up heavy fields for output
            doc_copy = doc.copy()
            if "full_text" in doc_copy:
                del doc_copy["full_text"]
            f.write(json.dumps(doc_copy, ensure_ascii=False) + "\n")
            
    logger.info("✓ File processing complete")

def main():
    parser = argparse.ArgumentParser(description="Parallel LLM Processor")
    parser.add_argument("input_file", type=Path, help="Input JSONL file")
    parser.add_argument("--workers", type=int, default=20, help="Number of parallel workers")
    args = parser.parse_args()
    
    if not args.input_file.exists():
        logger.error(f"Input file not found: {args.input_file}")
        sys.exit(1)
        
    process_jsonl_file_parallel(args.input_file, args.input_file, args.workers)

if __name__ == "__main__":
    main()
