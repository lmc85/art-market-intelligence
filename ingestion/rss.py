"""RSS generation for auction and sale feed records."""

from __future__ import annotations

import json
from datetime import datetime, time, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from xml.etree import ElementTree as ET


ARTMI_NS = "https://artmarketintelligence.local/rss/1.0"
ATOM_NS = "http://www.w3.org/2005/Atom"

ET.register_namespace("artmi", ARTMI_NS)
ET.register_namespace("atom", ATOM_NS)


def load_auction_items(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_rss(
    items: Iterable[Dict[str, Any]],
    output_path: Path,
    site_url: str = "http://localhost:4173/",
    feed_url: str = "http://localhost:4173/feeds/auction-results.xml",
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_rss_xml(items, site_url=site_url, feed_url=feed_url),
        encoding="utf-8",
    )


def build_rss_xml(
    items: Iterable[Dict[str, Any]],
    site_url: str = "http://localhost:4173/",
    feed_url: str = "http://localhost:4173/feeds/auction-results.xml",
) -> str:
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    add_text(channel, "title", "Art Market Intelligence Auction Results")
    add_text(channel, "link", site_url)
    add_text(
        channel,
        "description",
        "Auction and sale records normalized for art market intelligence.",
    )
    add_text(channel, "language", "en-us")
    add_text(channel, "lastBuildDate", format_datetime(datetime.now(timezone.utc)))
    add_text(channel, "ttl", "60")
    ET.SubElement(
        channel,
        f"{{{ATOM_NS}}}link",
        {"href": feed_url, "rel": "self", "type": "application/rss+xml"},
    )

    for item in sorted(items, key=lambda record: record.get("auction_date", ""), reverse=True):
        add_item(channel, item)

    ET.indent(rss, space="  ")
    return ET.tostring(rss, encoding="unicode", xml_declaration=True)


def add_item(channel: ET.Element, item: Dict[str, Any]) -> None:
    artists = ", ".join(item.get("artists") or [])
    item_title = item.get("title") or "Untitled lot"
    auction_house = item.get("auction_house") or "Unknown auction house"
    auction_date = item.get("auction_date") or ""
    status = item.get("status") or "auctioned"
    link = item.get("source_url") or "http://localhost:4173/"

    node = ET.SubElement(channel, "item")
    add_text(node, "title", f"{item_title} - {auction_house}")
    add_text(node, "link", link)
    add_text(node, "guid", item.get("id") or f"{auction_house}-{item_title}-{auction_date}")
    add_text(node, "pubDate", rss_date(auction_date))
    add_text(node, "category", status)
    add_text(node, "description", description(item))

    add_artmi(node, "title", item_title)
    add_artmi(node, "artists", artists)
    add_artmi(node, "style", item.get("style"))
    add_artmi(node, "auctionHouse", auction_house)
    add_artmi(node, "auctionDate", auction_date)
    add_artmi(node, "status", status)
    add_artmi(node, "startingPrice", money_display(item.get("starting_price")))
    add_artmi(node, "estimatedSellingPrice", money_display(item.get("estimated_selling_price")))
    add_artmi(node, "resultPrice", money_display(item.get("result_price")))
    add_artmi(node, "lastSoldPrice", money_display(item.get("last_sold_price")))
    add_artmi(node, "recordSource", item.get("record_source"))


def description(item: Dict[str, Any]) -> str:
    lines = [
        f"Artist(s): {', '.join(item.get('artists') or []) or 'Not available'}",
        f"Style: {item.get('style') or 'Not available'}",
        f"Auction house: {item.get('auction_house') or 'Not available'}",
        f"Auction date: {item.get('auction_date') or 'Not available'}",
        f"Starting price: {money_display(item.get('starting_price')) or 'Not available'}",
        f"Estimated selling price: {money_display(item.get('estimated_selling_price')) or 'Not available'}",
        f"Result price: {money_display(item.get('result_price')) or 'Not available'}",
        f"Last sold price: {money_display(item.get('last_sold_price')) or 'Not available'}",
    ]
    if item.get("notes"):
        lines.append(f"Notes: {item['notes']}")
    return "\n".join(lines)


def money_display(value: Optional[Dict[str, Any]]) -> str:
    if not value:
        return ""
    if value.get("display"):
        return str(value["display"])
    currency = value.get("currency") or ""
    amount = value.get("amount")
    if amount is None:
        return ""
    return f"{currency} {amount}".strip()


def rss_date(value: str) -> str:
    try:
        parsed = datetime.combine(datetime.fromisoformat(value).date(), time(12, 0), timezone.utc)
    except ValueError:
        parsed = datetime.now(timezone.utc)
    return format_datetime(parsed)


def add_text(parent: ET.Element, tag: str, value: Any) -> ET.Element:
    child = ET.SubElement(parent, tag)
    child.text = "" if value is None else str(value)
    return child


def add_artmi(parent: ET.Element, tag: str, value: Any) -> Optional[ET.Element]:
    if value in (None, ""):
        return None
    return add_text(parent, f"{{{ARTMI_NS}}}{tag}", value)
