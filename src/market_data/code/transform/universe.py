"""Rules over the universe of instruments."""

import polars


def active_tickers(universe: polars.DataFrame) -> list[str]:
    """Return the tickers of the active instruments, in the universe's order."""
    return universe.filter(polars.col("active")).get_column("ticker").to_list()
