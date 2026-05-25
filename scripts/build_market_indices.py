#!/usr/bin/env python3
"""Build derived market indices from the local auction SQLite store."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ingestion.auction_store import DEFAULT_DB_PATH
from ingestion.market_indices import build_market_index_payload, load_indexable_lots, write_market_indices


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build internal auction-derived market index JSON.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output", type=Path, default=Path("data/market_indices.json"))
    parser.add_argument("--min-lots-per-series", type=int, default=1)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    lots = load_indexable_lots(args.db_path)
    payload = build_market_index_payload(
        lots,
        source_db=args.db_path,
        min_lots_per_series=args.min_lots_per_series,
    )
    write_market_indices(payload, args.output)

    summary = payload["summary"]
    print(
        f"built {summary['index_count']} market index series from "
        f"{summary['lot_count']} auction lots"
    )
    print(
        f"{summary['history_ready_count']} history-ready, "
        f"{summary['needs_more_history_count']} need more history"
    )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
