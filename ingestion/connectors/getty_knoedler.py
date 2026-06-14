"""Connector for the Getty Provenance Index — Knoedler stock books (CC0).

The Knoedler dataset is a single ~17.6 MB CC0 CSV transcribed from the stock books
of the M. Knoedler & Co. dealership. Unlike the app's live auction connectors — which
only capture a single recent sale snapshot — Knoedler carries realized transaction
prices spanning 1873–1912, giving the derived market indices the multi-year depth
they need to become trend-ready (a series needs realized prices in >= 2 distinct
years before it stops reporting "needs more history").

What this is and is not:
  * These are historical *dealer* transactions, not auction hammer prices, recorded in
    period nominal currency (overwhelmingly US dollars). Amounts are NOT inflation- or
    currency-adjusted, so they build separate historical lanes and should not be read
    as continuous with present-day auction results.
  * Records are loaded into the same auction store so the existing index builder can
    derive per-artist / per-genre / per-medium price history from them.

Source: https://github.com/thegetty/provenance-index-csv (knoedler dataset, CC0).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

from ingestion.auction_models import AuctionLot, MoneyValue
from ingestion.http import HttpClient


CSV_URL = "https://jpgt-or-prd-provenance-index-csv.s3.us-west-2.amazonaws.com/knoedler/knoedler.csv"
SOURCE_ID = "getty_knoedler"
SOURCE_NAME = "Getty Provenance Index — Knoedler"
AUCTION_HOUSE = "M. Knoedler & Co."
RECORD_SOURCE = "Getty Provenance Index Knoedler stock books (CC0)"

# Knoedler currency words -> (ISO-ish code, display symbol).
_CURRENCY_MAP = {
    "dollars": ("USD", "$"),
    "francs": ("FRF", "₣"),
    "pounds": ("GBP", "£"),
    "marks": ("DEM", "ℳ"),
}

_AMOUNT_RE = re.compile(r"([0-9][0-9,]*(?:\.[0-9]+)?)")


class KnoedlerConnector:
    """Stream realized dealer transactions from the Knoedler CC0 CSV."""

    source_id = SOURCE_ID
    source_name = SOURCE_NAME

    def __init__(self, client: Optional[HttpClient] = None):
        self.client = client or HttpClient()

    def ensure_local_csv(self, cache_path: Path) -> Path:
        """Download the CSV to ``cache_path`` once; reuse it on later runs."""

        if cache_path.exists() and cache_path.stat().st_size > 0:
            return cache_path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.client.open_text_stream(CSV_URL, encoding="utf-8") as stream:
            with cache_path.open("w", encoding="utf-8", newline="") as handle:
                for chunk in stream:
                    handle.write(chunk)
        return cache_path

    def fetch_lots(
        self,
        limit: int = 0,
        currencies: Iterable[str] = ("dollars",),
        cache_path: Optional[Path] = None,
    ) -> List[AuctionLot]:
        """Return normalized sold lots, optionally capped at ``limit`` records.

        ``currencies`` restricts which Knoedler price currencies are kept (default
        dollars only, since the index does not normalize across currencies).
        """

        path = self.ensure_local_csv(cache_path or Path("data/ingested/knoedler.csv"))
        allowed = {value.lower() for value in currencies} if currencies else None

        lots: List[AuctionLot] = []
        # utf-8-sig strips the byte-order mark the source CSV carries on its first column.
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                lot = knoedler_row_to_lot(row, allowed_currencies=allowed)
                if lot:
                    lots.append(lot)
                if limit and len(lots) >= limit:
                    break
        return lots


def knoedler_row_to_lot(
    row: Dict[str, Any],
    allowed_currencies: Optional[set] = None,
) -> Optional[AuctionLot]:
    if cell(row, "Transaction").lower() != "sold":
        return None

    year = cell(row, "Sale Date-Year")
    if not year.isdigit() or len(year) != 4:
        return None

    currency_word = cell(row, "Price Currency").lower()
    if allowed_currencies is not None and currency_word and currency_word not in allowed_currencies:
        return None

    amount = parse_amount(cell(row, "Price Amount"))
    if amount is None or amount <= 0:
        return None

    record_id = cell(row, "PI Record No.")
    if not record_id:
        return None

    code, symbol = _CURRENCY_MAP.get(currency_word, (currency_word.upper(), ""))
    artist = cell(row, "Art. Authority 1") or cell(row, "Artist Name 1")
    genre = cell(row, "Genre")
    materials = cell(row, "Materials")
    result = MoneyValue(
        currency=code,
        amount=amount,
        display=f"{symbol}{amount:,.0f}".strip() if symbol else f"{amount:,.0f} {code}".strip(),
    )

    return AuctionLot(
        source_id=SOURCE_ID,
        source_name=SOURCE_NAME,
        auction_house=AUCTION_HOUSE,
        sale_id=year,
        sale_title=f"Knoedler stock book sales {year}",
        sale_url="https://www.getty.edu/research/tools/provenance/search.html",
        lot_id=record_id,
        source_record_id=record_id,
        title=cell(row, "Title") or "[Untitled]",
        artists=[artist] if artist else [],
        style=genre,
        auction_date=build_date(year, cell(row, "Sale Date-Month"), cell(row, "Sale Date-Day")),
        currency=code,
        result_price=result,
        source_url="https://www.getty.edu/research/tools/provenance/search.html",
        medium=materials,
        dimensions=cell(row, "Dimensions"),
        description=cell(row, "Description"),
        record_source=RECORD_SOURCE,
        notes=(
            "Historical dealer transaction (M. Knoedler & Co.); nominal period price, "
            "not inflation- or currency-adjusted and not an auction hammer price."
        ),
        raw={"pi_record_no": record_id, "genre": genre, "price_note": cell(row, "Price Note")},
    )


def parse_amount(value: str) -> Optional[float]:
    match = _AMOUNT_RE.search(value or "")
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def build_date(year: str, month: str, day: str) -> str:
    mm = month.zfill(2) if month.isdigit() and 1 <= int(month) <= 12 else "01"
    dd = day.zfill(2) if day.isdigit() and 1 <= int(day) <= 31 else "01"
    return f"{year}-{mm}-{dd}"


def cell(row: Dict[str, Any], key: str) -> str:
    return (row.get(key) or "").strip()
