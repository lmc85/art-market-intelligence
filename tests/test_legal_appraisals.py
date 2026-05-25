import unittest

from ingestion.legal_appraisals import build_legal_appraisal_payload, lead_from_search_result


class LegalAppraisalTests(unittest.TestCase):
    def test_search_result_maps_to_appraisal_lead(self):
        result = {
            "absolute_url": "/docket/52985890/697/example/",
            "description": "Report RE: <mark>Art Appraisal</mark> and Notice of Intent to Pay Appraiser for fine art collection valued at $120,000.",
            "docket_entry_id": 201575065,
            "docket_id": 52985890,
            "document_number": 697,
            "entry_date_filed": "2015-05-11",
            "id": 207348688,
            "is_available": True,
            "pacer_doc_id": "196027554725",
        }

        lead = lead_from_search_result('"art appraisal" bankruptcy', result)

        self.assertEqual(lead.id, "courtlistener_recap:207348688")
        self.assertEqual(lead.date_filed, "2015-05-11")
        self.assertIn("art appraisal", lead.matched_terms)
        self.assertIn("$120,000", lead.value_mentions)
        self.assertEqual(lead.confidence, "high")
        self.assertTrue(lead.document_available)
        self.assertTrue(lead.source_url.endswith("/docket/52985890/697/example/"))

    def test_build_payload_summarizes_records(self):
        payload = build_legal_appraisal_payload(
            records=[
                {"confidence": "high", "document_available": True},
                {"confidence": "medium", "document_available": False},
            ],
            query_counts={"art": 2},
            token_present=False,
        )

        self.assertEqual(payload["summary"]["record_count"], 2)
        self.assertEqual(payload["summary"]["high_confidence_count"], 1)
        self.assertEqual(payload["summary"]["available_document_count"], 1)
        self.assertFalse(payload["source"]["token_present"])


if __name__ == "__main__":
    unittest.main()
