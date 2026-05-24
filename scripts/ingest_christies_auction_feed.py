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
from ingestion.auction_store import DEFAULT_DB_PATH, AuctionStore, write_feed_json
from ingestion.models import utc_now_iso
from ingestion.rss import write_rss


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest Christie's public auction results into the RSS feed data.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum Christie's lots to add.")
    parser.add_argument("--sale-url", default="", help="Optional explicit Christie's sale URL.")
    parser.add_argument("--sale-query", default="", help="Optional sale-title query for the results page.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/auction/raw_snapshots"))
    parser.add_argument("--output", type=Path, default=Path("data/auction_feed_items.json"))
    parser.add_argument("--rss-output", type=Path, default=Path("feeds/auction-results.xml"))
    parser.add_argument("--feed-limit", type=int, default=100, help="Maximum stored lots to publish to feed files.")
    parser.add_argument("--replace", action="store_true", help="Clear existing Christie's lots before storing this run.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    connector = ChristiesResultsConnector()
    store = AuctionStore(args.db_path)
    run_id = store.start_run(
        source_id=connector.source_id,
        source_name=connector.source_name,
        sale_url=args.sale_url,
        sale_query=args.sale_query,
        limit_requested=args.limit,
    )

    try:
        if args.replace:
            store.clear_source(connector.source_id)

        snapshot, lots = connector.fetch_auction_lots(
            limit=args.limit,
            sale_url=args.sale_url or None,
            sale_query=args.sale_query,
        )
        raw_snapshot_path = write_raw_snapshot(snapshot, args.raw_dir)
        records_written = store.upsert_lots(lots)
        feed_items = store.lots_for_feed(args.feed_limit)
        write_feed_json(feed_items, args.output)
        write_rss(feed_items, args.rss_output)
        store.finish_run(
            run_id,
            status="ok",
            records_seen=len(lots),
            records_written=records_written,
            raw_snapshot_path=str(raw_snapshot_path),
        )
        summary = store.quality_summary()
    except Exception as exc:
        store.finish_run(
            run_id,
            status="error",
            records_seen=0,
            records_written=0,
            error=str(exc),
        )
        raise
    finally:
        store.close()

    print(f"stored {records_written} Christie's lots in {args.db_path}")
    print(f"wrote raw snapshot to {raw_snapshot_path}")
    print(f"published {len(feed_items)} feed items to {args.output}")
    print(f"wrote RSS to {args.rss_output}")
    print(
        "quality: "
        f"{summary['prediction_ready']}/{summary['total']} prediction-ready, "
        f"{summary['missing_prior_sale']} missing prior sale, "
        f"{summary['missing_medium']} missing medium, "
        f"{summary['missing_dimensions']} missing dimensions"
    )
    return 0


def write_raw_snapshot(snapshot, raw_dir: Path) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    sale_key = snapshot.sale_id or "sale"
    timestamp = utc_now_iso().replace(":", "").replace("-", "")
    path = raw_dir / f"christies_{sale_key}_{timestamp}.json"
    payload = {
        "source_id": ChristiesResultsConnector.source_id,
        "source_name": ChristiesResultsConnector.source_name,
        "captured_at": utc_now_iso(),
        "sale_url": snapshot.sale_url,
        "sale_title": snapshot.sale_title,
        "sale_id": snapshot.sale_id,
        "sale_number": snapshot.sale_number,
        "lots_payload": snapshot.lots_payload,
        "raw_html": snapshot.raw_html,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
