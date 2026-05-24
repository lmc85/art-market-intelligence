"""Base classes and utilities for source connectors."""

from __future__ import annotations

import time
from typing import Iterable, Optional

from ingestion.http import HttpClient
from ingestion.models import NormalizedArtwork
from ingestion.registry import SourceInfo


class Connector:
    """Base connector contract."""

    source_id = ""
    default_query = "painting"

    def __init__(self, source: SourceInfo, client: Optional[HttpClient] = None, delay_seconds: float = 0.15):
        self.source = source
        self.client = client or HttpClient()
        self.delay_seconds = delay_seconds

    def fetch(self, limit: int, query: Optional[str] = None) -> Iterable[NormalizedArtwork]:
        raise NotImplementedError

    def nap(self) -> None:
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)


def compact_join(values):
    return ", ".join(str(value).strip() for value in values if value)


def as_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
