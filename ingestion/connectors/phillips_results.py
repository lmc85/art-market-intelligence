"""Connector for Phillips public auction result pages."""

from __future__ import annotations

import json
import re
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from ingestion.auction_models import AuctionLot, MoneyValue
from ingestion.connectors.auction_results_common import (
    AuctionHouseSaleSnapshot,
    absolute_url,
    clean_multiline_text,
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

    def fetch_lot_detail_html(self, lot_url: str) -> str:
        return self.client.get_text(lot_url)

    def enrich_lots_with_details(
        self,
        lots: List[AuctionLot],
        limit: int = 0,
        delay_seconds: float = 0.2,
    ) -> Tuple[List[AuctionLot], List[Dict[str, Any]]]:
        detail_urls = []
        seen = set()
        for lot in lots:
            if lot.source_url and lot.source_url not in seen:
                seen.add(lot.source_url)
                detail_urls.append(lot.source_url)

        detail_limit = 1 if limit <= 0 else min(limit, len(detail_urls))
        snapshots: List[Dict[str, Any]] = []

        for index, detail_url in enumerate(detail_urls[:detail_limit]):
            try:
                raw_html = self.fetch_lot_detail_html(detail_url)
                data = extract_react_router_data(raw_html)
                detail_lots = extract_lot_detail_payloads(data)
                enrich_phillips_lots_from_detail_payloads(lots, detail_lots)
                snapshots.append(
                    {
                        "status": "ok",
                        "source_url": detail_url,
                        "detail_lot_count": len(detail_lots),
                        "detail_payloads": detail_lots,
                        "raw_html": raw_html,
                    }
                )
            except Exception as exc:
                snapshots.append({"status": "error", "source_url": detail_url, "error": str(exc)})

            if delay_seconds > 0 and index < detail_limit - 1:
                time.sleep(delay_seconds)

        return lots, snapshots

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

    def discover_sale_urls(self, sale_query: str = "", limit_sales: int = 0) -> List[Dict[str, str]]:
        """Return many past art sales (newest first) for multi-year backfill.

        Each item is ``{"url", "date", "name"}``. The Phillips results page lists
        the full past-auction archive (currently 2013 onward), so this is the
        connector's deep history lane; watches/jewels/wine sales are filtered out.
        """

        results_html = self.client.get_text(RESULTS_URL)
        try:
            past_auctions = extract_past_auctions(extract_react_router_data(results_html))
        except ValueError:
            past_auctions = []
        return select_phillips_sales(past_auctions, sale_query=sale_query, limit_sales=limit_sales)

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
        medium=clean_multiline_text(lot.get("medium") or ""),
        dimensions=clean_multiline_text(lot.get("dimensions") or ""),
        description=clean_multiline_text(lot.get("sigEdtMan") or ""),
        provenance=clean_multiline_text(lot.get("provenance") or ""),
        literature=clean_multiline_text(lot.get("literature") or ""),
        record_source=RECORD_SOURCE,
        notes="Starting price and prior sale price were not exposed in the public Phillips sale payload.",
        raw=lot,
    )


def enrich_phillips_lots_from_detail_payloads(
    lots: List[AuctionLot],
    detail_lots: List[Dict[str, Any]],
) -> List[AuctionLot]:
    details_by_record = {
        clean_text(detail.get("objectNumber")): detail
        for detail in detail_lots
        if detail.get("objectNumber")
    }
    details_by_lot = {
        clean_text(detail.get("lotNumberFull") or detail.get("lotNumber")): detail
        for detail in detail_lots
        if detail.get("lotNumberFull") or detail.get("lotNumber")
    }

    for lot in lots:
        detail = details_by_record.get(lot.source_record_id) or details_by_lot.get(lot.lot_id)
        if detail:
            enrich_phillips_lot_from_detail(lot, detail)
    return lots


def enrich_phillips_lot_from_detail(lot: AuctionLot, detail: Dict[str, Any]) -> AuctionLot:
    if detail.get("medium"):
        lot.medium = clean_multiline_text(detail.get("medium"))
    if detail.get("dimensions"):
        lot.dimensions = clean_multiline_text(detail.get("dimensions"))
    if detail.get("sigEdtMan"):
        lot.description = clean_multiline_text(detail.get("sigEdtMan"))
    if detail.get("provenance"):
        lot.provenance = clean_multiline_text(detail.get("provenance"))
    if detail.get("literature"):
        lot.literature = clean_multiline_text(detail.get("literature"))
    if detail.get("mainImagePath"):
        lot.image_url = lot.image_url or clean_text(detail.get("mainImagePath"))

    lot.notes = append_detail_note(lot.notes, "Enriched from Phillips public lot detail page.")
    lot.raw = {
        **(lot.raw or {}),
        "detail_enrichment": {
            "objectNumber": detail.get("objectNumber"),
            "has_medium": bool(lot.medium),
            "has_dimensions": bool(lot.dimensions),
            "has_provenance": bool(lot.provenance),
            "has_literature": bool(lot.literature),
        },
    }
    return lot


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


def select_phillips_sales(
    past_auctions: List[Dict[str, Any]],
    sale_query: str = "",
    limit_sales: int = 0,
) -> List[Dict[str, str]]:
    """Filter the past-auction list to ingestible art sales, newest first.

    Drops watches/jewels/wine (``EXCLUDED_SALE_TERMS``), applies an optional
    title/url query, and caps the count at ``limit_sales`` (0 = no cap).
    """

    query = sale_query.strip().lower()
    selected: List[Dict[str, str]] = []
    for auction in past_auctions:
        url = auction.get("auctionUrl")
        if not url:
            continue
        name = clean_text(auction.get("auctionName") or "")
        haystack = f"{name} {url}".lower()
        if any(term in haystack for term in EXCLUDED_SALE_TERMS):
            continue
        if query and query not in haystack:
            continue
        selected.append({"url": url, "date": (auction.get("auctionStartDateTime") or "")[:10], "name": name})
        if limit_sales and len(selected) >= limit_sales:
            break
    return selected


def extract_lot_detail_payloads(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    loader_data = data.get("loaderData") or {}
    for value in loader_data.values():
        if not isinstance(value, dict):
            continue
        lot_payload = value.get("lot")
        if isinstance(lot_payload, list):
            return [lot for lot in lot_payload if isinstance(lot, dict)]
        if isinstance(lot_payload, dict):
            return [lot_payload]
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
    for arg in react_router_enqueue_args(html_text):
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


def react_router_enqueue_args(html_text: str) -> List[str]:
    needle = "window.__reactRouterContext.streamController.enqueue("
    args = []
    offset = 0
    while True:
        start = html_text.find(needle, offset)
        if start < 0:
            break
        arg_start = start + len(needle)
        arg, end = read_js_call_argument(html_text, arg_start)
        if arg:
            args.append(arg.strip())
        offset = end + 2
    return args


def read_js_call_argument(text: str, start: int) -> Tuple[str, int]:
    in_string = False
    quote = ""
    escaped = False

    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                in_string = False
            continue

        if char in ("'", '"'):
            in_string = True
            quote = char
            continue

        if char == ")" and text[index : index + 2] == ");":
            return text[start:index], index

    return "", len(text)


def append_detail_note(existing: str, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing} {note}"


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
