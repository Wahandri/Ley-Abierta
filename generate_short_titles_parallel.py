#!/usr/bin/env python3
"""
El Vigilante - Parallel Short Title Generator
Generates descriptive, short titles for laws using LLM in parallel
"""

import json
import logging
import sys
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from llm_processor import call_llm_json, get_cache_key, save_to_cache, load_from_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/short_titles_parallel.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres un redactor experto que simplifica lenguaje jurídico para ciudadanos.
Tu objetivo: Generar un título BREVE, PERIODÍSTICO y DESCRIPTIVO (máximo 12 palabras) para esta ley.
El título debe capturar la esencia de lo que cambia o aprueba, para que un ciudadano entienda de qué va a primera vista.
IMPORTANTE:
- NO empieces con "Ley...", "Real Decreto...", "Resolución...". Ve directo al grano.
- NO uses números de ley ni fechas.
- Usa lenguaje directo y sencillo.

Ejemplos:
- Original: "Real Decreto-ley 2/2025... medidas urgentes..." -> Titulo corto: "Nuevas medidas urgentes contra la sequía y ayudas al campo"
- Original: "Resolución... lista de admitidos..." -> Titulo corto: "Lista de admitidos para oposiciones de Hacienda"
- Original: "Orden... tipos de interés..." -> Titulo corto: "Actualización de tipos de interés oficiales para 2025"

Responde en JSON: {"short_title": "..."}"""

def generate_title_for_doc(doc):
    """Generate title for a single doc"""
    # Skip if already has short_title (unless empty)
    if doc.get("short_title"):
        return doc
        
    try:
        title = doc.get("title_original", "")
        summary = doc.get("summary_plain_es", "")
        context = f"TÍTULO ORIGINAL: {title}\nRESUMEN: {summary}"
        
        user_prompt = f"""Genera un título corto para esta norma:\n\n{context}"""
        
        # Check cache logic
        cache_key = get_cache_key("TITLE_GEN_" + user_prompt)
        cached = load_from_cache(cache_key)
        
        if cached:
            result = json.loads(cached)
            short_title = result.get("short_title", title[:100])
        else:
            # Call LLM
            result = call_llm_json(SYSTEM_PROMPT, user_prompt, max_tokens=100)
            short_title = result.get("short_title", title[:100])
            
            # Save to cache
            save_to_cache(cache_key, user_prompt, json.dumps(result))
        
        doc["short_title"] = short_title
        return doc
        
    except Exception as e:
        logger.error(f"Error processing {doc.get('id')}: {e}")
        doc["short_title"] = doc.get("title_original", "")[:100] # Fallback
        return doc

def process_file_parallel(input_path: Path, output_path: Path, workers: int = 20):
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        sys.exit(1)

    logger.info(f"Reading documents from {input_path}")
    documents = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    documents.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    
    logger.info(f"Loaded {len(documents)} documents")
    
    processed_results = []
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_doc = {executor.submit(generate_title_for_doc, doc): doc for doc in documents}
        
        for future in tqdm(as_completed(future_to_doc), total=len(documents), desc="Generating titles"):
            try:
                result = future.result()
                processed_results.append(result)
            except Exception as e:
                logger.error(f"Worker exception: {e}")
                processed_results.append(future_to_doc[future])

    # Re-sort to maintain original order if possible, or just save
    # Since we act on a list, order might be scrambled by as_completed
    # We can reconstruct order using IDs or index if needed, but for jsonl order is often less critical
    # Let's try to simple sort by ID or just dump results (jsonl usually implies no specific order unless time)
    
    logger.info(f"Saving {len(processed_results)} documents to {output_path}")
    with open(output_path, "w", encoding="utf-8") as f:
        for doc in processed_results:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
            
    logger.info("Done!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate short titles for laws in parallel")
    parser.add_argument("--input", "-i", type=Path, required=True, help="Input JSONL file")
    parser.add_argument("--output", "-o", type=Path, required=True, help="Output JSONL file")
    parser.add_argument("--workers", "-w", type=int, default=20, help="Number of workers")
    
    args = parser.parse_args()
    process_file_parallel(args.input, args.output, args.workers)
