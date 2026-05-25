const sourcePath = "data/free_data_sources.csv";
const auctionFeedPath = "data/auction_feed_items.json";
const nextTargetsPath = "data/next_ingestion_targets.json";
const marketIndicesPath = "data/market_indices.json";
const legalAppraisalsPath = "data/legal_appraisal_records.json";

const feedItems = [
  {
    type: "demand",
    market: "Asia",
    source: "UN Comtrade + auction queue",
    title: "Demand pressure rising for postwar prints",
    detail: "Cross-border art trade momentum and public sale volume point to a stronger bid stack.",
    confidence: "74%",
    series: [30, 38, 35, 48, 56, 61, 72],
  },
  {
    type: "price",
    market: "New York",
    source: "Official results",
    title: "Estimate spread widening in contemporary editions",
    detail: "Recent lots show broader low/high ranges, a cue to track premium-inclusive realized prices carefully.",
    confidence: "68%",
    series: [42, 47, 51, 50, 58, 63, 69],
  },
  {
    type: "risk",
    market: "Global",
    source: "Source register",
    title: "Aggregator records need duplicate controls",
    detail: "Official house records should win when title, dimensions, image hash, and sale date match.",
    confidence: "High",
    series: [60, 57, 53, 49, 43, 39, 35],
  },
  {
    type: "demand",
    market: "Nordics",
    source: "Bukowskis + Bruun Rasmussen",
    title: "Nordic design coverage is an early advantage",
    detail: "Regional houses can fill mid-market comps that major-house feeds often underrepresent.",
    confidence: "71%",
    series: [24, 28, 34, 41, 44, 53, 61],
  },
  {
    type: "price",
    market: "Europe",
    source: "Lempertz + Dorotheum",
    title: "Old master comps need provenance-weighted features",
    detail: "Attribution language, exhibition history, and catalog citations will matter as much as dimensions.",
    confidence: "63%",
    series: [55, 52, 57, 54, 59, 62, 65],
  },
];

const fallbackSources = [
  {
    source_name: "Heritage Auctions Archives",
    source_class: "realized_price",
    access_type: "free_browse",
    priority: "P0",
  },
  {
    source_name: "Christie's Results",
    source_class: "official_auction_result",
    access_type: "free_browse",
    priority: "P0",
  },
  {
    source_name: "The Met Open Access",
    source_class: "object_metadata",
    access_type: "open_api",
    priority: "P0",
  },
  {
    source_name: "UN Comtrade API",
    source_class: "macro_demand",
    access_type: "open_api",
    priority: "P0",
  },
];

const fallbackAuctionItems = [
  {
    status: "sold",
    title: "Untitled screenprint from a late twentieth-century edition",
    artists: ["Attributed artist pending verification"],
    style: "Postwar prints",
    auction_house: "Swann Galleries",
    auction_date: "2026-05-18",
    starting_price: { display: "$18,000" },
    estimated_selling_price: { display: "$24,000-$32,000" },
    last_sold_price: { display: "$28,000" },
    medium: "Screenprint",
    dimensions: "24 x 32 in.",
  },
];

const fallbackNextTargets = [
  {
    source_id: "heritage_auctions",
    source_name: "Heritage Auctions Archives",
    priority: "P0",
    target_type: "Realized price archive",
    stage: "Terms review",
    rss_use: "Sold lots, estimates, realized prices",
    next_action: "Confirm automated-use terms, then map search/result pages.",
  },
];

const fallbackMarketIndices = {
  summary: {
    index_count: 0,
    history_ready_count: 0,
    needs_more_history_count: 0,
  },
  indices: [],
};

const fallbackLegalAppraisals = {
  summary: {
    record_count: 0,
    high_confidence_count: 0,
    available_document_count: 0,
  },
  records: [],
};

let sources = [];
let auctionItems = [];
let nextTargets = [];
let marketIndexPayload = fallbackMarketIndices;
let legalAppraisalPayload = fallbackLegalAppraisals;
let activeFilter = "all";
let searchTerm = "";

const elements = {
  metricSources: document.querySelector("#metric-sources"),
  metricSourcesDetail: document.querySelector("#metric-sources-detail"),
  metricP0: document.querySelector("#metric-p0"),
  metricPrice: document.querySelector("#metric-price"),
  metricAuctionEvents: document.querySelector("#metric-auction-events"),
  metricAuctionDetail: document.querySelector("#metric-auction-detail"),
  feedList: document.querySelector("#feed-list"),
  auctionFeedBody: document.querySelector("#auction-feed-body"),
  marketIndexList: document.querySelector("#market-index-list"),
  marketIndexCount: document.querySelector("#market-index-count"),
  legalLeadList: document.querySelector("#legal-lead-list"),
  legalLeadCount: document.querySelector("#legal-lead-count"),
  coverageList: document.querySelector("#coverage-list"),
  queueBody: document.querySelector("#queue-body"),
  targetList: document.querySelector("#target-list"),
  targetCount: document.querySelector("#target-count"),
  search: document.querySelector("#global-search"),
  filterButtons: document.querySelectorAll("[data-filter]"),
};

