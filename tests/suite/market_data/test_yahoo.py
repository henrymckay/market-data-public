import datetime

import pandas
import polars
import pytest
import yfinance.exceptions

from market_data.code import port
from market_data.code.adapt import yahoo


def _answering(frame):
    return lambda _ticker: frame


def _raising(failure):
    def history(_ticker):
        raise failure

    return history


def test_when_fetch_bars_then_a_recorded_response_maps_to_the_bars_schema(aapl_frame):
    fetched = yahoo.fetch_bars(
        ["AAPL"], history=_answering(aapl_frame), requests=yahoo.Requests()
    )

    assert fetched.bars.schema == port.BARS
    assert fetched.bars.height == len(aapl_frame)
    assert fetched.failed == ()
    assert fetched.bars.get_column("ticker").unique().to_list() == ["AAPL"]


def test_when_fetch_bars_then_day_is_the_exchange_local_date(aapl_frame):
    fetched = yahoo.fetch_bars(
        ["AAPL"], history=_answering(aapl_frame), requests=yahoo.Requests()
    )

    expected = [timestamp.date() for timestamp in aapl_frame.index]
    assert fetched.bars.get_column("day").to_list() == expected


def test_when_fetch_bars_then_dividends_and_closes_come_through(aapl_frame):
    fetched = yahoo.fetch_bars(
        ["AAPL"], history=_answering(aapl_frame), requests=yahoo.Requests()
    )

    assert fetched.bars.get_column("dividend").sum() == pytest.approx(
        aapl_frame["Dividends"].sum()
    )
    assert fetched.bars.get_column("adj_close").to_list() == pytest.approx(
        aapl_frame["Adj Close"].to_list()
    )
    assert (
        fetched.bars.get_column("adj_close").to_list()
        != fetched.bars.get_column("close").to_list()
    )


def test_when_fetch_bars_then_a_forming_bar_is_returned_for_the_core_to_drop(
    eurusd_frame,
):
    fetched = yahoo.fetch_bars(
        ["EURUSD=X"], history=_answering(eurusd_frame), requests=yahoo.Requests()
    )

    assert fetched.bars.get_column("day").to_list()[-1] >= datetime.date(2026, 11, 17)


def test_when_a_ticker_is_missing_then_it_fails_with_no_data(aapl_frame):
    def history(ticker):
        if ticker == "NOPE":
            raise yfinance.exceptions.YFPricesMissingError("NOPE", "delisted")
        return aapl_frame

    fetched = yahoo.fetch_bars(
        ["AAPL", "NOPE"], history=history, requests=yahoo.Requests()
    )

    assert fetched.failed == (port.Failure(reason="no data", ticker="NOPE"),)
    assert fetched.bars.get_column("ticker").unique().to_list() == ["AAPL"]


def test_when_the_frame_is_empty_then_the_ticker_fails_with_no_data():
    fetched = yahoo.fetch_bars(
        ["AAPL"], history=_answering(pandas.DataFrame()), requests=yahoo.Requests()
    )

    assert fetched.failed == (port.Failure(reason="no data", ticker="AAPL"),)
    assert fetched.bars.schema == port.BARS


def test_when_the_frame_lacks_columns_then_the_ticker_is_unparseable():
    frame = pandas.DataFrame(
        {"Close": [1.0]}, index=pandas.DatetimeIndex(["2026-11-13"])
    )

    fetched = yahoo.fetch_bars(
        ["AAPL"], history=_answering(frame), requests=yahoo.Requests()
    )

    assert fetched.failed == (
        port.Failure(reason="unparseable response", ticker="AAPL"),
    )


def test_when_every_ticker_fails_then_bars_are_empty_in_the_schema():
    fetched = yahoo.fetch_bars(
        ["A", "B"],
        history=_raising(yfinance.exceptions.YFPricesMissingError("A", "x")),
        requests=yahoo.Requests(),
    )

    assert fetched.bars.equals(polars.DataFrame(schema=port.BARS))
    assert [failure.ticker for failure in fetched.failed] == ["A", "B"]


class _FlakyTicker:
    """A stand-in for yfinance.Ticker that throttles a set number of times."""

    throttles = 0
    calls = 0

    def __init__(self, ticker):
        self.ticker = ticker

    def history(self, **_options):
        type(self).calls += 1
        if type(self).calls <= type(self).throttles:
            raise yfinance.exceptions.YFRateLimitError()
        return pandas.DataFrame()


def _constants(attempts):
    return yahoo.Constants(
        attempts=attempts, max_wait=1, requests_per_second=1000, tolerance=0
    )


def test_when_yahoo_throttles_then_the_request_is_retried_and_counted(monkeypatch):
    monkeypatch.setattr(yahoo.yfinance, "Ticker", _FlakyTicker)
    _FlakyTicker.throttles, _FlakyTicker.calls = 2, 0
    waits: list[float] = []
    requests = yahoo.Requests()
    history = yahoo.build_history(_constants(5), requests=requests, sleep=waits.append)

    frame = history("AAPL")

    assert len(frame) == 0
    assert (requests.sent, len(waits)) == (3, 2)


def test_when_retries_run_out_then_the_ticker_fails_with_the_error_name(monkeypatch):
    monkeypatch.setattr(yahoo.yfinance, "Ticker", _FlakyTicker)
    _FlakyTicker.throttles, _FlakyTicker.calls = 99, 0
    requests = yahoo.Requests()
    history = yahoo.build_history(
        _constants(3), requests=requests, sleep=lambda _s: None
    )

    fetched = yahoo.fetch_bars(["AAPL"], history=history, requests=requests)

    assert fetched.failed == (port.Failure(reason="YFRateLimitError", ticker="AAPL"),)
    assert fetched.requests == 3


def test_when_read_constants_then_the_yaml_values_arrive():
    constants = yahoo.read_constants()

    assert (constants.attempts, constants.requests_per_second, constants.tolerance) == (
        5,
        1,
        0,
    )
