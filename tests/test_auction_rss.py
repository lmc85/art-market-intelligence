import unittest
from xml.etree import ElementTree as ET

from ingestion.rss import ARTMI_NS, build_rss_xml
from ingestion.auction_models import AuctionLot, MoneyValue
from ingestion.connectors.christies_results import (
    enrich_lot_from_detail,
    extract_component_data,
    extract_detail_sections,
    extract_lot_header_data,
    lot_to_feed_item,
)


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
                    "medium": "Oil on panel",
                    "dimensions": "10 x 12 in.",
                    "provenance": "Private collection",
                    "literature": "Example catalogue",
                    "prediction_ready": True,
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
        self.assertEqual(item.findtext(f"{{{ARTMI_NS}}}medium"), "Oil on panel")
        self.assertEqual(item.findtext(f"{{{ARTMI_NS}}}dimensions"), "10 x 12 in.")
        self.assertEqual(item.findtext(f"{{{ARTMI_NS}}}provenance"), "Private collection")
        self.assertEqual(item.findtext(f"{{{ARTMI_NS}}}literature"), "Example catalogue")
        self.assertEqual(item.findtext(f"{{{ARTMI_NS}}}predictionReady"), "true")

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

        self.assertEqual(item["id"], "christies_results|christie's|post-war and contemporary art day sale|401")
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

    def test_christies_detail_enrichment_maps_catalogue_fields(self):
        detail_html = """
        <script>
          window.chrComponents = window.chrComponents || {};
          window.chrComponents.lotHeader_123 = {"data":{"lots":[{"object_id":"6585915","lot_id_txt":"401","lot_assets":[{"image_url":"https://example.test/image.jpg","measurements_txt":"W 4 x H 6 3/4 in. (10.2 x 14.6 cm.)"}]}]}};
        </script>
        <chr-accordion-item open accordion-id="0">
          <div slot="header">Details</div>
          <div slot="content">
            <span class="chr-lot-section__accordion--text">GERHARD RICHTER (B. 1932)<br><i>Untitled</i><br>signed and dated 'Richter'<br>oil on photograph<br>5 3/4 x 4 in. (14.6 x 10.2 cm.)<br>Executed in 1989.</span>
          </div>
        </chr-accordion-item>
        <chr-accordion-item open accordion-id="1">
          <div slot="header">Provenance</div>
          <div slot="content">
            <span class="chr-lot-section__accordion--text">Acquired directly from the artist by the late owner, 1989</span>
          </div>
        </chr-accordion-item>
        <chr-accordion-item open accordion-id="2">
          <div slot="header">Literature</div>
          <div slot="content">
            <span class="chr-lot-section__accordion--text">Example catalogue, London, 2024, p. 9.</span>
          </div>
        </chr-accordion-item>
        """
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
            artists=["GERHARD RICHTER (B. 1932)"],
            auction_date="2026-05-21",
            estimate=MoneyValue(currency="USD", low=60000, high=80000, display="USD 60,000 - 80,000"),
            result_price=MoneyValue(currency="USD", amount=330200, display="USD 330,200"),
            source_url="https://www.christies.com/en/lot/lot-6585915",
        )

        sections = extract_detail_sections(detail_html)
        header = extract_lot_header_data(detail_html)
        enrich_lot_from_detail(lot, detail_html)

        self.assertEqual(sections["details"].splitlines()[3], "oil on photograph")
        self.assertEqual(header["lots"][0]["object_id"], "6585915")
        self.assertEqual(lot.medium, "oil on photograph")
        self.assertEqual(lot.dimensions, "5 3/4 x 4 in. (14.6 x 10.2 cm.)")
        self.assertEqual(lot.provenance, "Acquired directly from the artist by the late owner, 1989")
        self.assertEqual(lot.literature, "Example catalogue, London, 2024, p. 9.")
        self.assertEqual(lot.image_url, "https://example.test/image.jpg")


if __name__ == "__main__":
    unittest.main()
