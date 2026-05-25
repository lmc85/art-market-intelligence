# Art Market Intelligence

An early-stage art market intelligence app for collecting public auction, sales, collection, provenance, and macroeconomic data in order to map art prices, demand by market, sales trends, and comparable-item price predictions.

## Current Artifacts

- `index.html` - initial dashboard/feed prototype.
- `styles.css` - dashboard layout and visual system.
- `app.js` - CSV-backed dashboard metrics, feed filters, and connector queue.
- `ingestion/` - open collection connector framework and CLI.
- `data/auction_feed_items.json` - seed auction/sales records for the prototype RSS feed.
- `data/market_indices.json` - generated internal auction-derived price index series.
- `data/legal_appraisal_records.json` - generated CourtListener/RECAP legal appraisal leads.
- `feeds/auction-results.xml` - generated RSS feed for pieces sold and auctioned.
- `scripts/generate_auction_rss.py` - regenerates the auction RSS XML from JSON.
- `scripts/ingest_christies_auction_feed.py` - fetches Christie’s public result lots into SQLite, then publishes JSON/RSS.
- `scripts/ingest_auction_house_feed.py` - fetches Sotheby’s, Bonhams, Phillips, and Heritage lanes into SQLite, then publishes JSON/RSS.
- `scripts/export_auction_feed.py` - republishes JSON/RSS from the local auction SQLite store.
- `scripts/build_market_indices.py` - derives prototype market indices from local auction lots.
- `scripts/ingest_legal_appraisal_records.py` - searches CourtListener/RECAP for public appraisal and bankruptcy leads.
- `docs/auction-pipeline.md` - pipeline storage, quality flags, and command notes.
- `docs/indices-and-appraisals.md` - derived index and legal appraisal lane notes.
- `docs/ingestion.md` - ingestion usage, schema, and guardrails.
- `docs/free-data-sources.md` - prioritized register of free/public/partial-free data sources.
- `data/free_data_sources.csv` - structured source inventory for future ingestion tooling.

## Run Locally

```bash
python3 -m http.server 4173
```

Then open `http://localhost:4173`.

## Run Ingestion

List connector status:

```bash
python3 -m ingestion.run list
```

Run the implemented open collection connectors:

```bash
python3 -m ingestion.run ingest --all --limit 5
```

Outputs are written to `data/ingested/` and ignored by git.

## Auction RSS Feed

The prototype feed is available at:

```text
http://localhost:4173/feeds/auction-results.xml
```

Regenerate it after editing `data/auction_feed_items.json`:

```bash
python3 scripts/generate_auction_rss.py
```

Fetch live first-pass Christie's result records into the RSS feed:

```bash
python3 scripts/ingest_christies_auction_feed.py --limit 12 --sale-query contemporary --replace
```

Fetch the additional official auction-house lanes:

```bash
python3 scripts/ingest_auction_house_feed.py --source bonhams_results --sale-query contemporary --limit 12 --replace-source
python3 scripts/ingest_auction_house_feed.py --source phillips_auctions --sale-query contemporary --limit 12 --replace-source
python3 scripts/ingest_auction_house_feed.py --source sothebys_results --sale-query modern --limit 12 --replace-source
```

Add public lot-detail enrichment for medium, dimensions, provenance, literature, and stronger image metadata:

```bash
python3 scripts/ingest_christies_auction_feed.py --limit 12 --sale-query contemporary --replace --enrich-details --detail-limit 5
```

The Christie’s script stores lots in `data/auction/auction_pipeline.sqlite`, saves sale and detail raw snapshots under `data/auction/raw_snapshots/`, then exports the dashboard JSON and RSS feed.

Build internal market index lanes from local auction results:

```bash
python3 scripts/build_market_indices.py --min-lots-per-series 1
```

Search public legal/appraisal filing leads through CourtListener/RECAP:

```bash
python3 scripts/ingest_legal_appraisal_records.py --limit-per-query 5
```

Set `COURTLISTENER_TOKEN` and pass `--enrich-documents` when document text enrichment is needed and permitted by the API.

## Near-Term Data Work

1. Expand open collection ingestion to bulk CSV sources: National Gallery of Art, MoMA, Tate, Smithsonian, and V&A.
2. Add macro and demand signals from UN Comtrade, World Bank, FRED, BLS, and FX sources.
3. Deepen auction-house detail enrichment for medium, dimensions, provenance, literature, and prior-sale cues.
4. Deduplicate aggregator records against official auction-house records.
5. Add historical OCR workflows for provenance and older sale catalogs.
