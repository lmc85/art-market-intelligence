import unittest

from ingestion.connectors.saffronart_results import (
    SaffronartResultsConnector,
    absolute_url,
    flatten_events,
    normalize_event,
    parse_wcf_date,
)


SAMPLE_PAYLOAD = {
    "Events": [
        [],
        [],
        [
            {
                "AuctionType": 0,
                "BannerImage": "auctions/2026/4975/cover.jpg",
                "EventDate": "June 2026",
                "EventEndDate": "/Date(1781623800000-0400)/",
                "EventFullDate": "15-16 June 2026",
                "EventId": 4975,
                "EventStartDate": "/Date(1781533800000-0400)/",
                "EventStatus": 6,
                "Title": "Summer Online Auction",
                "URL": "auctions/summer-online-auction-2026-4975",
            },
            {
                "AuctionType": 0,
                "BannerImage": "",
                "EventDate": "November 2000",
                "EventEndDate": "/Date(975474000000-0500)/",
                "EventFullDate": "24 November-1 December 2000",
                "EventId": 1,
                "EventStartDate": "/Date(975042000000-0500)/",
                "EventStatus": 3,
                "Title": "Auction 2000 (November)",
                "URL": "auctions/auction-2000-november-1",
            },
        ],
    ],
    "Response": {"IsSuccess": True, "Message": "Success"},
}


class _StubClient:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        return self._payload


class SaffronartResultsTests(unittest.TestCase):
    def test_parse_wcf_date_applies_offset(self):
        self.assertEqual(parse_wcf_date("/Date(1781533800000-0400)/"), "2026-06-15")
        self.assertEqual(parse_wcf_date("/Date(975042000000-0500)/"), "2000-11-24")
        self.assertEqual(parse_wcf_date(""), "")
        self.assertEqual(parse_wcf_date("not-a-date"), "")

    def test_absolute_url_prefixes_relative_paths(self):
        self.assertEqual(
            absolute_url("auctions/summer-online-auction-2026-4975"),
            "https://www.saffronart.com/auctions/summer-online-auction-2026-4975",
        )
        self.assertEqual(absolute_url("https://x.test/a"), "https://x.test/a")
        self.assertEqual(absolute_url(""), "")

    def test_flatten_events_drops_empty_groups(self):
        flat = flatten_events(SAMPLE_PAYLOAD)
        self.assertEqual(len(flat), 2)
        self.assertEqual({e["EventId"] for e in flat}, {4975, 1})

    def test_flatten_events_handles_missing_key(self):
        self.assertEqual(flatten_events({}), [])
        self.assertEqual(flatten_events({"Events": None}), [])

    def test_normalize_event_maps_core_fields(self):
        event = normalize_event(SAMPLE_PAYLOAD["Events"][2][1])

        self.assertEqual(event.sale_id, "1")
        self.assertEqual(event.title, "Auction 2000 (November)")
        self.assertEqual(event.status, "past")
        self.assertEqual(event.auction_type, "art")
        self.assertEqual(event.start_date, "2000-11-24")
        self.assertEqual(event.region, "India / South Asia")
        self.assertEqual(
            event.source_url,
            "https://www.saffronart.com/auctions/auction-2000-november-1",
        )
        self.assertEqual(event.banner_image_url, "")

    def test_normalize_event_labels_live_status(self):
        event = normalize_event(SAMPLE_PAYLOAD["Events"][2][0])
        self.assertEqual(event.status, "live")
        self.assertEqual(event.start_date, "2026-06-15")
        self.assertNotIn("raw", event.as_record())

    def test_normalize_event_rejects_missing_id_or_title(self):
        self.assertIsNone(normalize_event({"Title": "No id"}))
        self.assertIsNone(normalize_event({"EventId": 9}))

    def test_fetch_events_filters_status_and_sorts_newest_first(self):
        client = _StubClient(SAMPLE_PAYLOAD)
        connector = SaffronartResultsConnector(client=client)

        past_only = connector.fetch_events(statuses=[3])
        self.assertEqual([e.sale_id for e in past_only], ["1"])

        every = connector.fetch_events()
        self.assertEqual([e.sale_id for e in every], ["4975", "1"])
        self.assertEqual(client.calls[0][1], {"AucType": "ART"})

    def test_fetch_events_respects_limit(self):
        connector = SaffronartResultsConnector(client=_StubClient(SAMPLE_PAYLOAD))
        self.assertEqual(len(connector.fetch_events(limit=1)), 1)


if __name__ == "__main__":
    unittest.main()
