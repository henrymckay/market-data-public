/** The docs page served at `/`: each endpoint with an example request, response and error. */

const ENDPOINTS = [
  {
    path: "/api/latest",
    summary: "The last stored nightly run, or null before any.",
    response: `{"day": "2026-11-17", "ended": "2026-11-18T02:19:41Z", "outcome": "stored", "rows": 833631}`,
  },
  {
    path: "/api/overview",
    summary: "One object per instrument: identity, coverage, every metric and a 63-bar sparkline, sorted by ticker.",
    response: `[{"ticker": "AAPL", "slug": "aapl", "name": "Apple", "asset_class": "stock", "bar_count": 11576, "return_1d": 0.0121, "spark": [236.1, 239.1], "…": "…"}]`,
  },
  {
    path: "/api/runs",
    summary: "The last 90 runs, newest first.",
    response: `[{"source": "yahoo", "outcome": "stored", "rows": 833631, "ended": "2026-11-18T02:19:41Z", "…": "…"}]`,
  },
  {
    path: "/api/bars/{slug}",
    summary: "One instrument's whole history, oldest first, as columns. The slug is the ticker lower-cased without ^, = and . (gspc, eurusdx).",
    response: `{"ticker": "^GSPC", "day": ["1927-12-30", "…"], "open": [17.66], "high": [17.66], "low": [17.66], "close": [17.66], "adj_close": [17.66], "volume": [0], "dividend": [0], "split": [0], "weekly": {"day": ["1927-12-26", "…"], "open": [17.66], "high": [17.66], "low": [17.66], "close": [17.66], "adj_close": [17.66], "volume": [0]}, "monthly": {"day": ["1927-12-01", "…"], "…": "…"}, "pivots": [{"timeframe": "d", "kind": "high", "label": "HH", "day": "2026-09-02", "price": 6712.4, "confirmed": "2026-09-09"}], "signals": [{"id": "^GSPC|d|break_up|2026-11-10", "timeframe": "d", "event": "break_up", "direction": "up", "day": "2026-11-10", "known": "2026-11-10", "level": 6650.2, "stop": 6401.9, "grade": "B", "score": 2, "return_to_date": 0.012, "held_to_date": true}]}`,
  },
  {
    path: "/api/signals",
    summary: "Signals known in the last 120 days, newest first and highest score first within a day, at most 5,000, each with its instrument's name, asset class and slug.",
    response: `[{"id": "NVDA|w|break_up|2026-11-09", "ticker": "NVDA", "name": "Nvidia", "asset_class": "stock", "slug": "nvda", "timeframe": "w", "event": "break_up", "direction": "up", "grade": "A", "score": 4, "day": "2026-11-09", "known": "2026-11-14", "level": 142.1, "stop": 128.4, "margin_atr": 0.6, "return_to_date": 0.023, "held_to_date": true, "…": "…"}]`,
  },
  {
    path: "/api/stats",
    summary: "Every base rate: per asset class, event, grade, timeframe and horizon, the hit rate beside the any-bar baseline and the edge between them.",
    response: `[{"asset_class": "all", "event": "break_up", "grade": "all", "timeframe": "d", "horizon": 20, "n": 2980, "hit_rate": 0.56, "baseline_hit": 0.565, "edge": 0.002, "held_rate": 0.71, "…": "…"}]`,
  },
];

const FIELDS = [
  ["Times", "`ended`, `started` and `fetched` are UTC, `2026-11-18T02:19:41Z`; `day` is a date, `2026-11-17`, in the instrument's own exchange calendar (crypto: UTC)."],
  ["Prices", "`open`, `high`, `low` and `close` are in the instrument's own quote unit (US dollars unless an index, rate or currency pair) and adjusted for splits only; `adj_close` is also adjusted for dividends. `/api/overview`'s `last_close` is the latest `close`."],
  ["Returns", "`return_1d` to `return_5y` are fractions (`0.0121` is +1.21%) of `adj_close`; `3y` and `5y` are annualised. `volatility_1y` is an annualised fraction and `drawdown_max_1y` a negative fraction."],
  ["Changes", "`change_1d` to `change_5y` are absolute changes in the quote unit, in percentage points for a rate (`^TNX`), and are what a rate shows instead of a return."],
  ["Ranges", "`high_52w` and `low_52w` are prices; `traded_value_20d` is the mean of close times volume over 20 bars, in the quote unit."],
  ["Structure", "`weekly` and `monthly` are the daily bars grouped by period: `day` is the period's first calendar day, and the period still running is included. A `pivots` row is a swing: `kind` `high` or `low`, `label` `HH`, `LH`, `EH`, `HL`, `LL` or `EL` (null for the first of its kind), `day` the swing's bar and `confirmed` the day a later bar proved it. A signal's `known` is the day it could first be acted on, `level` the price it turned on and `stop` the price that proves it wrong."],
  ["Base rates", "`hit_rate` is the share of a signal's forward returns that moved its way after `horizon` bars of its timeframe; `baseline_hit` is the same share over every bar; `edge` is `mean_return` less `baseline_mean`. All stored history of today's members, so survivorship flatters the long side, and the rules were set on this data."],
  ["Size", "`/api/bars/{slug}` is the whole history with its structure: about 1.9 MB for AAPL (430 KB compressed) and 3.9 MB for ^GSPC (670 KB compressed), measured 2026-11-18. `/api/signals` is about 0.9 MB (180 KB compressed) and `/api/stats` 0.6 MB (110 KB compressed). A figure an instrument has no history for is absent or null."],
] as const;

