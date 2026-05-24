"""Command line runner for open collection ingestion."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from ingestion.connectors import CONNECTORS, implemented_source_ids
from ingestion.models import utc_now_iso
from ingestion.registry import DEFAULT_REGISTER_PATH, find_source, load_source_register, open_collection_sources
from ingestion.writer import IngestionManifest, write_jsonl, write_manifest


DEFAULT_OUTPUT_DIR = Path("data/ingested")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest open art collection metadata.")
    parser.add_argument(
        "--register",
        type=Path,
        default=DEFAULT_REGISTER_PATH,
        help="Path to the source register CSV.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List open collection sources and connector status.")
    list_parser.add_argument("--implemented-only", action="store_true", help="Only show implemented connectors.")

    ingest_parser = subparsers.add_parser("ingest", help="Run one or more implemented connectors.")
    target = ingest_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--source", choices=implemented_source_ids(), help="Source id to ingest.")
    target.add_argument("--all", action="store_true", help="Run all implemented connectors.")
    ingest_parser.add_argument("--limit", type=int, default=10, help="Maximum records per source.")
    ingest_parser.add_argument("--query", default="", help="Optional source search query.")
    ingest_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for JSONL output.")
    ingest_parser.add_argument("--include-raw", action="store_true", help="Include raw source payloads in JSONL.")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    sources = load_source_register(args.register)

    if args.command == "list":
        return list_sources(sources, args.implemented_only)
    if args.command == "ingest":
        return ingest_sources(args, sources)

    parser.error("Unknown command")
    return 2


def list_sources(sources, implemented_only: bool) -> int:
    rows = []
    for source in open_collection_sources(sources):
        status = "implemented" if source.source_id in CONNECTORS else "queued"
        if implemented_only and status != "implemented":
            continue
        rows.append((source.source_id, status, source.source_name, source.ingestion_method))

    widths = [max(len(str(row[index])) for row in rows + [("source_id", "status", "source", "method")]) for index in range(4)]
    print_row(("source_id", "status", "source", "method"), widths)
    print_row(tuple("-" * width for width in widths), widths)
    for row in rows:
        print_row(row, widths)
    return 0


def print_row(row, widths) -> None:
    print("  ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)))


def ingest_sources(args, sources) -> int:
    if args.limit < 1:
        print("--limit must be at least 1", file=sys.stderr)
        return 2

    source_ids = implemented_source_ids() if args.all else [args.source]
    manifests: List[IngestionManifest] = []
    run_started = utc_now_iso()

    for source_id in source_ids:
        source = find_source(source_id, sources)
        if not source:
            print(f"Source {source_id} is missing from {args.register}", file=sys.stderr)
            return 1

        connector = CONNECTORS[source_id](source)
        output_path = args.output_dir / f"{source_id}.jsonl"
        started_at = utc_now_iso()
        count = write_jsonl(connector.fetch(limit=args.limit, query=args.query or None), output_path, args.include_raw)
        finished_at = utc_now_iso()

        manifests.append(
            IngestionManifest(
                source_id=source.source_id,
                source_name=source.source_name,
                record_count=count,
                output_path=str(output_path),
                query=args.query,
                limit=args.limit,
                include_raw=args.include_raw,
                started_at=started_at,
                finished_at=finished_at,
            )
        )
        print(f"{source_id}: wrote {count} records to {output_path}")

    manifest_path = args.output_dir / "latest_manifest.json"
    write_manifest(manifests, manifest_path)
    print(f"manifest: wrote {manifest_path} for run started {run_started}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
