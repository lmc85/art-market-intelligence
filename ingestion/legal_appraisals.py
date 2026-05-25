"""CourtListener/RECAP legal appraisal lead ingestion."""

from __future__ import annotations

import html
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin

from ingestion.http import HttpClient
from ingestion.models import utc_now_iso


COURTLISTENER_BASE_URL = "https://www.courtlistener.com"
COURTLISTENER_SEARCH_URL = f"{COURTLISTENER_BASE_URL}/api/rest/v4/search/"
COURTLISTENER_DOCUMENT_URL = f"{COURTLISTENER_BASE_URL}/api/rest/v4/recap-documents/"

DEFAULT_APPRAISAL_QUERIES = [
    '"art appraisal" bankruptcy',
    '"fine art" appraisal bankruptcy',
    '"artwork" appraisal "chapter 11"',
    '"auction consignment" bankruptcy art',
    '"Christie\'s" appraisal bankruptcy',
    '"Sotheby\'s" appraisal bankruptcy',
]

APPRAISAL_TERMS = (
    "art appraisal",
    "fine art",
    "artwork",
    "painting",
    "sculpture",
    "collection",
    "auction",
    "consignment",
    "christie's",
    "sotheby's",
    "appraiser",
    "valuation",
)


@dataclass
class LegalAppraisalLead:
    id: str
    source_id: str = "courtlistener_recap"
    source_name: str = "CourtListener RECAP Search"
    query: str = ""
    case_name: str = ""
    court: str = ""
    docket_number: str = ""
    docket_id: str = ""
    docket_entry_id: str = ""
    recap_document_id: str = ""
    pacer_doc_id: str = ""
    document_number: str = ""
    document_description: str = ""
    short_description: str = ""
    date_filed: str = ""
    source_url: str = ""
    document_available: bool = False
    matched_terms: List[str] = field(default_factory=list)
    value_mentions: List[str] = field(default_factory=list)
    confidence: str = "low"
    text_sample: str = ""
    record_source: str = "CourtListener public Search API"
    notes: str = ""
    raw: Optional[Dict[str, Any]] = None

    def as_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data.pop("raw", None)
        return data


class CourtListenerLegalAppraisalConnector:
    """Search CourtListener for public docket/document leads tied to art valuation."""

    source_id = "courtlistener_recap"
    source_name = "CourtListener RECAP Search"

    def __init__(self, token: str = "", client: Optional[HttpClient] = None):
        self.token = token or os.environ.get("COURTLISTENER_TOKEN", "")
        headers = {"Authorization": f"Token {self.token}"} if self.token else {}
        self.client = client or HttpClient(headers=headers)

    def search_appraisal_leads(
        self,
        queries: Iterable[str] = DEFAULT_APPRAISAL_QUERIES,
        limit_per_query: int = 5,
        result_type: str = "rd",
        enrich_documents: bool = False,
        text_sample_chars: int = 1200,
    ) -> Dict[str, Any]:
        leads: Dict[str, LegalAppraisalLead] = {}
        query_counts: Dict[str, int] = {}

        for query in queries:
            results = self.search(query=query, result_type=result_type, limit=limit_per_query)
            query_counts[query] = len(results)
            for result in results:
                lead = lead_from_search_result(query, result)
                if enrich_documents and self.token and lead.recap_document_id:
                    self.enrich_lead_with_document_text(lead, text_sample_chars=text_sample_chars)
                leads.setdefault(lead.id, lead)

        records = [lead.as_dict() for lead in leads.values()]
        records.sort(key=lambda item: item.get("date_filed") or "", reverse=True)
        records.sort(key=lambda item: confidence_rank(item.get("confidence") or "low"))
        return build_legal_appraisal_payload(records, query_counts, bool(self.token))

    def search(self, query: str, result_type: str = "rd", limit: int = 5) -> List[Dict[str, Any]]:
        if limit < 1:
            return []

        results: List[Dict[str, Any]] = []
        url = COURTLISTENER_SEARCH_URL
        params: Optional[Dict[str, Any]] = {
            "q": query,
            "type": result_type,
            "highlight": "on",
        }
        while len(results) < limit and url:
            payload = self.client.get_json(url, params=params)
            for result in payload.get("results", []):
                results.append(result)
                if len(results) >= limit:
                    break
            url = payload.get("next")
            params = None
        return results

    def fetch_recap_document(self, recap_document_id: str) -> Dict[str, Any]:
        if not self.token:
            raise ValueError("COURTLISTENER_TOKEN is required for recap document detail enrichment")
        return self.client.get_json(f"{COURTLISTENER_DOCUMENT_URL}{recap_document_id}/")

    def enrich_lead_with_document_text(self, lead: LegalAppraisalLead, text_sample_chars: int = 1200) -> None:
        document = self.fetch_recap_document(lead.recap_document_id)
        plain_text = clean_text(document.get("plain_text") or "")
        if plain_text:
            lead.text_sample = plain_text[:text_sample_chars]
            lead.notes = append_note(lead.notes, "Document plain text sample retrieved from RECAP document API.")


