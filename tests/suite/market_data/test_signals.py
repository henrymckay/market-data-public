import datetime

import numpy
import polars
import pytest

from market_data.code import transform
from market_data.code.transform import outcomes, score
from pytest_ import series

_EMPTY_PERIODS = polars.DataFrame(
    schema={
        "adj_close": polars.Float64,
        "close": polars.Float64,
        "day": polars.Date,
        "high": polars.Float64,
        "last_day": polars.Date,
        "low": polars.Float64,
        "open": polars.Float64,
        "ticker": polars.String,
        "timeframe": polars.String,
        "volume": polars.Int64,
    }
)
_TODAY = datetime.date(2030, 1, 1)


def _run(rules, universe, bars, *, periods=_EMPTY_PERIODS, today=_TODAY):
    return transform.build_signals(
        bars=bars,
        periods=periods,
        rules=rules,
        rules_id=transform.hash_rules(rules),
        tickers=universe,
        today=today,
    )


def _periods(closes, *, timeframe, first_day, step):
    """Weekly or monthly bars of a path: `step` maps a bar's number to its day."""
    bars = series.path(closes)
    days = [step(first_day, index) for index in range(len(closes))]
    return polars.DataFrame(
        {
            "adj_close": bars["close"],
            "close": bars["close"],
            "day": days,
            "high": bars["high"],
            "last_day": [
                day + datetime.timedelta(days=4 if timeframe == "w" else 27)
                for day in days
            ],
            "low": bars["low"],
            "open": bars["close"],
            "ticker": "AAA",
            "timeframe": timeframe,
            "volume": 100,
        },
        schema=_EMPTY_PERIODS.schema,
    )


def _weeks(first, index):
    return first + datetime.timedelta(weeks=index)


def _months(first, index):
    year, month = divmod(first.month - 1 + index, 12)
    return datetime.date(first.year + year, month + 1, 1)


def _weekly(closes):
    return _periods(
        closes, timeframe="w", first_day=datetime.date(2024, 1, 1), step=_weeks
    )


def _monthly(closes):
    return _periods(
        closes, timeframe="m", first_day=datetime.date(2020, 1, 1), step=_months
    )


def test_when_a_daily_downtrend_breaks_then_the_signal_carries_its_evidence(
    rules, universe_frame
):
    volumes: list[int | None] = [100] * 49
    volumes[48] = 300
    bars = series.daily_frame("AAA", series.DOWNTREND, volumes=volumes)

    computed = _run(rules, universe_frame, bars)

    [signal] = computed.signals.to_dicts()
    day = bars.get_column("day")[48]
    assert signal["id"] == f"AAA|d|break_up|{day}"
    assert (signal["day"], signal["known"]) == (day, day)
    assert (signal["direction"], signal["level"], signal["stop"]) == (
        "up",
        107.5,
        100.5,
    )
    assert (signal["close"], signal["trend_swings"]) == (108.0, 2)
    assert signal["volume_ratio"] == pytest.approx(3.0)
    assert signal["rules"] == transform.hash_rules(rules)
    assert (signal["aligned"], signal["score"], signal["grade"]) == (False, 1, "C")


def test_when_the_volume_is_missing_or_the_prior_mean_zero_then_the_ratio_is_null(
    rules, universe_frame
):
    missing: list[int | None] = [100] * 49
    missing[48] = None
    zero = [0] * 49
    zero[48] = 50

    ratios = [
        _run(
            rules,
            universe_frame,
            series.daily_frame("AAA", series.DOWNTREND, volumes=volumes),
        ).signals.item(0, "volume_ratio")
        for volumes in (missing, zero)
    ]

    assert ratios == [None, None]


def test_when_a_swing_is_confirmed_then_the_pivots_table_dates_both_bars(
    rules, universe_frame
):
    bars = series.daily_frame("AAA", series.DOWNTREND)
    days = bars.get_column("day")

    computed = _run(rules, universe_frame, bars)

    first = computed.pivots.row(0, named=True)
    assert (first["day"], first["confirmed"]) == (days[10], days[13])
    assert (first["kind"], first["label"], first["price"]) == ("high", None, 110.5)
    assert computed.pivots.height == 6
    assert computed.pivots.get_column("label").to_list().count("LL") == 2


