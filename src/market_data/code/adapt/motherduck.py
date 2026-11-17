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
