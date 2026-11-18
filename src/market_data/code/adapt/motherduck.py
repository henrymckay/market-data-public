# pyright: reportUnknownArgumentType=false
"""The store: MotherDuck, or a local DuckDB file, over one connection."""

import collections.abc
import dataclasses
import datetime
import functools
import logging
import re
import time
import typing
from importlib import resources

import duckdb
import polars

from market_data.code import error, port, transform

_LOGGER = logging.getLogger(__name__)

_DATABASE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

_INSERT_BARS = """
insert into bars (
    adj_close, close, day, dividend, fetched, high, low, open, split, ticker, volume
)
select
    adj_close, close, day, dividend, fetched, high, low, open, split, ticker, volume
from incoming_bars
"""

_INSERT_REJECTED = """
insert into rejected (day, fetched, reason, record, ticker)
select day, fetched, reason, record, ticker from incoming_rejected
"""

_INSERT_RUN = """
insert into runs (
    day, ended, failed_items, last_day, outcome, rejected, requests, rows,
    source, started
)
values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_SELECT_BARS = """
select adj_close, close, day, high, low, ticker, volume from bars
"""

_SELECT_PERIOD_BARS = """
select adj_close, close, day, high, last_day, low, open, ticker, timeframe, volume
from period_bars
"""

_SELECT_SIGNALS = """
select
    aligned, atr, close, day, direction, event, grade, held_to_date, id, known,
    level, margin_atr, return_to_date, rules, score, stop, swing_atr, ticker,
    timeframe, trend_swings, volume_ratio
from signals
where known >= ?
"""

_SELECT_CHART_BARS = """
select close, day, high, low, open
from (select * from bars where ticker = ? order by day desc limit ?)
order by day
"""

_SELECT_CHART_PERIODS = """
select close, day, high, low, open
from (
    select * from period_bars where ticker = ? and timeframe = ?
    order by day desc limit ?
)
order by day
"""

_SELECT_MISSING = """
select ticker
from tickers
where active and ticker not in (select distinct ticker from bars)
order by ticker
"""

_INSERT_TICKERS = """
insert into tickers (
    active, asset_class, featured, name, quote_type, sector, source, ticker
)
select
    active, asset_class, featured, name, quote_type, sector, source, ticker
from incoming_tickers
"""

_SELECT_LAST_DAYS = "select max(day) as day, ticker from bars group by ticker"

_SELECT_OVERLAP = """
select adj_close, close, day, dividend, split, ticker
from bars
where list_contains(?, ticker) and day >= ?
"""

_DELETE_SINCE = """
delete from {table}
using incoming_since as plan
where {table}.ticker = plan.ticker
    and (plan.since is null or {table}.day is null or {table}.day >= plan.since)
"""


@dataclasses.dataclass(slots=True)
class Meter:
    """The seconds a run has spent inside store calls, connecting included."""

    seconds: float = 0.0


def _timed[**P, T](
    work: collections.abc.Callable[typing.Concatenate[Store, P], T],
) -> collections.abc.Callable[typing.Concatenate[Store, P], T]:
    """Add the seconds a store method takes to its store's meter."""

    @functools.wraps(work)
    def run(store: Store, *args: P.args, **kwargs: P.kwargs) -> T:
        opened = time.monotonic()
        try:
            return work(store, *args, **kwargs)
        finally:
            store.meter.seconds += time.monotonic() - opened

    return run


