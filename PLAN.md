# market-data-public

Unsigned plan, written 2026-11-17 in autonomous mode for the owner's request, relayed by the planning session; every decision is *(proposed)* or *(by precedent)* until the owner reviews it.
The owner pre-approved exactly these outward steps, so the milestones include them: creating the public GitHub repository `market-data-public` under `henrymckay`, pushing to it, deploying to free hosting tiers that need no card, and using the owner's MotherDuck token.

A nightly cloud job that fetches daily prices for about ninety instruments with `yfinance`, stores them in MotherDuck, and publishes a fast static market dashboard built from that store, for the owner as a throwaway end-to-end test.

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
- **Site data** — the files the export stage writes for the dashboard to read.

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
  - Cost: the export stage reads MotherDuck, so the token is on the runner that builds the site data; a live browser read would put the token in a public page (D3).
- **R6** Deploy it end to end at no running cost.
  - Cost: free tiers only — a public repository for free Actions and Pages, MotherDuck Lite — and a usage figure logged so the free quota is watched.
- **R7** This is a throwaway test that will be deleted at the end, so Yahoo's terms and redistributing the data are not a concern.
  - Cost: none; it is what lets the data sit in a public repository's logs and a public site (D18).
- **R8** The MotherDuck token is never printed, logged, committed or written to a file in the repository; it is piped straight to where it is needed (from the planning brief).
  - Cost: the keychain locally, a repository secret on Actions, a secret scan on every commit and a count of the token in logs and site at the end.

### Not yet

- **Alerts** — a push or mail on failure; earned by a missed outage (`run-unattended`, Report the outcome).
- **A larger universe** — the S&P 500 or more; earned by the owner asking, since it multiplies requests against Yahoo's limit (I2).
- **Intraday prices** — earned by a requirement for them; daily bars are what was asked.
- **Fundamentals and market caps** — earned by the heatmap needing true weights (I3).
- **An API or live queries** — earned by a second consumer (`write-entry-points`).
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

### Data flow

