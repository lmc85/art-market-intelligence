#!/usr/bin/env python3
"""Fetch the Saffronart (India / South Asia) auction calendar into a JSON artifact.

Pulls Saffronart's public, unauthenticated auctions JSON web service and writes a
normalized sale-event feed to ``data/saffronart_auctions.json``. This is
sale-level coverage (titles, dates, status, results URL) for a region the rest of
the pipeline does not reach; per-lot realized prices are not exposed by the JSON
service and are intentionally left for a later, terms-cleared enrichment pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ingestion.connectors.saffronart_results import (
    REGION,
    SOURCE_ID,
    SOURCE_NAME,
    SaffronartResultsConnector,
)
from ingestion.models import utc_now_iso


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest the Saffronart auction calendar into JSON.")
    parser.add_argument("--output", type=Path, default=Path("data/saffronart_auctions.json"))
    parser.add_argument("--limit", type=int, default=0, help="Max events to keep (0 = all).")
    parser.add_argument(
        "--include-upcoming",
        action="store_true",
        help="Include live/upcoming sales; by default only completed (past) sales are kept.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    connector = SaffronartResultsConnector()
    statuses = None if args.include_upcoming else [3]
    events = connector.fetch_events(limit=args.limit, statuses=statuses)

    payload = {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "region": REGION,
        "generated_at": utc_now_iso(),
        "event_count": len(events),
        "coverage": "sale-event calendar; per-lot realized prices not exposed by the JSON service",
        "events": [event.as_record() for event in events],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    span = ""
    if events:
        dates = [event.start_date for event in events if event.start_date]
        if dates:
            span = f" spanning {min(dates)} to {max(dates)}"
    print(f"fetched {len(events)} Saffronart auction events{span}")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
