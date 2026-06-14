"""Connector for a global art-fair calendar via Artsy's Metaphysics GraphQL API.

Artsy exposes an unauthenticated GraphQL endpoint that returns fair names, ISO-8601
start/end dates, and a slug, consumable with the standard library (urllib + json).
It is the most structured free art-events source available; dedicated fair sites are
either scrape-only with no Event markup or anti-bot protected.

Scope notes the data forces on us:
  * The API's ``location`` / ``summary`` / ``organizer`` fields return null, so city,
    country, and region are *derived from the fair name* (which nearly always carries
    the city, e.g. "Frieze Seoul 2026"). This is a heuristic and will miss or
    mis-tag some fairs.
  * Access facets the app wants — invitation-only vs public, free vs ticketed — are
    not exposed by any structured source, so ``access`` is recorded as "unknown"
    rather than guessed. A later classifier / curation layer can fill it in.

The endpoint is an internal Artsy API with no stability guarantee; treat breakage as
expected and keep the connector non-fatal.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from ingestion.http import HttpClient
from ingestion.models import utc_now_iso


METAPHYSICS_URL = "https://metaphysics-production.artsy.net/v2"
ARTSY_BASE_URL = "https://www.artsy.net"
SOURCE_ID = "artsy_fairs"
SOURCE_NAME = "Artsy Fairs"
RECORD_SOURCE = "Artsy Metaphysics GraphQL fairs query"

FAIRS_QUERY = (
    "query Fairs($size: Int!, $page: Int!) {"
    " fairs(size: $size, page: $page, sort: START_AT_DESC) {"
    " name slug href startAt endAt isActive } }"
)

# US cities/keywords drive the US-vs-International region facet. Order does not
# matter within a country; multi-word keys are matched as substrings of the name.
_LOCATION_KEYWORDS = [
    # United States
    (("new york", "nyc", "armory show", "hamptons", "tribeca"), "New York", "United States", "US"),
    (("miami", "art basel miami", "untitled miami"), "Miami", "United States", "US"),
    (("los angeles", "frieze los angeles", "la art", "felix"), "Los Angeles", "United States", "US"),
    (("chicago", "expo chicago"), "Chicago", "United States", "US"),
    (("san francisco", "fog design"), "San Francisco", "United States", "US"),
    (("dallas",), "Dallas", "United States", "US"),
    (("aspen",), "Aspen", "United States", "US"),
    (("seattle",), "Seattle", "United States", "US"),
    (("santa fe",), "Santa Fe", "United States", "US"),
    # International
    (("basel", "liste"), "Basel", "Switzerland", "International"),
    (("london", "frieze masters"), "London", "United Kingdom", "International"),
    (("paris", "fiac"), "Paris", "France", "International"),
    (("seoul", "kiaf", "suwon"), "Seoul", "South Korea", "International"),
    (("hong kong", "art central"), "Hong Kong", "Hong Kong", "International"),
    (("singapore", "art sg"), "Singapore", "Singapore", "International"),
    (("tokyo",), "Tokyo", "Japan", "International"),
    (("shanghai", "west bund"), "Shanghai", "China", "International"),
    (("beijing",), "Beijing", "China", "International"),
    (("taipei",), "Taipei", "Taiwan", "International"),
    (("dubai", "art dubai"), "Dubai", "United Arab Emirates", "International"),
    (("abu dhabi",), "Abu Dhabi", "United Arab Emirates", "International"),
    (("maastricht", "tefaf"), "Maastricht", "Netherlands", "International"),
    (("amsterdam",), "Amsterdam", "Netherlands", "International"),
    (("cologne", "köln"), "Cologne", "Germany", "International"),
    (("berlin",), "Berlin", "Germany", "International"),
    (("munich",), "Munich", "Germany", "International"),
    (("vienna",), "Vienna", "Austria", "International"),
    (("brussels", "brafa"), "Brussels", "Belgium", "International"),
    (("madrid", "arco"), "Madrid", "Spain", "International"),
    (("barcelona",), "Barcelona", "Spain", "International"),
    (("ibiza",), "Ibiza", "Spain", "International"),
    (("santander",), "Santander", "Spain", "International"),
    (("milan", "milano", "miart"), "Milan", "Italy", "International"),
    (("turin", "torino", "artissima"), "Turin", "Italy", "International"),
    (("bologna", "arte fiera"), "Bologna", "Italy", "International"),
    (("venice", "venezia", "biennale"), "Venice", "Italy", "International"),
    (("lisbon", "arco lisboa"), "Lisbon", "Portugal", "International"),
    (("mexico", "zona maco", "guadalajara"), "Mexico City", "Mexico", "International"),
    (("são paulo", "sao paulo", "sp-arte"), "São Paulo", "Brazil", "International"),
    (("buenos aires", "arteba"), "Buenos Aires", "Argentina", "International"),
    (("bogota", "bogotá", "artbo"), "Bogotá", "Colombia", "International"),
    (("cape town", "investec"), "Cape Town", "South Africa", "International"),
    (("johannesburg", "joburg"), "Johannesburg", "South Africa", "International"),
    (("marrakech", "1-54"), "Marrakech", "Morocco", "International"),
    (("mumbai", "india art fair", "new delhi", "delhi"), "Mumbai", "India", "International"),
    (("sydney",), "Sydney", "Australia", "International"),
    (("melbourne",), "Melbourne", "Australia", "International"),
    (("toronto",), "Toronto", "Canada", "International"),
    (("africa basel",), "Basel", "Switzerland", "International"),
]

# Fair-type keywords, checked before the default "art_fair".
_FAIR_TYPE_KEYWORDS = [
    (("biennial", "biennale", "triennial", "triennale"), "biennial"),
    (("design",), "design_fair"),
    (("photo", "photograph"), "photography_fair"),
    (("print", "editions", "works on paper"), "prints_fair"),
    (("antique", "antiques"), "antiques_fair"),
    (("drawing",), "drawings_fair"),
]


@dataclass
class ArtFairEvent:
    """A normalized art-fair calendar event."""

    source_id: str
    source_name: str
    fair_id: str
    name: str
    start_date: str
    end_date: str
    year: Optional[int]
    city: str
    country: str
    region: str
    fair_type: str
    access: str
    status: str
    source_url: str
    is_active: bool
    record_source: str
    categories: List[str] = field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None
    ingested_at: str = field(default_factory=utc_now_iso)

    def as_record(self) -> Dict[str, Any]:
        record = asdict(self)
        record.pop("raw", None)
        return record


class ArtsyFairsConnector:
    """Fetch a forward-looking art-fair calendar from Artsy's GraphQL API."""

    source_id = SOURCE_ID
    source_name = SOURCE_NAME

    def __init__(self, client: Optional[HttpClient] = None):
        self.client = client or HttpClient()

    def fetch_fairs(
        self,
        limit: int = 0,
        pages: int = 3,
        page_size: int = 100,
        include_past: bool = False,
        today: Optional[str] = None,
    ) -> List[ArtFairEvent]:
        """Return normalized fairs sorted by start date (soonest first).

        Pages through the API, dedupes by slug, and — unless ``include_past`` is
        set — keeps only fairs whose end date (or start date when no end is given)
        is on or after ``today`` (defaults to the current date).
        """

        cutoff = today or date.today().isoformat()
        seen: Dict[str, ArtFairEvent] = {}

        for page in range(1, max(1, pages) + 1):
            nodes = self._fetch_page(page=page, page_size=page_size)
            if not nodes:
                break
            for node in nodes:
                event = normalize_fair(node, cutoff=cutoff)
                if not event:
                    continue
                if not include_past and not _is_current_or_future(event, cutoff):
                    continue
                seen.setdefault(event.fair_id, event)

        events = sorted(seen.values(), key=lambda e: (e.start_date or "9999", e.name))
        if limit and limit > 0:
            return events[:limit]
        return events

    def _fetch_page(self, page: int, page_size: int) -> List[Dict[str, Any]]:
        payload = self.client.post_json(
            METAPHYSICS_URL,
            {"query": FAIRS_QUERY, "variables": {"size": page_size, "page": page}},
        )
        if payload.get("errors"):
            messages = "; ".join(str(err.get("message", err)) for err in payload["errors"])
            raise RuntimeError(f"Artsy fairs query failed: {messages}")
        return ((payload.get("data") or {}).get("fairs")) or []


