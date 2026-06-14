#!/usr/bin/env python3
"""Fetch a global art-fair calendar from Artsy's GraphQL API into a JSON artifact.

Writes a forward-looking, category-tagged fair calendar to ``data/art_fairs.json``
for the dashboard's Fair Calendar panel. City / country / region are derived from
the fair name (Artsy's location field is null); free-vs-paid and invitation-only
facets are not exposed by the source and are recorded as "unknown".
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ingestion.connectors.art_fairs import SOURCE_ID, SOURCE_NAME, ArtsyFairsConnector
from ingestion.models import utc_now_iso


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest the Artsy art-fair calendar into JSON.")
    parser.add_argument("--output", type=Path, default=Path("data/art_fairs.json"))
    parser.add_argument("--limit", type=int, default=0, help="Max fairs to keep (0 = all).")
    parser.add_argument("--pages", type=int, default=3, help="API pages to page through (100 fairs each).")
    parser.add_argument("--include-past", action="store_true", help="Keep fairs that have already ended.")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    connector = ArtsyFairsConnector()
    fairs = connector.fetch_fairs(limit=args.limit, pages=args.pages, include_past=args.include_past)

    by_region = Counter(fair.region for fair in fairs)
    by_type = Counter(fair.fair_type for fair in fairs)

    payload = {
        "source_id": SOURCE_ID,
        "source_name": SOURCE_NAME,
        "generated_at": utc_now_iso(),
        "fair_count": len(fairs),
        "coverage": "Artsy fairs (forward-looking); city/region derived from fair name, access facets not exposed by source",
        "facets": {
            "region": dict(by_region),
            "fair_type": dict(by_type),
        },
        "fairs": [fair.as_record() for fair in fairs],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    span = ""
    dated = [fair.start_date for fair in fairs if fair.start_date]
    if dated:
        span = f" spanning {min(dated)} to {max(dated)}"
    located = sum(1 for fair in fairs if fair.city)
    print(f"fetched {len(fairs)} art fairs{span}")
    print(f"{located}/{len(fairs)} located by name; regions: {dict(by_region)}")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
