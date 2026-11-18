import numpy
import polars
import pytest

from market_data.code.transform import structure
from pytest_ import series

_ATR_BARS = 1
_K = 2.0


def _walk(bars, *, k=_K, atr_bars=_ATR_BARS):
    return structure.walk(atr_bars=atr_bars, k=k, **bars)


def _swings(walked):
    return [(p.bar, p.confirmed, p.kind, p.price, p.label) for p in walked.pivots]


def _events(walked):
    return [(s.bar, s.event) for s in walked.signals]


def test_when_a_downtrend_then_swings_are_confirmed_three_points_back_and_labelled():
    walked = _walk(series.path(series.DOWNTREND))

    assert _swings(walked) == [
        (10, 13, "high", 110.5, None),
        (17, 20, "low", 102.5, None),
        (23, 26, "high", 109.5, "LH"),
        (30, 33, "low", 101.5, "LL"),
        (35, 38, "high", 107.5, "LH"),
        (41, 44, "low", 100.5, "LL"),
    ]


def test_when_two_lower_highs_and_lows_then_a_close_above_the_last_high_is_break_up():
    walked = _walk(series.path(series.DOWNTREND))

    [signal] = walked.signals
    assert (signal.bar, signal.event) == (48, "break_up")
    assert (signal.level, signal.stop, signal.trend_swings) == (107.5, 100.5, 2)
    assert signal.margin_atr == pytest.approx(0.5 / 1.5)
    assert signal.swing_atr == pytest.approx(7.0 / 1.5)
    assert signal.atr == pytest.approx(1.5)


def test_when_the_labels_settle_then_the_structure_is_down_until_the_break():
    walked = _walk(series.path(series.DOWNTREND), atr_bars=_ATR_BARS)

    assert walked.states[32:33] == ["none"]
    assert walked.states[33] == "down"
    assert walked.states[47] == "down"
    assert walked.states[48] == "turning_up"
    assert (walked.state, walked.since) == ("turning_up", 48)


def test_when_a_wick_passes_the_level_but_the_close_does_not_then_no_break():
    bars = series.path(series.DOWNTREND)
    bars["high"][46] = 108.2

    walked = _walk(bars)

    assert _events(walked) == [(48, "break_up")]


def test_when_the_next_swing_low_is_above_the_stop_then_confirm_up():
    walked = _walk(series.path(series.CONFIRMED))

    confirm = walked.signals[1]
    assert (confirm.bar, confirm.event) == (59, "confirm_up")
    assert (confirm.level, confirm.stop, confirm.trend_swings) == (103.5, 103.5, 2)
    assert confirm.margin_atr == pytest.approx(3.0 / 1.5)
    assert confirm.swing_atr == pytest.approx(7.0 / 1.5)
    assert (walked.state, walked.since) == ("up", 59)
    assert (walked.last_high, walked.last_low) == (110.5, 103.5)


def test_when_a_close_falls_below_the_stop_before_a_confirmation_then_fail_up():
    walked = _walk(series.path(series.FAILED_ON_CLOSE))

    failure = walked.signals[1]
    assert (failure.bar, failure.event) == (56, "fail_up")
    assert (failure.level, failure.stop) == (100.5, 100.5)
    assert failure.margin_atr == pytest.approx(0.5 / 1.5)
    assert walked.state == "down"


def test_when_the_next_swing_low_is_at_the_stop_then_fail_up():
    walked = _walk(series.path(series.FAILED_ON_SWING))

    failure = walked.signals[1]
    assert (failure.bar, failure.event) == (62, "fail_up")
    assert failure.margin_atr == pytest.approx(0.0)
    assert (walked.state, walked.since) == ("down", 62)


