"""The API's fixed queries, run on a DuckDB file the store adapter wrote."""

import datetime
import json
import pathlib

import polars
import pytest
from sqlfluff.api import lint
from sqlfluff.core import FluffConfig

from market_data.code import operate, port, transform
from market_data.code.adapt import motherduck
from pytest_ import fake, series

_ROOT = pathlib.Path(__file__).parents[3]
_QUERIES = _ROOT / "api" / "src" / "queries"
_DAY = datetime.date(2026, 11, 16)
_STARTED = datetime.datetime(2026, 11, 17, 2, 17, tzinfo=datetime.UTC)
_ENDED = datetime.datetime(2026, 11, 17, 2, 19, 41, tzinfo=datetime.UTC)


def _read(name: str) -> str:
    return (_QUERIES / f"{name}.sql").read_text()


def _body(connection, name: str, *params: str):
    row = connection.execute(_read(name), list(params)).fetchone()
    assert row is not None
    assert isinstance(row[0], str)
    return json.loads(row[0])


@pytest.fixture
def connection(tmp_path, make_bars, small_universe, clock):
    connection = motherduck.connect(str(tmp_path / "market.duckdb"))
    store = motherduck.Store(connection)
    days = [_DAY - datetime.timedelta(days=offset) for offset in (2, 1, 0)]
    bars = make_bars(
        *(
            (ticker, day, {"close": 10.0 + index, "dividend": 0.5 if index else 0.0})
            for ticker in ("AAA", "BBB", "^TNX")
            for index, day in enumerate(days)
        )
    )
    store.replace(
        port.Load(
            since=fake.whole(("AAA", "BBB", "^TNX")),
            bars=bars,
            fetched=_STARTED,
            rejected=polars.DataFrame(schema=port.REJECTED),
            universe=small_universe,
        )
    )
    operate.compute_metrics(
        bars=store.read_bars(),
        now=clock,
        store=store,
        tolerance=0,
        universe=small_universe,
    )
    store.append_run(
        transform.Run(
            day=_DAY,
            ended=_ENDED,
            failed_items=0,
            last_day=_DAY,
            outcome=transform.Outcome.STORED,
            rejected=0,
            requests=3,
            rows=9,
            source="yahoo",
            started=_STARTED,
        )
    )
    return connection


def test_when_latest_then_it_is_the_last_stored_yahoo_run(connection):
    body = _body(connection, "latest")

    assert body == {
        "day": "2026-11-16",
        "ended": "2026-11-17T02:19:41Z",
        "outcome": "stored",
        "rows": 9,
        "version": "2026-11-17T02:18:00Z",
    }


@pytest.mark.parametrize("source", ["metrics", "signals"])
def test_when_a_later_stage_run_stores_then_the_version_moves_to_its_end(
    connection, source
):
    later = datetime.datetime(2026, 11, 17, 3, 5, 9, tzinfo=datetime.UTC)
    for outcome, ended in (
        (transform.Outcome.STORED, later),
        (transform.Outcome.FAILED, later + datetime.timedelta(hours=1)),
    ):
        connection.execute(
            "insert into runs values (?, ?, 0, ?, ?, 0, 0, 0, ?, ?)",
            [_DAY, ended, _DAY, str(outcome), source, later],
        )

    body = _body(connection, "latest")

    assert body["version"] == "2026-11-17T03:05:09Z"
    assert body["ended"] == "2026-11-17T02:19:41Z"


def test_when_no_metrics_run_is_stored_then_the_version_is_null(tmp_path):
    connection = motherduck.connect(str(tmp_path / "yahoo-only.duckdb"))
    connection.execute(
        "insert into runs values (?, ?, 0, ?, 'stored', 0, 0, 0, 'yahoo', ?)",
        [_DAY, _ENDED, _DAY, _STARTED],
    )

    assert _body(connection, "latest")["version"] is None


