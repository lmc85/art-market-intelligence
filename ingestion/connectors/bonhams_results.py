"""Connector for Bonhams public auction result pages."""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple

from ingestion.auction_models import AuctionLot, MoneyValue
from ingestion.connectors.auction_results_common import (
    AuctionHouseSaleSnapshot,
    absolute_url,
    clean_html_lines,
    clean_multiline_text,
    clean_text,
    estimate_money,
    extract_medium_dimensions_from_lines,
    extract_meta,
    extract_next_data,
    iso_date,
    money_value,
    parse_float,
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

    def fetch_lot_detail_html(self, lot_url: str) -> str:
        return self.client.get_text(lot_url)

    def enrich_lots_with_details(
        self,
        lots: List[AuctionLot],
        limit: int = 0,
        delay_seconds: float = 0.2,
    ) -> Tuple[List[AuctionLot], List[Dict[str, Any]]]:
        detail_limit = len(lots) if limit <= 0 else min(limit, len(lots))
        snapshots: List[Dict[str, Any]] = []

        for index, lot in enumerate(lots[:detail_limit]):
            if not lot.source_url:
                continue

            try:
                raw_html = self.fetch_lot_detail_html(lot.source_url)
                detail_payload = extract_bonhams_lot_detail_payload(raw_html)
                enrich_bonhams_lot_from_detail(lot, detail_payload)
                snapshots.append(
                    {
                        "status": "ok",
                        "lot_id": lot.lot_id,
                        "source_record_id": lot.source_record_id,
                        "source_url": lot.source_url,
                        "detail_payload": detail_payload,
                        "raw_html": raw_html,
                    }
                )
            except Exception as exc:
                lot.notes = f"{lot.notes} Detail enrichment failed: {exc}".strip()
                snapshots.append(
                    {
                        "status": "error",
                        "lot_id": lot.lot_id,
                        "source_record_id": lot.source_record_id,
                        "source_url": lot.source_url,
                        "error": str(exc),
                    }
                )

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


def extract_bonhams_lot_detail_payload(raw_html: str) -> Dict[str, Any]:
    data = extract_next_data(raw_html)
    return data.get("props", {}).get("pageProps", {}).get("lot") or {}


def enrich_bonhams_lot_from_detail(lot: AuctionLot, detail: Dict[str, Any]) -> AuctionLot:
    currency = clean_text((detail.get("currency") or {}).get("iso_code") or lot.currency)
    currency_symbol = clean_text(detail.get("sCurrencySymbol") or "")
    estimate = estimate_money(currency, detail.get("dEstimateLow"), detail.get("dEstimateHigh"), symbol=currency_symbol)
    result = money_value(currency, detail.get("dHammerPremium") or detail.get("dHammerPrice"), symbol=currency_symbol)
    starting_amount = parse_float(detail.get("dStartingBidAmt"))
    starting = (
        money_value(currency, starting_amount, symbol=currency_symbol)
        if starting_amount is not None and starting_amount > 0
        else None
    )

    catalog_lines = clean_html_lines(detail.get("sCatalogDesc") or detail.get("sDesc") or "")
    medium, dimensions = extract_medium_dimensions_from_lines(catalog_lines)
    sections = extract_bonhams_footnote_sections(detail.get("footnote_sExtraDesc") or detail.get("sExtraDesc") or "")
    images = detail.get("images") or []

    if currency:
        lot.currency = currency
    if estimate:
        lot.estimate = MoneyValue.from_dict(estimate)
    if result and clean_text(detail.get("sLotStatus")).upper() == "SOLD":
        lot.result_price = MoneyValue.from_dict(result)
    if starting:
        lot.starting_price = MoneyValue.from_dict(starting)
    if catalog_lines:
        lot.description = "\n".join(catalog_lines)
    if medium:
        lot.medium = medium
    if dimensions:
        lot.dimensions = dimensions
    if sections.get("provenance"):
        lot.provenance = sections["provenance"]
    if sections.get("literature"):
        lot.literature = sections["literature"]
    if sections.get("exhibited") and not lot.literature:
        lot.literature = sections["exhibited"]
    if images:
        lot.image_url = lot.image_url or clean_text(images[0].get("image_url") or "")

    lot.notes = append_detail_note(lot.notes, "Enriched from Bonhams public lot detail page.")
    lot.raw = {**(lot.raw or {}), "detail_enrichment": {"sections": sorted(sections), "image_count": len(images)}}
    return lot


def extract_bonhams_footnote_sections(raw_html: str) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    if not raw_html:
        return sections

    parts = re.split(r"<b>(.*?)</b>\s*<br\s*/?>", raw_html, flags=re.IGNORECASE | re.DOTALL)
    for index in range(1, len(parts), 2):
        key = clean_text(parts[index]).lower()
        section_html = parts[index + 1] if index + 1 < len(parts) else ""
        section_html = re.split(r"<br\s*/?>\s*<br\s*/?>", section_html, maxsplit=1, flags=re.IGNORECASE)[0]
        value = clean_multiline_text(section_html)
        if key and value:
            sections[key] = value
    return sections


def append_detail_note(existing: str, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing} {note}"


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
