import datetime

import polars

from market_data.code import operate, port, transform
from pytest_ import fake


def _fetch(tickers, bars, *failed, clock, sink, universe):
    return operate.fetch_bars(
        tickers,
        fetch=fake.fetching(bars, *failed, requests=len(tickers)),
        now=clock,
        sink=sink,
        tolerance=0,
        universe=universe,
    )


def test_when_fetch_bars_then_complete_valid_bars_are_stored_and_run_is_stored(
    make_bars, small_universe, clock
):
    sink = fake.Sink()
    day = datetime.date(2026, 11, 16)
    bars = make_bars(
        ("AAA", day, {}),
        ("AAA", datetime.date(2026, 11, 17), {}),
        ("BBB", day, {}),
    )

    run = _fetch(["AAA", "BBB"], bars, clock=clock, sink=sink, universe=small_universe)

    assert sink.loads[0].bars.height == 2
    assert (run.outcome, run.rows, run.day, run.last_day, run.requests) == (
        transform.Outcome.STORED,
        2,
        day,
        day,
        2,
    )
    assert sink.runs == [run]


def test_when_an_instrument_fails_then_run_is_partial_and_others_store(
    make_bars, small_universe, clock
):
    sink = fake.Sink()
    bars = make_bars(("AAA", datetime.date(2026, 11, 16), {}))

    run = _fetch(
        ["AAA", "BBB"],
        bars,
        port.Failure(reason="no data", ticker="BBB"),
        clock=clock,
        sink=sink,
        universe=small_universe,
    )

    assert sink.loads[0].answered == ("AAA",)
    assert (run.outcome, run.failed_items) == (transform.Outcome.PARTIAL, 1)


def test_when_no_bar_of_an_instrument_validates_then_its_rows_are_kept(
    make_bars, small_universe, clock
):
    sink = fake.Sink()
    day = datetime.date(2026, 11, 16)
    bars = make_bars(("AAA", day, {}), ("BBB", day, {"close": None}))

    run = _fetch(["AAA", "BBB"], bars, clock=clock, sink=sink, universe=small_universe)

    load = sink.loads[0]
    assert load.answered == ("AAA",)
    assert load.rejected.height == 0
    assert (run.outcome, run.failed_items) == (transform.Outcome.PARTIAL, 1)


def test_when_every_instrument_fails_then_nothing_is_replaced_and_run_failed(
    small_universe, clock
):
    sink = fake.Sink()
    nothing = polars.DataFrame(schema=port.BARS)

    run = _fetch(["AAA"], nothing, clock=clock, sink=sink, universe=small_universe)

    assert sink.loads == []
    assert (run.outcome, run.rows) == (transform.Outcome.FAILED, 0)
    assert sink.runs == [run]


def test_when_a_stored_instrument_has_a_bad_bar_then_it_is_quarantined(
    make_bars, small_universe, clock
):
    sink = fake.Sink()
    day = datetime.date(2026, 11, 16)
    bars = make_bars(
        ("AAA", day, {}), ("AAA", datetime.date(2026, 11, 13), {"high": 1.0})
    )

    run = _fetch(["AAA"], bars, clock=clock, sink=sink, universe=small_universe)

    assert (run.outcome, run.rows, run.rejected) == (transform.Outcome.STORED, 1, 1)