def test_when_no_run_is_stored_then_latest_is_null(tmp_path):
    connection = motherduck.connect(str(tmp_path / "empty.duckdb"))

    assert _body(connection, "latest") is None


def test_when_overview_then_one_object_per_instrument_with_the_tables_columns(
    connection,
):
    body = _body(connection, "overview")
    columns = [row[0] for row in connection.execute("describe overview").fetchall()]

    assert [row["ticker"] for row in body] == ["AAA", "BBB", "^TNX"]
    assert all(set(row) == set(columns) for row in body)
    assert body[2]["slug"] == "tnx"
    assert len(body[0]["spark"]) == 3


def test_when_overview_is_empty_then_it_is_an_empty_array(tmp_path):
    connection = motherduck.connect(str(tmp_path / "empty.duckdb"))

    assert _body(connection, "overview") == []


def test_when_slugs_then_one_slug_per_instrument_and_every_overview_slug_resolves(
    connection,
):
    slugs = _body(connection, "slugs")
    overview = _body(connection, "overview")

    assert slugs == {row["slug"]: row["ticker"] for row in overview}
    assert slugs["tnx"] == "^TNX"


def test_when_overview_has_featured_and_source_then_each_row_carries_them(connection):
    body = _body(connection, "overview")

    assert [(row["featured"], row["source"]) for row in body] == [
        (True, "sp500"),
        (False, "sp500"),
        (True, "curated"),
    ]


def test_when_slugs_is_empty_then_it_is_an_empty_object(tmp_path):
    connection = motherduck.connect(str(tmp_path / "empty.duckdb"))

    assert _body(connection, "slugs") == {}


def test_when_runs_then_newest_first_with_utc_times(connection):
    body = _body(connection, "runs")

    assert body[0]["source"] == "yahoo"
    assert body[0]["ended"] == "2026-11-17T02:19:41Z"
    assert len(body) == 2


def test_when_bars_then_columns_oldest_first_and_agree_with_the_table(connection):
    body = _body(connection, "bars", "AAA")
    count = connection.execute(
        "select count(*) from bars where ticker = 'AAA'"
    ).fetchone()

    assert body["ticker"] == "AAA"
    assert len(body["day"]) == count[0] == 3
    assert body["day"] == sorted(body["day"])
    assert body["close"] == [10.0, 11.0, 12.0]
    assert body["dividend"] == [0.0, 0.5, 0.5]
    assert set(body) == {
        "ticker", "day", "open", "high", "low", "close", "adj_close",
        "volume", "dividend", "split", "weekly", "monthly", "pivots", "signals",
    }  # fmt: skip


def test_when_bars_for_an_unknown_ticker_then_every_column_is_empty(connection):
    body = _body(connection, "bars", "NOPE")

    assert body["ticker"] is None
    assert body["day"] == []


@pytest.fixture
def signalled(tmp_path, small_universe, rules, clock):
    connection = motherduck.connect(str(tmp_path / "signalled.duckdb"))
    store = motherduck.Store(connection)
    bars = polars.concat(
        [
            series.daily_frame("AAA", series.CONFIRMED),
            series.daily_frame("BBB", series.FAILED_ON_CLOSE),
        ]
    )
    store.replace(
        port.Load(
            since=fake.whole(("AAA", "BBB")),
            bars=bars,
            fetched=_STARTED,
            rejected=polars.DataFrame(schema=port.REJECTED),
            universe=small_universe,
        )
    )
    operate.compute_signals(bars=store.read_bars(), now=clock, rules=rules, store=store)
    operate.compute_metrics(
        bars=store.read_bars(),
        now=clock,
        store=store,
        tolerance=0,
        universe=small_universe,
    )
    return connection


def test_when_signals_then_each_row_carries_the_signal_and_its_instrument(signalled):
    body = _body(signalled, "signals")
    columns = [row[0] for row in signalled.execute("describe signals").fetchall()]

    assert body
    assert all(set(row) == {*columns, "name", "asset_class", "slug"} for row in body)
    assert {row["ticker"]: (row["name"], row["slug"]) for row in body} == {
        "AAA": ("Alpha", "aaa"),
        "BBB": ("Beta", "bbb"),
    }
    assert len(body) == signalled.execute("select count(*) from signals").fetchone()[0]


