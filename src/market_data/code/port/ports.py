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

    def read_rejected_counts(self) -> polars.DataFrame:
        """Return `ticker` and `rejected`, the quarantined rows per instrument."""
        ...

    def read_structure(self) -> polars.DataFrame:
        """Return `state`, `ticker` and `timeframe` of the stored structure."""
        ...

    def read_tickers(self) -> polars.DataFrame:
        """Return the stored universe."""
        ...

    def replace_metrics(
        self, metrics: polars.DataFrame, overview: polars.DataFrame
    ) -> None:
        """Replace the whole `metrics` and `overview` tables, as one unit."""
        ...


class SignalsStore(typing.Protocol):
    """Where the signals stage reads period bars and the universe and writes tables."""

    def append_run(self, run: transform.Run) -> None:
        """Append one manifest row."""
        ...

    def read_period_bars(self) -> polars.DataFrame:
        """Return every weekly and monthly bar of the `period_bars` view."""
        ...

    def read_tickers(self) -> polars.DataFrame:
        """Return the stored universe."""
        ...

    def replace_signals(self, computed: transform.Computed) -> None:
        """Replace the pivots, signals, outcomes, base rates and structure as one unit.

        :raises StoreError: If the transaction fails; nothing is replaced.
        """
        ...


type Send = collections.abc.Callable[[transform.Message, bytes | None], str]
type Render = collections.abc.Callable[
    [transform.ChartRequest, polars.DataFrame, polars.DataFrame], bytes
]


class AlertsStore(typing.Protocol):
    """Where the notify stage reads what is due and records what was sent."""

    def append_alerts(self, rows: polars.DataFrame) -> None:
        """Append `alerts` rows, one per signal a sent message named."""
        ...

    def read_alert_state(self) -> str | None:
        """Return the recorded health state, or none before any."""
        ...

    def read_chart_bars(
        self, ticker: str, timeframe: str, limit: int
    ) -> polars.DataFrame:
        """Return the last `limit` bars of a timeframe, oldest first.

        The columns are `close`, `day`, `high`, `low` and `open`.
        """
        ...

    def read_chart_pivots(self, ticker: str, timeframe: str) -> polars.DataFrame:
        """Return the pivots of a timeframe: `day`, `kind`, `label` and `price`."""
        ...

    def read_missing(self) -> tuple[str, ...]:
        """Return the active instruments that have no bars, sorted."""
        ...

    def read_runs(self) -> polars.DataFrame:
        """Return every manifest row."""
        ...

    def read_sent(self) -> polars.DataFrame:
        """Return `id` of every signal a sent message named."""
        ...

    def read_signal_stats(self) -> polars.DataFrame:
        """Return every `signal_stats` row."""
        ...

    def read_signals(self, since: datetime.date) -> polars.DataFrame:
        """Return the stored signals known on or after `since`, every grade."""
        ...

    def read_structure(self) -> polars.DataFrame:
        """Return `state`, `ticker` and `timeframe` of the stored structure."""
        ...

    def read_tickers(self) -> polars.DataFrame:
        """Return the stored universe."""
        ...

    def replace_alert_state(
        self, *, changed: datetime.datetime, detail: str, state: str
    ) -> None:
        """Replace the one `alert_state` row."""
        ...
