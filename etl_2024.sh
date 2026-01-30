#!/bin/bash
# etl_2024.sh - Complete ETL pipeline for El Vigilante 2024 Master Database

set -e  # Exit on any error

# Activate venv if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo "=============================================="
echo "=== El Vigilante - ETL Pipeline 2024 ==="
echo "=============================================="
echo ""

# PASO 1: EXTRACT
echo "=== PASO 1: EXTRACT (Cosecha Masiva 2024) ==="
echo "Iniciando descarga de todos los BOE de 2024..."
python3 harvest_year.py --year 2024

echo ""
echo "✓ PASO 1 completado"
echo ""

# PASO 2: TRANSFORM
echo "=== PASO 2: TRANSFORM (Procesamiento LLM) ==="
echo "Enriqueciendo documentos con IA..."

# Check if there are files to process
if [ ! -d "data/jsonl/2024" ]; then
    echo "Directory data/jsonl/2024 does not exist. EXTRACT step might have failed."
    exit 1
fi

count=$(find data/jsonl/2024 -name "*.jsonl" | wc -l)
if [ "$count" -eq "0" ]; then
    echo "No JSONL files found for 2024. EXTRACT step might have failed."
    exit 1
fi

echo "Processing $count files..."
find data/jsonl/2024 -name "*.jsonl" | while read f; do
    echo "Processing $f..."
    python3 process_with_llm.py "$f"
done

echo ""
echo "✓ PASO 2 completado"
echo ""

# PASO 3: LOAD
echo "=== PASO 3: LOAD (Fusión en Maestro) ==="
echo "Fusionando todos los archivos JSONL en master_2024.jsonl..."
# Sort to ensure chronological order if filenames have date
find data/jsonl/2024 -name "*.jsonl" -type f | sort | xargs cat > data/master_2024.jsonl

echo ""
echo "✓ PASO 3 completado"
echo ""

# PASO 4: SHORT TITLES
echo "=== PASO 4: GENERACIÓN TÍTULOS CORTOS ==="
echo "Generando títulos cortos para master_2024.jsonl..."
python3 generate_short_titles.py --input data/master_2024.jsonl --output data/master_2024.jsonl

echo ""
echo "✓ PASO 4 completado"
echo ""

# VERIFICACIÓN
echo "=== VERIFICACIÓN ==="
total_docs=$(wc -l < data/master_2024.jsonl)
file_size=$(du -h data/master_2024.jsonl | cut -f1)

echo "📊 Total documentos: $total_docs"
echo "💾 Tamaño archivo: $file_size"
echo ""

# Validar JSON
if cat data/master_2024.jsonl | jq -c . > /dev/null 2>&1; then
    echo "✓ JSON válido"
else
    echo "⚠️  Advertencia: Algunos documentos pueden tener JSON malformado"
fi

echo ""
echo "=============================================="
echo "✓✓✓ ETL PIPELINE 2024 COMPLETADO ✓✓✓"
echo "=============================================="
echo ""
echo "Archivo maestro generado en: data/master_2024.jsonl"
