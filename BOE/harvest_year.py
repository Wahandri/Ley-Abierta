#!/usr/bin/env python3
"""
El Vigilante - Year-Long BOE Harvester
Orchestrates mass data extraction for all days of a given year
Author: El Vigilante Team
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

# === CONFIGURATION ===
PYTHON_BIN = ".venv/bin/python3"  # Use virtual environment Python
SCRAPER_SCRIPT = "boe_scraper.py"
RATE_LIMIT_SECONDS = 0.5  # Rate limiting between days
DATA_DIR = Path("../data")
LOG_DIR = Path("../logs")


class HarvestStats:
    """Track harvesting statistics"""
    def __init__(self):
        self.total_days = 0
        self.successful_days = 0
        self.failed_days = 0
        self.skipped_days = 0
        self.errors: List[Tuple[str, str]] = []  # (date, error_message)
    
    def add_success(self):
        self.successful_days += 1
    
    def add_failure(self, date_str: str, error_msg: str):
        self.failed_days += 1
        self.errors.append((date_str, error_msg))
    
    def add_skip(self):
        self.skipped_days += 1
    
    def print_summary(self):
        """Print final statistics"""
        print("\n" + "=" * 60)
        print("=== HARVEST SUMMARY ===")
        print("=" * 60)
        print(f"Total days processed: {self.total_days}")
        print(f"✓ Successful: {self.successful_days}")
        print(f"✗ Failed: {self.failed_days}")
        print(f"⊘ Skipped: {self.skipped_days}")
        
        if self.errors:
            print(f"\n=== ERRORS ({len(self.errors)}) ===")
            for date_str, error_msg in self.errors[:10]:  # Show first 10
                print(f"  • {date_str}: {error_msg}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more errors")
        
        print("=" * 60)


def generate_date_range(year: int, end_date: datetime = None) -> List[datetime]:
    """
    Generate list of dates from Jan 1 to Dec 31 of the given year
    If end_date is provided and is before Dec 31, stop at that date
    """
    start = datetime(year, 1, 1)
    
    # Determine end date
    if end_date and end_date.year == year:
        end = end_date
    else:
        end = datetime(year, 12, 31)
    
    dates = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    
    return dates


def run_scraper_for_date(date: datetime, dry_run: bool = False) -> bool:
    """
    Execute boe_scraper.py for a specific date using subprocess
    Returns True if successful, False if failed
    
    Args:
        date: Date to scrape
        dry_run: If True, preview the command without executing
    
    Returns:
        True if scraper executed successfully, False otherwise
    """
    date_str = date.strftime("%Y-%m-%d")
    
    # Build command
    cmd = [PYTHON_BIN, SCRAPER_SCRIPT, "--date", date_str]
    
    if dry_run:
        print(f"  [DRY-RUN] Would execute: {' '.join(cmd)}")
        return True
    
    try:
        # Execute scraper as subprocess
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout per day
        )
        
        # Check return code
        if result.returncode == 0:
            return True
        else:
            # Log error but continue
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            print(f"  ⚠️  Scraper failed: {error_msg[:100]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"  ⚠️  Scraper timed out (>5 minutes)")
        return False
    except Exception as e:
        print(f"  ⚠️  Execution error: {str(e)[:100]}")
        return False


def harvest_year(year: int, dry_run: bool = False, resume_from: str = None):
    """
    Main harvesting function
    Iterates through all days of the year and executes scraper for each
    
    Args:
        year: Year to harvest (e.g., 2025)
        dry_run: If True, preview without executing
        resume_from: Optional date string (YYYY-MM-DD) to resume from
    """
    print("=" * 60)
    print(f"=== El Vigilante - Year Harvester ===")
    print(f"Year: {year}")
    print(f"Mode: {'DRY-RUN' if dry_run else 'EXECUTION'}")
    print("=" * 60)
    
    # Determine end date (don't go beyond today)
    today = datetime.now()
    end_date = today if year == today.year else None
    
    # Generate date range
    dates = generate_date_range(year, end_date)
    
    # Resume logic
    if resume_from:
        try:
            resume_date = datetime.strptime(resume_from, "%Y-%m-%d")
            dates = [d for d in dates if d >= resume_date]
            print(f"📅 Resuming from: {resume_from}")
        except ValueError:
            print(f"⚠️  Invalid resume date: {resume_from}, starting from beginning")
    
    total_days = len(dates)
    stats = HarvestStats()
    stats.total_days = total_days
    
    print(f"📊 Total days to process: {total_days}")
    print(f"🕐 Estimated time: ~{total_days * (RATE_LIMIT_SECONDS + 2) / 60:.1f} minutes")
    print()
    
    # Iterate through each day
    for i, date in enumerate(dates, start=1):
        date_str = date.strftime("%Y-%m-%d")
        
        # Progress indicator
        progress_pct = (i / total_days) * 100
        print(f"[Day {i}/{total_days} - {progress_pct:.1f}%] Processing {date_str}...", end=" ")
        
        # Run scraper
        success = run_scraper_for_date(date, dry_run)
        
        if success:
            print("✓")
            stats.add_success()
        else:
            print("✗")
            stats.add_failure(date_str, "Scraper execution failed")
        
        # Rate limiting (except on last day or dry-run)
        if not dry_run and i < total_days:
            time.sleep(RATE_LIMIT_SECONDS)
    
    # Print summary
    stats.print_summary()
    
    # Save error log
    if stats.errors and not dry_run:
        error_log_path = LOGS_DIR / f"harvest_errors_{year}.log"
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(error_log_path, "w", encoding="utf-8") as f:
            f.write(f"Harvest Errors for Year {year}\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            for date_str, error_msg in stats.errors:
                f.write(f"{date_str}: {error_msg}\n")
        
        print(f"\n📝 Error log saved to: {error_log_path}")


def main():
    parser = argparse.ArgumentParser(
        description="El Vigilante - Year-Long BOE Harvester",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2025,
        help="Year to harvest (default: 2025)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview commands without executing"
    )
    parser.add_argument(
        "--resume-from",
        type=str,
        default=None,
        help="Resume from a specific date (YYYY-MM-DD)"
    )
    
    args = parser.parse_args()
    
    # Validate year
    current_year = datetime.now().year
    if args.year < 2000 or args.year > current_year:
        print(f"⚠️  Invalid year: {args.year}. Must be between 2000 and {current_year}")
        sys.exit(1)
    
    # Start harvesting
    try:
        harvest_year(args.year, args.dry_run, args.resume_from)
    except KeyboardInterrupt:
        print("\n\n⚠️  Harvesting interrupted by user (Ctrl+C)")
        print("💡 Tip: Use --resume-from YYYY-MM-DD to continue from where you left off")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
