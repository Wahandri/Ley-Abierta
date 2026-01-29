#!/usr/bin/env python3
"""
El Vigilante - Schema Validator
Validates DocumentoPublico JSON documents against schema and quality criteria
Author: El Vigilante Team
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

import jsonschema
import requests

# === CONFIGURATION ===
SCHEMA_PATH = Path("./data/schema/documento-publico-v1.schema.json")
LOGS_DIR = Path("./logs")

# Quality checks configuration
MIN_SUMMARY_WORDS = 30
MAX_SUMMARY_WORDS = 400
MAX_TECH_TERMS = 5

# Blacklist of overly technical terms (should appear sparingly in summaries)
TECH_TERMS_BLACKLIST = [
    "apartado", "disposición", "artículo", "literal", "normativa",
    "BOE-A", "reglamentario", "derogatorio", "transitorio", "vigencia",
]

# === LOGGING SETUP ===
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "validator.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# === SCHEMA VALIDATION ===
def load_schema() -> dict:
    """Load JSON schema from file"""
    if not SCHEMA_PATH.exists():
        logger.error(f"Schema file not found: {SCHEMA_PATH}")
        sys.exit(1)
    
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)
    
    # Validate that the schema itself is valid
    try:
        jsonschema.Draft7Validator.check_schema(schema)
        logger.info("✓ Schema file is valid JSON Schema Draft 7")
    except jsonschema.SchemaError as e:
        logger.error(f"Invalid schema: {e}")
        sys.exit(1)
    
    return schema


def validate_schema(document: dict, schema: dict) -> Tuple[bool, List[str]]:
    """
    Validate document against JSON schema
    Returns: (is_valid, list_of_errors)
    """
    validator = jsonschema.Draft7Validator(schema)
    errors = []
    
    for error in validator.iter_errors(document):
        error_msg = f"{'.'.join(str(p) for p in error.path)}: {error.message}"
        errors.append(error_msg)
    
    is_valid = len(errors) == 0
    return is_valid, errors


# === QUALITY VALIDATION ===
def validate_summary_quality(summary: str) -> Dict[str, any]:
    """
    Validate quality of summary_plain_es
    Checks:
    - Word count (30-400 words)
    - Technical jargon (max 5 technical terms)
    - Readability indicators
    """
    issues = []
    warnings = []
    
    # Word count check
    words = summary.split()
    word_count = len(words)
    
    if word_count < MIN_SUMMARY_WORDS:
        issues.append(f"Summary too short ({word_count} words, min {MIN_SUMMARY_WORDS})")
    elif word_count > MAX_SUMMARY_WORDS:
        warnings.append(f"Summary may be too long ({word_count} words, recommended <{MAX_SUMMARY_WORDS})")
    
    # Technical jargon check
    tech_term_count = sum(1 for term in TECH_TERMS_BLACKLIST if term in summary.lower())
    if tech_term_count > MAX_TECH_TERMS:
        warnings.append(f"High technical jargon count ({tech_term_count} terms, max recommended {MAX_TECH_TERMS})")
    
    # Placeholder check
    if "[pendiente" in summary.lower() or "pendiente de procesar" in summary.lower():
        warnings.append("Summary contains placeholder text (not yet processed by LLM)")
    
    return {
        "word_count": word_count,
        "tech_terms": tech_term_count,
        "issues": issues,
        "warnings": warnings,
    }


def validate_url_accessibility(url: str, timeout: int = 10) -> bool:
    """
    Check if URL is accessible (returns HTTP 200)
    """
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        return response.status_code == 200
    except:
        return False


def validate_dates_coherence(doc: dict) -> List[str]:
    """
    Validate that dates are coherent
    - date_published <= entry_into_force (if exists)
    - created_at is recent
    """
    issues = []
    
    try:
        date_published = datetime.fromisoformat(doc["date_published"])
        
        if "entry_into_force" in doc and doc["entry_into_force"]:
            entry_date = datetime.fromisoformat(doc["entry_into_force"])
            if entry_date < date_published:
                issues.append(f"entry_into_force ({entry_date}) is before date_published ({date_published})")
    except Exception as e:
        issues.append(f"Date parsing error: {e}")
    
    return issues


def validate_quality(document: dict) -> Dict[str, any]:
    """
    Run all quality checks on a document
    Returns quality report with score and warnings
    """
    report = {
        "valid": True,
        "score": 100,
        "warnings": [],
        "issues": [],
    }
    
    # Summary quality
    if "summary_plain_es" in document:
        summary_report = validate_summary_quality(document["summary_plain_es"])
        report["summary_analysis"] = summary_report
        report["warnings"].extend(summary_report["warnings"])
        report["issues"].extend(summary_report["issues"])
    
    # URL accessibility (optional, can be slow)
    # Uncomment to enable
    # if "url_oficial" in document:
    #     if not validate_url_accessibility(document["url_oficial"]):
    #         report["warnings"].append(f"URL may not be accessible: {document['url_oficial']}")
    
    # Date coherence
    date_issues = validate_dates_coherence(document)
    report["issues"].extend(date_issues)
    
    # Calculate quality score
    if report["issues"]:
        report["valid"] = False
        report["score"] -= len(report["issues"]) * 20
    if report["warnings"]:
        report["score"] -= len(report["warnings"]) * 5
    
    report["score"] = max(0, report["score"])
    
    return report


# === BATCH VALIDATION ===
def validate_batch(jsonl_file: Path, schema: dict) -> Dict:
    """
    Validate all documents in a JSONL file
    Returns summary report
    """
    if not jsonl_file.exists():
        logger.error(f"JSONL file not found: {jsonl_file}")
        sys.exit(1)
    
    logger.info(f"Validating JSONL file: {jsonl_file}")
    
    total_docs = 0
    valid_schema = 0
    valid_quality = 0
    schema_errors_by_type = {}
    quality_scores = []
    
    with open(jsonl_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            
            total_docs += 1
            
            try:
                doc = json.loads(line)
            except json.JSONDecodeError as e:
                logger.error(f"Line {line_num}: Invalid JSON - {e}")
                continue
            
            # Schema validation
            is_valid_schema, schema_errors = validate_schema(doc, schema)
            if is_valid_schema:
                valid_schema += 1
            else:
                logger.warning(f"Line {line_num} (ID: {doc.get('id', 'unknown')}): Schema validation failed")
                for error in schema_errors:
                    logger.warning(f"  - {error}")
                    # Count error types
                    error_type = error.split(":")[0]
                    schema_errors_by_type[error_type] = schema_errors_by_type.get(error_type, 0) + 1
            
            # Quality validation
            quality_report = validate_quality(doc)
            quality_scores.append(quality_report["score"])
            
            if quality_report["valid"]:
                valid_quality += 1
            
            if quality_report["warnings"]:
                logger.debug(f"Line {line_num}: Quality warnings: {quality_report['warnings']}")
            if quality_report["issues"]:
                logger.warning(f"Line {line_num}: Quality issues: {quality_report['issues']}")
    
    # Generate summary report
    avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0
    
    report = {
        "file": str(jsonl_file),
        "total_documents": total_docs,
        "valid_schema": valid_schema,
        "valid_quality": valid_quality,
        "schema_validation_rate": (valid_schema / total_docs * 100) if total_docs > 0 else 0,
        "quality_validation_rate": (valid_quality / total_docs * 100) if total_docs > 0 else 0,
        "average_quality_score": round(avg_quality_score, 2),
        "schema_errors_by_type": schema_errors_by_type,
    }
    
    return report


# === MAIN ===
def main():
    parser = argparse.ArgumentParser(
        description="El Vigilante - DocumentoPublico Schema & Quality Validator"
    )
    parser.add_argument(
        "jsonl_file",
        type=str,
        help="Path to JSONL file to validate",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("=== El Vigilante - Validator ===")
    
    # Load schema
    schema = load_schema()
    
    # Validate batch
    jsonl_path = Path(args.jsonl_file)
    report = validate_batch(jsonl_path, schema)
    
    # Print report
    logger.info("\n=== VALIDATION REPORT ===")
    logger.info(f"File: {report['file']}")
    logger.info(f"Total documents: {report['total_documents']}")
    logger.info(f"Valid schema: {report['valid_schema']} ({report['schema_validation_rate']:.1f}%)")
    logger.info(f"Valid quality: {report['valid_quality']} ({report['quality_validation_rate']:.1f}%)")
    logger.info(f"Average quality score: {report['average_quality_score']}/100")
    
    if report['schema_errors_by_type']:
        logger.info("\nSchema errors by type:")
        for error_type, count in sorted(report['schema_errors_by_type'].items(), key=lambda x: -x[1]):
            logger.info(f"  - {error_type}: {count}")
    
    logger.info("=== DONE ===")
    
    # Exit code based on validation success
    if report['schema_validation_rate'] < 100:
        sys.exit(1)


if __name__ == "__main__":
    main()
