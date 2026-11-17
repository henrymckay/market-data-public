"""Read the universe of instruments from the package's CSV."""

from importlib import resources

import polars

from market_data.code import port


def read_universe() -> polars.DataFrame:
    """Return the universe, one row per instrument, in the port's schema."""
    text = resources.files("market_data").joinpath("data/transform/universe.csv")
    return polars.read_csv(text.read_bytes(), schema_overrides=port.UNIVERSE).select(
        port.UNIVERSE.names()
    )
