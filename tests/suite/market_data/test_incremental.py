import datetime

import polars
import pytest

from market_data.code import operate, port
from market_data.code.adapt import motherduck
from pytest_ import fake

_LAST = datetime.date(2026, 11, 16)
_TICKERS = ["AAA", "BBB"]


@pytest.fixture
def histories(make_bars):
    days = [_LAST - datetime.timedelta(days=offset) for offset in range(59, -1, -1)]
    return make_bars(
        *(
            (ticker, day, {"close": 10.0 + index, "adj_close": 10.0 + index})
            for ticker in _TICKERS
            for index, day in enumerate(days)
        )
    )


@pytest.fixture
def store(tmp_path):
    return motherduck.Store(motherduck.connect(str(tmp_path / "market.duckdb")))


def _run(store, source, universe, clock, *, full=False):
    return operate.fetch_bars(
        _TICKERS,
        fetch=source,
        full=full,
        now=clock,
        sink=store,
        tolerance=0,
        universe=universe,
    )


def _stored(store):
    return store.connection.execute(
        "select ticker, day, close, adj_close, dividend from bars order by ticker, day"
    ).fetchall()


def test_when_the_store_is_empty_then_every_instrument_is_asked_for_max(
    store, histories, small_universe, clock
):
    source = fake.Source(histories)

    _run(store, source, small_universe, clock)

    assert source.calls == [(("AAA", "BBB"), "max")]
    assert len(_stored(store)) == histories.height


def test_when_the_run_repeats_then_only_a_month_is_asked_for_and_the_rows_are_the_same(
    store, histories, small_universe, clock
):
    source = fake.Source(histories)
    _run(store, source, small_universe, clock)
    first = _stored(store)

    _run(store, source, small_universe, clock)

    assert source.calls[1:] == [(("AAA", "BBB"), "1mo")]
    assert _stored(store) == first


def test_when_a_dividend_lands_in_the_overlap_then_only_that_one_is_asked_for_max(
    store, histories, small_universe, clock
):
    _run(store, fake.Source(histories), small_universe, clock)
    restated = histories.with_columns(
        polars.when(polars.col("ticker").eq("BBB") & polars.col("day").eq(_LAST))
        .then(0.5)
        .otherwise(polars.col("dividend"))
        .alias("dividend")
    )
    source = fake.Source(restated)

    _run(store, source, small_universe, clock)

    assert source.calls == [(("AAA", "BBB"), "1mo"), (("BBB",), "max")]
    assert store.connection.execute(
        "select count(*) from bars where dividend = 0.5"
    ).fetchone() == (1,)


def test_when_a_close_is_restated_in_the_overlap_then_the_whole_history_replaces_it(
    store, histories, small_universe, clock
):
    _run(store, fake.Source(histories), small_universe, clock)
    older = _LAST - datetime.timedelta(days=50)
    restated = histories.with_columns(
        polars.when(polars.col("ticker").eq("AAA"))
        .then(polars.col("adj_close").mul(0.9))
        .otherwise(polars.col("adj_close"))
        .alias("adj_close")
    )

    _run(store, fake.Source(restated), small_universe, clock)

    row = store.connection.execute(
        "select adj_close from bars where ticker = 'AAA' and day = ?", [older]
    ).fetchone()
    assert row is not None
    assert row[0] == pytest.approx(
        restated.filter(
            polars.col("ticker").eq("AAA"), polars.col("day").eq(older)
        ).item(0, "adj_close")
    )


def test_when_the_run_is_full_then_every_instrument_is_asked_for_max(
    store, histories, small_universe, clock
):
    _run(store, fake.Source(histories), small_universe, clock)
    source = fake.Source(histories)

    _run(store, source, small_universe, clock, full=True)

    assert source.calls == [(("AAA", "BBB"), "max")]


def test_when_a_month_is_fetched_then_older_stored_rows_are_kept(
    store, histories, small_universe, clock
):
    _run(store, fake.Source(histories), small_universe, clock)
    source = fake.Source(
        histories.filter(polars.col("day").gt(_LAST - datetime.timedelta(days=35)))
    )

    _run(store, source, small_universe, clock)

    assert len(_stored(store)) == histories.height


def test_when_a_fake_source_is_asked_then_it_answers_a_port_fetched(histories):
    assert isinstance(fake.Source(histories)(["AAA"], "1mo"), port.Fetched)
