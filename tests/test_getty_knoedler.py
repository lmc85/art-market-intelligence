import unittest

from ingestion.connectors.getty_knoedler import (
    build_date,
    knoedler_row_to_lot,
    parse_amount,
)


def row(**overrides):
    base = {
        "PI Record No.": "10001",
        "Transaction": "Sold",
        "Sale Date-Year": "1885",
        "Sale Date-Month": "4",
        "Sale Date-Day": "12",
        "Price Amount": "1,250.50",
        "Price Currency": "dollars",
        "Art. Authority 1": "COROT, JEAN BAPTISTE CAMILLE",
        "Artist Name 1": "Corot",
        "Title": "Souvenir of Italy",
        "Genre": "Landscape",
        "Materials": "oil on canvas",
        "Dimensions": "24 x 32 in.",
        "Description": "A wooded river landscape.",
        "Price Note": "",
    }
    base.update(overrides)
    return base


class ParseHelpersTests(unittest.TestCase):
    def test_parse_amount_strips_separators(self):
        self.assertEqual(parse_amount("1,250.50"), 1250.5)
        self.assertEqual(parse_amount("15000"), 15000.0)
        self.assertEqual(parse_amount("$237.5"), 237.5)
        self.assertIsNone(parse_amount(""))
        self.assertIsNone(parse_amount("n/a"))

    def test_build_date_pads_and_defaults(self):
        self.assertEqual(build_date("1885", "4", "12"), "1885-04-12")
        self.assertEqual(build_date("1907", "", ""), "1907-01-01")
        self.assertEqual(build_date("1878", "13", "40"), "1878-01-01")


class KnoedlerRowMappingTests(unittest.TestCase):
    def test_maps_sold_row_to_auction_lot(self):
        lot = knoedler_row_to_lot(row())
        self.assertIsNotNone(lot)
        self.assertEqual(lot.auction_house, "M. Knoedler & Co.")
        self.assertEqual(lot.artists, ["COROT, JEAN BAPTISTE CAMILLE"])
        self.assertEqual(lot.auction_date, "1885-04-12")
        self.assertEqual(lot.style, "Landscape")
        self.assertEqual(lot.currency, "USD")
        self.assertEqual(lot.result_price.amount, 1250.5)
        self.assertEqual(lot.result_price.display, "$1,250")
        self.assertEqual(lot.source_record_id, "10001")

    def test_skips_unsold_and_returned(self):
        self.assertIsNone(knoedler_row_to_lot(row(Transaction="Unsold")))
        self.assertIsNone(knoedler_row_to_lot(row(Transaction="Returned")))

    def test_skips_missing_year_or_price(self):
        self.assertIsNone(knoedler_row_to_lot(row(**{"Sale Date-Year": ""})))
        self.assertIsNone(knoedler_row_to_lot(row(**{"Sale Date-Year": "18xx"})))
        self.assertIsNone(knoedler_row_to_lot(row(**{"Price Amount": ""})))

    def test_currency_filter_skips_non_dollars(self):
        franc_row = row(**{"Price Currency": "francs", "Price Amount": "8000"})
        self.assertIsNone(knoedler_row_to_lot(franc_row, allowed_currencies={"dollars"}))
        lot = knoedler_row_to_lot(franc_row, allowed_currencies=None)
        self.assertEqual(lot.currency, "FRF")

    def test_falls_back_to_verbatim_artist_and_untitled(self):
        lot = knoedler_row_to_lot(row(**{"Art. Authority 1": "", "Title": ""}))
        self.assertEqual(lot.artists, ["Corot"])
        self.assertEqual(lot.title, "[Untitled]")

    def test_realized_lot_is_indexable_shape(self):
        # The market-index loader requires a positive result price and a 4-digit year.
        lot = knoedler_row_to_lot(row())
        self.assertGreater(lot.result_price.amount, 0)
        self.assertEqual(lot.auction_date[:4], "1885")
        self.assertEqual(lot.status, "sold")


if __name__ == "__main__":
    unittest.main()
