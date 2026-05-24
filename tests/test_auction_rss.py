import unittest
from xml.etree import ElementTree as ET

from ingestion.rss import ARTMI_NS, build_rss_xml
from ingestion.connectors.christies_results import extract_component_data, lot_to_feed_item


class AuctionRssTests(unittest.TestCase):
    def test_build_rss_xml_includes_required_auction_fields(self):
        xml = build_rss_xml(
            [
                {
                    "id": "sale-1",
                    "status": "sold",
                    "title": "Untitled print",
                    "artists": ["Example Artist"],
                    "style": "Postwar prints",
                    "auction_house": "Example House",
                    "auction_date": "2026-05-18",
                    "starting_price": {"display": "$1,000"},
                    "estimated_selling_price": {"display": "$1,500-$2,000"},
                    "last_sold_price": {"display": "$900"},
                    "source_url": "https://example.test/lot",
                    "record_source": "test",
                }
            ],
            site_url="https://example.test/",
            feed_url="https://example.test/feed.xml",
        )

        root = ET.fromstring(xml)
        item = root.find("./channel/item")
        self.assertIsNotNone(item)
        self.assertEqual(item.findtext(f"{{{ARTMI_NS}}}title"), "Untitled print")
        self.assertEqual(item.findtext(f"{{{ARTMI_NS}}}artists"), "Example Artist")
        self.assertEqual(item.findtext(f"{{{ARTMI_NS}}}style"), "Postwar prints")
        self.assertEqual(item.findtext(f"{{{ARTMI_NS}}}auctionHouse"), "Example House")
        self.assertEqual(item.findtext(f"{{{ARTMI_NS}}}auctionDate"), "2026-05-18")
        self.assertEqual(item.findtext(f"{{{ARTMI_NS}}}startingPrice"), "$1,000")
        self.assertEqual(item.findtext(f"{{{ARTMI_NS}}}estimatedSellingPrice"), "$1,500-$2,000")
        self.assertEqual(item.findtext(f"{{{ARTMI_NS}}}lastSoldPrice"), "$900")

    def test_christies_lot_normalizer_maps_estimate_and_result(self):
        item = lot_to_feed_item(
            {
                "object_id": "6585915",
                "lot_id_txt": "401",
                "analytics_id": "24267.401",
                "start_date": "2026-05-21T00:00Z",
                "url": "https://www.christies.com/en/lot/lot-6585915",
                "title_primary_txt": "GERHARD RICHTER (B. 1932)",
                "title_secondary_txt": "Untitled (7.2.89)",
                "estimate_low": "60000.0",
                "estimate_high": "80000.0",
                "estimate_txt": "USD 60,000 - 80,000",
                "price_realised": "330200.0",
                "price_realised_txt": "USD 330,200",
            },
            sale_title="Post-War and Contemporary Art Day Sale",
            sale_url="https://www.christies.com/en/auction/post-war-and-contemporary-art-day-sale-31036/",
        )

        self.assertEqual(item["id"], "christies-24267.401")
        self.assertEqual(item["status"], "sold")
        self.assertEqual(item["title"], "Untitled (7.2.89)")
        self.assertEqual(item["artists"], ["GERHARD RICHTER (B. 1932)"])
        self.assertEqual(item["auction_date"], "2026-05-21")
        self.assertEqual(item["estimated_selling_price"]["display"], "USD 60,000 - 80,000")
        self.assertEqual(item["result_price"]["display"], "USD 330,200")

    def test_extract_component_data_reads_christies_payload(self):
        html = """
        <script>
          window.chrComponents = window.chrComponents || {};
          window.chrComponents.lots = {"data":{"lots":[{"object_id":"1","lot_id_txt":"1"}]}};
        </script>
        """

        payload = extract_component_data(html, "window.chrComponents.lots")

        self.assertEqual(payload["lots"][0]["object_id"], "1")


if __name__ == "__main__":
    unittest.main()
