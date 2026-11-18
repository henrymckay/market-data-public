"""In-memory doubles of the core's ports."""

import collections.abc
import dataclasses
import datetime

import polars

from market_data.code import error, port, transform


@dataclasses.dataclass(slots=True)
class Sink:
    """A sink that keeps what it was given."""

    last_days: polars.DataFrame = dataclasses.field(
        default_factory=lambda: polars.DataFrame(schema=port.LAST_DAYS)
    )
    loads: list[port.Load] = dataclasses.field(default_factory=list[port.Load])
    overlap: polars.DataFrame = dataclasses.field(
        default_factory=lambda: polars.DataFrame(schema=port.OVERLAP)
    )
    runs: list[transform.Run] = dataclasses.field(default_factory=list[transform.Run])

    def append_run(self, run: transform.Run) -> None:
        """Keep the manifest row."""
        self.runs.append(run)

    def read_last_days(self) -> polars.DataFrame:
        """Return the stored days it was given."""
        return self.last_days

    def read_overlap(
        self, tickers: collections.abc.Sequence[str], start: datetime.date
    ) -> polars.DataFrame:
        """Return the stored bars it was given for the tickers from `start`."""
        return self.overlap.filter(
            polars.col("ticker").is_in(tickers), polars.col("day").ge(start)
        )

    def replace(self, load: port.Load) -> None:
        """Keep the load."""
        self.loads.append(load)


def fetching(
    bars: polars.DataFrame, *failed: port.Failure, requests: int = 1
) -> port.Fetch:
    """Return a fetch that answers with the given bars and failures."""
    return lambda _tickers, _period: port.Fetched(
        bars=bars, failed=failed, requests=requests
    )


@dataclasses.dataclass(slots=True)
class Source:
    """A source holding whole histories, which answers a month or everything."""

    histories: polars.DataFrame
    calls: list[tuple[tuple[str, ...], str]] = dataclasses.field(
        default_factory=list[tuple[tuple[str, ...], str]]
    )

    def __call__(
        self, tickers: collections.abc.Sequence[str], period: port.Period
    ) -> port.Fetched:
        """Return the tickers' bars for the period, recording the request."""
        self.calls.append((tuple(tickers), period))
        wanted = self.histories.filter(polars.col("ticker").is_in(tickers))
        newest: datetime.date | None = wanted.select(polars.col("day").max()).item()
        kept = (
            wanted
            if period == "max" or newest is None
            else wanted.filter(
                polars.col("day").gt(newest - datetime.timedelta(days=30))
            )
        )
        return port.Fetched(bars=kept, failed=(), requests=len(self.calls))


@dataclasses.dataclass(slots=True)
class Ledger:
    """A metrics store that serves the bars it was given and keeps the results."""

    bars: polars.DataFrame
    metrics: list[polars.DataFrame] = dataclasses.field(
        default_factory=list[polars.DataFrame]
    )
    overviews: list[polars.DataFrame] = dataclasses.field(
        default_factory=list[polars.DataFrame]
    )
    runs: list[transform.Run] = dataclasses.field(default_factory=list[transform.Run])
    structure: polars.DataFrame = dataclasses.field(
        default_factory=lambda: polars.DataFrame(
            schema={
                "state": polars.String,
                "ticker": polars.String,
                "timeframe": polars.String,
            }
        )
    )
    tickers: polars.DataFrame = dataclasses.field(
        default_factory=lambda: polars.DataFrame(schema=port.UNIVERSE)
    )

    def append_run(self, run: transform.Run) -> None:
        """Keep the manifest row."""
        self.runs.append(run)

    def read_rejected_counts(self) -> polars.DataFrame:
        """Return no rejected rows."""
        return polars.DataFrame(
            schema={"ticker": polars.String, "rejected": polars.Int64}
        )

    def read_structure(self) -> polars.DataFrame:
        """Return the structure."""
        return self.structure

    def read_tickers(self) -> polars.DataFrame:
        """Return the universe."""
        return self.tickers

    def replace_metrics(
        self, metrics: polars.DataFrame, overview: polars.DataFrame
    ) -> None:
        """Keep the metrics and the overview."""
        self.metrics.append(metrics)
        self.overviews.append(overview)


