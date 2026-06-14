#!/usr/bin/env python3
"""Backfill multi-year auction history by walking a house's past-sale archive.

The live connectors normally store one recent sale, leaving the derived indices at a
single period ("needs more history"). This walks the connector's full past-sale list
(Phillips publishes ~2013 onward) and accumulates realized lots from many sales across
years into the store, then rebuilds data/market_indices.json so per-artist and
per-medium lanes become trend-ready.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Type

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ingestion.auction_store import DEFAULT_DB_PATH, AuctionStore, write_feed_json
from ingestion.backfill import backfill_sales, sample_across_years
from ingestion.connectors.phillips_results import PhillipsResultsConnector
from ingestion.market_indices import build_market_index_payload, load_indexable_lots, write_market_indices
from ingestion.rss import write_rss


# Connectors that expose discover_sale_urls (a deep, structured past-sale archive).
CONNECTORS: Dict[str, Type] = {
    PhillipsResultsConnector.source_id: PhillipsResultsConnector,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill multi-year auction history from a house archive.")
    parser.add_argument("--source", choices=sorted(CONNECTORS), default="phillips_auctions")
    parser.add_argument("--max-sales", type=int, default=16, help="Past sales to walk.")
    parser.add_argument("--newest-only", action="store_true", help="Walk the newest sales instead of spreading across years.")
    parser.add_argument("--lots-per-sale", type=int, default=60, help="Max lots to pull per sale.")
    parser.add_argument("--sale-query", default="", help="Optional sale-title/url filter (e.g. 'contemporary').")
    parser.add_argument("--delay", type=float, default=1.0, help="Polite delay between sale fetches (seconds).")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output", type=Path, default=Path("data/auction_feed_items.json"))
    parser.add_argument("--rss-output", type=Path, default=Path("feeds/auction-results.xml"))
    parser.add_argument("--feed-limit", type=int, default=100)
    parser.add_argument("--no-rebuild-indices", action="store_true")
    parser.add_argument("--indices-output", type=Path, default=Path("data/market_indices.json"))
    parser.add_argument("--min-lots-per-series", type=int, default=15)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    connector = CONNECTORS[args.source]()

    discovered = connector.discover_sale_urls(sale_query=args.sale_query, limit_sales=0)
    if not discovered:
        print(f"no past sales discovered for {args.source} (query={args.sale_query!r})")
        return 1
    sales = (
        discovered[: args.max_sales]
        if args.newest_only
        else sample_across_years(discovered, args.max_sales)
    )
    print(
        f"discovered {len(discovered)} past art sales for {connector.source_name}; "
        f"walking {len(sales)} ({'newest first' if args.newest_only else 'spread across years'})"
    )

    store = AuctionStore(args.db_path)
    try:
        stats = backfill_sales(
            connector,
            store,
            sales,
            lots_per_sale=args.lots_per_sale,
            delay_seconds=args.delay,
        )
        feed_items = store.lots_for_feed(args.feed_limit)
        write_feed_json(feed_items, args.output)
        write_rss(feed_items, args.rss_output)
    finally:
        store.close()

    for row in stats["per_sale"]:
        print(f"  {row['date'] or '????-??-??'}  {row['priced']:>3} priced / {row['lots']:>3} lots  {row['name'][:48]}")
    if stats["errors"]:
        print(f"{len(stats['errors'])} sale(s) failed and were skipped")

    years = sorted(stats["years"])
    print(
        f"ingested {stats['lots_written']} lots ({stats['priced_lots']} priced) "
        f"from {stats['sales_ingested']} sales spanning {len(years)} years"
        + (f" ({years[0]}–{years[-1]})" if years else "")
    )

    if not args.no_rebuild_indices:
        rows = load_indexable_lots(args.db_path)
        payload = build_market_index_payload(rows, source_db=args.db_path, min_lots_per_series=args.min_lots_per_series)
        write_market_indices(payload, args.indices_output)
        summary = payload["summary"]
        print(
            f"rebuilt indices: {summary['index_count']} series, "
            f"{summary['history_ready_count']} history-ready, "
            f"{summary['needs_more_history_count']} need more history"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
