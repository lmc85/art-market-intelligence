"""Connector for Sotheby's public historical result pages."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from ingestion.auction_models import AuctionLot, MoneyValue
from ingestion.connectors.auction_results_common import (
    AuctionHouseSaleSnapshot,
    absolute_url,
    clean_text,
    estimate_money,
    extract_meta,
    extract_next_data,
    iso_date,
)
from ingestion.http import HttpClient


RESULTS_URL = "https://www.sothebys.com/en/results?locale=en"
BASE_URL = "https://www.sothebys.com"
AUCTION_HOUSE = "Sotheby's"
RECORD_SOURCE = "Sotheby's public auction result page"
EXCLUDED_SALE_TERMS = (
    "wine",
    "jewel",
    "watch",
    "handbag",
    "sneaker",
    "sports",
    "whisky",
    "cars",
    "real-estate",
)


class SothebysResultsConnector:
    """Fetch lot metadata from public Sotheby's result sale pages."""

    source_id = "sothebys_results"
    source_name = "Sotheby's Results"

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
        snapshot = self.fetch_sale_snapshot(sale_url=sale_url, sale_query=sale_query)
        payload = snapshot.lots_payload
        lots = []
        hits_by_id = {
            str(hit.get("objectID") or ""): hit
            for hit in payload.get("algolia_hits", [])
            if hit.get("objectID")
        }

        for lot_card in payload.get("lot_cards", []):
            if len(lots) >= limit:
                break
            lot = lot_card_to_auction_lot(lot_card, snapshot, hits_by_id.get(str(lot_card.get("lotId") or "")))
            if lot:
                lots.append(lot)
        return snapshot, lots

    def fetch_sale_snapshot(
        self,
        sale_url: Optional[str] = None,
        sale_query: str = "",
    ) -> AuctionHouseSaleSnapshot:
        target_sale_url = sale_url or self.discover_sale_url(sale_query=sale_query)
        sale_html = self.client.get_text(target_sale_url)
        data = extract_next_data(sale_html)
        page_props = data.get("props", {}).get("pageProps", {})
        cache = page_props.get("apolloCache", {})
        auction = first_auction(cache)
        lot_cards = [value for key, value in cache.items() if str(key).startswith("LotCard:")]
        sale_title = clean_text(auction.get("title") or extract_meta(sale_html, "og:title"))

        return AuctionHouseSaleSnapshot(
            source_id=self.source_id,
            source_name=self.source_name,
            sale_url=target_sale_url,
            sale_title=sale_title.replace(" | Sotheby's", ""),
            sale_id=str(auction.get("auctionId") or page_props.get("auctionId") or ""),
            sale_number=str(auction.get("sapSaleNumber") or ""),
            raw_html=sale_html,
            lots_payload={
                "auction": auction,
                "lot_cards": lot_cards,
                "algolia_hits": page_props.get("algoliaJson", {}).get("hits", []),
            },
            notes=[
                "Public Sotheby's sale payload exposes estimates and dates, but realized prices may be absent or gated."
            ],
        )

    def discover_sale_url(self, sale_query: str = "") -> str:
        results_html = self.client.get_text(RESULTS_URL)
        query = sale_query.strip().lower()
        urls = unique_urls(
            absolute_url(match.group(0), BASE_URL)
            for match in re.finditer(r"/en/buy/auction/\d{4}/[A-Za-z0-9-]+", results_html)
        )

        for url in urls:
            haystack = url.lower()
            if query and query not in haystack:
                continue
            if any(term in haystack for term in EXCLUDED_SALE_TERMS):
                continue
            return url

        for url in urls:
            if not any(term in url.lower() for term in EXCLUDED_SALE_TERMS):
                return url

        raise ValueError("No Sotheby's public result sale URL found")


def lot_card_to_auction_lot(
    lot_card: Dict[str, Any],
    snapshot: AuctionHouseSaleSnapshot,
    algolia_hit: Optional[Dict[str, Any]] = None,
) -> Optional[AuctionLot]:
    lot_id = clean_text((lot_card.get("lotNumber") or {}).get("lotDisplayNumber") or (algolia_hit or {}).get("lotDisplayNumber"))
    source_record_id = clean_text(lot_card.get("lotId") or (algolia_hit or {}).get("objectID"))
    if not lot_id and not source_record_id:
        return None

    auction = lot_card.get("auction") or snapshot.lots_payload.get("auction") or {}
    currency = clean_text(auction.get("currency") or (algolia_hit or {}).get("currency") or "")
    estimate = sothebys_estimate(lot_card, algolia_hit, currency)
    slug = clean_text((algolia_hit or {}).get("slug") or "")
    if not slug:
        lot_slug = clean_text((lot_card.get("slug") or {}).get("lotSlug") or "")
        auction_slug = auction.get("slug") or {}
        if lot_slug and auction_slug.get("year") and auction_slug.get("name"):
            slug = f"/en/buy/auction/{auction_slug['year']}/{auction_slug['name']}/{lot_slug}"

    notes = "Starting price, realized price, and prior sale price were not exposed in the sampled public Sotheby's payload."
    return AuctionLot(
        source_id=SothebysResultsConnector.source_id,
        source_name=SothebysResultsConnector.source_name,
        auction_house=AUCTION_HOUSE,
        sale_id=snapshot.sale_id or clean_text(auction.get("auctionId") or ""),
        sale_title=snapshot.sale_title,
        sale_url=snapshot.sale_url,
        lot_id=lot_id,
        source_record_id=source_record_id,
        title=clean_text(lot_card.get("title") or (algolia_hit or {}).get("title") or "Untitled lot"),
        artists=[clean_text(lot_card.get("creatorsDisplayTitle") or (algolia_hit or {}).get("creatorsDisplayTitle"))]
        if clean_text(lot_card.get("creatorsDisplayTitle") or (algolia_hit or {}).get("creatorsDisplayTitle"))
        else [],
        style=snapshot.sale_title,
        auction_date=iso_date((algolia_hit or {}).get("auctionDate") or (auction.get("dates") or {}).get("goesLive") or ""),
        currency=currency,
        estimate=MoneyValue.from_dict(estimate),
        source_url=absolute_url(slug, BASE_URL) or snapshot.sale_url,
        image_url=sothebys_image(algolia_hit or {}),
        record_source=RECORD_SOURCE,
        notes=notes,
        raw={"lot_card": lot_card, "algolia_hit": algolia_hit or {}},
    )


def sothebys_estimate(
    lot_card: Dict[str, Any],
    algolia_hit: Optional[Dict[str, Any]],
    currency: str,
) -> Optional[Dict[str, Any]]:
    estimate_v2 = lot_card.get("estimateV2") or {}
    low = ((estimate_v2.get("lowEstimate") or {}).get("amount")) or (algolia_hit or {}).get("lowEstimate")
    high = ((estimate_v2.get("highEstimate") or {}).get("amount")) or (algolia_hit or {}).get("highEstimate")
    return estimate_money(currency, low, high)


def sothebys_image(hit: Dict[str, Any]) -> str:
    image = hit.get("image") or {}
    if isinstance(image, dict):
        return clean_text(image.get("url") or image.get("src") or "")
    return clean_text(image)


def first_auction(cache: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in cache.items():
        if str(key).startswith("Auction:") and isinstance(value, dict):
            return value
    for value in cache.values():
        if isinstance(value, dict) and value.get("__typename") == "AuctionCard":
            return value
    return {}


def unique_urls(urls) -> List[str]:
    seen = set()
    output = []
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        output.append(url)
    return output
