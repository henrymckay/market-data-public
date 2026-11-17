# pyright: reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportUnknownParameterType=false
"""Fetch each instrument's daily history from Yahoo through yfinance."""

import collections.abc
import dataclasses
import logging
import time
from importlib import resources

import curl_cffi.requests.exceptions
import pandas
import polars
import pyrate_limiter
import tenacity
import yaml
import yfinance
import yfinance.exceptions

from market_data.code import port

_LOGGER = logging.getLogger(__name__)

_COLUMNS = {
    "Adj Close": "adj_close",
    "Close": "close",
    "Dividends": "dividend",
    "High": "high",
    "Low": "low",
    "Open": "open",
    "Stock Splits": "split",
    "Volume": "volume",
}

_RETRYABLE = (
    curl_cffi.requests.exceptions.RequestException,
    yfinance.exceptions.YFRateLimitError,
)

type History = collections.abc.Callable[[str], pandas.DataFrame]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Constants:
    """Yahoo's per-source constants, from the package's YAML."""

    attempts: int
    max_wait: float
    requests_per_second: int
    tolerance: int


@dataclasses.dataclass(slots=True)
class Requests:
    """A run's count of requests sent to Yahoo, retries included."""

    sent: int = 0


def _parse(ticker: str, frame: pandas.DataFrame) -> polars.DataFrame:
    """Map one instrument's yfinance frame into the bars schema."""
    days = polars.Series(
        "day", pandas.DatetimeIndex(frame.index).strftime("%Y-%m-%d")
    ).str.to_date()
    return (
        polars.DataFrame(frame[list(_COLUMNS)].reset_index(drop=True))
        .rename(_COLUMNS)
        .with_columns(
            days,
            polars.col("dividend", "split").fill_null(0.0),
            polars.col("volume").cast(polars.Int64, strict=False),
            ticker=polars.lit(ticker),
        )
        .select(port.BARS.names())
        .match_to_schema(port.BARS)
    )


def build_history(
    constants: Constants,
    *,
    requests: Requests,
    sleep: collections.abc.Callable[[float], None] = time.sleep,
) -> History:
    """Return the getter of one instrument's full history, paced and retried.

    :param constants: Pace and retry constants.
    :param requests: Counts every request sent, retries included.
    :param sleep: Waits between retries; a test passes a spy.
    :returns: A function from a ticker to yfinance's raw frame.
    """
    yfinance.config.debug.hide_exceptions = False
    limiter = pyrate_limiter.Limiter(
        [
            pyrate_limiter.Rate(
                constants.requests_per_second, pyrate_limiter.Duration.SECOND
            )
        ]
    )
    retrying = tenacity.Retrying(
        reraise=True,
        retry=tenacity.retry_if_exception_type(_RETRYABLE),
        sleep=sleep,
        stop=tenacity.stop_after_attempt(constants.attempts),
        wait=tenacity.wait_exponential_jitter(initial=1, max=constants.max_wait),
    )

    def attempt(ticker: str) -> pandas.DataFrame:
        limiter.try_acquire("yahoo", timeout=60)
        requests.sent += 1
        return yfinance.Ticker(ticker).history(
            actions=True, auto_adjust=False, interval="1d", period="max"
        )

    def get_history(ticker: str) -> pandas.DataFrame:
        return retrying(attempt, ticker)

    return get_history


def fetch_bars(
    tickers: collections.abc.Sequence[str],
    *,
    history: History,
    requests: Requests,
) -> port.Fetched:
    """Fetch every ticker's history, failing an instrument rather than the run.

    :param tickers: The instruments to fetch.
    :param history: Returns one instrument's raw frame.
    :param requests: The run's request count, read once all are fetched.
    :returns: The bars that arrived and the instruments that answered nothing.
    """
    answers: list[polars.DataFrame] = []
    failed: list[port.Failure] = []
    for ticker in tickers:
        try:
            frame = history(ticker)
            bars = _parse(ticker, frame) if len(frame) else None
        except yfinance.exceptions.YFTickerMissingError:
            failed.append(port.Failure(reason="no data", ticker=ticker))
        except (*_RETRYABLE, yfinance.exceptions.YFException) as failure:
            failed.append(port.Failure(reason=type(failure).__name__, ticker=ticker))
        except AttributeError, KeyError, ValueError, polars.exceptions.PolarsError:
            failed.append(port.Failure(reason="unparseable response", ticker=ticker))
        else:
            if bars is None:
                failed.append(port.Failure(reason="no data", ticker=ticker))
            else:
                answers.append(bars)
    for failure in failed:
        _LOGGER.warning("%s failed: %s", failure.ticker, failure.reason)
    return port.Fetched(
        bars=polars.concat(answers) if answers else polars.DataFrame(schema=port.BARS),
        failed=tuple(failed),
        requests=requests.sent,
    )


def read_constants() -> Constants:
    """Read Yahoo's constants from the package data."""
    text = resources.files("market_data").joinpath("data/adapt/yahoo.yaml").read_text()
    raw = yaml.safe_load(text)
    return Constants(
        attempts=raw["attempts"],
        max_wait=raw["max-wait"],
        requests_per_second=raw["requests-per-second"],
        tolerance=raw["tolerance"],
    )
