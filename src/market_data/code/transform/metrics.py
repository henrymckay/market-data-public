"""The figures derived from stored bars: returns, ranges, volatility, drawdown."""

import dataclasses
import math

import polars

_TRADING_DAYS = 252
_TRADED_VALUE_BARS = 20
_YEAR = "-1y"

_EMPTY = polars.Schema(
    {
        "day": polars.Date,
        "metric": polars.String,
        "ticker": polars.String,
        "value": polars.Float64,
    }
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class _Window:
    """A window's name, where it starts and the years it is annualised over."""

    name: str
    start: polars.Expr
    years: int | None = None


def _back(offset: str) -> polars.Expr:
    """Return the date an offset before the instrument's last bar."""
    return polars.col("day").max().dt.offset_by(offset).over("ticker")


def _windows() -> tuple[_Window, ...]:
    """Return the plan's windows, each measured from a date before the last bar."""
    year_end = polars.date(polars.col("day").max().dt.year() - 1, 12, 31).over("ticker")
    return (
        _Window(name="1d", start=_back("-1d")),
        _Window(name="1w", start=_back("-1w")),
        _Window(name="1m", start=_back("-1mo")),
        _Window(name="3m", start=_back("-3mo")),
        _Window(name="ytd", start=year_end),
        _Window(name="1y", start=_back(_YEAR)),
        _Window(name="3y", start=_back("-3y"), years=3),
        _Window(name="5y", start=_back("-5y"), years=5),
    )


def _long(frame: polars.DataFrame, metric: str, value: polars.Expr) -> polars.DataFrame:
    """Return one metric per instrument as long rows, without the nulls."""
    return (
        frame.select(
            "day", polars.lit(metric).alias("metric"), "ticker", value.alias("value")
        )
        .filter(polars.col("value").is_not_null() & polars.col("value").is_finite())
        .select(_EMPTY.names())
    )


def _window_figures(
    window: _Window, *, bars: polars.DataFrame, lasts: polars.DataFrame
) -> list[polars.DataFrame]:
    """Return the window's return and change, from the bar at or before its start."""
    starts = (
        bars.select("ticker", window.start.alias("start"))
        .unique("ticker")
        .sort("start")
    )
    opening = bars.select("ticker", "day", polars.col("adj_close").alias("opening"))
    paired = (
        lasts.join(starts, on="ticker")
        .sort("start")
        .join_asof(
            opening.sort("day"),
            left_on="start",
            right_on="day",
            by="ticker",
            strategy="backward",
            check_sortedness=False,
            suffix="_open",
        )
    )
    ratio = polars.col("last_adj") / polars.col("opening")
    growth = ratio if window.years is None else ratio.pow(1 / window.years)
    return [
        _long(paired, f"return_{window.name}", growth - 1),
        _long(
            paired,
            f"change_{window.name}",
            polars.col("last_adj") - polars.col("opening"),
        ),
    ]


def build_metrics(bars: polars.DataFrame) -> polars.DataFrame:
    """Derive every metric for every instrument, as of its last bar.

    Returns and changes use adjusted close, measured from the last bar at or
    before each window's start and absent where history does not reach it;
    3-year and 5-year returns are annualised. The 52-week range, volatility and
    drawdown cover the bars in the year to the last bar, and traded value the
    last 20 bars.

    :param bars: Stored bars, one row per instrument and day.
    :returns: One row per instrument and metric: `day`, `metric`, `ticker`, `value`.
    """
    if bars.is_empty():
        return polars.DataFrame(schema=_EMPTY)
    ordered = bars.sort("ticker", "day").with_columns(
        daily=polars.col("adj_close").pct_change().over("ticker"),
        traded=(polars.col("close") * polars.col("volume")).cast(polars.Float64),
    )
    lasts = ordered.group_by("ticker").agg(
        day=polars.col("day").max(),
        last_adj=polars.col("adj_close").last(),
        last_close=polars.col("close").last(),
        traded_value_20d=polars.col("traded").tail(_TRADED_VALUE_BARS).mean(),
    )
    in_year = ordered.filter(polars.col("day") > _back(_YEAR)).with_columns(
        drawdown=polars.col("adj_close")
        / polars.col("adj_close").cum_max().over("ticker")
        - 1
    )
    year = (
        in_year.group_by("ticker")
        .agg(
            high_52w=polars.col("high").max(),
            low_52w=polars.col("low").min(),
            volatility_1y=polars.col("daily").std() * math.sqrt(_TRADING_DAYS),
            drawdown_max_1y=polars.col("drawdown").min(),
        )
        .join(lasts.select("ticker", "day"), on="ticker")
    )
    figures = [
        _long(lasts, "last_close", polars.col("last_close")),
        _long(lasts, "traded_value_20d", polars.col("traded_value_20d")),
        *(
            _long(year, name, polars.col(name))
            for name in ("high_52w", "low_52w", "volatility_1y", "drawdown_max_1y")
        ),
        *(
            figure
            for window in _windows()
            for figure in _window_figures(window, bars=ordered, lasts=lasts)
        ),
    ]
    return polars.concat(figures).sort("ticker", "metric")
