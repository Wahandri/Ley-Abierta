#!/usr/bin/env python3
"""
El Vigilante - Streaming ETL Pipeline
Optimized "Assembly Line" for simultaneous Extract, Transform, and Load.
"""

import argparse
import json
import logging
import queue
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Import modules (assuming they are in the same directory)
import boe_scraper
import llm_processor
from llm_processor import call_llm_json, get_cache_key, save_to_cache, load_from_cache

# === CONFIGURATION ===
MAX_DOWNLOAD_WORKERS = 5
MAX_LLM_WORKERS = 30
QUEUE_SIZE = 1000  # Buffer size

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(threadName)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/stream_etl.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Silent other loggers to avoid noise
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("pdfplumber").setLevel(logging.WARNING)

# === SHARED QUEUES ===
# Tuple: (priority, doc_object) - priority can be used later, for now just FIFO
download_queue = queue.Queue(maxsize=QUEUE_SIZE)
llm_queue = queue.Queue(maxsize=QUEUE_SIZE)
writer_queue = queue.Queue(maxsize=QUEUE_SIZE)

# Control flags
STOP_EVENT = threading.Event()

# Title Generation Prompt
TITLE_SYSTEM_PROMPT = """Eres un redactor experto que simplifica lenguaje jurídico para ciudadanos.
Tu objetivo: Generar un título BREVE, PERIODÍSTICO y DESCRIPTIVO (máximo 12 palabras) para esta ley.
El título debe capturar la esencia de lo que cambia o aprueba, para que un ciudadano entienda de qué va a primera vista.
IMPORTANTE:
- NO empieces con "Ley...", "Real Decreto...", "Resolución...". Ve directo al grano.
- NO uses números de ley ni fechas.
- Usa lenguaje directo y sencillo.
Responde en JSON: {"short_title": "..."}"""

# === WORKER FUNCTIONS ===

def discovery_worker(year: int, resume_date: Optional[datetime] = None):
    """
    DISCOVERY STAGE
    Iterates days, discovers documents, pushes to Download Queue.
    """
    current_date = datetime(year, 1, 1)
    if resume_date:
        current_date = resume_date
        
    end_date = datetime(year, 12, 31)
    today = datetime.now()
    if end_date > today:
        end_date = today

    logger.info(f"🔎 DISCOVERY STARTED: {current_date.date()} to {end_date.date()}")

    while current_date <= end_date and not STOP_EVENT.is_set():
        date_str = current_date.strftime("%Y-%m-%d")
        
        try:
            # 1. Fetch Summary
            soup = boe_scraper.fetch_boe_summary(current_date)
            
            # 2. Parse Docs
            docs = boe_scraper.parse_boe_summary(soup, current_date)
            
            if docs:
                logger.info(f"Found {len(docs)} docs for {date_str}")
                for doc in docs:
                    download_queue.put(doc)
            else:
                # logger.info(f"No relevant docs for {date_str}")
                pass
                
        except Exception as e:
            logger.error(f"Discovery failed for {date_str}: {e}")

        current_date += timedelta(days=1)
        # Small sleep to be polite to BOE server during discovery
        time.sleep(0.5)

    logger.info("🔎 DISCOVERY FINISHED")
    # Signal buffers? No, we just stop putting. 
    # But we need to signal downstream workers that no more items are coming
    # We'll use a sentinel value or external coordination.

def download_worker_thread():
    """
    EXTRACTION STAGE
    Consumes from download_queue, Downloads PDF, Extracts Text, Pushes to llm_queue.
    """
    while not STOP_EVENT.is_set():
        try:
            doc = download_queue.get(timeout=2)
        except queue.Empty:
            # If discovery is done and queue is empty, we act based on global state
            # For now just continue checking
            continue

        try:
            # Check if PDF exists/Download
            # Hack: convert string date back to object if needed, but scraper handles it
            date_obj = datetime.fromisoformat(doc['date_published'])
            
            pdf_path = boe_scraper.download_pdf(doc['url_oficial'], doc['id'], date_obj)
            
            if pdf_path:
                doc['pdf_path'] = str(pdf_path)
                doc['full_text'] = boe_scraper.extract_text_from_pdf(pdf_path)
                doc['text_length'] = len(doc['full_text'])
            else:
                doc['pdf_path'] = ""
                doc['full_text'] = ""
                doc['text_length'] = 0
            
            # Basic Enrich
            doc = boe_scraper.enrich_metadata_basic(doc)
            
            llm_queue.put(doc)
            
        except Exception as e:
            logger.error(f"Download worker error for {doc.get('id')}: {e}")
        finally:
            download_queue.task_done()

