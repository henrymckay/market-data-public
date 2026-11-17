"""Schemas, records and interfaces shared by the core and its adapters."""

import collections.abc
import dataclasses
import datetime
import typing

import polars

from market_data.code import transform

BARS = polars.Schema(
    {
        "adj_close": polars.Float64,
        "close": polars.Float64,
        "day": polars.Date,
        "dividend": polars.Float64,
        "high": polars.Float64,
        "low": polars.Float64,
        "open": polars.Float64,
        "split": polars.Float64,
        "ticker": polars.String,
        "volume": polars.Int64,
    }
)

REJECTED = polars.Schema(
    {
        "day": polars.Date,
        "reason": polars.String,
        "record": polars.String,
        "ticker": polars.String,
    }
)

UNIVERSE = polars.Schema(
    {
        "active": polars.Boolean,
        "asset_class": polars.String,
        "name": polars.String,
        "quote_type": polars.String,
        "sector": polars.String,
        "ticker": polars.String,
    }
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Failure:
    """One instrument that answered nothing usable, and why."""

    reason: str
    ticker: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Fetched:
    """What Yahoo sent for a run, as it arrived."""

    bars: polars.DataFrame
    failed: tuple[Failure, ...]
    requests: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Load:
    """What one run replaces in the store, for the instruments that answered."""

    answered: tuple[str, ...]
    bars: polars.DataFrame
    fetched: datetime.datetime
    rejected: polars.DataFrame
    universe: polars.DataFrame


type Fetch = collections.abc.Callable[[collections.abc.Sequence[str]], Fetched]


class Sink(typing.Protocol):
    """Where a run's results are written."""

    def append_run(self, run: transform.Run) -> None:
        """Append one manifest row."""
        ...

    def replace(self, load: Load) -> None:
        """Replace the answered instruments' rows and the universe, as one unit."""
        ...


class MetricsStore(typing.Protocol):
    """Where the compute stage reads bars and writes metrics and its run."""

    def append_run(self, run: transform.Run) -> None:
        """Append one manifest row."""
        ...

    def read_bars(self) -> polars.DataFrame:
        """Return every stored bar, with `BARS`' columns."""
        ...

    def replace_metrics(self, metrics: polars.DataFrame) -> None:
        """Replace the whole `metrics` table."""
        ...
