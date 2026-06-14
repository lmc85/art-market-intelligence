#!/usr/bin/env python3
"""Ingest the Getty Provenance Index Knoedler stock books into the auction store.

Loads realized 1873–1912 dealer transactions into the SQLite auction store so the
derived market indices gain multi-year price history, then (by default) rebuilds
data/market_indices.json so the change is visible on the dashboard.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ingestion.auction_store import DEFAULT_DB_PATH, AuctionStore
from ingestion.connectors.getty_knoedler import KnoedlerConnector
from ingestion.market_indices import build_market_index_payload, load_indexable_lots, write_market_indices


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest Getty Knoedler historical prices into the auction store.")
    parser.add_argument("--limit", type=int, default=2500, help="Max records to ingest (0 = all ~7,800 sold).")
    parser.add_argument("--all-currencies", action="store_true", help="Keep non-dollar prices too (default: dollars only).")
    parser.add_argument("--cache", type=Path, default=Path("data/ingested/knoedler.csv"), help="Local CSV cache path.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--no-rebuild-indices", action="store_true", help="Skip rebuilding data/market_indices.json.")
    parser.add_argument("--indices-output", type=Path, default=Path("data/market_indices.json"))
    parser.add_argument("--min-lots-per-series", type=int, default=15)
    return parser


def main() -> int:
    args = build_parser().parse_args()

    currencies = None if args.all_currencies else ("dollars",)
    connector = KnoedlerConnector()
    lots = connector.fetch_lots(limit=args.limit, currencies=currencies or (), cache_path=args.cache)

    store = AuctionStore(args.db_path)
    try:
        written = store.upsert_lots(lots)
    finally:
        store.close()

    years = sorted({lot.auction_date[:4] for lot in lots if lot.auction_date})
    artists = {lot.artists[0] for lot in lots if lot.artists}
    print(f"ingested {written} Knoedler lots into {args.db_path}")
    if years:
        print(f"{len(years)} distinct sale years ({years[0]}–{years[-1]}); {len(artists)} distinct artists")

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
        print(f"wrote {args.indices_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