init();

async function init() {
  [sources, auctionItems, nextTargets, marketIndexPayload, legalAppraisalPayload] = await Promise.all([
    loadSources(),
    loadJson(auctionFeedPath, fallbackAuctionItems),
    loadJson(nextTargetsPath, fallbackNextTargets),
    loadJson(marketIndicesPath, fallbackMarketIndices),
    loadJson(legalAppraisalsPath, fallbackLegalAppraisals),
  ]);
  renderMetrics();
  renderMarketIndices();
  renderLegalLeads();
  renderCoverage();
  renderQueue();
  renderAuctionFeed();
  renderNextTargets();
  renderFeed();
  bindEvents();
}

async function loadSources() {
  try {
    const response = await fetch(sourcePath);
    if (!response.ok) throw new Error(`Unable to load ${sourcePath}`);
    const text = await response.text();
    return parseCsv(text);
  } catch (error) {
    console.warn(error);
    return fallbackSources;
  }
}

async function loadJson(path, fallback) {
  try {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`Unable to load ${path}`);
    return await response.json();
  } catch (error) {
    console.warn(error);
    return fallback;
  }
}

function bindEvents() {
  elements.filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
      activeFilter = button.dataset.filter;
      elements.filterButtons.forEach((item) => item.classList.toggle("active", item === button));
      renderFeed();
    });
  });

  elements.search.addEventListener("input", (event) => {
    searchTerm = event.target.value.trim().toLowerCase();
    renderFeed();
    renderAuctionFeed();
    renderMarketIndices();
    renderLegalLeads();
    renderQueue();
    renderNextTargets();
  });
}

function renderMarketIndices() {
  const indices = (marketIndexPayload.indices || []).filter((item) => {
    if (!searchTerm) return true;
    return [
      item.series_type,
      item.label,
      item.status,
      item.confidence,
      item.latest_period,
      item.notes,
    ]
      .join(" ")
      .toLowerCase()
      .includes(searchTerm);
  });
  const summary = marketIndexPayload.summary || {};
  elements.marketIndexCount.textContent = `${summary.history_ready_count || 0}/${summary.index_count || 0} trend-ready`;

  elements.marketIndexList.innerHTML = indices.length
    ? indices.slice(0, 6).map(renderMarketIndex).join("")
    : `<p class="empty-state">No market index series match the current search.</p>`;
}

function renderMarketIndex(item) {
  const points = item.points || [];
  const series = points.map((point) => point.index_value || 100);
  return `
    <article class="index-row">
      <div class="index-body">
        <div class="feed-meta">
          <span>${escapeHtml(formatLabel(item.series_type || "series"))}</span>
          <span>${escapeHtml(formatLabel(item.status || "queued"))}</span>
          <span>${escapeHtml(formatLabel(item.confidence || "low"))}</span>
        </div>
        <h3>${escapeHtml(item.label || "Market index")}</h3>
        <p>${escapeHtml(item.notes || "")}</p>
        <div class="index-stats">
          <span><strong>${escapeHtml(numberLabel(item.latest_index_value))}</strong> index</span>
          <span><strong>${escapeHtml(item.latest_lots_sold || 0)}</strong> lots</span>
          <span><strong>${escapeHtml(moneyNumberLabel(item.latest_median_result))}</strong> median</span>
          <span><strong>${escapeHtml(ratioLabel(item.latest_estimate_ratio))}</strong> est. ratio</span>
        </div>
      </div>
      ${renderSparkline(series)}
    </article>
  `;
}

function renderLegalLeads() {
  const records = (legalAppraisalPayload.records || []).filter((item) => {
    if (!searchTerm) return true;
    return [
      item.case_name,
      item.court,
      item.docket_number,
      item.document_description,
      item.short_description,
      item.date_filed,
      item.query,
      (item.matched_terms || []).join(" "),
      (item.value_mentions || []).join(" "),
    ]
      .join(" ")
      .toLowerCase()
      .includes(searchTerm);
  });
  const summary = legalAppraisalPayload.summary || {};
  elements.legalLeadCount.textContent = `${summary.record_count || records.length} leads`;

  elements.legalLeadList.innerHTML = records.length
    ? records.slice(0, 6).map(renderLegalLead).join("")
    : `<p class="empty-state">No legal appraisal leads match the current search.</p>`;
}

