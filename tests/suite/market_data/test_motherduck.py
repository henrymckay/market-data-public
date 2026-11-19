import datetime

import duckdb
import polars
import pytest

from market_data.code import error, port, transform
from market_data.code.adapt import motherduck
from pytest_ import fake

_DAY = datetime.date(2026, 11, 16)
_STARTED = datetime.datetime(2026, 11, 17, 2, 17, tzinfo=datetime.UTC)


@pytest.fixture
def database(tmp_path):
    return str(tmp_path / "market.duckdb")


def _load(make_bars, universe, tickers, *, close=10.0, rejected_for=()):
    bars = make_bars(*((ticker, _DAY, {"close": close}) for ticker in tickers))
    rejected = polars.DataFrame(
        [
            {"day": _DAY, "reason": "high below low", "record": "{}", "ticker": ticker}
            for ticker in rejected_for
        ],
        schema=port.REJECTED,
    )
    return port.Load(
        since=fake.whole(tickers),
        bars=bars,
        fetched=_STARTED,
        rejected=rejected,
        universe=universe,
    )


_OVERVIEW_SCHEMA = {"ticker": polars.String, "bar_count": polars.Int64}


def _count(connection, table):
    return connection.execute(f"select count(*) from {table}").fetchone()[0]


def _run(outcome=transform.Outcome.STORED):
    return transform.Run(
        day=_DAY,
        ended=_STARTED + datetime.timedelta(minutes=2),
        failed_items=0,
        last_day=_DAY,
        outcome=outcome,
        rejected=0,
        requests=2,
        rows=2,
        source="yahoo",
        started=_STARTED,
    )


def test_when_connect_then_migrations_create_the_tables_and_record_the_version(
    database,
):
    connection = motherduck.connect(database)

    tables = {row[0] for row in connection.execute("show tables").fetchall()}
    version = connection.execute("select max(version) from schema_version").fetchone()
    assert tables >= {
        "alert_state",
        "alerts",
        "bars",
        "metrics",
        "overview",
        "rejected",
        "runs",
        "schema_version",
        "tickers",
    }
    assert version == (6,)


def test_when_connect_twice_then_migrations_are_applied_once(database):
    motherduck.connect(database).close()

    connection = motherduck.connect(database)

    assert _count(connection, "schema_version") == 6


def test_when_replace_twice_then_the_same_rows_remain(
    database, make_bars, small_universe
):
    store = motherduck.Store(motherduck.connect(database))
    load = _load(make_bars, small_universe, ["AAA", "BBB"], rejected_for=["AAA"])

    store.replace(load)
    first = (_count(store.connection, "bars"), _count(store.connection, "rejected"))
    store.replace(load)

    assert first == (2, 1)
    assert (
        _count(store.connection, "bars"),
        _count(store.connection, "rejected"),
    ) == first
    assert _count(store.connection, "tickers") == 3


def test_when_replace_for_some_tickers_then_the_others_keep_their_rows(
    database, make_bars, small_universe
):
    store = motherduck.Store(motherduck.connect(database))
    store.replace(_load(make_bars, small_universe, ["AAA", "BBB"], close=10.0))

    store.replace(_load(make_bars, small_universe, ["AAA"], close=20.0))

    rows = store.connection.execute(
        "select ticker, close from bars order by ticker"
    ).fetchall()
    assert rows == [("AAA", 20.0), ("BBB", 10.0)]


def test_when_replace_fails_then_it_rolls_back_and_raises_store_error(
    database, make_bars, small_universe
):
    store = motherduck.Store(motherduck.connect(database))
    store.replace(_load(make_bars, small_universe, ["AAA"], close=10.0))
    broken = _load(make_bars, small_universe, ["AAA"], close=20.0)
    broken = port.Load(
        since=broken.since,
        bars=broken.bars,
        fetched=broken.fetched,
        rejected=broken.rejected.drop("reason"),
        universe=broken.universe,
    )

    with pytest.raises(error.StoreError):
        store.replace(broken)

    assert store.connection.execute("select close from bars").fetchall() == [(10.0,)]


@pytest.mark.parametrize(
    "call",
    [
        lambda store: store.read_tickers(),
        lambda store: store.read_period_bars(),
        lambda store: store.read_sent(),
        lambda store: store.append_run(_run()),
    ],
    ids=["read_tickers", "read_period_bars", "read_sent", "append_run"],
)
def test_when_the_connection_is_lost_then_a_store_call_raises_store_error(
    database, call
):
    connection = motherduck.connect(database)
    store = motherduck.Store(connection=connection)
    connection.close()

    with pytest.raises(error.StoreError):
        call(store)


