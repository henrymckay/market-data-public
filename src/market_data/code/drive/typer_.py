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

import polars
import typer

from market_data.code import error, operate, transform
from market_data.code.adapt import motherduck, rules, universe, wikipedia, yahoo
from market_data.code.drive import config, logging_, output

_LOGGER = logging.getLogger(__name__)

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)
universe_app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Keep the universe of instruments current.",
    no_args_is_help=True,
)
app.add_typer(universe_app, name="universe")


class Form(enum.StrEnum):
    """How a dry run's base rates are written."""

    CSV = "csv"
    TABLE = "table"


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
        except (error.SourceError, error.StoreError) as failure:
            typer.echo(str(failure), err=True)
            raise typer.Exit(code=1) from None

    return run


def _full_option() -> typer.models.OptionInfo:
    """Return the option asking for every instrument's whole history."""
    return typer.Option(
        help="Fetch each instrument's whole history, not its last month."
    )


def _log_level() -> typer.models.OptionInfo:
    """Return the option choosing the lowest log level shown."""
    return typer.Option(help="Lowest log level shown, on standard error.")


@contextlib.contextmanager
def _connected(
    settings: config.Settings,
) -> collections.abc.Generator[motherduck.Store]:
    """Hold the store for the block and log the seconds spent inside its calls."""
    opened = time.monotonic()
    connection = motherduck.connect(settings.database)
    store = motherduck.Store(
        connection, meter=motherduck.Meter(seconds=time.monotonic() - opened)
    )
    try:
        yield store
    finally:
        connection.close()
        _LOGGER.info("Store busy for %.0f s", store.meter.seconds)


def _start(log_level: Level) -> config.Settings:
    """Configure logging and read the settings, once per command."""
    logging_.configure(
        level=logging.getLevelNamesMapping()[log_level.upper()],
        secret=config.read_token_for_redaction(),
    )
    return config.read_settings()


def _fetch(
    requested: list[str] | None, *, full: bool, store: motherduck.Store
) -> transform.Run:
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
        fetch=lambda wanted, period: yahoo.fetch_bars(
            wanted, period, history=history, requests=requests
        ),
        full=full,
        now=_now,
        sink=store,
        tolerance=constants.tolerance,
        universe=everyone,
    )


def _compute(*, bars: polars.DataFrame, store: motherduck.Store) -> transform.Run:
    """Recompute the metrics from the bars."""
    return operate.compute_metrics(
        bars=bars,
        now=_now,
        store=store,
        tolerance=yahoo.read_constants().tolerance,
        universe=universe.read_universe(),
    )


def _signals(
    *, bars: polars.DataFrame, path: pathlib.Path | None, store: motherduck.Store
) -> transform.Run:
    """Recompute the signals from the bars under the packaged or another rules file."""
    return operate.compute_signals(
        bars=bars, now=_now, rules=rules.read_rules(path), store=store
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
    full: typing.Annotated[bool, _full_option()] = False,
    log_level: typing.Annotated[Level, _log_level()] = Level.WARNING,
) -> None:
    """Fetch the given instruments' last month, or whole history, and store it."""
    settings = _start(log_level)
    with _connected(settings) as store:
        run = _fetch(tickers, full=full, store=store)
    _exit_unless_stored(run)


@app.command()
@_exit_on_error
def compute(
    log_level: typing.Annotated[Level, _log_level()] = Level.WARNING,
) -> None:
    """Recompute every metric from the stored bars."""
    settings = _start(log_level)
    with _connected(settings) as store:
        run = _compute(bars=store.read_bars(), store=store)
    _exit_unless_stored(run)


@app.command()
@_exit_on_error
def signals(
    dry_run: typing.Annotated[
        bool,
        typer.Option(help="Write nothing; show the base rates over every grade."),
    ] = False,
    form: typing.Annotated[
        Form, typer.Option("--format", help="How a dry run's base rates are written.")
    ] = Form.CSV,
    log_level: typing.Annotated[Level, _log_level()] = Level.WARNING,
    rules_path: typing.Annotated[
        pathlib.Path | None,
        typer.Option(
            "--rules", help="Another rules file.", show_default="the packaged"
        ),
    ] = None,
) -> None:
    """Recompute every pivot, signal, outcome, base rate and structure."""
    settings = _start(log_level)
    with _connected(settings) as store:
        if dry_run:
            computed = operate.find_signals(
                bars=store.read_bars(),
                now=_now,
                rules=rules.read_rules(rules_path),
                store=store,
            )
            output.display_rates(
                transform.build_rates(computed.signal_stats), table=form is Form.TABLE
            )
            return
        run = _signals(bars=store.read_bars(), path=rules_path, store=store)
    _exit_unless_stored(run)


@app.command()
@_exit_on_error
def nightly(
    full: typing.Annotated[bool, _full_option()] = False,
    log_level: typing.Annotated[Level, _log_level()] = Level.WARNING,
) -> None:
    """Fetch every active instrument, then signals, then compute; a scheduler's call."""
    settings = _start(log_level)
    with _connected(settings) as store:
        fetched = _fetch(None, full=full, store=store)
        bars = store.read_bars()
        found = _signals(bars=bars, path=None, store=store)
        computed = _compute(bars=bars, store=store)
    _exit_unless_stored(fetched, found, computed)


@app.command()
@_exit_on_error
def status(
    log_level: typing.Annotated[Level, _log_level()] = Level.WARNING,
) -> None:
    """Show the last runs' health; exit 1 when a run did not store or data is stale."""
    settings = _start(log_level)
    with _connected(settings) as store:
        judged = transform.build_status(
            store.read_runs(), missing=store.read_missing(), now=_now()
        )
    output.display_status(judged)
    if not judged.healthy:
        raise typer.Exit(code=1)


@universe_app.command()
@_exit_on_error
def sync(
    check: typing.Annotated[
        bool,
        typer.Option(help="Change nothing; exit 1 when the CSV is out of date."),
    ] = False,
    log_level: typing.Annotated[Level, _log_level()] = Level.WARNING,
) -> None:
    """Bring the CSV's S&P 500 rows in line with Wikipedia's list of members."""
    logging_.configure(
        level=logging.getLevelNamesMapping()[log_level.upper()],
        secret=config.read_token_for_redaction(),
    )
    before = universe.read_universe()
    after = transform.sync_members(before, wikipedia.fetch_members())
    output.display_changes(transform.diff_universe(before, after))
    if after.equals(before):
        return
    if check:
        raise typer.Exit(code=1)
    universe.write_universe(after)