@dataclasses.dataclass(frozen=True, slots=True)
class Store:
    """The store's sink, over a connection with the schema applied."""

    connection: duckdb.DuckDBPyConnection
    meter: Meter = dataclasses.field(default_factory=Meter)

    @_timed
    def append_run(self, run: transform.Run) -> None:
        """Append one manifest row."""
        self.connection.execute(
            _INSERT_RUN,
            [
                run.day,
                run.ended,
                run.failed_items,
                run.last_day,
                str(run.outcome),
                run.rejected,
                run.requests,
                run.rows,
                run.source,
                run.started,
            ],
        )

    @_timed
    def read_bars(self) -> polars.DataFrame:
        """Return every stored bar the metrics read."""
        return self.connection.execute(_SELECT_BARS).pl()

    @_timed
    def read_period_bars(self) -> polars.DataFrame:
        """Return every weekly and monthly bar, from the `period_bars` view."""
        return self.connection.execute(_SELECT_PERIOD_BARS).pl()

    @_timed
    def read_structure(self) -> polars.DataFrame:
        """Return each instrument's structure on each timeframe."""
        return self.connection.execute(
            "select state, ticker, timeframe from structure"
        ).pl()

    @_timed
    def read_metrics(self) -> polars.DataFrame:
        """Return every stored metric, long."""
        return self.connection.execute(
            "select day, metric, ticker, value from metrics"
        ).pl()

    @_timed
    def read_signals(self, since: datetime.date) -> polars.DataFrame:
        """Return the stored signals known on or after `since`, every grade."""
        return self.connection.execute(_SELECT_SIGNALS, [since]).pl()

    @_timed
    def read_signal_stats(self) -> polars.DataFrame:
        """Return every `signal_stats` row."""
        return self.connection.execute("select * from signal_stats").pl()

    @_timed
    def read_sent(self) -> polars.DataFrame:
        """Return `id` of every signal a sent message named."""
        return self.connection.execute(
            "select distinct id from alerts where kind <> 'health'"
        ).pl()

    @_timed
    def read_alert_state(self) -> str | None:
        """Return the recorded health state, or none before any."""
        row = self.connection.execute(
            "select state from alert_state where key = 'health'"
        ).fetchone()
        return None if row is None else row[0]

    @_timed
    def read_chart_bars(
        self, ticker: str, timeframe: str, limit: int
    ) -> polars.DataFrame:
        """Return the last `limit` bars of a timeframe, oldest first."""
        return self.connection.execute(
            _SELECT_CHART_BARS if timeframe == "d" else _SELECT_CHART_PERIODS,
            [ticker, limit] if timeframe == "d" else [ticker, timeframe, limit],
        ).pl()

    @_timed
    def read_chart_pivots(self, ticker: str, timeframe: str) -> polars.DataFrame:
        """Return the pivots of a timeframe: `day`, `kind`, `label` and `price`."""
        return self.connection.execute(
            "select day, kind, label, price from pivots "
            "where ticker = ? and timeframe = ? order by day",
            [ticker, timeframe],
        ).pl()

    @_timed
    def append_alerts(self, rows: polars.DataFrame) -> None:
        """Append `alerts` rows, one per signal a sent message named."""
        self.connection.register("incoming_alerts", rows.to_arrow())
        self.connection.execute(
            "insert into alerts (id, kind, message, sent, title) "
            "select id, kind, message, sent, title from incoming_alerts"
        )

    @_timed
    def replace_alert_state(
        self, *, changed: datetime.datetime, detail: str, state: str
    ) -> None:
        """Replace the one `alert_state` row."""
        self.connection.execute("begin transaction")
        self.connection.execute("delete from alert_state")
        self.connection.execute(
            "insert into alert_state (changed, detail, key, state) "
            "values (?, ?, 'health', ?)",
            [changed, detail, state],
        )
        self.connection.execute("commit")

    @_timed
    def read_rejected_counts(self) -> polars.DataFrame:
        """Return `ticker` and `rejected`, the quarantined rows per instrument."""
        return self.connection.execute(
            "select ticker, count(*)::bigint as rejected from rejected group by ticker"
        ).pl()

    @_timed
    def read_tickers(self) -> polars.DataFrame:
        """Return the stored universe."""
        return self.connection.execute(
            "select active, asset_class, featured, name, quote_type, sector, source, "
            "ticker from tickers"
        ).pl()

    @_timed
    def read_last_days(self) -> polars.DataFrame:
        """Return each stored instrument's newest day, as `port.LAST_DAYS`."""
        return self.connection.execute(_SELECT_LAST_DAYS).pl()

    @_timed
    def read_overlap(
        self, tickers: collections.abc.Sequence[str], start: datetime.date
    ) -> polars.DataFrame:
        """Return the tickers' stored bars on or after `start`, as `port.OVERLAP`."""
        return self.connection.execute(_SELECT_OVERLAP, [list(tickers), start]).pl()

    @_timed
    def read_missing(self) -> tuple[str, ...]:
        """Return the active instruments that have no bars, sorted."""
        rows = self.connection.execute(_SELECT_MISSING).fetchall()
        return tuple(row[0] for row in rows)

    @_timed
    def read_runs(self) -> polars.DataFrame:
        """Return every manifest row, its times in UTC whatever the session's zone."""
        return (
            self.connection.execute("select * from runs")
            .pl()
            .with_columns(polars.col("ended", "started").dt.convert_time_zone("UTC"))
        )

    def _replace_tables(self, tables: dict[str, polars.DataFrame]) -> None:
        """Replace each table's rows with the frame's, as one transaction.

        The frame's columns name the columns written, so a type the table
        refuses fails the transaction.

        :raises StoreError: If the transaction fails; it is rolled back.
        """
        for name, frame in tables.items():
            self.connection.register(f"incoming_{name}", frame.to_arrow())
        self.connection.execute("begin transaction")
        try:
            for name, frame in tables.items():
                columns = ", ".join(frame.columns)
                self.connection.execute(f"delete from {name}")
                self.connection.execute(
                    f"insert into {name} ({columns}) "
                    f"select {columns} from incoming_{name}"
                )
            self.connection.execute("commit")
        except duckdb.Error as failure:
            self.connection.execute("rollback")
            raise error.StoreError("The load failed and was rolled back") from failure

    @_timed
    def replace_metrics(
        self, metrics: polars.DataFrame, overview: polars.DataFrame
    ) -> None:
        """Replace the whole `metrics` and `overview` tables, as one unit.

        :param metrics: The new rows, one per instrument and metric.
        :param overview: The new rows, one per instrument.
        :raises StoreError: If the transaction fails; it is rolled back.
        """
        self._replace_tables({"metrics": metrics, "overview": overview})

    @_timed
    def replace_signals(self, computed: transform.Computed) -> None:
        """Replace the five signal tables, as one unit.

        :param computed: The new rows of every table.
        :raises StoreError: If the transaction fails; it is rolled back.
        """
        self._replace_tables(
            {
                "outcomes": computed.outcomes,
                "pivots": computed.pivots,
                "signal_stats": computed.signal_stats,
                "signals": computed.signals,
                "structure": computed.structure,
            }
        )

    @_timed
    def replace(self, load: port.Load) -> None:
        """Replace the answered instruments' bars and rejected rows, and the tickers.

        Each instrument's rows from its `since` day on are replaced, or all of
        them where `since` is null.

        :param load: What the run keeps.
        :raises StoreError: If the transaction fails; it is rolled back.
        """
        stamped = polars.lit(load.fetched).alias("fetched")
        self.connection.register(
            "incoming_bars", load.bars.with_columns(stamped).to_arrow()
        )
        self.connection.register(
            "incoming_rejected", load.rejected.with_columns(stamped).to_arrow()
        )
        self.connection.register("incoming_tickers", load.universe.to_arrow())
        self.connection.register("incoming_since", load.since.to_arrow())
        self.connection.execute("begin transaction")
        try:
            for table in ("bars", "rejected"):
                self.connection.execute(_DELETE_SINCE.format(table=table))
            self.connection.execute(_INSERT_BARS)
            self.connection.execute(_INSERT_REJECTED)
            self.connection.execute("delete from tickers")
            self.connection.execute(_INSERT_TICKERS)
            self.connection.execute("commit")
        except duckdb.Error as failure:
            self.connection.execute("rollback")
            raise error.StoreError("The load failed and was rolled back") from failure


