"""Rules over bars: which are complete and which are valid."""

import datetime

import polars

_PRICES = ("open", "high", "low", "close", "adj_close")

_REASONS = (
    (
        "null or non-finite close",
        polars.col("close").is_null() | ~polars.col("close").is_finite(),
    ),
    (
        "null or non-finite adjusted close",
        polars.col("adj_close").is_null() | ~polars.col("adj_close").is_finite(),
    ),
    (
        "non-positive price",
        polars.col("quote_type").eq("price")
        & polars.any_horizontal(polars.col(*_PRICES).le(0).fill_null(False)),
    ),
    ("high below low", polars.col("high").lt(polars.col("low")).fill_null(False)),
    ("duplicate day", polars.struct("ticker", "day").is_first_distinct().not_()),
)


def keep_complete(bars: polars.DataFrame, *, today: datetime.date) -> polars.DataFrame:
    """Drop bars dated on or after the run's UTC date, which are still forming.

    :param bars: Bars of any days.
    :param today: The run's UTC date.
    :returns: The bars dated before it.
    """
    return bars.filter(polars.col("day").lt(today))


def validate_bars(
    bars: polars.DataFrame, *, universe: polars.DataFrame
) -> tuple[polars.DataFrame, polars.DataFrame]:
    """Split complete bars into valid bars and rejected rows with a reason.

    :param bars: Complete bars of the port's schema.
    :param universe: The universe, for each instrument's quote type.
    :returns: The valid bars, and the rejected rows (day, reason, record, ticker).
    """
    columns = bars.columns
    judged = bars.join(
        universe.select("ticker", "quote_type"), on="ticker", how="left"
    ).with_columns(
        record=polars.struct(columns).struct.json_encode(),
        reason=polars.coalesce(
            *(
                polars.when(failing).then(polars.lit(reason))
                for reason, failing in _REASONS
            )
        ),
    )
    valid = judged.filter(polars.col("reason").is_null()).select(columns)
    rejected = judged.filter(polars.col("reason").is_not_null()).select(
        "day", "reason", "record", "ticker"
    )
    return valid, rejected