def test_when_the_path_is_mirrored_then_a_break_down_with_the_same_margins():
    walked = _walk(series.mirror(series.path(series.DOWNTREND)))

    [signal] = walked.signals
    assert (signal.bar, signal.event) == (48, "break_down")
    assert (signal.level, signal.stop, signal.trend_swings) == (92.5, 99.5, 2)
    assert signal.margin_atr == pytest.approx(0.5 / 1.5)
    assert signal.swing_atr == pytest.approx(7.0 / 1.5)


def test_when_the_mirrored_break_holds_then_confirm_down():
    walked = _walk(series.mirror(series.path(series.CONFIRMED)))

    confirm = walked.signals[1]
    assert (confirm.bar, confirm.event) == (59, "confirm_down")
    assert (confirm.level, confirm.stop) == (96.5, 96.5)
    assert walked.state == "down"


def test_when_the_mirrored_break_fails_on_a_close_then_fail_down():
    walked = _walk(series.mirror(series.path(series.FAILED_ON_CLOSE)))

    assert _events(walked) == [(48, "break_down"), (56, "fail_down")]
    assert walked.state == "up"


def test_when_the_mirrored_break_fails_on_a_swing_then_fail_down():
    walked = _walk(series.mirror(series.path(series.FAILED_ON_SWING)))

    assert _events(walked) == [(48, "break_down"), (62, "fail_down")]


def test_when_a_higher_high_swings_without_a_close_over_the_level_then_none():
    bars = series.path((*series.DOWNTREND[:45], 105, 106, 104))
    bars["high"][46] = 112.0

    walked = _walk(bars)

    assert walked.states[44] == "down"
    assert walked.states[47] == "none"
    assert walked.signals == []


def test_when_there_are_fewer_bars_than_the_atr_needs_then_nothing_is_found():
    walked = _walk(series.path(series.DOWNTREND[:10]), atr_bars=14)

    assert (walked.pivots, walked.signals, walked.state) == ([], [], "none")
    assert (walked.last_high, walked.last_low, walked.since) == (None, None, None)


def test_when_the_walk_is_cut_short_then_its_findings_are_a_prefix_of_the_whole():
    whole = _walk(series.path(series.CONFIRMED))
    cut = _walk(series.path(series.CONFIRMED[:50]))

    assert cut.pivots == [p for p in whole.pivots if p.confirmed < 50]
    assert cut.signals == [s for s in whole.signals if s.bar < 50]


def test_when_a_swing_ties_on_the_lowest_low_then_the_later_bar_is_the_extreme():
    closes = [100, 104, 108, 104, 100, 100, 104, 108]
    bars = series.path(closes)

    walked = _walk(bars, atr_bars=1, k=1.0)

    assert [p.bar for p in walked.pivots if p.kind == "low"][:1] == [5]


def test_when_atr_bars_is_14_then_the_atr_is_wilders_over_true_range(random_bars):
    closes = random_bars.get_column("close").to_numpy()
    bars = {
        "close": closes,
        "high": random_bars.get_column("high").to_numpy(),
        "low": random_bars.get_column("low").to_numpy(),
    }
    walked = structure.walk(atr_bars=14, k=0.1, **bars)
    previous = polars.col("close").shift(1)
    expected = random_bars.select(
        polars.max_horizontal(
            polars.col("high") - polars.col("low"),
            (polars.col("high") - previous).abs(),
            (polars.col("low") - previous).abs(),
        )
        .ewm_mean(alpha=1 / 14, adjust=False, min_samples=14)
        .alias("atr")
    ).get_column("atr")
    atr_at = {s.bar: s.atr for s in walked.signals}

    assert atr_at
    for bar, atr in atr_at.items():
        assert atr == pytest.approx(expected[bar])


@pytest.fixture
def random_bars():
    generator = numpy.random.default_rng(7)
    close = 100 + numpy.cumsum(generator.normal(0, 1, 400))
    return polars.DataFrame(
        {
            "close": close,
            "high": close + generator.uniform(0, 1, 400),
            "low": close - generator.uniform(0, 1, 400),
        }
    )
