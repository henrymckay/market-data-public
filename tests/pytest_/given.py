"""Fixtures: the starting states the tests are given."""

import datetime
import pathlib

import pandas
import polars
import pytest

from market_data.code import port, transform
from market_data.code.adapt import rules as rules_adapter
from market_data.code.adapt import universe as universe_adapter

_DATA = pathlib.Path(__file__).parent.parent / "data"


def _bar(ticker: str, day: datetime.date, **changes: float | None) -> dict[str, object]:
    """Return one valid bar for a ticker and day, with fields overridden."""
    bar: dict[str, object] = {
        "adj_close": 10.0,
        "close": 10.0,
        "day": day,
        "dividend": 0.0,
        "high": 11.0,
        "low": 9.0,
        "open": 10.0,
        "split": 0.0,
        "ticker": ticker,
        "volume": 100,
    }
    return bar | changes


@pytest.fixture
def aapl_frame() -> pandas.DataFrame:
    """Yahoo's raw frame for AAPL over two years, as recorded."""
    return pandas.read_parquet(_DATA / "yahoo" / "aapl.parquet")


@pytest.fixture
def eurusd_frame() -> pandas.DataFrame:
    """Yahoo's raw frame for EURUSD=X over a month, forming bar included."""
    return pandas.read_parquet(_DATA / "yahoo" / "eurusdx.parquet")


@pytest.fixture
def make_bars():
    """Return a builder of bars frames from (ticker, day, overrides) triples."""

    def make(*rows: tuple[str, datetime.date, dict[str, float | None]]):
        return polars.DataFrame(
            [_bar(ticker, day, **changes) for ticker, day, changes in rows],
            schema=port.BARS,
        )

    return make


@pytest.fixture
def small_universe() -> polars.DataFrame:
    """A universe of two prices and one yield, all active."""
    return polars.DataFrame(
        {
            "active": [True, True, True],
            "asset_class": ["stock", "stock", "rate"],
            "featured": [True, False, True],
            "name": ["Alpha", "Beta", "Ten year"],
            "quote_type": ["price", "price", "yield"],
            "sector": ["Tech", "Tech", "Treasury yield"],
            "source": ["sp500", "sp500", "curated"],
            "ticker": ["AAA", "BBB", "^TNX"],
        },
        schema=port.UNIVERSE,
    )


@pytest.fixture
def no_structure() -> polars.DataFrame:
    """A stored structure with no row."""
    return polars.DataFrame(
        schema={
            "state": polars.String,
            "ticker": polars.String,
            "timeframe": polars.String,
        }
    )


@pytest.fixture
def real_universe() -> polars.DataFrame:
    """The packaged universe."""
    return universe_adapter.read_universe()


@pytest.fixture
def monday() -> datetime.date:
    """A UTC date the run treats as today."""
    return datetime.date(2026, 11, 16)


@pytest.fixture
def clock():
    """Return a clock stepping a minute per read from 02:17 UTC on 2026-11-17."""
    ticks = iter(
        datetime.datetime(2026, 11, 17, 2, 17, tzinfo=datetime.UTC)
        + datetime.timedelta(minutes=minute)
        for minute in range(100)
    )
    return lambda: next(ticks)


@pytest.fixture
def rules():
    """The packaged rules with one-bar ATRs, so hand-built paths set the swings."""
    packaged = rules_adapter.read_rules()
    return packaged.model_copy(
        update={
            "atr_bars": 1,
            "swing_atr": transform.PerTimeframe(d=2.0, m=2.0, w=2.0),
        }
    )


@pytest.fixture
def universe_frame() -> polars.DataFrame:
    """A one-stock universe for the signals tests."""
    return polars.DataFrame(
        {
            "active": [True],
            "asset_class": ["stock"],
            "featured": [True],
            "name": ["Alpha"],
            "quote_type": ["price"],
            "sector": ["Tech"],
            "source": ["sp500"],
            "ticker": ["AAA"],
        },
        schema=port.UNIVERSE,
    )