function renderLegalLead(item) {
  const description = item.document_description || item.short_description || "Public court filing lead";
  const availability = item.document_available ? "RECAP file" : "Lead only";
  const terms = (item.matched_terms || []).slice(0, 4).join(", ") || "term review";
  return `
    <article class="legal-lead-row">
      <div>
        <div class="feed-meta">
          <span>${escapeHtml(formatLabel(item.confidence || "low"))}</span>
          <span>${escapeHtml(item.date_filed || "No date")}</span>
          <span>${escapeHtml(availability)}</span>
        </div>
        <h3>${escapeHtml(description)}</h3>
        <p>${escapeHtml(terms)}</p>
      </div>
      <a class="ghost-action legal-link" href="${escapeHtml(item.source_url || "#")}" target="_blank" rel="noreferrer">Open</a>
    </article>
  `;
}

function parseCsv(text) {
  const rows = [];
  let cell = "";
  let row = [];
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (char === '"' && next === '"') {
      cell += '"';
      index += 1;
    } else if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === "," && !inQuotes) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(cell);
      if (row.some((value) => value.length)) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }

  if (cell.length || row.length) {
    row.push(cell);
    rows.push(row);
  }

  const [headers, ...records] = rows;
  return records.map((record) =>
    headers.reduce((item, header, index) => {
      item[header] = record[index] || "";
      return item;
    }, {}),
  );
}

function renderMetrics() {
  const p0Count = sources.filter((source) => source.priority === "P0").length;
  const priceCount = sources.filter((source) =>
    ["realized_price", "official_auction_result", "auction_result"].includes(source.source_class),
  ).length;
  const openCount = sources.filter((source) =>
    ["open_api", "bulk_file", "open_api_key"].includes(source.access_type),
  ).length;
  const soldCount = auctionItems.filter((item) => item.status === "sold").length;
  const auctionedCount = auctionItems.filter((item) => item.status === "auctioned").length;

  elements.metricSources.textContent = sources.length;
  elements.metricSourcesDetail.textContent = `${openCount} open API or bulk sources`;
  elements.metricP0.textContent = p0Count;
  elements.metricPrice.textContent = priceCount;
  elements.metricAuctionEvents.textContent = auctionItems.length;
  elements.metricAuctionDetail.textContent = `${soldCount} sold, ${auctionedCount} auctioned in RSS`;
}

function renderCoverage() {
  const counts = countBy(sources, "source_class");
  const max = Math.max(...Object.values(counts));
  const rows = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 7)
    .map(([sourceClass, count]) => {
      const width = Math.max(8, Math.round((count / max) * 100));
      return `
        <div class="coverage-row">
          <span>${formatLabel(sourceClass)}</span>
          <strong>${count}</strong>
          <div class="coverage-bar" aria-hidden="true"><span style="width:${width}%"></span></div>
        </div>
      `;
    })
    .join("");

  elements.coverageList.innerHTML = rows;
}

function renderAuctionFeed() {
  const items = auctionItems
    .filter((item) => {
      if (!searchTerm) return true;
      return [
        item.status,
        item.title,
        artistsLabel(item),
        item.style,
        item.auction_house,
        item.auction_date,
        item.medium,
        item.dimensions,
        item.provenance,
        item.literature,
        priceLabel(item.starting_price),
        priceLabel(item.estimated_selling_price),
        priceLabel(item.result_price),
        priceLabel(item.last_sold_price),
      ]
        .join(" ")
        .toLowerCase()
        .includes(searchTerm);
    })
    .sort((a, b) => String(b.auction_date || "").localeCompare(String(a.auction_date || "")));

  if (!items.length) {
    elements.auctionFeedBody.innerHTML = `
      <tr>
        <td class="table-empty" colspan="9">No auction feed items match the current search.</td>
      </tr>
    `;
    return;
  }

  elements.auctionFeedBody.innerHTML = items
    .map(
      (item) => `
        <tr>
          <td><span class="status-pill status-${escapeAttribute(item.status)}">${escapeHtml(formatLabel(item.status))}</span></td>
          <td>
            <strong class="auction-title">${escapeHtml(item.title || "Untitled lot")}</strong>
            <span class="auction-artist">${escapeHtml(artistsLabel(item))}</span>
            ${lotDetailsLabel(item) ? `<span class="auction-detail">${escapeHtml(lotDetailsLabel(item))}</span>` : ""}
          </td>
          <td>${escapeHtml(item.style || "Not available")}</td>
          <td>${escapeHtml(item.auction_house || "Not available")}</td>
          <td>${escapeHtml(item.auction_date || "Not available")}</td>
          <td>${escapeHtml(priceLabel(item.starting_price))}</td>
          <td>${escapeHtml(priceLabel(item.estimated_selling_price))}</td>
          <td>${escapeHtml(priceLabel(item.result_price))}</td>
          <td>${escapeHtml(priceLabel(item.last_sold_price))}</td>
        </tr>
      `,
    )
    .join("");
}

