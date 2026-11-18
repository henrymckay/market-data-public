# market-data-public

Unsigned plan, written 2026-11-17 in autonomous mode for the owner's request, relayed by the planning session; every decision is *(proposed)* or *(by precedent)* until the owner reviews it.
The owner pre-approved exactly these outward steps, so the milestones include them: creating the public GitHub repository `market-data-public` under `henrymckay`, pushing to it, deploying to free hosting tiers that need no card, and using the owner's MotherDuck token.
Extended 2026-11-18 in autonomous mode for the owner's live-read request, relayed by the planning session: R9 and R10 are the owner's signed words; D51 to D65, A15 to A20, Q4 to Q6, I11 to I15 and M5 to M7 are new and unsigned; D3, D16, D17, D43 and D45 are superseded and D7, D39 and D47 narrowed by them.

A nightly cloud job that fetches daily prices for about ninety instruments with `yfinance` and stores them in MotherDuck, and a fast market dashboard that reads that store live through a small API, for the owner as a throwaway end-to-end test.

## Brief

### Goal

The owner wants to see a market-data pipeline and dashboard run end to end in the cloud at no cost, with nothing on their own machine.
Done is observable: a scheduled GitHub Actions run, fired with the owner's machine off, has loaded last night's bars into MotherDuck, and the public Pages URL shows them on a dashboard that passes the design bar and its speed budget.

### Terms

- **Instrument** — one thing with a price series, named by its Yahoo symbol (`AAPL`, `^GSPC`, `EURUSD=X`, `BTC-USD`); code calls its symbol `ticker`.
- **Universe** — the curated list of instruments the job fetches, with each one's name, asset class and sector.
- **Asset class** — one of `index`, `etf`, `stock`, `rate`, `fx`, `commodity`, `crypto`.
- **Quote type** — `price` for everything but rates, `yield` for rates (`^TNX`), whose moves are shown as changes in percentage points, never as returns.
- **Bar** — one instrument's open, high, low, close, adjusted close and volume for one day.
- **Day** — the trading date of a bar in the instrument's own exchange calendar, as Yahoo dates it; crypto days are UTC days.
- **Complete bar** — a bar whose day is before the run's UTC date; a bar for today is still forming and is never stored.
- **Close** — the closing price adjusted for splits only, as quoted; **adjusted close** is also adjusted for dividends and is what every return is computed from.
- **Return** — the relative change of adjusted close over a window; **change** is the absolute change, used for yields.
- **Window** — `1d`, `1w`, `1m`, `3m`, `ytd`, `1y`, `3y`, `5y`, each measured from the last bar at or before the window's start.
- **Drawdown** — the fall of adjusted close from its running peak, as a negative percentage.
- **Run** — one execution of a stage, recorded as one manifest row.
- **Metric** — one derived figure for one instrument as of its last complete bar, stored long.
- **Site data** — the files the export stage wrote for the dashboard to read until R9; replaced by the API's responses (D59).
- **API** — the Cloudflare Worker that holds the MotherDuck token and answers the dashboard's four reads with fixed queries (D51).
- **Data version** — the `ended` of the last stored `yahoo` run the API has seen; it keys the API's cache and the page's refetch (D53).

### Requirements

- **R1** Fetch daily prices with `yfinance` every night.
  - Cost: a scheduled job, its pacing against Yahoo's unpublished rate limit, and a manifest so a missed night shows; dropping "every night" for on-demand runs saves the schedule and the status check.
- **R2** Without my machine being on.
  - Cost: a hosted scheduler (GitHub Actions), a repository secret and a public repository to run free; dropping it would let a launchd job on the laptop do the work.
- **R3** Store them in MotherDuck.
  - Cost: an outside service, its token on the runner and a client pinned to the DuckDB versions MotherDuck accepts, which holds Python at 3.14 (D5).
- **R4** A slick, fast, impressive dashboard on the web.
  - Cost: a built front end (Node via `nodejs-wheel`, React, two chart libraries), four designed screens and a scored design gate.
  Measured as: `design-interface`'s ten criteria pass on screenshots; on the live site from a cold cache the Markets screen is ready within 1.5 s and transfers at most 800 KB compressed; a period, range or sort control answers within 200 ms; switching instrument draws within 500 ms.
- **R5** The dashboard reads its data from MotherDuck.
  - Cost: since R9, through the API (D51), which holds the token so no page does.
- **R6** Deploy it end to end at no running cost.
  - Cost: free tiers only — a public repository for free Actions and Pages, MotherDuck Lite — and a usage figure logged so the free quota is watched.
- **R7** This is a throwaway test that will be deleted at the end, so Yahoo's terms and redistributing the data are not a concern.
  - Cost: none; it is what lets the data sit in a public repository's logs and a public site (D18).
- **R8** The MotherDuck token is never printed, logged, committed or written to a file in the repository; it is piped straight to where it is needed (from the planning brief).
  - Cost: the keychain locally, a repository secret on Actions, a secret scan on every commit and a count of the token in logs and site at the end.
- **R9** "Ideally deployment means the dashboard reads live from MotherDuck, not from files exported each night. I asked for the dashboard to read its data from MotherDuck. Make it a live read through a small API that holds the token" (the owner, 2026-11-18; overrides D3).
  - Cost: a second host and account (Cloudflare) the owner signs in to once, a TypeScript Worker with its own toolchain, tests and deploy workflow, a second MotherDuck token held by a third party, a cache so page views do not become MotherDuck compute, and the page up to 15 minutes behind the store (D53, Q6); dropping it keeps the nightly export, which is built and live.
- **R10** "On a free host that needs no card" (the owner, 2026-11-18).
  - Cost: rules out Cloud Run, Koyeb and Hugging Face's Docker Spaces, and holds the API inside Cloudflare's free limits — 100,000 requests a day, 10 ms of CPU a request, 1,000 KV writes a day (D51).

### Not yet

- **Alerts** — a push or mail on failure; earned by a missed outage (`run-unattended`, Report the outcome).
- **A larger universe** — the S&P 500 or more; earned by the owner asking, since it multiplies requests against Yahoo's limit (I2).
- **Intraday prices** — earned by a requirement for them; daily bars are what was asked.
- **Fundamentals and market caps** — earned by the heatmap needing true weights (I3).
- **A general API** — a `/v1/` prefix, date-range or filter parameters, or SQL from the caller; earned by a second client (`write-entry-points`, HTTP surface), since each parameter multiplies the cache keys D55 bounds.
- **Access control on the site** — earned by data that is not public.

## Design

### Inputs

- **Yahoo Finance through `yfinance` 1.8** — one `Ticker.history(period="max", interval="1d", auto_adjust=False, actions=True)` request per instrument, returning a pandas frame indexed by an exchange-local midnight timestamp with `Open`, `High`, `Low`, `Close`, `Adj Close`, `Volume`, `Dividends`, `Stock Splits` (and `Capital Gains` for funds, dropped).
  Probed 2026-11-17: `^GSPC` 24,837 bars from 1927-12-30, `AAPL` 11,575, `SPY` 8,508, `EURUSD=X` 5,958, `BTC-USD` 4,445; about 1 s a request after an 8 s first one; FX, futures and crypto already carry a forming bar for today.
  About 90 requests a night, roughly 800,000 bars in all.
  No credential; Yahoo's limit is unpublished and its blocks reported to last hours, so the source is untrusted for availability, and values are revised when splits and dividends land.
  Class: public, by the owner's statement (R7, D18).
- **The universe** — `src/market_data/data/transform/universe.csv`, columns `ticker,name,asset_class,sector,quote_type,active`, about 90 rows (D8, A6); class public.
- **The MotherDuck token** — the owner's access token, in the macOS keychain under service `motherduck-token`, and on Actions the repository secret `MOTHERDUCK_TOKEN`, read into the environment as `motherduck_token` (`store-data`); a secret for an account that can bill by use, so `secure-project`'s money rules apply (one consumer, keychain, rotation dated in Runs on).
- **The API's MotherDuck token** — a second token, for the API alone (D57): a service account's, reading `market_data` through a read-only share once Q4 is answered; the repository secret `MOTHERDUCK_API_TOKEN`, copied by the deploy job into the Worker secret `MOTHERDUCK_TOKEN`; read-write at the account level, since Lite offers no read-only token (A16).
- **MotherDuck's Postgres endpoint** — `pg.eu-west-1-aws.motherduck.com:5432` (the account's region, from `md_user_info()` 2026-11-18), user `postgres`, the token as password, TLS required, DuckDB SQL with `$1` binding; labelled preview (A20).
  Probed live 2026-11-18 with `psycopg` 3 and the keychain token: connect 1.2–1.7 s; a parameterised year of `AAPL` bars, 252 rows, 0.35–0.70 s; all 1,958 `metrics` rows 0.29 s; `^GSPC`'s 24,838 bars as rows 8.7–9.3 s, as one columnar JSON string (2.9 MB, 488 KB gzipped) 2.5–12.4 s, timed from the planning machine, far from `eu-west-1`.

### Data flow

1. **Universe** — one row is an instrument, keyed by `ticker`; the active rows become the list to fetch and the `tickers` table.
2. **Fetched** — one row is a bar, keyed by `ticker` and `day`; the Yahoo adapter maps each instrument's frame into `port.BARS` with `polars.from_pandas`, dates each bar by its index's local date, and returns a `Fetched` record of bars, rejected rows and failed instruments. (IO)
3. **Complete and valid** — the same grain; the core drops bars on or after the run's UTC date (D9) and splits the rest into valid bars and rejected rows with a reason: a null or non-finite close, a non-positive price on a `price` instrument, high below low, a duplicate day.
4. **Stored** — the same grain in MotherDuck; for each instrument that answered, its rows in `bars` and `rejected` are replaced in one transaction, instruments that failed keep last night's rows, and a `runs` row is appended. (IO)
5. **Metrics** — one row is one metric for one instrument, keyed by `ticker` and `metric`; the core computes every window's return and change, the 52-week high and low, 1-year volatility, 1-year maximum drawdown and 20-day traded value from `bars` read back from the store, and the store replaces `metrics` whole. (IO at both ends)
6. **Overview** — one row per instrument, keyed by `ticker`; in the same `compute` stage the core pivots the metrics beside the instrument's identity, coverage and a 63-bar adjusted-close sparkline (`transform/site.py`, unchanged), and the store replaces `overview` whole (D54). (IO)
7. **API responses** — on a request whose response is not cached for the current data version, the Worker runs that endpoint's fixed query on MotherDuck, which returns the whole JSON body as one string, and caches it in KV under the version (D52, D53); a cron every 15 minutes reads the latest stored run to move the version. (IO)
8. **Screens** — `web/src/lib/data.ts` fetches the API's JSON into the same `Instrument`, `Run`, `Series` and `Latest` shapes the Parquet gave; range-dependent figures (a chosen range's return, drawdown, correlations) are computed in `web/src/lib/` from the bars, and every figure the overview already holds is read from it, never recomputed (`write-sql`, Never compute one result both ways).

