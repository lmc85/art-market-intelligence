# Free Art Market Data Source Register

Snapshot date: 2026-05-24

This register separates genuinely open/free sources from sources that are only free to browse or free with an account. For anything without an official API, treat the entry as an ingestion candidate until we review its terms, robots policy, rate limits, and whether a data partnership is safer.

## Best First Stack

1. **Sales comps and realized prices:** start with [Heritage Auctions](https://www.ha.com/c/search/results.zx), [LiveAuctioneers](https://www.liveauctioneers.com/auction-results), [Artsy Price Database](https://www.artsy.net/price-database), and official auction-house result pages from Christie's, Sotheby's, Bonhams, Phillips, Artcurial, Dorotheum, Lempertz, Bukowskis, Doyle, Swann, Freeman's Hindman, and Bruun Rasmussen.
2. **Artwork and artist enrichment:** normalize sale lots against object/artist vocabularies from [The Met](https://www.metmuseum.org/en/hubs/open-access), [Art Institute of Chicago](https://api.artic.edu/docs/), [Cleveland Museum of Art](https://www.clevelandart.org/open-access-api), [Smithsonian Open Access](https://www.si.edu/OpenAccess), [Rijksmuseum](https://data.rijksmuseum.nl/), [National Gallery of Art](https://github.com/NationalGalleryOfArt/opendata), [Harvard Art Museums](https://github.com/harvardartmuseums/api-docs), [MoMA](https://github.com/MuseumofModernArt/collection), [Tate](https://github.com/tategallery/collection), [Europeana](https://www.europeana.eu/en/apis), and [Wikidata](https://query.wikidata.org/).
3. **Historical provenance and sales context:** use [Getty Provenance Index](https://www.getty.edu/databases-tools-and-technologies/provenance/), [Getty Vocabularies](https://www.getty.edu/research/tools/vocabularies/), [Getty Research Portal](https://www.getty.edu/research/tools/portal/), [Internet Archive](https://archive.org/), [HathiTrust](https://www.hathitrust.org/), and [Gallica](https://gallica.bnf.fr/) for historical catalog and provenance features.
4. **Demand and market geography:** combine sale-location signals with [UN Comtrade](https://comtradeapi.un.org/) HS 97 trade flows, [World Bank Indicators](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation), [FRED](https://fred.stlouisfed.org/docs/api/fred/), [BLS CPI](https://www.bls.gov/bls/api_features.htm), exchange-rate sources, and public art-market reports.

## Source Inventory

| Priority | Source | Data class | Free access | Coverage/value | Ingestion notes |
|---|---|---|---|---|---|
| P0 | [Heritage Auctions Archives](https://www.ha.com/c/search/results.zx) | Realized prices | Free browse; account may improve access | Large searchable archive with realized prices, images, descriptions, dates, categories, and bidder context across fine art and collectibles | Strong first target for structured comps; confirm automated-use terms before scraping |
| P0 | [LiveAuctioneers Auction Results](https://www.liveauctioneers.com/auction-results) | Realized prices | Free browse/search; account may be required for depth | Aggregated global auction results across many houses, often with hammer/sold prices, dates, categories, and images | Valuable market breadth; likely no public API, so terms review and throttled extraction strategy required |
| P0 | [Artsy Price Database](https://www.artsy.net/price-database) | Realized prices | Free public product; login may be required | Auction results for artists and works sold through major houses; useful artist-level comp surface | Good for discovery and benchmarking; verify access constraints before automation |
| P0 | [Christie's Results](https://www.christies.com/results?sc_lang=en) | Official auction results | Free browse | Major global auction-house result pages with sale names, locations, dates, lots, estimates, and realized prices where exposed | High-quality canonical data; page structure and availability vary by sale |
| P0 | [Sotheby's Results](https://www.sothebys.com/en/results) | Official auction results | Free browse; login may be prompted | Major global auction results, categories, sale dates, locations, lot metadata, and realized prices where exposed | High-value canonical source; terms and anti-bot behavior need review |
| P0 | [Bonhams Results](https://www.bonhams.com/auctions/results/) | Official auction results | Free browse | Global auction results across fine art, design, jewelry, wine, cars, and collectibles | Good category breadth; some pages may block automated clients |
| P0 | [Phillips Auctions](https://www.phillips.com/auctions) | Official auction results | Free browse | Modern/contemporary art, design, watches, editions, photographs | High signal for contemporary market; confirm current result URL patterns |
| P0 | [Artcurial Results](https://www.artcurial.com/en/results-auctions-sales/) | Official auction results | Free browse | French and international auction results across art, design, watches, cars, luxury | Useful Europe signal; multilingual normalization needed |
| P0 | [Dorotheum Auction Results](https://www.dorotheum.com/en/auction-results/) | Official auction results | Free browse | Austrian/European auction results across fine art, antiques, jewelry, design | Strong Central Europe source; multilingual categories and currencies |
| P0 | [Lempertz Sale Results](https://www.lempertz.com/en/auctions/sale-results.html) | Official auction results | Free browse | German auction-house results, including old masters, modern, Asian art, decorative art | Good specialist European data; normalize EUR and estimates |
| P1 | [Bukowskis Results](https://www.bukowskis.com/en/results) | Official auction results | Free browse | Nordic auction results, modern/design/fine art/decorative arts | Adds Scandinavia demand and sale-location signal |
| P1 | [Bruun Rasmussen Past Auctions](https://bruun-rasmussen.dk/m/auctions?tab=past) | Official auction results | Free browse | Danish/Nordic auction results, now under Bonhams brand | Useful for Nordic market; confirm result depth by sale |
| P1 | [Doyle Past Auctions](https://www.doyle.com/past-auctions) | Official auction results | Free browse | US regional auction results across fine art, jewelry, design, estates | Helpful mid-market US comps |
| P1 | [Swann Galleries Past Auctions](https://www.swanngalleries.com/auctions/past-auctions/) | Official auction results | Free browse | Prints, photographs, books, African American art, illustration, works on paper | High value for works-on-paper categories |
| P1 | [Freeman's Hindman Past Auctions](https://hindmanauctions.com/auctions/past-auctions) | Official auction results | Free browse | US regional auction results across fine art, design, jewelry, Native American art, books | Strong mid-market and regional US signal |
| P1 | [Barnebys Realized Prices](https://www.barnebys.com/realized-prices) | Aggregated realized prices | Free browse/search | Aggregated auction results across houses and categories | Useful discovery surface; verify data depth and automation terms |
| P1 | [BidtoArt](https://bidtoart.com/) | Realized prices | Free browse/search | Fine-art auction result database and artist pages | Candidate comp source; validate coverage and reuse terms |
| P1 | [FindArtValue](https://findartvalue.com/) | Realized prices | Free browse/search | Art auction result search by artist and title | Candidate comp source; validate data quality and duplicate overlap |
| P2 | [Drouot / Gazette Drouot Results](https://www.gazette-drouot.com/en/auctions/results) | Auction results | Partial free; subscription may gate full records | French auction ecosystem results, sale catalogs, and realized prices | Great France coverage; may not satisfy free-only requirement at scale |
| P2 | [Invaluable Price Archive](https://www.invaluable.com/inv/help/faq/search-price-archive/) | Aggregated realized prices | Free account for some access; older/deeper access may be paid | Large auction platform archive across art, antiques, design, collectibles | Use for source discovery unless free-access scope is sufficient |
| P2 | [MutualArt Price Database](https://www.mutualart.com/price-database) | Aggregated realized prices | Limited free; full access usually paid | Large artist/result database with analytics | Useful benchmark and artist discovery, not a core free ingestion source |
| P0 | [The Met Open Access](https://www.metmuseum.org/en/hubs/open-access) | Object metadata/images | Open API/CC0 records where marked | Artist names, dates, media, dimensions, culture, department, images, object records | Key object-normalization and visual similarity source |
| P0 | [Art Institute of Chicago API](https://api.artic.edu/docs/) | Object metadata/images | Open API | Rich artwork metadata, images, provenance, exhibitions, classification, artist data | Excellent structured API for feature engineering |
| P0 | [Cleveland Museum of Art Open Access API](https://www.clevelandart.org/open-access-api) | Object metadata/images | Open API | Artwork records, creators, departments, measurements, provenance, images | High-quality metadata and CC0 image set |
| P0 | [Smithsonian Open Access](https://www.si.edu/OpenAccess) | Object metadata/images | Open data/API | Cross-institution collection data and images, including art, design, photography | Broad enrichment and image data; mixed institution vocabularies |
| P0 | [Rijksmuseum Data Services](https://data.rijksmuseum.nl/) | Object metadata/images | Open API with key | Dutch and European collection metadata, artists, images, production places, dates | Great for old master/Dutch categories and artist normalization |
| P0 | [National Gallery of Art Open Data](https://github.com/NationalGalleryOfArt/opendata) | Object metadata | GitHub CSV/open data | Artwork, artist, provenance, constituents, exhibitions, dimensions | Easy bulk ingest and entity-resolution test set |
| P0 | [Harvard Art Museums API](https://github.com/harvardartmuseums/api-docs) | Object metadata/images | Free API key | Artwork records, people, exhibitions, provenance, places, images | Good API shape; key required |
| P0 | [MoMA Collection Data](https://github.com/MuseumofModernArt/collection) | Object and artist metadata | GitHub CSV | Modern/contemporary artwork and artist collection data | Useful for contemporary artist/category normalization |
| P0 | [Tate Collection Data](https://github.com/tategallery/collection) | Object and artist metadata | GitHub JSON/CSV | British/international modern and contemporary collection data | Good artist birth/death/date enrichment |
| P1 | [Cooper Hewitt API](https://apidocs.cooperhewitt.org/api-home/) | Design object metadata | API/GitHub-style data | Design/decorative arts metadata, makers, media, periods | Useful for design-market comps |
| P1 | [Europeana APIs](https://www.europeana.eu/en/apis) | Aggregated cultural metadata | Open APIs | Pan-European cultural heritage metadata across institutions | Excellent for multilingual entity matching and cross-institution references |
| P1 | [Wikidata Query Service](https://query.wikidata.org/) | Entity graph | Open SPARQL endpoint | Artists, movements, nationalities, auction-related entities, authority IDs | Best authority-resolution backbone; cache and respect query limits |
| P1 | [Wikimedia Commons Structured Data](https://commons.wikimedia.org/wiki/Commons:Structured_data) | Images/entity metadata | Open APIs | Image metadata, depicts statements, creator links, licensing | Useful for visual enrichment where licensing permits |
| P1 | [Victoria and Albert Museum API](https://developers.vam.ac.uk/) | Object metadata/images | Open API | Design, decorative arts, fashion, photography, sculpture, Asian art | Strong design/decorative arts enrichment |
| P2 | [Finnish National Gallery API](https://www.kansallisgalleria.fi/en/api) | Object metadata/images | Open API | Finnish and Nordic collection records | Useful regional enrichment; lower priority for global MVP |
| P0 | [Getty Provenance Index](https://www.getty.edu/databases-tools-and-technologies/provenance/) | Historical sales/provenance | Free database/search; linked data availability varies | Historical sale catalogs, provenance events, collector/dealer names, artwork references | Important for historical market and provenance features, not contemporary price predictions |
| P0 | [Getty Vocabularies](https://www.getty.edu/research/tools/vocabularies/) | Authority data | Open linked data/APIs | ULAN artists, AAT object/material terms, TGN geography, CONA works | Use for canonical artist/place/material/category IDs |
| P1 | [Getty Research Portal](https://www.getty.edu/research/tools/portal/) | Digitized art history/catalogs | Free search | Digitized books and sale catalogs from art-history libraries | OCR source for historical auction catalogs and bibliographic context |
| P1 | [Internet Archive](https://archive.org/) | Digitized catalogs/OCR | Free | Public-domain books, sale catalogs, image scans, OCR | Use for historical sale catalog extraction where rights allow |
| P1 | [HathiTrust](https://www.hathitrust.org/) | Digitized books/catalogs | Free search; access varies by rights | Historical catalogs, art-history books, OCR snippets/full text where public domain | Good source discovery and OCR pipeline input |
| P1 | [Gallica BnF](https://gallica.bnf.fr/) | Digitized French catalogs/OCR | Free | French books, journals, sale catalogs, archival scans | Good for French historical market and names in original language |
| P0 | [UN Comtrade API](https://comtradeapi.un.org/) | Trade/demand signals | Free API with limits | HS 97 art/antiques trade flows by country, partner, year/month, value, quantity | Core demand geography signal by market; map HS codes carefully |
| P0 | [World Bank Indicators API](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation) | Macro context | Free API | GDP, population, income, inflation, trade, country metadata | Use for country-level demand and purchasing-power features |
| P0 | [FRED API](https://fred.stlouisfed.org/docs/api/fred/) | Macro/financial data | Free API key | Rates, CPI, FX, wealth proxies, financial conditions, US and some global series | Useful for time-series adjustment and forecasting covariates |
| P1 | [BLS Public Data API](https://www.bls.gov/bls/api_features.htm) | Inflation/labor macro | Free API | CPI, PPI, wage, labor-market data | Use for inflation adjustment, especially US-dollar realized prices |
| P1 | [ExchangeRate.host](https://exchangerate.host/documentation) | FX rates | Free tier/API | Current and historical exchange rates depending on plan | Normalize hammer prices to base currency; verify free historical coverage |
| P1 | [ECB Data Portal API](https://data.ecb.europa.eu/help/api/overview) | FX/rates/macro | Free API | Euro-area exchange rates, rates, financial statistics | Strong EUR normalization source |
| P1 | [World Inequality Database](https://wid.world/data/) | Wealth distribution | Free data | Income/wealth distribution indicators by country | Useful demand proxy for high-end art markets |
| P2 | [OECD Data Explorer](https://data-explorer.oecd.org/) | Macro context | Free API/downloads | Income, demographics, trade, finance, tourism, culture-adjacent indicators | Add after core macro sources |
| P2 | [Art Basel and UBS Art Market Report](https://www.ubs.com/us/en/wealth-management/our-solutions/private-wealth-management/family-office-solutions/art-advisory/art-basel-art-market-report.html) | Market report | Free PDF/download, not raw data | Annual market size, regional shares, dealer/auction/e-commerce context | Use for assumptions, validation, charts; not training data |
| P2 | [Deloitte Art & Finance Report](https://www.deloitte.com/global/en/Industries/financial-services/research/art-finance-report.html) | Market report | Free PDF/download, not raw data | Wealth management, art finance, risk, collector sentiment | Context and product strategy, not core ingestion |
| P2 | [Hiscox Online Art Trade Report](https://www.hiscox.com/online-art-trade-report) | Market report | Free report, not raw data | Online art sales trends and collector behavior | Useful qualitative validation and product positioning |

## Initial Data Model

Minimum source-register fields:

| Field | Purpose |
|---|---|
| `source_id` | Stable internal key, e.g. `heritage_auctions` |
| `source_name` | Display/source name |
| `source_class` | `realized_price`, `official_auction_result`, `object_metadata`, `authority`, `historical_catalog`, `macro`, or `report` |
| `access_type` | `open_api`, `bulk_file`, `free_browse`, `free_account`, `partial_free`, or `report` |
| `license_or_terms_status` | `open`, `review_needed`, `limited`, `unknown` |
| `geography` | Main market/geographic coverage |
| `date_span` | Expected historical coverage |
| `core_fields` | Expected useful fields |
| `ingestion_method` | API, CSV/GitHub, crawl candidate, manual upload, OCR, PDF extraction |
| `priority` | P0/P1/P2 for MVP sequencing |
| `risk_notes` | Terms, duplicate risk, currency issues, login, quality caveats |

## MVP Ingestion Order

1. Ingest open/bulk enrichment data first: NGA, MoMA, Tate, Met, AIC, Cleveland, Getty vocabularies, and Wikidata. This gives us canonical artist/category/place/material IDs before price data gets messy.
2. Add macro normalization: UN Comtrade, World Bank, FRED, BLS, ECB/FX. This makes every sale record currency- and inflation-aware from day one.
3. Build first price-comp connectors for sources with the clearest public structure: Heritage, Christie's, Sotheby's, Bonhams, Phillips, Artcurial, Dorotheum, Lempertz, Doyle, Swann, Freeman's Hindman, Bukowskis, and Bruun Rasmussen.
4. Add aggregation platforms as discovery/coverage sources after terms review: LiveAuctioneers, Artsy, Barnebys, BidtoArt, FindArtValue, Invaluable, MutualArt.
5. Add historical OCR pipeline for Getty Research Portal, Internet Archive, HathiTrust, and Gallica once contemporary comps are flowing.

## Key Normalization Rules

- Store both original hammer/realized currency and normalized USD/EUR values.
- Preserve estimate low/high, premium inclusion status, and sale currency whenever available.
- Split artist attribution from lot title; do not assume the first phrase before a comma is the artist.
- Track auction house, venue city, venue country, sale date, lot date, and buyer geography separately.
- Deduplicate across aggregator platforms and official auction-house records by lot title, artist, sale date, auction house, dimensions, medium, and image hash.
- Keep image URLs and local thumbnails separate from image rights/licensing status.
- Make access provenance auditable: every sale record should know which source URL produced it and when it was collected.