def test_when_append_run_then_the_manifest_row_reads_back(database):
    store = motherduck.Store(motherduck.connect(database))

    store.append_run(_run(transform.Outcome.PARTIAL))

    row = store.connection.execute(
        "select day, outcome, requests, rows, source, started from runs"
    ).fetchone()
    assert row == (_DAY, "partial", 2, 2, "yahoo", _STARTED)


def test_when_the_database_name_is_not_an_identifier_then_configuration_error():
    with pytest.raises(error.ConfigurationError):
        motherduck.connect('md:x"; drop database y; --')


def test_when_connect_cannot_authenticate_then_the_message_hides_the_failure(
    monkeypatch,
):
    secret = "the-secret-value"

    def refuse(*_args):
        raise duckdb.InvalidInputException(f"not authenticated {secret}")

    monkeypatch.setattr(motherduck.duckdb, "connect", refuse)

    with pytest.raises(error.ConfigurationError) as raised:
        motherduck.connect("md:market_data")

    assert str(raised.value) == "MotherDuck refused the token"
    assert secret not in repr(raised.value)
    assert raised.value.__cause__ is None


def test_when_replace_metrics_twice_then_the_table_holds_the_latest_rows(database):
    store = motherduck.Store(motherduck.connect(database))
    schema = {
        "day": polars.Date,
        "metric": polars.String,
        "ticker": polars.String,
        "value": polars.Float64,
    }
    first = polars.DataFrame(
        {
            "day": [_DAY] * 2,
            "metric": ["a", "b"],
            "ticker": ["AAA"] * 2,
            "value": [1.0, 2.0],
        },
        schema=schema,
    )
    second = polars.DataFrame(
        {"day": [_DAY], "metric": ["a"], "ticker": ["BBB"], "value": [3.0]},
        schema=schema,
    )

    empty = polars.DataFrame(schema=_OVERVIEW_SCHEMA)
    store.replace_metrics(first, empty)
    store.replace_metrics(second, empty)

    rows = store.connection.execute(
        "select ticker, metric, value from metrics"
    ).fetchall()
    assert rows == [("BBB", "a", 3.0)]


def test_when_read_bars_then_what_replace_stored_comes_back(
    database, make_bars, small_universe
):
    store = motherduck.Store(motherduck.connect(database))
    store.replace(_load(make_bars, small_universe, ["AAA", "BBB"]))

    bars = store.read_bars()

    assert bars.height == 2
    assert bars.schema["day"] == polars.Date
    assert set(bars.columns) == {
        "adj_close",
        "close",
        "day",
        "high",
        "low",
        "ticker",
        "volume",
    }


def test_when_read_missing_then_active_instruments_without_bars_are_named(
    database, make_bars, small_universe
):
    store = motherduck.Store(motherduck.connect(database))
    store.replace(_load(make_bars, small_universe, ["AAA"]))

    assert store.read_missing() == ("BBB", "^TNX")


def test_when_read_runs_in_another_zone_then_times_come_back_in_utc(database):
    store = motherduck.Store(motherduck.connect(database))
    store.append_run(_run())
    store.connection.execute("set timezone = 'Asia/Dubai'")

    runs = store.read_runs()

    assert runs.schema["ended"] == polars.Datetime("us", "UTC")
    assert runs.row(0, named=True)["ended"].hour == _STARTED.hour
    assert runs.row(0, named=True)["ended"].minute == _STARTED.minute + 2


def test_when_replace_metrics_then_the_overview_table_takes_the_cores_columns(
    database, make_bars, small_universe
):
    store = motherduck.Store(motherduck.connect(database))
    bars = make_bars(("AAA", _DAY, {}), ("BBB", _DAY, {}))
    store.replace(_load(make_bars, small_universe, ["AAA", "BBB"]))
    metrics = transform.build_metrics(bars)
    overview = transform.build_overview(
        bars=bars,
        metrics=metrics,
        rejected=store.read_rejected_counts(),
        structure=store.read_structure(),
        tickers=store.read_tickers(),
    )

    store.replace_metrics(metrics, overview)
    store.replace_metrics(metrics, overview)

    stored = store.connection.execute("select * from overview order by ticker").pl()
    assert sorted(stored.columns) == sorted(overview.columns)
    assert (
        stored.get_column("ticker").to_list() == overview.get_column("ticker").to_list()
    )
    assert (
        stored.get_column("spark").to_list() == overview.get_column("spark").to_list()
    )


