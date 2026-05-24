"""Output helpers for JSONL ingestion runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List

from ingestion.models import NormalizedArtwork, utc_now_iso


@dataclass
class IngestionManifest:
    source_id: str
    source_name: str
    record_count: int
    output_path: str
    query: str
    limit: int
    include_raw: bool
    started_at: str
    finished_at: str
    status: str = "ok"


def write_jsonl(records: Iterable[NormalizedArtwork], output_path: Path, include_raw: bool) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.as_dict(include_raw=include_raw), ensure_ascii=False))
            handle.write("\n")
            count += 1
    return count


def write_manifest(manifests: List[IngestionManifest], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": utc_now_iso(),
        "runs": [asdict(manifest) for manifest in manifests],
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
