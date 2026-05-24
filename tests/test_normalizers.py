import unittest

from ingestion.connectors.artic import ArtInstituteConnector
from ingestion.connectors.cleveland import ClevelandConnector
from ingestion.connectors.met import MetConnector
from ingestion.connectors.moma import MomaConnector
from ingestion.registry import SourceInfo


def source_info(source_id, source_name):
    return SourceInfo(
        source_id=source_id,
        source_name=source_name,
        source_class="object_metadata",
        access_type="open_api",
        priority="P0",
        geography="Global",
        access_url="https://example.test",
        ingestion_method="api",
        license_or_terms_status="open",
        notes="test",
    )


class NormalizerTests(unittest.TestCase):
    def test_met_normalizer_maps_core_fields(self):
        connector = MetConnector(source_info("met_open_access", "The Met Open Access"))
        record = connector.normalize(
            {
                "objectID": 123,
                "title": "Study of Flowers",
                "artistDisplayName": "A. Painter",
                "objectDate": "1880",
                "objectBeginDate": 1879,
                "objectEndDate": 1881,
                "medium": "Oil on canvas",
                "dimensions": "20 x 30 cm",
                "classification": "Paintings",
                "department": "European Paintings",
                "culture": "French",
                "country": "France",
                "city": "Paris",
                "primaryImageSmall": "https://images.example/met.jpg",
                "objectURL": "https://met.example/object/123",
                "isPublicDomain": True,
                "creditLine": "Gift",
                "accessionNumber": "1999.1",
            }
        )

        self.assertEqual(record.source_record_id, "123")
        self.assertEqual(record.artist_names, ["A. Painter"])
        self.assertEqual(record.date_begin, 1879)
        self.assertEqual(record.license, "Public domain")
        self.assertIn("France", record.geography)

    def test_artic_normalizer_builds_iiif_image_url(self):
        connector = ArtInstituteConnector(source_info("artic_api", "Art Institute of Chicago API"))
        record = connector.normalize(
            {
                "id": 456,
                "title": "Blue Form",
                "artist_display": "B. Sculptor",
                "artist_title": "B. Sculptor",
                "date_display": "1965",
                "date_start": 1964,
                "date_end": 1966,
                "medium_display": "Screenprint",
                "dimensions": "10 x 12 in.",
                "classification_title": "Prints",
                "department_title": "Prints and Drawings",
                "place_of_origin": "United States",
                "image_id": "abc123",
                "api_link": "https://api.artic.edu/api/v1/artworks/456",
                "is_public_domain": True,
                "main_reference_number": "1965.2",
            },
            "https://www.artic.edu/iiif/2",
        )

        self.assertEqual(record.source_record_id, "456")
        self.assertIn("abc123", record.image_url)
        self.assertEqual(record.classification, "Prints")
        self.assertEqual(record.accession_number, "1965.2")

    def test_cleveland_normalizer_handles_nested_images_and_creators(self):
        connector = ClevelandConnector(source_info("cleveland_open_access", "Cleveland Museum of Art Open Access API"))
        record = connector.normalize(
            {
                "id": 789,
                "accession_number": "1915.534",
                "title": "Nathaniel Hurd",
                "creation_date": "c. 1765",
                "creation_date_earliest": 1760,
                "creation_date_latest": 1770,
                "creators": [{"description": "John Singleton Copley (American, 1738-1815)"}],
                "images": {"web": {"url": "https://images.example/cma.jpg"}},
                "type": "Painting",
                "department": "American Painting and Sculpture",
                "culture": ["America"],
                "technique": "oil on canvas",
                "measurements": "76.2 x 64.8 cm",
                "url": "https://clevelandart.org/art/1915.534",
                "share_license_status": "CC0",
                "creditline": "Gift",
            }
        )

        self.assertEqual(record.source_record_id, "789")
        self.assertEqual(record.image_url, "https://images.example/cma.jpg")
        self.assertEqual(record.artist_names, ["John Singleton Copley (American, 1738-1815)"])
        self.assertEqual(record.culture, "America")

    def test_moma_normalizer_maps_bulk_csv_row(self):
        connector = MomaConnector(source_info("moma_collection", "MoMA Collection Data"))
        record = connector.normalize(
            {
                "ObjectID": "2",
                "Title": "Ferdinandsbrücke Project, Vienna, Austria",
                "Artist": "Otto Wagner",
                "Date": "1896",
                "Medium": "Ink on paper",
                "Dimensions": "48.6 x 168.9 cm",
                "Classification": "Architecture",
                "Department": "Architecture & Design",
                "Nationality": "Austrian",
                "ImageURL": "https://images.example/moma.jpg",
                "URL": "https://www.moma.org/collection/works/2",
                "CreditLine": "Fractional gift",
                "AccessionNumber": "885.1996",
            }
        )

        self.assertEqual(record.source_record_id, "2")
        self.assertEqual(record.artist_display, "Otto Wagner")
        self.assertEqual(record.license, "CC0 metadata; image rights separate")
        self.assertEqual(record.department, "Architecture & Design")


if __name__ == "__main__":
    unittest.main()
