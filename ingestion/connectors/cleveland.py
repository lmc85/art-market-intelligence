"""Connector for the Cleveland Museum of Art Open Access API."""

from __future__ import annotations

from typing import Iterable, Optional

from ingestion.connectors.base import Connector, as_int, compact_join
from ingestion.models import NormalizedArtwork


class ClevelandConnector(Connector):
    source_id = "cleveland_open_access"
    base_url = "https://openaccess-api.clevelandart.org/api"
    default_query = ""

    def fetch(self, limit: int, query: Optional[str] = None) -> Iterable[NormalizedArtwork]:
        params = {"has_image": 1, "limit": limit, "skip": 0}
        if query:
            params["q"] = query

        response = self.client.get_json(f"{self.base_url}/artworks/", params)
        for item in (response.get("data") or [])[:limit]:
            record = self.normalize(item)
            if record:
                yield record
            self.nap()

    def normalize(self, item):
        source_record_id = str(item.get("id") or item.get("accession_number") or "")
        if not source_record_id:
            return None

        creators = item.get("creators") or []
        artist_names = [creator.get("description") for creator in creators if creator.get("description")]
        artist_display = compact_join(artist_names)
        images = item.get("images") or {}
        image_url = (images.get("web") or {}).get("url") or (images.get("print") or {}).get("url") or ""

        return NormalizedArtwork(
            source_id=self.source.source_id,
            source_name=self.source.source_name,
            source_record_id=source_record_id,
            title=item.get("title") or "Untitled",
            artist_display=artist_display,
            artist_names=artist_names,
            object_date=item.get("creation_date") or item.get("date_text") or "",
            date_begin=as_int(item.get("creation_date_earliest")),
            date_end=as_int(item.get("creation_date_latest")),
            medium=item.get("technique") or "",
            dimensions=item.get("measurements") or item.get("dimensions") or "",
            classification=item.get("type") or "",
            department=item.get("department") or "",
            culture=compact_join(item.get("culture") or []),
            geography=compact_join([item.get("current_location"), item.get("find_spot")]),
            image_url=image_url,
            source_url=item.get("url") or f"{self.base_url}/artworks/{source_record_id}",
            license=item.get("share_license_status") or item.get("legal_status") or "",
            credit_line=item.get("creditline") or "",
            accession_number=item.get("accession_number") or "",
            raw=item,
        )