function renderNextTargets() {
  const targets = nextTargets.filter((target) => {
    if (!searchTerm) return true;
    return [
      target.source_name,
      target.priority,
      target.target_type,
      target.stage,
      target.rss_use,
      target.next_action,
    ]
      .join(" ")
      .toLowerCase()
      .includes(searchTerm);
  });

  elements.targetCount.textContent = `${targets.length} targets`;

  elements.targetList.innerHTML = targets.length
    ? targets
        .map(
          (target) => `
            <article class="target-row">
              <div>
                <div class="feed-meta">
                  <span>${escapeHtml(target.priority || "P?")}</span>
                  <span>${escapeHtml(target.stage || "Queued")}</span>
                  <span>${escapeHtml(target.target_type || "Auction source")}</span>
                </div>
                <h3>${escapeHtml(target.source_name || target.source_id)}</h3>
                <p>${escapeHtml(target.rss_use || "")}</p>
              </div>
              <strong>${escapeHtml(target.next_action || "Review source")}</strong>
            </article>
          `,
        )
        .join("")
    : `<p class="empty-state">No next targets match the current search.</p>`;
}

function renderQueue() {
  const term = searchTerm;
  const queue = sources
    .filter((source) => ["P0", "P1"].includes(source.priority))
    .filter((source) => {
      if (!term) return true;
      return [
        source.source_name,
        source.source_class,
        source.access_type,
        source.geography,
        source.notes,
      ]
        .join(" ")
        .toLowerCase()
        .includes(term);
    })
    .slice(0, 12);

  if (!queue.length) {
    elements.queueBody.innerHTML = `
      <tr>
        <td class="table-empty" colspan="4">No connector targets match the current search.</td>
      </tr>
    `;
    return;
  }

  elements.queueBody.innerHTML = queue
    .map(
      (source) => `
        <tr>
          <td>${source.source_name}</td>
          <td>${formatLabel(source.source_class)}</td>
          <td>${formatLabel(source.access_type)}</td>
          <td><span class="risk-pill priority-${source.priority.toLowerCase()}">${source.priority}</span></td>
        </tr>
      `,
    )
    .join("");
}

function renderFeed() {
  const items = feedItems
    .filter((item) => activeFilter === "all" || item.type === activeFilter)
    .filter((item) => {
      if (!searchTerm) return true;
      return [item.market, item.source, item.title, item.detail, item.type]
        .join(" ")
        .toLowerCase()
        .includes(searchTerm);
    });

  elements.feedList.innerHTML = items.length
    ? items.map(renderFeedItem).join("")
    : `<p class="empty-state">No market movements match the current filter.</p>`;
}

function renderFeedItem(item) {
  return `
    <article class="feed-item">
      <div class="feed-swatch ${item.type}">${item.type.toUpperCase().slice(0, 3)}</div>
      <div class="feed-body">
        <div class="feed-meta">
          <span>${item.market}</span>
          <span>${item.source}</span>
          <span>${item.confidence}</span>
        </div>
        <h3>${item.title}</h3>
        <p>${item.detail}</p>
      </div>
      ${renderSparkline(item.series)}
    </article>
  `;
}

function renderSparkline(series) {
  const width = 112;
  const height = 44;
  const values = series && series.length ? series : [100, 100];
  const drawable = values.length === 1 ? [values[0], values[0]] : values;
  const max = Math.max(...drawable);
  const min = Math.min(...drawable);
  const spread = max - min || 1;
  const step = width / (drawable.length - 1);
  const points = drawable.map((value, index) => {
    const x = index * step;
    const y = height - ((value - min) / spread) * (height - 8) - 4;
    return `${x},${y}`;
  });

  return `
    <svg class="sparkline" viewBox="0 0 ${width} ${height}" role="img" aria-label="Trend sparkline">
      <path d="M0 ${height - 8} H${width}"></path>
      <path d="M${points.join(" L")}"></path>
    </svg>
  `;
}

function countBy(records, key) {
  return records.reduce((counts, record) => {
    const value = record[key] || "unknown";
    counts[value] = (counts[value] || 0) + 1;
    return counts;
  }, {});
}

function artistsLabel(item) {
  return (item.artists || []).join(", ") || "Artist not available";
}

function lotDetailsLabel(item) {
  return [item.medium, item.dimensions].filter(Boolean).join(" / ");
}

function priceLabel(price) {
  return price?.display || "Not available";
}

function numberLabel(value) {
  if (value === null || value === undefined || value === "") return "N/A";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function moneyNumberLabel(value) {
  if (value === null || value === undefined || value === "") return "N/A";
  return `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function ratioLabel(value) {
  if (value === null || value === undefined || value === "") return "N/A";
  return `${Number(value).toFixed(2)}x`;
}

function formatLabel(value = "") {
  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace(/\bApi\b/g, "API");
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttribute(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9_-]/g, "");
}
