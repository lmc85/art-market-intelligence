"""Connector for Bonhams public auction result pages."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from ingestion.auction_models import AuctionLot, MoneyValue
from ingestion.connectors.auction_results_common import (
    AuctionHouseSaleSnapshot,
    absolute_url,
    clean_html_lines,
    clean_text,
    estimate_money,
    extract_meta,
    extract_next_data,
    iso_date,
    money_value,
)
from ingestion.http import HttpClient


RESULTS_URL = "https://www.bonhams.com/auctions/results/"
BASE_URL = "https://www.bonhams.com"
AUCTION_HOUSE = "Bonhams"
RECORD_SOURCE = "Bonhams public auction result page"
EXCLUDED_SALE_TERMS = (
    "cars",
    "motorcar",
    "automobilia",
    "motorcycle",
    "jewel",
    "watch",
    "wine",
    "whisky",
    "coin",
    "stamp",
)


class BonhamsResultsConnector:
    """Fetch lot-level auction results from Bonhams public result pages."""

    source_id = "bonhams_results"
    source_name = "Bonhams Results"

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
        lots = []
        for lot in snapshot.lots_payload.get("auctionLots", []):
            if len(lots) >= limit:
                break
            item = bonhams_lot_to_auction_lot(lot, snapshot)
            if item:
                lots.append(item)
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
        auction = page_props.get("auction") or {}
        lot_data = page_props.get("lotData") or {}
        sale_title = clean_text(
            auction.get("sSaleName")
            or auction.get("sSaleNameStyled")
            or extract_meta(sale_html, "og:title")
        ).replace("Bonhams :", "").strip()

        return AuctionHouseSaleSnapshot(
            source_id=self.source_id,
            source_name=self.source_name,
            sale_url=target_sale_url,
            sale_title=sale_title,
            sale_id=clean_text(auction.get("iSaleNo") or first_lot_value(lot_data.get("auctionLots", []), "auctionId")),
            raw_html=sale_html,
            lots_payload={
                "auction": auction,
                "auctionLots": lot_data.get("auctionLots", []),
            },
        )

    def discover_sale_url(self, sale_query: str = "") -> str:
        results_html = self.client.get_text(RESULTS_URL)
        query = sale_query.strip().lower()
        candidates = []
        for match in re.finditer(r"/auction/\d+/[A-Za-z0-9-]+/", results_html):
            url = absolute_url(match.group(0), BASE_URL)
            context = clean_text(results_html[max(0, match.start() - 300) : match.end() + 300]).lower()
            if url not in {candidate["url"] for candidate in candidates}:
                candidates.append({"url": url, "context": context})

        for candidate in candidates:
            haystack = f"{candidate['url']} {candidate['context']}".lower()
            if query and query not in haystack:
                continue
            if any(term in haystack for term in EXCLUDED_SALE_TERMS):
                continue
            return candidate["url"]

        for candidate in candidates:
            haystack = f"{candidate['url']} {candidate['context']}".lower()
            if not any(term in haystack for term in EXCLUDED_SALE_TERMS):
                return candidate["url"]

        raise ValueError("No Bonhams public result sale URL found")


def bonhams_lot_to_auction_lot(lot: Dict[str, Any], snapshot: AuctionHouseSaleSnapshot) -> Optional[AuctionLot]:
    lot_id = clean_text((lot.get("lotNo") or {}).get("full") or lot.get("lotId"))
    source_record_id = clean_text(lot.get("lotUniqueId") or lot.get("lotItemId") or lot.get("id"))
    if not lot_id and not source_record_id:
        return None

    currency = clean_text((lot.get("currency") or {}).get("iso_code") or "")
    currency_symbol = clean_text((lot.get("price") or {}).get("currencySymbol") or "")
    price = lot.get("price") or {}
    estimate = estimate_money(
        currency,
        price.get("estimateLow"),
        price.get("estimateHigh"),
        symbol=currency_symbol,
    )
    result = None
    if clean_text(lot.get("status")).upper() == "SOLD" or price.get("hammerPremium") is not None:
        result = money_value(currency, price.get("hammerPremium") or price.get("hammerPrice"), symbol=currency_symbol)

    artist, title = parse_bonhams_artist_title(lot)
    department = lot.get("department") or {}
    image = lot.get("image") or {}
    auction_date = iso_date((lot.get("hammerTime") or {}).get("datetime") or (lot.get("biddableFrom") or {}).get("datetime"))
    slug = clean_text(lot.get("slug"))
    source_url = absolute_url(
        f"/auction/{lot.get('auctionId') or snapshot.sale_id}/lot/{lot.get('lotId') or lot_id}/{slug}/",
        BASE_URL,
    )

    return AuctionLot(
        source_id=BonhamsResultsConnector.source_id,
        source_name=BonhamsResultsConnector.source_name,
        auction_house=AUCTION_HOUSE,
        sale_id=snapshot.sale_id,
        sale_title=snapshot.sale_title,
        sale_url=snapshot.sale_url,
        lot_id=lot_id,
        source_record_id=source_record_id,
        title=title or clean_text(lot.get("title") or "Untitled lot"),
        artists=[artist] if artist else [],
        style=clean_text((department or {}).get("name") or snapshot.sale_title),
        auction_date=auction_date,
        currency=currency,
        estimate=MoneyValue.from_dict(estimate),
        result_price=MoneyValue.from_dict(result),
        source_url=source_url,
        image_url=clean_text(image.get("url") or ""),
        dimensions=extract_dimensions(clean_text(lot.get("title") or "")),
        description="\n".join(clean_html_lines(lot.get("styledDescription") or "")),
        record_source=RECORD_SOURCE,
        notes="Starting price and prior sale price were not exposed in the public Bonhams lot-list payload.",
        raw=lot,
    )


def parse_bonhams_artist_title(lot: Dict[str, Any]) -> Tuple[str, str]:
    lines = clean_html_lines(lot.get("styledDescription") or "")
    if not lines:
        title = clean_text(lot.get("title") or "")
        return "", title

    artist_parts = [lines[0]]
    if len(lines) > 1 and re.search(r"\(\s*(?:b\.|\d{4}|[0-9?-]{4,})", lines[1], flags=re.IGNORECASE):
        artist_parts.append(lines[1])
    artist = " ".join(artist_parts)
    title_index = 2 if len(artist_parts) > 1 else 1
    title = lines[title_index] if len(lines) > title_index else clean_text(lot.get("title") or "")
    return clean_text(artist), clean_text(title)


def extract_dimensions(value: str) -> str:
    match = re.search(
        r"((?:overall:\s*)?\d[\d\s/\.]*\s*x\s*\d[\d\s/\.]*(?:\s*x\s*\d[\d\s/\.]*)?\s*in(?:\.|ches)?\s*\([^)]+\))",
        value,
        flags=re.IGNORECASE,
    )
    return clean_text(match.group(1)) if match else ""


def first_lot_value(lots: List[Dict[str, Any]], key: str) -> str:
    for lot in lots:
        if lot.get(key):
            return clean_text(lot.get(key))
    return ""
