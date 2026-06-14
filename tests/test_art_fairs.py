import unittest

from ingestion.connectors.art_fairs import (
    ArtsyFairsConnector,
    absolute_url,
    derive_fair_type,
    derive_location,
    derive_status,
    iso_day,
    normalize_fair,
    year_from_dates,
)


def fair_node(name, slug, start, end, active=False):
    return {"name": name, "slug": slug, "href": f"/fair/{slug}", "startAt": start, "endAt": end, "isActive": active}


PAGE_ONE = [
    fair_node("Art Basel 2026", "art-basel-2026", "2026-06-18T00:00:00+00:00", "2026-06-21T23:00:00+00:00", True),
    fair_node("Frieze Seoul 2026", "frieze-seoul-2026", "2026-09-02T00:00:00+00:00", "2026-09-05T00:00:00+00:00"),
    fair_node("The Armory Show 2024", "armory-2024", "2024-09-06T00:00:00+00:00", "2024-09-08T00:00:00+00:00"),
]
PAGE_TWO = [
    fair_node("Photo London 2026", "photo-london-2026", "2026-06-14T00:00:00+00:00", "2026-06-16T00:00:00+00:00"),
    # Duplicate slug across pages must be deduped.
    fair_node("Art Basel 2026", "art-basel-2026", "2026-06-18T00:00:00+00:00", "2026-06-21T23:00:00+00:00", True),
]


class _StubClient:
    """Returns canned GraphQL pages keyed by the requested page variable."""

    def __init__(self, pages):
        self._pages = pages
        self.calls = []

    def post_json(self, url, payload):
        page = payload["variables"]["page"]
        self.calls.append((url, page))
        return {"data": {"fairs": self._pages.get(page, [])}}


class ArtFairLocationTests(unittest.TestCase):
    def test_derive_location_us_cities_get_us_region(self):
        self.assertEqual(derive_location("The Armory Show 2026"), ("New York", "United States", "US"))
        self.assertEqual(derive_location("EXPO Chicago 2026"), ("Chicago", "United States", "US"))
        self.assertEqual(derive_location("Frieze Los Angeles 2026")[2], "US")

    def test_derive_location_international_cities(self):
        self.assertEqual(derive_location("Frieze Seoul 2026"), ("Seoul", "South Korea", "International"))
        self.assertEqual(derive_location("Art Basel 2026")[1], "Switzerland")
        self.assertEqual(derive_location("TEFAF Maastricht 2027")[1], "Netherlands")

    def test_derive_location_unknown_defaults_to_international(self):
        self.assertEqual(derive_location("Some Mystery Fair 2026"), ("", "", "International"))

    def test_derive_fair_type(self):
        self.assertEqual(derive_fair_type("photo basel 2026"), "photography_fair")
        self.assertEqual(derive_fair_type("MAZE Design Basel 2026"), "design_fair")
        self.assertEqual(derive_fair_type("Venice Biennale 2026"), "biennial")
        self.assertEqual(derive_fair_type("Sydney Contemporary 2026"), "art_fair")

    def test_derive_status_relative_to_cutoff(self):
        self.assertEqual(derive_status("2026-09-02", "2026-09-05", "2026-06-13"), "upcoming")
        self.assertEqual(derive_status("2026-06-10", "2026-06-21", "2026-06-13"), "running")
        self.assertEqual(derive_status("2024-09-06", "2024-09-08", "2026-06-13"), "past")

    def test_iso_day_and_helpers(self):
        self.assertEqual(iso_day("2026-06-18T00:00:00+00:00"), "2026-06-18")
        self.assertEqual(iso_day(None), "")
        self.assertEqual(iso_day("garbage"), "")
        self.assertEqual(year_from_dates("2026-06-18", "", "Art Basel"), 2026)
        self.assertEqual(year_from_dates("", "", "Frieze London 2025"), 2025)
        self.assertEqual(absolute_url("/fair/art-basel-2026"), "https://www.artsy.net/fair/art-basel-2026")


class NormalizeFairTests(unittest.TestCase):
    def test_normalize_maps_fields_and_categories(self):
        event = normalize_fair(PAGE_ONE[0], cutoff="2026-06-13")
        self.assertEqual(event.fair_id, "art-basel-2026")
        self.assertEqual(event.start_date, "2026-06-18")
        self.assertEqual(event.end_date, "2026-06-21")
        self.assertEqual(event.region, "International")
        self.assertEqual(event.city, "Basel")
        self.assertEqual(event.year, 2026)
        self.assertEqual(event.access, "unknown")
        self.assertEqual(event.status, "upcoming")
        self.assertIn("region:International", event.categories)
        self.assertIn("type:art_fair", event.categories)
        self.assertNotIn("raw", event.as_record())

    def test_normalize_rejects_missing_name_or_id(self):
        self.assertIsNone(normalize_fair({"slug": "x"}))
        self.assertIsNone(normalize_fair({"name": "No id fair"}))


class ConnectorPagingTests(unittest.TestCase):
    def test_fetch_dedupes_and_drops_past_fairs(self):
        connector = ArtsyFairsConnector(client=_StubClient({1: PAGE_ONE, 2: PAGE_TWO, 3: []}))
        fairs = connector.fetch_fairs(pages=3, today="2026-06-13")

        ids = [fair.fair_id for fair in fairs]
        self.assertNotIn("armory-2024", ids)  # past fair dropped
        self.assertEqual(ids.count("art-basel-2026"), 1)  # deduped across pages
        # Sorted soonest-first: Photo London (May) before Art Basel (June) before Frieze Seoul (Sep).
        self.assertEqual(ids, ["photo-london-2026", "art-basel-2026", "frieze-seoul-2026"])

    def test_include_past_keeps_ended_fairs(self):
        connector = ArtsyFairsConnector(client=_StubClient({1: PAGE_ONE, 2: [], 3: []}))
        fairs = connector.fetch_fairs(pages=3, include_past=True, today="2026-06-13")
        self.assertIn("armory-2024", [fair.fair_id for fair in fairs])

    def test_limit_caps_results(self):
        connector = ArtsyFairsConnector(client=_StubClient({1: PAGE_ONE, 2: PAGE_TWO, 3: []}))
        self.assertEqual(len(connector.fetch_fairs(limit=2, pages=3, today="2026-06-13")), 2)

    def test_graphql_errors_raise(self):
        class ErrorClient:
            def post_json(self, url, payload):
                return {"errors": [{"message": "boom"}]}

        connector = ArtsyFairsConnector(client=ErrorClient())
        with self.assertRaises(RuntimeError):
            connector.fetch_fairs(pages=1, today="2026-06-13")


if __name__ == "__main__":
    unittest.main()
