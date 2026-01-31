#!/bin/bash
# process_history.sh - Batch process historical years
# Runs the Streaming ETL for 2023, 2022, and 2021 sequentially

set -e

# Activate venv
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo "=================================================="
echo "🚀 STARTING HISTORICAL BATCH PROCESSING"
echo "Years: 2023, 2022, 2021"
echo "=================================================="
echo ""

# Process 2023
echo ">>> Processing YEAR 2023..."
python3 stream_etl.py --year 2023 --output data/master_2023.jsonl
echo "✓ 2023 Complete"
echo ""

# Process 2022
echo ">>> Processing YEAR 2022..."
python3 stream_etl.py --year 2022 --output data/master_2022.jsonl
echo "✓ 2022 Complete"
echo ""

# Process 2021
echo ">>> Processing YEAR 2021..."
python3 stream_etl.py --year 2021 --output data/master_2021.jsonl
echo "✓ 2021 Complete"
echo ""

echo "=================================================="
echo "✅ ALL YEARS COMPLETED SUCCESSFULLY"
echo "=================================================="
