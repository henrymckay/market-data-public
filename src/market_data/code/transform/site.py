"""Shape the stored tables into the files the dashboard reads."""

import re

import polars
import polars.selectors

_SPARK_BARS = 63
_SPARK_DIGITS = 5
_METRIC_DIGITS = 7
_PUNCTUATION = re.compile(r"[\^=.]")

_WINDOWS = ("1d", "1w", "1m", "3m", "ytd", "1y", "3y", "5y")
METRICS = (
    *(f"return_{window}" for window in _WINDOWS),
    *(f"change_{window}" for window in _WINDOWS),
    "high_52w",
    "low_52w",
    "volatility_1y",
    "drawdown_max_1y",
    "traded_value_20d",
    "last_close",
)


def slug(ticker: str) -> str:
    """Return the ticker lower-cased without `^`, `=` and `.`, as a file name."""
    return _PUNCTUATION.sub("", ticker.lower())


def build_overview(
    *,
    bars: polars.DataFrame,
    metrics: polars.DataFrame,
    rejected: polars.DataFrame,
    tickers: polars.DataFrame,
) -> polars.DataFrame:
    """Return one row per instrument: its identity, metrics, coverage and sparkline.

    An instrument with no bars stays, with null figures and a bar count of 0, so
    a dead symbol shows in the coverage.
    Figures are rounded to seven significant digits and the sparkline to five,
    which keeps the API's overview body small for a page that shows fewer.

    :param bars: Stored bars, with `adj_close`, `day` and `ticker`.
    :param metrics: Long metrics: `metric`, `ticker`, `value`.
    :param rejected: Rejected rows per instrument: `ticker`, `rejected`.
    :param tickers: The stored universe.
    :returns: The overview, sorted by ticker.
    """
    wide = metrics.pivot(on="metric", index="ticker", values="value").select(
        "ticker",
        *(
            polars.col(name)
            if name in metrics.get_column("metric").unique()
            else polars.lit(None, polars.Float64).alias(name)
            for name in METRICS
        ),
    )
    ordered = bars.sort("ticker", "day")
    coverage = ordered.group_by("ticker").agg(
        bar_count=polars.len(),
        first_day=polars.col("day").first(),
        last_day=polars.col("day").last(),
        spark=polars.col("adj_close").tail(_SPARK_BARS),
    )
    return (
        tickers.join(wide, on="ticker", how="left")
        .join(coverage, on="ticker", how="left")
        .join(rejected, on="ticker", how="left")
        .with_columns(
            bar_count=polars.col("bar_count").fill_null(0),
            rejected=polars.col("rejected").fill_null(0),
            slug=polars.col("ticker").map_elements(slug, return_dtype=polars.String),
        )
        .with_columns(
            polars.selectors.float().round_sig_figs(_METRIC_DIGITS),
            polars.col("spark").list.eval(
                polars.element().round_sig_figs(_SPARK_DIGITS)
            ),
        )
        .sort("ticker")
    )
