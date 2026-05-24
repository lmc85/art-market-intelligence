# Art Market Intelligence

An early-stage art market intelligence app for collecting public auction, sales, collection, provenance, and macroeconomic data in order to map art prices, demand by market, sales trends, and comparable-item price predictions.

## Current Artifacts

- `index.html` - initial dashboard/feed prototype.
- `styles.css` - dashboard layout and visual system.
- `app.js` - CSV-backed dashboard metrics, feed filters, and connector queue.
- `docs/free-data-sources.md` - prioritized register of free/public/partial-free data sources.
- `data/free_data_sources.csv` - structured source inventory for future ingestion tooling.

## Run Locally

```bash
python3 -m http.server 4173
```

Then open `http://localhost:4173`.

## Near-Term Data Work

1. Normalize open collection and authority data from museum APIs, Getty vocabularies, and Wikidata.
2. Add macro and demand signals from UN Comtrade, World Bank, FRED, BLS, and FX sources.
3. Build terms-reviewed connectors for official auction-house result pages and public realized-price archives.
4. Deduplicate aggregator records against official auction-house records.
5. Add historical OCR workflows for provenance and older sale catalogs.
