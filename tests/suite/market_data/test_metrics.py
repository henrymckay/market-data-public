import datetime
import math

import polars
import pytest

from market_data.code import transform

_LAST = datetime.date(2026, 11, 16)


def _daily(make_bars, ticker, count, *, last=_LAST, **overrides):
    """Bars for `count` consecutive days ending on `last`, adj_close 100, 101, ..."""
    return make_bars(
        *(
            (
                ticker,
                last - datetime.timedelta(days=count - 1 - index),
                {"adj_close": 100.0 + index, "close": 100.0 + index} | overrides,
            )
            for index in range(count)
        )
    )


def _value(metrics, ticker, metric):
    rows = metrics.filter(
        (polars.col("ticker") == ticker) & (polars.col("metric") == metric)
    )
    assert rows.height <= 1
    return rows.get_column("value").to_list()[0] if rows.height else None


@pytest.fixture
def rising(make_bars):
    return _daily(make_bars, "AAA", 400)


def test_when_build_metrics_then_every_figure_is_long_and_dated_by_the_last_bar(
    rising,
):
    metrics = transform.build_metrics(rising)

    assert metrics.columns == ["day", "metric", "ticker", "value"]
    assert set(metrics.get_column("day")) == {_LAST}
    assert metrics.filter(polars.col("value").is_null()).height == 0


@pytest.mark.parametrize(
    ("window", "start_value"),
    [
        ("1d", 498.0),
        ("1w", 492.0),
        ("1m", 468.0),
        ("3m", 407.0),
        ("ytd", 179.0),
        ("1y", 134.0),
    ],
)
def test_when_build_metrics_then_return_and_change_run_from_the_bar_at_the_start(
    rising, window, start_value
):
    metrics = transform.build_metrics(rising)

    assert _value(metrics, "AAA", f"return_{window}") == pytest.approx(
        499.0 / start_value - 1
    )
    assert _value(metrics, "AAA", f"change_{window}") == pytest.approx(
        499.0 - start_value
    )


def test_when_history_is_shorter_than_a_window_then_that_window_is_absent(rising):
    metrics = transform.build_metrics(rising)

    assert _value(metrics, "AAA", "return_3y") is None
    assert _value(metrics, "AAA", "change_5y") is None


def test_when_the_start_falls_on_a_weekend_then_the_last_bar_before_it_is_used(
    make_bars,
):
    friday, tuesday = datetime.date(2026, 11, 13), datetime.date(2026, 11, 17)
    bars = make_bars(
        ("AAA", friday, {"adj_close": 50.0}),
        ("AAA", tuesday, {"adj_close": 55.0}),
    )

    metrics = transform.build_metrics(bars)

    assert _value(metrics, "AAA", "return_1d") == pytest.approx(0.1)


def test_when_three_years_pass_then_the_return_is_annualised(make_bars):
    bars = make_bars(
        ("AAA", datetime.date(2023, 11, 16), {"adj_close": 100.0}),
        ("AAA", _LAST, {"adj_close": 200.0}),
    )

    metrics = transform.build_metrics(bars)

    assert _value(metrics, "AAA", "return_3y") == pytest.approx(2 ** (1 / 3) - 1)
    assert _value(metrics, "AAA", "change_3y") == pytest.approx(100.0)


def test_when_build_metrics_then_the_year_figures_follow_the_last_year_of_bars(
    make_bars,
):
    days = [_LAST - datetime.timedelta(days=offset) for offset in (3, 2, 1, 0)]
    closes = [100.0, 120.0, 90.0, 110.0]
    bars = make_bars(
        *(
            (
                "AAA",
                day,
                {
                    "adj_close": close,
                    "close": close,
                    "high": close + 5,
                    "low": close - 5,
                },
            )
            for day, close in zip(days, closes, strict=True)
        )
    )

    metrics = transform.build_metrics(bars)

    assert _value(metrics, "AAA", "high_52w") == 125.0
    assert _value(metrics, "AAA", "low_52w") == 85.0
    assert _value(metrics, "AAA", "last_close") == 110.0
    assert _value(metrics, "AAA", "drawdown_max_1y") == pytest.approx(90 / 120 - 1)
    returns = [120 / 100 - 1, 90 / 120 - 1, 110 / 90 - 1]
    mean = sum(returns) / 3
    spread = math.sqrt(sum((one - mean) ** 2 for one in returns) / 2)
    assert _value(metrics, "AAA", "volatility_1y") == pytest.approx(
        spread * math.sqrt(252)
    )


def test_when_build_metrics_then_traded_value_averages_the_last_twenty_bars(make_bars):
    bars = _daily(make_bars, "AAA", 30, volume=10)

    metrics = transform.build_metrics(bars)

    last_twenty_mean_close = sum(100.0 + index for index in range(10, 30)) / 20
    assert _value(metrics, "AAA", "traded_value_20d") == pytest.approx(
        last_twenty_mean_close * 10
    )


def test_when_volume_is_unknown_then_traded_value_is_absent(make_bars):
    bars = _daily(make_bars, "AAA", 30, volume=None)

    metrics = transform.build_metrics(bars)

    assert _value(metrics, "AAA", "traded_value_20d") is None
    assert _value(metrics, "AAA", "last_close") is not None


def test_when_two_instruments_then_each_is_measured_on_its_own_last_bar(make_bars):
    older = _LAST - datetime.timedelta(days=5)
    bars = polars.concat(
        [_daily(make_bars, "AAA", 10), _daily(make_bars, "BBB", 10, last=older)]
    )

    metrics = transform.build_metrics(bars)

    days = dict(
        metrics.filter(polars.col("metric") == "last_close")
        .select("ticker", "day")
        .iter_rows()
    )
    assert days == {"AAA": _LAST, "BBB": older}


def test_when_there_are_no_bars_then_there_are_no_metrics(make_bars):
    metrics = transform.build_metrics(make_bars())

    assert metrics.height == 0
    assert metrics.columns == ["day", "metric", "ticker", "value"]