def whole(tickers: collections.abc.Iterable[str]) -> polars.DataFrame:
    """Return a replacement plan that swaps each ticker's whole history."""
    return polars.DataFrame(
        {"since": [None for _ in tickers], "ticker": list(tickers)},
        schema=port.SINCE,
    )


@dataclasses.dataclass(slots=True)
class SignalsLedger:
    """A signals store that serves the period bars and universe it was given."""

    periods: polars.DataFrame
    tickers: polars.DataFrame
    failing: bool = False
    replaced: list[transform.Computed] = dataclasses.field(
        default_factory=list[transform.Computed]
    )
    runs: list[transform.Run] = dataclasses.field(default_factory=list[transform.Run])

    def append_run(self, run: transform.Run) -> None:
        """Keep the manifest row."""
        self.runs.append(run)

    def read_period_bars(self) -> polars.DataFrame:
        """Return the period bars."""
        return self.periods

    def read_tickers(self) -> polars.DataFrame:
        """Return the universe."""
        return self.tickers

    def replace_signals(self, computed: transform.Computed) -> None:
        """Keep the tables, or fail as a store whose transaction rolled back."""
        if self.failing:
            raise error.StoreError("The load failed and was rolled back")
        self.replaced.append(computed)


@dataclasses.dataclass(slots=True)
class AlertsLedger:
    """An alerts store that serves the tables it was given and keeps what is written."""

    runs: polars.DataFrame
    signals: polars.DataFrame
    stats: polars.DataFrame
    structure: polars.DataFrame
    tickers: polars.DataFrame
    flat: bool = False
    missing: tuple[str, ...] = ()
    sent: polars.DataFrame = dataclasses.field(
        default_factory=lambda: polars.DataFrame(schema={"id": polars.String})
    )
    state: str | None = None
    alerts: list[polars.DataFrame] = dataclasses.field(
        default_factory=list[polars.DataFrame]
    )
    states: list[str] = dataclasses.field(default_factory=list[str])

    def append_alerts(self, rows: polars.DataFrame) -> None:
        """Keep the rows."""
        self.alerts.append(rows)

    def read_alert_state(self) -> str | None:
        """Return the state it was given."""
        return self.state

    def read_chart_bars(
        self, ticker: str, timeframe: str, limit: int
    ) -> polars.DataFrame:
        """Return 30 weekly bars ending on the signal day, flat when told to."""
        days = [
            datetime.date(2026, 11, 9) - datetime.timedelta(days=7 * n)
            for n in reversed(range(30))
        ]
        spread = 0.0 if self.flat else 1.0
        return polars.DataFrame(
            {
                "close": [10.0] * 30,
                "day": days,
                "high": [10.0 + spread] * 30,
                "low": [10.0 - spread] * 30,
                "open": [10.0] * 30,
            }
        )

    def read_chart_pivots(self, ticker: str, timeframe: str) -> polars.DataFrame:
        """Return no pivots."""
        return polars.DataFrame(
            schema={
                "day": polars.Date,
                "kind": polars.String,
                "label": polars.String,
                "price": polars.Float64,
            }
        )

    def read_missing(self) -> tuple[str, ...]:
        """Return the instruments it was told lack bars."""
        return self.missing

    def read_runs(self) -> polars.DataFrame:
        """Return the runs."""
        return self.runs

    def read_sent(self) -> polars.DataFrame:
        """Return the ids sent so far, including this run's."""
        appended = [rows.select("id") for rows in self.alerts]
        return polars.concat([self.sent, *appended])

    def read_signal_stats(self) -> polars.DataFrame:
        """Return the base rates."""
        return self.stats

    def read_signals(self, since: datetime.date) -> polars.DataFrame:
        """Return the signals known since the day."""
        return self.signals.filter(polars.col("known").ge(since))

    def read_structure(self) -> polars.DataFrame:
        """Return the structure."""
        return self.structure

    def read_tickers(self) -> polars.DataFrame:
        """Return the universe."""
        return self.tickers

    def replace_alert_state(
        self, *, changed: datetime.datetime, detail: str, state: str
    ) -> None:
        """Keep the state."""
        self.states.append(state)
        self.state = state
