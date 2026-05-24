import unittest

from ingestion.connectors import implemented_source_ids
from ingestion.registry import load_source_register, open_collection_sources


class RegistryTests(unittest.TestCase):
    def test_implemented_sources_exist_in_register(self):
        source_ids = {source.source_id for source in load_source_register()}

        for source_id in implemented_source_ids():
            self.assertIn(source_id, source_ids)

    def test_open_collection_sources_include_api_and_bulk_candidates(self):
        sources = open_collection_sources(load_source_register())
        source_ids = {source.source_id for source in sources}

        self.assertIn("met_open_access", source_ids)
        self.assertIn("artic_api", source_ids)
        self.assertIn("nga_open_data", source_ids)
        self.assertNotIn("christies_results", source_ids)


if __name__ == "__main__":
    unittest.main()
