#!/bin/bash
cd "$(dirname "$0")"
#!/bin/bash
# etl_full_pipeline.sh - Complete ETL pipeline for El Vigilante 2025 Master Database

set -e  # Exit on any error

echo "=============================================="
echo "=== El Vigilante - ETL Pipeline 2025 ==="
echo "=============================================="
echo ""

# PASO 1: EXTRACT
echo "=== PASO 1: EXTRACT (Cosecha Masiva) ==="
echo "Iniciando descarga de todos los BOE de 2025..."
python3 harvest_year.py --year 2025

echo ""
echo "✓ PASO 1 completado"
echo ""

# PASO 2: TRANSFORM
echo "=== PASO 2: TRANSFORM (Procesamiento LLM) ==="
echo "Enriqueciendo documentos con IA..."
python3 process_with_llm.py --input-dir data/jsonl/2025/ --recursive

echo ""
echo "✓ PASO 2 completado"
echo ""

# PASO 3: LOAD
echo "=== PASO 3: LOAD (Fusión en Maestro) ==="
echo "Fusionando todos los archivos JSONL en master_2025.jsonl..."
find data/jsonl/2025/ -name "*_enriched.jsonl" -type f | sort | xargs cat > data/master_2025.jsonl

echo ""
echo "✓ PASO 3 completado"
echo ""

# VERIFICACIÓN
echo "=== VERIFICACIÓN ==="
total_docs=$(wc -l < data/master_2025.jsonl)
file_size=$(du -h data/master_2025.jsonl | cut -f1)

echo "📊 Total documentos: $total_docs"
echo "💾 Tamaño archivo: $file_size"
echo ""

# Validar JSON
if cat data/master_2025.jsonl | jq -c . > /dev/null 2>&1; then
    echo "✓ JSON válido"
else
    echo "⚠️  Advertencia: Algunos documentos pueden tener JSON malformado"
fi

echo ""
echo "=============================================="
echo "✓✓✓ ETL PIPELINE COMPLETADO ✓✓✓"
echo "=============================================="
echo ""
echo "Archivo maestro generado en: data/master_2025.jsonl"
echo "Listo para ser consumido por la web estática"
