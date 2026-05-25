import tempfile
import unittest
from pathlib import Path

from ingestion.auction_models import AuctionLot, MoneyValue
from ingestion.auction_store import AuctionStore


class AuctionStoreTests(unittest.TestCase):
    def test_upsert_dedupes_and_exports_feed_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AuctionStore(Path(tmpdir) / "auction.sqlite")
            try:
                lot = AuctionLot(
                    source_id="christies_results",
                    source_name="Christie's Results",
                    auction_house="Christie's",
                    sale_id="31036",
                    sale_title="Post-War and Contemporary Art Day Sale",
                    sale_url="https://example.test/sale",
                    lot_id="401",
                    source_record_id="6585915",
                    title="Untitled",
                    artists=["Example Artist"],
                    auction_date="2026-05-21",
                    currency="USD",
                    estimate=MoneyValue(currency="USD", low=1000, high=2000, display="USD 1,000 - 2,000"),
                    result_price=MoneyValue(currency="USD", amount=2500, display="USD 2,500"),
                    source_url="https://example.test/lot",
                    medium="Oil on panel",
                    dimensions="10 x 12 in.",
                    provenance="Private collection",
                    literature="Example catalogue",
                    record_source="test",
                )

                self.assertEqual(store.upsert_lots([lot]), 1)
                self.assertEqual(store.upsert_lots([lot]), 1)
                items = store.lots_for_feed()
                summary = store.quality_summary()
            finally:
                store.close()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Untitled")
        self.assertEqual(items[0]["result_price"]["display"], "USD 2,500")
        self.assertEqual(items[0]["medium"], "Oil on panel")
        self.assertEqual(items[0]["dimensions"], "10 x 12 in.")
        self.assertEqual(items[0]["provenance"], "Private collection")
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["prediction_ready"], 1)
        self.assertEqual(summary["missing_medium"], 0)
        self.assertEqual(summary["missing_dimensions"], 0)


if __name__ == "__main__":
    unittest.main()
