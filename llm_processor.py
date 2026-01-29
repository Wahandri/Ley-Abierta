#!/usr/bin/env python3
"""
El Vigilante - LLM Processor
Processes BOE documents with LLM to generate citizen-friendly content
Requires OpenAI API key in .env file
Author: El Vigilante Team
"""

import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

# Load environment variables
load_dotenv()

# === CONFIGURATION ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "500"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))

CACHE_DIR = Path("./data/cache/llm_responses")
LOGS_DIR = Path("./logs")

# === LOGGING SETUP ===
LOGS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "llm_processor.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# === OpenAI CLIENT ===
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY not found in environment. Please set it in .env file")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)


# === CACHE MANAGEMENT ===
def get_cache_key(prompt: str) -> str:
    """Generate cache key from prompt hash"""
    return hashlib.md5(prompt.encode()).hexdigest()


def load_from_cache(cache_key: str) -> Optional[str]:
    """Load LLM response from cache if exists"""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.debug(f"Cache hit: {cache_key}")
                return data.get("response")
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
    return None


def save_to_cache(cache_key: str, prompt: str, response: str):
    """Save LLM response to cache"""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({
                "prompt": prompt,
                "response": response,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": LLM_MODEL,
            }, f, ensure_ascii=False, indent=2)
        logger.debug(f"Cached response: {cache_key}")
    except Exception as e:
        logger.warning(f"Cache write error: {e}")


# === LLM CALLS ===
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
def call_llm_json(system_prompt: str, user_prompt: str, max_tokens: int = 1000) -> Dict:
    """
    Call OpenAI API with strict JSON response format
    Returns parsed JSON dict
    """
    logger.debug(f"Calling LLM ({LLM_MODEL}) with {len(user_prompt)} chars")
    
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=LLM_TEMPERATURE,
        response_format={"type": "json_object"},  # Force JSON output
    )
    
    content = response.choices[0].message.content.strip()
    logger.debug(f"LLM response: {len(content)} chars")
    
    # Parse JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        logger.error(f"Response was: {content[:500]}...")
        raise


# === MAIN PROCESSING FUNCTION ===
def process_document_with_llm(doc: Dict) -> Dict:
    """
    Process a single document with LLM to generate all citizen-oriented fields
    Uses full document text if available, falls back to title only
    Updates the document dict in-place and returns it
    """
    logger.info(f"Processing document with LLM: {doc.get('id', 'unknown')}")
    
    title = doc.get("title_original", "")
    full_text = doc.get("full_text", "")
    
    # Truncate text to avoid token limits (~8000 chars = ~2000 tokens)
    max_text_chars = 8000
    text_excerpt = full_text[:max_text_chars] if full_text else ""
    
    # Build comprehensive prompt
    system_prompt = """Eres un experto en derecho administrativo español que analiza documentos del BOE para hacerlos accesibles al público general.

Tu trabajo es leer documentos oficiales y generar un análisis estructurado en JSON.

IMPORTANTE: Debes responder ÚNICAMENTE con un objeto JSON válido.
NO incluyas markdown (```json), explicaciones, ni texto antes o después del JSON.
El JSON debe tener exactamente esta estructura:

{
  "summary_plain_es": "Resumen en español sencillo (150-300 palabras). Usa segunda persona. Explica qué aprueba, a quién afecta, y qué cambia.",
  "keywords": ["palabra1", "palabra2", ...],
  "affects_to": ["grupo1", "grupo2", ...],
  "transparency_notes": "1-2 frases explicando por qué es importante que los ciudadanos conozcan esto"
}

GRUPOS VÁLIDOS para affects_to: todos_ciudadanos, autónomos, empresas, funcionarios, pensionistas, estudiantes, familias, sector_sanitario, sector_educativo, sector_agrícola, sector_tecnológico, sector_industrial, otros

REGLAS:
- summary_plain_es: 150-300 palabras, segunda persona, sin tecnicismos innecesarios
- keywords: 5-8 palabras o frases cortas, minúsculas, relevantes para búsqueda
- affects_to: 1-3 grupos más relevantes
- transparency_notes: máximo 100 palabras, tono pedagógico"""

    if text_excerpt:
        content_section = f"""CONTENIDO COMPLETO (primeros {max_text_chars} caracteres):
{text_excerpt}"""
    else:
        content_section = "[No se pudo extraer el contenido del PDF]"
    
    user_prompt = f"""Analiza el siguiente documento del BOE:

TÍTULO: {title}

{content_section}

Responde SOLO con el JSON (sin markdown, sin explicaciones):"""

    # Check cache
    cache_key = get_cache_key(user_prompt)
    cached_response = load_from_cache(cache_key)
    if cached_response:
        try:
            result = json.loads(cached_response)
            logger.info("✓ Using cached LLM response")
            # Update document
            doc["summary_plain_es"] = result.get("summary_plain_es", "")
            doc["keywords"] = result.get("keywords", [])
            doc["affects_to"] = result.get("affects_to", ["todos_ciudadanos"])
            doc["transparency_notes"] = result.get("transparency_notes", "")
            doc["updated_at"] = datetime.now(timezone.utc).isoformat()
            return doc
        except Exception as e:
            logger.warning(f"Cache parse error: {e}")
    
    # Call LLM
    try:
        result = call_llm_json(system_prompt, user_prompt, max_tokens=1000)
        
        # Validate and update document
        doc["summary_plain_es"] = result.get("summary_plain_es", f"[Error: no summary] {title}")
        doc["keywords"] = result.get("keywords", ["boe", doc.get("type", "documento")])
        doc["affects_to"] = result.get("affects_to", ["todos_ciudadanos"])
        doc["transparency_notes"] = result.get("transparency_notes", "Documento oficial del BOE.")
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Save to cache
        save_to_cache(cache_key, user_prompt, json.dumps(result))
        
        logger.info(f"✓ Document processed: {doc['id']}")
        
    except Exception as e:
        logger.error(f"Failed to process document with LLM: {e}")
        doc["summary_plain_es"] = f"[Error al procesar] {title}"
        doc["keywords"] = ["boe", doc.get("type", "documento")]
        doc["affects_to"] = ["todos_ciudadanos"]
        doc["transparency_notes"] = "Documento oficial del BOE."
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    return doc


# === CLI (for testing) ===
def main():
    """
    Simple CLI for testing LLM processor with a sample document
    """
    logger.info("=== El Vigilante - LLM Processor Test ===")
    
    # Sample document
    sample_doc = {
        "id": "boe-2026-01-27-real-decreto-test",
        "title_original": "Real Decreto 52/2026, de 26 de enero, por el que se modifica el Reglamento del Impuesto sobre la Renta de las Personas Físicas",
        "type": "real_decreto",
        "date_published": "2026-01-27",
    }
    
    print("\nProcessing sample document:")
    print(json.dumps(sample_doc, indent=2, ensure_ascii=False))
    
    # Process with LLM
    processed = process_document_with_llm(sample_doc)
    
    print("\n=== PROCESSED RESULT ===")
    print(json.dumps(processed, indent=2, ensure_ascii=False))
    
    logger.info("=== DONE ===")


if __name__ == "__main__":
    main()
