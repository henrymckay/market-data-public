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
    response: `[{"ticker": "AAPL", "slug": "aapl", "name": "Apple", "asset_class": "stock", "bar_count": 11575, "return_1d": 0.0121, "spark": [236.1, 239.1], "…": "…"}]`,
  },
  {
    path: "/api/runs",
    summary: "The last 90 runs, newest first.",
    response: `[{"source": "yahoo", "outcome": "stored", "rows": 833631, "ended": "2026-11-18T02:19:41Z", "…": "…"}]`,
  },
  {
    path: "/api/bars/{slug}",
    summary: "One instrument's whole history, oldest first, as columns. The slug is the ticker lower-cased without ^, = and . (gspc, eurusdx).",
    response: `{"ticker": "^GSPC", "day": ["1927-12-30", "…"], "open": [17.66], "high": [17.66], "low": [17.66], "close": [17.66], "adj_close": [17.66], "volume": [0], "dividend": [0], "split": [0]}`,
  },
];

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
<style>${STYLE}</style>
</head>
<body>
<main>
  <h1>Market data API</h1>
  <p class="muted">Daily prices for about ninety instruments, read live from MotherDuck through a cache that trails the store by at most fifteen minutes. Read-only, public data, no key.</p>
  ${sections}
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
