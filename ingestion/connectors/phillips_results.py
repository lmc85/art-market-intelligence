"""Connector for Phillips public auction result pages."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from ingestion.auction_models import AuctionLot, MoneyValue
from ingestion.connectors.auction_results_common import (
    AuctionHouseSaleSnapshot,
    absolute_url,
    clean_text,
    estimate_money,
    extract_meta,
    iso_date,
    money_value,
)
from ingestion.http import HttpClient


RESULTS_URL = "https://www.phillips.com/calendar/results"
BASE_URL = "https://www.phillips.com"
AUCTION_HOUSE = "Phillips"
RECORD_SOURCE = "Phillips public auction result page"
EXCLUDED_SALE_TERMS = (
    "watch",
    "jewel",
    "jewelry",
    "diamonds",
    "wine",
    "private-sales",
)


class PhillipsResultsConnector:
    """Fetch lot-level auction results from Phillips sale pages."""

    source_id = "phillips_auctions"
    source_name = "Phillips Auctions"

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
        auction = snapshot.lots_payload.get("auction") or {}
        for lot in auction.get("lots", []):
            if len(lots) >= limit:
                break
            item = phillips_lot_to_auction_lot(lot, snapshot, auction)
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
        data = extract_react_router_data(sale_html)
        auction = extract_auction_payload(data)
        sale_title = clean_text(
            auction.get("auctionName")
            or auction.get("auctionTitle")
            or extract_meta(sale_html, "og:title")
        )

        return AuctionHouseSaleSnapshot(
            source_id=self.source_id,
            source_name=self.source_name,
            sale_url=target_sale_url,
            sale_title=sale_title,
            sale_id=clean_text(auction.get("auctionCode") or auction.get("auctionId")),
            sale_number=clean_text(auction.get("auctionCode") or ""),
            raw_html=sale_html,
            lots_payload={"auction": auction},
        )

    def discover_sale_url(self, sale_query: str = "") -> str:
        results_html = self.client.get_text(RESULTS_URL)
        query = sale_query.strip().lower()
        try:
            data = extract_react_router_data(results_html)
            past_auctions = extract_past_auctions(data)
        except ValueError:
            past_auctions = []

        for auction in past_auctions:
            haystack = phillips_auction_haystack(auction)
            if query and query not in haystack:
                continue
            if any(term in haystack for term in EXCLUDED_SALE_TERMS):
                continue
            if auction.get("auctionUrl"):
                return auction["auctionUrl"]

        for auction in past_auctions:
            haystack = phillips_auction_haystack(auction)
            if not any(term in haystack for term in EXCLUDED_SALE_TERMS) and auction.get("auctionUrl"):
                return auction["auctionUrl"]

        candidates = []
        seen = set()
        for match in re.finditer(r"https://www\.phillips\.com/auction/[A-Z]{2}\d{6}", results_html):
            url = match.group(0)
            if url in seen:
                continue
            seen.add(url)
            context = clean_text(results_html[max(0, match.start() - 500) : match.end() + 500]).lower()
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

        raise ValueError("No Phillips public auction result URL found")


def phillips_lot_to_auction_lot(
    lot: Dict[str, Any],
    snapshot: AuctionHouseSaleSnapshot,
    auction: Dict[str, Any],
) -> Optional[AuctionLot]:
    lot_id = clean_text(lot.get("lotNumberFull") or lot.get("lotNumber"))
    source_record_id = clean_text(lot.get("objectNumber") or lot.get("id"))
    if not lot_id and not source_record_id:
        return None

    estimate = lot.get("estimate") or {}
    main_estimate = estimate.get("mainEstimate") or {}
    currency = clean_text(main_estimate.get("currencyCode") or (auction.get("auctionCurrency") or {}).get("currencyCode") or "")
    currency_symbol = clean_text(main_estimate.get("currencySymbol") or "")
    estimate_value = estimate_money(
        currency,
        main_estimate.get("lowEstimate"),
        main_estimate.get("highEstimate"),
        symbol=currency_symbol,
    )
    sold_price = money_value(currency, lot.get("soldPrice"), symbol=currency_symbol)

    return AuctionLot(
        source_id=PhillipsResultsConnector.source_id,
        source_name=PhillipsResultsConnector.source_name,
        auction_house=AUCTION_HOUSE,
        sale_id=snapshot.sale_id,
        sale_title=snapshot.sale_title,
        sale_url=snapshot.sale_url,
        lot_id=lot_id,
        source_record_id=source_record_id,
        title=clean_text(lot.get("description") or "Untitled lot"),
        artists=[clean_text(lot.get("makerName"))] if clean_text(lot.get("makerName")) else [],
        style=snapshot.sale_title,
        auction_date=iso_date(auction.get("auctionStartDateTime") or auction.get("auctionDate") or ""),
        currency=currency,
        estimate=MoneyValue.from_dict(estimate_value),
        result_price=MoneyValue.from_dict(sold_price) if clean_text(lot.get("lotStatus")).lower() == "sold" else None,
        source_url=absolute_url(clean_text(lot.get("detailLink")), BASE_URL) or snapshot.sale_url,
        image_url=clean_text(lot.get("mainImagePath") or ""),
        medium=clean_text(lot.get("medium") or ""),
        dimensions=clean_text(lot.get("dimensions") or ""),
        description=clean_text(lot.get("sigEdtMan") or ""),
        provenance=clean_text(lot.get("provenance") or ""),
        literature=clean_text(lot.get("literature") or ""),
        record_source=RECORD_SOURCE,
        notes="Starting price and prior sale price were not exposed in the public Phillips sale payload.",
        raw=lot,
    )


def extract_auction_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    loader_data = data.get("loaderData") or {}
    for value in loader_data.values():
        if isinstance(value, dict) and isinstance(value.get("auction"), dict):
            return value["auction"]
    raise ValueError("Could not find Phillips auction payload")


def extract_past_auctions(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    loader_data = data.get("loaderData") or {}
    for value in loader_data.values():
        if isinstance(value, dict) and isinstance(value.get("pastAuctions"), list):
            return value["pastAuctions"]
    return []


def phillips_auction_haystack(auction: Dict[str, Any]) -> str:
    departments = " ".join(
        clean_text(department.get("departmentDisplayName") or department.get("departmentName") or "")
        for department in auction.get("departments", [])
        if isinstance(department, dict)
    )
    return " ".join(
        clean_text(value)
        for value in (
            auction.get("auctionCode"),
            auction.get("auctionName"),
            auction.get("auctionLocation"),
            auction.get("auctionStatus"),
            departments,
        )
        if value
    ).lower()


def extract_react_router_data(html_text: str) -> Dict[str, Any]:
    for match in re.finditer(
        r"window\.__reactRouterContext\.streamController\.enqueue\((.*?)\);",
        html_text,
        flags=re.DOTALL,
    ):
        arg = match.group(1).strip()
        try:
            stream_payload = json.loads(arg)
            values = json.loads(stream_payload)
        except json.JSONDecodeError:
            continue
        if isinstance(values, list) and values:
            decoded = decode_react_router_values(values)
            if isinstance(decoded, dict) and decoded.get("loaderData"):
                return decoded

    raise ValueError("Could not decode Phillips React Router payload")


def decode_react_router_values(values: List[Any]) -> Any:
    @lru_cache(maxsize=None)
    def resolve_index(index: int) -> Any:
        if index < 0:
            return None
        return resolve(values[index])

    def resolve(value: Any) -> Any:
        if isinstance(value, dict):
            output = {}
            for key, nested in value.items():
                resolved_key = resolve_index(int(key[1:])) if key.startswith("_") and key[1:].isdigit() else key
                output[resolved_key] = resolve_index(nested) if isinstance(nested, int) else resolve(nested)
            return output
        if isinstance(value, list):
            return [resolve_index(item) if isinstance(item, int) else resolve(item) for item in value]
        return value

    return resolve_index(0)