def _migrate(connection: duckdb.DuckDBPyConnection) -> None:
    """Apply each numbered migration newer than the schema version, in order."""
    connection.execute("create table if not exists schema_version (version integer)")
    row = connection.execute("select max(version) from schema_version").fetchone()
    current = row[0] if row is not None and row[0] is not None else 0
    folder = resources.files("market_data").joinpath("data/adapt/migrations")
    for file in sorted(folder.iterdir(), key=lambda entry: entry.name):
        version = int(file.name.split("_")[0])
        if version > current:
            connection.execute("begin transaction")
            connection.execute(file.read_text())
            connection.execute("insert into schema_version values (?)", [version])
            connection.execute("commit")
            _LOGGER.info("Applied migration %s", file.name)


def connect(database: str) -> duckdb.DuckDBPyConnection:
    """Open the store and apply its migrations.

    :param database: `md:<name>` for MotherDuck, else a DuckDB file path.
    :returns: The open connection.
    :raises ConfigurationError: If MotherDuck refuses the token or the name is bad.
    :raises StoreError: If MotherDuck cannot be reached.
    """
    if not database.startswith("md:"):
        connection = duckdb.connect(database)
        _migrate(connection)
        return connection
    name = database.removeprefix("md:")
    if not _DATABASE_NAME.fullmatch(name):
        raise error.ConfigurationError(f"{name!r} is not a database name")
    try:
        connection = duckdb.connect("md:")
        connection.execute(f'create database if not exists "{name}"')
        connection.execute(f'use "{name}"')
    except duckdb.Error as failure:
        if "authenticated" in str(failure):
            raise error.ConfigurationError("MotherDuck refused the token") from None
        raise error.StoreError("Could not connect to MotherDuck") from None
    _migrate(connection)
    return connection