def _bars_of(store, ticker):
    return store.connection.execute(
        "select day from bars where ticker = ? order by day", [ticker]
    ).fetchall()


def test_when_replace_has_a_since_day_then_only_rows_from_it_on_are_replaced(
    database, make_bars, small_universe
):
    store = motherduck.Store(motherduck.connect(database))
    days = [_DAY - datetime.timedelta(days=offset) for offset in (2, 1, 0)]
    old = make_bars(*(("AAA", day, {"close": 10.0}) for day in days))
    store.replace(
        port.Load(
            since=fake.whole(["AAA"]),
            bars=old,
            fetched=_STARTED,
            rejected=polars.DataFrame(schema=port.REJECTED),
            universe=small_universe,
        )
    )
    new = make_bars(*(("AAA", day, {"close": 20.0}) for day in days[1:]))

    store.replace(
        port.Load(
            since=polars.DataFrame(
                {"since": [days[1]], "ticker": ["AAA"]}, schema=port.SINCE
            ),
            bars=new,
            fetched=_STARTED,
            rejected=polars.DataFrame(schema=port.REJECTED),
            universe=small_universe,
        )
    )

    closes = store.connection.execute(
        "select close from bars where ticker = 'AAA' order by day"
    ).fetchall()
    assert closes == [(10.0,), (20.0,), (20.0,)]


def test_when_replace_has_a_null_since_then_every_row_of_the_ticker_is_replaced(
    database, make_bars, small_universe
):
    store = motherduck.Store(motherduck.connect(database))
    store.replace(_load(make_bars, small_universe, ["AAA", "BBB"], close=10.0))
    shorter = _load(make_bars, small_universe, ["AAA"], close=20.0)
    longer_before = make_bars(("AAA", _DAY - datetime.timedelta(days=1), {}))
    store.replace(
        port.Load(
            since=shorter.since,
            bars=polars.concat([longer_before, shorter.bars]),
            fetched=_STARTED,
            rejected=shorter.rejected,
            universe=small_universe,
        )
    )
    store.replace(shorter)

    assert _bars_of(store, "AAA") == [(_DAY,)]
    assert _bars_of(store, "BBB") == [(_DAY,)]


def test_when_the_store_is_read_then_last_days_and_the_overlap_come_back(
    database, make_bars, small_universe
):
    store = motherduck.Store(motherduck.connect(database))
    store.replace(_load(make_bars, small_universe, ["AAA", "BBB"]))

    last_days = store.read_last_days()
    overlap = store.read_overlap(["AAA"], _DAY)

    assert last_days.schema == port.LAST_DAYS
    assert last_days.sort("ticker").rows() == [(_DAY, "AAA"), (_DAY, "BBB")]
    assert overlap.schema == port.OVERLAP
    assert overlap.get_column("ticker").to_list() == ["AAA"]


def test_when_the_store_is_used_then_its_meter_adds_the_seconds_spent_inside_calls(
    database, make_bars, small_universe
):
    store = motherduck.Store(motherduck.connect(database))

    store.replace(_load(make_bars, small_universe, ["AAA"]))

    assert store.meter.seconds > 0


def test_when_a_database_at_version_3_is_connected_then_featured_and_source_are_added(
    database,
):
    connection = duckdb.connect(database)
    connection.execute("create table schema_version (version integer)")
    for name in (
        "0001_create_tables.sql",
        "0002_create_metrics.sql",
        "0003_create_overview.sql",
    ):
        from importlib import resources

        connection.execute(
            resources.files("market_data")
            .joinpath(f"data/adapt/migrations/{name}")
            .read_text()
        )
        connection.execute("insert into schema_version values (?)", [int(name[:4])])
    connection.execute("insert into tickers (ticker, active) values ('AAA', true)")
    connection.close()

    migrated = motherduck.connect(database)

    row = migrated.execute("select featured, source from tickers").fetchone()
    assert row == (None, None)
    columns = {r[0] for r in migrated.execute("describe overview").fetchall()}
    assert {"featured", "source"} <= columns


def _stored_bars(store, make_bars, small_universe, rows):
    bars = make_bars(*rows)
    store.replace(
        port.Load(
            since=fake.whole(sorted({row[0] for row in rows})),
            bars=bars,
            fetched=_STARTED,
            rejected=polars.DataFrame(schema=port.REJECTED),
            universe=small_universe,
        )
    )


