# Indices And Legal Appraisal Lanes

The app now has two enrichment lanes beyond direct auction-result ingestion.

## Internal Market Indices

The internal index builder derives prototype price-history series from normalized auction lots in SQLite:

```bash
python3 scripts/build_market_indices.py --min-lots-per-series 1
```

Output:

```text
data/market_indices.json
```

The current method groups sold lots by market, artist, sale context, and medium family. Each series is rebased to 100 at its first observed period using median realized price. Series with fewer than two periods are explicitly marked `needs_more_history`.

This is not a replacement for proprietary repeat-sale indices yet. It is the scaffolding for our own index layer once we ingest deeper historical results from Christie’s, Sotheby’s, Phillips, Bonhams, Heritage, and other archives.

## Legal Appraisal Leads

The legal appraisal lane searches CourtListener/RECAP filing metadata for public valuation, appraisal, auction-consignment, and bankruptcy leads:

```bash
python3 scripts/ingest_legal_appraisal_records.py --limit-per-query 5
```

Output:

```text
data/legal_appraisal_records.json
```

Default queries include:

- `"art appraisal" bankruptcy`
- `"fine art" appraisal bankruptcy`
- `"artwork" appraisal "chapter 11"`
- `"auction consignment" bankruptcy art`
- `"Christie's" appraisal bankruptcy`
- `"Sotheby's" appraisal bankruptcy`

The Search API returns useful filing metadata without a token. Set `COURTLISTENER_TOKEN` and pass `--enrich-documents` to attempt RECAP document text enrichment where the document is available.

```bash
COURTLISTENER_TOKEN=... python3 scripts/ingest_legal_appraisal_records.py --enrich-documents
```

These records are leads, not comps. Treat appraisal values, filing fees, sale motions, and estate schedules as separate evidence types until we match extracted works to actual auction outcomes.
