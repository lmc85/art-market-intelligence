"""Canonical models for auction result ingestion."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from ingestion.models import utc_now_iso


@dataclass
class MoneyValue:
    currency: str = ""
    amount: Optional[float] = None
    low: Optional[float] = None
    high: Optional[float] = None
    display: str = ""

    @classmethod
    def from_dict(cls, value: Optional[Dict[str, Any]]) -> Optional["MoneyValue"]:
        if not value:
            return None
        return cls(
            currency=str(value.get("currency") or ""),
            amount=value.get("amount"),
            low=value.get("low"),
            high=value.get("high"),
            display=str(value.get("display") or ""),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value not in (None, "")}


@dataclass
class AuctionLot:
    source_id: str
    source_name: str
    auction_house: str
    sale_id: str
    sale_title: str
    sale_url: str
    lot_id: str
    source_record_id: str
    title: str
    artists: List[str] = field(default_factory=list)
    style: str = ""
    auction_date: str = ""
    currency: str = ""
    estimate: Optional[MoneyValue] = None
    starting_price: Optional[MoneyValue] = None
    result_price: Optional[MoneyValue] = None
    last_sold_price: Optional[MoneyValue] = None
    last_sold_date: str = ""
    source_url: str = ""
    image_url: str = ""
    medium: str = ""
    dimensions: str = ""
    description: str = ""
    provenance: str = ""
    literature: str = ""
    record_source: str = ""
    notes: str = ""
    raw: Optional[Dict[str, Any]] = None
    ingested_at: str = field(default_factory=utc_now_iso)

    @property
    def identity_key(self) -> str:
        return "|".join(
            [
                self.source_id,
                self.auction_house.lower(),
                self.sale_id or self.sale_title.lower(),
                self.lot_id or self.source_record_id,
            ]
        )

    @property
    def status(self) -> str:
        return "sold" if self.result_price else "auctioned"

    def quality_flags(self) -> Dict[str, bool]:
        return {
            "has_artist": bool(self.artists),
            "has_title": bool(self.title),
            "has_auction_date": bool(self.auction_date),
            "has_estimate": bool(self.estimate and (self.estimate.low is not None or self.estimate.high is not None or self.estimate.display)),
            "has_result_price": bool(self.result_price and (self.result_price.amount is not None or self.result_price.display)),
            "has_starting_price": bool(self.starting_price),
            "has_prior_sale": bool(self.last_sold_price),
            "has_source_url": bool(self.source_url),
            "has_image": bool(self.image_url),
            "has_medium": bool(self.medium),
            "has_dimensions": bool(self.dimensions),
        }

    def prediction_ready(self) -> bool:
        flags = self.quality_flags()
        return all(
            [
                flags["has_artist"],
                flags["has_title"],
                flags["has_auction_date"],
                flags["has_estimate"],
                flags["has_result_price"],
                flags["has_source_url"],
            ]
        )

    def to_feed_item(self) -> Dict[str, Any]:
        return {
            "id": self.identity_key,
            "status": self.status,
            "title": self.title,
            "artists": self.artists,
            "style": self.style or self.sale_title,
            "auction_house": self.auction_house,
            "auction_date": self.auction_date,
            "starting_price": self.starting_price.as_dict() if self.starting_price else None,
            "estimated_selling_price": self.estimate.as_dict() if self.estimate else None,
            "result_price": self.result_price.as_dict() if self.result_price else None,
            "last_sold_price": self.last_sold_price.as_dict() if self.last_sold_price else None,
            "source_url": self.source_url,
            "record_source": self.record_source,
            "notes": self.notes,
            "medium": self.medium,
            "dimensions": self.dimensions,
            "provenance": self.provenance,
            "literature": self.literature,
            "quality_flags": self.quality_flags(),
            "prediction_ready": self.prediction_ready(),
        }

    def as_db_values(self) -> Dict[str, Any]:
        estimate = self.estimate or MoneyValue()
        starting = self.starting_price or MoneyValue()
        result = self.result_price or MoneyValue()
        last_sold = self.last_sold_price or MoneyValue()
        flags = self.quality_flags()

        return {
            "identity_key": self.identity_key,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "auction_house": self.auction_house,
            "sale_id": self.sale_id,
            "sale_title": self.sale_title,
            "sale_url": self.sale_url,
            "lot_id": self.lot_id,
            "source_record_id": self.source_record_id,
            "title": self.title,
            "artists_json": json.dumps(self.artists, ensure_ascii=False),
            "style": self.style,
            "auction_date": self.auction_date,
            "currency": self.currency,
            "estimate_low": estimate.low,
            "estimate_high": estimate.high,
            "estimate_display": estimate.display,
            "starting_price_amount": starting.amount,
            "starting_price_display": starting.display,
            "result_price_amount": result.amount,
            "result_price_display": result.display,
            "last_sold_price_amount": last_sold.amount,
            "last_sold_price_display": last_sold.display,
            "last_sold_date": self.last_sold_date,
            "source_url": self.source_url,
            "image_url": self.image_url,
            "medium": self.medium,
            "dimensions": self.dimensions,
            "description": self.description,
            "provenance": self.provenance,
            "literature": self.literature,
            "record_source": self.record_source,
            "notes": self.notes,
            "quality_flags_json": json.dumps(flags, ensure_ascii=False, sort_keys=True),
            "prediction_ready": 1 if self.prediction_ready() else 0,
            "last_seen_at": self.ingested_at,
            "raw_json": json.dumps(self.raw or {}, ensure_ascii=False),
        }


def lot_from_row(row: Dict[str, Any]) -> AuctionLot:
    estimate = money_from_row(row, "estimate", low_key="estimate_low", high_key="estimate_high")
    starting = money_from_row(row, "starting_price")
    result = money_from_row(row, "result_price")
    last_sold = money_from_row(row, "last_sold_price")

    return AuctionLot(
        source_id=row["source_id"],
        source_name=row["source_name"],
        auction_house=row["auction_house"],
        sale_id=row["sale_id"],
        sale_title=row["sale_title"],
        sale_url=row["sale_url"],
        lot_id=row["lot_id"],
        source_record_id=row["source_record_id"],
        title=row["title"],
        artists=json.loads(row["artists_json"] or "[]"),
        style=row["style"],
        auction_date=row["auction_date"],
        currency=row["currency"],
        estimate=estimate,
        starting_price=starting,
        result_price=result,
        last_sold_price=last_sold,
        last_sold_date=row["last_sold_date"],
        source_url=row["source_url"],
        image_url=row["image_url"],
        medium=row["medium"],
        dimensions=row["dimensions"],
        description=row["description"],
        provenance=row.get("provenance", ""),
        literature=row.get("literature", ""),
        record_source=row["record_source"],
        notes=row["notes"],
        raw=json.loads(row["raw_json"] or "{}"),
        ingested_at=row["last_seen_at"],
    )


def money_from_row(
    row: Dict[str, Any],
    prefix: str,
    low_key: str = "",
    high_key: str = "",
) -> Optional[MoneyValue]:
    display = row.get(f"{prefix}_display") or ""
    amount = row.get(f"{prefix}_amount")
    low = row.get(low_key) if low_key else None
    high = row.get(high_key) if high_key else None
    if display in ("", None) and amount is None and low is None and high is None:
        return None
    return MoneyValue(
        currency=row.get("currency") or "",
        amount=amount,
        low=low,
        high=high,
        display=display or "",
    )
