import csv
import dataclasses
import logging

import duckdb
import pytest
import typer.testing
import yfinance.exceptions

from market_data.code.adapt import yahoo
from market_data.code.drive import cli, logging_

_CONSTANTS = yahoo.read_constants

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
    constants = dataclasses.replace(_CONSTANTS(), tolerance=0)
    monkeypatch.setattr(yahoo, "read_constants", lambda: constants)

    def build_history(_constants, *, requests, sleep=None):
        def history(ticker, _period):
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
    assert [line[8] for line in lines[1:]] == ["yahoo", "signals", "metrics"]
    assert [line[4] for line in lines[1:]] == ["stored", "stored", "stored"]
    assert len(lines) == 4
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
    assert [line[4] for line in _rows(result.stdout)[1:]] == [
        "partial",
        "stored",
        "partial",
    ]


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


def test_when_a_few_instruments_fail_within_tolerance_then_exit_0_and_stored(
    runner, database, answering, monkeypatch
):
    monkeypatch.setattr(yahoo, "read_constants", _CONSTANTS)
    answering.add("MSFT")

    result = runner.invoke(cli.app, ["fetch", "AAPL", "MSFT"])

    row = result.stdout.splitlines()[1].split(",")
    assert result.exit_code == 0
    assert (row[2], row[4]) == ("1", "stored")


def test_when_fetch_is_full_then_every_instrument_is_asked_for_max(
    runner, database, monkeypatch, aapl_frame
):
    monkeypatch.delenv("motherduck_token", raising=False)
    periods: list[str] = []

    def build_history(_constants, *, requests, sleep=None):
        def history(_ticker, period):
            requests.sent += 1
            periods.append(period)
            return aapl_frame

        return history

    monkeypatch.setattr(yahoo, "build_history", build_history)
    runner.invoke(cli.app, ["fetch", "AAPL"])
    runner.invoke(cli.app, ["fetch", "AAPL"])
    runner.invoke(cli.app, ["fetch", "AAPL", "--full"])

    assert periods == ["max", "1mo", "max"]


_RATES_HEADER = "event,timeframe,horizon,n,hit_rate,baseline_hit,edge,held_rate"


def _table_counts(database, *tables):
    connection = duckdb.connect(database, read_only=True)
    return {
        table: connection.execute(f"select count(*) from {table}").fetchall()[0][0]
        for table in tables
    }


def test_when_signals_runs_then_it_stores_the_five_tables_and_one_manifest_row(
    runner, database, answering
):
    runner.invoke(cli.app, ["fetch", "AAPL", "MSFT"])

    result = runner.invoke(cli.app, ["signals"])

    lines = _rows(result.stdout)
    counts = _table_counts(database, "signals", "pivots", "structure", "signal_stats")
    assert result.exit_code == 0
    assert lines[0] == _HEADER.split(",")
    assert (lines[1][4], lines[1][6], lines[1][8]) == ("stored", "0", "signals")
    assert int(lines[1][7]) == counts["signals"] > 0
    assert counts["pivots"] > 0
    assert counts["structure"] == 6
    assert counts["signal_stats"] > 0


def test_when_signals_runs_twice_then_the_tables_hold_the_same_rows(
    runner, database, answering
):
    runner.invoke(cli.app, ["fetch", "AAPL", "MSFT"])
    runner.invoke(cli.app, ["signals"])
    first = _table_counts(database, "signals", "pivots", "outcomes", "signal_stats")

    runner.invoke(cli.app, ["signals"])

    assert (
        _table_counts(database, "signals", "pivots", "outcomes", "signal_stats")
        == first
    )


def test_when_signals_runs_dry_then_nothing_is_written_and_the_base_rates_print(
    runner, database, answering
):
    runner.invoke(cli.app, ["fetch", "AAPL", "MSFT"])

    result = runner.invoke(cli.app, ["signals", "--dry-run"])

    lines = _rows(result.stdout)
    assert result.exit_code == 0
    assert ",".join(lines[0]) == _RATES_HEADER
    assert len(lines) > 1
    assert _table_counts(database, "signals", "pivots", "runs") == {
        "signals": 0,
        "pivots": 0,
        "runs": 1,
    }


def test_when_the_format_is_table_then_the_columns_are_aligned(
    runner, database, answering
):
    runner.invoke(cli.app, ["fetch", "AAPL", "MSFT"])

    result = runner.invoke(cli.app, ["signals", "--dry-run", "--format", "table"])

    lines = result.stdout.splitlines()
    assert result.exit_code == 0
    assert lines[0].split() == _RATES_HEADER.split(",")
    assert len({len(line) for line in lines}) == 1


def test_when_the_rules_file_lacks_a_key_then_exit_2_names_it(
    runner, database, answering, tmp_path
):
    rules = tmp_path / "alt.yaml"
    rules.write_text("atr-bars: 14\n")

    result = runner.invoke(cli.app, ["signals", "--rules", str(rules), "--dry-run"])

    assert result.exit_code == 2
    assert "alerts" in result.stderr


def test_when_the_rules_file_has_an_unknown_grade_then_exit_2(
    runner, database, answering, tmp_path
):
    packaged = yahoo.resources.files("market_data").joinpath(
        "data/transform/monitor.yaml"
    )
    rules = tmp_path / "alt.yaml"
    rules.write_text(
        packaged.read_text().replace("grades: {A: 3, B: 2}", "grades: {A: 3, D: 2}")
    )

    result = runner.invoke(cli.app, ["signals", "--rules", str(rules)])

    assert result.exit_code == 2
    assert "grades" in result.stderr


def test_when_another_rules_file_is_dry_run_then_its_rates_differ_from_the_packaged(
    runner, database, answering, tmp_path
):
    runner.invoke(cli.app, ["fetch", "AAPL", "MSFT"])
    packaged = yahoo.resources.files("market_data").joinpath(
        "data/transform/monitor.yaml"
    )
    rules = tmp_path / "alt.yaml"
    rules.write_text(packaged.read_text().replace("d: 2.5", "d: 1.0", 1))

    first = runner.invoke(cli.app, ["signals", "--dry-run"])
    second = runner.invoke(cli.app, ["signals", "--rules", str(rules), "--dry-run"])

    assert first.exit_code == second.exit_code == 0
    assert first.stdout != second.stdout


def test_when_there_are_no_bars_then_signals_fails_and_stores_nothing(runner, database):
    result = runner.invoke(cli.app, ["signals"])

    assert result.exit_code == 1
    assert ",failed," in result.stdout
    assert _table_counts(database, "signals") == {"signals": 0}


def test_when_nightly_runs_then_the_overview_carries_each_instruments_trend(
    runner, database, answering
):
    runner.invoke(cli.app, ["nightly"])

    connection = duckdb.connect(database, read_only=True)
    states = connection.execute(
        "select distinct trend_d from overview where ticker = 'AAPL'"
    ).fetchall()
    assert states[0][0] in {"up", "down", "turning_up", "turning_down", "none"}
