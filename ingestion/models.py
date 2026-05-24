"""Normalized data models used by open collection connectors."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class NormalizedArtwork:
    """A source-neutral artwork record ready for JSONL storage."""

    source_id: str
    source_name: str
    source_record_id: str
    title: str
    artist_display: str = ""
    artist_names: List[str] = field(default_factory=list)
    object_date: str = ""
    date_begin: Optional[int] = None
    date_end: Optional[int] = None
    medium: str = ""
    dimensions: str = ""
    classification: str = ""
    department: str = ""
    culture: str = ""
    geography: str = ""
    image_url: str = ""
    source_url: str = ""
    license: str = ""
    credit_line: str = ""
    accession_number: str = ""
    ingestion_type: str = "object_metadata"
    ingested_at: str = field(default_factory=utc_now_iso)
    raw: Optional[Dict[str, Any]] = None

    def as_dict(self, include_raw: bool = False) -> Dict[str, Any]:
        data = asdict(self)
        if not include_raw:
            data.pop("raw", None)
        return data
