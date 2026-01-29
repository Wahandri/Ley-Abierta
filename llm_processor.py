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
def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = LLM_MAX_TOKENS) -> str:
    """
    Call OpenAI API with retry logic
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
    )
    
    content = response.choices[0].message.content.strip()
    logger.debug(f"LLM response: {len(content)} chars")
    
    return content


# === CONTENT GENERATION FUNCTIONS ===
def generate_plain_summary(title: str, boe_text: str = "", max_chars: int = 2000) -> str:
    """
    Generate citizen-friendly summary from BOE title (and optional text excerpt)
    """
    system_prompt = """Eres un traductor de lenguaje jurídico a lenguaje ciudadano para el proyecto 'El Vigilante'.

Tu tarea es explicar leyes, decretos y normativas en español claro y accesible.

REGLAS ESTRICTAS:
- Usa segunda persona ("te afecta si...", "podrás deducir...")
- Evita tecnicismos jurídicos innecesarios (no uses "apartado", "disposición", "literal", etc.)
- Sé conciso: 150-300 palabras máximo
- Explica el impacto real en la vida de las personas
- Si hay cambios, indica qué cambia respecto a antes
- Tono pedagógico, no alarmista ni sensacionalista
- No emitas juicios políticos"""

    # Limit boe_text to avoid token overflow
    boe_excerpt = boe_text[:max_chars] if boe_text else ""
    
    user_prompt = f"""Documento del BOE:

TÍTULO: {title}

{f"EXTRACTO: {boe_excerpt}" if boe_excerpt else ""}

Genera un resumen en lenguaje ciudadano que explique:
1. ¿Qué aprueba este documento?
2. ¿A quién afecta?
3. ¿Qué cambia o qué novedad trae?

Resumen (150-300 palabras):"""

    # Check cache
    cache_key = get_cache_key(user_prompt)
    cached_response = load_from_cache(cache_key)
    if cached_response:
        return cached_response
    
    # Call LLM
    summary = call_llm(system_prompt, user_prompt, max_tokens=600)
    
    # Save to cache
    save_to_cache(cache_key, user_prompt, summary)
    
    return summary


def extract_keywords(title: str, summary: str) -> List[str]:
    """
    Extract 5-8 relevant keywords from title and summary
    """
    system_prompt = """Eres un clasificador de contenido para el proyecto 'El Vigilante'.
Extrae las 5-8 palabras clave más relevantes de documentos del BOE.

REGLAS:
- Solo palabras o frases cortas (1-3 palabras)
- En minúsculas
- Relevantes para búsqueda ciudadana (no jerga jurídica)
- Formato: lista JSON de strings"""

    user_prompt = f"""Documento:

TÍTULO: {title}

RESUMEN: {summary[:500]}

Extrae 5-8 keywords en formato JSON:
["keyword1", "keyword2", ...]"""

    # Check cache
    cache_key = get_cache_key(user_prompt)
    cached_response = load_from_cache(cache_key)
    if cached_response:
        try:
            return json.loads(cached_response)
        except:
            pass
    
    # Call LLM
    response = call_llm(system_prompt, user_prompt, max_tokens=100)
    
    # Parse JSON
    try:
        # Extract JSON array from response
        json_start = response.find("[")
        json_end = response.rfind("]") + 1
        if json_start != -1 and json_end > json_start:
            keywords = json.loads(response[json_start:json_end])
            # Save to cache
            save_to_cache(cache_key, user_prompt, json.dumps(keywords))
            return keywords[:8]  # Max 8
    except Exception as e:
        logger.warning(f"Failed to parse keywords JSON: {e}")
    
    # Fallback: simple word extraction
    return [title.split()[0].lower(), "boe", "normativa"]


def determine_affected_groups(summary: str, title: str = "") -> List[str]:
    """
    Identify affected groups (autónomos, empresas, etc.)
    """
    system_prompt = """Eres un clasificador para 'El Vigilante'.
Identifica a quién afecta un documento del BOE.

