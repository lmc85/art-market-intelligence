import unittest

from ingestion.market_indices import build_market_index_payload, medium_family


class MarketIndexTests(unittest.TestCase):
    def test_build_market_index_payload_rebases_series(self):
        lots = [
            {
                "identity_key": "a",
                "auction_date": "2024-01-01",
                "artists_json": '["Example Artist"]',
                "style": "Postwar",
                "medium": "oil on canvas",
                "result_price_amount": 100.0,
                "estimate_low": 80.0,
                "estimate_high": 120.0,
                "currency": "USD",
            },
            {
                "identity_key": "b",
                "auction_date": "2025-01-01",
                "artists_json": '["Example Artist"]',
                "style": "Postwar",
                "medium": "oil on canvas",
                "result_price_amount": 150.0,
                "estimate_low": 100.0,
                "estimate_high": 140.0,
                "currency": "USD",
            },
        ]

        payload = build_market_index_payload(lots)
        market = next(item for item in payload["indices"] if item["id"] == "market:all-auction-results")

        self.assertEqual(payload["summary"]["lot_count"], 2)
        self.assertEqual(market["status"], "history_ready")
        self.assertEqual(market["points"][0]["index_value"], 100)
        self.assertEqual(market["points"][1]["index_value"], 150)
        self.assertEqual(market["latest_estimate_ratio"], 1.25)

    def test_medium_family_maps_common_art_media(self):
        self.assertEqual(medium_family("screenprint in colors"), "Prints and editions")
        self.assertEqual(medium_family("oil on canvas"), "Paintings")
        self.assertEqual(medium_family("glazed ceramic"), "Sculpture and objects")


if __name__ == "__main__":
    unittest.main()
