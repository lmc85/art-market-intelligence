"""Connector for The Metropolitan Museum of Art Collection API."""

from __future__ import annotations

from typing import Iterable, Optional

from ingestion.connectors.base import Connector, as_int, compact_join
from ingestion.models import NormalizedArtwork


class MetConnector(Connector):
    source_id = "met_open_access"
    base_url = "https://collectionapi.metmuseum.org/public/collection/v1"
    default_query = "painting"

    def fetch(self, limit: int, query: Optional[str] = None) -> Iterable[NormalizedArtwork]:
        search_query = query or self.default_query
        search = self.client.get_json(
            f"{self.base_url}/search",
            {"hasImages": "true", "q": search_query},
        )
        object_ids = search.get("objectIDs") or []

        yielded = 0
        for object_id in object_ids:
            if yielded >= limit:
                break
            item = self.client.get_json(f"{self.base_url}/objects/{object_id}")
            record = self.normalize(item)
            if record:
                yielded += 1
                yield record
            self.nap()

    def normalize(self, item):
        source_record_id = str(item.get("objectID") or "")
        if not source_record_id:
            return None

        artist = item.get("artistDisplayName") or ""
        geography = compact_join(
            [
                item.get("country"),
                item.get("region"),
                item.get("subregion"),
                item.get("city"),
            ]
        )

        return NormalizedArtwork(
            source_id=self.source.source_id,
            source_name=self.source.source_name,
            source_record_id=source_record_id,
            title=item.get("title") or "Untitled",
            artist_display=artist,
            artist_names=[artist] if artist else [],
            object_date=item.get("objectDate") or "",
            date_begin=as_int(item.get("objectBeginDate")),
            date_end=as_int(item.get("objectEndDate")),
            medium=item.get("medium") or "",
            dimensions=item.get("dimensions") or "",
            classification=item.get("classification") or item.get("objectName") or "",
            department=item.get("department") or "",
            culture=item.get("culture") or "",
            geography=geography,
            image_url=item.get("primaryImageSmall") or item.get("primaryImage") or "",
            source_url=item.get("objectURL") or f"{self.base_url}/objects/{source_record_id}",
            license="Public domain" if item.get("isPublicDomain") else "",
            credit_line=item.get("creditLine") or "",
            accession_number=item.get("accessionNumber") or "",
            raw=item,
        )
