"""Connector for Saffronart's public auction-events JSON web service.

Saffronart (India / South Asia) exposes an unauthenticated WCF JSON endpoint that
lists every art auction it has run, including title, dates, status, and a relative
results URL. The endpoint is genuinely free and consumable with the standard
library, which fills the app's India / South Asia regional gap.

Scope note: this service returns *sale events*, not lot-level realized prices. The
per-auction results pages that carry hammer prices block automated fetchers
(HTTP 403 / anti-bot), so this connector deliberately stays at the auction-calendar
level and records each event as a structured sale, leaving lot enrichment for a
later, terms-cleared pass.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ingestion.http import HttpClient
from ingestion.models import utc_now_iso


SERVICE_URL = "https://www.saffronart.com/Service1.svc/FetchAllSaffronAuctions/"
SITE_BASE_URL = "https://www.saffronart.com/"
SOURCE_ID = "saffronart_auctions"
SOURCE_NAME = "Saffronart Auctions"
AUCTION_HOUSE = "Saffronart"
RECORD_SOURCE = "Saffronart public auctions JSON web service"
REGION = "India / South Asia"

# EventStatus values observed on the live service.
STATUS_LABELS = {
    3: "past",
    6: "live",
}

_WCF_DATE_RE = re.compile(r"/Date\((-?\d+)(?P<offset>[+-]\d{4})?\)/")


@dataclass
class SaffronartAuctionEvent:
    """A normalized Saffronart sale event."""

    source_id: str
    source_name: str
    auction_house: str
    region: str
    sale_id: str
    title: str
    status: str
    auction_type: str
    start_date: str
    end_date: str
    date_display: str
    source_url: str
    banner_image_url: str
    record_source: str
    raw: Dict[str, Any]
    ingested_at: str

    def as_record(self) -> Dict[str, Any]:
        record = asdict(self)
        record.pop("raw", None)
        return record


class SaffronartResultsConnector:
    """Fetch Saffronart auction events from the public JSON web service."""

    source_id = SOURCE_ID
    source_name = SOURCE_NAME

    def __init__(self, client: Optional[HttpClient] = None):
        self.client = client or HttpClient()

    def fetch_events(
        self,
        limit: int = 0,
        statuses: Optional[List[int]] = None,
        auction_type: str = "ART",
    ) -> List[SaffronartAuctionEvent]:
        """Return normalized auction events, newest first.

        ``limit`` of 0 returns every event. ``statuses`` filters by raw
        ``EventStatus`` codes (e.g. ``[3]`` for past sales only).
        """

        payload = self.client.get_json(SERVICE_URL, {"AucType": auction_type})
        raw_events = flatten_events(payload)
        status_filter = set(statuses) if statuses else None

        events: List[SaffronartAuctionEvent] = []
        for raw in raw_events:
            if status_filter is not None and raw.get("EventStatus") not in status_filter:
                continue
            event = normalize_event(raw)
            if event:
                events.append(event)

        events.sort(key=_event_sort_key, reverse=True)
        if limit and limit > 0:
            return events[:limit]
        return events


def flatten_events(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten the service's nested ``Events`` groups into a single list.

    The service returns ``Events`` as a list of lists (upcoming / live / past
    buckets), most of which are empty. Anything else is treated as no events.
    """

    groups = (payload or {}).get("Events")
    if not isinstance(groups, list):
        return []

    flat: List[Dict[str, Any]] = []
    for group in groups:
        if isinstance(group, list):
            flat.extend(item for item in group if isinstance(item, dict))
        elif isinstance(group, dict):
            flat.append(group)
    return flat


def normalize_event(raw: Dict[str, Any]) -> Optional[SaffronartAuctionEvent]:
    sale_id = str(raw.get("EventId") or "").strip()
    title = clean_text(raw.get("Title") or "")
    if not sale_id or not title:
        return None

    start_date = parse_wcf_date(raw.get("EventStartDate"))
    end_date = parse_wcf_date(raw.get("EventEndDate"))
    status_code = raw.get("EventStatus")

    return SaffronartAuctionEvent(
        source_id=SOURCE_ID,
        source_name=SOURCE_NAME,
        auction_house=AUCTION_HOUSE,
        region=REGION,
        sale_id=sale_id,
        title=title,
        status=STATUS_LABELS.get(status_code, f"status_{status_code}"),
        auction_type=auction_type_label(raw.get("AuctionType")),
        start_date=start_date,
        end_date=end_date,
        date_display=clean_text(raw.get("EventFullDate") or raw.get("EventDate") or ""),
        source_url=absolute_url(raw.get("URL") or ""),
        banner_image_url=absolute_url(raw.get("BannerImage") or ""),
        record_source=RECORD_SOURCE,
        raw=raw,
        ingested_at=utc_now_iso(),
    )


def parse_wcf_date(value: Any) -> str:
    """Convert a WCF ``/Date(epoch_ms-offset)/`` string to an ISO calendar date.

    The offset is applied so the rendered date matches Saffronart's own
    ``EventFullDate`` display; an empty or unparseable value yields ``""``.
    """

    match = _WCF_DATE_RE.search(str(value or ""))
    if not match:
        return ""

    milliseconds = int(match.group(1))
    moment = datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)

    offset = match.group("offset")
    if offset:
        sign = 1 if offset[0] == "+" else -1
        moment = moment + sign * timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5]))

    return moment.date().isoformat()


def auction_type_label(value: Any) -> str:
    # The ART feed reports AuctionType 0 uniformly; keep the raw code if it ever varies.
    if value in (None, "", 0):
        return "art"
    return f"type_{value}"


def absolute_url(path: str) -> str:
    path = (path or "").strip()
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    return SITE_BASE_URL + path.lstrip("/")


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.split())


def _event_sort_key(event: SaffronartAuctionEvent):
    # Sort by start date when known, falling back to numeric sale id so the
    # newest auctions surface first even when a date is missing.
    try:
        sale_ordinal = int(event.sale_id)
    except ValueError:
        sale_ordinal = 0
    return (event.start_date or "", sale_ordinal)