def llm_worker_thread():
    """
    TRANSFORMATION STAGE
    Consumes from llm_queue, Calls LLM (Analysis + Title), Pushes to writer_queue.
    """
    while not STOP_EVENT.is_set():
        try:
            doc = llm_queue.get(timeout=2)
        except queue.Empty:
            continue

        try:
            # 1. LLM Analysis (Summary, Keywords, etc)
            # This function modifies doc in place
            doc = llm_processor.process_document_with_llm(doc)
            
            # 2. Short Title Generation
            # We do this here to save an extra queue/step
            title = doc.get("title_original", "")
            summary = doc.get("summary_plain_es", "")
            
            if not doc.get("short_title"):
                context = f"TÍTULO ORIGINAL: {title}\nRESUMEN: {summary}"
                user_prompt = f"Genera un título corto para esta norma:\n\n{context}"
                
                # We reuse the caching logic manually or via helper
                # Implementing simple cache check here to avoid circular imports issues or complexity
                try:
                    cache_key = get_cache_key("TITLE_GEN_" + user_prompt)
                    cached = load_from_cache(cache_key)
                    if cached:
                        res = json.loads(cached)
                        doc["short_title"] = res.get("short_title", title[:100])
                    else:
                        res = call_llm_json(TITLE_SYSTEM_PROMPT, user_prompt, max_tokens=100)
                        doc["short_title"] = res.get("short_title", title[:100])
                        save_to_cache(cache_key, user_prompt, json.dumps(res))
                except Exception as e:
                    logger.warning(f"Title Gen failed for {doc['id']}: {e}")
                    doc["short_title"] = title[:100]

            writer_queue.put(doc)

        except Exception as e:
            logger.error(f"LLM worker error for {doc.get('id')}: {e}")
            # Even if failed, push to writer so we don't lose the doc (it has basic metadata)
            writer_queue.put(doc)
        finally:
            llm_queue.task_done()

def writer_worker(output_file: Path):
    """
    LOAD STAGE
    Consumes from writer_queue, Appends to JSONL file.
    """
    logger.info(f"💾 Writer ready. Output: {output_file}")
    
    # Ensure directory
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    count = 0
    start_time = time.time()
    
    with open(output_file, "a", encoding="utf-8") as f:
        while not STOP_EVENT.is_set() or not writer_queue.empty():
            try:
                doc = writer_queue.get(timeout=2)
            except queue.Empty:
                continue
            
            # Clean before write (remove heavy full_text)
            doc_copy = doc.copy()
            if "full_text" in doc_copy:
                del doc_copy["full_text"]
                
            f.write(json.dumps(doc_copy, ensure_ascii=False) + "\n")
            f.flush() # Ensure it's written
            
            count += 1
            writer_queue.task_done()
            
            if count % 10 == 0:
                elapsed = time.time() - start_time
                rate = count / elapsed if elapsed > 0 else 0
                print(f"Stats: {count} docs processed. Rate: {rate:.2f} docs/sec. Queues: DL={download_queue.qsize()} LLM={llm_queue.qsize()} WR={writer_queue.qsize()}", end='\r')

def main():
    parser = argparse.ArgumentParser(description="Stream ETL Pipeline")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--output", type=Path, default=Path("data/master_2024_stream.jsonl"))
    args = parser.parse_args()
    
    print("==================================================")
    print(f"🚀 STREAMING ETL PIPELINE - YEAR {args.year}")
    print("==================================================")
    print(f"Output: {args.output}")
    print(f"Threads: {MAX_DOWNLOAD_WORKERS} Downloaders, {MAX_LLM_WORKERS} AI Workers")
    print("==================================================")

    # Start Writer
    writer_t = threading.Thread(target=writer_worker, args=(args.output,), daemon=True)
    writer_t.start()
    
    # Start Download Workers
    extraction_pool = ThreadPoolExecutor(max_workers=MAX_DOWNLOAD_WORKERS, thread_name_prefix="Downloader")
    for _ in range(MAX_DOWNLOAD_WORKERS):
        extraction_pool.submit(download_worker_thread)
        
    # Start LLM Workers
    llm_pool = ThreadPoolExecutor(max_workers=MAX_LLM_WORKERS, thread_name_prefix="LLM")
    for _ in range(MAX_LLM_WORKERS):
        llm_pool.submit(llm_worker_thread)
        
    # Start Discovery (Main Thread blocks here until discovery is done)
    try:
        discovery_worker(args.year)
        
        print("\n\nDiscovery finished. Waiting for queues to drain...")
        
        # Wait for queues to handle all items
        download_queue.join()
        llm_queue.join()
        writer_queue.join()
        
        print("\nAll queues drained. Pipeline complete.")
        
    except KeyboardInterrupt:
        print("\n\n🛑 STOPPING PIPELINE...")
        STOP_EVENT.set()
        
    # Shutdown pools (wait=False to kill immediately if we want, but let's be nice)
    extraction_pool.shutdown(wait=False)
    llm_pool.shutdown(wait=False)
    
    # Stop writer
    STOP_EVENT.set()
    writer_t.join(timeout=2)
    
    print("\n✅ DONE.")

if __name__ == "__main__":
    main()
