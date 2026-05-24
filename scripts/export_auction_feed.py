#!/usr/bin/env python3
"""Export dashboard JSON and RSS from the local auction SQLite store."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ingestion.auction_store import DEFAULT_DB_PATH, AuctionStore, write_feed_json
from ingestion.rss import write_rss


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export auction feed files from SQLite.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output", type=Path, default=Path("data/auction_feed_items.json"))
    parser.add_argument("--rss-output", type=Path, default=Path("feeds/auction-results.xml"))
    parser.add_argument("--limit", type=int, default=100)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    store = AuctionStore(args.db_path)
    try:
        items = store.lots_for_feed(args.limit)
        write_feed_json(items, args.output)
        write_rss(items, args.rss_output)
        summary = store.quality_summary()
    finally:
        store.close()

    print(f"exported {len(items)} feed items to {args.output}")
    print(f"wrote RSS to {args.rss_output}")
    print(f"quality: {summary['prediction_ready']}/{summary['total']} prediction-ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
