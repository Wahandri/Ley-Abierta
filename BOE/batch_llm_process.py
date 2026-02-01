#!/usr/bin/env python3
"""
Batch LLM Processor for all 2025 JSONL files
Processes each monthly JSONL file with LLM enrichment
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Configuration
PYTHON_BIN = ".venv/bin/python3"
PROCESSOR_SCRIPT = "process_with_llm.py"
JSONL_DIR = Path("data/jsonl/2025")
LOGS_DIR = Path("logs")

def main():
    print("=" * 60)
    print("=== El Vigilante - Batch LLM Processor 2025 ===")
    print("=" * 60)
    
    # Find all JSONL files
    jsonl_files = sorted(JSONL_DIR.glob("*/*.jsonl"))
    
    if not jsonl_files:
        print("❌ No JSONL files found in data/jsonl/2025/")
        sys.exit(1)
    
    print(f"📊 Found {len(jsonl_files)} JSONL files to process")
    print()
    
    # Process each file
    total_files = len(jsonl_files)
    successful = 0
    failed = 0
    
    for i, jsonl_file in enumerate(jsonl_files, 1):
        print(f"[{i}/{total_files}] Processing {jsonl_file.name}...", end=" ", flush=True)
        
        try:
            # Run process_with_llm.py for this file
            result = subprocess.run(
                [PYTHON_BIN, PROCESSOR_SCRIPT, str(jsonl_file)],
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout per file
            )
            
            if result.returncode == 0:
                print("✓")
                successful += 1
            else:
                print("✗")
                print(f"  Error: {result.stderr[:200]}")
                failed += 1
                
        except subprocess.TimeoutExpired:
            print("✗ (timeout)")
            failed += 1
        except Exception as e:
            print(f"✗ ({str(e)[:50]})")
            failed += 1
    
    # Summary
    print()
    print("=" * 60)
    print("=== SUMMARY ===")
    print(f"✓ Successful: {successful}")
    print(f"✗ Failed: {failed}")
    print("=" * 60)
    
    # Save log
    log_file = LOGS_DIR / f"batch_llm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file.write_text(f"Processed: {successful}/{total_files}\\nFailed: {failed}\\n")
    print(f"📝 Log saved to: {log_file}")

if __name__ == "__main__":
    main()
