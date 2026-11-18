import datetime

import polars

from market_data.code import operate, port, transform
from pytest_ import fake


def _bars(make_bars, *tickers):
    day = datetime.date(2026, 11, 16)
    return make_bars(*((ticker, day, {}) for ticker in tickers))


def _compute(bars, universe, clock, *, store=None, tolerance=0):
    store = store or fake.Ledger(bars=bars)
    run = operate.compute_metrics(
        bars=bars, now=clock, store=store, tolerance=tolerance, universe=universe
    )
    return run, store


def test_when_every_active_instrument_has_bars_then_metrics_are_stored(
    make_bars, small_universe, clock
):
    bars = _bars(make_bars, "AAA", "BBB", "^TNX")

    run, store = _compute(bars, small_universe, clock)

    assert run.outcome is transform.Outcome.STORED
    assert (run.source, run.requests, run.failed_items) == ("metrics", 0, 0)
    assert run.rows == store.metrics[0].height
    assert run.day == run.last_day == datetime.date(2026, 11, 16)
    assert store.runs == [run]


def test_when_an_active_instrument_has_no_bars_then_the_run_is_partial(
    make_bars, small_universe, clock
):
    run, store = _compute(_bars(make_bars, "AAA", "BBB"), small_universe, clock)

    assert (run.outcome, run.failed_items) == (transform.Outcome.PARTIAL, 1)
    assert store.metrics


def test_when_no_instrument_has_bars_then_nothing_is_replaced_and_the_run_failed(
    make_bars, small_universe, clock
):
    empty = polars.DataFrame(schema=port.BARS)

    run, store = _compute(empty, small_universe, clock)

    assert run.outcome is transform.Outcome.FAILED
    assert store.metrics == []
    assert store.runs == [run]


def test_when_the_paused_instrument_has_no_bars_then_it_is_not_a_failure(
    make_bars, small_universe, clock
):
    paused = small_universe.with_columns(active=polars.col("ticker").ne("BBB"))

    run, _ = _compute(_bars(make_bars, "AAA", "^TNX"), paused, clock)

    assert run.outcome is transform.Outcome.STORED


def test_when_metrics_are_stored_then_the_overview_has_a_row_per_instrument(
    make_bars, small_universe, clock
):
    bars = _bars(make_bars, "AAA", "BBB", "^TNX")
    ledger = fake.Ledger(bars=bars, tickers=small_universe)

    _compute(bars, small_universe, clock, store=ledger)

    overview = ledger.overviews[0]
    assert overview.get_column("ticker").to_list() == ["AAA", "BBB", "^TNX"]
    assert overview.get_column("slug").to_list() == ["aaa", "bbb", "tnx"]
