#!/usr/bin/env python3
"""Fetch public Christie's auction results into the prototype RSS feed data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ingestion.connectors.christies_results import ChristiesResultsConnector
from ingestion.rss import load_auction_items, write_rss


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest Christie's public auction results into the RSS feed data.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum Christie's lots to add.")
    parser.add_argument("--sale-url", default="", help="Optional explicit Christie's sale URL.")
    parser.add_argument("--sale-query", default="", help="Optional sale-title query for the results page.")
    parser.add_argument("--input", type=Path, default=Path("data/auction_feed_items.json"))
    parser.add_argument("--output", type=Path, default=Path("data/auction_feed_items.json"))
    parser.add_argument("--rss-output", type=Path, default=Path("feeds/auction-results.xml"))
    parser.add_argument("--replace", action="store_true", help="Replace existing feed items instead of merging.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    connector = ChristiesResultsConnector()
    live_items = connector.fetch_lots(
        limit=args.limit,
        sale_url=args.sale_url or None,
        sale_query=args.sale_query,
    )

    if args.replace or not args.input.exists():
        items = live_items
    else:
        existing = load_auction_items(args.input)
        items = merge_items(live_items, existing)

    args.output.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_rss(items, args.rss_output)

    print(f"wrote {len(live_items)} Christie's lots to {args.output}")
    print(f"wrote RSS to {args.rss_output}")
    return 0


def merge_items(primary_items, secondary_items):
    merged = []
    seen = set()
    for item in list(primary_items) + list(secondary_items):
        item_id = item.get("id") or item.get("source_url") or item.get("title")
        if item_id in seen:
            continue
        seen.add(item_id)
        merged.append(item)
    return merged


if __name__ == "__main__":
    raise SystemExit(main())