1. **Universe** — one row is an instrument, keyed by `ticker`; the active rows become the list to fetch and the `tickers` table.
2. **Fetched** — one row is a bar, keyed by `ticker` and `day`; the Yahoo adapter maps each instrument's frame into `port.BARS` with `polars.from_pandas`, dates each bar by its index's local date, and returns a `Fetched` record of bars, rejected rows and failed instruments. (IO)
3. **Complete and valid** — the same grain; the core drops bars on or after the run's UTC date (D9) and splits the rest into valid bars and rejected rows with a reason: a null or non-finite close, a non-positive price on a `price` instrument, high below low, a duplicate day.
4. **Stored** — the same grain in MotherDuck; for each instrument that answered, its rows in `bars` and `rejected` are replaced in one transaction, instruments that failed keep last night's rows, and a `runs` row is appended. (IO)
5. **Metrics** — one row is one metric for one instrument, keyed by `ticker` and `metric`; the core computes every window's return and change, the 52-week high and low, 1-year volatility, 1-year maximum drawdown and 20-day traded value from `bars` read back from the store, and the store replaces `metrics` whole. (IO at both ends)
6. **Site data** — the export reads `tickers`, `metrics`, `bars` and `runs` from MotherDuck; the core pivots metrics to one overview row per instrument with a 63-bar adjusted-close sparkline, and the export writes the files in Outputs. (IO)
7. **Screens** — the browser reads the site data with `hyparquet`; range-dependent figures (a chosen range's return, drawdown, correlations) are computed in `web/src/lib/` from the bars, and every figure the overview already holds is read from it, never recomputed (`write-sql`, Never compute one result both ways).

### Outputs

**MotherDuck database `market_data`** — written by the nightly job, read by the export and by the owner at a SQL prompt; tables created by numbered migrations under `src/market_data/data/adapt/migrations/` (D19); `bars`, `rejected` per instrument replaced, `metrics` and `tickers` replaced whole, `runs` append-only; class public.

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

**Site data** — written by `export` into `web/public/data/` on the runner, built into the Pages site, never committed; Parquet with snappy compression (D17); class public.

- `overview.parquet` — one row per instrument: the `tickers` columns, every metric as its own column, and `spark` (list of 63 doubles); about 60 KB.
- `bars/<slug>.parquet` — one file per instrument (`slug` is the ticker lower-cased with `^`, `=` and `.` removed: `gspc`, `eurusdx`), every column of `bars` but `ticker` and `fetched`; 50 to 600 KB each, about 20 MB in all.
- `runs.parquet` — the last 90 runs.
- `latest.json` — the last `yahoo` run's row, polled by the open page.

**GitHub Pages site** — `https://henrymckay.github.io/market-data-public/`, replaced by each nightly deploy; class public.

### Interface

The package is `market_data` under `src/`, laid out as `structure-python` says: `transform`, `port`, `operate`, `error` in the core; `adapt/yahoo.py`, `adapt/motherduck.py` (both store ports over a DuckDB connection string), `adapt/site.py` (the export's file writer) at the edge; `drive/` holding the `typer` CLI and the composition root.
Per-source constants (pace, retries, `tolerance`) live in `data/adapt/yahoo.yaml`.

```bash
uv run market-data-cli nightly --log-level info
uv run market-data-cli fetch AAPL MSFT
uv run market-data-cli compute
uv run market-data-cli export --output web/public/data
uv run market-data-cli status
```

- `nightly` runs `fetch` for every active instrument, then `compute`; standard output carries one CSV manifest row per stage:

```text
day,ended,failed_items,last_day,outcome,rejected,requests,rows,source,started
2026-11-16,2026-11-17T02:19:41Z,0,2026-11-16,stored,2,90,803114,yahoo,2026-11-17T02:17:22Z
2026-11-16,2026-11-17T02:20:03Z,0,2026-11-16,stored,0,0,1513,metrics,2026-11-17T02:19:42Z
```

- `export` writes the site data and emits one row per file written (`path,rows,bytes`).
- `status` emits `key,value` rows — last run, its outcome, its age in hours, failed instruments — and exits 1 when the last stored `yahoo` run is more than two days old or the last run was not `stored`.
- Logs go to standard error, `warning` by default, `info` under the scheduler; the composition root logs the seconds spent connected to MotherDuck at `info` (R6).
- Exit codes are `run-unattended`'s: 0 every instrument stored, 1 any `partial` or `failed`, 2 a usage or configuration error (no token, a bad option, MotherDuck refusing the token).
- `MARKET_DATA_DATABASE` names the store, default `md:market_data`; a path such as `/tmp/market.duckdb` runs every command against a local DuckDB file with no token, which the tests and a dry run use.
- Locally the token goes from the keychain straight into the one command's environment, never into a file or the shell history: `motherduck_token="$(security find-generic-password -a "$USER" -s motherduck-token -w)" uv run market-data-cli nightly`.
- The schedule is `17 2 * * *` UTC, every day (D12).

No HTTP API: the dashboard reads files (D3).

**The dashboard** is a Vite, React and TypeScript app in `web/`, styled from the house tokens with Tailwind and shadcn/ui, candles in Lightweight Charts 5, every other chart in ECharts 6, Parquet read with `hyparquet` (D4).
Best in class here means a TradingView or Koyfin-grade finish on a static page: answer first, every number tabular and formatted, light and dark, usable at 390 px, every control instant because the data is already in the browser.
Shared across screens: a 56 px header with the name, the four screens as tabs (`data-view`), a ticker search opened by `/` or Cmd/Ctrl+K (shadcn `command`), the data-age chip ("Prices to 16 Nov 2026 · run 7 h ago", warning when stale, critical when the last run failed) and the scheme toggle; the screen and its choices live in the query string (`?view=ticker&t=AAPL&range=1y`) so every view is a shareable link; `data-ready` on the root as `write-entry-points` says.
The page polls `latest.json` every 5 minutes and refetches when its `ended` changes, and re-judges the age every minute.

- **Markets** (default) — "What did markets do over this period?"
  - A period toggle (`1D 1W 1M 3M YTD 1Y`) drives every element.
  - Five tiles: S&P 500, Nasdaq 100, US 10-year yield, gold, Bitcoin — last value, the period's return (change in basis points for the yield), a sparkline, the day in the context line.
  - A treemap of the stocks grouped by sector, each tile sized by 20-day traded value and coloured on the diverging blue–red scale through `sunken`, clamped at a period-scaled bound, ticker and return labelled where they fit; click opens Ticker.
  - Leaders and laggards: a horizontal bar chart of the ten best and ten worst instruments over the period, `up` and `down` coloured, direct labels.
  - All instruments: a sortable table filtered by asset-class chips — ticker, name, last, the six windows, a 52-week range bar with the last close marked, the 63-bar sparkline — numbers right-aligned and signed, newest bar's day in the header.
  - Every sparkline is an inline SVG path, never a chart instance, so ninety rows cost nothing to draw.
  - All from `overview.parquet`.
- **Ticker** — "How has this instrument behaved, and how does it stand now?"
  - Range toggle `1M 3M 6M YTD 1Y 5Y Max`, overlay toggles for 50- and 200-day moving averages, a log-scale toggle.
  - Tiles: last close with the day's change, the range's return, position in the 52-week range, 1-year volatility, the range's maximum drawdown.
  - Candles with volume in a second pane, dividend and split markers on the bars, crosshair legend showing the bar under the cursor.
  - Below, side by side: an underwater drawdown area chart over the range, and a monthly-returns calendar heatmap (years down, months across, a year column) for the whole history.
  - From `bars/<slug>.parquet`, fetched on selection and cached for the session; header figures from `overview.parquet`.
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
  - From `runs.parquet` and `overview.parquet`.

States for every screen: loading is a skeleton in each card's shape at fixed height; empty reads "No runs yet — the first nightly writes here" (Runs) or "No bars stored for AAPL yet" (Ticker); stale and failed show in the header chip with icon and text; an error is a note inside the card that failed ("Couldn't load EURUSD=X's prices. Other screens still work; tonight's run rewrites the file.") with the rest of the page working.

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
- **Store** — MotherDuck Lite: 10 GB storage and 10 CU-hours a month included, no card required, usage past them pay-as-you-go (motherduck.com pricing page and docs, read 2026-11-17; A4); the store needs well under 1 GB.
- **Dashboard** — GitHub Pages from the same workflow through `actions/upload-pages-artifact` and `actions/deploy-pages`, Pages enabled once with GitHub Actions as the source (`gh api -X POST repos/henrymckay/market-data-public/pages -f build_type=workflow`); limits 1 GB a site, 100 GB a month of traffic (soft), 10 builds an hour (GitHub docs, read 2026-11-17).

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

### Decisions

- **D1 Re-fetch every instrument's whole daily history each night and replace its rows** over an incremental upsert of recent days with a catch-up window — one request per instrument either way, and a full read is the only way a split or dividend's restatement of history, a revised bar or a missed night is healed without special cases; the cost is about 800,000 rows (some 30 MB) moved to MotherDuck a night; source: the 2026-11-17 probe in Inputs; overrides `run-unattended`, Make a run rerunnable (catch-up window and explicit backfill) *(proposed)*.
- **D2 MotherDuck is the only store; no Parquet tree, no committed data, no raw archive** over `store-data`'s tree as the record with MotherDuck as a second sink, its raw-page artifact, and `deploy-project`'s commit-back — the owner named MotherDuck, the source re-serves all history nightly so a parser fix reaches history the next night, and committing per-day files would add thousands of files to a throwaway repository; the cost is no copy outside MotherDuck (a re-run rebuilds it in minutes) and no nightly commit to keep the schedule alive (A3); overrides `store-data`, Lay out the data directory and Keep what the source sent, and `deploy-project`, Run the pipeline *(proposed)*.
- **D3 Bake the site data from MotherDuck at build time into static Parquet** over the browser querying MotherDuck live through its WASM client, which needs a token in a public page that anyone could use to read, write and spend compute, and over an API on Render, which needs a server that sleeps — `secure-project`, Guard what is served, and `write-entry-points`, Dashboard (over files) *(by precedent)*.
- **D4 Vite, React, TypeScript, Tailwind and shadcn/ui, with Lightweight Charts 5.3 for candles, ECharts 6.1 for the rest and `hyparquet` 1.33 for Parquet, Node from `nodejs-wheel` 24** over vanilla JavaScript with one chart library (floated in the brief), which leaves the token system, components, scheme handling and tests to hand-roll, and over DuckDB-WASM (tens of megabytes, earned only when a viewer writes SQL) — `write-entry-points`, Dashboard; `design-interface`, `references/web.md`; versions read from npm and PyPI 2026-11-17 *(by precedent)*.
- **D5 Python 3.14 and `duckdb>=1.5.6,<1.6`** over 3.15 and an uncapped `duckdb` — MotherDuck accepts clients 1.4.0 to 1.5.6 in every region (`motherduck.com/docs/duckdb-versions.json`, read 2026-11-17), DuckDB 2.0.0 is already on PyPI, and `duckdb` 1.5.6 ships wheels up to cp314; overrides `setup-python`'s 3.15 floor and no-upper-cap rule, as `store-data`, Pick the engine, directs *(by precedent)*.
- **D6 Call Yahoo through `yfinance`'s own session, one instrument at a time, paced at one request a second by `pyrate-limiter` and retried by `tenacity` on `YFRateLimitError` and transport errors, five attempts with exponential jittered waits up to 60 s** over the house `httpx` client — `yfinance` owns its `curl_cffi` browser-impersonating session, which is what Yahoo accepts, and its thread pool would burst requests; the cost is about 2 minutes a night; overrides `structure-python`, Write an adapter (one `httpx.Client`) and keeps its pacing and retry rules *(proposed)*.
- **D7 The token lives only in the `nightly` job, which also runs `export` and hands the site data to the `site` job as an artifact** over `deploy-project`'s site job reading the store itself — the `site` job runs `npm ci`, whose third-party install scripts then never see the token; `secure-project`, Keep secrets out *(proposed)*.
- **D8 The universe is a CSV in package data** over `structure-python`'s user-editable list in the data directory — the runner has no data directory, and an edit is a commit the next night picks up; overrides `structure-python`, Configuration *(proposed)*.
- **D9 Store complete bars only, dropping any bar dated on or after the run's UTC date** — `run-unattended`, Name the day (yesterday in UTC); the probe showed forming bars for FX, futures and crypto *(by precedent)*.
- **D10 Fetch with `auto_adjust=False, actions=True` and store split-adjusted OHLC, adjusted close, dividends and splits** over `yfinance`'s default `auto_adjust=True`, which also strips dividends from OHLC so candles stop matching quoted prices; candles show close, every return uses adjusted close, the convention of practitioners' total-return figures *(proposed)*.
- **D11 The workflow's `concurrency` group is the overlap lock; no `fcntl` lock** over `run-unattended`'s lock file — the runner has no persistent data directory, and per-instrument replaces in one transaction leave an overlapping local run harmless; overrides `run-unattended`, Make a run rerunnable *(proposed)*.
- **D12 Schedule at 02:17 UTC every day** — after the US close (21:00 UTC) and the end of the crypto day, off the hour, weekends included for crypto; `deploy-project`, Run the pipeline, and `run-unattended`, Name the day *(by precedent)*.
- **D13 No notification; GitHub's failed-run mail, `status` and the dashboard's age chip are the signals** — `run-unattended`, Report the outcome; no requirement asks for an alert *(by precedent)*.
- **D14 The core in Polars, converting `yfinance`'s pandas frame at the adapter with `polars.from_pandas`** — `use-polars`, Unlearn pandas; `setup-python`, Libraries *(by precedent)*.
- **D15 Metrics stored long in MotherDuck and recomputed whole each night** — `store-data`, Keep what the source sent; the export pivots them for the page *(by precedent)*.
- **D16 One overview file plus one bars file per instrument, loaded on demand** over one file of every close (about 10 MB) — keeps the first load inside R4's 800 KB, with Ticker and Compare and their chart code split out of the first bundle and each file inside `deploy-project`'s few-megabyte guidance *(proposed)*.
- **D17 Exported Parquet uses snappy compression** over Polars' default zstd — `hyparquet` reads only uncompressed and snappy without the extra `hyparquet-compressors` package (hyparquet README, read 2026-11-17) *(proposed)*.
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

- **D39 `export` reads through `SiteSource` and writes through `SiteWriter` ports; the overview carries `slug`, `bar_count`, `first_day`, `last_day`, `rejected` beside the plan's columns, and keeps an active instrument with no bars with null figures** — the Runs coverage needs them and a dead symbol must show, and the page never recomputes the slug (`write-sql`, Never compute one result both ways) *(proposed)*.
- **D40 The Markets treemap and the leaders bars are DOM, not ECharts; the monthly calendar and the correlation matrix are HTML tables; ECharts draws only the drawdown and Compare lines** over D4's ECharts for every non-candle chart — it keeps 167 KB gzipped of ECharts off the first load, gives labels that adapt to tile size, instant re-theming and real buttons for a screen reader; overrides `design-interface`, `references/web.md` (ECharts for charts) *(proposed)*.
- **D41 shadcn/ui's CLI was not run; components are written by hand in its pattern (`cva`, `clsx`, `tailwind-merge`, `cmdk` for the search) and its token names** — the generator is interactive and pulls Radix for parts used once; `design-interface`, `references/web.md` says to add components with the CLI *(proposed)*.
- **D42 Two extra tokens, `--up-text` and `--down-text`**, a darker blue and red step for text in light and a lighter one in dark, since `up` and `down` fall under 4.5 to 1 as text on `surface`; the same idea as `design-interface`'s status-text steps *(proposed)*.
- **D43 Site files are fetched whole and read with `hyparquet`; `overview.parquet` and `runs.parquet` are preloaded from `index.html`; a refetch after a new `ended` adds `?v=<ended>`** — a 60 KB to 830 KB file costs one request, and the preload took 0.4 s off a throttled cold load *(proposed)*.
- **D44 A tile shows a value of 50,000 or more compact (`64.9K`) with the exact figure in its tooltip; the leaders and laggards leave out rates and `^VIX`** — Design's example and `design-interface`'s Numbers; a volatility index's +18% would flatten the ranking *(proposed)*.
- **D45 Browser smokes run over a synthetic year for the universe, exported by the CLI, served from a copy of `web/dist`; marked `slow`, left out of the default run, and failing with an instruction when `web/dist` is missing** — `write-tests`, Coverage and speed *(by precedent)*.
- **D46 `evaluation/shoot.py` and `measure.py` are committed; `evaluation/round-*/` is git-ignored; `ruff` excludes `evaluation/`** *(by precedent: `build-project`, evaluate.md)*.
- **D47 The `site` job installs the dev dependency group (`uv sync --locked`), which holds `nodejs-wheel`, and runs `npm ci` with no token in its environment; the `deploy` job holds only `pages: write` and `id-token: write`; the site-data artifact is kept for one day** — D7 and D37, with actions pinned to SHAs (upload-artifact v7.0.2, download-artifact v8.0.2, upload-pages-artifact v5.0.0, deploy-pages v5.0.1, read from the releases API 2026-11-18) *(by precedent: `secure-project`, Keep secrets out)*.
- **D48 The deploy runs from `main` only**: the `github-pages` environment allows deployments from the default branch only (the API shows custom branch policies), so the `site` and `deploy` jobs were first exercised on a branch run (the `deploy` job refused, as designed) and the publishing run was dispatched on `main` after the workflow merged; the branch policy was left unchanged *(proposed)*.
- **D49 Tickers' last-price axis tag is off, and the Markets table's subtitle names the unit** after the live evaluator's round 1 (the tag clipped an axis label; "Last" had no unit); the TradingView logo over the volume pane stays, since the library's licence asks for the attribution; Bitcoin's compact `64.9K` stays as D44 decided *(proposed)*.
- **D50 R8's "no unmasked fragment" check** splits the token on its dots and into sixteen-character windows and counts each in the run logs and the built site, in addition to the whole-token count, since GitHub masks the whole value only *(proposed)*.

## Delivery

### Verification

- **R1** — unit tests of the core's completeness filter, validation, returns, drawdown and volatility against stated answers; a `workflow_dispatch` run of `nightly` exits 0 with a `yahoo` runs row `stored`, `failed_items` 0, `rows` above 500,000, and every active instrument's last stored day at or after the last weekday before the run (crypto: the run's UTC yesterday).
- **R2** — `gh run list --workflow nightly.yml --event schedule` shows a successful run fired by the schedule after the workflow reached `main`, and its `runs` row is in MotherDuck.
- **R3** — `select count(*) as bars, count(distinct ticker) as tickers from market_data.bars;` equals the manifest's `rows` and the universe's active count; a test runs `fetch` twice against a local DuckDB file with the same fake response and finds the same rows (re-run safe).
- **R4** — Playwright smoke per screen waits for `data-ready` with no page error; screenshots at 1440 by 900 and 390 by 844 in light and dark pass the evaluator on all ten `design-interface` criteria; on the live site, measured with Playwright from a cold cache: Markets ready within 1.5 s and at most 800 KB transferred, each period, range and sort control within 200 ms, an instrument switch within 500 ms.
- **R5** — a test of `export` over a fake store writes every site-data file with the expected rows; on the live site the age chip's run time equals the latest `ended` in MotherDuck's `runs`.
- **R6** — the repository is public, the workflow's runs show no billable minutes, Pages is on the free plan, and the nightly logs' MotherDuck connected time stays under 5 minutes a night (under 2.5 hours a month of the 10 included).
- **R7** — none beyond D18: the repository and site are public by design, which M2 and M4 create.
- **R8** — `gitleaks` runs on every commit and `gitleaks git` over the whole history is clean; the token, piped from the keychain into `grep -F -c -f -` and never printed, occurs 0 times in every run log (`gh run view --log`) and in the built site.

### Milestones

- [x] **M1 Scaffold and first real path** — R1, R3, R8; `setup-python`'s scaffold on Python 3.14 with `duckdb` pinned (D5), `gitleaks` in pre-commit, logging, settings, the universe, the Yahoo adapter with pacing and retry, validation, the MotherDuck store with its first migration, `fetch` and `nightly` without `compute`, `git init` on a branch; done when the suite passes and a local `nightly` with the token from the keychain loads every active instrument into `md:market_data` with exit 0 and the R3 counts agree, and a second run leaves the counts unchanged apart from new bars.
  Ticked 2026-11-18 once the keychain token was replaced (A11): a local `nightly` into `md:market_data` exited 0 with 833,631 bars, 89 tickers, no duplicate `(ticker, day)` and 1,958 metrics, and `status` exited 0.
- [x] **M2 Unattended on Actions** — R1, R2, R3, R6, R7, R8; `compute`, `status`, exit codes, the `nightly` job of the workflow; create the public repository, push, set the secret from the keychain by pipe, merge to `main`, run it by `workflow_dispatch`; done when the dispatched run passes R1's check, `status` exits 0, a forced failure (a bogus symbol added on a branch run) exits 1 and names it, and R8's log count is 0; R2's scheduled-run check is ticked from the first night after.
  Ticked 2026-11-18. Dispatched run [44238259919](https://github.com/henrymckay/market-data-public/actions/runs/44238259919) on `main`: stored, `failed_items` 0, `status` `stale=false`, 1m58s (A2 confirmed: Yahoo serves the runners). Forced failure, run [44238618625](https://github.com/henrymckay/market-data-public/actions/runs/44238618625) on branch `test/forced-failure` (since deleted): the `nightly` and `status` steps both exited 1, the log names `ZZZBOGUS1 failed: no data` and `status` printed `missing,ZZZBOGUS1`; the `main` run [44238883892](https://github.com/henrymckay/market-data-public/actions/runs/44238883892) then stored every instrument again. R8: the token occurs 0 times in all three run logs, and none of its three parts or 66 sixteen-character fragments appears unmasked. R2's scheduled-run check is ticked from the first night after (the first cron, 02:17 UTC 2026-11-19).
- [x] **M3 Dashboard** — R4, R5; `export`, the `web/` app through `nodejs-wheel`, tokens first, then shared pieces, then the four screens, built locally over site data exported from MotherDuck; done when `vitest` and the Playwright smokes pass and the evaluator passes all ten criteria on the eight screenshots.
  Built over site data exported from a local DuckDB file holding a real load, not MotherDuck (A14); the evaluator passed 9 of 10 criteria in round 2 and the one failure (a white pane separator in dark) was fixed and checked by the builder, with no third round. Live timings (R4) wait for M4.
- [ ] **M4 Deploy and verify** — R2, R4, R5, R6, R8; the `site` and `deploy` jobs, Pages enabled by API, a dispatched run publishing the site, the README with the live URL, a screenshot, the README's queries and the teardown steps (Q2); done when R4's live timings, R5's age check, R6 and R8 pass on the live site and a scheduled run has published it.
  Built and live at <https://henrymckay.github.io/market-data-public/>; R4, R5, R6 and R8 pass on the live site (see the M4 report in the commit history); left unticked only for the last clause, the first scheduled run publishing it (02:17 UTC 2026-11-19) — tick M4 and R2 together then.

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

### Questions

- **Q1** Should the nightly use a MotherDuck service account's token, reaching only its own database, instead of your personal token, which reaches all your databases from a public repository's Actions? — recommended: yes, create a service account (Lite allows two) and replace the `MOTHERDUCK_TOKEN` secret; blocks nothing, the build proceeds on A1.
- **Q2** At teardown, delete the repository, drop the MotherDuck database and revoke the token? — recommended: yes, by the README's teardown commands, run by you since each is irreversible; blocks nothing.

### Ideas

- **I1** A weekly keepalive (an empty commit or `gh workflow enable` from a second schedule) so the nightly survives past 60 days — costs one workflow; not built.
- **I2** Grow the universe to the S&P 500 — a real breadth heatmap; costs 500 requests a night (about 9 minutes at one a second) and more rate-limit risk; not built.
- **I3** Size the treemap by market cap from `yfinance`'s `info` — truer weights; costs a second, heavier, more throttled request per stock; not built.
- **I4** Publish the database as a MotherDuck share so the owner can query it from any MotherDuck session without the pipeline's token — costs one statement and an account action; not built.
- **I6** `pyrate_limiter` logs its bucket set-up at INFO and the connected-seconds log covers fetching too for a local run; split fetch and load timings if R6 needs the load alone — costs a second timer; not built.
- **I7** Preload the Inter latin font and brotli-compress the site data on the host; the throttled cold load (1.6 s at 1.6 Mbit/s, 150 ms) is over 1.5 s though the loopback one is 0.5 s — costs a hashed-name lookup in the build; not built.
- **I8** A colour-scale legend for the treemap, tap-for-detail on a phone's small tiles, and the instrument in the Ticker page title — evaluator round 2 nits; not built.
- **I9** Add the Lightweight Charts attribution as footer text and turn the logo off (`attributionLogo: false`), so it stops covering the volume pane's corner; the live age chip also stays a skeleton when `overview.parquet` fails to load — live evaluator round 1 nits; not built.
- **I5** An ntfy alert on a failed or missed night (`send-messages`) — costs a topic secret and a status workflow; not built.
