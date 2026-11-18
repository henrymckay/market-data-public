"""Builders of the tables the alerts read: signals, base rates, structure, runs."""

import datetime

import polars

from market_data.code import port
from market_data.code.transform import signals as signals_

TODAY = datetime.date(2026, 11, 18)
NOW = datetime.datetime(2026, 11, 18, 3, 0, tzinfo=datetime.UTC)


def signal(ticker: str = "NVDA", **changes: object) -> dict[str, object]:
    """Return one stored signal row: a weekly `break_up` graded A, known yesterday."""
    row: dict[str, object] = {
        "aligned": True,
        "atr": 5.0,
        "close": 145.30,
        "day": datetime.date(2026, 11, 9),
        "direction": "up",
        "event": "break_up",
        "grade": "A",
        "held_to_date": True,
        "known": datetime.date(2026, 11, 17),
        "level": 142.10,
        "margin_atr": 0.64,
        "return_to_date": 0.01,
        "rules": "abc",
        "score": 4,
        "stop": 128.40,
        "swing_atr": 3.0,
        "ticker": ticker,
        "timeframe": "w",
        "trend_swings": 4,
        "volume_ratio": 1.8,
    }
    row |= changes
    row["id"] = changes.get(
        "id", f"{ticker}|{row['timeframe']}|{row['event']}|{row['day']}"
    )
    return row


def signals_of(*rows: dict[str, object]) -> polars.DataFrame:
    """Return the rows as the `signals` table."""
    return polars.DataFrame(list(rows), schema=signals_.SIGNALS)


def tickers_of(*rows: tuple[str, str]) -> polars.DataFrame:
    """Return a universe of (ticker, asset class) pairs, named after the ticker."""
    return polars.DataFrame(
        {
            "active": [True] * len(rows),
            "asset_class": [asset_class for _, asset_class in rows],
            "featured": [True] * len(rows),
            "name": [f"{ticker} Inc" for ticker, _ in rows],
            "quote_type": ["price"] * len(rows),
            "sector": ["Tech"] * len(rows),
            "source": ["curated"] * len(rows),
            "ticker": [ticker for ticker, _ in rows],
        },
        schema=port.UNIVERSE,
    )


def stat(*, asset_class: str = "stock", **changes: object) -> dict[str, object]:
    """Return one `signal_stats` row at the weekly primary horizon, grade all."""
    row: dict[str, object] = {
        "asset_class": asset_class,
        "baseline_hit": 0.61,
        "baseline_mean": 0.002,
        "edge": 0.01,
        "event": "break_up",
        "grade": "all",
        "held_rate": 0.7,
        "hit_rate": 0.66,
        "horizon": 13,
        "mae_median": -0.05,
        "mean_return": 0.012,
        "median_return": 0.01,
        "mfe_median": 0.08,
        "n": 412,
        "rules": "abc",
        "timeframe": "w",
    }
    return row | changes


def stats_of(*rows: dict[str, object]) -> polars.DataFrame:
    """Return the rows as `signal_stats`."""
    return polars.DataFrame(list(rows), schema=signals_.SIGNAL_STATS)


def structure_of(*rows: tuple[str, str, str]) -> polars.DataFrame:
    """Return (ticker, timeframe, state) triples as the `structure` table."""
    return polars.DataFrame(
        {
            "last_high": [None] * len(rows),
            "last_low": [None] * len(rows),
            "since": [None] * len(rows),
            "state": [state for _, _, state in rows],
            "ticker": [ticker for ticker, _, _ in rows],
            "timeframe": [timeframe for _, timeframe, _ in rows],
        },
        schema=signals_.STRUCTURE,
    )


def nothing_sent() -> polars.DataFrame:
    """Return the `id` column of an empty `alerts` table."""
    return polars.DataFrame(schema={"id": polars.String})


def runs_of(*rows: tuple[str, str, int, datetime.timedelta]) -> polars.DataFrame:
    """Return (source, outcome, failed items, age) as manifest rows before NOW."""
    return polars.DataFrame(
        {
            "ended": [NOW - age for *_, age in rows],
            "failed_items": [failed for _, _, failed, _ in rows],
            "outcome": [outcome for _, outcome, *_ in rows],
            "source": [source for source, *_ in rows],
        },
        schema={
            "ended": polars.Datetime(time_zone="UTC"),
            "failed_items": polars.Int64,
            "outcome": polars.String,
            "source": polars.String,
        },
    )
