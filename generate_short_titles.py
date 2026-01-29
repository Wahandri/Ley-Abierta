#!/usr/bin/env python3
"""
El Vigilante - Short Title Generator
Generates descriptive, short titles for laws using LLM
"""

import json
import logging
import sys
from pathlib import Path
from tqdm import tqdm
from llm_processor import call_llm_json, get_cache_key, save_to_cache, load_from_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/short_titles.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

INPUT_FILE = Path("data/master_2025.jsonl")
OUTPUT_FILE = Path("data/master_2025_v2.jsonl")

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

def process_file():
    if not INPUT_FILE.exists():
        logger.error(f"Input file not found: {INPUT_FILE}")
        sys.exit(1)

    documents = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                documents.append(json.loads(line))
    
    logger.info(f"Loaded {len(documents)} documents")
    
    updated_docs = []
    processed_count = 0
    
    for doc in tqdm(documents, desc="Generating titles"):
        # Skip if already has short_title (unless empty)
        if doc.get("short_title"):
            updated_docs.append(doc)
            continue
            
        # Prepare context for LLM
        title = doc.get("title_original", "")
        summary = doc.get("summary_plain_es", "")
        # Use summary if available as it is already simplified, otherwise title
        context = f"TÍTULO ORIGINAL: {title}\nRESUMEN: {summary}"
        
        user_prompt = f"""Genera un título corto para esta norma:\n\n{context}"""
        
        # Check cache structure from llm_processor uses simple cache keys
        # We can reuse cache mechanism if we import it, or just call LLM
        # Importing cache functions from llm_processor to maintain consistency
        
        try:
            # Try to get from cache first (if we ran this script partially before)
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
            processed_count += 1
            
        except Exception as e:
            logger.error(f"Error processing {doc.get('id')}: {e}")
            doc["short_title"] = title # Fallback
            
        updated_docs.append(doc)

    # Save output
    logger.info(f"Saving {len(updated_docs)} documents to {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for doc in updated_docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
            
    logger.info("Done!")

if __name__ == "__main__":
    process_file()
