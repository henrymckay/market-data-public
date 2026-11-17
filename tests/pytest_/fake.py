"""In-memory doubles of the core's ports."""

import dataclasses

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
