import unittest
from xml.etree import ElementTree as ET

from ingestion.rss import ARTMI_NS, build_rss_xml


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


if __name__ == "__main__":
    unittest.main()
