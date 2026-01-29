#!/bin/bash
# El Vigilante - Pipeline Test Script
# Tests complete workflow: scrape → LLM process → validate → index

set -e  # Exit on error

echo "========================================="
echo "El Vigilante - Pipeline Test"
echo "========================================="
echo ""

# Activate virtual environment
source .venv/bin/activate

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}[1/6] Verificando API key de OpenAI...${NC}"
if grep -q "TU_API_KEY_AQUI" .env; then
    echo "❌ Error: Debes reemplazar 'TU_API_KEY_AQUI' con tu clave real en .env"
    exit 1
fi
echo -e "${GREEN}✓ API key configurada${NC}"
echo ""

echo -e "${YELLOW}[2/6] Scraping BOE (fecha reciente, 5 documentos)...${NC}"
./boe_scraper.py --date 2026-01-27 --limit 5
echo -e "${GREEN}✓ Scraping completado${NC}"
echo ""

echo -e "${YELLOW}[3/6] Probando LLM processor con documento de ejemplo...${NC}"
./llm_processor.py
echo -e "${GREEN}✓ LLM processor funciona${NC}"
echo ""

echo -e "${YELLOW}[4/6] Validando documentos scraped...${NC}"
./validator.py data/jsonl/2026/01/boe-2026-01.jsonl
echo -e "${GREEN}✓ Validación completada${NC}"
echo ""

echo -e "${YELLOW}[5/6] Generando índices para web...${NC}"
./index_generator.py --generate-latest
echo -e "${GREEN}✓ Índices generados${NC}"
echo ""

echo -e "${YELLOW}[6/6] Resumen de resultados...${NC}"
echo ""

# Count documents
DOC_COUNT=$(wc -l < data/jsonl/2026/01/boe-2026-01.jsonl 2>/dev/null || echo "0")
echo "📄 Documentos scraped: $DOC_COUNT"

# Check if latest.json exists
if [ -f "data/index/latest.json" ]; then
    LATEST_COUNT=$(cat data/index/latest.json | grep -o '"count": [0-9]*' | grep -o '[0-9]*' || echo "0")
    echo "📊 Documentos en latest.json: $LATEST_COUNT"
fi

# Show sample document
echo ""
echo "📋 Documento de ejemplo (primero en JSONL):"
head -n 1 data/jsonl/2026/01/boe-2026-01.jsonl | python3 -m json.tool | head -20
echo "..."

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}✓ Pipeline test completado exitosamente${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Próximos pasos:"
echo "1. Revisar: data/jsonl/2026/01/boe-2026-01.jsonl"
echo "2. Ver índices: data/index/latest.json"
echo "3. Logs: logs/boe_scraper.log"
echo ""
