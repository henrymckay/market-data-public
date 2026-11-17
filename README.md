# market-data-public

A nightly job that fetches daily prices for about ninety instruments from Yahoo Finance with `yfinance` and stores them in MotherDuck.
A static dashboard reads the exported data; the scheduled GitHub Actions run and the deploy arrive in later milestones (see `PLAN.md`); this is a throwaway end-to-end test.

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
- `export --output web/public/data` writes the dashboard's data (`overview.parquet`, `bars/<slug>.parquet`, `runs.parquet`, `latest.json`) and prints a `path,rows,bytes` row per file.
- Exit codes: 0 every instrument stored, 1 any `partial` or `failed`, 2 a usage or configuration error such as a missing token.

`.github/workflows/nightly.yml` runs `nightly` then `status` at 02:17 UTC every day and on demand, with the repository secret `MOTHERDUCK_TOKEN` as `motherduck_token`; `PLAN.md` (M2) lists the steps still to take before it can run.

Every night replaces each answering instrument's whole history, so a re-run is safe and leaves the same rows.

## Dashboard

A Vite, React and TypeScript app in `web/`; Node comes from `nodejs-wheel` through `uv`, so none is needed on the system.

```bash
uv sync
MARKET_DATA_DATABASE=/tmp/market.duckdb uv run market-data-cli export --output web/public/data
uv run npm --prefix web ci
uv run npm --prefix web run build
uv run npm --prefix web run preview    # http://127.0.0.1:4173/
```

Four screens: Markets, Ticker, Compare and Runs; every view is a link (`?view=ticker&t=AAPL&range=5Y`), `/` opens the search, and the page follows the system's light or dark scheme.
`web/public/data/` is generated and git-ignored.

## Develop

```bash
uv run pytest
uv run ruff check && uv run ruff format --check
uv run pyright
uv run pytest -m real   # one run against Yahoo itself
uv run npm --prefix web run typecheck && uv run npm --prefix web run lint && uv run npm --prefix web test
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" uv run pytest -m slow   # browser smokes over web/dist; build first
```
