# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""The typer app and its commands; the composition root."""

import collections.abc
import contextlib
import datetime
import enum
import functools
import logging
import pathlib
import time
import typing

import duckdb
import typer

from market_data.code import error, operate, transform
from market_data.code.adapt import motherduck, site, universe, yahoo
from market_data.code.drive import config, logging_, output

_LOGGER = logging.getLogger(__name__)

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)


class Level(enum.StrEnum):
    """Log levels, by name."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"


def _exit_on_error[**P, T](
    work: collections.abc.Callable[P, T],
) -> collections.abc.Callable[P, T]:
    """Turn the app's errors into a message on standard error and an exit code."""

    @functools.wraps(work)
    def run(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return work(*args, **kwargs)
        except error.ConfigurationError as failure:
            typer.echo(str(failure), err=True)
            raise typer.Exit(code=2) from None
        except error.StoreError as failure:
            typer.echo(str(failure), err=True)
            raise typer.Exit(code=1) from None

    return run


def _log_level() -> typer.models.OptionInfo:
    """Return the option choosing the lowest log level shown."""
    return typer.Option(help="Lowest log level shown, on standard error.")


@contextlib.contextmanager
def _connected(
    settings: config.Settings,
) -> collections.abc.Generator[duckdb.DuckDBPyConnection]:
    """Hold the store's connection for the block and log the seconds it was open."""
    opened = time.monotonic()
    connection = motherduck.connect(settings.database)
    try:
        yield connection
    finally:
        connection.close()
        _LOGGER.info("Connected to the store for %.0f s", time.monotonic() - opened)


def _start(log_level: Level) -> config.Settings:
    """Configure logging and read the settings, once per command."""
    logging_.configure(
        level=logging.getLevelNamesMapping()[log_level.upper()],
        secret=config.read_token_for_redaction(),
    )
    return config.read_settings()


def _fetch(requested: list[str] | None, *, store: motherduck.Store) -> transform.Run:
    """Fetch the requested instruments, or every active one, and store them."""
    everyone = universe.read_universe()
    tickers = requested or transform.active_tickers(everyone)
    unknown = sorted(set(tickers) - set(everyone.get_column("ticker").to_list()))
    if unknown:
        raise error.ConfigurationError(f"Not in the universe: {', '.join(unknown)}")
    constants = yahoo.read_constants()
    requests = yahoo.Requests()
    history = yahoo.build_history(constants, requests=requests)
    return operate.fetch_bars(
        tickers,
        fetch=lambda wanted: yahoo.fetch_bars(
            wanted, history=history, requests=requests
        ),
        now=_now,
        sink=store,
        tolerance=constants.tolerance,
        universe=everyone,
    )


def _compute(*, store: motherduck.Store) -> transform.Run:
    """Recompute the metrics from the stored bars."""
    return operate.compute_metrics(
        now=_now,
        store=store,
        tolerance=yahoo.read_constants().tolerance,
        universe=universe.read_universe(),
    )


def _now() -> datetime.datetime:
    """Return the current time, aware, in UTC."""
    return datetime.datetime.now(datetime.UTC)


def _exit_unless_stored(*runs: transform.Run) -> None:
    """Show the runs' manifest rows and exit 1 if any did not store."""
    output.display_manifest(*runs)
    if any(run.outcome is not transform.Outcome.STORED for run in runs):
        raise typer.Exit(code=1)


@app.command()
@_exit_on_error
def fetch(
    tickers: typing.Annotated[
        list[str] | None,
        typer.Argument(help="Yahoo symbols, e.g. AAPL.", show_default="every active"),
    ] = None,
    log_level: typing.Annotated[Level, _log_level()] = Level.WARNING,
) -> None:
    """Fetch the history of the given instruments and store it."""
    settings = _start(log_level)
    with _connected(settings) as connection:
        run = _fetch(tickers, store=motherduck.Store(connection))
    _exit_unless_stored(run)


@app.command()
@_exit_on_error
def compute(
    log_level: typing.Annotated[Level, _log_level()] = Level.WARNING,
) -> None:
    """Recompute every metric from the stored bars."""
    settings = _start(log_level)
    with _connected(settings) as connection:
        run = _compute(store=motherduck.Store(connection))
    _exit_unless_stored(run)


@app.command()
@_exit_on_error
def nightly(
    log_level: typing.Annotated[Level, _log_level()] = Level.WARNING,
) -> None:
    """Fetch every active instrument, then compute; the command a scheduler calls."""
    settings = _start(log_level)
    with _connected(settings) as connection:
        store = motherduck.Store(connection)
        fetched = _fetch(None, store=store)
        computed = _compute(store=store)
    _exit_unless_stored(fetched, computed)


@app.command()
@_exit_on_error
def status(
    log_level: typing.Annotated[Level, _log_level()] = Level.WARNING,
) -> None:
    """Show the last runs' health; exit 1 when a run did not store or data is stale."""
    settings = _start(log_level)
    with _connected(settings) as connection:
        store = motherduck.Store(connection)
        judged = transform.build_status(
            store.read_runs(), missing=store.read_missing(), now=_now()
        )
    output.display_status(judged)
    if not judged.healthy:
        raise typer.Exit(code=1)


@app.command()
@_exit_on_error
def export(
    folder: typing.Annotated[
        pathlib.Path,
        typer.Option("--output", help="Folder the site data is written into."),
    ] = pathlib.Path("web/public/data"),
    log_level: typing.Annotated[Level, _log_level()] = Level.WARNING,
) -> None:
    """Write the dashboard's data files from the store; one CSV row per file."""
    settings = _start(log_level)
    with _connected(settings) as connection:
        written = operate.export_site(
            motherduck.Store(connection), writer=site.Writer(folder)
        )
    output.display_written(written)
