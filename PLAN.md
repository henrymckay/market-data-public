# market-data-public

Unsigned plan, written 2026-11-17 in autonomous mode for the owner's request, relayed by the planning session; every decision is *(proposed)* or *(by precedent)* until the owner reviews it.
The owner pre-approved exactly these outward steps, so the milestones include them: creating the public GitHub repository `market-data-public` under `henrymckay`, pushing to it, deploying to free hosting tiers that need no card, and using the owner's MotherDuck token.
Extended 2026-11-18 in autonomous mode for the owner's live-read request, relayed by the planning session: R9 and R10 are the owner's signed words; D51 to D65, A15 to A20, Q4 to Q6, I11 to I15 and M5 to M7 are new and unsigned; D3, D16, D17, D43 and D45 are superseded and D7, D39 and D47 narrowed by them.
Extended again 2026-11-18 in autonomous mode for the owner's market-monitor request, relayed by the planning session: R11 to R17 are the owner's words and R18 the brief's constraints; D83 to D107, A22 to A33, Q8 to Q11, I24 to I32 and M8 to M11 are new and unsigned; D1, D13, D21 and A3 are superseded and D20, D55, D60, D79 and R6's check narrowed by them.
The owner pre-approved for this extension: pushing to this repository and merging Claude's own pull requests, deploying through the accounts and repository secrets the project already uses (GitHub Actions and Pages, the Cloudflare Worker, MotherDuck), and sending alert messages to the owner alone over a channel that needs no new account; nothing that needs a new account, costs money or needs a card.

A nightly cloud job that fetches daily prices for about 680 instruments with `yfinance` into MotherDuck, finds swing highs, swing lows and changes of trend on daily, weekly and monthly bars, pushes the ones worth a look to the owner's phone with their base rates, and serves a fast market dashboard that reads the store live through a small API; for the owner, first as an end-to-end test and now as the first piece of a trading assistant.

## Brief

### Goal

The owner wants to see a market-data pipeline and dashboard run end to end in the cloud at no cost, with nothing on their own machine.
Done is observable: a scheduled GitHub Actions run, fired with the owner's machine off, has loaded last night's bars into MotherDuck, and the public Pages URL shows them on a dashboard that passes the design bar and its speed budget.

The owner trades and wants the first piece of a trading assistant: a monitor that watches a broad universe and tells them when price structure turns, so they spend their attention only on charts worth opening.
Done is observable: a scheduled nightly over about 680 instruments stores that night's signals on daily, weekly and monthly bars with their base rates over all stored history; the owner's phone receives that night's alerts, each readable in seconds; and a tap opens the dashboard's Ticker view at the signal with the swings and the level drawn.

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
- **Data version** — the `ended` of the last stored `yahoo` run the API has seen; it keys the API's cache and the page's refetch (D53); from M9 the `ended` of the last stored `metrics` run, the nightly's last stage (D96).
- **Featured** — the 89 instruments of the first universe, which the headline screens and the warm job keep using (D86, D98).
- **Timeframe** — `d`, `w` or `m`: the daily bars as stored, or weekly (Monday to Sunday) and calendar-monthly bars built from them; a weekly or monthly bar counts only once its period has ended (D85).
- **Period bar** — one instrument's open, high, low, close, adjusted close and volume over one week or month, keyed by the period's first calendar day, with `last_day` its last trading day.
- **ATR** — average true range over 14 bars of a timeframe (D83).
- **Swing high** and **swing low**, together **pivots** — a bar's high (low) that a later close retreated from by the swing threshold; confirmed on that close and never moved after (D83).
- **Swing threshold** — `k × ATR`, with `k` per timeframe in the rules.
- **HH, LH, HL, LL** — a swing high labelled higher or lower than the previous swing high, a swing low higher or lower than the previous swing low; `EH` and `EL` when equal.
- **Structure** — an instrument's trend state on a timeframe: `up` (last swing high HH, last swing low HL), `down` (LH and LL), `turning_up`, `turning_down` or `none` (D84).
- **Break** — `break_up`: in a downtrend, the first close above the last lower high, the owner's "first higher high" (practitioners' bullish change of character); `break_down`, its mirror, the "first lower low".
- **Confirmation** — `confirm_up`: after a `break_up`, the next swing low confirmed above the downtrend's last low, the owner's "first higher low after the higher high"; `confirm_down`, its mirror, the "first lower high".
- **Failure** — `fail_up`: a close below the downtrend's last low, or a next swing low at or under it, before a confirmation; `fail_down` its mirror; stored and measured, never messaged.
- **Signal** — one break, confirmation or failure on one instrument, timeframe and bar, keyed by `id`, `<ticker>|<timeframe>|<event>|<day>`.
- **Level** — the price a signal turned on: the broken swing for a break, the new swing for a confirmation; **stop** — the price a close beyond would invalidate it.
- **Score** and **grade** — the points the rules give a signal and the letter they make, `A`, `B` or `C` (D90).
- **Outcome** — a signal's forward return, best and worst excursion and whether its stop held, after each horizon of its timeframe's bars (D89).
- **Base rate** — how signals of one event, timeframe and asset class did at a horizon over all stored history; **baseline** — how any bar of that asset class and timeframe did at the same horizon; **edge** — the first's mean signed return minus the second's.
- **Alert** — a message sent to the owner: a **push** for one signal, a **digest** for one asset class's signals of a night, or a **health** message when the pipeline's state changes (D91, D93).
- **Topic** — the ntfy topic the alerts go to; whoever knows it can read and post, so it is a secret.
- **Rules** — `src/market_data/data/transform/monitor.yaml`, every parameter of the monitor, hashed into each signal (D95).

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
- **R11** "Extend this project with a market monitoring service that messages me when something worth looking at happens ... across a broad universe of symbols, split by asset type" (the owner, 2026-11-18).
  - Cost: about 680 instruments, eight times the requests to Yahoo (about 12 minutes a night at one a second), an S&P 500 list kept current from Wikipedia by a monthly workflow, a nightly fetch that loads only recent days (D87, superseding D1), and screens and API bodies that carry 680 rows; a narrower universe saves all of it.
- **R12** "I get message alerts when technical triggers fire around highs and lows and changes of direction."
  - Cost: a push channel (D91) with its topic as a new secret, a `notify` command and job, an `alerts` table so each signal is sent once, and the owner subscribing once (Q9).
- **R13** "A break upwards out of a downtrend (the first higher high), the consolidation of that move (the first higher low after the higher high), the mirror of both in the breakdown direction."
  - Cost: a swing and trend-state engine in the core (D83, D84) whose signals never change once emitted, proved by a property test; the definitions are the plan's reading of these words (A22).
- **R14** "And all of it on multiple timeframes."
  - Cost: weekly and monthly bars built from the stored daily ones with their own swing scale (D85), at no extra fetch; intraday stays under Not yet.
- **R15** "What it is for: I trade, and this is the first piece of a trading assistant. An alert should let me decide in a few seconds whether to open the chart."
  - Cost: graded, ranked messages (D90, D94) carrying the level, the invalidation, the higher-timeframe trend and the base rate in four lines, a chart image on the strongest (D105), and a tap that opens the Ticker view at the signal with the swings drawn (M11).
- **R16** "These are unbacktested signals on public data only; nothing here places a trade or knows what I hold."
  - Cost: every input stays public and no broker credential exists; Claude backtests the signals anyway (D88, D89), since base rates need no new data, and every alert shows its base rate beside the baseline.
- **R17** "What I am leaving to you: how a high, a low and a change of direction are best defined, which timeframes, how large the universe can sensibly be, which events deserve a message and in what form, and how I refine that over time."
  - Cost: every signal stored with its rules' hash and its forward outcomes, base rates recomputed nightly over all history, the rules in one YAML file a commit changes, and a dry run that compares rule sets before one is committed (D95).
- **R18** Alert messages go to the owner alone over a channel that needs no new account; no new account, nothing that costs money or needs a card; no token printed, logged or committed (from the planning brief).
  - Cost: ntfy.sh's public server used anonymously within its 250 messages a day (D91), and the topic held as a secret as R8 holds the token.

### Not yet

- **A universe beyond about 680** — the Russell 1000, European and Asian stocks, Nasdaq-100 membership kept by a feed; earned by base rates showing the signals worth more breadth, since each instrument is a request against Yahoo's limit (I30).
- **Intraday prices and timeframes** — 1-hour and 4-hour bars; earned by daily and weekly base rates showing an edge worth acting on within a day and by the owner asking, since each run costs about 700 more requests and an hourly schedule (D85, I26).
- **Trading, positions and orders** — nothing places a trade or knows what the owner holds (R16); earned only by a signed decision naming the account, read-only first (`secure-project`, Hold a credential for an account with money in it).
- **Owner feedback on alerts** — "useful" and "noise" buttons that train the grades; earned once a few weeks of alerts exist, since it needs a write path on a read-only API (I25).
- **Fundamentals and market caps** — earned by the heatmap needing true weights (I3).
- **A general API** — a `/v1/` prefix, date-range or filter parameters, or SQL from the caller; earned by a second client (`write-entry-points`, HTTP surface), since each parameter multiplies the cache keys D55 bounds; D97 adds two fixed endpoints, not parameters.
- **Access control on the site** — earned by data that is not public.

## Design

### Inputs

- **Yahoo Finance through `yfinance` 1.8** — one `Ticker.history(period="max", interval="1d", auto_adjust=False, actions=True)` request per instrument, returning a pandas frame indexed by an exchange-local midnight timestamp with `Open`, `High`, `Low`, `Close`, `Adj Close`, `Volume`, `Dividends`, `Stock Splits` (and `Capital Gains` for funds, dropped).
  Probed 2026-11-17: `^GSPC` 24,837 bars from 1927-12-30, `AAPL` 11,575, `SPY` 8,508, `EURUSD=X` 5,958, `BTC-USD` 4,445; about 1 s a request after an 8 s first one; FX, futures and crypto already carry a forming bar for today.
  About 90 requests a night, roughly 800,000 bars in all.
  From M8, about 680 instruments: each night one `period="1mo"` request per instrument and a `period="max"` one where the store has none or the overlap disagrees, about 700 requests, and every instrument's whole history on Sundays (D87); roughly 6 million bars in all.
  The calibration of 2026-11-18 fetched 20 histories from the planning machine at about 1 s each.
  No credential; Yahoo's limit is unpublished and its blocks reported to last hours, so the source is untrusted for availability, and values are revised when splits and dividends land.
  Class: public, by the owner's statement (R7, D18).
- **The universe** — `src/market_data/data/transform/universe.csv`, columns `ticker,name,asset_class,sector,quote_type,active`, about 90 rows (D8, A6); class public.
  From M8 it gains `featured` and `source` (`curated` or `sp500`) and about 680 rows (D86).
- **Wikipedia's S&P 500 list** — `https://en.wikipedia.org/wiki/List_of_S%26P_500_companies`, the table `id="constituents"` with `Symbol`, `Security` and `GICS Sector`; read once a month by `universe sync` with a generic `User-Agent`; 503 rows on 2026-11-18; untrusted text, so each symbol is checked against a pattern before it enters the CSV; class public (A29).
- **The rules** — `src/market_data/data/transform/monitor.yaml`: swing thresholds, horizons, score points, grade bounds and what is sent (D95); class public.
- **The ntfy topic** — generated once, kept in the macOS keychain under service `ntfy-market-monitor` and as the repository secret `NTFY_TOPIC`, read into the environment as `NTFY_TOPIC`; a secret, since it is the only key to the channel (D104).
- **The MotherDuck token** — the owner's access token, in the macOS keychain under service `motherduck-token`, and on Actions the repository secret `MOTHERDUCK_TOKEN`, read into the environment as `motherduck_token` (`store-data`); a secret for an account that can bill by use, so `secure-project`'s money rules apply (one consumer, keychain, rotation dated in Runs on).
- **The API's MotherDuck token** — a second token, for the API alone (D57): the service account `market_data_api`'s, reading `market_data` through a read-only share (D77); the repository secret `MOTHERDUCK_API_TOKEN`, copied by the deploy job into the Worker secret `MOTHERDUCK_TOKEN`; read-write at the account level, since Lite offers no read-only token (A16).
- **MotherDuck's Postgres endpoint** — `pg.eu-west-1-aws.motherduck.com:5432` (the account's region, from `md_user_info()` 2026-11-18), user `postgres`, the token as password, TLS required, DuckDB SQL with `$1` binding; labelled preview (A20).
  Probed live 2026-11-18 with `psycopg` 3 and the keychain token: connect 1.2–1.7 s; a parameterised year of `AAPL` bars, 252 rows, 0.35–0.70 s; all 1,958 `metrics` rows 0.29 s; `^GSPC`'s 24,838 bars as rows 8.7–9.3 s, as one columnar JSON string (2.9 MB, 488 KB gzipped) 2.5–12.4 s, timed from the planning machine, far from `eu-west-1`.

