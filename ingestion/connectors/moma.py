"""Streaming CSV connector for MoMA collection data."""

from __future__ import annotations

import csv
from typing import Iterable, Optional

from ingestion.connectors.base import Connector
from ingestion.models import NormalizedArtwork


class MomaConnector(Connector):
    source_id = "moma_collection"
    csv_url = "https://media.githubusercontent.com/media/MuseumofModernArt/collection/main/Artworks.csv"
    default_query = ""

    def fetch(self, limit: int, query: Optional[str] = None) -> Iterable[NormalizedArtwork]:
        query_text = (query or "").lower()
        yielded = 0

        with self.client.open_text_stream(self.csv_url) as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if query_text and not self.matches_query(row, query_text):
                    continue

                record = self.normalize(row)
                if record:
                    yielded += 1
                    yield record

                if yielded >= limit:
                    break

    @staticmethod
    def matches_query(row, query_text: str) -> bool:
        haystack = " ".join(
            [
                row.get("Title", ""),
                row.get("Artist", ""),
                row.get("Medium", ""),
                row.get("Classification", ""),
                row.get("Department", ""),
            ]
        ).lower()
        return query_text in haystack

    def normalize(self, row):
        source_record_id = row.get("ObjectID") or ""
        if not source_record_id:
            return None

        artist_display = row.get("Artist") or ""
        artist_names = [artist_display] if artist_display else []

        return NormalizedArtwork(
            source_id=self.source.source_id,
            source_name=self.source.source_name,
            source_record_id=source_record_id,
            title=row.get("Title") or "Untitled",
            artist_display=artist_display,
            artist_names=artist_names,
            object_date=row.get("Date") or "",
            medium=row.get("Medium") or "",
            dimensions=row.get("Dimensions") or "",
            classification=row.get("Classification") or "",
            department=row.get("Department") or "",
            culture=row.get("Nationality") or "",
            image_url=row.get("ImageURL") or "",
            source_url=row.get("URL") or "",
            license="CC0 metadata; image rights separate",
            credit_line=row.get("CreditLine") or "",
            accession_number=row.get("AccessionNumber") or "",
            raw=row,
        )
