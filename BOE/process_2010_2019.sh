#!/bin/bash
cd "$(dirname "$0")"
#!/bin/bash
# process_2010_2019.sh - Batch process years 2010-2019
# Runs the Streaming ETL for 2019 down to 2010 sequentially

set -e
export PYTHONIOENCODING=utf-8

# Activate venv
if [ -d ".venv/Scripts" ]; then
    source .venv/Scripts/activate
elif [ -d ".venv/bin" ]; then
    source .venv/bin/activate
fi

echo "=================================================="
echo "🚀 STARTING BATCH PROCESSING: 2010-2019"
echo "=================================================="
echo ""

# Loop from 2019 down to 2010
for year in {2019..2010}; do
    echo ">>> Processing YEAR $year..."
    python stream_etl.py --year $year --output data/master_${year}.jsonl
    echo "✓ $year Complete"
    echo ""
done

echo "=================================================="
echo "✅ ALL YEARS (2010-2019) COMPLETED SUCCESSFULLY"
echo "=================================================="