### Data flow

1. **Universe** — one row is an instrument, keyed by `ticker`; the active rows become the list to fetch and the `tickers` table.
2. **Fetched** — one row is a bar, keyed by `ticker` and `day`; the Yahoo adapter maps each instrument's frame into `port.BARS` with `polars.from_pandas`, dates each bar by its index's local date, and returns a `Fetched` record of bars, rejected rows and failed instruments. (IO)
   From M8 each instrument's last month is fetched, and its whole history where the store holds none, its last stored day is over 25 days old, the overlap disagrees with the store or the run is `--full`; the store replaces its rows from the first fetched day on (D87).
3. **Complete and valid** — the same grain; the core drops bars on or after the run's UTC date (D9) and splits the rest into valid bars and rejected rows with a reason: a null or non-finite close, a non-positive price on a `price` instrument, high below low, a duplicate day.
4. **Stored** — the same grain in MotherDuck; for each instrument that answered, its rows in `bars` and `rejected` are replaced in one transaction, instruments that failed keep last night's rows, and a `runs` row is appended. (IO)
5. **Metrics** — one row is one metric for one instrument, keyed by `ticker` and `metric`; the core computes every window's return and change, the 52-week high and low, 1-year volatility, 1-year maximum drawdown and 20-day traded value from `bars` read back from the store, and the store replaces `metrics` whole. (IO at both ends)
6. **Overview** — one row per instrument, keyed by `ticker`; in the same `compute` stage the core pivots the metrics beside the instrument's identity, coverage and a 63-bar adjusted-close sparkline (`transform/site.py`, unchanged), and the store replaces `overview` whole (D54). (IO)
7. **API responses** — on a request whose response is not cached for the current data version, the Worker runs that endpoint's fixed query on MotherDuck, which returns the whole JSON body as one string, and caches it in KV under the version (D52, D53); a cron every 15 minutes reads the latest stored run to move the version. (IO)
8. **Screens** — `web/src/lib/data.ts` fetches the API's JSON into the same `Instrument`, `Run`, `Series` and `Latest` shapes the Parquet gave; range-dependent figures (a chosen range's return, drawdown, correlations) are computed in `web/src/lib/` from the bars, and every figure the overview already holds is read from it, never recomputed (`write-sql`, Never compute one result both ways).
9. **Period bars** — one row per instrument, timeframe and period; the `period_bars` view groups `bars` by ISO week and calendar month (first open, highest high, lowest low, last close and adjusted close, summed volume, `last_day`), the one definition the core and the chart both read (D85); the core drops a period whose end is on or after the run's UTC date. (IO)
10. **Pivots and structure** — one row per confirmed swing, keyed by `ticker`, `timeframe`, `day` and `kind`; the core runs the swing kernel over each instrument's daily and period bars in order, on split-adjusted high, low and close (D102), labelling each swing and moving the structure bar by bar (D83, D84, D103).
11. **Signals** — one row per signal, keyed by `id`, emitted by the same pass and then scored: the next timeframe up's structure as of its last bar complete before the signal, the run of lower highs (higher lows) the break ended, the bar's volume against its 20-bar mean and the margin past the level give the score and grade (D90).
12. **Outcomes and base rates** — one row per signal and horizon from adjusted close, high and low after the signal bar, then one row per event, timeframe, asset class, grade and horizon beside the any-bar baseline (D89); the `signals` stage replaces `pivots`, `signals`, `outcomes`, `signal_stats` and `structure` whole in one transaction and appends its run (D88). (IO)
13. **Alerts** — one row per signal sent; `notify` takes the signals known in the last four days that no `alerts` row names, keeps the events, grades and asset classes the rules send, composes pushes, each with a chart image, and digests per asset class, sends them to the topic and appends an `alerts` row per signal sent (D91, D92, D94); it also compares `status`'s verdict with `alert_state` and sends a health message when it changes (D93). (IO)

From M9 the nightly runs fetch, then signals, then compute, so the overview carries each instrument's structure and the API's data version moves only after the last stage (D96).

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

