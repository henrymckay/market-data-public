"""Put daily, weekly and monthly bars on one footing and drop the unfinished ones."""

import datetime

import polars

_BAR_COLUMNS = (
    "adj_close",
    "close",
    "day",
    "high",
    "last_day",
    "low",
    "ticker",
    "timeframe",
    "volume",
)


def build_timeframe_bars(
    daily: polars.DataFrame, periods: polars.DataFrame, *, today: datetime.date
) -> polars.DataFrame:
    """Return every complete bar on every timeframe, sorted by ticker, timeframe, day.

    A period counts only once its last calendar day (the Sunday, the month's end)
    is before `today`; a bar with no high, low or close is dropped.

    :param daily: Stored bars with `adj_close`, `close`, `day`, `high`, `low`,
        `ticker` and `volume`.
    :param periods: The `period_bars` view's rows.
    :param today: The run's UTC date.
    :returns: Rows with `adj_close`, `close`, `day`, `high`, `last_day`, `low`,
        `ticker`, `timeframe` and `volume`.
    """
    day = polars.col("day")
    period_end = (
        polars.when(polars.col("timeframe").eq("w"))
        .then(day.dt.offset_by("6d"))
        .when(polars.col("timeframe").eq("m"))
        .then(day.dt.month_end())
        .otherwise(day)
    )
    return (
        polars.concat(
            [
                daily.with_columns(last_day=day, timeframe=polars.lit("d")).select(
                    _BAR_COLUMNS
                ),
                periods.select(_BAR_COLUMNS),
            ]
        )
        .filter(
            period_end.lt(today),
            polars.col("close").is_finite(),
            polars.col("high").is_finite(),
            polars.col("low").is_finite(),
        )
        .sort("ticker", "timeframe", "day")
    )
