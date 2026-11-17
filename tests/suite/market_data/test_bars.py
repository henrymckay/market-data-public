import datetime

import polars
import pytest

from market_data.code import transform
from pytest_ import then


def test_when_keep_complete_then_bars_from_today_on_are_dropped(make_bars, monday):
    bars = make_bars(
        ("AAA", monday - datetime.timedelta(days=1), {}),
        ("AAA", monday, {}),
        ("AAA", monday + datetime.timedelta(days=1), {}),
    )

    kept = transform.keep_complete(bars, today=monday)

    assert kept.get_column("day").to_list() == [monday - datetime.timedelta(days=1)]


@pytest.mark.parametrize(
    ("ticker", "changes", "reason"),
    [
        ("AAA", {"close": None}, "null or non-finite close"),
        ("AAA", {"close": float("inf")}, "null or non-finite close"),
        ("AAA", {"adj_close": None}, "null or non-finite adjusted close"),
        ("AAA", {"close": 0.0}, "non-positive price"),
        ("AAA", {"low": -1.0}, "non-positive price"),
        ("AAA", {"high": 8.0}, "high below low"),
    ],
)
def test_when_validate_bars_then_each_bad_bar_is_rejected_with_its_reason(
    make_bars, small_universe, monday, ticker, changes, reason
):
    bars = make_bars((ticker, monday, changes))

    valid, rejected = transform.validate_bars(bars, universe=small_universe)

    assert valid.height == 0
    assert rejected.get_column("reason").to_list() == [reason]


def test_when_validate_bars_then_a_yield_may_be_zero_or_negative(
    make_bars, small_universe, monday
):
    bars = make_bars(("^TNX", monday, {"close": -0.1, "adj_close": -0.1, "low": -0.2}))

    valid, rejected = transform.validate_bars(bars, universe=small_universe)

    assert (valid.height, rejected.height) == (1, 0)


def test_when_validate_bars_then_a_missing_high_and_low_still_validate(
    make_bars, small_universe, monday
):
    bars = make_bars(("AAA", monday, {"high": None, "low": None, "open": None}))

    valid, _ = transform.validate_bars(bars, universe=small_universe)

    assert valid.height == 1


def test_when_validate_bars_then_a_duplicate_day_keeps_the_first(
    make_bars, small_universe, monday
):
    bars = make_bars(
        ("AAA", monday, {"close": 10.0}),
        ("AAA", monday, {"close": 11.0}),
        ("BBB", monday, {"close": 12.0}),
    )

    valid, rejected = transform.validate_bars(bars, universe=small_universe)

    assert valid.sort("ticker").get_column("close").to_list() == [10.0, 12.0]
    assert rejected.get_column("reason").to_list() == ["duplicate day"]


def test_when_validate_bars_then_rows_are_conserved_and_record_is_json(
    make_bars, small_universe, monday
):
    bars = make_bars(
        ("AAA", monday, {}),
        ("AAA", monday - datetime.timedelta(days=1), {"close": None}),
        ("BBB", monday, {"close": 0.0}),
    )

    valid, rejected = transform.validate_bars(bars, universe=small_universe)

    then.conserves(kept=valid, rejected=rejected, sent=bars.height)
    assert polars.Series(rejected.get_column("record")).str.contains('"ticker"').all()