def test_when_the_signal_is_last_then_structure_reports_the_state_and_its_start(
    rules, universe_frame
):
    bars = series.daily_frame("AAA", series.DOWNTREND)

    computed = _run(rules, universe_frame, bars)

    [row] = computed.structure.filter(polars.col("timeframe").eq("d")).to_dicts()
    assert row["state"] == "turning_up"
    assert row["since"] == bars.get_column("day")[48]
    assert (row["last_high"], row["last_low"]) == (107.5, 100.5)


def test_when_a_signal_has_its_horizons_then_outcomes_are_forward_only(
    rules, universe_frame
):
    closes = (*series.CONFIRMED, *range(108, 130))
    bars = series.daily_frame("AAA", closes)

    computed = _run(rules, universe_frame, bars)

    break_up = computed.outcomes.filter(polars.col("id").str.contains("break_up")).sort(
        "horizon"
    )
    assert break_up.get_column("horizon").to_list() == [5, 20]
    assert break_up.item(0, "return") == pytest.approx(closes[53] / closes[48] - 1)
    assert break_up.item(0, "end_day") == bars.get_column("day")[53]


def test_when_a_week_is_still_running_then_a_saturday_run_emits_no_signal_for_it(
    rules, universe_frame
):
    weekly = _weekly(series.DOWNTREND)
    break_week = weekly.get_column("day")[48]
    sunday = break_week + datetime.timedelta(days=6)
    daily = series.daily_frame("AAA", [100.0] * 20)

    saturday = _run(
        rules,
        universe_frame,
        daily,
        periods=weekly,
        today=sunday - datetime.timedelta(days=1),
    )
    monday = _run(
        rules,
        universe_frame,
        daily,
        periods=weekly,
        today=sunday + datetime.timedelta(days=1),
    )

    assert saturday.signals.filter(polars.col("timeframe").eq("w")).is_empty()
    [signal] = monday.signals.filter(polars.col("timeframe").eq("w")).to_dicts()
    assert (signal["day"], signal["known"]) == (
        break_week,
        break_week + datetime.timedelta(days=4),
    )


def test_when_a_month_closes_then_a_run_on_the_first_emits_its_signal(
    rules, universe_frame
):
    monthly = _monthly(series.DOWNTREND)
    last = monthly.get_column("day")[48]
    month_end = last.replace(day=28) + datetime.timedelta(days=4)
    month_end = month_end - datetime.timedelta(days=month_end.day)
    daily = series.daily_frame("AAA", [100.0] * 20)

    on_the_last = _run(rules, universe_frame, daily, periods=monthly, today=month_end)
    on_the_first = _run(
        rules,
        universe_frame,
        daily,
        periods=monthly,
        today=month_end + datetime.timedelta(days=1),
    )

    assert on_the_last.signals.filter(polars.col("timeframe").eq("m")).is_empty()
    assert on_the_first.signals.filter(polars.col("timeframe").eq("m")).height == 1


def test_when_a_signal_falls_in_a_week_then_it_reads_the_weeks_before_not_its_own():
    signals = polars.DataFrame(
        {
            "day": [datetime.date(2024, 3, 13)] * 2 + [datetime.date(2024, 3, 8)],
            "direction": ["up", "down", "up"],
            "id": ["up", "down", "friday"],
            "ticker": ["AAA"] * 3,
            "timeframe": ["d"] * 3,
        }
    )
    weeks = polars.DataFrame(
        {
            "last_day": [
                datetime.date(2024, 3, 1),
                datetime.date(2024, 3, 8),
                datetime.date(2024, 3, 15),
            ],
            "state": ["down", "turning_up", "up"],
            "ticker": ["AAA"] * 3,
            "timeframe": ["w"] * 3,
        }
    )

    aligned = score.map_attach_alignment(signals, weeks).sort("id")

    assert dict(
        zip(aligned.get_column("id"), aligned.get_column("aligned"), strict=True)
    ) == {
        "up": True,
        "down": False,
        "friday": False,
    }


