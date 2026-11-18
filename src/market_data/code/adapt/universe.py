"""Read and write the universe of instruments in the package's CSV."""

import pathlib
from importlib import resources

import polars

from market_data.code import port

_COLUMNS = (
    "ticker",
    "name",
    "asset_class",
    "sector",
    "quote_type",
    "active",
    "featured",
    "source",
)


def read_universe() -> polars.DataFrame:
    """Return the universe, one row per instrument, in the port's schema."""
    text = resources.files("market_data").joinpath("data/transform/universe.csv")
    return polars.read_csv(text.read_bytes(), schema_overrides=port.UNIVERSE).select(
        port.UNIVERSE.names()
    )


def write_universe(universe: polars.DataFrame) -> None:
    """Replace the package's CSV with the universe, atomically.

    :param universe: The universe, in the port's schema.
    """
    path = pathlib.Path(
        str(resources.files("market_data").joinpath("data/transform/universe.csv"))
    )
    staged = path.with_suffix(".csv.tmp")
    universe.select(_COLUMNS).write_csv(staged)
    staged.replace(path)
