# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""The typer app and its commands; the composition root."""

import collections.abc
import datetime
import enum
import functools
import logging
import time
import typing

import typer

from market_data.code import error, operate, transform
from market_data.code.adapt import motherduck, universe, yahoo
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


def _run_fetch(requested: list[str] | None, *, log_level: Level) -> None:
    """Fetch the requested instruments, or every active one, and show the run."""
    logging_.configure(
        level=logging.getLevelNamesMapping()[log_level.upper()],
        secret=config.read_token_for_redaction(),
    )
    settings = config.read_settings()
    everyone = universe.read_universe()
    tickers = requested or transform.active_tickers(everyone)
    unknown = sorted(set(tickers) - set(everyone.get_column("ticker").to_list()))
    if unknown:
        raise error.ConfigurationError(f"Not in the universe: {', '.join(unknown)}")
    constants = yahoo.read_constants()
    requests = yahoo.Requests()
    history = yahoo.build_history(constants, requests=requests)
    opened = time.monotonic()
    connection = motherduck.connect(settings.database)
    try:
        run = operate.fetch_bars(
            tickers,
            fetch=lambda wanted: yahoo.fetch_bars(
                wanted, history=history, requests=requests
            ),
            now=lambda: datetime.datetime.now(datetime.UTC),
            sink=motherduck.Store(connection),
            tolerance=constants.tolerance,
            universe=everyone,
        )
    finally:
        connection.close()
        _LOGGER.info("Connected to the store for %.0f s", time.monotonic() - opened)
    output.display_manifest(run)
    if run.outcome is not transform.Outcome.STORED:
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
    _run_fetch(tickers, log_level=log_level)


@app.command()
@_exit_on_error
def nightly(
    log_level: typing.Annotated[Level, _log_level()] = Level.WARNING,
) -> None:
    """Fetch every active instrument; the command a scheduler calls."""
    _run_fetch(None, log_level=log_level)