def test_when_nothing_is_earlier_up_then_not_aligned_and_monthly_has_none():
    signals = polars.DataFrame(
        {
            "day": [datetime.date(2024, 3, 13)] * 2,
            "direction": ["up", "up"],
            "id": ["d", "m"],
            "ticker": ["AAA"] * 2,
            "timeframe": ["d", "m"],
        }
    )
    states = polars.DataFrame(
        schema={
            "last_day": polars.Date,
            "state": polars.String,
            "ticker": polars.String,
            "timeframe": polars.String,
        }
    )

    aligned = score.map_attach_alignment(signals, states).sort("id")

    assert aligned.get_column("aligned").to_list() == [False, None]


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"timeframe": "d"}, (0, "C")),
        ({"timeframe": "w"}, (1, "C")),
        ({"timeframe": "m"}, (2, "B")),
        ({"timeframe": "w", "aligned": True}, (2, "B")),
        ({"timeframe": "d", "trend_swings": 3}, (1, "C")),
        ({"timeframe": "d", "volume_ratio": 1.5}, (1, "C")),
        ({"timeframe": "d", "event": "break_up", "margin_atr": 0.5}, (1, "C")),
        ({"timeframe": "d", "event": "break_up", "margin_atr": 0.49}, (0, "C")),
        ({"timeframe": "d", "event": "confirm_up", "margin_atr": 0.9}, (0, "C")),
        ({"timeframe": "d", "event": "confirm_up", "margin_atr": 1.0}, (1, "C")),
        (
            {
                "timeframe": "w",
                "aligned": True,
                "trend_swings": 4,
                "volume_ratio": 2.0,
                "event": "break_down",
                "margin_atr": 1.2,
            },
            (5, "A"),
        ),
        (
            {"timeframe": "m", "aligned": None, "trend_swings": 3},
            (3, "A"),
        ),
    ],
)
def test_when_scoring_then_each_reason_earns_its_point_and_the_grade_follows(
    rules, row, expected
):
    base = {
        "aligned": False,
        "event": "fail_up",
        "margin_atr": None,
        "trend_swings": 0,
        "volume_ratio": None,
    }
    signals = polars.DataFrame(
        [base | row],
        schema={
            "aligned": polars.Boolean,
            "event": polars.String,
            "margin_atr": polars.Float64,
            "timeframe": polars.String,
            "trend_swings": polars.Int32,
            "volume_ratio": polars.Float64,
        },
    )

    scored = score.map_score(signals, rules)

    assert (scored.item(0, "score"), scored.item(0, "grade")) == expected


def _arrays():
    close = numpy.array([100.0, 102.0, 99.0, 104.0, 110.0, 108.0])
    return {
        "adj_close": numpy.array([50.0, 51.0, 49.5, 52.0, 55.0, 54.0]),
        "close": close,
        "high": close + 1,
        "low": close - 1,
    }


def _one_signal(*, direction, stop, row=0):
    return polars.DataFrame(
        {
            "direction": [direction],
            "end": [6],
            "id": ["s"],
            "row": [row],
            "stop": [stop],
            "timeframe": ["d"],
        },
        schema_overrides={"row": polars.Int64, "end": polars.Int64},
    )


def test_when_an_up_signal_has_its_horizon_then_the_outcome_is_worked_by_hand():
    arrays = _arrays()
    days = polars.Series("last_day", [datetime.date(2024, 1, d) for d in range(1, 7)])

    result = outcomes.build_outcomes(
        _one_signal(direction="up", stop=98.0),
        horizons={"d": (3,), "m": (), "w": ()},
        last_day=days,
        **arrays,
    )

    row = result.row(0, named=True)
    assert row["return"] == pytest.approx(52.0 / 50.0 - 1)
    assert row["signed_return"] == pytest.approx(0.04)
    assert row["mfe"] == pytest.approx(105.0 / 100.0 - 1)
    assert row["mae"] == pytest.approx(98.0 / 100.0 - 1)
    assert row["held"] is True
    assert (row["horizon"], row["end_day"]) == (3, datetime.date(2024, 1, 4))


