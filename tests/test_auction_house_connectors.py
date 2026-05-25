import json
import unittest

from ingestion.connectors.auction_results_common import AuctionHouseSaleSnapshot
from ingestion.connectors.bonhams_results import bonhams_lot_to_auction_lot
from ingestion.connectors.heritage_results import blocked_snapshot
from ingestion.connectors.phillips_results import (
    extract_auction_payload,
    extract_react_router_data,
    phillips_lot_to_auction_lot,
)
from ingestion.connectors.sothebys_results import lot_card_to_auction_lot


class AuctionHouseConnectorTests(unittest.TestCase):
    def test_sothebys_maps_public_lot_card_estimate_and_date(self):
        snapshot = AuctionHouseSaleSnapshot(
            source_id="sothebys_results",
            source_name="Sotheby's Results",
            sale_url="https://www.sothebys.com/en/buy/auction/2026/modern-day-auction",
            sale_title="Modern Day Auction",
            sale_id="auction-1",
            sale_number="N12125",
            raw_html="",
            lots_payload={},
        )
        lot = lot_card_to_auction_lot(
            {
                "lotId": "lot-1",
                "title": "Sin titulo",
                "creatorsDisplayTitle": "Example Artist",
                "auction": {"auctionId": "auction-1", "currency": "USD"},
                "lotNumber": {"lotDisplayNumber": "301"},
                "estimateV2": {
                    "lowEstimate": {"amount": "40000"},
                    "highEstimate": {"amount": "60000"},
                },
                "slug": {"lotSlug": "sin-titulo"},
            },
            snapshot,
            {
                "objectID": "lot-1",
                "auctionDate": "2026-05-20T15:00Z",
                "slug": "/en/buy/auction/2026/modern-day-auction/sin-titulo",
            },
        )

        self.assertEqual(lot.auction_house, "Sotheby's")
        self.assertEqual(lot.auction_date, "2026-05-20")
        self.assertEqual(lot.estimate.display, "USD 40,000 - 60,000")
        self.assertIsNone(lot.result_price)

    def test_bonhams_maps_estimate_result_artist_and_title(self):
        snapshot = AuctionHouseSaleSnapshot(
            source_id="bonhams_results",
            source_name="Bonhams Results",
            sale_url="https://www.bonhams.com/auction/31876/post-war-and-contemporary-art/",
            sale_title="Post-War & Contemporary Art",
            sale_id="31876",
            raw_html="",
        )
        lot = bonhams_lot_to_auction_lot(
            {
                "auctionId": "31876",
                "lotId": "201",
                "lotUniqueId": "6142547",
                "lotNo": {"full": "201"},
                "currency": {"iso_code": "USD"},
                "department": {"name": "Post-War and Contemporary Art"},
                "hammerTime": {"datetime": "2026-05-21T18:00:00+00:00"},
                "price": {
                    "currencySymbol": "US$",
                    "estimateLow": 30000,
                    "estimateHigh": 50000,
                    "hammerPremium": 64000,
                },
                "status": "SOLD",
                "styledDescription": "<div>EMILY MASON</div><div>(1932-2019)</div><div><i>Spending Scarlet</i></div>",
                "title": "EMILY MASON (1932-2019) Spending Scarlet 32 x 23 7/8 in (81.1 x 60.6 cm)",
                "slug": "emily-mason-spending-scarlet",
                "image": {"url": "https://images2.bonhams.com/example.jpg"},
            },
            snapshot,
        )

        self.assertEqual(lot.artists, ["EMILY MASON (1932-2019)"])
        self.assertEqual(lot.title, "Spending Scarlet")
        self.assertEqual(lot.auction_date, "2026-05-21")
        self.assertEqual(lot.estimate.display, "US$ 30,000 - 50,000")
        self.assertEqual(lot.result_price.display, "US$ 64,000")

    def test_phillips_decodes_react_router_payload_and_maps_lot(self):
        values = [
            {"_1": 2},
            "loaderData",
            {"_3": 4},
            "route",
            {"_5": 6},
            "auction",
            {"_7": 8, "_9": 10, "_11": 12, "_13": 14, "_15": 16},
            "auctionCode",
            "NY010526",
            "auctionName",
            "Modern & Contemporary Art: Afternoon Session",
            "auctionStartDateTime",
            "2026-05-21T18:00:00.000000Z",
            "lots",
            [17],
            "auctionCurrency",
            {"_18": 19},
            {"_20": 21, "_22": 23, "_24": 25, "_26": 27, "_28": 29, "_30": 31, "_32": 33},
            "currencyCode",
            "USD",
            "objectNumber",
            "234922",
            "lotNumberFull",
            "302",
            "description",
            "The First to Arrive",
            "makerName",
            "Cynthia Hawkins",
            "lotStatus",
            "Sold",
            "soldPrice",
            38700,
            "estimate",
            {"_34": 35},
            "mainEstimate",
            {"_18": 19, "_36": 37, "_38": 39, "_40": 41},
            "currencySymbol",
            "$",
            "lowEstimate",
            40000,
            "highEstimate",
            60000,
        ]
        html = f"<script>window.__reactRouterContext.streamController.enqueue({json.dumps(json.dumps(values))});</script>"
        data = extract_react_router_data(html)
        auction = extract_auction_payload(data)
        snapshot = AuctionHouseSaleSnapshot(
            source_id="phillips_auctions",
            source_name="Phillips Auctions",
            sale_url="https://www.phillips.com/auction/NY010526",
            sale_title=auction["auctionName"],
            sale_id=auction["auctionCode"],
            raw_html="",
        )

        lot = phillips_lot_to_auction_lot(auction["lots"][0], snapshot, auction)

        self.assertEqual(lot.artists, ["Cynthia Hawkins"])
        self.assertEqual(lot.title, "The First to Arrive")
        self.assertEqual(lot.auction_date, "2026-05-21")
        self.assertEqual(lot.estimate.display, "$ 40,000 - 60,000")
        self.assertEqual(lot.result_price.display, "$ 38,700")

    def test_heritage_blocked_snapshot_keeps_lane_nonfatal(self):
        snapshot = blocked_snapshot("https://www.ha.com/c/search/results.zx", "fine art", "HTTP Error 403")

        self.assertEqual(snapshot.source_id, "heritage_auctions")
        self.assertIn("blocked", " ".join(snapshot.notes).lower())
        self.assertEqual(snapshot.lots_payload, {})


if __name__ == "__main__":
    unittest.main()
