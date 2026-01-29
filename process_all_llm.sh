#!/bin/bash
# Process all 2025 JSONL files with LLM enrichment

cd /home/wahandri/Documentos/Proyectos/el-vigilante-scraper

echo "=== LLM Processing Started: $(date) ===" 

for file in data/jsonl/2025/*/*.jsonl; do
    echo "[$(date)] Processing $file..."
    .venv/bin/python3 process_with_llm.py "$file"
    if [ $? -eq 0 ]; then
        echo "[$(date)] ✓ $file completed"
    else
        echo "[$(date)] ✗ $file failed"
    fi
done

echo "=== LLM Processing Finished: $(date) ==="
