"""Connector for the Art Institute of Chicago public API."""

from __future__ import annotations

from typing import Iterable, Optional

from ingestion.connectors.base import Connector, as_int
from ingestion.models import NormalizedArtwork


ARTIC_FIELDS = ",".join(
    [
        "id",
        "api_link",
        "title",
        "date_display",
        "date_start",
        "date_end",
        "artist_display",
        "artist_id",
        "artist_title",
        "place_of_origin",
        "dimensions",
        "medium_display",
        "is_public_domain",
        "image_id",
        "classification_title",
        "department_title",
        "artwork_type_title",
        "style_title",
        "thumbnail",
        "credit_line",
        "main_reference_number",
    ]
)


class ArtInstituteConnector(Connector):
    source_id = "artic_api"
    base_url = "https://api.artic.edu/api/v1"
    default_query = ""

    def fetch(self, limit: int, query: Optional[str] = None) -> Iterable[NormalizedArtwork]:
        params = {"fields": ARTIC_FIELDS, "limit": limit, "page": 1}
        endpoint = f"{self.base_url}/artworks"
        if query:
            endpoint = f"{self.base_url}/artworks/search"
            params["q"] = query

        response = self.client.get_json(endpoint, params)
        iiif_url = response.get("config", {}).get("iiif_url") or "https://www.artic.edu/iiif/2"

        for item in (response.get("data") or [])[:limit]:
            record = self.normalize(item, iiif_url)
            if record:
                yield record
            self.nap()

    def normalize(self, item, iiif_url):
        source_record_id = str(item.get("id") or "")
        if not source_record_id:
            return None

        image_id = item.get("image_id") or ""
        image_url = f"{iiif_url}/{image_id}/full/843,/0/default.jpg" if image_id else ""
        artist_name = item.get("artist_title") or ""

        return NormalizedArtwork(
            source_id=self.source.source_id,
            source_name=self.source.source_name,
            source_record_id=source_record_id,
            title=item.get("title") or "Untitled",
            artist_display=item.get("artist_display") or artist_name,
            artist_names=[artist_name] if artist_name else [],
            object_date=item.get("date_display") or "",
            date_begin=as_int(item.get("date_start")),
            date_end=as_int(item.get("date_end")),
            medium=item.get("medium_display") or "",
            dimensions=item.get("dimensions") or "",
            classification=item.get("classification_title") or item.get("artwork_type_title") or "",
            department=item.get("department_title") or "",
            culture=item.get("style_title") or "",
            geography=item.get("place_of_origin") or "",
            image_url=image_url,
            source_url=item.get("api_link") or f"{self.base_url}/artworks/{source_record_id}",
            license="Public domain" if item.get("is_public_domain") else "",
            credit_line=item.get("credit_line") or "",
            accession_number=item.get("main_reference_number") or "",
            raw=item,
        )