const ERRORS = `{"error": "No instrument with slug 'xyz'; see /api/overview for the list.", "code": "not_found"}`;

const STYLE = `
:root { --bg: #f6f6f3; --card: #fcfcfb; --fg: #0b0b0b; --muted: #66655f; --border: #e4e3dc; --link: #1f64b8; }
@media (prefers-color-scheme: dark) { :root { --bg: #0d0d0d; --card: #1a1a19; --fg: #f0efec; --muted: #a9a8a0; --border: #ffffff17; --link: #3987e5; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, sans-serif; }
main { max-width: 52rem; margin: 0 auto; padding: 2rem 1rem 4rem; }
h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
h2 { font-size: 1.125rem; margin: 0 0 .5rem; font-family: ui-monospace, monospace; }
p { margin: 0 0 .75rem; }
.muted { color: var(--muted); }
section { background: var(--card); border: 1px solid var(--border); border-radius: .75rem; padding: 1rem 1.25rem; margin-top: 1rem; }
pre { margin: 0 0 .75rem; padding: .75rem; border: 1px solid var(--border); border-radius: .5rem; overflow-x: auto; font: 13px/1.5 ui-monospace, monospace; white-space: pre-wrap; word-break: break-all; }
a { color: var(--link); }
`;

const escape = (text: string): string =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/** The page as HTML, for the API at `origin`. */
export function docsPage(origin: string): string {
  const sections = ENDPOINTS.map(
    ({ path, summary, response }) => `
    <section>
      <h2>GET ${escape(path)}</h2>
      <p>${escape(summary)}</p>
      <pre>curl -s ${escape(origin)}${escape(path.replace("{slug}", "gspc"))}</pre>
      <pre>${escape(response)}</pre>
    </section>`,
  ).join("");
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Market data API</title>
<meta name="description" content="Daily prices, swing structure and signals for about 680 instruments, read from MotherDuck through a cache. Read-only, public data, no key.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%232a78d6'/%3E%3Cpath d='M6 22l7-8 5 5 8-10' fill='none' stroke='%23fff' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<style>${STYLE}</style>
</head>
<body>
<main>
  <h1>Market data API</h1>
  <p class="muted">Daily prices, swing structure and signals for about 680 instruments, read live from MotherDuck through a cache that trails the store by at most fifteen minutes. Read-only, public data, no key. The signals are unbacktested rules on public data, not advice.</p>
  ${sections}
  <section>
    <h2>Fields and units</h2>
    ${FIELDS.map(([name, text]) => `<p><strong>${name}.</strong> ${escape(text).replace(/`([^`]+)`/g, "<code>$1</code>")}</p>`).join("")}
  </section>
  <section>
    <h2>Errors</h2>
    <p>Always JSON with a message and a code: 404 <code>not_found</code> for an unknown path or slug, 405 for a method other than GET, HEAD or OPTIONS, 503 <code>store_unavailable</code> with <code>Retry-After: 60</code> when MotherDuck does not answer.</p>
    <pre>${escape(ERRORS)}</pre>
  </section>
  <section>
    <h2>Caching</h2>
    <p>Every data response carries an <code>ETag</code> naming the data version, the time the last nightly run ended, and <code>Cache-Control: public, max-age=60</code>. Send the version back as <code>If-None-Match</code> for a 304, or as <code>?v=</code> to bypass a browser's copy. No endpoint takes any other parameter.</p>
  </section>
</main>
</body>
</html>`;
}
