"""Shared helpers for public auction-house result connectors."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin


@dataclass
class AuctionHouseSaleSnapshot:
    source_id: str
    source_name: str
    sale_url: str
    sale_title: str
    raw_html: str
    lots_payload: Dict[str, Any] = field(default_factory=dict)
    sale_id: str = ""
    sale_number: str = ""
    notes: List[str] = field(default_factory=list)


class AccessBlockedError(RuntimeError):
    """Raised when a source blocks direct public HTTP access."""


def extract_next_data(html_text: str) -> Dict[str, Any]:
    match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError("Could not find __NEXT_DATA__ payload")
    return json.loads(html.unescape(match.group(1)))


def extract_json_ld(html_text: str) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        try:
            payload = json.loads(html.unescape(match.group(1)))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def extract_meta(html_text: str, *names: str) -> str:
    for name in names:
        patterns = (
            rf'<meta[^>]+property=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)["\']',
            rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']*)["\']',
            rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']{re.escape(name)}["\']',
        )
        for pattern in patterns:
            match = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                return clean_text(match.group(1))

    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    return clean_text(title_match.group(1)) if title_match else ""


def clean_html_lines(value: Any) -> List[str]:
    text = "" if value is None else str(value)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(?:p|div|li|h\d)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    decoded = html.unescape(text)
    return [clean_text(line) for line in decoded.splitlines() if clean_text(line)]


def clean_multiline_text(value: Any) -> str:
    return "\n".join(clean_html_lines(value))


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(" ".join(text.split()))


def parse_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        match = re.search(r"-?\d[\d,]*(?:\.\d+)?", value)
        value = match.group(0).replace(",", "") if match else value.strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def iso_date(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10]


def absolute_url(url: str, base_url: str) -> str:
    if not url:
        return ""
    return urljoin(base_url, html.unescape(url))


def estimate_money(
    currency: str,
    low: Any,
    high: Any,
    symbol: str = "",
    display: str = "",
) -> Optional[Dict[str, Any]]:
    low_value = parse_float(low)
    high_value = parse_float(high)
    if low_value is None and high_value is None and not display:
        return None
    return {
        "currency": currency,
        "low": low_value,
        "high": high_value,
        "display": display or range_display(currency, low_value, high_value, symbol=symbol),
    }


def money_value(
    currency: str,
    amount: Any,
    symbol: str = "",
    display: str = "",
) -> Optional[Dict[str, Any]]:
    amount_value = parse_float(amount)
    if amount_value is None and not display:
        return None
    return {
        "currency": currency,
        "amount": amount_value,
        "display": display or amount_display(currency, amount_value, symbol=symbol),
    }


def range_display(
    currency: str,
    low: Optional[float],
    high: Optional[float],
    symbol: str = "",
) -> str:
    prefix = symbol or currency
    if low is None and high is None:
        return ""
    if low is not None and high is not None:
        return f"{prefix} {low:,.0f} - {high:,.0f}".strip()
    value = low if low is not None else high
    return f"{prefix} {value:,.0f}".strip()


def amount_display(currency: str, amount: Optional[float], symbol: str = "") -> str:
    if amount is None:
        return ""
    prefix = symbol or currency
    return f"{prefix} {amount:,.0f}".strip()


def extract_medium_dimensions_from_lines(lines: List[str]) -> tuple[str, str]:
    for index, line in enumerate(lines):
        if looks_like_dimensions(line):
            return previous_catalogue_line(lines, index), clean_text(line)
    return "", ""


def previous_catalogue_line(lines: List[str], index: int) -> str:
    for candidate in reversed(lines[:index]):
        text = clean_text(candidate)
        lower = text.lower()
        if not text:
            continue
        if lower.startswith(("signed", "dated", "titled", "numbered", "stamped", "executed", "painted")):
            continue
        if text.isupper():
            continue
        return text
    return ""


def looks_like_dimensions(value: str) -> bool:
    lower = value.lower()
    has_measure_unit = any(unit in lower for unit in (" cm", " mm", " in.", " in ", " inch"))
    has_separator = " x " in lower or "\u00d7" in lower or " by " in lower
    return has_measure_unit and has_separator


def append_note(existing: str, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing} {note}"
