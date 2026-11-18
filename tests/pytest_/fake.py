"""In-memory doubles of the core's ports."""

import collections.abc
import dataclasses
import datetime

import polars

from market_data.code import port, transform


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
    tickers: polars.DataFrame = dataclasses.field(
        default_factory=lambda: polars.DataFrame(schema=port.UNIVERSE)
    )

    def append_run(self, run: transform.Run) -> None:
        """Keep the manifest row."""
        self.runs.append(run)

    def read_bars(self) -> polars.DataFrame:
        """Return the bars."""
        return self.bars

    def read_rejected_counts(self) -> polars.DataFrame:
        """Return no rejected rows."""
        return polars.DataFrame(
            schema={"ticker": polars.String, "rejected": polars.Int64}
        )

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
