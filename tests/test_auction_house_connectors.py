import json
import unittest

from ingestion.connectors.auction_results_common import AuctionHouseSaleSnapshot
from ingestion.auction_models import AuctionLot
from ingestion.connectors.bonhams_results import bonhams_lot_to_auction_lot, enrich_bonhams_lot_from_detail
from ingestion.connectors.heritage_results import blocked_snapshot
from ingestion.connectors.phillips_results import (
    enrich_phillips_lots_from_detail_payloads,
    extract_auction_payload,
    extract_lot_detail_payloads,
    extract_react_router_data,
    phillips_lot_to_auction_lot,
)
from ingestion.connectors.sothebys_results import enrich_sothebys_lot_from_detail, lot_card_to_auction_lot


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

    def test_bonhams_detail_enrichment_maps_catalogue_fields(self):
        lot = AuctionLot(
            source_id="bonhams_results",
            source_name="Bonhams Results",
            auction_house="Bonhams",
            sale_id="31876",
            sale_title="Post-War & Contemporary Art",
            sale_url="https://example.test/sale",
            lot_id="201",
            source_record_id="6142547",
            title="Spending Scarlet",
        )

        enrich_bonhams_lot_from_detail(
            lot,
            {
                "currency": {"iso_code": "USD"},
                "sCurrencySymbol": "US$",
                "dEstimateLow": 30000,
                "dEstimateHigh": 50000,
                "dHammerPremium": 64000,
                "dStartingBidAmt": 15000,
                "sLotStatus": "SOLD",
                "sCatalogDesc": "<div>EMILY MASON</div><div><i>Spending Scarlet</i></div><div>signed lower right</div><div>oil on canvas</div><div><i>32 x 23 7/8 in (81.1 x 60.6 cm)</i></div>",
                "footnote_sExtraDesc": "<b>Provenance</b><br />M B Modern, New York.<br />Private collection.<br /><br /><b>Literature</b><br />Example catalogue, p. 9.",
                "images": [{"image_url": "https://images2.bonhams.com/example.jpg"}],
            },
        )

        self.assertEqual(lot.medium, "oil on canvas")
        self.assertEqual(lot.dimensions, "32 x 23 7/8 in (81.1 x 60.6 cm)")
        self.assertEqual(lot.provenance, "M B Modern, New York.\nPrivate collection.")
        self.assertEqual(lot.literature, "Example catalogue, p. 9.")
        self.assertEqual(lot.starting_price.display, "US$ 15,000")
        self.assertEqual(lot.image_url, "https://images2.bonhams.com/example.jpg")

    def test_sothebys_detail_enrichment_maps_description_sections(self):
        lot = AuctionLot(
            source_id="sothebys_results",
            source_name="Sotheby's Results",
            auction_house="Sotheby's",
            sale_id="auction-1",
            sale_title="Modern Day Auction",
            sale_url="https://example.test/sale",
            lot_id="301",
            source_record_id="lot-1",
            title="Sin titulo",
        )

        enrich_sothebys_lot_from_detail(
            lot,
            {
                "description": "<p>Example Artist</p><p><em>Sin titulo</em></p><p>signed lower right</p><p>oil on canvas</p><p>8 by 8 in.</p>",
                "provenance": "<p>Private Collection, Mexico City</p>",
                "literature": "<p>Example catalogue</p>",
                "session": {"scheduledOpeningDate": "2026-05-20T15:00Z"},
                'media({"imageSizes":["Small"]})': {
                    "images": [{"renditions": [{"width": 385, "url": "https://sothebys.example/image.jpg"}]}]
                },
            },
        )

        self.assertEqual(lot.medium, "oil on canvas")
        self.assertEqual(lot.dimensions, "8 by 8 in.")
        self.assertEqual(lot.provenance, "Private Collection, Mexico City")
        self.assertEqual(lot.literature, "Example catalogue")
        self.assertEqual(lot.auction_date, "2026-05-20")
        self.assertEqual(lot.image_url, "https://sothebys.example/image.jpg")

    def test_phillips_detail_stream_handles_internal_call_syntax(self):
        values = [
            {"_1": 2},
            "loaderData",
            {"_3": 4},
            "route",
            {"_5": 6},
            "lot",
            [7],
            {"_8": 9, "_10": 11, "_12": 13, "_14": 15, "_16": 17, "_18": 19},
            "objectNumber",
            "234922",
            "lotNumberFull",
            "302",
            "medium",
            "acrylic on canvas",
            "dimensions",
            "47 x 59 in. (121 x 151 cm)",
            "provenance",
            "STARS Gallery, Los Angeles",
            "sigEdtMan",
            "Painted in 2021.",
        ]
        values.append("text containing ); inside the JS string")
        stream = json.dumps(values)
        html = f"<script>window.__reactRouterContext.streamController.enqueue({json.dumps(stream)});</script>"
        detail_lots = extract_lot_detail_payloads(extract_react_router_data(html))
        lot = AuctionLot(
            source_id="phillips_auctions",
            source_name="Phillips Auctions",
            auction_house="Phillips",
            sale_id="NY010526",
            sale_title="Modern & Contemporary Art",
            sale_url="https://example.test/sale",
            lot_id="302",
            source_record_id="234922",
            title="The First to Arrive",
        )

        enrich_phillips_lots_from_detail_payloads([lot], detail_lots)

        self.assertEqual(lot.medium, "acrylic on canvas")
        self.assertEqual(lot.dimensions, "47 x 59 in. (121 x 151 cm)")
        self.assertEqual(lot.provenance, "STARS Gallery, Los Angeles")
        self.assertEqual(lot.description, "Painted in 2021.")

    def test_heritage_blocked_snapshot_keeps_lane_nonfatal(self):
        snapshot = blocked_snapshot("https://www.ha.com/c/search/results.zx", "fine art", "HTTP Error 403")

        self.assertEqual(snapshot.source_id, "heritage_auctions")
        self.assertIn("blocked", " ".join(snapshot.notes).lower())
        self.assertEqual(snapshot.lots_payload, {})


if __name__ == "__main__":
    unittest.main()
