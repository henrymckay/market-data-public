"""Hand-built price paths whose swings and events can be read off the page."""

import collections.abc
import datetime

import numpy
import polars

from market_data.code.adapt import motherduck

SPREAD = 0.5

# With a one-bar ATR and steps of one point the true range is 1.5, so at k=2 a swing
# confirms three points back from its extreme: highs 110.5 (bar 10), 109.5 (23) and
# 107.5 (35), lows 102.5 (17), 101.5 (30) and 100.5 (41), then a close of 108 on
# bar 48, above the last lower high.
DOWNTREND = (
    *range(100, 111),
    *range(109, 102, -1),
    *range(104, 110),
    *range(108, 101, -1),
    *range(103, 108),
    *range(106, 100, -1),
    *range(102, 109),
)
# The break holds: a new high of 110.5 (bar 50), a pullback to a low of 103.5
# (bar 56) and a close of 107 on bar 59 that confirms it.
CONFIRMED = (*DOWNTREND, 109, 110, 109, 108, 107, 106, 105, 104, 105, 106, 107)
# The break fails on a close of 100 (bar 56), under the last low of 100.5.
FAILED_ON_CLOSE = (*DOWNTREND, 107, 106, 105, 104, 103, 102, 101, 100)
# The break fails on a swing low of 100.5 (bar 59) confirmed on bar 62.
FAILED_ON_SWING = (
    *DOWNTREND,
    *(109, 110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 102, 103, 104),
)


def path(closes: collections.abc.Sequence[float]) -> dict[str, numpy.ndarray]:
    """Return bars whose high and low sit half a point either side of each close."""
    close = numpy.array(closes, dtype=float)
    return {"close": close, "high": close + SPREAD, "low": close - SPREAD}


def mirror(
    bars: dict[str, numpy.ndarray], around: float = 200.0
) -> dict[str, numpy.ndarray]:
    """Return the path seen in a mirror: highs become lows."""
    return {
        "close": around - bars["close"],
        "high": around - bars["low"],
        "low": around - bars["high"],
    }


def weekdays(start: datetime.date, count: int) -> list[datetime.date]:
    """Return `count` consecutive weekdays from `start`, skipping weekends."""
    days: list[datetime.date] = []
    day = start
    while len(days) < count:
        if day.weekday() < 5:
            days.append(day)
        day += datetime.timedelta(days=1)
    return days


def daily_frame(
    ticker: str,
    closes: collections.abc.Sequence[float],
    *,
    start: datetime.date = datetime.date(2024, 1, 1),
    volumes: collections.abc.Sequence[int | None] | None = None,
    wicks: dict[int, float] | None = None,
) -> polars.DataFrame:
    """Return bars on consecutive weekdays, half a point either side of each close."""
    bars = path(closes)
    highs = bars["high"].copy()
    for row, high in (wicks or {}).items():
        highs[row] = high
    return polars.DataFrame(
        {
            "adj_close": bars["close"],
            "close": bars["close"],
            "day": weekdays(start, len(closes)),
            "dividend": 0.0,
            "high": highs,
            "low": bars["low"],
            "open": bars["close"],
            "split": 0.0,
            "ticker": ticker,
            "volume": list(volumes) if volumes is not None else [100] * len(closes),
        },
        schema_overrides={"volume": polars.Int64},
    )


def periods_of(bars: polars.DataFrame) -> polars.DataFrame:
    """Return the `period_bars` view over bars, as the store's migrations define it."""
    connection = motherduck.connect(":memory:")
    connection.register("incoming", bars.to_arrow())
    connection.execute(
        "insert into bars (adj_close, close, day, dividend, fetched, high, low, open,"
        " split, ticker, volume) select adj_close, close, day, dividend, null, high,"
        " low, open, split, ticker, volume from incoming"
    )
    return connection.execute(
        "select adj_close, close, day, high, last_day, low, open, ticker, timeframe,"
        " volume from period_bars"
    ).pl()