def normalize_fair(node: Dict[str, Any], cutoff: str = "") -> Optional[ArtFairEvent]:
    name = clean_text(node.get("name") or "")
    fair_id = str(node.get("slug") or node.get("href") or "").strip().lstrip("/")
    if not name or not fair_id:
        return None

    start_date = iso_day(node.get("startAt"))
    end_date = iso_day(node.get("endAt"))
    city, country, region = derive_location(name)
    fair_type = derive_fair_type(name)
    status = derive_status(start_date, end_date, cutoff or start_date)

    event = ArtFairEvent(
        source_id=SOURCE_ID,
        source_name=SOURCE_NAME,
        fair_id=fair_id,
        name=name,
        start_date=start_date,
        end_date=end_date,
        year=year_from_dates(start_date, end_date, name),
        city=city,
        country=country,
        region=region,
        fair_type=fair_type,
        access="unknown",
        status=status,
        source_url=absolute_url(node.get("href") or f"/fair/{fair_id}"),
        is_active=bool(node.get("isActive")),
        record_source=RECORD_SOURCE,
        raw=node,
    )
    event.categories = build_categories(event)
    return event


def derive_location(name: str) -> tuple[str, str, str]:
    haystack = name.lower()
    for keywords, city, country, region in _LOCATION_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return city, country, region
    return "", "", "International"


def derive_fair_type(name: str) -> str:
    haystack = name.lower()
    for keywords, label in _FAIR_TYPE_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return label
    return "art_fair"


def derive_status(start_date: str, end_date: str, cutoff: str) -> str:
    if not cutoff:
        return "scheduled"
    if start_date and start_date > cutoff:
        return "upcoming"
    if end_date and end_date < cutoff:
        return "past"
    if start_date and start_date <= cutoff and (not end_date or end_date >= cutoff):
        return "running"
    return "scheduled"


def build_categories(event: ArtFairEvent) -> List[str]:
    categories = [f"region:{event.region}", f"type:{event.fair_type}", f"status:{event.status}"]
    if event.country:
        categories.append(f"country:{event.country}")
    return categories


def _is_current_or_future(event: ArtFairEvent, cutoff: str) -> bool:
    horizon = event.end_date or event.start_date
    return bool(horizon) and horizon >= cutoff


def year_from_dates(start_date: str, end_date: str, name: str) -> Optional[int]:
    for value in (start_date, end_date):
        if value[:4].isdigit():
            return int(value[:4])
    match = re.search(r"\b(19|20)\d{2}\b", name)
    return int(match.group(0)) if match else None


def iso_day(value: Any) -> str:
    text = str(value or "")
    return text[:10] if len(text) >= 10 and text[4] == "-" else ""


def absolute_url(href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    if href.startswith(("http://", "https://")):
        return href
    return ARTSY_BASE_URL + ("" if href.startswith("/") else "/") + href


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.split())
