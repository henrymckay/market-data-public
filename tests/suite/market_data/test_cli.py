import csv
import logging

import duckdb
import pytest
import typer.testing
import yfinance.exceptions

from market_data.code.adapt import yahoo
from market_data.code.drive import cli, logging_

_HEADER = (
    "day,ended,failed_items,last_day,outcome,rejected,requests,rows,source,started"
)


@pytest.fixture
def runner():
    return typer.testing.CliRunner()


@pytest.fixture
def database(tmp_path, monkeypatch):
    path = str(tmp_path / "market.duckdb")
    monkeypatch.setenv("MARKET_DATA_DATABASE", path)
    monkeypatch.delenv("motherduck_token", raising=False)
    return path


@pytest.fixture
def answering(monkeypatch, aapl_frame):
    """Make Yahoo answer with the recorded frame, except for the symbols in `dead`."""
    dead: set[str] = set()

    def build_history(_constants, *, requests, sleep=None):
        def history(ticker):
            requests.sent += 1
            if ticker in dead:
                raise yfinance.exceptions.YFPricesMissingError(ticker, "gone")
            return aapl_frame

        return history

    monkeypatch.setattr(yahoo, "build_history", build_history)
    return dead


def _counts(database):
    connection = duckdb.connect(database, read_only=True)
    return connection.execute(
        "select count(*), count(distinct ticker) from bars"
    ).fetchone()


def test_when_fetch_some_tickers_then_manifest_row_is_csv_and_exit_0(
    runner, database, answering
):
    result = runner.invoke(cli.app, ["fetch", "AAPL", "MSFT"])

    lines = result.stdout.splitlines()
    assert result.exit_code == 0
    assert lines[0] == _HEADER
    assert lines[1].split(",")[4:9] == ["stored", "0", "2", "1000", "yahoo"]
    assert _counts(database) == (1000, 2)


def test_when_nightly_then_every_active_instrument_is_loaded(
    runner, database, answering, real_universe
):
    result = runner.invoke(cli.app, ["nightly"])

    assert result.exit_code == 0
    assert _counts(database) == (500 * real_universe.height, real_universe.height)


def test_when_run_twice_then_counts_do_not_change(runner, database, answering):
    runner.invoke(cli.app, ["fetch", "AAPL", "MSFT"])
    first = _counts(database)

    result = runner.invoke(cli.app, ["fetch", "AAPL", "MSFT"])

    assert result.exit_code == 0
    assert _counts(database) == first


def test_when_an_instrument_fails_then_exit_1_and_partial(runner, database, answering):
    answering.add("MSFT")

    result = runner.invoke(cli.app, ["fetch", "AAPL", "MSFT"])

    assert result.exit_code == 1
    row = result.stdout.splitlines()[1].split(",")
    assert (row[2], row[4]) == ("1", "partial")
    assert _counts(database) == (500, 1)


def test_when_every_instrument_fails_then_exit_1_failed_and_no_bars(
    runner, database, answering
):
    answering.update({"AAPL", "MSFT"})

    result = runner.invoke(cli.app, ["fetch", "AAPL", "MSFT"])

    assert result.exit_code == 1
    assert ",failed," in result.stdout
    assert _counts(database) == (0, 0)


def test_when_the_token_is_missing_for_motherduck_then_exit_2(runner, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_DATABASE", "md:market_data")
    monkeypatch.delenv("motherduck_token", raising=False)

    result = runner.invoke(cli.app, ["fetch", "AAPL"])

    assert result.exit_code == 2
    assert "motherduck_token is not set" in result.stderr


def test_when_a_ticker_is_not_in_the_universe_then_exit_2(runner, database, answering):
    result = runner.invoke(cli.app, ["fetch", "ZZZZ"])

    assert result.exit_code == 2
    assert "ZZZZ" in result.stderr


def test_when_a_token_is_set_then_no_output_or_log_line_holds_it(
    runner, database, answering, monkeypatch
):
    secret = "placeholder value for the test"
    monkeypatch.setenv("motherduck_token", secret)

    result = runner.invoke(cli.app, ["fetch", "AAPL", "--log-level", "debug"])

    assert result.exit_code == 0
    assert secret not in result.stdout + result.stderr


def test_when_a_line_holds_the_secret_then_logging_replaces_it(capsys):
    logging_.configure(level=logging.INFO, secret="s3cret-value")

    logging.getLogger("market_data").info("connecting with s3cret-value now")

    logged = capsys.readouterr().err
    assert "s3cret-value" not in logged
    assert "connecting with [redacted] now" in logged


def _rows(stdout):
    return [line.split(",") for line in stdout.splitlines()]


def _status(result):
    rows = csv.reader(result.stdout.splitlines()[1:])
    return dict(rows)


def test_when_compute_after_fetch_then_a_metrics_row_is_shown_and_stored(
    runner, database, answering
):
    runner.invoke(cli.app, ["fetch", "AAPL", "MSFT"])

    result = runner.invoke(cli.app, ["compute"])

    lines = _rows(result.stdout)
    assert result.exit_code == 1
    assert lines[0] == _HEADER.split(",")
    assert (lines[1][4], lines[1][8]) == ("partial", "metrics")
    connection = duckdb.connect(database, read_only=True)
    stored = connection.execute("select count(distinct ticker) from metrics").fetchone()
    assert stored == (2,)


def test_when_nightly_then_one_header_and_a_row_per_stage_and_exit_0(
    runner, database, answering, real_universe
):
    result = runner.invoke(cli.app, ["nightly"])

    lines = _rows(result.stdout)
    assert result.exit_code == 0
    assert [line[8] for line in lines[1:]] == ["yahoo", "metrics"]
    assert [line[4] for line in lines[1:]] == ["stored", "stored"]
    assert len(lines) == 3
    connection = duckdb.connect(database, read_only=True)
    stored = connection.execute("select count(distinct ticker) from metrics").fetchone()
    assert stored == (real_universe.height,)


def test_when_compute_finds_no_bars_then_exit_1_and_failed(runner, database):
    result = runner.invoke(cli.app, ["compute"])

    assert result.exit_code == 1
    assert ",failed," in result.stdout


def test_when_nightly_and_one_instrument_has_no_data_then_exit_1_naming_it(
    runner, database, answering
):
    answering.add("MSFT")

    result = runner.invoke(cli.app, ["nightly"])

    assert result.exit_code == 1
    assert "MSFT failed" in result.stderr
    assert [line[4] for line in _rows(result.stdout)[1:]] == ["partial", "partial"]


def test_when_status_after_a_good_nightly_then_exit_0_and_key_value_rows(
    runner, database, answering
):
    runner.invoke(cli.app, ["nightly"])

    result = runner.invoke(cli.app, ["status"])

    assert result.exit_code == 0
    assert result.stdout.splitlines()[0] == "key,value"
    assert _status(result)["outcome"] == "stored"
    assert _status(result)["missing"] == ""
    assert _status(result)["stale"] == "false"


def test_when_status_after_a_partial_nightly_then_exit_1_and_the_missing_are_named(
    runner, database, answering
):
    answering.add("MSFT")
    runner.invoke(cli.app, ["nightly"])

    result = runner.invoke(cli.app, ["status"])

    assert result.exit_code == 1
    assert _status(result)["missing"] == "MSFT"


def test_when_status_on_an_empty_store_then_exit_1(runner, database):
    result = runner.invoke(cli.app, ["status"])

    assert result.exit_code == 1
    assert _status(result)["outcome"] == "none"
