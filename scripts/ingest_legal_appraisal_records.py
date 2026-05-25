#!/usr/bin/env python3
"""Search CourtListener/RECAP for public legal appraisal leads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ingestion.legal_appraisals import (
    DEFAULT_APPRAISAL_QUERIES,
    CourtListenerLegalAppraisalConnector,
    write_legal_appraisal_records,
)
from ingestion.models import utc_now_iso


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest public appraisal-related legal leads from CourtListener.")
    parser.add_argument("--query", action="append", default=[], help="CourtListener query. May be repeated.")
    parser.add_argument("--limit-per-query", type=int, default=5)
    parser.add_argument("--result-type", default="rd", choices=["r", "rd", "d"], help="CourtListener search type.")
    parser.add_argument("--output", type=Path, default=Path("data/legal_appraisal_records.json"))
    parser.add_argument("--raw-output", type=Path, default=Path("data/legal_appraisals/raw_snapshots/latest_search.json"))
    parser.add_argument("--enrich-documents", action="store_true", help="Fetch RECAP document detail/text when COURTLISTENER_TOKEN is set.")
    parser.add_argument("--text-sample-chars", type=int, default=1200)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    queries = args.query or DEFAULT_APPRAISAL_QUERIES
    connector = CourtListenerLegalAppraisalConnector()
    payload = connector.search_appraisal_leads(
        queries=queries,
        limit_per_query=args.limit_per_query,
        result_type=args.result_type,
        enrich_documents=args.enrich_documents,
        text_sample_chars=args.text_sample_chars,
    )
    payload["source"]["result_type"] = args.result_type
    write_legal_appraisal_records(payload, args.output)
    write_raw_snapshot(payload, args.raw_output)

    summary = payload["summary"]
    print(
        f"stored {summary['record_count']} legal appraisal leads "
        f"from {summary['query_count']} CourtListener queries"
    )
    print(
        f"{summary['high_confidence_count']} high-confidence, "
        f"{summary['available_document_count']} with available RECAP documents"
    )
    if args.enrich_documents and not payload["source"]["token_present"]:
        print("document enrichment skipped because COURTLISTENER_TOKEN is not set")
    print(f"wrote {args.output}")
    return 0


def write_raw_snapshot(payload, raw_output: Path) -> None:
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "captured_at": utc_now_iso(),
        "source": payload["source"],
        "queries": payload["queries"],
        "record_count": payload["summary"]["record_count"],
    }
    raw_output.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
