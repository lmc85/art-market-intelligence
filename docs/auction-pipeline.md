# Auction Pipeline

The auction pipeline now writes live result records through a local SQLite store before publishing dashboard JSON and RSS.

## Flow

```text
fetch source page
  -> save raw snapshot
  -> parse source payload
  -> normalize to canonical auction lots
  -> optionally fetch lot detail pages
  -> enrich medium, dimensions, provenance, literature, and image metadata
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

Fetch the same sale and enrich selected lots from their public detail pages:

```bash
python3 scripts/ingest_christies_auction_feed.py --limit 12 --sale-query contemporary --replace --enrich-details --detail-limit 5
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

`prediction_ready` is currently true when a lot has artist, title, auction date, estimate, result price, and source URL. Detail enrichment improves confidence for valuation work by adding medium, dimensions, provenance, literature, and stronger image metadata; prior-sale context still needs a matching source such as official archive pages or a terms-reviewed realized-price database.
