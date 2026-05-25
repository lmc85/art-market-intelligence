"""Derived market index generation from normalized auction lots."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Tuple

from ingestion.auction_store import DEFAULT_DB_PATH
from ingestion.models import utc_now_iso


def load_indexable_lots(db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT *
            FROM auction_lots
            WHERE result_price_amount IS NOT NULL
              AND result_price_amount > 0
              AND auction_date IS NOT NULL
              AND auction_date <> ''
            ORDER BY auction_date ASC, identity_key ASC
            """
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def build_market_index_payload(
    lots: Iterable[Dict[str, Any]],
    source_db: Path = DEFAULT_DB_PATH,
    min_lots_per_series: int = 1,
) -> Dict[str, Any]:
    records = [normalize_lot(row) for row in lots]
    records = [record for record in records if record.get("result_amount")]
    series = build_index_series(records, min_lots_per_series=min_lots_per_series)
    return {
        "generated_at": utc_now_iso(),
        "source": {
            "type": "internal_auction_results",
            "db_path": str(source_db),
            "method": "Median realized-price index, rebased to 100 at the first observed period.",
            "caveat": "Prototype indices are only as strong as the available normalized lot history.",
        },
        "summary": {
            "lot_count": len(records),
            "index_count": len(series),
            "history_ready_count": sum(1 for item in series if item["status"] == "history_ready"),
            "needs_more_history_count": sum(1 for item in series if item["status"] != "history_ready"),
        },
        "indices": series,
    }


def build_index_series(
    records: List[Dict[str, Any]],
    min_lots_per_series: int = 1,
) -> List[Dict[str, Any]]:
    buckets: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        buckets[("market", "All auction results")].append(record)
        if record["primary_artist"]:
            buckets[("artist", record["primary_artist"])].append(record)
        if record["style"]:
            buckets[("sale_context", record["style"])].append(record)
        if record["medium_family"]:
            buckets[("medium", record["medium_family"])].append(record)

    series = []
    for (series_type, label), bucket_records in buckets.items():
        if len(bucket_records) < min_lots_per_series:
            continue
        series.append(make_series(series_type, label, bucket_records))

    return sorted(
        series,
        key=lambda item: (
            item["status"] != "history_ready",
            -item["lot_count"],
            item["series_type"],
            item["label"],
        ),
    )


def make_series(series_type: str, label: str, records: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_period: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_period[record["period"]].append(record)

    period_points = []
    base_median = None
    for period in sorted(by_period):
        period_records = by_period[period]
        results = [record["result_amount"] for record in period_records if record["result_amount"]]
        estimates = [
            estimate_midpoint(record)
            for record in period_records
            if estimate_midpoint(record) is not None
        ]
        ratios = [
            record["result_amount"] / estimate_midpoint(record)
            for record in period_records
            if record["result_amount"] and estimate_midpoint(record)
        ]
        period_median = median(results) if results else 0
        if base_median is None:
            base_median = period_median or 1

        period_points.append(
            {
                "period": period,
                "index_value": round((period_median / base_median) * 100, 2) if base_median else 100,
                "lots_sold": len(period_records),
                "total_value": round(sum(results), 2),
                "median_result": round(period_median, 2),
                "median_estimate": round(median(estimates), 2) if estimates else None,
                "estimate_ratio": round(median(ratios), 3) if ratios else None,
            }
        )

    latest = period_points[-1] if period_points else {}
    confidence = confidence_label(len(period_points), len(records))
    return {
        "id": f"{series_type}:{slug(label)}",
        "series_type": series_type,
        "label": label,
        "status": "history_ready" if len(period_points) >= 2 else "needs_more_history",
        "confidence": confidence,
        "period_count": len(period_points),
        "lot_count": len(records),
        "latest_period": latest.get("period", ""),
        "latest_index_value": latest.get("index_value"),
        "latest_lots_sold": latest.get("lots_sold", 0),
        "latest_median_result": latest.get("median_result"),
        "latest_estimate_ratio": latest.get("estimate_ratio"),
        "points": period_points,
        "notes": notes_for_series(period_points, records),
    }


def normalize_lot(row: Dict[str, Any]) -> Dict[str, Any]:
    artists = json.loads(row.get("artists_json") or "[]")
    return {
        "identity_key": row.get("identity_key", ""),
        "period": str(row.get("auction_date") or "")[:4],
        "auction_date": row.get("auction_date", ""),
        "primary_artist": artists[0] if artists else "",
        "style": row.get("style") or row.get("sale_title") or "",
        "medium": row.get("medium") or "",
        "medium_family": medium_family(row.get("medium") or ""),
        "result_amount": as_float(row.get("result_price_amount")),
        "estimate_low": as_float(row.get("estimate_low")),
        "estimate_high": as_float(row.get("estimate_high")),
        "currency": row.get("currency") or "",
    }


def medium_family(value: str) -> str:
    lower = value.lower()
    if any(term in lower for term in ("screenprint", "print", "lithograph", "etching", "woodcut")):
        return "Prints and editions"
    if any(term in lower for term in ("photograph", "gelatin", "c-print", "inkjet")):
        return "Photography"
    if any(term in lower for term in ("oil", "acrylic", "encaustic", "tempera")):
        return "Paintings"
    if any(term in lower for term in ("charcoal", "graphite", "watercolor", "gouache", "pencil")):
        return "Works on paper"
    if any(term in lower for term in ("bronze", "ceramic", "steel", "sculpture", "marble")):
        return "Sculpture and objects"
    return ""


def estimate_midpoint(record: Dict[str, Any]) -> float | None:
    low = record.get("estimate_low")
    high = record.get("estimate_high")
    if low is not None and high is not None:
        return (low + high) / 2
    return low if low is not None else high


def confidence_label(period_count: int, lot_count: int) -> str:
    if period_count >= 4 and lot_count >= 20:
        return "high"
    if period_count >= 2 and lot_count >= 6:
        return "medium"
    return "low"


def notes_for_series(points: List[Dict[str, Any]], records: List[Dict[str, Any]]) -> str:
    if len(points) < 2:
        return "Needs at least two observed periods before this behaves like a trend index."
    if len(records) < 10:
        return "Directional only; add more lots before using this for pricing confidence."
    return "Usable directional index; still needs repeat-sale and hedonic controls."


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def write_market_indices(payload: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
