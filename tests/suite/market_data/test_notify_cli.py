import csv
import datetime
import io
import logging

import duckdb
import polars
import pytest
import typer.testing

from market_data.code import transform
from market_data.code.adapt import motherduck, ntfy
from market_data.code.drive import cli, logging_
from pytest_ import alerting, ntfy_stub

TOPIC = "md-topic-for-tests"


@pytest.fixture
def runner():
    return typer.testing.CliRunner()


def _fill(path, *, partial=False):
    """Fill a local store with a signal, its universe and a night's runs."""
    connection = motherduck.connect(path)
    tables = {
        "signals": alerting.signals_of(
            alerting.signal("NVDA"), alerting.signal("AMD", grade="B", score=2)
        ),
        "tickers": alerting.tickers_of(("NVDA", "stock"), ("AMD", "stock")),
        "signal_stats": alerting.stats_of(alerting.stat()),
        "structure": alerting.structure_of(("NVDA", "m", "up")),
    }
    for name, frame in tables.items():
        connection.register("incoming", frame.to_arrow())
        columns = ", ".join(frame.columns)
        connection.execute(
            f"insert into {name} ({columns}) select {columns} from incoming"
        )
    now = datetime.datetime.now(datetime.UTC)
    today = now.date()
    sources = [
        ("yahoo", "partial" if partial else "stored"),
        ("signals", "stored"),
        ("metrics", "stored"),
    ]
    for source, outcome in sources:
        connection.execute(
            "insert into runs values (?, ?, ?, ?, ?, 0, 0, 1, ?, ?)",
            [today, now, 3 if outcome == "partial" else 0, today, outcome, source, now],
        )
    connection.close()


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = str(tmp_path / "alerts.duckdb")
    monkeypatch.setenv("MARKET_DATA_DATABASE", path)
    monkeypatch.delenv("motherduck_token", raising=False)
    monkeypatch.delenv("NTFY_TOPIC", raising=False)
    return path


def _recent(path, *, days=1):
    """Move the stored signals to `days` ago, whatever day the suite runs."""
    yesterday = datetime.datetime.now(datetime.UTC).date() - datetime.timedelta(
        days=days
    )
    connection = duckdb.connect(path)
    connection.execute("update signals set known = ?", [yesterday])
    connection.close()


def _count(path, table):
    connection = duckdb.connect(path, read_only=True)
    try:
        row = connection.execute(f"select count(*) from {table}").fetchone()
        assert row is not None
        return row[0]
    finally:
        connection.close()


def _rows(text):
    return list(csv.DictReader(io.StringIO(text)))


@pytest.fixture
def channel(monkeypatch):
    with ntfy_stub.Stub() as stub:
        monkeypatch.setattr(
            ntfy,
            "read_constants",
            lambda: ntfy.Constants(
                base_url=stub.url, pause=0.0, retry_waits=(0.0,), timeout=2.0
            ),
        )
        monkeypatch.setenv("NTFY_TOPIC", TOPIC)
        yield stub


def test_when_dry_run_then_every_message_is_shown_whole_and_nothing_is_recorded(
    runner, store
):
    _fill(store)
    _recent(store)

    result = runner.invoke(cli.app, ["notify", "--dry-run"])

    [push, digest] = _rows(result.stdout)
    assert result.exit_code == 0
    assert push["title"] == "NVDA weekly: first higher high (A)"
    assert push["priority"] == "4"
    assert push["attachment"] == "nvda-w.png"
    assert "Base rate: 66% rose" in push["message"]
    assert digest["kind"] == "digest"
    assert _count(store, "alerts") == 0


def test_when_dry_run_asks_for_a_table_then_messages_are_laid_out_as_text(
    runner, store
):
    _fill(store)
    _recent(store)

    result = runner.invoke(cli.app, ["notify", "--dry-run", "--format", "table"])

    assert "push (priority 4): NVDA weekly: first higher high (A)" in result.stdout
    assert "  button Chart: " in result.stdout


