# Auction RSS Feed

The auction RSS feed exposes sold and auctioned pieces for downstream tools. The prototype feed is generated from `data/auction_feed_items.json` and written to `feeds/auction-results.xml`.

Local feed URL:

```text
http://localhost:4173/feeds/auction-results.xml
```

Regenerate the feed:

```bash
python3 scripts/generate_auction_rss.py
```

Fetch the first live Christie’s result feed:

```bash
python3 scripts/ingest_christies_auction_feed.py --limit 12 --sale-query contemporary --replace
```

Fetch live records with detail-page enrichment:

```bash
python3 scripts/ingest_christies_auction_feed.py --limit 12 --sale-query contemporary --replace --enrich-details --detail-limit 5
```

Republish from the local SQLite store without fetching:

```bash
python3 scripts/export_auction_feed.py --limit 100
```

## Required Fields

Each feed item supports the fields requested for sale and auction monitoring:

| Field | JSON key | RSS tag |
|---|---|---|
| Title | `title` | `artmi:title` |
| Artists | `artists` | `artmi:artists` |
| Style | `style` | `artmi:style` |
| Auction house | `auction_house` | `artmi:auctionHouse` |
| Auction date | `auction_date` | `artmi:auctionDate` |
| Starting price | `starting_price.display` | `artmi:startingPrice` |
| Estimated selling price | `estimated_selling_price.display` | `artmi:estimatedSellingPrice` |
| Last sold price | `last_sold_price.display` | `artmi:lastSoldPrice` |
| Sold/result price | `result_price.display` | `artmi:resultPrice` |
| Medium | `medium` | `artmi:medium` |
| Dimensions | `dimensions` | `artmi:dimensions` |
| Provenance | `provenance` | `artmi:provenance` |
| Literature | `literature` | `artmi:literature` |
| Prediction ready | `prediction_ready` | `artmi:predictionReady` |

Optional fields are omitted from the XML when they are not available. The dashboard displays unavailable values as `Not available`.

## Notes

- Current records are live first-pass Christie’s public auction results.
- Christie’s public lot-list payload includes estimates and realized prices, but not starting price or prior sale price. Detail pages now enrich medium, dimensions, provenance, and literature when available; prior sale price still needs archive matching or partner data.
- Live records should preserve source URL, source ID, auction house, sale date, and collection timestamp.
- The next connector targets are tracked in `data/next_ingestion_targets.json`.
- The feed uses an `artmi` namespace for custom fields: `https://artmarketintelligence.local/rss/1.0`.