GRUPOS POSIBLES:
- todos_ciudadanos
- autónomos
- empresas
- funcionarios
- pensionistas
- estudiantes
- familias
- sector_sanitario
- sector_educativo
- sector_agrícola
- sector_tecnológico
- sector_industrial
- otros

REGLAS:
- Devuelve 1-3 grupos más relevantes
- Formato: lista JSON de strings"""

    user_prompt = f"""Documento:

TÍTULO: {title}

RESUMEN: {summary[:500]}

¿A quién afecta principalmente? Responde en formato JSON:
["grupo1", "grupo2"]"""

    # Check cache
    cache_key = get_cache_key(user_prompt)
    cached_response = load_from_cache(cache_key)
    if cached_response:
        try:
            return json.loads(cached_response)
        except:
            pass
    
    # Call LLM
    response = call_llm(system_prompt, user_prompt, max_tokens=50)
    
    # Parse JSON
    try:
        json_start = response.find("[")
        json_end = response.rfind("]") + 1
        if json_start != -1 and json_end > json_start:
            groups = json.loads(response[json_start:json_end])
            # Save to cache
            save_to_cache(cache_key, user_prompt, json.dumps(groups))
            return groups[:3]  # Max 3
    except Exception as e:
        logger.warning(f"Failed to parse affected groups JSON: {e}")
    
    # Fallback
    return ["todos_ciudadanos"]


def explain_transparency_importance(title: str, summary: str) -> str:
    """
    Generate transparency_notes: why citizens should know about this
    """
    system_prompt = """Eres un educador cívico para 'El Vigilante'.
Explica en 1-2 frases POR QUÉ es importante que la ciudadanía conozca este documento del BOE.

REGLAS:
- Tono pedagógico, no alarmista
- Enfócate en el impacto práctico en sus vidas
- Máximo 100 palabras"""

    user_prompt = f"""Documento:

TÍTULO: {title}

RESUMEN: {summary[:400]}

¿Por qué es importante que los ciudadanos sepan esto?"""

    # Check cache
    cache_key = get_cache_key(user_prompt)
    cached_response = load_from_cache(cache_key)
    if cached_response:
        return cached_response
    
    # Call LLM
    explanation = call_llm(system_prompt, user_prompt, max_tokens=150)
    
    # Save to cache
    save_to_cache(cache_key, user_prompt, explanation)
    
    return explanation


# === MAIN PROCESSING FUNCTION ===
def process_document_with_llm(doc: Dict) -> Dict:
    """
    Process a single document with LLM to generate all citizen-oriented fields
    Updates the document dict in-place and returns it
    """
    logger.info(f"Processing document with LLM: {doc.get('id', 'unknown')}")
    
    title = doc.get("title_original", "")
    
    # 1. Generate plain summary
    try:
        summary = generate_plain_summary(title)
        doc["summary_plain_es"] = summary
    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        doc["summary_plain_es"] = f"[Error al procesar] {title}"
        return doc
    
    # 2. Extract keywords
    try:
        keywords = extract_keywords(title, doc["summary_plain_es"])
        doc["keywords"] = keywords
    except Exception as e:
        logger.error(f"Failed to extract keywords: {e}")
        doc["keywords"] = ["boe", doc.get("type", "documento")]
    
    # 3. Determine affected groups
    try:
        affected = determine_affected_groups(doc["summary_plain_es"], title)
        doc["affects_to"] = affected
    except Exception as e:
        logger.error(f"Failed to determine affected groups: {e}")
        doc["affects_to"] = ["todos_ciudadanos"]
    
    # 4. Explain transparency importance
    try:
        transparency = explain_transparency_importance(title, doc["summary_plain_es"])
        doc["transparency_notes"] = transparency
    except Exception as e:
        logger.error(f"Failed to generate transparency notes: {e}")
        doc["transparency_notes"] = "Documento oficial del BOE que puede afectar a la ciudadanía."
    
    # Update timestamp
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    logger.info(f"✓ Document processed: {doc['id']}")
    
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
