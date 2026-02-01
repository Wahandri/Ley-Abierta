#!/bin/bash
cd "$(dirname "$0")"
#!/bin/bash
# etl_2024_fast.sh - Hyper-Accelerated ETL pipeline for El Vigilante 2024
# Helper script to run the pipeline with high concurrency

set -e

echo "=========================================================="
echo "=== El Vigilante - FAST ETL Pipeline 2024 (Turbo Mode) ==="
echo "=========================================================="
echo "Running with 20 concurrent threads for AI processing"
echo ""

# Activate venv
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# PASO 1: EXTRACT (Resume or Start)
echo "=== PASO 1: EXTRACT (Cosecha) ==="
echo "Verificando descargas de BOE..."
# We use resume-from to pick up where we left off or ensure completion
# If harvest is complete, this will just verify quickly
# Getting the last downloaded date or just starting from Jan 1 with logic to skip existing is handled by scraper
# But harvest_year.py iterates days. Let's just run it, it skips checking if --resume-from is not used but files exist?
# Actually harvest_year checks if scraper returns success. Scraper downloads PDF.
# We will assume user wants to continue harvesting if it was interrupted.
# To be safe, let's run harvest_year.py normally. It should be relatively fast if PDFs exist.
# However, for "Fast" mode, maybe we assume Extraction is done or running separately? 
# The user asked to "accelerate the process".
# Let's run harvest in the background or just run it safely.
# Since extraction is single threaded, we can't speed it up much without rewriting harvest_year.
# BUT, we can run process_llm IN PARALLEL with harvest if we wanted, but that's complex.
# Let's just run harvest first. It skips existing PDFs effectively?
# Checking harvest_year.py code: run_scraper_for_date -> boe_scraper.py -> download_pdf (checks if exists)
# So re-running harvest_year is safe and efficient enough.
python3 harvest_year.py --year 2024

echo ""
echo "✓ PASO 1 completado"
echo ""

# PASO 2: TRANSFORM PARALLEL
echo "=== PASO 2: TRANSFORM (Procesamiento LLM Paralelo) ==="
echo "Enriqueciendo documentos con IA (20 hilos)..."

if [ ! -d "data/jsonl/2024" ]; then
    echo "Error: No data directory found."
    exit 1
fi

count=$(find data/jsonl/2024 -name "*.jsonl" | wc -l)
echo "Processing $count files in parallel..."

# Run parallel processor on each file sequentially (but each file is processed in parallel internally)
# Or we could just find all files and run them.
find data/jsonl/2024 -name "*.jsonl" | while read f; do
    echo "Processing $f..."
    python3 process_with_llm_parallel.py "$f" --workers 20
done

echo ""
echo "✓ PASO 2 completado"
echo ""

# PASO 3: LOAD
echo "=== PASO 3: LOAD (Fusión en Maestro) ==="
echo "Fusionando todos los archivos JSONL en master_2024.jsonl..."
find data/jsonl/2024 -name "*.jsonl" -type f | sort | xargs cat > data/master_2024.jsonl

echo ""
echo "✓ PASO 3 completado"
echo ""

# PASO 4: SHORT TITLES PARALLEL
echo "=== PASO 4: GENERACIÓN TÍTULOS CORTOS (Paralelo) ==="
echo "Generando títulos cortos con 30 hilos..."
python3 generate_short_titles_parallel.py --input data/master_2024.jsonl --output data/master_2024.jsonl --workers 30

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

echo "=============================================="
echo "✓✓✓ FAST PIPELINE COMPLETADO ✓✓✓"
echo "=============================================="
