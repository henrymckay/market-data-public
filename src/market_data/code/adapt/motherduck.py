# pyright: reportUnknownArgumentType=false
"""The store: MotherDuck, or a local DuckDB file, over one connection."""

import dataclasses
import logging
import re
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

_INSERT_METRICS = """
insert into metrics (day, metric, ticker, value)
select day, metric, ticker, value from incoming_metrics
"""

_INSERT_OVERVIEW = "insert into overview by name select * from incoming_overview"

_SELECT_BARS = """
select adj_close, close, day, high, low, ticker, volume from bars
"""

_SELECT_SITE_BARS = """
select
    adj_close, close, day, dividend, high, low, open, split, ticker, volume
from bars
"""

_SELECT_MISSING = """
select ticker
from tickers
where active and ticker not in (select distinct ticker from bars)
order by ticker
"""

_INSERT_TICKERS = """
insert into tickers (active, asset_class, name, quote_type, sector, ticker)
select active, asset_class, name, quote_type, sector, ticker from incoming_tickers
"""


@dataclasses.dataclass(frozen=True, slots=True)
class Store:
    """The store's sink, over a connection with the schema applied."""

    connection: duckdb.DuckDBPyConnection

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

    def read_bars(self) -> polars.DataFrame:
        """Return every stored bar the metrics read."""
        return self.connection.execute(_SELECT_BARS).pl()

    def read_metrics(self) -> polars.DataFrame:
        """Return every stored metric, long."""
        return self.connection.execute(
            "select day, metric, ticker, value from metrics"
        ).pl()

    def read_rejected_counts(self) -> polars.DataFrame:
        """Return `ticker` and `rejected`, the quarantined rows per instrument."""
        return self.connection.execute(
            "select ticker, count(*)::bigint as rejected from rejected group by ticker"
        ).pl()

    def read_site_bars(self) -> polars.DataFrame:
        """Return every stored bar as the site's bars files hold it."""
        return self.connection.execute(_SELECT_SITE_BARS).pl()

    def read_tickers(self) -> polars.DataFrame:
        """Return the stored universe."""
        return self.connection.execute(
            "select active, asset_class, name, quote_type, sector, ticker from tickers"
        ).pl()

    def read_missing(self) -> tuple[str, ...]:
        """Return the active instruments that have no bars, sorted."""
        rows = self.connection.execute(_SELECT_MISSING).fetchall()
        return tuple(row[0] for row in rows)

    def read_runs(self) -> polars.DataFrame:
        """Return every manifest row, its times in UTC whatever the session's zone."""
        return (
            self.connection.execute("select * from runs")
            .pl()
            .with_columns(polars.col("ended", "started").dt.convert_time_zone("UTC"))
        )

    def replace_metrics(
        self, metrics: polars.DataFrame, overview: polars.DataFrame
    ) -> None:
        """Replace the whole `metrics` and `overview` tables, as one unit.

        :param metrics: The new rows, one per instrument and metric.
        :param overview: The new rows, one per instrument.
        :raises StoreError: If the transaction fails; it is rolled back.
        """
        self.connection.register("incoming_metrics", metrics.to_arrow())
        self.connection.register("incoming_overview", overview.to_arrow())
        self.connection.execute("begin transaction")
        try:
            self.connection.execute("delete from metrics")
            self.connection.execute(_INSERT_METRICS)
            self.connection.execute("delete from overview")
            self.connection.execute(_INSERT_OVERVIEW)
            self.connection.execute("commit")
        except duckdb.Error as failure:
            self.connection.execute("rollback")
            raise error.StoreError("The load failed and was rolled back") from failure

    def replace(self, load: port.Load) -> None:
        """Replace the answered instruments' bars and rejected rows, and the tickers.

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
        answered = list(load.answered)
        self.connection.execute("begin transaction")
        try:
            for table in ("bars", "rejected"):
                self.connection.execute(
                    f"delete from {table} where list_contains(?, ticker)", [answered]
                )
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
