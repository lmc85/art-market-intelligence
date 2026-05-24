"""Source register loading and connector discovery helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


DEFAULT_REGISTER_PATH = Path("data/free_data_sources.csv")


@dataclass
class SourceInfo:
    source_id: str
    source_name: str
    source_class: str
    access_type: str
    priority: str
    geography: str
    access_url: str
    ingestion_method: str
    license_or_terms_status: str
    notes: str


def load_source_register(path: Path = DEFAULT_REGISTER_PATH) -> List[SourceInfo]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [SourceInfo(**row) for row in csv.DictReader(handle)]


def find_source(source_id: str, sources: Iterable[SourceInfo]) -> Optional[SourceInfo]:
    for source in sources:
        if source.source_id == source_id:
            return source
    return None


def open_collection_sources(sources: Iterable[SourceInfo]) -> List[SourceInfo]:
    return [
        source
        for source in sources
        if source.source_class == "object_metadata"
        and source.ingestion_method in {"api", "csv_github", "json_csv_github"}
        and source.license_or_terms_status.startswith("open")
    ]
