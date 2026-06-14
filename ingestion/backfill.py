"""Reusable core for backfilling multi-year auction history into the store.

The live house connectors normally capture a single recent sale. Backfilling walks
a connector's past-sale archive (via ``discover_sale_urls``) and accumulates realized
lots from many sales — spanning years — into the auction store so the derived indices
gain real per-artist / per-medium price history rather than a single snapshot.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any, Callable, Dict, List


def sample_across_years(sales: List[Dict[str, str]], max_sales: int) -> List[Dict[str, str]]:
    """Pick up to ``max_sales`` sales spread across distinct years, newest first.

    A naive "newest N" slice would stay within the last year or two; the indices key
    history by year, so spreading the budget across years is what lets a single artist
    accumulate the >= 2 distinct years needed to become trend-ready.
    """

    if not max_sales or len(sales) <= max_sales:
        return sales

    by_year: "OrderedDict[str, List[Dict[str, str]]]" = OrderedDict()
    for sale in sales:  # sales arrive newest-first
        year = (sale.get("date") or "")[:4]
        by_year.setdefault(year, []).append(sale)

    picked: List[Dict[str, str]] = []
    depth = 0
    while len(picked) < max_sales:
        progressed = False
        for year_sales in by_year.values():
            if depth < len(year_sales):
                picked.append(year_sales[depth])
                progressed = True
                if len(picked) >= max_sales:
                    break
        if not progressed:
            break
        depth += 1
    return picked


def backfill_sales(
    connector: Any,
    store: Any,
    sales: List[Dict[str, str]],
    lots_per_sale: int = 60,
    delay_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    """Fetch each sale's lots and upsert them into ``store``, accumulating history.

    ``sales`` is a list of ``{"url", "date", "name"}`` dicts (or bare URL strings).
    Returns a stats dict with totals, the distinct years seen, per-sale rows, and any
    per-sale errors (a failed sale is recorded and skipped, never fatal).
    """

    stats: Dict[str, Any] = {
        "sales_ingested": 0,
        "lots_written": 0,
        "priced_lots": 0,
        "years": set(),
        "per_sale": [],
        "errors": [],
    }

    for index, sale in enumerate(sales):
        url = sale["url"] if isinstance(sale, dict) else sale
        label = sale if isinstance(sale, dict) else {"url": url, "date": "", "name": ""}

        try:
            _, lots = connector.fetch_auction_lots(limit=lots_per_sale, sale_url=url)
        except Exception as exc:  # a brittle live page must not abort the whole run
            stats["errors"].append({"url": url, "error": str(exc)})
            continue

        priced = [lot for lot in lots if lot.result_price and lot.result_price.amount]
        written = store.upsert_lots(lots)
        years = {lot.auction_date[:4] for lot in lots if lot.auction_date}

        stats["sales_ingested"] += 1
        stats["lots_written"] += written
        stats["priced_lots"] += len(priced)
        stats["years"].update(years)
        stats["per_sale"].append(
            {
                "url": url,
                "date": label.get("date", ""),
                "name": label.get("name", ""),
                "lots": written,
                "priced": len(priced),
            }
        )

        if delay_seconds and index < len(sales) - 1:
            sleep(delay_seconds)

    return stats
