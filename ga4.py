"""
GA4 connection for Fidget Newton.
Uses OAuth credentials from .env to query the GA4 Data API.

Usage:
    from ga4 import run_report
    results = run_report(dimensions=["pagePath"], metrics=["sessions"], days=30)
"""

import os
import datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv, set_key
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
    OrderBy,
    FilterExpression,
)

# ── Load credentials ───────────────────────────────────────────────────────────

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH)

PROPERTY_ID   = os.environ["GA4_PROPERTY_ID"]
CLIENT_ID     = os.environ["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["GOOGLE_REFRESH_TOKEN"]

# ── Auth ───────────────────────────────────────────────────────────────────────

def _get_credentials() -> Credentials:
    """
    Returns valid GA4 credentials.

    Strategy:
    1. If GOOGLE_ACCESS_TOKEN + GOOGLE_TOKEN_EXPIRY are set in .env and the
       token hasn't expired, use them directly (no network call needed).
       This lets the scheduled task run inside the sandbox, which cannot
       reach oauth2.googleapis.com through the proxy.
    2. Otherwise fall back to a live refresh via oauth2.googleapis.com.
       This works when running directly on the host machine.
       The companion refresh_token.py script (run by a LaunchAgent every 30 min)
       keeps the cached token fresh so path 1 always succeeds in the sandbox.
    """
    cached_token  = os.environ.get("GOOGLE_ACCESS_TOKEN", "").strip()
    cached_expiry = os.environ.get("GOOGLE_TOKEN_EXPIRY", "").strip()

    if cached_token and cached_expiry:
        try:
            expiry_dt = datetime.datetime.fromisoformat(cached_expiry)
            # Use cached token if it has more than 5 minutes of life left
            if expiry_dt > datetime.datetime.utcnow() + datetime.timedelta(minutes=5):
                return Credentials(
                    token=cached_token,
                    refresh_token=REFRESH_TOKEN,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=CLIENT_ID,
                    client_secret=CLIENT_SECRET,
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"],
                    expiry=expiry_dt,
                )
        except ValueError:
            pass  # malformed expiry — fall through to live refresh

    # Live refresh (requires direct access to oauth2.googleapis.com)
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/analytics.readonly"],
    )
    creds.refresh(Request())
    return creds


def _get_client() -> BetaAnalyticsDataClient:
    return BetaAnalyticsDataClient(credentials=_get_credentials())


# ── Core query function ────────────────────────────────────────────────────────

def run_report(
    dimensions: list[str],
    metrics: list[str],
    days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    order_by_metric: Optional[str] = None,
) -> list[dict]:
    """
    Run a GA4 report and return rows as a list of dicts.

    Args:
        dimensions:      e.g. ["pagePath", "sessionDefaultChannelGroup"]
        metrics:         e.g. ["sessions", "conversions", "totalRevenue"]
        days:            lookback window (ignored if start_date/end_date set)
        start_date:      "YYYY-MM-DD" or GA4 relative e.g. "30daysAgo"
        end_date:        "YYYY-MM-DD" or "today"
        limit:           max rows to return
        order_by_metric: metric name to sort descending by

    Returns:
        List of dicts with dimension + metric values keyed by name.
    """
    client = _get_client()

    if start_date is None:
        start_date = f"{days}daysAgo"
    if end_date is None:
        end_date = "today"

    order_bys = []
    if order_by_metric:
        order_bys = [
            OrderBy(metric=OrderBy.MetricOrderBy(metric_name=order_by_metric), desc=True)
        ]

    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        limit=limit,
        order_bys=order_bys,
    )

    response = client.run_report(request)

    dim_headers = [h.name for h in response.dimension_headers]
    met_headers = [h.name for h in response.metric_headers]

    rows = []
    for row in response.rows:
        record = {}
        for i, val in enumerate(row.dimension_values):
            record[dim_headers[i]] = val.value
        for i, val in enumerate(row.metric_values):
            record[met_headers[i]] = val.value
        rows.append(record)

    return rows


# ── Convenience queries ────────────────────────────────────────────────────────

def conversion_funnel(days: int = 30) -> dict:
    """Sessions → cart → checkout → purchase funnel."""
    rows = run_report(
        dimensions=[],
        metrics=["sessions", "addToCarts", "checkouts", "ecommercePurchases", "purchaseRevenue"],
        days=days,
    )
    return rows[0] if rows else {}


def top_pages(days: int = 30, limit: int = 20) -> list[dict]:
    """Top pages by sessions with engagement metrics."""
    return run_report(
        dimensions=["pagePath", "pageTitle"],
        metrics=["sessions", "engagementRate", "averageSessionDuration"],
        days=days,
        limit=limit,
        order_by_metric="sessions",
    )


def traffic_by_source(days: int = 30) -> list[dict]:
    """Sessions and revenue by channel."""
    return run_report(
        dimensions=["sessionDefaultChannelGroup"],
        metrics=["sessions", "ecommercePurchases", "purchaseRevenue", "sessionConversionRate"],
        days=days,
        order_by_metric="sessions",
    )


def product_performance(days: int = 30) -> list[dict]:
    """Revenue and purchases by product."""
    return run_report(
        dimensions=["itemName"],
        metrics=["itemRevenue", "itemsPurchased", "addToCarts"],
        days=days,
        limit=50,
        order_by_metric="itemRevenue",
    )


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Testing GA4 connection...\n")

    print("── Conversion funnel (last 30 days) ──")
    funnel = conversion_funnel(30)
    for k, v in funnel.items():
        print(f"  {k}: {v}")

    print("\n── Traffic by source ──")
    for row in traffic_by_source(30):
        print(f"  {row}")

    print("\n── Top 5 pages ──")
    for row in top_pages(30, limit=5):
        print(f"  {row}")
