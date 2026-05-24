# Art Market Intelligence

An early-stage art market intelligence app for collecting public auction, sales, collection, provenance, and macroeconomic data in order to map art prices, demand by market, sales trends, and comparable-item price predictions.

## Current Artifacts

- `index.html` - initial dashboard/feed prototype.
- `styles.css` - dashboard layout and visual system.
- `app.js` - CSV-backed dashboard metrics, feed filters, and connector queue.
- `ingestion/` - open collection connector framework and CLI.
- `data/auction_feed_items.json` - seed auction/sales records for the prototype RSS feed.
- `feeds/auction-results.xml` - generated RSS feed for pieces sold and auctioned.
- `scripts/generate_auction_rss.py` - regenerates the auction RSS XML from JSON.
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

## Near-Term Data Work

1. Expand open collection ingestion to bulk CSV sources: National Gallery of Art, MoMA, Tate, Smithsonian, and V&A.
2. Add macro and demand signals from UN Comtrade, World Bank, FRED, BLS, and FX sources.
3. Build terms-reviewed connectors for official auction-house result pages and public realized-price archives.
4. Deduplicate aggregator records against official auction-house records.
5. Add historical OCR workflows for provenance and older sale catalogs.
