# market-data-public

A nightly job that fetches daily prices for about ninety instruments from Yahoo Finance with `yfinance`, stores them in MotherDuck, and shows them on a dashboard that reads the store live through a small API; a throwaway end-to-end test.

**Live dashboard: <https://henrymckay.github.io/market-data-public/>**

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

`.github/workflows/nightly.yml` runs at 02:17 UTC every day and on demand, in one job: `nightly`, then `status`; it holds the repository secret `MOTHERDUCK_TOKEN` (as `motherduck_token`).
`.github/workflows/site.yml` builds `web/` and publishes it to GitHub Pages on a push to `main` that touches `web/`, once the repository variable `API_URL` names the API.

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

`api/` is a Cloudflare Worker that answers the dashboard's four reads (`/api/latest`, `/api/overview`, `/api/runs`, `/api/bars/{slug}`) from MotherDuck through a cache, with a docs page at `/`; it is built and tested but not deployed yet, and the dashboard on `main` still reads the files the old export published until the front end on the API is merged and deployed.
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
The schedule is disabled by GitHub after 60 days without repository activity, so a forgotten copy stops itself.
