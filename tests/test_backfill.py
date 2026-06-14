import unittest

from ingestion.auction_models import AuctionLot, MoneyValue
from ingestion.backfill import backfill_sales, sample_across_years
from ingestion.connectors.phillips_results import select_phillips_sales


PAST_AUCTIONS = [
    {"auctionUrl": "https://www.phillips.com/auction/NY010326", "auctionName": "Modern & Contemporary Art Evening Sale", "auctionStartDateTime": "2026-05-19T21:00:00.000000Z"},
    {"auctionUrl": "https://www.phillips.com/auction/HK080226", "auctionName": "The Hong Kong Watch Auction: XXII", "auctionStartDateTime": "2026-05-30T04:00:00.000000Z"},
    {"auctionUrl": "https://www.phillips.com/auction/NY010120", "auctionName": "New Now", "auctionStartDateTime": "2020-03-04T18:00:00.000000Z"},
    {"auctionUrl": "https://www.phillips.com/auction/NY060126", "auctionName": "The New York Jewels Auction", "auctionStartDateTime": "2026-06-10T16:00:00.000000Z"},
    {"auctionName": "No URL sale", "auctionStartDateTime": "2019-01-01T00:00:00.000000Z"},
]


class SelectPhillipsSalesTests(unittest.TestCase):
    def test_drops_watches_and_jewels_and_urlless(self):
        sales = select_phillips_sales(PAST_AUCTIONS)
        names = [s["name"] for s in sales]
        self.assertNotIn("The Hong Kong Watch Auction: XXII", names)
        self.assertFalse(any("Jewels" in n for n in names))
        self.assertEqual(len(sales), 2)  # the two art sales only

    def test_extracts_url_and_date(self):
        sales = select_phillips_sales(PAST_AUCTIONS)
        self.assertEqual(sales[0]["url"], "https://www.phillips.com/auction/NY010326")
        self.assertEqual(sales[0]["date"], "2026-05-19")
        self.assertEqual(sales[1]["date"], "2020-03-04")

    def test_query_filter(self):
        sales = select_phillips_sales(PAST_AUCTIONS, sale_query="new now")
        self.assertEqual([s["name"] for s in sales], ["New Now"])

    def test_limit_caps_count(self):
        self.assertEqual(len(select_phillips_sales(PAST_AUCTIONS, limit_sales=1)), 1)


class SampleAcrossYearsTests(unittest.TestCase):
    def _sales(self):
        # 3 sales in 2026, 2 in 2025, 1 in 2024 (newest first).
        return [
            {"url": "a", "date": "2026-06-01"}, {"url": "b", "date": "2026-04-01"}, {"url": "c", "date": "2026-02-01"},
            {"url": "d", "date": "2025-09-01"}, {"url": "e", "date": "2025-03-01"},
            {"url": "f", "date": "2024-05-01"},
        ]

    def test_spreads_one_per_year_before_doubling_up(self):
        picked = sample_across_years(self._sales(), max_sales=3)
        self.assertEqual([s["url"] for s in picked], ["a", "d", "f"])  # newest of each year

    def test_returns_all_when_budget_exceeds_count(self):
        sales = self._sales()
        self.assertEqual(sample_across_years(sales, max_sales=99), sales)

    def test_second_pass_takes_next_newest_within_year(self):
        picked = sample_across_years(self._sales(), max_sales=5)
        self.assertEqual([s["url"] for s in picked], ["a", "d", "f", "b", "e"])


def lot(record_id, year, amount, artist="Cynthia Hawkins"):
    return AuctionLot(
        source_id="phillips_auctions",
        source_name="Phillips Auctions",
        auction_house="Phillips",
        sale_id=f"S{year}",
        sale_title=f"Sale {year}",
        sale_url=f"https://example.test/{year}",
        lot_id=record_id,
        source_record_id=record_id,
        title="A work",
        artists=[artist],
        auction_date=f"{year}-05-19",
        result_price=MoneyValue(currency="USD", amount=amount, display=f"${amount}"),
    )


class _StubConnector:
    """Returns canned lots per sale URL; records fetch calls."""

    def __init__(self, sales_to_lots):
        self._map = sales_to_lots
        self.calls = []

    def fetch_auction_lots(self, limit, sale_url):
        self.calls.append((sale_url, limit))
        if sale_url == "boom":
            raise RuntimeError("page 403")
        return None, self._map.get(sale_url, [])[:limit]


class _MemoryStore:
    def __init__(self):
        self.lots = {}

    def upsert_lots(self, lots):
        for item in lots:
            self.lots[item.identity_key] = item
        return len(list(lots)) if not isinstance(lots, list) else len(lots)


class BackfillSalesTests(unittest.TestCase):
    def test_accumulates_lots_across_years(self):
        connector = _StubConnector({
            "s2026": [lot("a", 2026, 100), lot("b", 2026, 200)],
            "s2020": [lot("c", 2020, 50)],
        })
        store = _MemoryStore()
        sales = [{"url": "s2026", "date": "2026-05-19", "name": "2026 sale"},
                 {"url": "s2020", "date": "2020-03-04", "name": "2020 sale"}]

        stats = backfill_sales(connector, store, sales, delay_seconds=0, sleep=lambda *_: None)

        self.assertEqual(stats["sales_ingested"], 2)
        self.assertEqual(stats["lots_written"], 3)
        self.assertEqual(stats["years"], {"2026", "2020"})
        self.assertEqual(len(store.lots), 3)

    def test_failed_sale_is_recorded_not_fatal(self):
        connector = _StubConnector({"good": [lot("a", 2026, 100)]})
        store = _MemoryStore()
        sales = [{"url": "boom"}, {"url": "good"}]

        stats = backfill_sales(connector, store, sales, delay_seconds=0, sleep=lambda *_: None)

        self.assertEqual(stats["sales_ingested"], 1)
        self.assertEqual(len(stats["errors"]), 1)
        self.assertEqual(stats["errors"][0]["url"], "boom")
        self.assertEqual(len(store.lots), 1)


if __name__ == "__main__":
    unittest.main()
