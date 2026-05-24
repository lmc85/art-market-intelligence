#!/usr/bin/env python3
"""Generate the static auction RSS feed from JSON seed/event data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ingestion.rss import load_auction_items, write_rss


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate auction result RSS XML.")
    parser.add_argument("--input", type=Path, default=Path("data/auction_feed_items.json"))
    parser.add_argument("--output", type=Path, default=Path("feeds/auction-results.xml"))
    parser.add_argument("--site-url", default="http://localhost:4173/")
    parser.add_argument("--feed-url", default="http://localhost:4173/feeds/auction-results.xml")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    write_rss(
        load_auction_items(args.input),
        args.output,
        site_url=args.site_url,
        feed_url=args.feed_url,
    )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
