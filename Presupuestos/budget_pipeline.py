import argparse
import sys
import os
import json
from typing import List
from dotenv import load_dotenv

# Load env vars
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
load_dotenv(env_path)


# Ensure src is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "src"))

from budget.sources.igae import IGAESource
from budget.sources.base import BudgetResource

def main():
    parser = argparse.ArgumentParser(description="Budget & Expenses Pipeline")
    parser.add_argument("--year", type=int, required=True, help="Year to process")
    parser.add_argument("--month", type=int, help="Month to process (optional, defaults to all available)")
    parser.add_argument("--sources", nargs="+", default=["igae"], help="Sources to use (default: igae)")
    parser.add_argument("--dry-run", action="store_true", help="Only list resources, do not download or process")
    
    args = parser.parse_args()

    print(f"🚀 Budget Pipeline started for {args.year} (Month: {args.month if args.month else 'ALL'})")
    print(f"Sources: {args.sources}")
    print("=" * 60)

    # Initialize sources
    sources = []
    if "igae" in args.sources:
        sources.append(IGAESource())
    
    all_resources: List[BudgetResource] = []

    # 1. Discovery Phase
    print("\n🔎 Phase 1: Discovery")
    for source in sources:
        print(f"Checking source: {source.name}...")
        try:
            resources = source.list_resources(year=args.year, month=args.month)
            print(f"  -> Found {len(resources)} resources.")
            all_resources.extend(resources)
        except Exception as e:
            print(f"  -> Error scanning {source.name}: {e}")

    if not all_resources:
        print("\n❌ No resources found. Exiting.")
        return

    # Dry run output
    if args.dry_run:
        print("\n📝 Dry Run Summary (Resources Found):")
        print("-" * 60)
        for r in all_resources:
            print(f"[{r.source_name}] {r.title_original}")
            print(f"  Url: {r.url}")
            print(f"  File: {r.filetype} | Date: {r.expected_month}/{r.expected_year}")
            print(f"  Filename: {r.get_filename()}")
            print("-" * 60)
        print(f"\nTotal: {len(all_resources)} resources found.")
        return

    # Future phases (Download, Extract, LLM) will go here
    from budget.extractor import BudgetExtractor
    from budget.llm import BudgetLLMProcessor
    
    extractor = BudgetExtractor()
    llm_processor = BudgetLLMProcessor()
    
    output_dir_raw = f"../data/raw/budgets/{args.year}/{args.month if args.month else 'all'}"
    output_dir_jsonl = f"../data/jsonl/budgets/{args.year}/{args.month if args.month else 'all'}"
    os.makedirs(output_dir_raw, exist_ok=True)
    os.makedirs(output_dir_jsonl, exist_ok=True)
    
    final_output_file = os.path.join(output_dir_jsonl, f"budgets-{args.year}-{args.month if args.month else 'all'}.jsonl")
    
    print("\n⚙️  Phase 2 & 3: Processing Resources")
    
    processed_count = 0
    with open(final_output_file, 'a') as f_out: # Append mode
        for resource in all_resources:
            print(f"Processing: {resource.title_original}...")
            
            # 2. Download
            local_filename = resource.get_filename()
            local_path = os.path.join(output_dir_raw, local_filename)
            
            # In a real scenario, download_resource would download content. 
            # For this MVP, we need real files or mocks.
            # If IGAE source is mocked, we can't extract without files.
            # Skipping download check for strict logic, assuming files exist or we simulate.
            
            # SIMULATION BLOCK FOR DEMO (Since we don't have real IGAE connectivity yet)
            # Create a dummy file if it doesn't exist to test the pipeline flow
            if not os.path.exists(local_path):
                with open(local_path, 'w') as f_dummy:
                    f_dummy.write("DUMMY PDF CONTENT FOR TESTING")
                print(f"  [Mock] Created dummy file: {local_path}")
                
            # 3. Extract
            print(f"  -> Extracting ({resource.filetype})...")
            # Force filetype for mock extraction if needed, normally resource.filetype
            extraction_result = extractor.extract(local_path, resource.filetype)
            
            # 4. LLM
            print(f"  -> Analying with LLM...")
            try:
                # Mock resource info for LLM
                r_info = resource.model_dump()
                r_info['filename'] = local_filename
                
                doc = llm_processor.process_document(extraction_result, r_info)
                
                # 5. Save
                f_out.write(doc.model_dump_json() + "\n")
                f_out.flush()
                print(f"  ✅ Saved: {doc.short_title}")
                processed_count += 1
                
            except Exception as e:
                print(f"  ❌ Failed to process: {e}")

    print("=" * 60)
    print(f"Pipeline Finished. Processed {processed_count} documents.")
    print(f"Output: {final_output_file}")

if __name__ == "__main__":
    main()
