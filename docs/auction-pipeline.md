# Auction Pipeline

The auction pipeline now writes live result records through a local SQLite store before publishing dashboard JSON and RSS.

## Flow

```text
fetch source page
  -> save raw snapshot
  -> parse source payload
  -> normalize to canonical auction lots
  -> validate quality flags
  -> upsert into SQLite by stable identity key
  -> export dashboard JSON
  -> export RSS XML
```

## Local Artifacts

| Path | Purpose | Git |
|---|---|---|
| `data/auction/auction_pipeline.sqlite` | Local auction lot and ingest-run database | Ignored |
| `data/auction/raw_snapshots/` | Raw source payload snapshots for audit/debug | Ignored |
| `data/auction_feed_items.json` | Published dashboard feed data | Committed |
| `feeds/auction-results.xml` | Published RSS feed | Committed |

## Commands

Fetch Christie’s public auction results, store them, and publish the feed:

```bash
python3 scripts/ingest_christies_auction_feed.py --limit 12 --sale-query contemporary --replace
```

Export feed files from the existing SQLite store:

```bash
python3 scripts/export_auction_feed.py --limit 100
```

Inspect the local database:

```bash
sqlite3 data/auction/auction_pipeline.sqlite \
  'select count(*), sum(prediction_ready) from auction_lots;'
```

## Quality Flags

Each normalized lot stores booleans for:

- `has_artist`
- `has_title`
- `has_auction_date`
- `has_estimate`
- `has_result_price`
- `has_starting_price`
- `has_prior_sale`
- `has_source_url`
- `has_image`
- `has_medium`
- `has_dimensions`

`prediction_ready` is currently true when a lot has artist, title, auction date, estimate, result price, and source URL. For stronger valuation work, the next enrichment target is lot detail pages for medium, dimensions, provenance, and prior-sale context.
