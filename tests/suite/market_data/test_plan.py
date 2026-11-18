import datetime

import polars
import pytest

from market_data.code import port, transform

_TODAY = datetime.date(2026, 11, 17)


def _last_days(**days):
    return polars.DataFrame(
        {"day": list(days.values()), "ticker": list(days)}, schema=port.LAST_DAYS
    )


def _periods(plan):
    return dict(plan.select("ticker", "period").iter_rows())


def test_when_plan_fetch_then_a_stored_recent_instrument_gets_a_month():
    plan = transform.plan_fetch(
        ["AAA"],
        full=False,
        last_days=_last_days(AAA=datetime.date(2026, 11, 16)),
        today=_TODAY,
    )

    assert _periods(plan) == {"AAA": "1mo"}


def test_when_plan_fetch_then_an_instrument_with_no_bars_gets_its_whole_history():
    plan = transform.plan_fetch(
        ["AAA", "NEW"],
        full=False,
        last_days=_last_days(AAA=datetime.date(2026, 11, 16)),
        today=_TODAY,
    )

    assert _periods(plan) == {"AAA": "1mo", "NEW": "max"}


@pytest.mark.parametrize(
    ("last", "period"),
    [
        (datetime.date(2026, 10, 23), "1mo"),
        (datetime.date(2026, 10, 22), "max"),
    ],
)
def test_when_plan_fetch_then_a_last_day_over_25_days_old_gets_the_whole_history(
    last, period
):
    plan = transform.plan_fetch(
        ["AAA"], full=False, last_days=_last_days(AAA=last), today=_TODAY
    )

    assert _periods(plan) == {"AAA": period}


def test_when_plan_fetch_is_full_then_every_instrument_gets_the_whole_history():
    plan = transform.plan_fetch(
        ["AAA", "BBB"],
        full=True,
        last_days=_last_days(AAA=datetime.date(2026, 11, 16)),
        today=_TODAY,
    )

    assert set(_periods(plan).values()) == {"max"}


def _month(make_bars, **changes):
    return make_bars(
        ("AAA", datetime.date(2026, 11, 13), changes),
        ("AAA", datetime.date(2026, 11, 16), {}),
        ("BBB", datetime.date(2026, 11, 16), {}),
    )


def _overlap(make_bars):
    return _month(make_bars).select(port.OVERLAP.names())


def test_when_the_month_matches_the_store_then_no_instrument_disagrees(make_bars):
    found = transform.find_disagreements(
        fetched=_month(make_bars), stored=_overlap(make_bars)
    )

    assert found == []


@pytest.mark.parametrize("field", ["close", "adj_close"])
def test_when_a_price_moves_by_more_than_a_millionth_then_that_instrument_disagrees(
    make_bars, field
):
    fetched = _month(make_bars, **{field: 10.0 * (1 + 2e-6)})

    found = transform.find_disagreements(fetched=fetched, stored=_overlap(make_bars))

    assert found == ["AAA"]


def test_when_a_price_moves_by_less_than_a_millionth_then_none_disagrees(make_bars):
    fetched = _month(make_bars, close=10.0 * (1 + 5e-8))

    found = transform.find_disagreements(fetched=fetched, stored=_overlap(make_bars))

    assert found == []


@pytest.mark.parametrize("field", ["dividend", "split"])
def test_when_an_action_is_missing_from_the_store_then_that_instrument_disagrees(
    make_bars, field
):
    fetched = _month(make_bars, **{field: 0.5})

    found = transform.find_disagreements(fetched=fetched, stored=_overlap(make_bars))

    assert found == ["AAA"]


def test_when_a_fetched_day_is_new_without_an_action_then_none_disagrees(make_bars):
    stored = _overlap(make_bars).filter(
        polars.col("day").lt(datetime.date(2026, 11, 16))
    )

    found = transform.find_disagreements(fetched=_month(make_bars), stored=stored)

    assert found == []


def test_when_build_since_then_a_month_instrument_starts_at_its_first_fetched_day(
    make_bars,
):
    since = transform.build_since(
        ["AAA", "BBB"], recent=_month(make_bars), whole=["BBB"]
    )

    assert since.sort("ticker").rows() == [
        ("AAA", datetime.date(2026, 11, 13)),
        ("BBB", None),
    ]
