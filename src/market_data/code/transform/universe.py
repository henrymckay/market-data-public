"""Rules over the universe of instruments."""

import dataclasses

import polars

from market_data.code import error

_SYMBOL = r"^[A-Z][A-Z0-9.]{0,9}$"
_MEMBER_ROWS = range(495, 511)
_SECTOR_NAMES = {"Information Technology": "Technology"}
_SP500 = "sp500"
_TEXT = r"^[^\x00-\x1f\x7f]{1,100}$"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Changes:
    """The tickers a sync made active and the ones it made inactive."""

    added: tuple[str, ...]
    removed: tuple[str, ...]


def active_tickers(universe: polars.DataFrame) -> list[str]:
    """Return the tickers of the active instruments, in the universe's order."""
    return universe.filter(polars.col("active")).get_column("ticker").to_list()


def _check_members(members: polars.DataFrame) -> None:
    """Raise unless the member list looks like the S&P 500's, symbol by symbol."""
    if members.height not in _MEMBER_ROWS:
        raise error.SourceError(
            f"The S&P 500 list has {members.height} rows, not 495 to 510"
        )
    symbols = members.get_column("symbol")
    if symbols.is_null().any() or not symbols.str.contains(_SYMBOL).all():
        raise error.SourceError("The S&P 500 list holds a symbol of an odd shape")
    if not symbols.is_unique().all():
        raise error.SourceError("The S&P 500 list repeats a symbol")
    if (
        members.select(polars.col("name", "sector"))
        .null_count()
        .sum_horizontal()
        .item()
    ):
        raise error.SourceError("The S&P 500 list lacks a name or a sector")
    if not members.select(polars.col("name", "sector").str.contains(_TEXT).all()).row(
        0
    ) == (True, True):
        raise error.SourceError("The S&P 500 list holds a name or sector of odd shape")


def sync_members(
    universe: polars.DataFrame, members: polars.DataFrame
) -> polars.DataFrame:
    """Bring the S&P 500 rows of the universe in line with the current members.

    A member the universe lacks is added as an active, unfeatured `sp500` stock;
    an `sp500` row no longer a member becomes inactive and comes back active if
    it rejoins; every other row stays as it is.

    :param universe: The universe, in the port's schema.
    :param members: The current members: `symbol`, `name` and `sector`, as published.
    :returns: The universe, sorted by asset class then ticker.
    :raises SourceError: If the member list does not look like the S&P 500's.
    """
    _check_members(members)
    wanted = members.select(
        polars.col("symbol").str.replace_all(".", "-", literal=True).alias("ticker"),
        polars.col("name"),
        polars.col("sector").replace(_SECTOR_NAMES),
    )
    current = universe.join(
        wanted.select("ticker", polars.lit(True).alias("member")),
        on="ticker",
        how="left",
        validate="1:1",
    ).select(
        polars.when(polars.col("source").eq(_SP500))
        .then(polars.col("member").fill_null(False))
        .otherwise(polars.col("active"))
        .alias("active"),
        polars.exclude("active", "member"),
    )
    added = wanted.join(universe.select("ticker"), on="ticker", how="anti").select(
        polars.lit(True).alias("active"),
        polars.lit("stock").alias("asset_class"),
        polars.lit(False).alias("featured"),
        polars.col("name"),
        polars.lit("price").alias("quote_type"),
        polars.col("sector"),
        polars.lit(_SP500).alias("source"),
        polars.col("ticker"),
    )
    return polars.concat(
        [current.select(universe.columns), added.select(universe.columns)]
    ).sort("asset_class", "ticker")


def diff_universe(before: polars.DataFrame, after: polars.DataFrame) -> Changes:
    """Return the tickers that became active and the ones that became inactive."""
    was = set(active_tickers(before))
    now = set(active_tickers(after))
    return Changes(added=tuple(sorted(now - was)), removed=tuple(sorted(was - now)))
