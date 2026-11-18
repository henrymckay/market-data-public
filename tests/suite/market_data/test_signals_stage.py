import datetime

import polars
import pytest

from market_data.code import operate, transform
from pytest_ import fake, series


@pytest.fixture
def ledger(universe_frame):
    bars = series.daily_frame("AAA", series.DOWNTREND)
    return fake.SignalsLedger(periods=series.periods_of(bars), tickers=universe_frame)


@pytest.fixture
def bars():
    return series.daily_frame("AAA", series.DOWNTREND)


def _clock():
    ticks = iter(
        datetime.datetime(2030, 1, 1, 2, 17, tzinfo=datetime.UTC)
        + datetime.timedelta(minutes=minute)
        for minute in range(10)
    )
    return lambda: next(ticks)


def test_when_the_stage_runs_then_the_tables_are_replaced_and_the_run_counts_signals(
    bars, ledger, rules
):
    run = operate.compute_signals(bars=bars, now=_clock(), rules=rules, store=ledger)

    [computed] = ledger.replaced
    assert run.outcome is transform.Outcome.STORED
    assert (run.source, run.requests, run.failed_items) == ("signals", 0, 0)
    assert run.rows == computed.signals.height == 1
    assert ledger.runs == [run]
    assert run.day == run.last_day == bars.get_column("day").max()


def test_when_the_store_has_no_bars_then_nothing_is_replaced_and_the_run_failed(
    ledger, rules
):
    empty = series.daily_frame("AAA", series.DOWNTREND).head(0)

    run = operate.compute_signals(bars=empty, now=_clock(), rules=rules, store=ledger)

    assert run.outcome is transform.Outcome.FAILED
    assert ledger.replaced == []
    assert ledger.runs == [run]


def test_when_the_replace_fails_then_a_failed_run_is_recorded_and_nothing_raised(
    bars, ledger, rules, caplog
):
    ledger.failing = True

    run = operate.compute_signals(bars=bars, now=_clock(), rules=rules, store=ledger)

    assert (run.outcome, run.rows) == (transform.Outcome.FAILED, 0)
    assert ledger.runs == [run]
    assert "signals stage failed" in caplog.text


def test_when_signals_are_only_found_then_nothing_is_written(bars, ledger, rules):
    computed = operate.find_signals(bars=bars, now=_clock(), rules=rules, store=ledger)

    assert computed.signals.height == 1
    assert (ledger.replaced, ledger.runs) == ([], [])


def test_when_one_threshold_changes_then_the_hash_and_the_signals_change(
    bars, ledger, rules
):
    looser = rules.model_copy(
        update={"swing_atr": transform.PerTimeframe(d=4.0, m=2.0, w=2.0)}
    )

    first = operate.find_signals(bars=bars, now=_clock(), rules=rules, store=ledger)
    second = operate.find_signals(bars=bars, now=_clock(), rules=looser, store=ledger)

    assert transform.hash_rules(rules) != transform.hash_rules(looser)
    assert first.signals.get_column("rules").unique().to_list() == [
        transform.hash_rules(rules)
    ]
    assert (first.signals.height, second.signals.height) == (1, 0)


def test_when_the_overview_is_built_then_it_carries_the_structure_per_timeframe(
    small_universe,
):
    structure = polars.DataFrame(
        {
            "state": ["up", "down", "turning_up"],
            "ticker": ["AAA", "AAA", "BBB"],
            "timeframe": ["d", "m", "w"],
        }
    )
    bars = series.daily_frame("AAA", series.DOWNTREND)

    overview = transform.build_overview(
        bars=bars,
        metrics=transform.build_metrics(bars),
        rejected=polars.DataFrame(
            schema={"ticker": polars.String, "rejected": polars.Int64}
        ),
        structure=structure,
        tickers=small_universe,
    )

    rows = {row["ticker"]: row for row in overview.to_dicts()}
    assert (rows["AAA"]["trend_d"], rows["AAA"]["trend_w"], rows["AAA"]["trend_m"]) == (
        "up",
        None,
        "down",
    )
    assert rows["BBB"]["trend_w"] == "turning_up"
    assert rows["^TNX"]["trend_d"] is None
