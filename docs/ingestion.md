# Open Collection Ingestion

The first ingestion layer focuses only on open API and bulk-file sources. It does not scrape auction result pages. That keeps the first pipeline auditable while we review terms for realized-price sources.

## Implemented Connectors

| Source ID | Source | Access | Notes |
|---|---|---|---|
| `met_open_access` | The Met Collection API | Open API | Searches object IDs, then fetches object detail records. |
| `artic_api` | Art Institute of Chicago API | Open API | Uses the artworks listing/search endpoint with an explicit field list. |
| `cleveland_open_access` | Cleveland Museum of Art Open Access API | Open API | Uses a User-Agent header and requests image-backed records. |
| `moma_collection` | MoMA Collection Data | Bulk CSV | Streams the GitHub-hosted `Artworks.csv` file without loading the full dataset into memory. |
| `christies_results` | Christie's Results | Public HTML payload | Fetches official lot-level result data into SQLite, then exports the auction RSS/dashboard schema. |

Queued but not implemented yet: National Gallery of Art, Tate, Smithsonian, Rijksmuseum, Harvard Art Museums, V&A, Europeana, and authority/macro connectors.

Official docs used for these connectors:

- The Met Collection API: `https://metmuseum.github.io/`
- Art Institute of Chicago API: `https://api.artic.edu/docs/`
- Cleveland Museum of Art Open Access API: `https://www.clevelandart.org/open-access-api`
- MoMA Collection Data: `https://github.com/MuseumofModernArt/collection`
- National Gallery of Art Open Data, queued bulk source: `https://github.com/NationalGalleryOfArt/opendata`

Auction result connector source reviewed:

- Christie's auction results: `https://www.christies.com/results?sc_lang=en`

## Run

List open collection sources and connector status:

```bash
python3 -m ingestion.run list
```

Run one connector:

```bash
python3 -m ingestion.run ingest --source artic_api --limit 10
```

Run all implemented connectors:

```bash
python3 -m ingestion.run ingest --all --limit 5
```

Search where a source supports it:

```bash
python3 -m ingestion.run ingest --source met_open_access --query "Renoir" --limit 5
```

Bulk CSV sources can be searched too:

```bash
python3 -m ingestion.run ingest --source moma_collection --query "architecture" --limit 5
```

Outputs are written to `data/ingested/*.jsonl` with a `data/ingested/latest_manifest.json` manifest. These files are gitignored because they can become large quickly.

## Normalized Artwork Shape

Each connector maps raw source data into a common JSONL record:

```json
{
  "source_id": "artic_api",
  "source_name": "Art Institute of Chicago API",
  "source_record_id": "129884",
  "title": "Starry Night and the Astronauts",
  "artist_display": "Alma Thomas",
  "artist_names": ["Alma Thomas"],
  "object_date": "1972",
  "date_begin": 1972,
  "date_end": 1972,
  "medium": "Acrylic on canvas",
  "dimensions": "152.4 x 127 cm",
  "classification": "Painting",
  "department": "Modern Art",
  "culture": "",
  "geography": "United States",
  "image_url": "https://...",
  "source_url": "https://...",
  "license": "Public domain",
  "credit_line": "",
  "accession_number": "",
  "ingestion_type": "object_metadata",
  "ingested_at": "2026-05-24T00:00:00Z"
}
```

Use `--include-raw` when debugging a connector. Default output excludes raw payloads to keep files smaller and easier to inspect.

## Guardrails

- Each request uses a clear User-Agent.
- Connectors default to small record limits.
- Generated outputs are not committed.
- Source URLs and source record IDs are preserved for auditability.
- Auction-house and realized-price pages stay out of this layer until terms review is complete.
