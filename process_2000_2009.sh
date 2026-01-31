#!/bin/bash
# process_2000_2009.sh - Batch process years 2000-2009
# Runs the Streaming ETL for 2009 down to 2000 sequentially

set -e
export PYTHONIOENCODING=utf-8

# Activate venv
if [ -d ".venv/Scripts" ]; then
    source .venv/Scripts/activate
elif [ -d ".venv/bin" ]; then
    source .venv/bin/activate
fi

echo "=================================================="
echo "🚀 STARTING BATCH PROCESSING: 2000-2009"
echo "=================================================="
echo ""

# Loop from 2009 down to 2000
for year in {2009..2000}; do
    echo ">>> Processing YEAR $year..."
    python stream_etl.py --year $year --output data/master_${year}.jsonl
    echo "✓ $year Complete"
    echo ""
done

echo "=================================================="
echo "✅ ALL YEARS (2000-2009) COMPLETED SUCCESSFULLY"
echo "=================================================="