def test_when_no_topic_is_set_then_notify_exits_2(runner, store):
    _fill(store)

    result = runner.invoke(cli.app, ["notify"])

    assert result.exit_code == 2
    assert "NTFY_TOPIC is not set" in result.output


def test_when_notify_sends_then_a_csv_row_per_message_and_alerts_rows_are_kept(
    runner, store, channel
):
    _fill(store)
    _recent(store)

    result = runner.invoke(cli.app, ["notify"])

    assert result.exit_code == 0
    assert [(row["kind"], row["status"]) for row in _rows(result.stdout)] == [
        ("push", "sent"),
        ("digest", "sent"),
    ]
    assert result.stdout.splitlines()[0] == "kind,title,signals,status"
    assert [seen.method for seen in channel.seen] == ["POST", "POST"]
    assert _count(store, "alerts") == 3
    assert TOPIC not in result.output


def test_when_nothing_is_due_then_notify_prints_a_header_and_exits_0(
    runner, store, channel
):
    _fill(store)
    _recent(store, days=30)

    result = runner.invoke(cli.app, ["notify"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "kind,title,signals,status"
    assert channel.seen == []


def test_when_the_channel_fails_then_notify_exits_1_and_records_nothing(
    runner, store, monkeypatch, caplog
):
    _fill(store)
    _recent(store)
    with ntfy_stub.Stub([500] * 20) as stub:
        monkeypatch.setattr(
            ntfy,
            "read_constants",
            lambda: ntfy.Constants(
                base_url=stub.url, pause=0.0, retry_waits=(0.0,), timeout=2.0
            ),
        )
        monkeypatch.setenv("NTFY_TOPIC", TOPIC)
        with caplog.at_level(logging.WARNING):
            result = runner.invoke(cli.app, ["notify"])

    assert result.exit_code == 1
    assert {row["status"] for row in _rows(result.stdout)} == {"failed"}
    assert _count(store, "alerts") == 0


def test_when_status_alert_finds_a_new_failure_then_one_health_message_goes(
    runner, store, channel
):
    _fill(store, partial=True)

    first = runner.invoke(cli.app, ["status", "--alert"])
    second = runner.invoke(cli.app, ["status", "--alert"])

    assert first.exit_code == second.exit_code == 1
    assert [seen.method for seen in channel.seen] == ["POST"]
    assert "Market data: nightly partial" in channel.seen[0].body.decode()
    assert _count(store, "alert_state") == 1


def test_when_status_alert_has_no_topic_then_it_exits_2(runner, store):
    _fill(store)

    result = runner.invoke(cli.app, ["status", "--alert"])

    assert result.exit_code == 2


def test_when_a_line_holds_the_topic_then_logging_replaces_it(capsys):
    logging_.configure(level=logging.INFO, secrets=["tok-en", TOPIC])

    logging.getLogger("x").info("sent to %s with tok-en", TOPIC)

    assert capsys.readouterr().err.count("[redacted]") == 2


def test_when_the_store_is_asked_then_alerts_state_and_chart_reads_work(tmp_path):
    connection = motherduck.connect(str(tmp_path / "s.duckdb"))
    store = motherduck.Store(connection)
    when = datetime.datetime(2026, 11, 18, 3, tzinfo=datetime.UTC)
    rows = polars.DataFrame(
        {
            "id": ["a"],
            "kind": ["push"],
            "message": ["m1"],
            "sent": [when],
            "title": ["t"],
        },
        schema=transform.ALERTS,
    )

    store.append_alerts(rows)
    store.replace_alert_state(changed=when, detail="d", state="unhealthy")
    store.replace_alert_state(changed=when, detail="d", state="healthy")

    assert store.read_sent().get_column("id").to_list() == ["a"]
    assert store.read_alert_state() == "healthy"


def test_when_the_app_fails_unexpectedly_then_tracebacks_show_no_locals():
    assert cli.app.pretty_exceptions_show_locals is False
    assert all(
        group.typer_instance is not None
        and group.typer_instance.pretty_exceptions_show_locals is False
        for group in cli.app.registered_groups
    )