From M8, `tickers` and `overview` gain `featured` (boolean) and `source` (varchar, `curated` or `sp500`) by migration `0004`; from M9 `overview` gains `trend_d`, `trend_w` and `trend_m` (varchar, the structure's state per timeframe, null without one) by migration `0005`, which also creates the tables and view below (D88).
All are replaced whole by the `signals` stage except `alerts`, which is append-only, and `alert_state`, which `notify` and `status --alert` replace (migration `0006`, M10).

`period_bars`, a view over `bars`, one row per instrument, timeframe and period (D85):

| column | type | meaning |
|---|---|---|
| adj_close | double | last adjusted close in the period |
| close | double | last close in the period |
| day | date | the period's first calendar day (Monday, or the 1st); key |
| high | double | highest high |
| last_day | date | the period's last trading day stored |
| low | double | lowest low |
| open | double | first open |
| ticker | varchar | key |
| timeframe | varchar | `w` or `m`; key |
| volume | bigint | summed volume, null when every day's is null |

`signals`, key `id` (D84, D90):

| column | type | meaning |
|---|---|---|
| aligned | boolean | the next timeframe up's structure pointed the signal's way at its last bar complete before `day`; null for monthly |
| atr | double | the ATR at the signal bar |
| close | double | the signal bar's close |
| day | date | the signal bar: its day, or its period's first day |
| direction | varchar | `up` or `down`, the way the signal points (`fail_up` points down) |
| event | varchar | `break_up`, `confirm_up`, `fail_up`, `break_down`, `confirm_down` or `fail_down` |
| grade | varchar | `A`, `B` or `C` |
| held_to_date | boolean | no close beyond `stop` since the signal bar, as of the last bar |
| id | varchar | `<ticker>\|<timeframe>\|<event>\|<day>`; key |
| known | date | the signal bar's last trading day, when it could first be acted on |
| level | double | the price the signal turned on |
| margin_atr | double | a break's close past its level, or a confirmation's new swing past the stop it replaces, in ATR, positive the signal's way |
| return_to_date | double | adjusted-close return from the signal bar to the last bar, a fraction, unsigned |
| rules | varchar | the first 12 hex digits of the rules' SHA-256 |
| score | integer | the points D90 gives |
| stop | double | the invalidation price |
| swing_atr | double | the height of the leg the level ends, from the opposite swing, in ATR |
| ticker | varchar | |
| timeframe | varchar | `d`, `w` or `m` |
| trend_swings | integer | lower highs in a row before a `break_up` (higher lows before a `break_down`), carried to its confirmation or failure |
| volume_ratio | double | the bar's volume over the mean of the 20 bars before it; null without volume |

`pivots`, key `(ticker, timeframe, day, kind)`: `confirmed` (date, the confirming bar's day or period), `day` (date, the swing's bar), `kind` (`high` or `low`), `label` (`HH`, `LH`, `EH`, `HL`, `LL`, `EL`, null for the first of its kind), `price` (double), `ticker`, `timeframe`.

`outcomes`, key `(id, horizon)`, complete horizons only (D89): `end_day` (date), `held` (boolean), `horizon` (integer, bars of the signal's timeframe), `id`, `mae` and `mfe` (double, worst and best excursion from the signal's close, fractions, `mae` negative), `return` (double, adjusted-close return, unsigned), `signed_return` (double, positive the signal's way).

`signal_stats`, key `(asset_class, event, grade, horizon, timeframe)`, with `all` as an asset class and a grade: `baseline_hit` and `baseline_mean` (the any-bar rate of moving the event's way and its mean signed return), `edge` (`mean_return` minus `baseline_mean`), `held_rate`, `hit_rate`, `mae_median`, `mean_return`, `median_return`, `mfe_median` (double), `n` (bigint), `rules` (varchar).

`structure`, key `(ticker, timeframe)`: `last_high` and `last_low` (double, the last swings' prices), `since` (date, when the state was entered), `state`, `ticker`, `timeframe`.

`alerts`, append-only: `id` (the signal's, or `health`), `kind` (`push`, `digest` or `health`), `message` (ntfy's message id), `sent` (timestamp with time zone), `title` (varchar).
`alert_state`, one row: `changed` (timestamp with time zone), `detail` (varchar), `key` (`health`), `state` (`healthy` or `unhealthy`).

**API responses** — JSON built by DuckDB on MotherDuck, cached in the Workers KV namespace `market-data-cache` under `<data version>/<endpoint>` with a three-day expiry, served by the Worker (Interface); class public.

**Site data** — *(retired by D59 in M6)* written by `export` into `web/public/data/` on the runner, built into the Pages site, never committed; Parquet with snappy compression (D17); class public.

- `overview.parquet` — one row per instrument: the `tickers` columns, every metric as its own column, and `spark` (list of 63 doubles); about 60 KB.
- `bars/<slug>.parquet` — one file per instrument (`slug` is the ticker lower-cased with `^`, `=` and `.` removed: `gspc`, `eurusdx`), every column of `bars` but `ticker` and `fetched`; 50 to 600 KB each, about 20 MB in all.
- `runs.parquet` — the last 90 runs.
- `latest.json` — the last `yahoo` run's row, polled by the open page.

**GitHub Pages site** — `https://henrymckay.github.io/market-data-public/`, replaced by each deploy of the front end (D58), holding code and no data once M7 lands; class public.

**Alert messages** — JSON POSTed to `https://ntfy.sh/`, or a PNG PUT to `https://ntfy.sh/<topic>` with its text as query parameters, cached on ntfy.sh for 12 hours and attachments for 3; read in the owner's ntfy app; one per push, digest or health change (Interface); class public, public data only, with the topic a secret (D104).

**`universe.csv` commits** — the monthly `universe.yml` run commits the synced CSV to `main` when the S&P 500's members changed (D100); class public.

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
- Logs go to standard error, `warning` by default, `info` under the scheduler; the composition root logs the seconds spent inside store calls, connecting included, at `info` as "Store busy for N s" (R6, D101).
- Exit codes are `run-unattended`'s: 0 every instrument stored, 1 any `partial` or `failed`, 2 a usage or configuration error (no token, a bad option, MotherDuck refusing the token).
- `MARKET_DATA_DATABASE` names the store, default `md:market_data`; a path such as `/tmp/market.duckdb` runs every command against a local DuckDB file with no token, which the tests and a dry run use.
- Locally the token goes from the keychain straight into the one command's environment, never into a file or the shell history: `motherduck_token="$(security find-generic-password -a "$USER" -s motherduck-token -w)" uv run market-data-cli nightly`.
- The schedule is `17 2 * * *` UTC, every day (D12).

The monitor adds these commands (M8 to M10):

```bash
uv run market-data-cli nightly --log-level info
uv run market-data-cli nightly --full --log-level info
uv run market-data-cli fetch --full AAPL
uv run market-data-cli signals --log-level info
uv run market-data-cli signals --rules /tmp/alt.yaml --dry-run --format table
uv run market-data-cli notify --log-level info
uv run market-data-cli notify --dry-run
uv run market-data-cli status --alert
uv run market-data-cli universe sync
uv run market-data-cli universe sync --check
```

- `nightly` fetches each instrument's last month (D87), then runs `signals`, then `compute` (D96), and prints three manifest rows, `yahoo`, `signals` and `metrics`; `--full` fetches every instrument's whole history, which the workflow passes on Sundays; `fetch --full` does so for the named instruments.
- `signals` recomputes pivots, signals, outcomes, base rates and structure over every stored bar and replaces them, printing its manifest row (`rows` is the signals stored); `--rules PATH` reads another rules file, and `--dry-run` writes nothing and prints the base rates for asset class and grade `all` as `event,timeframe,horizon,n,hit_rate,baseline_hit,edge,held_rate`, `--format table` aligned, so two rule sets compare by running it twice (D95).
- `notify` sends what Data flow 13 selects and prints one CSV row a message, `kind,title,signals,status` with `status` `sent` or `failed`; it exits 0 when every send succeeded or nothing was due, 1 when any failed, 2 when `NTFY_TOPIC` is not set; `--dry-run` needs no topic, prints every message whole (title, message, tags, priority, click, actions, attachment name) and records nothing.
- `status --alert` also sends a health message when its verdict differs from `alert_state`, and records the new state; its exit code is `status`'s.
- `status` judges the `signals` source as it judges `metrics`: healthy only when its last run stored (D35).
- `universe sync` reads Wikipedia's S&P 500 table, adds new members as `source=sp500` rows, marks leavers `active=false`, leaves `curated` rows alone, rewrites the CSV sorted by asset class then ticker, and prints `added,removed` counts; `--check` writes nothing and exits 1 when the list differs; either fails without writing when the table has under 495 or over 510 rows or a symbol fails `^[A-Z][A-Z0-9.]{0,9}$` (before `.` becomes `-`).
- `NTFY_TOPIC` is read once at the composition root as a `SecretStr`, and the log formatter redacts it as it does the token (D32); the sender never logs a URL.

**Messages** (D94), in the owner's words for the events — "first higher high", "first higher low", "first lower low", "first lower high" — with prices formatted as the page formats them and dates as `17 Nov 2026`.
Best in class here means a trader's alert service, a TradingView alert with the chart attached: the verdict in the title, the level and what proves it wrong in the first line, the evidence after, and one tap to a chart that already shows the swings.

A push, one per signal graded `A`, at most ten a night, ntfy priority 4:

```text
Title:   NVDA weekly: first higher high (A)
Message: Closed 145.30 above the lower high 142.10 (+0.6 ATR) after 4 lower highs.
         Invalid below 128.40 (-11.6%). Volume 1.8x. Monthly trend up.
         Base rate: 66% rose within 13 weeks (n 412); any week 61%.
Tags:    chart_with_upwards_trend, stock
Click:   https://henrymckay.github.io/market-data-public/?view=ticker&t=NVDA&tf=w&range=5Y&sig=2026-11-10.break_up
Actions: view, Chart, <the click URL>; view, All signals, <the Signals screen for that day>
Attach:  nvda-w.png, the last 80 bars of the timeframe with swings labelled and the level and stop drawn
```

A digest, one per asset class with a signal graded `B` or better that night, priority 3:

```text
Title:   Stocks: 9 signals on 17 Nov 2026, 2 graded A
Message: A NVDA W first higher high 142.10, base 66%
         A AMD  D first higher low  151.20, base 58%
         B JPM  D first lower low   241.00, base 44%
         ...
         +14 graded C on the Signals screen
Click:   https://henrymckay.github.io/market-data-public/?view=signals&cls=stock&day=2026-11-17
Actions: up to three, view, <ticker>, <its chart>, for the three highest scores
```

A health message on a change of state only: `Market data: nightly partial` at priority 5 with `yahoo partial: 7 of 681 failed (ABC, DEF, GHI +4); signals and metrics stored.` and the run's URL as its click; then `Market data: healthy again` at priority 3.
A title holds at most 60 characters, a push's message at most four lines and 300 bytes, a digest's at most 12 lines and 1,500 bytes, with the rest counted in a last line; the click's `range` is `1Y` for daily, `5Y` for weekly and `Max` for monthly.
The base rate is `signal_stats` for the signal's event, timeframe and asset class at the timeframe's primary horizon with grade `all`, or asset class `all` where that has under 30 signals.

**The API** is a Cloudflare Worker in `api/` named `market-data-api`, served at `https://market-data-api.<subdomain>.workers.dev` (the subdomain is the owner's account's, known at M7), read-only, with four data endpoints and a docs page (D51, D55):

| method | path | returns |
|---|---|---|
| GET | `/api/latest` | the last stored `yahoo` run, `{"day": "2026-11-17", "ended": "2026-11-18T02:19:41Z", "outcome": "stored", "rows": 833631}`, or `null` before any; `Cache-Control: public, max-age=60` |
| GET | `/api/overview` | an array of one object per instrument with the `overview` table's columns (Outputs), sorted by `ticker`; about 90 objects, 181 KB measured 2026-11-18 |
| GET | `/api/runs` | an array of the last 90 `runs` rows, newest first, with the `runs` table's columns, times as `2026-11-18T02:19:41Z` |
| GET | `/api/bars/{slug}` | one instrument's whole history, oldest first, as columns: `{"ticker": "^GSPC", "day": ["1927-12-30", …], "open": […], "high": […], "low": […], "close": […], "adj_close": […], "volume": […], "dividend": […], "split": […]}`; `slug` must be one of `/api/overview`'s, else 404; at most 2.9 MB, 490 KB compressed (`^GSPC`) |
| GET | `/api/signals` | from M11, signals known in the last 120 days, newest `known` first then highest `score`, at most 5,000, each with the `signals` columns plus `name`, `asset_class` and `slug` (D97) |
| GET | `/api/stats` | from M11, every `signal_stats` row (D97) |
| GET | `/` | the docs page: each endpoint with an example request, response and error (D64) |

- From M9, `/api/latest` adds `version`, the `ended` of the last stored `metrics` run, which the Worker keys its cache on (D96).
- From M11, `/api/bars/{slug}` adds `weekly` and `monthly` (the `period_bars` columns as arrays, like the daily ones), `pivots` (an array of `{timeframe, kind, label, day, price, confirmed}`) and `signals` (the instrument's signals over all history as `{id, timeframe, event, day, known, level, stop, grade, score}`).
- From M8, the Worker resolves a slug through a `slugs` body (`{"aapl": "AAPL", …}`, from `slugs.sql`, cached under the version) instead of parsing the overview, which grows to about 1.4 MB (D97).

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
- **Signals** (M11, a fifth tab between Compare and Runs) — "What turned last night, and how have such turns done before?" (D99).
  - The asset-class chips as on Markets, a timeframe toggle `All D W M`, an event toggle (`All`, the four sent events in the owner's words, `Failures`), a grade toggle `A`, `A+B` (default), `All`, and a day picker defaulting to the latest `known`; all in the query string (`view=signals&cls=stock&tf=w&ev=break_up&grade=ab&day=2026-11-17`).
  - Four tiles: signals on the day, graded A on the day, weekly and monthly on the day, and the share of the last 90 days' signals whose stop has held so far, each with its count in the context line.
  - Recent signals: a table, newest first then by score — known, ticker, name, timeframe, event with an up or down icon and words, grade chip, level, stop, margin in ATR, base rate at the primary horizon, return to date and held — paginated at 50 rows; a row opens Ticker at the signal.
  - Base rates: a table per event and timeframe for the chosen asset class (n, hit rate, any-bar rate, edge, held rate, median best and worst excursion) at each timeframe's primary horizon, with a horizon toggle; beside it a horizontal bar chart of edge by event and timeframe in percentage points, `up` and `down` coloured from a zero line, DOM bars as D40 draws the leaders.
  - A caption under the base rates: "All stored history of today's members: survivorship flatters the long side, and the rules were set on this data."
  - From `/api/signals` and `/api/stats`.
- **Ticker**, from M11, also shows structure (D99).
  - A timeframe toggle `D W M` (`tf`) switches the candles to `weekly` or `monthly` from the bars body; ranges stay as they are.
  - Each swing of the timeframe is a series marker labelled `HH`, `LH`, `HL` or `LL` above or below its bar in `muted`; each signal is an arrow marker in `up` or `down` with its event's short words.
  - With `sig`, the chart scrolls to the signal, draws the level as a dashed `accent` price line titled "Level" and the stop as a dotted `down` (or `up`) line titled "Invalid", and a note above the chart states the signal in the push's first line.
  - A card under the chart lists the instrument's signals on the timeframe with grade, level, return to date and held.
- **Markets**, from M8, carries about 680 instruments (D99).
  - The table is paginated at 100 rows with the asset-class chips and sort as now, and from M9 gains a Trend column: three chips, `D`, `W`, `M`, each an arrow up, down, turning or a dash with its state in words for a screen reader.
  - The treemap holds every stock of the S&P 500 by sector; the headline tiles and the leaders and laggards are unchanged.

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

Signals at desktop width (M11); at 390 px the tiles go two by two, the toggles wrap and both tables scroll inside their cards:

```text
+--------------------------------------------------------------------------------------------+
| Market data  Markets Ticker Compare [Signals] Runs   [Search /]  Prices to 17 Nov . 3 h ago |
+--------------------------------------------------------------------------------------------+
| [All] Indices ETFs Stocks Rates FX Commodities Crypto     Day [17 Nov 2026 v]               |
| Timeframe [All] D W M   Event [All] Higher high Higher low Lower low Lower high Failures     |
| Grade A [A+B] All                                                                           |
| +----------------+ +----------------+ +----------------+ +-----------------------+         |
| | Signals        | | Graded A       | | Weekly, monthly| | Stop held, 90 days    |         |
| | 14             | | 3              | | 5              | | 58%                   |         |
| | on 17 Nov 2026 | | 2 pushed       | | 4 W, 1 M       | | of 1,204 signals      |         |
| +----------------+ +----------------+ +----------------+ +-----------------------+         |
| +----------------------------------------------------------------------------------------+ |
| | Recent signals                                                                         | |
| | Known        Ticker  Name     TF  Event                Grade   Level    Stop  Base  Since | |
| | 17 Nov 2026  NVDA    Nvidia   W   ^ First higher high  A      142.10  128.40  66%  +2.3% | |
| | 17 Nov 2026  JPM     JPMorgan D   v First lower low    B      241.00  252.30  44%  -0.4% | |
| +----------------------------------------------------------------------------------------+ |
| +-------------------------------------------------------+ +------------------------------+ |
| | Base rates at the primary horizon      [5] [20] [60]  | | Edge over any bar (pp)       | |
| | Event              TF  n      Hit   Any   Edge  Held  | |  Higher high D   |#   +0.2   | |
| | First higher high  D   2,980  56%   56%  +0.2%  71%   | |  Higher high W   |##  +0.6   | |
| | First higher low   W     612  70%   61%  +3.1%  64%   | |  Lower low D   #|     -0.3   | |
| +-------------------------------------------------------+ +------------------------------+ |
| All stored history of today's members: survivorship flatters the long side, and the rules   |
| were set on this data.                                                                      |
+--------------------------------------------------------------------------------------------+
```

Its states: loading is a skeleton per card; empty reads "No signals on 17 Nov 2026 for stocks — try All or another day"; before the first monitor run, "No signals yet — the first nightly with the monitor writes here"; an error is the card's note with the rest working.

### Runs on

- **Pipeline and export** — GitHub Actions in the public repository `henrymckay/market-data-public`, free for public repositories; one workflow `.github/workflows/nightly.yml` from `deploy-project`'s `references/github-actions.md`, with jobs `nightly` (fetch, compute, export, upload the site data as an artifact), `site` (build with `nodejs-wheel`'s `npm`, upload the Pages artifact) and `deploy`; `timeout-minutes: 30`, `concurrency: group: data` without cancelling.
  Limit that matters: a public repository's schedule is disabled after 60 days without repository activity (GitHub docs, read 2026-11-17; A3).
  Secret: `MOTHERDUCK_TOKEN`, set with `security find-generic-password -a "$USER" -s motherduck-token -w | gh secret set MOTHERDUCK_TOKEN --repo henrymckay/market-data-public`, exposed to the `nightly` job's run steps only (D7); rotate at teardown or by 2027-02-15, whichever comes first.
  From M7 the `nightly` job drops `export` and the site-data artifact, and a `warm` job with no secret follows it (D60).
- **Store** — MotherDuck Lite: 10 GB storage and 10 CU-hours a month included, no card required, usage past them pay-as-you-go (motherduck.com pricing page and docs, read 2026-11-17; A4); the store needs well under 1 GB.
- **Dashboard** — GitHub Pages from the same workflow through `actions/upload-pages-artifact` and `actions/deploy-pages`, Pages enabled once with GitHub Actions as the source (`gh api -X POST repos/henrymckay/market-data-public/pages -f build_type=workflow`); limits 1 GB a site, 100 GB a month of traffic (soft), 10 builds an hour (GitHub docs, read 2026-11-17).
  From M7 the `site` and `deploy` jobs move to `.github/workflows/site.yml`, run on a push to `main` touching `web/**` and on dispatch, with `VITE_API_URL` from the repository variable `API_URL` (public, not a secret); the nightly no longer builds the site (D58, D59).
- **API** — Cloudflare Workers Free (no card): 100,000 requests a day (Error 1027 past it, reset 00:00 UTC), 10 ms of CPU a request and a cron invocation, 50 subrequests a request, 6 open connections, 128 MB, 5 cron triggers an account (developers.cloudflare.com, Workers limits, read 2026-11-18); KV Free: 100,000 reads, 1,000 writes and 1,000 deletes a day, 1 GB (KV pricing, read 2026-11-18).
  Deployed by `.github/workflows/api.yml` on a push to `main` touching `api/**` and on dispatch, through `cloudflare/wrangler-action` v4.1.3 pinned to its commit SHA (released 2026-09-24), with the repository secrets `CLOUDFLARE_API_TOKEN` (the owner's, template "Edit Cloudflare Workers", scoped to their one account) and `CLOUDFLARE_ACCOUNT_ID`; the deploy step names `MOTHERDUCK_TOKEN` in wrangler-action's `secrets:` input, which uploads it from the step's environment before `wrangler deploy` runs, so the first deploy finds the secret `wrangler.toml` requires (D61, D74).
  `wrangler.toml`: `compatibility_date = "2026-11-18"`, `compatibility_flags = ["nodejs_compat"]`, `[vars]` `MOTHERDUCK_HOST = "pg.eu-west-1-aws.motherduck.com"`, `MOTHERDUCK_DATABASE` (the share's alias after Q4, else `market_data`), `ALLOWED_ORIGIN = "https://henrymckay.github.io"`, a `[[kv_namespaces]]` binding `CACHE`, and `[triggers] crons = ["*/15 * * * *"]`.
  Rotate the Cloudflare token and the API's MotherDuck token at teardown or by 2027-02-15, whichever comes first.
- **Monitor** — the same public repository's Actions, free and unmetered for standard runners on a public repository (GitHub docs, Actions billing).
  `nightly.yml` from M8: the `nightly` job's timeout is 60 minutes and it passes `--full` when `date -u +%u` is 7; from M10 a `notify` job follows `warm` (`needs: [nightly, warm]`, `if: ${{ !cancelled() }}`) with `MOTHERDUCK_TOKEN` and `NTFY_TOPIC` in its run step's environment alone, so a tap on a push opens a chart the warm job has cached (D98); each job ends with an `if: failure()` step that posts the run's URL to the topic only when the failure came before the CLI ran (`steps.run.outcome == 'skipped'`) or, in `warm`, from the API (D93).
  `watch.yml` (M10): `47 9 * * *` UTC, `status --alert` with the two secrets, so a night that never ran is reported by a run that did.
  `universe.yml` (M8): `0 6 1 * *` UTC and on dispatch; a `sync` job (`contents: write`) runs `universe sync` and commits and pushes `universe.csv` to `main` as `github-actions[bot]` when it changed; a `keepalive` job (`actions: write`) calls `gh workflow enable` on `nightly.yml`, `watch.yml` and `universe.yml` (D100).
  Secret: `NTFY_TOPIC`, set once by piping the generated topic into `gh secret set NTFY_TOPIC` with nothing printed; it needs no rotation unless leaked, and a new one means the owner subscribing again.
- **Alert channel** — ntfy.sh's public server, used anonymously; read from `https://ntfy.sh/v1/account` on 2026-11-18: 250 messages a day per address, messages cached 12 hours, attachments up to 2 MB each and 20 MB in all, kept 3 hours; 4,096 bytes a message (docs.ntfy.sh, Publishing, read 2026-11-18).

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
- **An instrument's overlap disagrees with the store** (a dividend, a split, a revision) — a second, whole-history request for it; that failing, the instrument is failed and keeps its rows (D87).
- **More than 5 instruments fail** — the `yahoo` run is `partial`, exit 1, and `status` and the health message name them; up to 5 is `stored` with the count (D101).
- **An instrument has too few bars for an ATR or two swings of each kind** — no pivots or signals for it on that timeframe and `none` as its structure; not a failure.
- **The `signals` stage fails** (a store error) — its transaction rolls back, a `failed` run row is appended, `compute` still runs over yesterday's structure, `nightly` exits 1, and `notify` sends only the health message.
- **The rules file is invalid** (a missing key, a threshold not positive, an unknown grade) — exit 2 naming the key, before anything is read.
- **`NTFY_TOPIC` is not set** — `notify` and `status --alert` exit 2 with "NTFY_TOPIC is not set"; `--dry-run` needs none.
- **ntfy.sh refuses or fails a send** (429 past the daily limit, 5xx, a timeout of 10 s) — retried twice after 5 and 20 s; still failing, the message is logged by title, its signals get no `alerts` row so the next night resends them while they are within the window, and `notify` exits 1.
- **The chart image fails to render or upload** — the push goes as text alone, and the failure is logged.
- **A digest is longer than its bounds** — its lowest-scored lines fold into the "+N" line.
- **More signals are due than the push cap** — the lowest-scored `A` signals go into their digest instead.
- **Wikipedia's table is missing, malformed or out of bounds** — `universe sync` exits 1 naming what failed and writes nothing; the workflow fails and GitHub mails the owner.
- **A missed night** (Actions skipped or disabled the schedule) — `watch.yml`'s `status --alert` finds the store stale and sends one health message; the next nightly's month-long fetch heals the gap (D87).

### Decisions

- **D1 Re-fetch every instrument's whole daily history each night and replace its rows** over an incremental upsert of recent days with a catch-up window — one request per instrument either way, and a full read is the only way a split or dividend's restatement of history, a revised bar or a missed night is healed without special cases; the cost is about 800,000 rows (some 30 MB) moved to MotherDuck a night; source: the 2026-11-17 probe in Inputs; overrides `run-unattended`, Make a run rerunnable (catch-up window and explicit backfill) *(proposed)*. *Superseded by D87 (M8): at about 680 instruments only each instrument's last month is fetched, with its whole history on a disagreement and every Sunday.*
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
- **D13 No notification; GitHub's failed-run mail, `status` and the dashboard's age chip are the signals** — `run-unattended`, Report the outcome; no requirement asks for an alert *(by precedent)*. *Superseded by D93 (M10): R12 earns a channel, and the pipeline's health goes to it on each change of state.*
- **D14 The core in Polars, converting `yfinance`'s pandas frame at the adapter with `polars.from_pandas`** — `use-polars`, Unlearn pandas; `setup-python`, Libraries *(by precedent)*.
- **D15 Metrics stored long in MotherDuck and recomputed whole each night** — `store-data`, Keep what the source sent; the export pivots them for the page *(by precedent)*.
- **D16 One overview file plus one bars file per instrument, loaded on demand** over one file of every close (about 10 MB) — keeps the first load inside R4's 800 KB, with Ticker and Compare and their chart code split out of the first bundle and each file inside `deploy-project`'s few-megabyte guidance *(proposed)*. *Superseded by D55: one overview response and one bars response per instrument, cached at the edge.*
- **D17 Exported Parquet uses snappy compression** over Polars' default zstd — `hyparquet` reads only uncompressed and snappy without the extra `hyparquet-compressors` package (hyparquet README, read 2026-11-17) *(proposed)*. *Superseded by D52: the API sends JSON.*
- **D18 All data is classed public** — the owner set aside Yahoo's terms in R7, which `secure-project` would otherwise read as private; so it may sit in public workflow logs and on Pages (from R7).
- **D19 MotherDuck's schema through numbered forward-only migrations in package data, applied when the store adapter connects** — `write-sql`, Change a schema *(by precedent)*.
- **D20 The pipeline's speed is not optimised** — about 2 minutes of fetching and a minute of loading against a 30-minute timeout; only the dashboard has a budget (R4) *(proposed)*. *Narrowed by D101: from M8 the nightly has a 45-minute budget (60 on Sundays) and the `signals` stage 5 minutes, checked in R11's line.*
- **D21 Universe of about ninety instruments** — 8 indices (`^GSPC ^NDX ^DJI ^RUT ^VIX ^FTSE ^GDAXI ^N225`), 4 rates (`^IRX ^FVX ^TNX ^TYX`), 22 ETFs (`SPY QQQ IWM EFA EEM TLT IEF HYG LQD GLD SLV` and the 11 SPDR sector funds), 40 large US stocks across sectors, 6 FX (`EURUSD=X GBPUSD=X USDJPY=X AUDUSD=X USDCHF=X DX-Y.NYB`), 5 commodity futures (`GC=F SI=F CL=F NG=F HG=F`), 4 crypto (`BTC-USD ETH-USD SOL-USD XRP-USD`) — broad enough for every screen, small enough for Yahoo's limit *(proposed)*. *Superseded by D86 (M8): these rows stay as the `featured` instruments inside a universe of about 680.*
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
- **D55 Four fixed `GET` endpoints, no SQL, no range or filter parameter, slugs checked against the cached overview before any query** over `write-entry-points`' `start` and `end` bounds — the page needs every instrument's whole history (the monthly calendar), and a closed key set caps MotherDuck at one query per endpoint and instrument per data version, about 92 a night, whatever the traffic *(proposed)*. *Narrowed by D97: six fixed endpoints, a larger bars body and a `slugs` body; the key set stays closed, about 690 bars keys a version.*
- **D56 The API checks no token and allows one browser origin, `https://henrymckay.github.io`; no rate limit** — overrides `secure-project`, Guard what is served (a token per consumer on an API reached beyond the machine): its one consumer is a public page, which the same section says holds no token, the data is public (D18), and the API only reads through fixed queries; CORS stops other sites' pages, not `curl`; D55's bound caps MotherDuck spend and Cloudflare's 100,000 a day caps the Worker, so a flood costs availability until 00:00 UTC, not money *(proposed)*.
- **D57 The API reads MotherDuck with its own token: a service account's, attached to a restricted share of `market_data` with `UPDATE AUTOMATIC`** over the owner's token (A1), which writes and reaches every database — Lite has no read-only token (read scaling is Business and Enterprise only, motherduck.com pricing, read 2026-11-18) but a share is read-only to its reader, and Lite allows two service accounts; `secure-project`, one credential per consumer; waits on Q4 *(proposed)*.
- **D58 The dashboard stays on GitHub Pages at its URL, built by `site.yml` on a push to `web/**`**, `data.ts` fetching JSON into the same shapes, preloading `/api/overview` and `/api/runs` from `index.html`, and `hyparquet` dropped, over Workers static assets on the API's origin (one origin, no CORS, one deploy, but a new URL for a live site the README, screenshot and evaluator rounds name; I13) — `write-entry-points`, Dashboard (one data module) *(proposed)*.
- **D59 The nightly export is removed with no static fallback** — `export`, `operate/export.py`, `adapt/site.py`, `build_runs` and `build_latest`, the site-data artifact — over keeping the Parquet files for the page to fall back on: R9 asks to stop the nightly files, a fallback is a second read path to keep true, and the cache already serves the last version while MotherDuck is down *(proposed)*.
- **D60 The nightly workflow gains a `warm` job with no secret**: it polls `/api/latest` until `ended` is at or after the `nightly` job's start (20 minutes at most), then requests `/api/overview`, `/api/runs` and every `/api/bars/<slug>`, failing on any status but 200, so no visitor waits on a miss (R4) for queries a visit would run anyway; over a cron that warms in the Worker, which 50 subrequests and 10 ms of CPU an invocation cannot fit *(proposed)*. *Narrowed by D98: from M8 it warms the featured instruments and those with a signal on the latest day, not all 680.*
- **D61 `api.yml` has a `test` job (`npm ci`, typecheck, lint, `vitest`) and a `deploy` job on `main` only**, `permissions: contents: read`, actions pinned to commit SHAs, `npm ci --ignore-scripts` where the tokens are present, the Cloudflare and MotherDuck tokens in the environment of the deploy steps alone, and the MotherDuck token reaching `wrangler secret put` on standard input through wrangler-action's `secrets:` input, never as an argument and uploaded before the deploy (D74) — D7's and D37's reasoning *(by precedent: `secure-project`, Keep secrets out)*.
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
- **D72 `VITE_API_URL` is read at build time and nowhere else; `data.ts` rejects with a message naming it when it is empty, every request times out after 30 s (`AbortSignal.timeout`), and a load still running after 3 s shows "Still loading" above the screen** — `design-interface`, States, for a slow or failed API *(proposed)*.
- **D73 The smokes run the built page against `tests/pytest_/stub_api.py` on the fixed loopback port 8788**, the page built with `VITE_API_URL=http://127.0.0.1:8788`, and fail with that command when `web/dist` is missing or built for another URL, over a rebuild in the fixture or a runtime-configurable URL (D58 fixes the URL at build time); refines D63 and D45 *(proposed)*.
- **D74 `api.yml` uploads the Worker's secret through wrangler-action's `secrets:` input**, which runs `wrangler secret put` per named variable before the deploy command, over a `secret put` step after the deploy, which left the first deploy failing on `secrets.required`; that the upload creates a Worker not yet deployed is unverified until M7 (A21) *(proposed)*.
- **D75 A slug may contain a hyphen (`^[a-z0-9-]+$`)** since `transform.slug` keeps `-`; M5's pattern rejected five instruments' bars *(proposed)*.
- **D76 `site.yml`'s `site` job runs only while the repository variable `API_URL` is set, and `nightly.yml` is `nightly` and `status` alone**; the `warm` job (D60) and the merge wait for M7, so a merge of M6 alone cannot replace the live page with a build that has no API *(proposed)*.

- **D77 The API's MotherDuck user is the service account `market_data_api` with a `read_write` token, kept read-only by the share `market_data_api`** (`create share market_data_api from market_data (access restricted, visibility hidden, update automatic)`, `grant read on share market_data_api to market_data_api`) over the owner's token and over a `read_scaling` token, which Lite refuses (REST 403 "Not authorized to create read scaling tokens"): a username takes only letters, digits and underscores, so not `market-data-api`; the grantee finds the share already attached as `market_data`, so `MOTHERDUCK_DATABASE` stays `market_data` and no query changed; a write through the DuckDB client and through the Postgres endpoint both fail with "attached in read-only mode" (checked with the token inside one pipeline); the account's own empty database `my_db` stays writable, which holds no data; the token went from the REST response straight into `gh secret set MOTHERDUCK_API_TOKEN`; `secure-project`, one credential per consumer, and `deploy-project`'s read-scaling pick, which Lite does not offer *(proposed)*.
- **D78 `verify-secrets.yml`, run by hand, is how R8's token counts after M7 are made**: the owner's Cloudflare token was pasted at a hidden prompt and the service account's token went straight into a secret, so neither value exists on the laptop to `grep -F` for; the workflow runs where the secrets are, collects every earlier run log, the published site and a `wrangler tail` session over every endpoint and error, and `scripts/scan_tokens.py` prints only counts of each whole token and its D50 fragments *(proposed)*.
- **D79 The `warm` job gets the nightly's start time as a job output, polls `/api/latest` every 30 s for up to 20 minutes until its `ended` is not before that time, then requests `/api/overview`, `/api/runs` and every `/api/bars/<slug>` four at a time**; a dispatched run took about seven minutes to see the new version (the cron's 15-minute step), all 91 responses were `200` and a cold miss took 2.5 to 3.3 s each (`^GSPC` 3.1 s); refines D60 *(proposed)*. *Narrowed by D98 as D60 is.*
- **D80 M7's workflows and fixes reached `main` by pushing a merge commit of the milestone branch**, as M3 and M4 did, since the approval named the PR's merge and pushes, and a schedule fires on `main` only *(proposed)*.
- **D81 The docs page keeps the system font stack and gains a "Fields and units" section** over bundling Inter in the Worker: the page is one static string and a font file needs a bundler rule and about 47 KB in the script, for a page the dashboard does not use; the evaluator's round 1 asked for the units, which are now stated *(proposed)*.
- **D82 The docs page has a description and an inline favicon, and the header chip no longer repeats itself; the page prefetches an instrument's bars when its search result is highlighted, shows "Age unknown" when the runs fail to load and an empty card when no instrument is stored** after the live evaluator's round 1 (criteria 6 and 7); the instrument switch stays network-bound (Ideas I20) *(proposed)*.

- **D83 Swings by an ATR-scaled directional change on closes**, per instrument and timeframe, bar by bar from the first bar with an ATR:
  - ATR is the `ewm_mean(alpha=1/14, adjust=False, min_samples=14)` of true range, the larger of high minus low and the distances from the previous close to the high and to the low;
  - tracking up, a bar whose high is at or above the extreme's becomes the extreme; otherwise a close at or below the extreme's high minus `k × ATR` (this bar's ATR) confirms a swing high at the extreme on this bar, and tracking turns down from the lowest low since the extreme, the later bar on a tie; tracking down is the mirror; tracking starts up;
  - `k` is 2.5 daily, 2.0 weekly and 2.0 monthly, which on 20 instruments across every asset class since 2000 gave one swing every 17, 13 and 14 bars (15.0, 4.1 and 0.85 swings a year), so a swing means the same on each timeframe.
  Over N-bar fractal pivots (TradingView's `ta.pivothigh`, Williams' fractals), which confirm a fixed N bars late whatever the move and pivot on every wiggle of a range, with the same N meaning different moves on Bitcoin and a Treasury fund; and over a percentage threshold (the directional-change literature's θ), which scales with time but not across asset classes.
  Cost: a swing is known only once price has retreated `k × ATR`, so its confirmation lags by a volatility-sized move, not a fixed number of bars; a confirmed swing never moves, which is what makes the signals repaint-free (TradingView's repainting docs: acting before a pivot confirms is what repaints).
  Sources: the directional-change definition (extreme point, confirmation point, threshold θ) in core.ac.uk/download/158172005.pdf and Tsang's 2024 nowcasting paper (eprints-gro.gold.ac.uk/37843), tradingview.com/pine-script-docs/concepts/repainting, and the 2026-11-18 calibration run over Yahoo histories from the planning machine *(proposed)*.
- **D84 Structure and events as Dow's highs and lows, each turn called on a close**, evaluated on every bar after its swings are updated:
  - from `none`, the structure becomes `down` once the last swing high is LH and the last swing low LL, and `up` on HH and HL; a new swing that contradicts a settled `up` or `down` (an LL in `up`, an HH in `down`) with no event returns it to `none` to be re-derived;
  - in `down`, a close above the last swing high's price is `break_up`, with that price as level, the last swing low as stop, and `turning_up` as the structure;
  - in `turning_up`, a close below the stop is `fail_up` and back to `down`; else the next swing low to confirm is `confirm_up`, level and stop its price and `up` the structure, when it is above the stop, and `fail_up` and `down` when it is not;
  - `break_down`, `fail_down` and `confirm_down` are the exact mirrors from `up`; at most one event a bar.
  Over an intrabar break on the high or low — a wick through a swing "is often a liquidity sweep rather than a real structural break", and the change of character is the first close beyond the protected swing (luxalgo.com/library/concept/change-of-character, read 2026-11-18) — and the nightly sees complete bars only, so a close is the first moment either is known; and over calling the "first higher high" only once that swing high confirms, which is a whole leg later.
  Cost: one reading of the owner's words (A22) *(proposed)*.
- **D85 Timeframes `d`, `w` and `m`, all from the stored daily bars through the `period_bars` view**, ISO weeks Monday to Sunday and calendar months, a period counting only once the run's UTC date is past its last calendar day, so stocks' weekly signals arrive in Monday's 02:17 run before the open and monthly ones on the 1st.
  Over 1-hour and 4-hour bars now: Yahoo serves 1-hour bars for only the last 730 days (yfinance wiki, Ticker), each intraday interval is another request per instrument per run, an hourly schedule is 24 runs of about 700 requests against an unpublished limit (A27), and the owner reads alerts once a day (A23); intraday is Not yet (I26).
  Over resampling in Polars beside SQL in the chart's query, two computations of one result (`write-sql`, Never compute one result both ways).
  Cost: the core trusts a view's shape, tested on a local DuckDB file; a week's signal waits for the week to end *(proposed)*.
- **D86 A universe of about 680 instruments**: the S&P 500's members from Wikipedia (`source=sp500`), and curated rows (`source=curated`) — 18 indices (the 8, `^STOXX50E ^FCHI ^HSI ^AXJO ^GSPTSE ^BVSP ^KS11 ^NSEI 000001.SS ^SOX`), the 4 yields, about 84 ETFs (the 22; `RSP MDY IJR VTV VUG MTUM QUAL USMV`; countries `EWJ EWG EWU EWQ EWI EWP EWL EWC EWA EWZ EWW FXI MCHI KWEB INDA EWY EWT EZA`; industries and themes `SMH SOXX XBI IBB KRE KBE XHB ITB XRT XOP OIH GDX GDXJ ARKK TAN ICLN URA LIT JETS IGV`; bonds `SHY TIP AGG BND EMB MUB BIL`; commodities `USO UNG DBC DBA CPER`; currencies `UUP FXE FXY`; `IBIT`), 19 FX pairs (the 6; `NZDUSD=X USDCAD=X EURGBP=X EURJPY=X GBPJPY=X EURCHF=X AUDJPY=X USDCNY=X USDMXN=X USDINR=X USDBRL=X USDZAR=X USDTRY=X`), 19 futures (the 5; `PL=F PA=F BZ=F RB=F HO=F ZC=F ZW=F ZS=F KC=F CC=F SB=F CT=F LE=F HE=F`), 20 coins (the 4; `BNB DOGE ADA TRX AVAX LINK DOT LTC BCH XLM HBAR SHIB NEAR ATOM ETC AAVE`, each `-USD`) and the large Nasdaq-100 members outside the S&P 500 (from `ASML AZN PDD ARM MELI CCEP SHOP MSTR TEAM MRVL ZS GFS DDOG TTD`, those not already listed); a curated symbol that answers no data in M8's first run is dropped; the 89 first rows are `featured`; GICS sector names are kept but for "Information Technology", written "Technology" as the first rows have it.
  Over the Russell 1000 or 3000 (no free member list, and 1,000 to 3,000 requests a night) and over Nasdaq-100 membership synced too (Wikipedia's Nasdaq-100 page held no member table on 2026-11-18, A31, and Nasdaq's own list needs a browser-like client).
  Cost: eight times the requests, about 12 minutes a night (A27), and 680-row screens *(proposed)*.
- **D87 Each night fetches each instrument's last month and replaces its rows from the first day fetched; an instrument gets its whole history where the store holds none, its last stored day is over 25 days old, or its overlap disagrees — a stored `close` or `adj_close` differing by more than one part in a million on a shared day, or a dividend or split the store lacks — and every instrument gets its whole history on Sundays (`--full`)**; supersedes D1.
  D1's reasons were healing and simplicity at 90 instruments; at 680, a whole replace moves about 6 million rows, some 230 MB, into MotherDuck a night, whose compute Lite does not report (I22) and whose overage terms its pricing page does not state (A26), so the measurement "Measure before optimising" asks for is not to be had and the cost of being wrong is a bill; the overlap check heals a dividend or split the night it lands, and Sunday's full fetch heals any revision the overlap misses.
  The fetch port takes a period per ticker, and `port.Load` gains a `since` per answered ticker, null for a whole history; the month covers `run-unattended`'s catch-up window, so a missed night or week needs no backfill.
  Cost: two fetch shapes and about 15 more requests a night where dividends land *(proposed)*.
- **D88 The `signals` stage recomputes every pivot, signal, outcome, base rate and structure over every stored bar each night and replaces the five tables whole in one transaction**, so the backtest is the live code and the base rates are what the monitor would have sent, which the no-repaint property test proves; over carrying state from night to night, a second code path under which a rules change would leave history on the old rules.
  Cost: about 7 million bars through the kernel each night, budgeted at 5 minutes (D101, measured in M9); `store-data`, Keep what the source sent (metrics recomputed whole), and D15 *(by precedent)*.
- **D89 Outcomes and base rates**:
  - horizons in bars of the signal's timeframe, 5, 20 and 60 daily, 4, 13 and 26 weekly, 3, 6 and 12 monthly, the middle one primary;
  - `return` is adjusted close at the horizon over adjusted close at the signal bar, less one; `signed_return` multiplies it by +1 for an `up` signal and -1 for a `down` one, `fail_up` pointing down and `fail_down` up;
  - `mfe` and `mae` are the best and worst high or low over the horizon's bars against the signal bar's close, the signal's way, `mae` negative; `held` is no close beyond the stop within the horizon;
  - the baseline is every bar of the asset class and timeframe from its first ATR on, its forward return at the same horizon: `baseline_mean` its mean signed the event's way, `baseline_hit` the share moving that way;
  - `signal_stats` counts complete horizons only, per event, timeframe, asset class and grade, each also as `all`.
  Over hit rates alone, which on the 2026-11-18 calibration looked like an edge until set against the drift: daily `break_up` rose within 20 days 56% of the time when any day did 56.5%, and `break_down` lost to the drift; the edge column is what tells the owner which signals carry information.
  Cost: an in-sample, survivorship-biased figure (A30), stated on the Signals screen *(proposed)*.
- **D90 Score and grade**, from the rules: points for the timeframe (`d` 0, `w` 1, `m` 2), +1 for `aligned`, +1 when `trend_swings` is at least 3, +1 when `volume_ratio` is at least 1.5, +1 when `margin_atr` is at least 0.5 for a break or 1.0 for a confirmation; `A` at 3 or more, `B` at 2, `C` below.
  `aligned` reads the next timeframe up's structure — weekly for daily, monthly for weekly — at its latest bar whose `last_day` is before the signal's `day`, by an as-of join, so no signal sees a bar that was not complete; `up` or `turning_up` aligns an `up` signal and the mirror a `down` one; monthly signals have none.
  Over a single significance number such as the leg's height in ATR, which ranks volatile instruments first; the points are each a reason the owner can read in the push, and the base rates per grade show whether they earn their weight (R17).
  The calibration's counts give about 11 sent daily signals a night across 680 instruments, 13 weekly on Mondays and 8 monthly on the 1st; the grades decide which of those reach the phone *(proposed)*.
- **D91 Alerts on ntfy.sh, anonymous, to one unguessable topic; each `A` signal of the night is a push, at most ten, the rest in their digest; each asset class with a signal graded `B` or better gets one digest; `C` signals and failures are never sent, and are on the Signals screen**, over email (needs the owner's mail password, a new credential), Telegram (a new account) and Pushover ($4.99), and over one digest a night (the owner asked for alerts split by asset type, and a push per strong signal is what lets them decide in seconds).
  `send-messages`, Pick the channel (ntfy for an alert, no account, one POST) *(by precedent)*; the split is *(proposed)*; ntfy's limits are in Runs on.
- **D92 Each signal is sent once**: `notify` selects signals whose `known` is within the last four days and whose `id` no `alerts` row names, and appends an `alerts` row per signal once its message is accepted; the four days let a missed or failed night's signals go the next night, and keep a backfill or a rules change from flooding the phone with history.
  `send-messages`, Alert on a change of state, and `run-unattended`'s catch-up window *(by precedent)*.
- **D93 The pipeline's health goes to the same topic on each change of state**: `notify` and `status --alert` compare `status`'s verdict with `alert_state` and send `unhealthy` or `healthy again` only when it differs; `watch.yml` runs `status --alert` at 09:47 UTC so a night that never ran is reported; an `if: failure()` step reports a job that failed before the CLI ran; supersedes D13.
  `send-messages`, Decide what deserves a message and Each failure has a sender that survives it *(by precedent)*.
- **D94 Messages as the Interface shows**: plain text, since ntfy renders Markdown only in its web app (docs.ntfy.sh, Markdown); text messages published as JSON to `https://ntfy.sh/` so UTF-8 needs no header encoding; a push with its image PUT to `https://ntfy.sh/<topic>` with `Filename` and the text as URL-encoded `message`, `title`, `tags`, `priority`, `click` and `actions` parameters, which ntfy accepts as it accepts headers (docs.ntfy.sh, Attachments and Publish as query parameters); a one-second pause between messages; the stdlib `urllib.request` as `send-messages`, Send from the job, shows, behind a `port.Send` the core never calls.
  `design-interface`, Set the bar (Message) *(by precedent)*.
- **D95 The rules live in `src/market_data/data/transform/monitor.yaml`**, read once into a frozen `Rules` record whose canonical JSON's SHA-256 is each signal's `rules`; a change is a commit, so the next night recomputes all history under it (D88); `signals --rules PATH --dry-run` prints the base rates under another file without writing, so the owner or a session compares before committing.
  The file:

  ```yaml
  atr-bars: 14
  swing-atr: {d: 2.5, w: 2.0, m: 2.0}
  horizons: {d: [5, 20, 60], w: [4, 13, 26], m: [3, 6, 12]}
  score:
    timeframe: {d: 0, w: 1, m: 2}
    aligned: 1
    trend-swings: {at-least: 3, points: 1}
    volume-ratio: {at-least: 1.5, points: 1}
    margin-atr: {break: 0.5, confirm: 1.0, points: 1}
  grades: {A: 3, B: 2}
  alerts:
    events: [break_up, confirm_up, break_down, confirm_down]
    push-grade: A
    push-cap: 10
    digest-grade: B
    window-days: 4
    muted-asset-classes: []
    base-rate-min-n: 30
    site-url: https://henrymckay.github.io/market-data-public/
  ```

  Package data as D8 keeps the universe, over `structure-python`'s user-editable file in the data directory, which a runner lacks *(by precedent: D8)*.
- **D96 The nightly runs fetch, then signals, then compute, and the API's version is the last stored `metrics` run's `ended`**: `compute` joins `structure` into the overview's trend columns, and `latest.sql` returns `version` beside the `yahoo` run's fields, which the Worker's `versionOf` reads, so the cron can no longer cache an overview from between stages (closes I21); `nightly` reads the bars once and hands the same frame to `signals` and `compute`.
  `write-sql`, Never compute one result both ways *(proposed)*.
- **D97 The API gains `/api/signals` and `/api/stats`, the bars body gains `weekly`, `monthly`, `pivots` and `signals`, and a `slugs` body resolves a slug**, all fixed queries under the data version, filled by the cron with `latest`, `overview` and `runs`; narrows D55.
  One bars request still draws a chart with its structure, so a tap on a push costs one fetch; the `slugs` body replaces parsing a 1.4 MB overview per bars request, which would spend most of the 10 ms CPU a request (A17); KV writes stay near 130 a night (cron 7, warm about 110) of the 1,000 a day.
  Over a separate `/api/structure/{slug}`, a second request per tap and twice the per-instrument keys, and over joining base rates into `/api/signals`, which the page can look up from `/api/stats` as the push does from `signal_stats` *(proposed)*.
- **D98 The warm job requests the featured instruments' bars and those of every instrument with a signal on the latest `known`, and `notify` runs after it**, so a tapped push opens a cached chart; over warming all 680, about 680 MotherDuck queries of 1 to 3 CU-seconds a night, some 10 CU-hours a month, Lite's whole allowance (motherduck.com pricing, Pulse, 1 CU-second minimum a query, read 2026-11-18); narrows D60 and D79.
  The cost is a cold miss of about 3 s for an instrument opened with neither *(proposed)*.
- **D99 The Signals screen, Ticker's structure and the 680-row Markets table as the Interface shows**; the Ticker's markers and price lines use Lightweight Charts' `createSeriesMarkers` and `createPriceLine`, already in use; the Signals edge chart is DOM bars as D40 draws the leaders; the Markets table pages at 100 rows, as `design-interface`'s Layout asks past about a hundred.
  `design-interface`, Plan the design before the code *(by precedent)*.
- **D100 `universe.yml` commits the synced CSV to `main` each month, and its `keepalive` job re-enables the scheduled workflows through the API**: the project now outlives GitHub's 60 days without activity that disables a public repository's schedules (A28; docs.github.com, Disabling and enabling a workflow), and the enable call is keepalive-workflow's API mode (A32); over opening a pull request, which needs the repository's "Allow GitHub Actions to create pull requests" setting changed and a person to merge a fact; supersedes A3 and builds I1.
  The job holds `contents: write` and runs no third-party code but `uv sync`, Wikipedia's text is checked symbol by symbol, and the commit touches `universe.csv` alone (`git add` by path) *(proposed)*.
- **D101 `tolerance` 5, the `nightly` job's timeout 60 minutes, and the store's busy time logged**: one acquisition a month in the S&P 500 would otherwise turn nights red until the next sync, and `status` still names every missing instrument; the busy time (seconds inside store calls, logged at `info` as "Store busy for N s") replaces the connected time as R6's proxy, since the connection now idles through a 12-minute fetch and MotherDuck meters per query; narrows D20 and R6's check *(proposed)*.
- **D102 Swings and levels use the stored split-adjusted high, low and close; outcomes use adjusted close for returns**: the levels in a push then match the candles the Ticker view draws (close as quoted, D10), and returns include dividends as every other return here does *(by precedent: D10)*.
- **D103 The kernel is a pure function over one instrument's and timeframe's NumPy arrays in `transform/structure.py`, called per group of a Polars frame, returning pivots, events and the final state**, keeping O(1) state (the last two swings of each kind, the extreme, the mode, the structure) rather than rescanning lists; over Polars expressions, which cannot carry path-dependent state, and over `numba`, a compiled dependency earned only by a timing past the 5-minute budget (I29).
  The calibration's naive loop handled 154,000 bars in 3.4 s with pandas reads included *(proposed)*.
- **D104 Signals, outcomes, base rates and messages are public**, derived from public data (D18) and carrying no position or account; the topic is the one new secret, generated as `md-` plus `secrets.token_urlsafe(18)` by a script that writes it to the keychain (`security add-generic-password -U -a "$USER" -s ntfy-market-monitor -w <topic>` from inside the script) and pipes it to `gh secret set NTFY_TOPIC`, printing neither; the log formatter redacts it, the sender never logs its URL, and `verify-secrets.yml` counts it with the tokens.
  `secure-project`, Classify the data and Keep secrets out *(by precedent)*.
- **D105 A push carries a 1200 by 600 PNG of its timeframe's last 80 bars**, drawn by `matplotlib` (Agg) in the house light tokens: candles in `up` and `down`, swing labels in `muted`, the level as a dashed `accent` line and the stop as a dotted `down` (or `up`) line, each labelled at the right edge with its price, the signal bar marked, and a title in the push's words; under 200 KB.
  Over text alone, since the owner decides from a chart and a picture of the structure is the fastest form of it; over an attachment by URL, which needs the image hosted.
  `design-interface`, Set the bar (Message: one chart, rendered with the tokens) and `references/python.md`; the cost is `matplotlib` in the runtime dependencies and a 3-hour attachment life on ntfy.sh (A24) *(proposed)*.
- **D106 Dependencies**: `matplotlib` for D105 and `lxml` for `pandas.read_html`, made direct (it is already locked through `yfinance`); no HTTP client beyond the stdlib, for two outside calls a night and a month *(by precedent: `setup-python`, Libraries; D14)*.
- **D107 The monitor's tests**: the kernel and events on handmade bar tables, every row of D84 and its mirror; a `hypothesis` property over random walks that pivots and signals on a prefix equal those on the whole with days up to the prefix's end; the as-of alignment never reading an incomplete period; outcomes and the baseline against hand-worked answers; message bounds and URLs; `notify` over a fake store and a recording sender (dedup, cap, grades, muted classes, health change); the ntfy adapter against a loopback `http.server` stub; the chart's PNG signature and size; migrations, `period_bars` and the API's new queries on a local DuckDB file; `vitest` for the Signals screen's logic; browser smokes of Signals and Ticker over the stub API — `write-tests`, D23, D63 *(by precedent)*.
- **D108 M8's build choices**: `universe sync` fails the whole sync with a `SourceError` (exit 1, nothing written) on an odd symbol, a repeated symbol, a name or sector over 100 characters or holding a control character, or a row count outside 495 to 510, rather than dropping the row, since a changed table is one the monthly job should not commit from; a sync counts a returning `sp500` member as added; the sync updates no name or sector of a row it already holds, so `--check` is exactly "a member to add or an `sp500` row to deactivate"; the curated list was probed on 2026-11-18 with `period="1mo"` and every symbol answered, so none was dropped, and `MRVL` and `DDOG`, being S&P 500 members that day, are `sp500` rows, not curated *(by precedent: D86, D100)*.
- **D109 The overview rounds its figures to seven significant digits and its sparkline to five**, in `build_overview`: with 679 rows the body measured 540 KB gzipped on synthetic walks, which alone would break R4's 800 KB, and 228 KB rounded; no screen shows more digits, and the rounding is on the stored overview, so the API stays a pass-through *(proposed)*.
- **D110 A new day carrying a dividend or split counts as a "dividend or split the store lacks" (D87)**, so that instrument is fetched whole at once; its earlier days' adjusted closes have moved anyway, so the overlap check would find it a night later by the close comparison *(by precedent: D87)*.
- **D111 `nightly.yml` takes a `full` dispatch input**, so a `--full` run can be dispatched on any day to check R11's 60-minute line without waiting for a Sunday *(proposed)*.
- **D112 The fetch port takes a period and the store's reads and the replacement plan are the sink's**: `Fetch(tickers, period)` with `"1mo"` or `"max"`, `Sink.read_last_days` and `Sink.read_overlap`, and `Load.since` (ticker, first day replaced, null for all) in place of `Load.answered`, so the use case plans from stored days without a third port *(by precedent: `structure-python`, Declare a port)*.

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
  From M8 R6's nightly proxy is the logged store busy time, under 5 minutes a night, in place of the connected time (D101).
- **R11** — `universe.csv` has at least 650 active rows and every asset class but `rate` at least 15; `universe sync --check` exits 0 right after a sync; a test of `sync_members` adds a new member, marks a leaver inactive and leaves curated rows alone; a test runs the incremental fetch twice against a local DuckDB file with a fake source and finds the same rows, and a fake dividend in the overlap triggers a whole-history request for that instrument alone; a dispatched `nightly` on `main` stores with at most 5 failed instruments and every active instrument current as R1 says, in under 45 minutes (a dispatched `--full` under 60), with the store busy under 5 minutes; `/api/overview` holds one object per active instrument, and the Markets screen's cold load stays within R4's 800 KB.
- **R12** — `notify` over a fake store and a recording sender sends one push per `A` signal up to the cap and one digest per asset class with a `B` or better, appends an `alerts` row per signal sent, and sends nothing on a second run; on `main` the dispatched nightly's `notify` job reports `sent` for every message, and `curl -s "https://ntfy.sh/$topic/json?poll=1&since=6h" | wc -l`, with `topic` read from the keychain inside the command and never printed, counts them.
- **R13** — the kernel's table tests: two lower highs and two lower lows, then a close above the last lower high, give `break_up` on that bar with that high as level and the last low as stop; a wick above the level with a close below gives nothing; the next swing low above the stop gives `confirm_up` on its confirming bar; a close below the stop first gives `fail_up`; each mirror likewise; the property test finds no signal or pivot on a prefix that differs from the whole history's (no repaint).
- **R14** — a real run stores signals on `d`, `w` and `m`; a run dated on a Saturday emits no signal for the week in progress, one dated the 1st emits the closed month's; a daily signal's `aligned` reads the weekly structure of the last complete week.
- **R15** — every push's title holds at most 60 characters and its message at most four lines and 300 bytes naming the level, the stop, the higher timeframe's trend and the base rate; every click opens `?view=ticker` with `t`, `tf`, `range` and `sig`; on the live site, Playwright opens a recent push's click and finds the level line and the signal marker drawn within 1 s once the bars are cached; the evaluator scores `notify --dry-run`'s transcript and three chart images against `design-interface`'s Message bar.
- **R16** — no dependency or code reaches a broker or an account, and every input is public (D104); every push and the Signals screen show a base rate beside its baseline.
- **R17** — every signal row carries the rules' hash; a test that changes one threshold changes the hash and the recomputed signals; `signals --rules alt.yaml --dry-run` leaves every table's count unchanged and prints the base rates; an outcome appears once its horizon's bars exist.
- **R18** — the adapter sends to `https://ntfy.sh` with no `Authorization` header; the topic occurs 0 times, whole or as D50's fragments, in every run log, the built site and the repository's history (`verify-secrets.yml` extended, `gitleaks git`).

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
- [x] **M6 Front end on the API** — R4, R9; `web/src/lib/data.ts` fetches JSON from `VITE_API_URL` into the unchanged `Instrument`, `Run`, `Series` and `Latest` (D58), `hyparquet` and the Parquet preloads go, the stub API serves the smokes (D63), and `export`, `operate/export.py` and `adapt/site.py` are removed (D59); done when the Python suite, `vitest` and the browser smokes pass, a local build against the local Worker shows every screen with live data, and the evaluator passes the eight screenshots on the ten criteria. No outward step.
  Ticked 2026-11-18 **on branch `feat/m6-front-end-api` only; the merge to `main` waits for M7**: merged alone, the nightly would already have lost `export` while the live page still reads its files until the Worker is deployed, and `site.yml` skips until `API_URL` is set. Python suite 123 and 14 browser smokes (stub API on port 8788), `vitest` 50 (web) and 22 (api), `tsc`, `oxlint`, `ruff`, `pyright`, `actionlint`, `pip-audit` and `gitleaks` pass; `npm audit --omit=dev` is clean in `web/` and `api/` (the dev-only `picomatch` advisory of D71 shows in `web/` too, accepted on D71's grounds). The built page over `wrangler dev` against live MotherDuck showed every screen (`evaluation/round-7/`); the evaluator passed all ten criteria and the API docs page in round 1. Local timings, loopback: on a cold API (empty KV) `/api/latest` took 2.2 s, `/api/overview` 2.6 s and `/api/bars/gspc` 4.8 s (489 KB gzipped), Markets ready took 5.1 s, against 0.52 s cached (217 KB transferred; 1.6 s on the throttled 1.6 Mbit/s link, I10); controls 23-39 ms; an instrument switch median 170 ms cached and 2.7-7.1 s on a cold miss (budget 10 s); a repeat `/api/bars/gspc` 74 ms. The token occurs 0 times in the dev log and in `web/dist`. The live smoke exposed an M5 bug: slugs with a hyphen (`btc-usd`, `eth-usd`, `sol-usd`, `xrp-usd`, `dx-ynyb`) answered 404; fixed with a regression test (D75).
- [ ] **M7 Deploy and verify** — R4, R5, R6, R8, R9, R10; **stops first for the owner**: Q5's sign-in steps, then Q4's answer; then `api.yml` deploys the Worker, `gh variable set API_URL` names it, `site.yml` publishes Pages, `nightly.yml` loses `export`, `site` and `deploy` and gains `warm` (D60), and the README gains the API (its URL, docs page, endpoint table and an example), a fresh screenshot, and the teardown of the Worker, the KV namespace, the Cloudflare token, the service account and the share (Q2); done when R4's re-measured timings, R5's age check, R6, R8, R9 and R10 pass and a scheduled nightly has warmed the API.
- [x] **M8 Broad universe and incremental fetch** — R11, R6, R8; migration `0004` (`featured`, `source`), `adapt/wikipedia.py` and `universe sync`, the curated rows and a first sync to about 680 (D86), the incremental fetch with its overlap check and `--full` (D87), `tolerance` 5 and the store's busy time (D101), the `slugs` body in the Worker (D97), the warm job's featured list (D98), Markets paged at 100 rows (D99), `universe.yml` with its keepalive (D100), `nightly.yml`'s timeout and Sunday `--full`; then merge to `main`, dispatch `nightly` and `nightly --full`, and let `api.yml` and `site.yml` deploy; done when the suites pass and R11's dispatched checks and R4's 800 KB pass on the live site.
  Ticked 2026-11-18, merged to `main` as 80902f8. Suites: 184 `pytest` (plus 15 browser smokes with `CHROME`), `ruff`, `pyright` and `gitleaks` clean, `pip-audit` clean after `lxml` became direct, API `vitest` 25, web `vitest` 50, `tsc` and `oxlint` clean.
  `universe.csv` holds 679 active rows (515 stocks, 84 ETFs, 20 coins, 19 currencies, 19 futures, 18 indices, 4 rates), 89 `featured`; `universe sync --check` exits 0 right after a sync; every curated symbol answered a `1mo` probe, none dropped (D108).
  Dispatched nightlies on `main`: [44277248960](https://github.com/henrymckay/market-data-public/actions/runs/44277248960) (first, 590 whole histories) stored 4,646,961 rows in 12 m 26 s, 0 failed, store busy 13 s; [44281435475](https://github.com/henrymckay/market-data-public/actions/runs/44281435475) (incremental) 679 requests, 15,113 rows, 0 failed, 12 m 33 s, store busy 16 s; [44284004193](https://github.com/henrymckay/market-data-public/actions/runs/44284004193) (`--full` through the new `full` input, D111) 5,478,603 rows, 12 m 35 s, store busy 20 s, `status` `stale=false`; warm jobs green, the token occurs 0 times in all three logs.
  `/api/overview` returns 679 objects (679 active, 89 featured, 679 distinct tickers, none without bars); Markets' cold load measured 404 KB compressed with the overview at 241 KB (D109), against R4's 800 KB.
  Not seen: the Sunday `--full` by the cron itself (the first is 2026-11-22) and the first monthly `universe.yml` run (2026-12-01); `universe.yml`'s `sync` and `keepalive` ran nowhere yet, and `gh workflow enable` on an enabled workflow is A32's unverified claim.
- [ ] **M9 Structure, signals and base rates** — R13, R14, R16, R17; the rules file (D95), migration `0005` (the view, five tables, the overview's trend columns), `transform/structure.py` (ATR, kernel, labels, events), `transform/score.py`, `transform/outcomes.py`, `operate/signals.py`, the `signals` command and stage, the nightly's new order and `/api/latest`'s `version` (D96); then merge, dispatch `nightly`, read the base rates; done when the suites, the property test and R13, R14 and R17's checks pass, the stage takes under 5 minutes on the full store, and the base rates are reported to the owner with the milestone.
- [ ] **M10 Alerts on ntfy** — R12, R15, R18; migration `0006`, `transform/alerts.py` (selection, composition, health), `adapt/ntfy.py`, `adapt/chart.py` (D105), `operate/notify.py`, `notify` and `status --alert`, the topic generated into the keychain and `NTFY_TOPIC` with nothing printed (D104), the `notify` job, the `if: failure()` steps and `watch.yml` (D93), `verify-secrets.yml` counting the topic; then merge and dispatch; done when the suites pass, the evaluator passes the dry-run transcript and chart images, a dispatched run's `notify` sends to the topic and R12's poll counts them, a forced failure on a branch sends one health message and its recovery one more, and R18's counts are 0.
- [ ] **M11 Signals on the API and the dashboard** — R15, R17, R4, R9; `signals.sql`, `stats.sql` and the bars body's additions (D97), the docs page's new endpoints, the stub API's, the Signals screen, Ticker's timeframe toggle, markers, price lines and `sig`, Markets' Trend column (D99); then merge, deploy, warm; done when the suites and smokes pass, R15's live click check passes, the evaluator passes the ten criteria on Signals and Ticker at both widths and schemes, and R4's timings hold on the live site.

## Open

### Assumptions

- **A1** The nightly uses the owner's own MotherDuck token, as pre-approved, rather than a service account's (replaces Q1's recommended answer until the owner acts) — it is the only credential provided; if the owner creates a service account, only the secret changes.
- **A2** Yahoo serves about 90 requests a night at one a second to GitHub's runner addresses without blocking them — reports of blocks concern bursts and shared addresses, unverified for Actions (search of yfinance issues, 2026-11-17); if wrong, M2's dispatched run fails partial or failed, and the fix is a slower pace or a question to the owner, since no free source replaces Yahoo here.
- **A3** The project is deleted within 60 days, so the schedule's 60-day inactivity rule never fires — the owner called it throwaway; if it lives longer, I1 keeps it alive. *Superseded by A28 (2026-11-18): the monitor makes it the first piece of a trading assistant.*
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
- **A16** *(resolved 2026-11-18 in M7: all three held; the token type is `read_write` because Lite refuses `read_scaling`, D77)* Restricted shares, `GRANT READ ON SHARE` to a service account and a service account's connection through the Postgres endpoint all work on Lite — the endpoint answered the owner's token from Lite on 2026-11-18, and Lite lists two service accounts, but shares on Lite are unverified (MotherDuck docs say nothing per plan); if not, the API runs on the owner's token (A1) and Q4 becomes a question of accepting that.
- **A17** Relaying the largest body (`^GSPC`, 2.9 MB in one `varchar`) fits Workers Free's 10 ms of CPU a request, since decoding one string and a KV write are native work — unverified until R10's metrics in M7; if not, the bars endpoint splits each history by decade (one more parameter, D55's bound times about ten), or the API moves to Vercel Hobby with the same TypeScript (D51's runner-up).
- **A18** *(resolved 2026-11-18: `wrangler dev` reached MotherDuck's endpoint locally, so M5's live check ran the Worker itself)* `wrangler dev` on the laptop opens the TLS socket to the Postgres endpoint — MotherDuck's Workers guide reports "Connection terminated" for some local runs; if so, M5's live check runs `store.ts` under Node from `nodejs-wheel` against live MotherDuck and the Worker's live check moves to M7.
- **A19** *(resolved 2026-11-18: the first deploy created the KV namespace `market-data-api-cache`)* `wrangler deploy` provisions the KV namespace on first deploy from Actions; if not, a one-off dispatched step runs `wrangler kv namespace create` and its id is committed to `wrangler.toml` (an id is not a secret).
- **A20** MotherDuck's Postgres endpoint, labelled preview, keeps its documented behaviour for the project's life — it is throwaway (A3); if it changes, the Worker's one adapter (`store.ts`) changes.
- **A21** *(resolved 2026-11-18: the first dispatched `api.yml` run answered the create prompt, uploaded the secret with `wrangler secret bulk` and deployed)* `wrangler secret put` before the first `wrangler deploy` creates the Worker with its secret in a non-interactive run, as the `secrets:` input relies on (D74) — unverified until M7; if it asks to confirm and fails, a dispatched step creates the Worker first.
- **A22** The owner's "first higher high" is the first close above a downtrend's last lower high, and "the first higher low after the higher high" the next swing low that confirms above the downtrend's last low (D84) — practitioners call the first a bullish change of character (LuxAlgo, read 2026-11-18), and a close is the first moment the nightly can know it; if the owner meant the higher high's own swing confirming, every break arrives one leg later, a rules option the build can add.
- **A23** The owner reads alerts once, in their morning, so one batch after the nightly (about 03:00 UTC, after every market's daily bar has closed) is enough (replaces Q11's recommended answer) — the brief asks for a few seconds' decision, not a reaction within the session; if not, a second run after the US close earns its place.
- **A24** The owner's phone runs the ntfy app, which shows image attachments on Android and iOS (docs.ntfy.sh, Attachments: supported on Android, iOS and the web) — if the image has expired (3 hours) by the time they look, the text still carries the call and the tap still opens the chart.
- **A25** ntfy.sh's anonymous allowance of 250 messages a day is counted per GitHub runner address and no other user of that address exhausts it — a night sends at most about 20; if a send meets 429, `notify` exits 1 and the next night resends what is still within the window.
- **A26** MotherDuck at about 680 instruments stays inside Lite with D87 — unmeasurable on Lite (I22), so the store's busy time under 5 minutes a night is the proxy; Lite's pricing page does not say what happens past the included 10 CU-hours without a card; if the busy time grows, Sunday's full fetch moves to the 1st of the month and the warm list shrinks to the featured.
- **A27** Yahoo serves about 700 requests a night at one a second to Actions runners without a block — A2 held at 90; if throttled, the pace drops to one every two seconds, about 24 minutes, inside the 60-minute timeout.
- **A28** The project now lives past 60 days as the first piece of a trading assistant (supersedes A3); R7's data class still holds until the owner says otherwise (Q8).
- **A29** Wikipedia's S&P 500 table keeps `id="constituents"` and its `Symbol`, `Security` and `GICS Sector` columns — read on 2026-11-18 with `pandas.read_html`, 503 rows; if it changes, `universe sync` fails and the CSV stays as it was.
- **A30** Base rates over today's members' whole histories carry survivorship bias (members that fell out are absent) and are in-sample for the rules' parameters, which the 2026-11-18 calibration chose on 20 of these instruments — the Signals screen says so; a split by period (I32) would show how stable they are.
- **A31** Wikipedia's Nasdaq-100 page held no member table on 2026-11-18 (`pandas.read_html` found none), so the Nasdaq-100 members outside the S&P 500 are curated by hand (D86).
- **A32** `gh workflow enable` on an enabled workflow counts as activity for GitHub's 60-day rule, as keepalive-workflow's API mode relies on — unverified (GitHub's docs name the rule, not what counts); if not, the monthly commit when the S&P 500 changes and the owner's own pushes are the activity, and the keepalive becomes an empty commit.
- **A33** The share `market_data_api` (D77, `update automatic`) carries the new tables and the `period_bars` view to the API's service account — unverified until M9's tables exist; if a view does not cross the share, `period_bars` becomes a table the `signals` stage replaces.

### Questions

- **Q1** Should the nightly use a MotherDuck service account's token, reaching only its own database, instead of your personal token, which reaches all your databases from a public repository's Actions? — recommended: yes, create a service account (Lite allows two) and replace the `MOTHERDUCK_TOKEN` secret; blocks nothing, the build proceeds on A1.
- **Q3** Should each instrument carry a quote unit (`USD`, `index points`, `USD per oz`) in the universe so the headline tiles and the Ticker's last-close tile can name it? — live evaluator round 2 failed criterion 8 (Copy) on that alone; the table subtitle names the unit already; recommended: yes, a `unit` column in `universe.csv` and `tickers` (a migration); blocks nothing, M4 ticked on it as open polish.
- **Q2** At teardown, delete the repository, drop the MotherDuck database and revoke the token? — recommended: yes, by the README's teardown commands, run by you since each is irreversible; from M7 also delete the Worker and its KV namespace (`wrangler delete`), revoke the Cloudflare API token, and drop the share and the API's service account; blocks nothing.
- **Q4** *(answered yes 2026-11-18 by the owner's brief to M7: a separate read-only service account; done, D77)* Should the API read MotherDuck with a service account's token through a read-only share of `market_data` (D57), rather than your own token, which can write and reaches every database you have, now held by Cloudflare as well as GitHub? — recommended: yes; on your yes Claude does it with your token in one sitting, nothing printed: MotherDuck's REST `POST /v1/users` for `market-data-api`, `create share market_data_api from market_data (access restricted, visibility hidden, update automatic)` and `grant read on share market_data_api to market-data-api`, the account's token piped straight into `gh secret set MOTHERDUCK_API_TOKEN`, then the share attached once with that token; blocks M7's deploy.
- **Q5** *(done 2026-11-18: the owner signed in, subdomain `henrymckay`, both repository secrets set)* Will you sign in to Cloudflare once and hand GitHub a deploy token, so every later deploy runs from Actions? — Claude cannot create or sign in to an account; the steps, about ten minutes, in order:
  1. Sign up at <https://dash.cloudflare.com/sign-up> with an email and password and verify the email; the Workers Free plan needs no card, and if a page asks for one, stop and tell Claude.
  2. Open Workers & Pages once, so the account's `workers.dev` subdomain exists, and note it (shown as "Your subdomain"; set one if asked).
  3. Note the Account ID from the same page's right-hand column (or Account home, the account's menu, Copy account ID).
  4. Go to My Profile, API Tokens, Create Token, use the "Edit Cloudflare Workers" template, set Account Resources to your one account and Zone Resources to none or all zones (there are none), then Continue, Create Token and copy it; it is shown once.
  5. In a terminal in any directory run `gh secret set CLOUDFLARE_API_TOKEN --repo henrymckay/market-data-public` and paste the token at its hidden prompt, so it is never in your shell history or a file.
  6. Run `gh secret set CLOUDFLARE_ACCOUNT_ID --repo henrymckay/market-data-public` and paste the Account ID.
  7. Answer Q4 and tell Claude the subdomain; Claude then runs M7 from step one of its list.
  — recommended: yes; blocks M7.
- **Q6** Is a dashboard that trails MotherDuck by up to 15 minutes live enough (D53)? — the store changes once a night, so a read through the cache gives the same answer a direct read would except in the minutes after a run; a direct query per request is truly live but turns every page view, or a flood of them, into MotherDuck compute billed past Lite's 10 CU-hours with no ceiling; recommended: yes; blocks nothing, built on yes.

- **Q7** Two live-evaluator findings after round 2 (M7) stay open: criterion 5, on a phone the Runs coverage table's Status column, the monthly calendar's last months and the Markets table's later periods sit beyond the card's own horizontal scroll with no cue (the page itself never scrolls sideways; `design-interface` lets a table scroll inside its card) — proposed: below 640 px hide the low-value columns and add an edge fade; and criterion 7, the first switch to an instrument takes 330 to 1,017 ms (median about 590 to 650) against R4's 500 ms because the whole history is 300 to 490 KB compressed over a variable link, while a cached switch takes 77 to 274 ms — proposed: a first body of the last few years with the rest fetched after (I14, which D55 rules out until the owner agrees to a `years` parameter) or a prefetch of the search's top results; recommended: yes to the first body; blocks nothing, M7 not ticked on R4's line until answered.
- **Q8** R7 calls this a throwaway test, which is why Yahoo's terms were set aside and the data, now signals too, sits in a public repository and site; does that still hold for the first piece of a trading assistant? — recommended: yes for now, since everything is public market data and nothing reveals what you hold; revisit before anything is shared or commercial; blocks nothing, built on yes (A28).
- **Q9** Will you subscribe your phone to the alert topic? — Claude cannot install an app; about two minutes:
  1. Install ntfy from the App Store or Google Play; no account is needed.
  2. In a terminal on this Mac, run `security find-generic-password -a "$USER" -s ntfy-market-monitor -w | pbcopy`, which copies the topic without showing it.
  3. In the app, tap +, paste the topic, leave the server as `ntfy.sh`, and subscribe; on Android, allow notifications and, under the topic's settings, automatic download of attachments.
  4. Never post the topic anywhere; whoever has it can read and send your alerts.
  — recommended: yes; blocks only your seeing the alerts, which are sent and cached for 12 hours from M10.
- **Q10** Is the delivery right: a push for each signal graded A (at most ten a night) with its chart, one digest per asset type for A and B, C and failures on the Signals screen only (D90, D91)? — the calibration suggests about 11 daily signals a night across 680 instruments, 13 weekly on Mondays and 8 monthly on the 1st; recommended: yes, and tune `push-grade`, `digest-grade` and `muted-asset-classes` in `monitor.yaml` after the first week; blocks nothing.
- **Q11** Do you want a second run after the US close (about 21:30 UTC) so US daily signals arrive the same evening? — recommended: no for now (A23); it costs a second fetch of the US instruments a day; blocks nothing.

### Ideas

- **I1** A weekly keepalive (an empty commit or `gh workflow enable` from a second schedule) so the nightly survives past 60 days — costs one workflow; built monthly by D100 (M8).
- **I2** Grow the universe to the S&P 500 — a real breadth heatmap; costs 500 requests a night (about 9 minutes at one a second) and more rate-limit risk; built by D86 (M8).
- **I3** Size the treemap by market cap from `yfinance`'s `info` — truer weights; costs a second, heavier, more throttled request per stock; not built.
- **I4** Publish the database as a MotherDuck share so the owner can query it from any MotherDuck session without the pipeline's token — costs one statement and an account action; not built.
- **I6** `pyrate_limiter` logs its bucket set-up at INFO and the connected-seconds log covers fetching too for a local run; split fetch and load timings if R6 needs the load alone — costs a second timer; not built.
- **I7** Preload the Inter latin font and brotli-compress the site data on the host; the throttled cold load (1.6 s at 1.6 Mbit/s, 150 ms) is over 1.5 s though the loopback one is 0.5 s — costs a hashed-name lookup in the build; not built.
- **I8** A colour-scale legend for the treemap, tap-for-detail on a phone's small tiles, and the instrument in the Ticker page title — evaluator round 2 nits; not built.
- **I9** Add the Lightweight Charts attribution as footer text and turn the logo off (`attributionLogo: false`), so it stops covering the volume pane's corner; the live age chip also stays a skeleton when `overview.parquet` fails to load — live evaluator round 1 nits; not built.
- **I10** The live cold load on a throttled 1.6 Mbit/s, 150 ms link was 1.9 s (budget 1.5 s) while a normal link's median was 0.5 s over seven cold loads — same cause as I7; not built.
- **I5** An ntfy alert on a failed or missed night (`send-messages`) — costs a topic secret and a status workflow; built by D93 (M10).
- **I11** Cloudflare's Workers Caching (`cache.enabled`, docs updated 2026-10-30) in place of KV: hits never invoke the Worker or spend CPU, tiered and purgeable by `Cache-Tag`; its Free-plan and `workers.dev` support are unstated — costs a trial deploy in M7; not built.
- **I12** Place the Worker near MotherDuck's `eu-west-1` (Smart Placement or a placement hint) so a cache miss pays a short round trip instead of one from the visitor's edge — costs a config line, Free-plan support unverified; not built.
- **I13** Serve the front end from the Worker's static assets: one origin, no CORS, one deploy and no Pages job — costs the Pages URL the README and evaluator rounds use; not built.
- **I14** Send a year of bars first and the rest after, so the Ticker screen draws within 500 ms even on a cold miss — costs a second request per instrument and a parameter D55 rules out; not built.
- **I16** `@cloudflare/vitest-pool-workers` is renamed `@cloudflare/vitest-plugin` and no longer updated (its own banner, 2026-11-18); migrate with `npx @cloudflare/codemods vitest:pool-workers-to-vitest-plugin`, which may also lift D69's date pin — costs one dependency swap; not built.
- **I17** A cache miss on `/api/bars/aapl` took 5.5 s from the laptop and `eurusdx` 2.6 s: the miss cost is the MotherDuck round trip and the 20 s timeout is far off, but `warm` (D60) is what keeps visitors off it; not built.
- **I15** Send prices at `float` precision (Yahoo's values are 32-bit, so `268.82000732421875` is `268.82`) to roughly halve the bars bodies — a quick cast in the live test did not shrink DuckDB's JSON, so it needs a rounding rule per quote; not built.
- **I18** The age chip stays a blank skeleton and the Ticker's return tiles show a bare dash when the API fails; write "Age unknown" there — evaluator round 1 nit; not built.
- **I19** An unset `VITE_API_URL` leaves a literal `%VITE_API_URL%` preload request and a console error in `index.html`; a build guard that fails on it would be clearer — code review nit; not built.
- **I20** The live instrument switch measured a median of 503 to 713 ms before the prefetch and 521 to 923 ms after (first switch about 1 s, loading the Ticker's code; later ones 300 to 600 ms), on a laptop whose link varied from 730 ms to 1.8 s for the Markets load: R4's 500 ms line is not met reliably from here, and the cause is the 300 to 490 KB compressed history each switch downloads; costs a smaller first body (a year of bars first, I14) or a prefetch of the headline instruments after the first paint; not built.
- **I21** The cron can read `latest` in the seconds between the `yahoo` run's row and `compute` replacing `overview`, and then caches the old overview under the new version until the next night (about 2 s in 900); keying the version on the `metrics` run's `ended` closes it; not built.
- **I22** MotherDuck's usage is not readable on Lite (`md_information_schema.compute_usage` and `query_history` need a paid plan), so R6's month-to-date CU-hours is read from the billing page by the owner; the logged connected time (101 s a nightly) is the proxy; not built.
- **I23** The docs page's `Inter` would come from the Pages site's hashed font file if the build wrote a fixed name for it; costs a build rule; not built.
- **I24** A Sunday review push: the week's signals and how each has done against its base rate, with a link to the Signals screen — closes the loop on R17 without opening the page; costs a message kind; not built.
- **I25** "Useful" and "Noise" buttons on each push (ntfy `http` actions) posting to a Worker endpoint that stores the owner's verdict per signal, joined into the base rates — the owner's judgement trains the grades; costs a write path and a per-alert token on a read-only API; not built.
- **I26** A 4-hour layer from 1-hour bars (730 days on Yahoo) for crypto and the featured list, run every four hours — catches turns a day sooner; costs about 110 requests a run and six runs a day; not built.
- **I27** A watchdog in the Worker's cron that posts to the topic when the nightly is stale, surviving an Actions outage or a disabled schedule — costs the topic held by Cloudflare too; not built.
- **I28** More score factors: relative strength against SPY and the sector ETF, days to the next earnings (`yfinance` calendar, a request per stock), distance from the 52-week high, a volatility squeeze before the break — each is a column the base rates can judge; not built.
- **I29** The kernel in `numba` or a Polars plugin, earned when the `signals` stage passes its 5-minute budget; not built.
- **I30** Nasdaq-100 membership from Nasdaq's own list, the Russell 1000, Europe's and Asia's large caps; costs requests and a second member source; not built.
- **I31** A Claude routine fired for each A push, writing a paragraph of context from the chart and recent news (`send-messages`, Reach Claude) — earned when a line is not enough; costs a session per fire; not built.
- **I32** Base rates split by period (before and after 2015) and a walk-forward check of each rules change, so the owner sees whether an edge is stable or fitted; costs a column in `signal_stats`; not built.
