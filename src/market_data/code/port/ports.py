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
        "featured": polars.Boolean,
        "name": polars.String,
        "quote_type": polars.String,
        "sector": polars.String,
        "source": polars.String,
        "ticker": polars.String,
    }
)

OVERLAP = polars.Schema(
    {
        "adj_close": polars.Float64,
        "close": polars.Float64,
        "day": polars.Date,
        "dividend": polars.Float64,
        "split": polars.Float64,
        "ticker": polars.String,
    }
)

SINCE = polars.Schema({"since": polars.Date, "ticker": polars.String})

LAST_DAYS = polars.Schema({"day": polars.Date, "ticker": polars.String})

type Period = typing.Literal["1mo", "max"]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Failure:
    """One instrument that answered nothing usable, and why."""

    reason: str
    ticker: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Fetched:
    """What Yahoo sent for a request; `requests` counts the whole run so far."""

    bars: polars.DataFrame
    failed: tuple[Failure, ...]
    requests: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Load:
    """What one run replaces in the store, for the instruments that answered."""

    bars: polars.DataFrame
    fetched: datetime.datetime
    rejected: polars.DataFrame
    since: polars.DataFrame
    universe: polars.DataFrame


type Fetch = collections.abc.Callable[[collections.abc.Sequence[str], Period], Fetched]


class Sink(typing.Protocol):
    """Where a run's results are written, and the stored days it plans from."""

    def append_run(self, run: transform.Run) -> None:
        """Append one manifest row."""
        ...

    def read_last_days(self) -> polars.DataFrame:
        """Return `LAST_DAYS`: each stored instrument's newest day."""
        ...

    def read_overlap(
        self, tickers: collections.abc.Sequence[str], start: datetime.date
    ) -> polars.DataFrame:
        """Return `OVERLAP`: the tickers' stored bars on or after `start`."""
        ...

    def replace(self, load: Load) -> None:
        """Replace the answered instruments' rows from `since` on, and the universe.

        The whole unit is one transaction.
        """
        ...


class MetricsStore(typing.Protocol):
    """Where the compute stage reads bars and writes metrics and its run."""

    def append_run(self, run: transform.Run) -> None:
        """Append one manifest row."""
        ...

    def read_bars(self) -> polars.DataFrame:
        """Return every stored bar, with `BARS`' columns."""
        ...

    def read_rejected_counts(self) -> polars.DataFrame:
        """Return `ticker` and `rejected`, the quarantined rows per instrument."""
        ...

    def read_tickers(self) -> polars.DataFrame:
        """Return the stored universe."""
        ...

    def replace_metrics(
        self, metrics: polars.DataFrame, overview: polars.DataFrame
    ) -> None:
        """Replace the whole `metrics` and `overview` tables, as one unit."""
        ...