def test_when_a_close_ends_beyond_the_stop_then_held_is_false_for_up_and_down():
    arrays = _arrays()
    days = polars.Series("last_day", [datetime.date(2024, 1, d) for d in range(1, 7)])
    horizons = {"d": (3,), "m": (), "w": ()}

    up = outcomes.build_outcomes(
        _one_signal(direction="up", stop=99.5),
        horizons=horizons,
        last_day=days,
        **arrays,
    )
    down = outcomes.build_outcomes(
        _one_signal(direction="down", stop=103.5),
        horizons=horizons,
        last_day=days,
        **arrays,
    )

    assert up.item(0, "held") is False
    assert down.item(0, "held") is False
    assert down.item(0, "signed_return") == pytest.approx(-0.04)
    assert down.item(0, "mfe") == pytest.approx(1 - 98.0 / 100.0)
    assert down.item(0, "mae") == pytest.approx(-(105.0 / 100.0 - 1))


def test_when_the_horizon_runs_past_the_last_bar_then_there_is_no_outcome():
    arrays = _arrays()
    days = polars.Series("last_day", [datetime.date(2024, 1, d) for d in range(1, 7)])

    result = outcomes.build_outcomes(
        _one_signal(direction="up", stop=90.0, row=3),
        horizons={"d": (2, 3), "m": (), "w": ()},
        last_day=days,
        **arrays,
    )

    assert result.get_column("horizon").to_list() == [2]


def test_when_a_signal_is_not_the_last_bar_then_to_date_reads_through_the_end():
    arrays = _arrays()

    held = outcomes.build_to_date(
        _one_signal(direction="up", stop=98.0),
        adj_close=arrays["adj_close"],
        bounds=[(0, 6)],
        close=arrays["close"],
    )
    broken = outcomes.build_to_date(
        _one_signal(direction="up", stop=99.5),
        adj_close=arrays["adj_close"],
        bounds=[(0, 6)],
        close=arrays["close"],
    )

    assert held.item(0, "return_to_date") == pytest.approx(54.0 / 50.0 - 1)
    assert (held.item(0, "held_to_date"), broken.item(0, "held_to_date")) == (
        True,
        False,
    )


def test_when_the_signal_is_the_last_bar_then_to_date_is_flat_and_held():
    arrays = _arrays()

    last = outcomes.build_to_date(
        _one_signal(direction="up", stop=200.0, row=5),
        adj_close=arrays["adj_close"],
        bounds=[(0, 6)],
        close=arrays["close"],
    )

    assert (last.item(0, "return_to_date"), last.item(0, "held_to_date")) == (0.0, True)


def test_when_bars_have_forward_returns_then_the_baseline_is_their_mean_and_shares():
    bars = polars.DataFrame(
        {
            "adj_close": [10.0, 11.0, 10.0, 12.0, 12.0],
            "asset_class": "stock",
            "day": [datetime.date(2024, 1, d) for d in range(1, 6)],
            "ticker": "AAA",
            "timeframe": "d",
        }
    )

    baseline = outcomes.build_baseline(
        bars, atr_bars=1, horizons={"d": (1,), "m": (), "w": ()}
    ).filter(polars.col("asset_class").eq("stock"))

    row = baseline.row(0, named=True)
    assert row["baseline_return"] == pytest.approx(
        (0.1 + (10 / 11 - 1) + 0.2 + 0.0) / 4
    )
    assert (row["share_up"], row["share_down"]) == (0.5, 0.25)


def test_when_bars_precede_the_first_atr_then_the_baseline_leaves_them_out():
    bars = polars.DataFrame(
        {
            "adj_close": [10.0, 20.0, 21.0, 21.0],
            "asset_class": "stock",
            "day": [datetime.date(2024, 1, d) for d in range(1, 5)],
            "ticker": "AAA",
            "timeframe": "d",
        }
    )

    baseline = outcomes.build_baseline(
        bars, atr_bars=3, horizons={"d": (1,), "m": (), "w": ()}
    ).filter(polars.col("asset_class").eq("all"))

    assert baseline.item(0, "baseline_return") == pytest.approx(0.0)


