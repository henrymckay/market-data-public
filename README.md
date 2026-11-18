# market-data-public

A nightly job that fetches daily prices for about ninety instruments from Yahoo Finance with `yfinance`, stores them in MotherDuck, and shows them on a dashboard that reads the store live through a small API; a throwaway end-to-end test.

**Live dashboard: <https://henrymckay.github.io/market-data-public/>**
**Live API: <https://market-data-api.henrymckay.workers.dev/>** (its docs page)

![The Markets screen: five headline tiles, a sector treemap, leaders and laggards, and the table of every instrument](docs/screenshot.png)

## Run it

Python 3.14 and `uv` are needed.
The MotherDuck token goes from the macOS keychain into the one command's environment, never into a file:

```bash
uv sync
motherduck_token="$(security find-generic-password -a "$USER" -s motherduck-token -w)" \
  uv run market-data-cli nightly --log-level info
```

A path in `MARKET_DATA_DATABASE` runs everything against a local DuckDB file and needs no token:

```bash
MARKET_DATA_DATABASE=/tmp/market.duckdb uv run market-data-cli fetch AAPL MSFT
```

- `nightly` fetches every active instrument in the universe (`src/market_data/data/transform/universe.csv`).
- `fetch TICKER...` fetches only those instruments.
- `compute` recomputes every metric from the stored bars; `nightly` runs `fetch`, then `compute`, on one connection.
- `status` shows `key,value` rows (last run, outcome, age in hours, failed items, instruments with no bars, stale) and exits 1 when a source's last run did not store or the last stored `yahoo` run is over two days old.
- `fetch`, `compute` and `nightly` print the manifest rows as CSV with one header, one row per stage; logs, including each failed instrument by name, go to standard error.
- Exit codes: 0 every instrument stored, 1 any `partial` or `failed`, 2 a usage or configuration error such as a missing token.

`.github/workflows/nightly.yml` runs at 02:17 UTC every day and on demand.
Its `nightly` job runs `nightly`, then `status`, and holds the repository secret `MOTHERDUCK_TOKEN` (as `motherduck_token`).
Its `warm` job holds no secret: it waits up to 20 minutes for `/api/latest` to reach the run, then requests `/api/overview`, `/api/runs` and every `/api/bars/{slug}` so no visitor waits on a cache miss, and fails on any status but 200.
`.github/workflows/site.yml` builds `web/` and publishes it to GitHub Pages on a push to `main` that touches `web/`, with `VITE_API_URL` from the repository variable `API_URL`.
`.github/workflows/api.yml` tests the Worker on every push touching `api/` and deploys it from `main` with the repository secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` and `MOTHERDUCK_API_TOKEN` (the read-only service account's token, uploaded as the Worker secret `MOTHERDUCK_TOKEN`).
`.github/workflows/verify-secrets.yml`, run by hand, counts each token in every run log, the published site and a `wrangler tail` session, and prints only the counts.

Run it by hand with `gh workflow run nightly.yml --ref main`.

Every night replaces each answering instrument's whole history, so a re-run is safe and leaves the same rows.

## Dashboard

A Vite, React and TypeScript app in `web/`; Node comes from `nodejs-wheel` through `uv`, so none is needed on the system.

The page fetches JSON from the API named by `VITE_API_URL` when it is built, so run the API first (below), then:

```bash
uv sync
uv run npm --prefix web ci
VITE_API_URL=http://127.0.0.1:8787 uv run npm --prefix web run build
uv run npm --prefix web run preview    # http://127.0.0.1:4173/
```

The API only answers pages from the origin in its `ALLOWED_ORIGIN`; for the preview, start it with `-- --var ALLOWED_ORIGIN:http://127.0.0.1:4173` after `npm run dev`.
A slow API shows a "still loading" note and a failed one an error with a retry; the rest of the page keeps working.

Four screens: Markets, Ticker, Compare and Runs; every view is a link (`?view=ticker&t=AAPL&range=5Y`), `/` opens the search, and the page follows the system's light or dark scheme.

## API

