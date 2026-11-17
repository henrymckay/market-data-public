# market-data-public

A nightly job that fetches daily prices for about ninety instruments from Yahoo Finance with `yfinance` and stores them in MotherDuck.
A static dashboard and the scheduled GitHub Actions run arrive in later milestones (see `PLAN.md`); this is a throwaway end-to-end test.

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
- Both print one CSV manifest row on standard output; logs go to standard error.
- Exit codes: 0 every instrument stored, 1 any `partial` or `failed`, 2 a usage or configuration error such as a missing token.

Every night replaces each answering instrument's whole history, so a re-run is safe and leaves the same rows.

## Develop

```bash
uv run pytest
uv run ruff check && uv run ruff format --check
uv run pyright
uv run pytest -m real   # one run against Yahoo itself
```