### Outputs

**MotherDuck database `market_data`** — written by the nightly job, read by the API and by the owner at a SQL prompt; tables created by numbered migrations under `src/market_data/data/adapt/migrations/` (D19); `bars`, `rejected` per instrument replaced, `metrics`, `overview` and `tickers` replaced whole, `runs` append-only; class public.

`bars`, key `(ticker, day)`:

| column | type | meaning |
|---|---|---|
| adj_close | double | close adjusted for splits and dividends |
| close | double | close adjusted for splits |
| day | date | trading date; key |
| dividend | double | cash dividend going ex on this day, 0 if none |
| fetched | timestamp with time zone | start of the run that stored it, UTC |
| high | double | split-adjusted high |
| low | double | split-adjusted low |
| open | double | split-adjusted open |
| split | double | split ratio effective this day, 0 if none |
| ticker | varchar | instrument; key |
| volume | bigint | shares or units traded, null where Yahoo reports none (indices' early years, FX) |

`metrics`, key `(ticker, metric)`:

| column | type | meaning |
|---|---|---|
| day | date | the instrument's last complete bar the figure is as of |
| metric | varchar | `return_1d` … `return_5y`, `change_1d` … `change_5y`, `high_52w`, `low_52w`, `volatility_1y`, `drawdown_max_1y`, `traded_value_20d`, `last_close`; key |
| ticker | varchar | key |
| value | double | the figure; returns as fractions, `3y` and `5y` annualised |

`runs`, one row per stage per run (`store-data`, Keep what the source sent):

| column | type | meaning |
|---|---|---|
| day | date | the last complete UTC day the run targeted |
| ended | timestamp with time zone | UTC |
| failed_items | integer | instruments that answered nothing usable |
| last_day | date | equal to `day` |
| outcome | varchar | `stored`, `partial` or `failed` |
| rejected | integer | rows quarantined |
| requests | integer | requests sent to Yahoo, retries included |
| rows | bigint | bars stored |
| source | varchar | `yahoo`, or `metrics` for the compute stage |
| started | timestamp with time zone | UTC |

`rejected` has `day`, `fetched`, `reason`, `record` (the row as JSON text, or the instrument's name where nothing arrived) and `ticker`; `tickers` mirrors the universe CSV; `schema_version` holds the last migration applied.

`overview`, key `ticker`, created by migration `0003_create_overview.sql`, columns in alphabetical order: the `tickers` columns, `bar_count` (bigint), `first_day` and `last_day` (date), `rejected` (bigint), `slug` (varchar), `spark` (`double[]`, the last 63 adjusted closes) and one `double` column per metric D33 defines (`return_1d` … `last_close`), null where the instrument has none; the columns `overview.parquet` carried (D39), so the page's `toInstrument` reads it unchanged.

**API responses** — JSON built by DuckDB on MotherDuck, cached in the Workers KV namespace `market-data-cache` under `<data version>/<endpoint>` with a three-day expiry, served by the Worker (Interface); class public.

**Site data** — *(retired by D59 in M6)* written by `export` into `web/public/data/` on the runner, built into the Pages site, never committed; Parquet with snappy compression (D17); class public.

- `overview.parquet` — one row per instrument: the `tickers` columns, every metric as its own column, and `spark` (list of 63 doubles); about 60 KB.
- `bars/<slug>.parquet` — one file per instrument (`slug` is the ticker lower-cased with `^`, `=` and `.` removed: `gspc`, `eurusdx`), every column of `bars` but `ticker` and `fetched`; 50 to 600 KB each, about 20 MB in all.
- `runs.parquet` — the last 90 runs.
- `latest.json` — the last `yahoo` run's row, polled by the open page.

**GitHub Pages site** — `https://henrymckay.github.io/market-data-public/`, replaced by each deploy of the front end (D58), holding code and no data once M7 lands; class public.

### Interface

The package is `market_data` under `src/`, laid out as `structure-python` says: `transform`, `port`, `operate`, `error` in the core; `adapt/yahoo.py`, `adapt/motherduck.py` (both store ports over a DuckDB connection string), `adapt/site.py` (the export's file writer) at the edge; `drive/` holding the `typer` CLI and the composition root.
Per-source constants (pace, retries, `tolerance`) live in `data/adapt/yahoo.yaml`.

```bash
uv run market-data-cli nightly --log-level info
uv run market-data-cli fetch AAPL MSFT
uv run market-data-cli compute
uv run market-data-cli status
```

- `nightly` runs `fetch` for every active instrument, then `compute`, which also replaces `overview` (D54); standard output carries one CSV manifest row per stage:

```text
day,ended,failed_items,last_day,outcome,rejected,requests,rows,source,started
2026-11-16,2026-11-17T02:19:41Z,0,2026-11-16,stored,2,90,803114,yahoo,2026-11-17T02:17:22Z
2026-11-16,2026-11-17T02:20:03Z,0,2026-11-16,stored,0,0,1513,metrics,2026-11-17T02:19:42Z
```

- `export` is removed in M6 (D59).
- `status` emits `key,value` rows — last run, its outcome, its age in hours, failed instruments — and exits 1 when the last stored `yahoo` run is more than two days old or the last run was not `stored`.
- Logs go to standard error, `warning` by default, `info` under the scheduler; the composition root logs the seconds spent connected to MotherDuck at `info` (R6).
- Exit codes are `run-unattended`'s: 0 every instrument stored, 1 any `partial` or `failed`, 2 a usage or configuration error (no token, a bad option, MotherDuck refusing the token).
- `MARKET_DATA_DATABASE` names the store, default `md:market_data`; a path such as `/tmp/market.duckdb` runs every command against a local DuckDB file with no token, which the tests and a dry run use.
- Locally the token goes from the keychain straight into the one command's environment, never into a file or the shell history: `motherduck_token="$(security find-generic-password -a "$USER" -s motherduck-token -w)" uv run market-data-cli nightly`.
- The schedule is `17 2 * * *` UTC, every day (D12).

**The API** is a Cloudflare Worker in `api/` named `market-data-api`, served at `https://market-data-api.<subdomain>.workers.dev` (the subdomain is the owner's account's, known at M7), read-only, with four data endpoints and a docs page (D51, D55):

| method | path | returns |
|---|---|---|
| GET | `/api/latest` | the last stored `yahoo` run, `{"day": "2026-11-17", "ended": "2026-11-18T02:19:41Z", "outcome": "stored", "rows": 833631}`, or `null` before any; `Cache-Control: public, max-age=60` |
| GET | `/api/overview` | an array of one object per instrument with the `overview` table's columns (Outputs), sorted by `ticker`; about 90 objects, 181 KB measured 2026-11-18 |
| GET | `/api/runs` | an array of the last 90 `runs` rows, newest first, with the `runs` table's columns, times as `2026-11-18T02:19:41Z` |
| GET | `/api/bars/{slug}` | one instrument's whole history, oldest first, as columns: `{"ticker": "^GSPC", "day": ["1927-12-30", …], "open": […], "high": […], "low": […], "close": […], "adj_close": […], "volume": […], "dividend": […], "split": […]}`; `slug` must be one of `/api/overview`'s, else 404; at most 2.9 MB, 490 KB compressed (`^GSPC`) |
| GET | `/` | the docs page: each endpoint with an example request, response and error (D64) |

- Each data endpoint takes one optional parameter, `v`, the data version the page last saw, used only to bust the browser's cache; every other parameter is ignored, and no endpoint takes a date range, a filter or SQL (D55).
- Every data response carries `ETag: "<data version>"`, `Cache-Control: public, max-age=60` (the page's poll refetches with `?v=` when the version moves), `Content-Type: application/json` and, for an `Origin` of `https://henrymckay.github.io`, `Access-Control-Allow-Origin` with `Vary: Origin` (D56); an `If-None-Match` equal to the version is answered `304` from KV alone.
- Errors are JSON, `{"error": "<what failed and what to do>", "code": "<code>"}`, with the statuses Errors lists.
- The cron (`*/15 * * * *`) runs `latest.sql`, and when its `ended` differs from the stored version writes the new version to KV and fills `overview` and `runs` under it.
- The four queries live as `api/src/queries/{latest,overview,runs,bars}.sql`, each returning one row with one `varchar` column `body` (D52).
- Logs are one line a request (path, status, cache hit or miss, milliseconds, no query text or token) through `console.log`, read with `wrangler tail`.

```bash
curl -s https://market-data-api.<subdomain>.workers.dev/api/latest
cd api && CLOUDFLARE_INCLUDE_PROCESS_ENV=true MOTHERDUCK_TOKEN="$(security find-generic-password -a "$USER" -s motherduck-token -w)" uv run npm run dev
```

The second line runs the Worker locally (`wrangler dev`, `http://127.0.0.1:8787`) against live MotherDuck with the token only in that process's environment, never in `.dev.vars` (R8); `wrangler.toml`'s `secrets.required` lists `MOTHERDUCK_TOKEN` so no other variable of the shell becomes a binding.

**The dashboard** is a Vite, React and TypeScript app in `web/`, styled from the house tokens with Tailwind and shadcn/ui, candles in Lightweight Charts 5, every other chart in ECharts 6, its data fetched as JSON from the API named by the build-time `VITE_API_URL` (D4, D58).
Best in class here means a TradingView or Koyfin-grade finish over a cached edge API: answer first, every number tabular and formatted, light and dark, usable at 390 px, every control instant because the data is already in the browser once fetched.
Shared across screens: a 56 px header with the name, the four screens as tabs (`data-view`), a ticker search opened by `/` or Cmd/Ctrl+K (shadcn `command`), the data-age chip ("Prices to 16 Nov 2026 · run 7 h ago", warning when stale, critical when the last run failed) and the scheme toggle; the screen and its choices live in the query string (`?view=ticker&t=AAPL&range=1y`) so every view is a shareable link; `data-ready` on the root as `write-entry-points` says.
The page polls `/api/latest` every 5 minutes and refetches with `?v=<ended>` when its `ended` changes, and re-judges the age every minute.
Each screen below names the endpoint it reads; until M6 lands it read the matching file (`overview.parquet`, `bars/<slug>.parquet`, `runs.parquet`, `latest.json`).

- **Markets** (default) — "What did markets do over this period?"
  - A period toggle (`1D 1W 1M 3M YTD 1Y`) drives every element.
  - Five tiles: S&P 500, Nasdaq 100, US 10-year yield, gold, Bitcoin — last value, the period's return (change in basis points for the yield), a sparkline, the day in the context line.
  - A treemap of the stocks grouped by sector, each tile sized by 20-day traded value and coloured on the diverging blue–red scale through `sunken`, clamped at a period-scaled bound, ticker and return labelled where they fit; click opens Ticker.
  - Leaders and laggards: a horizontal bar chart of the ten best and ten worst instruments over the period, `up` and `down` coloured, direct labels.
  - All instruments: a sortable table filtered by asset-class chips — ticker, name, last, the six windows, a 52-week range bar with the last close marked, the 63-bar sparkline — numbers right-aligned and signed, newest bar's day in the header.
  - Every sparkline is an inline SVG path, never a chart instance, so ninety rows cost nothing to draw.
  - All from `/api/overview`.
- **Ticker** — "How has this instrument behaved, and how does it stand now?"
  - Range toggle `1M 3M 6M YTD 1Y 5Y Max`, overlay toggles for 50- and 200-day moving averages, a log-scale toggle.
  - Tiles: last close with the day's change, the range's return, position in the 52-week range, 1-year volatility, the range's maximum drawdown.
  - Candles with volume in a second pane, dividend and split markers on the bars, crosshair legend showing the bar under the cursor.
  - Below, side by side: an underwater drawdown area chart over the range, and a monthly-returns calendar heatmap (years down, months across, a year column) for the whole history.
  - From `/api/bars/<slug>`, fetched on selection and cached for the session; header figures from `/api/overview`.
- **Compare** — "How have these moved against each other?"
  - Up to six instruments as removable chips, added from the search; range toggle as on Ticker.
  - Each series rebased to 100 at the range's first common day, in the palette's order, direct end labels.
  - A stats table: total return, annualised return, annualised volatility, return over volatility, maximum drawdown.
  - A correlation matrix of daily returns over the range, diverging scale, values printed in cells.
  - From the same per-instrument files.
- **Runs** — "Is the data fresh and complete?"
  - Tiles: last run's outcome (status chip with label), bars stored, rows rejected, failed instruments.
  - A table of the last 90 runs, newest first.
  - Coverage: per instrument its first day, last day, bar count and rejected rows, so a gap or a dead symbol shows.
  - From `/api/runs` and `/api/overview`.

States for every screen: loading is a skeleton in each card's shape at fixed height; empty reads "No runs yet — the first nightly writes here" (Runs) or "No bars stored for AAPL yet" (Ticker); stale and failed show in the header chip with icon and text; an error is a note inside the card that failed ("Couldn't load EURUSD=X's prices. Other screens still work; try again in a minute.") with the rest of the page working.

Markets at desktop width:

```text
+--------------------------------------------------------------------------------------------+
| Market data  [Markets] Ticker  Compare  Runs    [Search  /]   Prices to 16 Nov 2026 . 7 h ago  (Dark) |
+--------------------------------------------------------------------------------------------+
| Period  [1D] 1W  1M  3M  YTD  1Y                                                           |
| +----------------+ +----------------+ +----------------+ +----------------+ +----------------+ |
| | S&P 500        | | Nasdaq 100     | | US 10Y yield   | | Gold           | | Bitcoin        | |
| | 6,712.40       | | 24,310.15      | | 4.21%          | | 2,694.10       | | 91.2K          | |
| | +0.84%  ~~~/~  | | +1.10%  ~~/~~  | | -3 bp   ~\~~~  | | +0.40%  ~~~~/  | | +2.31%  _/~~~  | |
| +----------------+ +----------------+ +----------------+ +----------------+ +----------------+ |
| +--------------------------------------------------------+ +-------------------------------+ |
| | Stocks by sector, return over 1D (%)                   | | Leaders and laggards, 1D (%)  | |
| | +----------------------+---------------+-------------+ | | NVDA   ##########  +4.21      | |
| | | Technology           | Financials    | Health      | | | AMD    ########    +3.40      | |
| | |  AAPL +1.2 | MSFT    | JPM  | V      | LLY  | UNH  | | | ...                           | |
| | |  NVDA +4.2 | AVGO    | BAC  | MA     | JNJ  | PFE  | | | BA       ######    -2.75      | |
| | +----------------------+---------------+-------------+ | | INTC   ########    -3.12      | |
| +--------------------------------------------------------+ +-------------------------------+ |
| +----------------------------------------------------------------------------------------+ |
| | All instruments    [All] Indices ETFs Stocks Rates FX Commodities Crypto               | |
| | Ticker  Name          Last       1D      1W      1M      YTD      1Y    52w range  3M  | |
| | ^GSPC   S&P 500    6,712.40   +0.84%  +1.92%  +3.05%  +14.20%  +18.33%  |---o-|   ~~/ | |
| | AAPL    Apple        239.12   +1.20%  ...                                             | |
| +----------------------------------------------------------------------------------------+ |
+--------------------------------------------------------------------------------------------+
```

Markets at phone width (390 px):

```text
+------------------------------------+
| Market data        [/]  7 h ago (D)|
| [Markets] Ticker Compare Runs      |
| Period [1D] 1W 1M 3M YTD 1Y        |
| +---------------+ +---------------+|
| | S&P 500       | | Nasdaq 100    ||
| | 6,712.40      | | 24,310.15     ||
| | +0.84%   ~~/~ | | +1.10%  ~~/~~ ||
| +---------------+ +---------------+|
| +---------------+ +---------------+|
| | US 10Y yield  | | Gold          ||
| +---------------+ +---------------+|
| +---------------+                  |
| | Bitcoin       |                  |
| +---------------+                  |
| +--------------------------------+ |
| | Stocks by sector, 1D (%)       | |
| | [treemap, 320 px tall]         | |
| +--------------------------------+ |
| | Leaders and laggards           | |
| +--------------------------------+ |
| | All instruments  (scrolls ->)  | |
| +--------------------------------+ |
+------------------------------------+
```

Read against `design-interface`'s Defaults to avoid: no animation on data updates, no all-caps labels, no shadowed cards, no gradient, no pie, no second y axis (volume has its own pane), up blue and down red.

### Runs on

- **Pipeline and export** — GitHub Actions in the public repository `henrymckay/market-data-public`, free for public repositories; one workflow `.github/workflows/nightly.yml` from `deploy-project`'s `references/github-actions.md`, with jobs `nightly` (fetch, compute, export, upload the site data as an artifact), `site` (build with `nodejs-wheel`'s `npm`, upload the Pages artifact) and `deploy`; `timeout-minutes: 30`, `concurrency: group: data` without cancelling.
  Limit that matters: a public repository's schedule is disabled after 60 days without repository activity (GitHub docs, read 2026-11-17; A3).
  Secret: `MOTHERDUCK_TOKEN`, set with `security find-generic-password -a "$USER" -s motherduck-token -w | gh secret set MOTHERDUCK_TOKEN --repo henrymckay/market-data-public`, exposed to the `nightly` job's run steps only (D7); rotate at teardown or by 2027-02-15, whichever comes first.
  From M7 the `nightly` job drops `export` and the site-data artifact, and a `warm` job with no secret follows it (D60).
- **Store** — MotherDuck Lite: 10 GB storage and 10 CU-hours a month included, no card required, usage past them pay-as-you-go (motherduck.com pricing page and docs, read 2026-11-17; A4); the store needs well under 1 GB.
- **Dashboard** — GitHub Pages from the same workflow through `actions/upload-pages-artifact` and `actions/deploy-pages`, Pages enabled once with GitHub Actions as the source (`gh api -X POST repos/henrymckay/market-data-public/pages -f build_type=workflow`); limits 1 GB a site, 100 GB a month of traffic (soft), 10 builds an hour (GitHub docs, read 2026-11-17).
  From M7 the `site` and `deploy` jobs move to `.github/workflows/site.yml`, run on a push to `main` touching `web/**` and on dispatch, with `VITE_API_URL` from the repository variable `API_URL` (public, not a secret); the nightly no longer builds the site (D58, D59).
- **API** — Cloudflare Workers Free (no card): 100,000 requests a day (Error 1027 past it, reset 00:00 UTC), 10 ms of CPU a request and a cron invocation, 50 subrequests a request, 6 open connections, 128 MB, 5 cron triggers an account (developers.cloudflare.com, Workers limits, read 2026-11-18); KV Free: 100,000 reads, 1,000 writes and 1,000 deletes a day, 1 GB (KV pricing, read 2026-11-18).
  Deployed by `.github/workflows/api.yml` on a push to `main` touching `api/**` and on dispatch, through `cloudflare/wrangler-action` v4.1.3 pinned to its commit SHA (released 2026-09-24), with the repository secrets `CLOUDFLARE_API_TOKEN` (the owner's, template "Edit Cloudflare Workers", scoped to their one account) and `CLOUDFLARE_ACCOUNT_ID`; the deploy job pipes `MOTHERDUCK_API_TOKEN` from its environment into `wrangler secret put MOTHERDUCK_TOKEN` (D61).
  `wrangler.toml`: `compatibility_date = "2026-11-18"`, `compatibility_flags = ["nodejs_compat"]`, `[vars]` `MOTHERDUCK_HOST = "pg.eu-west-1-aws.motherduck.com"`, `MOTHERDUCK_DATABASE` (the share's alias after Q4, else `market_data`), `ALLOWED_ORIGIN = "https://henrymckay.github.io"`, a `[[kv_namespaces]]` binding `CACHE`, and `[triggers] crons = ["*/15 * * * *"]`.
  Rotate the Cloudflare token and the API's MotherDuck token at teardown or by 2027-02-15, whichever comes first.

### Errors

- **Yahoo throttles or a request fails in transit** — retried as D6 says; still failing, the instrument is failed with the error as its reason, the rest stored, exit 1.
- **An instrument returns no bars** (a delisted or mistyped symbol) — failed with reason `no data`; above the `tolerance` of 0 the run is `partial`, exit 1, and `status` names it.
- **Every instrument fails** — the adapter raises, nothing is replaced, a `failed` runs row is written, exit 1; yesterday's data stays in place and on the site.
- **Rows arrive but none validate for an instrument** — that instrument is failed, its stored rows kept, since an empty replace would read as a delisting.
- **A row fails validation** — quarantined in `rejected` with its reason; the instrument still stores.
- **The token is missing or refused** — exit 2 with "motherduck_token is not set" or "MotherDuck refused the token"; the token's value is never in the message.
- **MotherDuck fails during the load** — the transaction rolls back, exit 1; the next run replaces everything anyway (D1).
- **The export or deploy fails** — the job fails and Pages keeps serving the previous deployment, whose age chip then turns stale.
- **The browser cannot load a file** — the card's error note, other cards and screens unaffected.
- **An unknown path or slug reaches the API** — `404`, `{"error": "No instrument with slug 'xyz'; see /api/overview for the list.", "code": "not_found"}`, answered from the cached overview without a query; a method other than `GET`, `HEAD` or `OPTIONS` is `405` with `Allow`.
- **MotherDuck is unreachable, refuses the token or takes over 20 s on a cache miss** — `503`, `{"error": "MotherDuck did not answer; try again in a minute.", "code": "store_unavailable"}` with `Retry-After: 60`; the log line carries a fixed reason, never the driver's message or the token (R8, as D32 does for the CLI).
- **The cron cannot reach MotherDuck** — the version stays where it was, so every cached response keeps being served and the page's age chip turns stale by its own rule; logged once per cron run.
- **A KV write fails** (the 1,000-a-day limit, which D53's bound keeps out of reach) — the body is still returned, with `Cache-Control: no-store`, and logged.
- **Cloudflare refuses the request** (Error 1027 past 100,000 a day, 1102 past the CPU limit) — Cloudflare's own error page; the dashboard shows each card's error note, and the API is back at 00:00 UTC or on the next request.
- **The warm job finds a non-200 or the version never moves within 20 minutes** — the job fails, so GitHub mails the owner; the API keeps serving and fills on first request.

### Decisions

- **D1 Re-fetch every instrument's whole daily history each night and replace its rows** over an incremental upsert of recent days with a catch-up window — one request per instrument either way, and a full read is the only way a split or dividend's restatement of history, a revised bar or a missed night is healed without special cases; the cost is about 800,000 rows (some 30 MB) moved to MotherDuck a night; source: the 2026-11-17 probe in Inputs; overrides `run-unattended`, Make a run rerunnable (catch-up window and explicit backfill) *(proposed)*.
- **D2 MotherDuck is the only store; no Parquet tree, no committed data, no raw archive** over `store-data`'s tree as the record with MotherDuck as a second sink, its raw-page artifact, and `deploy-project`'s commit-back — the owner named MotherDuck, the source re-serves all history nightly so a parser fix reaches history the next night, and committing per-day files would add thousands of files to a throwaway repository; the cost is no copy outside MotherDuck (a re-run rebuilds it in minutes) and no nightly commit to keep the schedule alive (A3); overrides `store-data`, Lay out the data directory and Keep what the source sent, and `deploy-project`, Run the pipeline *(proposed)*.
- **D3 Bake the site data from MotherDuck at build time into static Parquet** over the browser querying MotherDuck live through its WASM client, which needs a token in a public page that anyone could use to read, write and spend compute, and over an API on Render, which needs a server that sleeps — `secure-project`, Guard what is served, and `write-entry-points`, Dashboard (over files) *(by precedent)*. *Superseded by R9 and D51 to D60 (2026-11-18): the export ends in M6.*
- **D4 Vite, React, TypeScript, Tailwind and shadcn/ui, with Lightweight Charts 5.3 for candles, ECharts 6.1 for the rest and `hyparquet` 1.33 for Parquet, Node from `nodejs-wheel` 24** over vanilla JavaScript with one chart library (floated in the brief), which leaves the token system, components, scheme handling and tests to hand-roll, and over DuckDB-WASM (tens of megabytes, earned only when a viewer writes SQL) — `write-entry-points`, Dashboard; `design-interface`, `references/web.md`; versions read from npm and PyPI 2026-11-17 *(by precedent)*.
- **D5 Python 3.14 and `duckdb>=1.5.6,<1.6`** over 3.15 and an uncapped `duckdb` — MotherDuck accepts clients 1.4.0 to 1.5.6 in every region (`motherduck.com/docs/duckdb-versions.json`, read 2026-11-17), DuckDB 2.0.0 is already on PyPI, and `duckdb` 1.5.6 ships wheels up to cp314; overrides `setup-python`'s 3.15 floor and no-upper-cap rule, as `store-data`, Pick the engine, directs *(by precedent)*.
- **D6 Call Yahoo through `yfinance`'s own session, one instrument at a time, paced at one request a second by `pyrate-limiter` and retried by `tenacity` on `YFRateLimitError` and transport errors, five attempts with exponential jittered waits up to 60 s** over the house `httpx` client — `yfinance` owns its `curl_cffi` browser-impersonating session, which is what Yahoo accepts, and its thread pool would burst requests; the cost is about 2 minutes a night; overrides `structure-python`, Write an adapter (one `httpx.Client`) and keeps its pacing and retry rules *(proposed)*.
- **D7 The token lives only in the `nightly` job, which also runs `export` and hands the site data to the `site` job as an artifact** over `deploy-project`'s site job reading the store itself — the `site` job runs `npm ci`, whose third-party install scripts then never see the token; `secure-project`, Keep secrets out *(proposed)*. *Narrowed by D59 and D61: once the export is removed the `nightly` job keeps the pipeline's token and hands nothing on; the API's token lives in the `api.yml` deploy job and the Worker.*
- **D8 The universe is a CSV in package data** over `structure-python`'s user-editable list in the data directory — the runner has no data directory, and an edit is a commit the next night picks up; overrides `structure-python`, Configuration *(proposed)*.
- **D9 Store complete bars only, dropping any bar dated on or after the run's UTC date** — `run-unattended`, Name the day (yesterday in UTC); the probe showed forming bars for FX, futures and crypto *(by precedent)*.
- **D10 Fetch with `auto_adjust=False, actions=True` and store split-adjusted OHLC, adjusted close, dividends and splits** over `yfinance`'s default `auto_adjust=True`, which also strips dividends from OHLC so candles stop matching quoted prices; candles show close, every return uses adjusted close, the convention of practitioners' total-return figures *(proposed)*.
- **D11 The workflow's `concurrency` group is the overlap lock; no `fcntl` lock** over `run-unattended`'s lock file — the runner has no persistent data directory, and per-instrument replaces in one transaction leave an overlapping local run harmless; overrides `run-unattended`, Make a run rerunnable *(proposed)*.
- **D12 Schedule at 02:17 UTC every day** — after the US close (21:00 UTC) and the end of the crypto day, off the hour, weekends included for crypto; `deploy-project`, Run the pipeline, and `run-unattended`, Name the day *(by precedent)*.
- **D13 No notification; GitHub's failed-run mail, `status` and the dashboard's age chip are the signals** — `run-unattended`, Report the outcome; no requirement asks for an alert *(by precedent)*.
- **D14 The core in Polars, converting `yfinance`'s pandas frame at the adapter with `polars.from_pandas`** — `use-polars`, Unlearn pandas; `setup-python`, Libraries *(by precedent)*.
- **D15 Metrics stored long in MotherDuck and recomputed whole each night** — `store-data`, Keep what the source sent; the export pivots them for the page *(by precedent)*.
- **D16 One overview file plus one bars file per instrument, loaded on demand** over one file of every close (about 10 MB) — keeps the first load inside R4's 800 KB, with Ticker and Compare and their chart code split out of the first bundle and each file inside `deploy-project`'s few-megabyte guidance *(proposed)*. *Superseded by D55: one overview response and one bars response per instrument, cached at the edge.*
- **D17 Exported Parquet uses snappy compression** over Polars' default zstd — `hyparquet` reads only uncompressed and snappy without the extra `hyparquet-compressors` package (hyparquet README, read 2026-11-17) *(proposed)*. *Superseded by D52: the API sends JSON.*
- **D18 All data is classed public** — the owner set aside Yahoo's terms in R7, which `secure-project` would otherwise read as private; so it may sit in public workflow logs and on Pages (from R7).
- **D19 MotherDuck's schema through numbered forward-only migrations in package data, applied when the store adapter connects** — `write-sql`, Change a schema *(by precedent)*.
- **D20 The pipeline's speed is not optimised** — about 2 minutes of fetching and a minute of loading against a 30-minute timeout; only the dashboard has a budget (R4) *(proposed)*.
- **D21 Universe of about ninety instruments** — 8 indices (`^GSPC ^NDX ^DJI ^RUT ^VIX ^FTSE ^GDAXI ^N225`), 4 rates (`^IRX ^FVX ^TNX ^TYX`), 22 ETFs (`SPY QQQ IWM EFA EEM TLT IEF HYG LQD GLD SLV` and the 11 SPDR sector funds), 40 large US stocks across sectors, 6 FX (`EURUSD=X GBPUSD=X USDJPY=X AUDUSD=X USDCHF=X DX-Y.NYB`), 5 commodity futures (`GC=F SI=F CL=F NG=F HG=F`), 4 crypto (`BTC-USD ETH-USD SOL-USD XRP-USD`) — broad enough for every screen, small enough for Yahoo's limit *(proposed)*.
- **D22 The core computes both return and change for every instrument; the page shows change for yields and return for prices** over a branch on quote type in the core *(proposed)*.
- **D23 Tests**: the core on fixtures and an in-memory fake store; the Yahoo parse on a recorded response saved by `tests/data/yahoo/record.py`; the MotherDuck adapter and the README's queries on a local DuckDB file under `tmp_path` (the same SQL MotherDuck runs); `vitest` for `web/src/lib/`; a Playwright smoke per screen marked `slow`; one real-surface run marked `real` against Yahoo — `write-tests`, `write-sql` *(by precedent)*.
- **D24 The Python sits in a `code/` layer beside `data/`** (`market_data.code.transform` and the rest) — `structure-python`, Code, since the package has a `data/` tree *(by precedent)*.
- **D25 A failed instrument writes nothing to `rejected`**; its reason is logged and it is counted in `runs.failed_items`, so its last stored `bars` and `rejected` rows stay untouched — `store-data`'s quarantine row per failed item would have needed a replace that erases the prior night's rows for it *(proposed)*.
- **D26 When every instrument fails, `operate.fetch_bars` replaces nothing and appends a `failed` runs row** over the adapter raising — the row needs the request count the adapter holds; overrides `structure-python`, Write an adapter (a source whose every item failed raises), with the same effect: no empty replace *(proposed)*.
- **D27 No primary-key constraints on `bars` or `rejected`**; uniqueness of `(ticker, day)` is enforced by validation's duplicate rule — an index on 800,000 rows costs a MotherDuck upload and delete-then-insert of the same keys in one transaction is the case constraints handle worst *(proposed)*.
- **D28 `ruff`'s `TC001`–`TC003` are off on Python 3.14**, since their fix needs `if TYPE_CHECKING:` blocks and the skill's fix is 3.15's `lazy import`; overrides `setup-python`, Configure the project (`select`) until the floor reaches 3.15 *(proposed)*.
- **D29 `pyright` is strict on `src/` and standard on `tests/`** — strict on 440 untyped fixture parameters costs more than it catches; overrides `write-tests`, Tests are code *(proposed)*.
- **D30 `yfinance.config.debug.hide_exceptions` is set to `False` when the history getter is built** — found in a run: by default a throttled or failed request returns an empty frame logged as "possibly delisted", which would count as `no data` and never retry; `YFTickerMissingError` is `no data`, `YFRateLimitError` and transport errors are retried *(by precedent: `write-python`, Classify outcomes)*.
- **D31 `--log-level` is an option of each command** (`nightly --log-level info`), as Interface writes it, not of the app *(by precedent: Interface)*.
- **D32 The token reaches DuckDB only as the environment variable `motherduck_token`**; settings check it is present, a log formatter replaces its value with `[redacted]` in every line, and a connection failure raises a fixed message without the library's text (R8) *(by precedent: `secure-project`, Keep secrets out)*.
- **D33 The metrics' definitions**: each window starts at the last bar's day minus `1d`, `1w`, one, three, twelve, thirty-six or sixty months, `ytd` at 31 December of the year before, and measures from the last bar at or before that start, so a weekend start reads Friday; a window history does not reach is absent, not null; volatility is the sample standard deviation of daily adjusted-close returns over the year to the last bar, times √252; the 52-week high and low are the extreme `high` and `low` of those bars; maximum drawdown is the worst fall below the running peak of adjusted close within them; traded value is the mean of `close × volume` over the last 20 bars, absent where volume is null (Terms: Window, Drawdown); `change` for `3y` and `5y` is not annualised *(proposed)*.
- **D34 `compute` fails an instrument that is active and has no bars**, with the same `tolerance` as Yahoo's, so a dead symbol makes both stages `partial`; with no instrument measured nothing is replaced and a `failed` row is appended, as D26 does for fetch *(proposed)*.
- **D35 `status` is healthy only when the latest run of every source is `stored` and the last stored `yahoo` run is under two days old**, a stricter reading of Interface's "the last run was not `stored`" so a failing `compute` after a stored fetch shows; its rows are `last_run`, `outcome`, `age_hours`, `failed_items` (all of the overall last run), `missing` (active instruments with no bars, `;`-separated, named from the store since D25 keeps failed items out of `rejected`) and `stale`; an empty store is unhealthy *(proposed)*.
- **D36 `nightly` opens one connection for fetch and compute and prints one header over one row per stage**, exiting 1 if either did not store; a failed fetch still runs compute over yesterday's bars *(proposed)*.
- **D37 The workflow** runs `nightly` then `status` (on `!cancelled()`) in one job so the dispatched run shows both exit codes; `permissions: {}` at the top and `contents: read` on the job; `persist-credentials: false`; each action pinned to a full commit SHA with its tag beside it (checkout v7.0.1, setup-uv v10.3.3, read from the releases API 2026-11-17); `cancel-in-progress: false`; the token only in the env of the two steps that read the store; overrides nothing, but `github-actions.md`'s sample grants `contents: write`, which nothing here needs *(by precedent: `deploy-project`, Run the pipeline; `secure-project`, Keep secrets out)*.
- **D38 `read_runs` returns its times converted to UTC**, found in a real run: DuckDB hands back the session's zone (here +04), which `status` printed as `Z` *(by precedent: `write-python`, Time and money)*.

- **D39 `export` reads through `SiteSource` and writes through `SiteWriter` ports; the overview carries `slug`, `bar_count`, `first_day`, `last_day`, `rejected` beside the plan's columns, and keeps an active instrument with no bars with null figures** — the Runs coverage needs them and a dead symbol must show, and the page never recomputes the slug (`write-sql`, Never compute one result both ways) *(proposed)*. *Narrowed by D54 and D59: `SiteSource`, `SiteWriter` and `export` go in M6; the overview columns live on in the `overview` table.*
- **D40 The Markets treemap and the leaders bars are DOM, not ECharts; the monthly calendar and the correlation matrix are HTML tables; ECharts draws only the drawdown and Compare lines** over D4's ECharts for every non-candle chart — it keeps 167 KB gzipped of ECharts off the first load, gives labels that adapt to tile size, instant re-theming and real buttons for a screen reader; overrides `design-interface`, `references/web.md` (ECharts for charts) *(proposed)*.
- **D41 shadcn/ui's CLI was not run; components are written by hand in its pattern (`cva`, `clsx`, `tailwind-merge`, `cmdk` for the search) and its token names** — the generator is interactive and pulls Radix for parts used once; `design-interface`, `references/web.md` says to add components with the CLI *(proposed)*.
- **D42 Two extra tokens, `--up-text` and `--down-text`**, a darker blue and red step for text in light and a lighter one in dark, since `up` and `down` fall under 4.5 to 1 as text on `surface`; the same idea as `design-interface`'s status-text steps *(proposed)*.
- **D43 Site files are fetched whole and read with `hyparquet`; `overview.parquet` and `runs.parquet` are preloaded from `index.html`; a refetch after a new `ended` adds `?v=<ended>`** — a 60 KB to 830 KB file costs one request, and the preload took 0.4 s off a throttled cold load *(proposed)*. *Superseded by D58: the page fetches the API's JSON, preloads `/api/overview` and `/api/runs`, and keeps `?v=<ended>`.*
- **D44 A tile shows a value of 50,000 or more compact (`64.9K`) with the exact figure in its tooltip; the leaders and laggards leave out rates and `^VIX`** — Design's example and `design-interface`'s Numbers; a volatility index's +18% would flatten the ranking *(proposed)*.
- **D45 Browser smokes run over a synthetic year for the universe, exported by the CLI, served from a copy of `web/dist`; marked `slow`, left out of the default run, and failing with an instruction when `web/dist` is missing** — `write-tests`, Coverage and speed *(by precedent)*. *Narrowed by D63: the smokes keep the synthetic year but serve it through a stub API instead of exported files.*
- **D46 `evaluation/shoot.py` and `measure.py` are committed; `evaluation/round-*/` is git-ignored; `ruff` excludes `evaluation/`** *(by precedent: `build-project`, evaluate.md)*.
- **D47 The `site` job installs the dev dependency group (`uv sync --locked`), which holds `nodejs-wheel`, and runs `npm ci` with no token in its environment; the `deploy` job holds only `pages: write` and `id-token: write`; the site-data artifact is kept for one day** — D7 and D37, with actions pinned to SHAs (upload-artifact v7.0.2, download-artifact v8.0.2, upload-pages-artifact v5.0.0, deploy-pages v5.0.1, read from the releases API 2026-11-18) *(by precedent: `secure-project`, Keep secrets out)*. *Narrowed by D58: the `site` job moves to `site.yml` and builds without a site-data artifact.*
- **D48 The deploy runs from `main` only**: the `github-pages` environment allows deployments from the default branch only (the API shows custom branch policies), so the `site` and `deploy` jobs were first exercised on a branch run (the `deploy` job refused, as designed) and the publishing run was dispatched on `main` after the workflow merged; the branch policy was left unchanged *(proposed)*.
- **D49 Tickers' last-price axis tag is off, and the Markets table's subtitle names the unit** after the live evaluator's round 1 (the tag clipped an axis label; "Last" had no unit); the TradingView logo over the volume pane stays, since the library's licence asks for the attribution; Bitcoin's compact `64.9K` stays as D44 decided *(proposed)*.
- **D50 R8's "no unmasked fragment" check** splits the token on its dots and into sixteen-character windows and counts each in the run logs and the built site, in addition to the whole-token count, since GitHub masks the whole value only *(proposed)*.
- **D51 The API is a Cloudflare Worker on Workers Free, querying MotherDuck through its Postgres endpoint with `pg` 8.23** over:
  - Vercel Hobby, a function in `dub1` beside MotherDuck's `eu-west-1` with CDN caching built in, but a cold start per idle instance, a Python function downloading the `motherduck` extension on each, non-commercial terms, and the owner pasting the token into Vercel's dashboard (vercel.com/docs/plans/hobby, updated 2026-11-12);
  - Render's free web service, which sleeps after 15 idle minutes and takes about a minute to wake, against R4's 1.5 s (`deploy-project`'s host table, 2026-11-12);
  - Hugging Face Docker Spaces, which now need a paid plan and allow outbound traffic on ports 80, 443 and 8080 only (huggingface.co/docs/hub/spaces-overview, read 2026-11-18);
  - Deno Deploy, which "will be sunset in April 2027" (deno.com/deploy/pricing, read 2026-11-18);
  - Cloud Run and Koyeb, which need a card (R10).
  A Worker has no cold start, a free cron and KV, needs no card, and MotherDuck documents this pairing (`pg` over `nodejs_compat`, `sslmode=require`; MotherDuck's Postgres endpoint reference and Cloudflare Workers guide, read 2026-11-18), and the endpoint answered a live test from Lite (Inputs); the cost is TypeScript beside the Python, a 10 ms CPU budget a request (A17) and an endpoint labelled preview (A20); overrides `deploy-project`, Serve an API (Render, once a second consumer earns it), since R9 earns it *(proposed)*.
- **D52 Each query builds its whole response body in DuckDB — one row, one `varchar` from `json_object`, `list` and `to_json` — and the Worker relays the string** over `pg` returning rows the Worker serialises: `^GSPC` as rows took 8.7–9.3 s against 2.5 s as one string in the live test, and decoding 25,000 rows in JavaScript would spend the 10 ms CPU budget; values are sent as stored, with no rounding (I15); the queries are `.sql` files in `api/src/queries/` bound with `$1` (`write-sql`, Keep each query in one place) *(proposed)*.
- **D53 Responses are cached in KV under the data version, which a cron every 15 minutes reads from MotherDuck; a request never queries MotherDuck for freshness** over a query per request (truly live, but every view costs at least 1 CU-second, Pulse's minimum per query, so traffic or a flood becomes MotherDuck spend with no ceiling), over a per-request freshness check cached in each isolate (bounded only by how many isolates Cloudflare runs), and over Workers Caching's `cache.enabled` (Oct 2026; Free-plan availability and `workers.dev` support unstated, I11); the cost is the page trailing MotherDuck by up to 15 minutes (Q6) and 96 small queries a day, about 0.8 CU-hours a month (motherduck.com pricing, read 2026-11-18); `secure-project`, money rules, and `make-decisions`, Earn it *(proposed)*.
- **D54 `compute` also writes an `overview` table in MotherDuck from the existing Polars pivot (`transform/site.py`)**, replaced whole in the metrics transaction, over a SQL view rewriting the pivot and sparkline in SQL and over the Worker pivoting `metrics` in TypeScript — either puts a second computation of the overview beside the core's, and the core keeps its tested transform (`write-sql`, Choose SQL or Polars; Never compute one result both ways); the cost is migration `0003` now and a migration per new metric column *(proposed)*.
- **D55 Four fixed `GET` endpoints, no SQL, no range or filter parameter, slugs checked against the cached overview before any query** over `write-entry-points`' `start` and `end` bounds — the page needs every instrument's whole history (the monthly calendar), and a closed key set caps MotherDuck at one query per endpoint and instrument per data version, about 92 a night, whatever the traffic *(proposed)*.
- **D56 The API checks no token and allows one browser origin, `https://henrymckay.github.io`; no rate limit** — overrides `secure-project`, Guard what is served (a token per consumer on an API reached beyond the machine): its one consumer is a public page, which the same section says holds no token, the data is public (D18), and the API only reads through fixed queries; CORS stops other sites' pages, not `curl`; D55's bound caps MotherDuck spend and Cloudflare's 100,000 a day caps the Worker, so a flood costs availability until 00:00 UTC, not money *(proposed)*.
- **D57 The API reads MotherDuck with its own token: a service account's, attached to a restricted share of `market_data` with `UPDATE AUTOMATIC`** over the owner's token (A1), which writes and reaches every database — Lite has no read-only token (read scaling is Business and Enterprise only, motherduck.com pricing, read 2026-11-18) but a share is read-only to its reader, and Lite allows two service accounts; `secure-project`, one credential per consumer; waits on Q4 *(proposed)*.
- **D58 The dashboard stays on GitHub Pages at its URL, built by `site.yml` on a push to `web/**`**, `data.ts` fetching JSON into the same shapes, preloading `/api/overview` and `/api/runs` from `index.html`, and `hyparquet` dropped, over Workers static assets on the API's origin (one origin, no CORS, one deploy, but a new URL for a live site the README, screenshot and evaluator rounds name; I13) — `write-entry-points`, Dashboard (one data module) *(proposed)*.
- **D59 The nightly export is removed with no static fallback** — `export`, `operate/export.py`, `adapt/site.py`, `build_runs` and `build_latest`, the site-data artifact — over keeping the Parquet files for the page to fall back on: R9 asks to stop the nightly files, a fallback is a second read path to keep true, and the cache already serves the last version while MotherDuck is down *(proposed)*.
- **D60 The nightly workflow gains a `warm` job with no secret**: it polls `/api/latest` until `ended` is at or after the `nightly` job's start (20 minutes at most), then requests `/api/overview`, `/api/runs` and every `/api/bars/<slug>`, failing on any status but 200, so no visitor waits on a miss (R4) for queries a visit would run anyway; over a cron that warms in the Worker, which 50 subrequests and 10 ms of CPU an invocation cannot fit *(proposed)*.
- **D61 `api.yml` has a `test` job (`npm ci`, typecheck, lint, `vitest`) and a `deploy` job on `main` only**, `permissions: contents: read`, actions pinned to commit SHAs, `npm ci --ignore-scripts` where the tokens are present, the Cloudflare and MotherDuck tokens in the environment of the deploy steps alone, and the MotherDuck token reaching `wrangler secret put` on standard input, never as an argument — D7's and D37's reasoning *(by precedent: `secure-project`, Keep secrets out)*.
- **D62 The Worker keeps a pure core and a thin shell**: `api/src/route.ts` (pure: path and method to an endpoint, the version and `ETag` check, headers, error to status), `api/src/store.ts` (the `pg` adapter: one `Client` an invocation, `connectionTimeoutMillis` 5,000, `query_timeout` 20,000, a fixed query by name), `api/src/cache.ts` (the KV adapter), `api/src/index.ts` (the `fetch` and `scheduled` handlers and composition root); the store is a port passed in as a function, `(query, params) => Promise<string>` — `structure-python`'s layers and `be-functional` in TypeScript *(by precedent)*.
- **D63 Tests**: `vitest` with `@cloudflare/vitest-pool-workers` 0.23 over the Worker with a fake store and miniflare's KV (routing, CORS, `304`, a 404 with no store call, one store call per key per version, each error's status and body); `pytest` runs each `api/src/queries/*.sql` against a DuckDB file the MotherDuck adapter wrote with every migration applied, asserting the JSON parses into the endpoint table's shapes and agrees with the stored rows; the browser smokes serve `web/dist` beside a stub API in Python that answers each endpoint by running the same `.sql` files over the synthetic year; one real run through `wrangler dev` against live MotherDuck — `write-tests`; `write-sql`, Test a documented query *(by precedent)*.
- **D64 `GET /` is the API's docs page**, one static HTML page in the house tokens listing each endpoint with an example request, response and error — `design-interface`, Set the bar (API) *(by precedent)*.
- **D65 `wrangler` 4.164, `pg` 8.23.1, `@cloudflare/vitest-pool-workers` 0.23.0 and `@cloudflare/workers-types` 5.20261118.1** (npm, read 2026-11-18), with Node from `nodejs-wheel` as D4 *(by precedent: D4)*.
- **D66 `worker.ts` holds `createWorker(makeStore)` and `index.ts` is only the composition root `export default createWorker(motherDuck)`**, so `vitest` loads the Worker without `pg`, which the test pool cannot load as CommonJS; refines D62 *(proposed)*.
- **D67 The cron fills `latest`, `overview` and `runs` under the new version and then moves the version, and a request that finds no version in KV initialises it from `latest.sql`** over moving the version first (D53's wording), so no request sees a version whose bodies are not yet cached; a log line `cache: miss` is written for that first request too *(proposed)*.
- **D68 `bars.sql` names the ticker with `any_value(ticker)`, not `$1`**, since MotherDuck's Postgres endpoint rejects a prepared parameter as a `json_object` value ("ambiguous result column types", found live 2026-11-18); a ticker with no bars answers `ticker: null` and empty columns, and the Worker only asks for tickers in the overview *(proposed)*.
- **D69 `vitest` runs the Worker with `compatibilityDate` `2026-08-15`**, since `@cloudflare/vitest-pool-workers` 0.23.0 bundles a `workerd` older than `wrangler` 4.164's and refuses `wrangler.toml`'s `2026-11-18`; production keeps `2026-11-18` *(proposed)*.
- **D70 `api.yml`'s `test` job runs on every push touching `api/**`; its `deploy` job runs only on `main` and only once the repository variable `API_URL` is set (M7)**, since an `if` cannot read a secret and the variable is public; until then the workflow only tests, with no token in its environment *(proposed)*.
- **D71 `npm audit` on `api/` reports one high advisory, `picomatch` ReDoS reached through `vitest` and `tinyglobby`, which is accepted**: it is a test-time dependency parsing the repository's own globs, `npm audit --omit=dev` is clean, and the only fix downgrades `vitest` below the pool's peer range *(proposed)*.

## Delivery

### Verification

- **R1** — unit tests of the core's completeness filter, validation, returns, drawdown and volatility against stated answers; a `workflow_dispatch` run of `nightly` exits 0 with a `yahoo` runs row `stored`, `failed_items` 0, `rows` above 500,000, and every active instrument's last stored day at or after the last weekday before the run (crypto: the run's UTC yesterday).
- **R2** — `gh run list --workflow nightly.yml --event schedule` shows a successful run fired by the schedule after the workflow reached `main`, and its `runs` row is in MotherDuck.
- **R3** — `select count(*) as bars, count(distinct ticker) as tickers from market_data.bars;` equals the manifest's `rows` and the universe's active count; a test runs `fetch` twice against a local DuckDB file with the same fake response and finds the same rows (re-run safe).
- **R4** — Playwright smoke per screen waits for `data-ready` with no page error; screenshots at 1440 by 900 and 390 by 844 in light and dark pass the evaluator on all ten `design-interface` criteria; on the live site, measured with Playwright from a cold cache: Markets ready within 1.5 s and at most 800 KB transferred, each period, range and sort control within 200 ms, an instrument switch within 500 ms.
  After M7 the same live timings are re-measured on the API version, after a `warm` job has run, and the switch to a warmed instrument stays within 500 ms; a cold miss on `/api/bars/gspc` (the largest) is timed and recorded, budgeted at 10 s.
- **R5** — on the live site the age chip's run time equals the latest stored `yahoo` `ended` in MotherDuck's `runs`, within 15 minutes of that run ending (D53); before M6, a test of `export` over a fake store wrote every site-data file with the expected rows.
- **R6** — the repository is public, the workflow's runs show no billable minutes, Pages is on the free plan, and the nightly logs' MotherDuck connected time stays under 5 minutes a night (under 2.5 hours a month of the 10 included).
  After M7: MotherDuck's month-to-date usage, read from its billing page or `md_information_schema` where Lite exposes it, stays under 5 CU-hours; Worker requests stay under 10,000 a day and KV writes under 200 a day for a week (Cloudflare's dashboard or `wrangler` analytics).
- **R7** — none beyond D18: the repository and site are public by design, which M2 and M4 create.
- **R8** — `gitleaks` runs on every commit and `gitleaks git` over the whole history is clean; the token, piped from the keychain into `grep -F -c -f -` and never printed, occurs 0 times in every run log (`gh run view --log`) and in the built site.
  After M7: the API's MotherDuck token and the Cloudflare token occur 0 times, whole or as D50's fragments, in every `api.yml`, `site.yml` and `nightly.yml` log, in the built site and in a `wrangler tail` session over every endpoint and error; no `wrangler` command line in a workflow names a token.
- **R9** — on the deployed API: `/api/latest`'s `ended` equals `select max(ended) from runs where source = 'yahoo' and outcome = 'stored'` within 15 minutes of a run; `/api/overview` has one object per active instrument; `/api/bars/gspc`'s `day` has as many entries as `select count(*) from bars where ticker = '^GSPC'`; `/api/bars/nope` and `/api/sql` answer 404, and `vitest` shows neither calls the store; `vitest` shows a second request for a key in the same data version makes no store call; a response to `Origin: https://example.com` carries no `Access-Control-Allow-Origin`; the live site's network log (Playwright) shows every data request going to the API's origin, `data/overview.parquet` answers 404 on Pages, and `web/dist` holds no `.parquet` file.
- **R10** — the owner confirms once that the Cloudflare account has no payment method and is on Workers Free; a week of the Worker's metrics shows no Error 1027 or 1102 and CPU time a request under 10 ms at the 99th percentile, including a cold `^GSPC` fill.

### Milestones

- [x] **M1 Scaffold and first real path** — R1, R3, R8; `setup-python`'s scaffold on Python 3.14 with `duckdb` pinned (D5), `gitleaks` in pre-commit, logging, settings, the universe, the Yahoo adapter with pacing and retry, validation, the MotherDuck store with its first migration, `fetch` and `nightly` without `compute`, `git init` on a branch; done when the suite passes and a local `nightly` with the token from the keychain loads every active instrument into `md:market_data` with exit 0 and the R3 counts agree, and a second run leaves the counts unchanged apart from new bars.
  Ticked 2026-11-18 once the keychain token was replaced (A11): a local `nightly` into `md:market_data` exited 0 with 833,631 bars, 89 tickers, no duplicate `(ticker, day)` and 1,958 metrics, and `status` exited 0.
- [x] **M2 Unattended on Actions** — R1, R2, R3, R6, R7, R8; `compute`, `status`, exit codes, the `nightly` job of the workflow; create the public repository, push, set the secret from the keychain by pipe, merge to `main`, run it by `workflow_dispatch`; done when the dispatched run passes R1's check, `status` exits 0, a forced failure (a bogus symbol added on a branch run) exits 1 and names it, and R8's log count is 0; R2's scheduled-run check is ticked from the first night after.
  Ticked 2026-11-18. Dispatched run [44238259919](https://github.com/henrymckay/market-data-public/actions/runs/44238259919) on `main`: stored, `failed_items` 0, `status` `stale=false`, 1m58s (A2 confirmed: Yahoo serves the runners). Forced failure, run [44238618625](https://github.com/henrymckay/market-data-public/actions/runs/44238618625) on branch `test/forced-failure` (since deleted): the `nightly` and `status` steps both exited 1, the log names `ZZZBOGUS1 failed: no data` and `status` printed `missing,ZZZBOGUS1`; the `main` run [44238883892](https://github.com/henrymckay/market-data-public/actions/runs/44238883892) then stored every instrument again. R8: the token occurs 0 times in all three run logs, and none of its three parts or 66 sixteen-character fragments appears unmasked. R2's scheduled-run check is ticked from the first night after (the first cron, 02:17 UTC 2026-11-19).
- [x] **M3 Dashboard** — R4, R5; `export`, the `web/` app through `nodejs-wheel`, tokens first, then shared pieces, then the four screens, built locally over site data exported from MotherDuck; done when `vitest` and the Playwright smokes pass and the evaluator passes all ten criteria on the eight screenshots.
  Built over site data exported from a local DuckDB file holding a real load, not MotherDuck (A14); the evaluator passed 9 of 10 criteria in round 2 and the one failure (a white pane separator in dark) was fixed and checked by the builder, with no third round. Live timings (R4) wait for M4.
- [ ] **M4 Deploy and verify** — R2, R4, R5, R6, R8; the `site` and `deploy` jobs, Pages enabled by API, a dispatched run publishing the site, the README with the live URL, a screenshot, the README's queries and the teardown steps (Q2); done when R4's live timings, R5's age check, R6 and R8 pass on the live site and a scheduled run has published it.
  Built and live at <https://henrymckay.github.io/market-data-public/>; R4, R5, R6 and R8 pass on the live site (see the M4 report in the commit history); left unticked only for the last clause, the first scheduled run publishing it (02:17 UTC 2026-11-19) — tick M4 and R2 together then.
- [x] **M5 API built and tested locally against live MotherDuck** — R8, R9; migration `0003_create_overview.sql` and `compute` writing `overview` (D54), run once into `md:market_data` from the laptop; the Worker in `api/` (D62): the four queries, the KV cache and cron, the docs page; `vitest` and the `pytest` query tests (D63); done when both suites pass, `wrangler dev` with the keychain token in its environment answers every endpoint with R9's counts, a repeat request logs a cache hit with no query, `/api/bars/nope` is 404 with no query, a cold `/api/bars/gspc` is timed, and the token occurs 0 times in the dev log. No outward step.
  Ticked 2026-11-18. `compute` ran into `md:market_data` (migration 0003 applied, `overview` 89 rows, `status` exit 0); the Python suite (130), `vitest` (21), `tsc`, `oxlint`, `actionlint` and `sqlfluff` pass; `wrangler dev` with the keychain token answered every endpoint against live MotherDuck (A18 held, the socket opens locally), a repeat request logged `hit` with no query, `/api/bars/nope` and `/api/sql` were 404 with no query, a cold `/api/bars/gspc` took 3.8 s (24,838 days, 2.9 MB, 492 KB gzipped) and the token occurs 0 times in the dev log.
- [ ] **M6 Front end on the API** — R4, R9; `web/src/lib/data.ts` fetches JSON from `VITE_API_URL` into the unchanged `Instrument`, `Run`, `Series` and `Latest` (D58), `hyparquet` and the Parquet preloads go, the stub API serves the smokes (D63), and `export`, `operate/export.py` and `adapt/site.py` are removed (D59); done when the Python suite, `vitest` and the browser smokes pass, a local build against the local Worker shows every screen with live data, and the evaluator passes the eight screenshots on the ten criteria. No outward step.
- [ ] **M7 Deploy and verify** — R4, R5, R6, R8, R9, R10; **stops first for the owner**: Q5's sign-in steps, then Q4's answer; then `api.yml` deploys the Worker, `gh variable set API_URL` names it, `site.yml` publishes Pages, `nightly.yml` loses `export`, `site` and `deploy` and gains `warm` (D60), and the README gains the API (its URL, docs page, endpoint table and an example), a fresh screenshot, and the teardown of the Worker, the KV namespace, the Cloudflare token, the service account and the share (Q2); done when R4's re-measured timings, R5's age check, R6, R8, R9 and R10 pass and a scheduled nightly has warmed the API.

## Open

### Assumptions

- **A1** The nightly uses the owner's own MotherDuck token, as pre-approved, rather than a service account's (replaces Q1's recommended answer until the owner acts) — it is the only credential provided; if the owner creates a service account, only the secret changes.
- **A2** Yahoo serves about 90 requests a night at one a second to GitHub's runner addresses without blocking them — reports of blocks concern bursts and shared addresses, unverified for Actions (search of yfinance issues, 2026-11-17); if wrong, M2's dispatched run fails partial or failed, and the fix is a slower pace or a question to the owner, since no free source replaces Yahoo here.
- **A3** The project is deleted within 60 days, so the schedule's 60-day inactivity rule never fires — the owner called it throwaway; if it lives longer, I1 keeps it alive.
- **A4** MotherDuck usage stays inside Lite's included 10 CU-hours and 10 GB, so nothing is billed — a few minutes of compute and well under 1 GB a night by estimate, unverified until R6's measurement; if usage approaches the quota, the run stops loading unchanged history (the incremental D1 rejected).
- **A5** "Daily prices" means daily OHLCV bars with full history — the domain's usual meaning; a shorter history only shortens the fetch.
- **A6** The universe in D21 suits the owner — a market overview needs breadth across asset classes; edits are one CSV row each.
- **A7** No database named `market_data` already exists in the owner's MotherDuck with other content — M1 checks before the first migration and uses `market_data_public` if it does.
- **A8** The pre-approval to use the token covers creating the database and its tables in MotherDuck — creating storage is what "store them in MotherDuck" requires.
- **A9** `hyparquet` returns a `date` column in a form `lib/data.ts` can normalise to ISO strings — unverified; a `vitest` case on a file the export wrote pins it.
- **A10** Each bar's day is the date of Yahoo's exchange-local index timestamp — the probe showed local midnights in each exchange's zone (New York, London, Chicago, UTC); if Yahoo shifts a zone, days move by one and R1's last-day check fails.
- **A11** *(resolved 2026-11-18)* The token first stored in the keychain was truncated and refused; the owner replaced it and a local `nightly` into `md:market_data` passed (M1).
- **A12** No `market_data` database exists in the owner's MotherDuck (A7) — read from the connector's `list_databases` (`my_db`, `sample_data`), assuming it is the token's account.

- **A13** A bogus symbol added to the universe CSV is how the forced failure is made (M2's wording "added on a branch run"); `fetch BOGUS` alone exits 2 as not in the universe, by design.

- **A14** *(resolved)* M3 was built over site data from a local DuckDB file because the token was invalid (A11); M4's live check read MotherDuck: the age chip equals MotherDuck's latest `ended`.
- **A15** The build proceeds as if Q4 and Q6 are answered yes (replacing them until the owner answers): the Worker reads the database named by `MOTHERDUCK_DATABASE`, `market_data` with the keychain token for M5's local run and the share's alias once Q4's service account exists; the deploy itself waits on Q4, since a security call takes the more private answer and waits (`make-decisions`).
- **A16** Restricted shares, `GRANT READ ON SHARE` to a service account and a service account's connection through the Postgres endpoint all work on Lite — the endpoint answered the owner's token from Lite on 2026-11-18, and Lite lists two service accounts, but shares on Lite are unverified (MotherDuck docs say nothing per plan); if not, the API runs on the owner's token (A1) and Q4 becomes a question of accepting that.
- **A17** Relaying the largest body (`^GSPC`, 2.9 MB in one `varchar`) fits Workers Free's 10 ms of CPU a request, since decoding one string and a KV write are native work — unverified until R10's metrics in M7; if not, the bars endpoint splits each history by decade (one more parameter, D55's bound times about ten), or the API moves to Vercel Hobby with the same TypeScript (D51's runner-up).
- **A18** *(resolved 2026-11-18: `wrangler dev` reached MotherDuck's endpoint locally, so M5's live check ran the Worker itself)* `wrangler dev` on the laptop opens the TLS socket to the Postgres endpoint — MotherDuck's Workers guide reports "Connection terminated" for some local runs; if so, M5's live check runs `store.ts` under Node from `nodejs-wheel` against live MotherDuck and the Worker's live check moves to M7.
- **A19** `wrangler deploy` provisions the KV namespace on first deploy from Actions; if not, a one-off dispatched step runs `wrangler kv namespace create` and its id is committed to `wrangler.toml` (an id is not a secret).
- **A20** MotherDuck's Postgres endpoint, labelled preview, keeps its documented behaviour for the project's life — it is throwaway (A3); if it changes, the Worker's one adapter (`store.ts`) changes.

### Questions

- **Q1** Should the nightly use a MotherDuck service account's token, reaching only its own database, instead of your personal token, which reaches all your databases from a public repository's Actions? — recommended: yes, create a service account (Lite allows two) and replace the `MOTHERDUCK_TOKEN` secret; blocks nothing, the build proceeds on A1.
- **Q3** Should each instrument carry a quote unit (`USD`, `index points`, `USD per oz`) in the universe so the headline tiles and the Ticker's last-close tile can name it? — live evaluator round 2 failed criterion 8 (Copy) on that alone; the table subtitle names the unit already; recommended: yes, a `unit` column in `universe.csv` and `tickers` (a migration); blocks nothing, M4 ticked on it as open polish.
- **Q2** At teardown, delete the repository, drop the MotherDuck database and revoke the token? — recommended: yes, by the README's teardown commands, run by you since each is irreversible; from M7 also delete the Worker and its KV namespace (`wrangler delete`), revoke the Cloudflare API token, and drop the share and the API's service account; blocks nothing.
- **Q4** Should the API read MotherDuck with a service account's token through a read-only share of `market_data` (D57), rather than your own token, which can write and reaches every database you have, now held by Cloudflare as well as GitHub? — recommended: yes; on your yes Claude does it with your token in one sitting, nothing printed: MotherDuck's REST `POST /v1/users` for `market-data-api`, `create share market_data_api from market_data (access restricted, visibility hidden, update automatic)` and `grant read on share market_data_api to market-data-api`, the account's token piped straight into `gh secret set MOTHERDUCK_API_TOKEN`, then the share attached once with that token; blocks M7's deploy.
- **Q5** Will you sign in to Cloudflare once and hand GitHub a deploy token, so every later deploy runs from Actions? — Claude cannot create or sign in to an account; the steps, about ten minutes, in order:
  1. Sign up at <https://dash.cloudflare.com/sign-up> with an email and password and verify the email; the Workers Free plan needs no card, and if a page asks for one, stop and tell Claude.
  2. Open Workers & Pages once, so the account's `workers.dev` subdomain exists, and note it (shown as "Your subdomain"; set one if asked).
  3. Note the Account ID from the same page's right-hand column (or Account home, the account's menu, Copy account ID).
  4. Go to My Profile, API Tokens, Create Token, use the "Edit Cloudflare Workers" template, set Account Resources to your one account and Zone Resources to none or all zones (there are none), then Continue, Create Token and copy it; it is shown once.
  5. In a terminal in any directory run `gh secret set CLOUDFLARE_API_TOKEN --repo henrymckay/market-data-public` and paste the token at its hidden prompt, so it is never in your shell history or a file.
  6. Run `gh secret set CLOUDFLARE_ACCOUNT_ID --repo henrymckay/market-data-public` and paste the Account ID.
  7. Answer Q4 and tell Claude the subdomain; Claude then runs M7 from step one of its list.
  — recommended: yes; blocks M7.
- **Q6** Is a dashboard that trails MotherDuck by up to 15 minutes live enough (D53)? — the store changes once a night, so a read through the cache gives the same answer a direct read would except in the minutes after a run; a direct query per request is truly live but turns every page view, or a flood of them, into MotherDuck compute billed past Lite's 10 CU-hours with no ceiling; recommended: yes; blocks nothing, built on yes.

### Ideas

- **I1** A weekly keepalive (an empty commit or `gh workflow enable` from a second schedule) so the nightly survives past 60 days — costs one workflow; not built.
- **I2** Grow the universe to the S&P 500 — a real breadth heatmap; costs 500 requests a night (about 9 minutes at one a second) and more rate-limit risk; not built.
- **I3** Size the treemap by market cap from `yfinance`'s `info` — truer weights; costs a second, heavier, more throttled request per stock; not built.
- **I4** Publish the database as a MotherDuck share so the owner can query it from any MotherDuck session without the pipeline's token — costs one statement and an account action; not built.
- **I6** `pyrate_limiter` logs its bucket set-up at INFO and the connected-seconds log covers fetching too for a local run; split fetch and load timings if R6 needs the load alone — costs a second timer; not built.
- **I7** Preload the Inter latin font and brotli-compress the site data on the host; the throttled cold load (1.6 s at 1.6 Mbit/s, 150 ms) is over 1.5 s though the loopback one is 0.5 s — costs a hashed-name lookup in the build; not built.
- **I8** A colour-scale legend for the treemap, tap-for-detail on a phone's small tiles, and the instrument in the Ticker page title — evaluator round 2 nits; not built.
- **I9** Add the Lightweight Charts attribution as footer text and turn the logo off (`attributionLogo: false`), so it stops covering the volume pane's corner; the live age chip also stays a skeleton when `overview.parquet` fails to load — live evaluator round 1 nits; not built.
- **I10** The live cold load on a throttled 1.6 Mbit/s, 150 ms link was 1.9 s (budget 1.5 s) while a normal link's median was 0.5 s over seven cold loads — same cause as I7; not built.
- **I5** An ntfy alert on a failed or missed night (`send-messages`) — costs a topic secret and a status workflow; not built.
- **I11** Cloudflare's Workers Caching (`cache.enabled`, docs updated 2026-10-30) in place of KV: hits never invoke the Worker or spend CPU, tiered and purgeable by `Cache-Tag`; its Free-plan and `workers.dev` support are unstated — costs a trial deploy in M7; not built.
- **I12** Place the Worker near MotherDuck's `eu-west-1` (Smart Placement or a placement hint) so a cache miss pays a short round trip instead of one from the visitor's edge — costs a config line, Free-plan support unverified; not built.
- **I13** Serve the front end from the Worker's static assets: one origin, no CORS, one deploy and no Pages job — costs the Pages URL the README and evaluator rounds use; not built.
- **I14** Send a year of bars first and the rest after, so the Ticker screen draws within 500 ms even on a cold miss — costs a second request per instrument and a parameter D55 rules out; not built.
- **I16** `@cloudflare/vitest-pool-workers` is renamed `@cloudflare/vitest-plugin` and no longer updated (its own banner, 2026-11-18); migrate with `npx @cloudflare/codemods vitest:pool-workers-to-vitest-plugin`, which may also lift D69's date pin — costs one dependency swap; not built.
- **I17** A cache miss on `/api/bars/aapl` took 5.5 s from the laptop and `eurusdx` 2.6 s: the miss cost is the MotherDuck round trip and the 20 s timeout is far off, but `warm` (D60) is what keeps visitors off it; not built.
- **I15** Send prices at `float` precision (Yahoo's values are 32-bit, so `268.82000732421875` is `268.82`) to roughly halve the bars bodies — a quick cast in the live test did not shrink DuckDB's JSON, so it needs a rounding rule per quote; not built.