def test_when_signals_are_summarised_then_every_class_and_grade_also_appears_as_all():
    signals = polars.DataFrame(
        {
            "asset_class": ["stock", "crypto"],
            "direction": ["up", "up"],
            "event": ["break_up", "break_up"],
            "grade": ["A", "B"],
            "id": ["a", "b"],
            "timeframe": ["d", "d"],
        }
    )
    results = polars.DataFrame(
        {
            "end_day": [datetime.date(2024, 1, 1)] * 2,
            "held": [True, False],
            "horizon": [5, 5],
            "id": ["a", "b"],
            "mae": [-0.02, -0.04],
            "mfe": [0.05, 0.01],
            "return": [0.10, -0.02],
            "signed_return": [0.10, -0.02],
        },
        schema=outcomes.OUTCOMES,
    )
    baseline = polars.DataFrame(
        {
            "asset_class": ["all", "crypto", "stock"],
            "baseline_return": [0.01, 0.02, 0.03],
            "horizon": [5, 5, 5],
            "share_down": [0.4, 0.3, 0.2],
            "share_up": [0.5, 0.6, 0.7],
            "timeframe": ["d", "d", "d"],
        },
        schema_overrides={"horizon": polars.Int32},
    )

    stats = outcomes.build_stats(
        baseline=baseline, outcomes=results, rules_id="abc", signals=signals
    )

    everything = stats.filter(
        polars.col("asset_class").eq("all"), polars.col("grade").eq("all")
    ).row(0, named=True)
    assert everything["n"] == 2
    assert everything["hit_rate"] == 0.5
    assert everything["mean_return"] == pytest.approx(0.04)
    assert everything["baseline_mean"] == pytest.approx(0.01)
    assert everything["baseline_hit"] == 0.5
    assert everything["edge"] == pytest.approx(0.03)
    assert everything["held_rate"] == 0.5
    assert everything["mfe_median"] == pytest.approx(0.03)
    assert everything["mae_median"] == pytest.approx(-0.03)
    assert stats.height == 7
    stock_a = stats.filter(
        polars.col("asset_class").eq("stock"), polars.col("grade").eq("A")
    ).row(0, named=True)
    assert (stock_a["n"], stock_a["baseline_hit"], stock_a["rules"]) == (1, 0.7, "abc")


def test_when_the_event_points_down_then_its_baseline_is_signed_the_other_way():
    signals = polars.DataFrame(
        {
            "asset_class": ["stock"],
            "direction": ["down"],
            "event": ["break_down"],
            "grade": ["A"],
            "id": ["a"],
            "timeframe": ["d"],
        }
    )
    results = polars.DataFrame(
        {
            "end_day": [datetime.date(2024, 1, 1)],
            "held": [True],
            "horizon": [5],
            "id": ["a"],
            "mae": [-0.02],
            "mfe": [0.05],
            "return": [-0.10],
            "signed_return": [0.10],
        },
        schema=outcomes.OUTCOMES,
    )
    baseline = polars.DataFrame(
        {
            "asset_class": ["all", "stock"],
            "baseline_return": [0.02, 0.02],
            "horizon": [5, 5],
            "share_down": [0.4, 0.4],
            "share_up": [0.6, 0.6],
            "timeframe": ["d", "d"],
        },
        schema_overrides={"horizon": polars.Int32},
    )

    stats = outcomes.build_stats(
        baseline=baseline, outcomes=results, rules_id="abc", signals=signals
    )

    row = stats.row(0, named=True)
    assert (row["baseline_mean"], row["baseline_hit"]) == (-0.02, 0.4)
    assert row["edge"] == pytest.approx(0.12)


def test_when_rates_are_listed_then_only_all_all_rows_in_event_timeframe_order():
    stats = polars.DataFrame(
        {
            "asset_class": ["all", "stock", "all", "all"],
            "baseline_hit": [0.5] * 4,
            "baseline_mean": [0.0] * 4,
            "edge": [0.1] * 4,
            "event": ["break_up", "break_up", "break_down", "break_up"],
            "grade": ["all", "all", "all", "all"],
            "held_rate": [0.5] * 4,
            "hit_rate": [0.6] * 4,
            "horizon": [5, 5, 5, 20],
            "mae_median": [0.0] * 4,
            "mean_return": [0.0] * 4,
            "median_return": [0.0] * 4,
            "mfe_median": [0.0] * 4,
            "n": [10] * 4,
            "rules": ["x"] * 4,
            "timeframe": ["d"] * 4,
        }
    )

    rates = transform.build_rates(stats)

    assert rates.columns == [
        "event",
        "timeframe",
        "horizon",
        "n",
        "hit_rate",
        "baseline_hit",
        "edge",
        "held_rate",
    ]
    assert rates.select("event", "horizon").rows() == [
        ("break_up", 5),
        ("break_up", 20),
        ("break_down", 5),
    ]