`api/` is a Cloudflare Worker, <https://market-data-api.henrymckay.workers.dev/>, that answers the dashboard's reads from MotherDuck through a cache (Workers KV, keyed by the last stored run, refreshed by a cron every 15 minutes).
It is read-only: its MotherDuck user is a service account that sees `market_data` only through a read-only share.
The root path is the docs page.

| Method | Path | Returns |
|---|---|---|
| GET | `/api/latest` | the last stored `yahoo` run, or `null` |
| GET | `/api/overview` | one object per instrument: identity, coverage, every metric, a 63-bar sparkline |
| GET | `/api/runs` | the last 90 runs, newest first |
| GET | `/api/bars/{slug}` | one instrument's whole history, oldest first, as columns |

```bash
curl -s https://market-data-api.henrymckay.workers.dev/api/latest
```

```json
{"day":"2026-11-17","ended":"2026-11-18T06:39:02Z","outcome":"stored","rows":833631}
```

An unknown slug is `404` with `{"error": "...", "code": "not_found"}`; MotherDuck being unreachable is `503` with `Retry-After`.
Only the dashboard's origin gets CORS headers.

Run it locally against the store, the token going from the keychain into that one process and nowhere else:

```bash
cd api && uv run npm ci
CLOUDFLARE_INCLUDE_PROCESS_ENV=true MOTHERDUCK_TOKEN="$(security find-generic-password -a "$USER" -s motherduck-token -w)" uv run npm run dev   # http://127.0.0.1:8787/
```

`compute` writes the `overview` table the Worker reads, so run it (or `nightly`) once before the first request.

## Develop

```bash
uv run pytest
uv run ruff check && uv run ruff format --check
uv run pyright
uv run pytest -m real   # one run against Yahoo itself
uv run npm --prefix web run typecheck && uv run npm --prefix web run lint && uv run npm --prefix web test
uv run npm --prefix api run typecheck && uv run npm --prefix api run lint && uv run npm --prefix api test
VITE_API_URL=http://127.0.0.1:8788 uv run npm --prefix web run build   # the smokes' stub API listens on 8788
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" uv run pytest -m slow   # browser smokes over web/dist
```

## Query the store

The data sits in the MotherDuck database `market_data`; open it with the token in the environment (`motherduck_token="$(security find-generic-password -a "$USER" -s motherduck-token -w)" duckdb md:market_data`) and run:

How many bars and instruments are stored:

```sql
select count(*) as bars, count(distinct ticker) as tickers from bars;
```

An instrument's latest five closes:

```sql
select day, close, adj_close from bars where ticker = 'AAPL' order by day desc limit 5;
```

The ten best instruments over one month:

```sql
select ticker, value as return_1m from metrics where metric = 'return_1m' order by value desc limit 10;
```

The last five nightly runs:

```sql
select ended, source, outcome, failed_items, rows from runs order by ended desc limit 5;
```

## Tear it down

Each step is irreversible, so run them yourself when the test is over:

```bash
gh repo delete henrymckay/market-data-public --yes        # the repository, its Actions runs, the secret and the Pages site
motherduck_token="$(security find-generic-password -a "$USER" -s motherduck-token -w)" \
  duckdb md: -c "drop database market_data"               # the stored data
security delete-generic-password -a "$USER" -s motherduck-token   # the local copy of the token
```

Then revoke the token in MotherDuck's settings (Settings, Access tokens), since the repository secret held a copy of it.

The API adds its own pieces, which `gh repo delete` does not reach:

```bash
motherduck_token="$(security find-generic-password -a "$USER" -s motherduck-token -w)" \
  duckdb md: -c "drop share market_data_api"              # the read-only share
curl -X DELETE https://api.motherduck.com/v1/users/market_data_api \
  -H "Authorization: Bearer $(security find-generic-password -a "$USER" -s motherduck-token -w)"   # the service account and its token
```

- Delete the Worker `market-data-api` and the KV namespace `market-data-api-cache` in the Cloudflare dashboard (Workers & Pages), or with `npx wrangler login` and `npx wrangler delete` in `api/`.
- Revoke the Cloudflare API token under My Profile, API Tokens.
The schedule is disabled by GitHub after 60 days without repository activity, so a forgotten copy stops itself.