def lead_from_search_result(query: str, result: Dict[str, Any]) -> LegalAppraisalLead:
    description = clean_text(result.get("description") or result.get("snippet") or "")
    snippet = clean_text(result.get("snippet") or "")
    combined_text = " ".join([description, snippet])
    source_url = urljoin(COURTLISTENER_BASE_URL, result.get("absolute_url") or "")
    recap_document_id = str(result.get("id") or "")
    lead_id = f"courtlistener_recap:{recap_document_id or source_url}"
    matched_terms = matched_appraisal_terms(combined_text)
    value_mentions = extract_value_mentions(combined_text)

    return LegalAppraisalLead(
        id=lead_id,
        query=query,
        case_name=clean_text(result.get("caseName") or result.get("case_name") or ""),
        court=clean_text(result.get("court") or result.get("court_id") or ""),
        docket_number=clean_text(result.get("docketNumber") or result.get("docket_number") or ""),
        docket_id=str(result.get("docket_id") or ""),
        docket_entry_id=str(result.get("docket_entry_id") or ""),
        recap_document_id=recap_document_id,
        pacer_doc_id=str(result.get("pacer_doc_id") or ""),
        document_number=str(result.get("document_number") or result.get("entry_number") or ""),
        document_description=description,
        short_description=clean_text(result.get("short_description") or ""),
        date_filed=str(result.get("entry_date_filed") or result.get("dateFiled") or ""),
        source_url=source_url,
        document_available=bool(result.get("is_available")),
        matched_terms=matched_terms,
        value_mentions=value_mentions,
        confidence=confidence_label(combined_text, matched_terms, value_mentions, bool(result.get("is_available"))),
        notes=availability_note(bool(result.get("is_available"))),
        raw=result,
    )


def build_legal_appraisal_payload(
    records: List[Dict[str, Any]],
    query_counts: Dict[str, int],
    token_present: bool,
) -> Dict[str, Any]:
    return {
        "generated_at": utc_now_iso(),
        "source": {
            "source_id": "courtlistener_recap",
            "source_name": "CourtListener RECAP Search",
            "search_url": COURTLISTENER_SEARCH_URL,
            "result_type": "rd",
            "token_present": token_present,
            "caveat": "Search metadata is public; document detail/text enrichment may require a CourtListener API token and depends on RECAP availability.",
        },
        "summary": {
            "record_count": len(records),
            "high_confidence_count": sum(1 for item in records if item.get("confidence") == "high"),
            "available_document_count": sum(1 for item in records if item.get("document_available")),
            "query_count": len(query_counts),
        },
        "queries": [{"query": query, "records_seen": count} for query, count in query_counts.items()],
        "records": records,
    }


def matched_appraisal_terms(text: str) -> List[str]:
    lower = text.lower()
    return [term for term in APPRAISAL_TERMS if term in lower]


def extract_value_mentions(text: str) -> List[str]:
    patterns = [
        r"(?:USD\s*)?\$\s?\d[\d,]*(?:\.\d{2})?",
        r"\b\d+(?:\.\d+)?\s+(?:million|billion)\b",
    ]
    mentions: List[str] = []
    for pattern in patterns:
        mentions.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return list(dict.fromkeys(clean_text(mention) for mention in mentions))[:8]


def confidence_label(
    text: str,
    matched_terms: List[str],
    value_mentions: List[str],
    document_available: bool,
) -> str:
    lower = text.lower()
    score = 0
    if "appraisal" in lower or "valuation" in lower:
        score += 2
    if re.search(r"\b(art|artwork|fine art|painting|sculpture)\b", lower):
        score += 2
    if any(term in lower for term in ("bankruptcy", "chapter 11", "debtor", "estate")):
        score += 1
    if value_mentions:
        score += 1
    if document_available:
        score += 1
    if len(matched_terms) >= 3:
        score += 1

    if score >= 6:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def confidence_rank(value: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(value, 3)


def availability_note(document_available: bool) -> str:
    if document_available:
        return "RECAP indicates the document file is available; fetch text with COURTLISTENER_TOKEN if needed."
    return "Search result is a lead only; the underlying PACER document may need RECAP/PACER retrieval."


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(" ".join(text.split()))


def append_note(existing: str, note: str) -> str:
    if not existing:
        return note
    if note in existing:
        return existing
    return f"{existing} {note}"


def write_legal_appraisal_records(payload: Dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
