#!/usr/bin/env python3
"""
Pre-fetches GA4 traffic data and saves it to ga4_cache.json.

Run by GitHub Actions at 3:30am PT daily.
Credentials come from GitHub Secrets (injected as environment variables).

Usage:
    python3 ga4_daily_fetch.py
"""

import json
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import ga4

# Write to repo root so the Actions workflow can commit it
CACHE_PATH = Path(__file__).parent / "ga4_cache.json"


def main():
    print(f"Fetching GA4 data at {datetime.datetime.now().isoformat()}...")

    try:
        yesterday = ga4.run_report(
            dimensions=["sessionSource", "sessionMedium"],
            metrics=["sessions", "activeUsers", "conversions", "purchaseRevenue", "ecommercePurchases"],
            days=1,
        )
        print(f"  Yesterday: {len(yesterday)} rows")

        prior_7 = ga4.run_report(
            dimensions=["sessionSource", "sessionMedium"],
            metrics=["sessions", "activeUsers", "conversions", "purchaseRevenue", "ecommercePurchases"],
            days=7,
        )
        print(f"  Prior 7 days: {len(prior_7)} rows")

        landing_pages = ga4.run_report(
            dimensions=["landingPage"],
            metrics=["sessions", "conversions", "purchaseRevenue"],
            days=1,
            limit=15,
            order_by_metric="sessions",
        )
        print(f"  Landing pages: {len(landing_pages)} rows")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    cache = {
        "fetched_at": datetime.datetime.utcnow().isoformat() + "Z",
        "report_date": (datetime.date.today() - datetime.timedelta(days=1)).isoformat(),
        "yesterday": yesterday,
        "prior_7_days": prior_7,
        "landing_pages": landing_pages,
    }

    CACHE_PATH.write_text(json.dumps(cache, indent=2))
    print(f"Saved to {CACHE_PATH}")


if __name__ == "__main__":
    main()