def test_when_period_bars_is_read_then_weeks_and_months_are_grouped_from_the_days(
    database, make_bars, small_universe
):
    store = motherduck.Store(motherduck.connect(database))
    thursday = datetime.date(2026, 10, 29)
    days = [thursday + datetime.timedelta(days=offset) for offset in (0, 1, 4, 5)]
    rows = [
        (
            "AAA",
            day,
            {
                "adj_close": 20.0 + index,
                "close": 10.0 + index,
                "high": 11.0 + index,
                "low": 9.0 - index,
                "open": 5.0 + index,
                "volume": 100 + index if index != 3 else None,
            },
        )
        for index, day in enumerate(days)
    ]
    _stored_bars(store, make_bars, small_universe, rows)

    periods = store.read_period_bars().sort("timeframe", "day")

    assert periods.select("timeframe", "day", "last_day").rows() == [
        ("m", datetime.date(2026, 10, 1), datetime.date(2026, 10, 30)),
        ("m", datetime.date(2026, 11, 1), datetime.date(2026, 11, 3)),
        ("w", datetime.date(2026, 10, 26), datetime.date(2026, 10, 30)),
        ("w", datetime.date(2026, 11, 2), datetime.date(2026, 11, 3)),
    ]
    october = periods.filter(
        polars.col("timeframe").eq("w"),
        polars.col("day").eq(datetime.date(2026, 10, 26)),
    ).row(0, named=True)
    assert october == {
        "adj_close": 21.0,
        "close": 11.0,
        "day": datetime.date(2026, 10, 26),
        "high": 12.0,
        "last_day": datetime.date(2026, 10, 30),
        "low": 8.0,
        "open": 5.0,
        "ticker": "AAA",
        "timeframe": "w",
        "volume": 201,
    }


def test_when_every_volume_of_a_period_is_null_then_its_volume_is_null(
    database, make_bars, small_universe
):
    store = motherduck.Store(motherduck.connect(database))
    _stored_bars(store, make_bars, small_universe, [("AAA", _DAY, {"volume": None})])

    periods = store.read_period_bars()

    assert periods.get_column("volume").to_list() == [None, None]
    assert periods.schema["volume"] == polars.Int64


def _computed(rules, universe_frame):
    from pytest_ import series

    bars = series.daily_frame("AAA", series.DOWNTREND)
    return transform.build_signals(
        bars=bars,
        periods=series.periods_of(bars),
        rules=rules,
        rules_id="abc",
        tickers=universe_frame,
        today=datetime.date(2030, 1, 1),
    )


def test_when_signals_are_replaced_twice_then_each_table_holds_the_last_rows_only(
    database, rules, universe_frame
):
    store = motherduck.Store(motherduck.connect(database))
    computed = _computed(rules, universe_frame)

    store.replace_signals(computed)
    store.replace_signals(computed)

    assert {
        table: _count(store.connection, table)
        for table in ("pivots", "signals", "outcomes", "signal_stats", "structure")
    } == {
        "pivots": computed.pivots.height,
        "signals": 1,
        "outcomes": 0,
        "signal_stats": 0,
        "structure": computed.structure.height,
    }
    assert store.read_structure().height == computed.structure.height


def test_when_a_signals_load_fails_then_every_table_keeps_its_old_rows(
    database, rules, universe_frame
):
    store = motherduck.Store(motherduck.connect(database))
    computed = _computed(rules, universe_frame)
    store.replace_signals(computed)
    broken = transform.Computed(
        outcomes=computed.outcomes,
        pivots=computed.pivots.with_columns(price=polars.lit("not a price")),
        signal_stats=computed.signal_stats,
        signals=computed.signals.head(0),
        structure=computed.structure,
    )

    with pytest.raises(error.StoreError):
        store.replace_signals(broken)

    assert _count(store.connection, "signals") == 1


def test_when_signals_are_stored_then_the_tables_take_the_cores_columns_in_order(
    database, rules, universe_frame
):
    store = motherduck.Store(motherduck.connect(database))
    computed = _computed(rules, universe_frame)

    for table, frame in (
        ("pivots", computed.pivots),
        ("signals", computed.signals),
        ("outcomes", computed.outcomes),
        ("signal_stats", computed.signal_stats),
        ("structure", computed.structure),
    ):
        columns = [
            row[0] for row in store.connection.execute(f"describe {table}").fetchall()
        ]
        assert columns == frame.columns