def test_when_signals_then_newest_known_first_and_highest_score_within_a_day(
    signalled,
):
    body = _body(signalled, "signals")
    keys = [(row["known"], row["score"]) for row in body]

    assert keys == sorted(keys, reverse=True)


def test_when_signals_are_older_than_120_days_then_they_are_left_out(signalled):
    signalled.execute(
        "update signals set known = known + 400 where id like 'AAA|d|break_up|%'"
    )
    newest = signalled.execute("select max(known) from signals").fetchone()[0]
    ids = {row["id"] for row in _body(signalled, "signals")}
    kept = signalled.execute(
        "select id from signals where known > ? - 120", [newest]
    ).fetchall()

    assert ids == {row[0] for row in kept}
    assert ids != {
        row[0] for row in signalled.execute("select id from signals").fetchall()
    }


def test_when_there_are_no_signals_then_the_body_is_an_empty_array(tmp_path):
    connection = motherduck.connect(str(tmp_path / "empty.duckdb"))

    assert _body(connection, "signals") == []
    assert _body(connection, "stats") == []


def test_when_stats_then_one_object_per_signal_stats_row(signalled):
    body = _body(signalled, "stats")
    count = signalled.execute("select count(*) from signal_stats").fetchone()[0]
    columns = [row[0] for row in signalled.execute("describe signal_stats").fetchall()]

    assert len(body) == count > 0
    assert all(set(row) == set(columns) for row in body)


def test_when_bars_then_weekly_and_monthly_columns_agree_with_period_bars(signalled):
    body = _body(signalled, "bars", "AAA")
    weekly = signalled.execute(
        "select count(*), max(high) from period_bars"
        " where ticker = 'AAA' and timeframe = 'w'"
    ).fetchone()

    assert len(body["weekly"]["day"]) == weekly[0]
    assert max(body["weekly"]["high"]) == weekly[1]
    assert body["weekly"]["day"] == sorted(body["weekly"]["day"])
    assert set(body["weekly"]) == {
        "day", "open", "high", "low", "close", "adj_close", "volume",
    }  # fmt: skip
    assert len(body["monthly"]["day"]) >= 3


def test_when_bars_then_pivots_and_signals_are_the_instruments_own(signalled):
    body = _body(signalled, "bars", "AAA")

    assert {row["timeframe"] for row in body["pivots"]} >= {"d"}
    assert set(body["pivots"][0]) == {
        "timeframe", "kind", "label", "day", "price", "confirmed",
    }  # fmt: skip
    assert {row["event"] for row in body["signals"]} >= {"break_up", "confirm_up"}
    assert set(body["signals"][0]) == {
        "id", "timeframe", "event", "direction", "day", "known", "level", "stop",
        "grade", "score", "return_to_date", "held_to_date",
    }  # fmt: skip
    assert all(row["id"].startswith("AAA|") for row in body["signals"])


def test_when_bars_has_no_structure_then_the_new_fields_are_empty(connection):
    body = _body(connection, "bars", "AAA")

    assert body["pivots"] == []
    assert body["signals"] == []
    assert body["weekly"]["day"] != []


def test_when_bars_for_an_unknown_ticker_then_weekly_and_monthly_are_empty(connection):
    body = _body(connection, "bars", "NOPE")

    assert body["weekly"]["day"] == body["monthly"]["day"] == []


@pytest.mark.parametrize(
    "name", ["latest", "overview", "runs", "bars", "slugs", "signals", "stats"]
)
def test_when_linted_then_each_query_follows_the_house_style(name):
    violations = lint(_read(name), config=FluffConfig.from_path(str(_ROOT)))

    assert violations == []
