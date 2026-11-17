import datetime

import duckdb
import polars
import pytest

from market_data.code import error, port, transform
from market_data.code.adapt import motherduck

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
        answered=tuple(tickers),
        bars=bars,
        fetched=_STARTED,
        rejected=rejected,
        universe=universe,
    )


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
    assert tables >= {"bars", "rejected", "runs", "schema_version", "tickers"}
    assert version == (1,)


def test_when_connect_twice_then_migrations_are_applied_once(database):
    motherduck.connect(database).close()

    connection = motherduck.connect(database)

    assert _count(connection, "schema_version") == 1


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
        answered=broken.answered,
        bars=broken.bars,
        fetched=broken.fetched,
        rejected=broken.rejected.drop("reason"),
        universe=broken.universe,
    )

    with pytest.raises(error.StoreError):
        store.replace(broken)

    assert store.connection.execute("select close from bars").fetchall() == [(10.0,)]


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
