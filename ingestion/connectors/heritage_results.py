"""Connector lane for Heritage Auctions public result archives."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ingestion.auction_models import AuctionLot
from ingestion.connectors.auction_results_common import AuctionHouseSaleSnapshot
from ingestion.http import HttpClient, HttpError


RESULTS_URL = "https://www.ha.com/c/search/results.zx"
AUCTION_HOUSE = "Heritage Auctions"
RECORD_SOURCE = "Heritage public auction archive"


class HeritageResultsConnector:
    """Track Heritage as a source while surfacing access blocks cleanly."""

    source_id = "heritage_auctions"
    source_name = "Heritage Auctions Archives"

    def __init__(self, client: Optional[HttpClient] = None):
        self.client = client or HttpClient()

    def fetch_lots(
        self,
        limit: int = 10,
        sale_url: Optional[str] = None,
        sale_query: str = "",
    ) -> List[Dict[str, Any]]:
        _, lots = self.fetch_auction_lots(limit=limit, sale_url=sale_url, sale_query=sale_query)
        return [lot.to_feed_item() for lot in lots]

    def fetch_auction_lots(
        self,
        limit: int = 10,
        sale_url: Optional[str] = None,
        sale_query: str = "",
    ) -> Tuple[AuctionHouseSaleSnapshot, List[AuctionLot]]:
        target_url = sale_url or RESULTS_URL
        try:
            raw_html = self.client.get_text(target_url, params={"Ntt": sale_query or "fine art"})
        except HttpError as exc:
            return blocked_snapshot(target_url, sale_query, str(exc)), []

        return AuctionHouseSaleSnapshot(
            source_id=self.source_id,
            source_name=self.source_name,
            sale_url=target_url,
            sale_title=f"Heritage archive search: {sale_query or 'fine art'}",
            raw_html=raw_html,
            lots_payload={},
            notes=[
                "Heritage returned an HTML response, but no stable public lot payload parser has been confirmed yet."
            ],
        ), []


def blocked_snapshot(target_url: str, sale_query: str, error: str) -> AuctionHouseSaleSnapshot:
    return AuctionHouseSaleSnapshot(
        source_id=HeritageResultsConnector.source_id,
        source_name=HeritageResultsConnector.source_name,
        sale_url=target_url,
        sale_title=f"Heritage archive search: {sale_query or 'fine art'}",
        raw_html="",
        lots_payload={},
        notes=[
            "Direct public HTTP access is currently blocked for Heritage from the local ingestion client.",
            error,
        ],
    )
