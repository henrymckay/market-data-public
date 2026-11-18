"""Rules over what each night fetches and which stored rows it replaces."""

import datetime

import polars

_MAX_AGE_DAYS = 25
_TOLERANCE = 1e-6


def plan_fetch(
    tickers: list[str],
    *,
    full: bool,
    last_days: polars.DataFrame,
    today: datetime.date,
) -> polars.DataFrame:
    """Choose each instrument's request: its last month, or its whole history.

    The whole history is asked for when the run is full, when the store holds no
    bar of the instrument, or when its newest stored day is over 25 days old.

    :param tickers: The instruments to fetch.
    :param full: Whether every instrument gets its whole history.
    :param last_days: Each stored instrument's newest day, as `port.LAST_DAYS`.
    :param today: The run's UTC date.
    :returns: `ticker` and `period`, one row per ticker, in the given order.
    """
    oldest = today - datetime.timedelta(days=_MAX_AGE_DAYS)
    return (
        polars.DataFrame({"ticker": tickers}, schema={"ticker": polars.String})
        .join(last_days, on="ticker", how="left", validate="1:1")
        .select(
            "ticker",
            polars.when(
                polars.lit(full)
                | polars.col("day").is_null()
                | polars.col("day").lt(oldest)
            )
            .then(polars.lit("max"))
            .otherwise(polars.lit("1mo"))
            .alias("period"),
        )
    )


def find_disagreements(
    *, fetched: polars.DataFrame, stored: polars.DataFrame
) -> list[str]:
    """Return the instruments whose last month contradicts the store's rows.

    A close or adjusted close differing by more than one part in a million on a
    day both hold, or a dividend or split on a fetched day that the store lacks,
    means history was restated.

    :param fetched: Complete bars fetched for the last month.
    :param stored: The store's bars of the same instruments, as `port.OVERLAP`.
    :returns: The tickers to fetch whole, sorted.
    """

    def moved(name: str) -> polars.Expr:
        before = polars.col(f"{name}_stored")
        return (
            polars.col(name)
            .sub(before)
            .abs()
            .truediv(before.abs())
            .gt(_TOLERANCE)
            .fill_null(False)
        )

    def lacked(name: str) -> polars.Expr:
        return (
            polars.col(name)
            .ne(0)
            .and_(polars.col(name).ne_missing(polars.col(f"{name}_stored")))
        )

    return (
        fetched.join(
            stored.select(
                "ticker",
                "day",
                *(
                    polars.col(name).alias(f"{name}_stored")
                    for name in ("adj_close", "close", "dividend", "split")
                ),
            ),
            on=["ticker", "day"],
            how="left",
            validate="1:1",
        )
        .filter(
            moved("close") | moved("adj_close") | lacked("dividend") | lacked("split")
        )
        .get_column("ticker")
        .unique()
        .sort()
        .to_list()
    )


def build_since(
    answered: list[str], *, recent: polars.DataFrame, whole: list[str]
) -> polars.DataFrame:
    """Return the day from which each answered instrument's stored rows are replaced.

    :param answered: The instruments whose bars arrived and validated.
    :param recent: The complete bars fetched for the last month.
    :param whole: The instruments fetched whole, which replace every stored row.
    :returns: `ticker` and `since`; `since` is null for an instrument fetched whole.
    """
    firsts = recent.group_by("ticker").agg(polars.col("day").min().alias("since"))
    return (
        polars.DataFrame({"ticker": answered}, schema={"ticker": polars.String})
        .join(firsts, on="ticker", how="left", validate="1:1")
        .with_columns(
            polars.when(polars.col("ticker").is_in(whole))
            .then(None)
            .otherwise(polars.col("since"))
            .alias("since")
        )
        .select("ticker", "since")
    )
