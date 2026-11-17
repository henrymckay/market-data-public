"""In-memory doubles of the core's ports."""

import dataclasses
import datetime

import polars

from market_data.code import port, transform


@dataclasses.dataclass(slots=True)
class Sink:
    """A sink that keeps what it was given."""

    loads: list[port.Load] = dataclasses.field(default_factory=list[port.Load])
    runs: list[transform.Run] = dataclasses.field(default_factory=list[transform.Run])

    def append_run(self, run: transform.Run) -> None:
        """Keep the manifest row."""
        self.runs.append(run)

    def replace(self, load: port.Load) -> None:
        """Keep the load."""
        self.loads.append(load)


def fetching(
    bars: polars.DataFrame, *failed: port.Failure, requests: int = 1
) -> port.Fetch:
    """Return a fetch that answers with the given bars and failures."""
    return lambda _tickers: port.Fetched(bars=bars, failed=failed, requests=requests)


@dataclasses.dataclass(slots=True)
class Ledger:
    """A metrics store that serves the bars it was given and keeps the results."""

    bars: polars.DataFrame
    metrics: list[polars.DataFrame] = dataclasses.field(
        default_factory=list[polars.DataFrame]
    )
    runs: list[transform.Run] = dataclasses.field(default_factory=list[transform.Run])

    def append_run(self, run: transform.Run) -> None:
        """Keep the manifest row."""
        self.runs.append(run)

    def read_bars(self) -> polars.DataFrame:
        """Return the bars."""
        return self.bars

    def replace_metrics(self, metrics: polars.DataFrame) -> None:
        """Keep the metrics."""
        self.metrics.append(metrics)


@dataclasses.dataclass(slots=True)
class Source:
    """A site source that serves the frames it was given."""

    bars: polars.DataFrame
    metrics: polars.DataFrame
    rejected: polars.DataFrame
    runs: polars.DataFrame
    tickers: polars.DataFrame

    def read_site_bars(self) -> polars.DataFrame:
        """Return the bars."""
        return self.bars

    def read_metrics(self) -> polars.DataFrame:
        """Return the metrics."""
        return self.metrics

    def read_rejected_counts(self) -> polars.DataFrame:
        """Return the rejected counts."""
        return self.rejected

    def read_runs(self) -> polars.DataFrame:
        """Return the runs."""
        return self.runs

    def read_tickers(self) -> polars.DataFrame:
        """Return the tickers."""
        return self.tickers


def runs_frame(count: int = 2) -> polars.DataFrame:
    """Return `count` yahoo runs a day apart, the last ended 2026-11-17 02:19:41."""
    last = datetime.datetime(2026, 11, 17, 2, 19, 41, tzinfo=datetime.UTC)
    ended = [last - datetime.timedelta(days=count - 1 - i) for i in range(count)]
    return polars.DataFrame(
        {
            "day": [e.date() - datetime.timedelta(days=1) for e in ended],
            "ended": ended,
            "failed_items": [0] * count,
            "last_day": [e.date() - datetime.timedelta(days=1) for e in ended],
            "outcome": ["stored"] * count,
            "rejected": [0] * count,
            "requests": [90] * count,
            "rows": [803114] * count,
            "source": ["yahoo"] * count,
            "started": [e - datetime.timedelta(minutes=2) for e in ended],
        },
        schema={
            "day": polars.Date,
            "ended": polars.Datetime("us", "UTC"),
            "failed_items": polars.Int32,
            "last_day": polars.Date,
            "outcome": polars.String,
            "rejected": polars.Int32,
            "requests": polars.Int32,
            "rows": polars.Int64,
            "source": polars.String,
            "started": polars.Datetime("us", "UTC"),
        },
    )
