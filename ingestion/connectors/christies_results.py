"""Connector for Christie's public auction result pages."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Dict, Iterable, List, Optional

from ingestion.http import HttpClient


RESULTS_URL = "https://www.christies.com/results?sc_lang=en"
AUCTION_HOUSE = "Christie's"
RECORD_SOURCE = "Christie's public auction result page"
EXCLUDED_SALE_TERMS = (
    "wine",
    "jewel",
    "watch",
    "handbag",
    "whisky",
    "cellar",
    "sneaker",
    "real estate",
)


class ChristiesResultsConnector:
    """Fetch lot-level auction results from public Christie's sale pages."""

    source_id = "christies_results"
    source_name = "Christie's Results"

    def __init__(self, client: Optional[HttpClient] = None):
        self.client = client or HttpClient()

    def fetch_lots(
        self,
        limit: int = 10,
        sale_url: Optional[str] = None,
        sale_query: str = "",
    ) -> List[Dict[str, Any]]:
        if limit < 1:
            return []

        target_sale_url = sale_url or self.discover_sale_url(sale_query=sale_query)
        sale_html = self.client.get_text(target_sale_url)
        sale_title = extract_sale_title(sale_html)
        lots_payload = extract_component_data(sale_html, "window.chrComponents.lots")
        lots = lots_payload.get("lots", [])

        items = []
        for lot in lots:
            if len(items) >= limit:
                break
            item = lot_to_feed_item(lot, sale_title=sale_title, sale_url=target_sale_url)
            if item:
                items.append(item)
        return items

    def discover_sale_url(self, sale_query: str = "") -> str:
        results_html = self.client.get_text(RESULTS_URL)
        calendar = extract_component_data(results_html, "window.chrComponents.calendar")
        events = calendar.get("events") or []
        query = sale_query.strip().lower()

        for event in events:
            title = event.get("title_txt", "")
            subtitle = event.get("subtitle_txt", "")
            landing_url = event.get("landing_url", "")
            haystack = f"{title} {subtitle}".lower()
            if query and query not in haystack:
                continue
            if not landing_url.startswith("https://www.christies.com/en/auction/"):
                continue
            if any(term in haystack for term in EXCLUDED_SALE_TERMS):
                continue
            return landing_url

        for event in events:
            landing_url = event.get("landing_url", "")
            if landing_url.startswith("https://www.christies.com/en/auction/"):
                return landing_url

        raise ValueError("No Christie's public auction result URL found on the results page")


def lot_to_feed_item(lot: Dict[str, Any], sale_title: str, sale_url: str) -> Optional[Dict[str, Any]]:
    object_id = str(lot.get("object_id") or "").strip()
    lot_id = str(lot.get("lot_id_txt") or "").strip()
    if not object_id and not lot_id:
        return None

    auction_date = iso_date(lot.get("start_date") or "")
    artist = clean_text(lot.get("title_primary_txt") or "")
    title = clean_text(lot.get("title_secondary_txt") or lot.get("title_tertiary_txt") or "Untitled lot")
    estimate = estimate_price(lot)
    result = money_value(lot.get("price_realised"), lot.get("price_realised_txt"))

    return {
        "id": f"christies-{lot.get('analytics_id') or lot_id or object_id}",
        "status": "sold" if result else "auctioned",
        "title": title,
        "artists": [artist] if artist else [],
        "style": sale_title,
        "auction_house": AUCTION_HOUSE,
        "auction_date": auction_date,
        "starting_price": None,
        "estimated_selling_price": estimate,
        "result_price": result,
        "last_sold_price": None,
        "source_url": lot.get("url") or sale_url,
        "record_source": RECORD_SOURCE,
        "notes": "Starting price and prior sale price were not exposed in the public lot-list payload.",
    }


def extract_component_data(html_text: str, assignment: str) -> Dict[str, Any]:
    start = html_text.find(f"{assignment} =")
    if start < 0:
        raise ValueError(f"Could not find {assignment} payload")

    if assignment.endswith(".calendar"):
        data_pos = html_text.find("data:", start)
        if data_pos < 0:
            raise ValueError("Could not find calendar data payload")
        object_start = html_text.find("{", data_pos)
    else:
        object_start = html_text.find("{", html_text.find("=", start))

    if object_start < 0:
        raise ValueError(f"Could not find object start for {assignment}")

    text = balanced_json_object(html_text, object_start)
    payload = json.loads(text)
    return payload.get("data", payload)


def balanced_json_object(text: str, start: int) -> str:
    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    raise ValueError("Could not find balanced JSON object")


def extract_sale_title(html_text: str) -> str:
    for pattern in (
        r'<meta\s+property="og:title"\s+content="([^"]+)"',
        r'<meta\s+name="og:title"\s+content="([^"]+)"',
        r"<title>(.*?)</title>",
    ):
        match = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return clean_text(match.group(1))
    return "Christie's auction result"


def estimate_price(lot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    display = clean_text(lot.get("estimate_txt") or "")
    low = parse_float(lot.get("estimate_low"))
    high = parse_float(lot.get("estimate_high"))
    currency = display.split(" ", 1)[0] if display and " " in display else ""

    if not display and low is None and high is None:
        return None

    return {
        "currency": currency,
        "low": low,
        "high": high,
        "display": display or range_display(currency, low, high),
    }


def money_value(value: Any, display: Any) -> Optional[Dict[str, Any]]:
    display_text = clean_text(display or "")
    amount = parse_float(value)
    currency = display_text.split(" ", 1)[0] if display_text and " " in display_text else ""

    if not display_text and amount is None:
        return None

    return {
        "currency": currency,
        "amount": amount,
        "display": display_text or f"{currency} {amount}".strip(),
    }


def range_display(currency: str, low: Optional[float], high: Optional[float]) -> str:
    if low is None and high is None:
        return ""
    if low is not None and high is not None:
        return f"{currency} {low:,.0f} - {high:,.0f}".strip()
    value = low if low is not None else high
    return f"{currency} {value:,.0f}".strip()


def parse_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def iso_date(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return value[:10]


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(" ".join(text.split()))


class LinkTextParser(HTMLParser):
    """Small parser kept for future fallback extraction work."""

    def __init__(self):
        super().__init__()
        self.links: List[Dict[str, str]] = []
        self._href = ""
        self._text: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href", "")
            self._text = []

    def handle_data(self, data):
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            self.links.append({"href": self._href, "text": clean_text(" ".join(self._text))})
            self._href = ""
            self._text = []
