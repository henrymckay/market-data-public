"""Swings, structure and events over one instrument's bars on one timeframe."""

import dataclasses
import math
import typing

import numpy

type Kind = typing.Literal["high", "low"]

STATES = ("none", "up", "down", "turning_up", "turning_down")
EVENTS = (
    "break_up",
    "confirm_up",
    "fail_up",
    "break_down",
    "confirm_down",
    "fail_down",
)
_HIGH_LABELS = {1: "HH", -1: "LH", 0: "EH"}
_LOW_LABELS = {1: "HL", -1: "LL", 0: "EL"}

_NONE, _UP, _DOWN, _TURNING_UP, _TURNING_DOWN = range(5)
_BREAK_UP, _CONFIRM_UP, _FAIL_UP, _BREAK_DOWN, _CONFIRM_DOWN, _FAIL_DOWN = range(6)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pivot:
    """A swing high or low, confirmed on a later bar and never moved after."""

    bar: int
    confirmed: int
    kind: Kind
    label: str | None
    price: float


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Signal:
    """One break, confirmation or failure, on the bar it was known."""

    atr: float
    bar: int
    event: str
    level: float
    margin_atr: float | None
    stop: float
    swing_atr: float | None
    trend_swings: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Walk:
    """What one pass over a group's bars found, and where it stands at the last bar."""

    last_high: float | None
    last_low: float | None
    pivots: list[Pivot]
    signals: list[Signal]
    since: int | None
    state: str
    states: list[str]


def _ratio(numerator: float, atr: float) -> float | None:
    """Return a price distance in ATR, or null where the ATR is zero."""
    return numerator / atr if atr > 0 else None


def _label(price: float, previous: float, labels: dict[int, str]) -> str | None:
    """Label a swing against the previous one of its kind; none if there is none."""
    if math.isnan(previous):
        return None
    return labels[(price > previous) - (price < previous)]


def walk(
    *,
    atr_bars: int,
    close: numpy.ndarray,
    high: numpy.ndarray,
    k: float,
    low: numpy.ndarray,
) -> Walk:
    """Walk one group's bars in order, finding swings, structure and signals.

    The ATR is Wilder's (`alpha` one over `atr_bars`, seeded by the first true range)
    and counts from the bar that has `atr_bars` observations.
    A swing is confirmed on the first bar whose close retreats `k` ATR from the
    extreme; a confirmed swing is never moved, so the pass never repaints.
    The state holds the last swing of each kind and the extreme; the lowest low or
    highest high since the extreme is read from the arrays once per swing.

    :param atr_bars: The ATR's length in bars.
    :param close: Split-adjusted closes, oldest first.
    :param high: Split-adjusted highs.
    :param k: The swing threshold in ATR.
    :param low: Split-adjusted lows.
    :returns: The pivots, signals, the state after every bar and where it stands.
    """
    highs, lows, closes = high.tolist(), low.tolist(), close.tolist()
    alpha = 1.0 / atr_bars
    warm = atr_bars - 1
    atr = 0.0
    previous_close = 0.0
    up_mode = True
    extreme = 0.0
    extreme_bar = 0
    high_price = low_price = math.nan
    high_label = low_label = None
    lower_highs = higher_lows = 0
    state = _NONE
    since: int | None = None
    break_level = break_stop = 0.0
    carried = 0
    pivots: list[Pivot] = []
    signals: list[Signal] = []
    states: list[int] = []

    def emit(
        code: int,
        bar: int,
        *,
        height: float,
        level: float,
        margin: float,
        stop: float,
        swings: int,
    ) -> None:
        signals.append(
            Signal(
                atr=atr,
                bar=bar,
                event=EVENTS[code],
                level=level,
                margin_atr=_ratio(margin, atr),
                stop=stop,
                swing_atr=_ratio(height, atr),
                trend_swings=swings,
            )
        )

    for bar, (bar_high, bar_low, bar_close) in enumerate(
        zip(highs, lows, closes, strict=True)
    ):
        true_range = (
            bar_high - bar_low
            if bar == 0
            else max(
                bar_high - bar_low,
                abs(bar_high - previous_close),
                abs(bar_low - previous_close),
            )
        )
        atr = true_range if bar == 0 else atr + alpha * (true_range - atr)
        previous_close = bar_close
        if bar <= warm:
            if bar == warm:
                extreme, extreme_bar = bar_high, bar
            states.append(_NONE)
            continue
        threshold = k * atr
        pre_high, pre_low = high_price, low_price
        pre_lower, pre_higher = lower_highs, higher_lows
        swing_kind: Kind | None = None
        swing_price = 0.0
        pivot_bar = 0
        if up_mode:
            if bar_high >= extreme:
                extreme, extreme_bar = bar_high, bar
            elif bar_close <= extreme - threshold:
                swing_kind, swing_price, pivot_bar = "high", extreme, extreme_bar
                segment = lows[extreme_bar + 1 : bar + 1]
                extreme_bar += len(segment) - int(numpy.argmin(segment[::-1]))
                extreme = lows[extreme_bar]
                up_mode = False
        elif bar_low <= extreme:
            extreme, extreme_bar = bar_low, bar
        elif bar_close >= extreme + threshold:
            swing_kind, swing_price, pivot_bar = "low", extreme, extreme_bar
            segment = highs[extreme_bar + 1 : bar + 1]
            extreme_bar += len(segment) - int(numpy.argmax(segment[::-1]))
            extreme = highs[extreme_bar]
            up_mode = True
        swing_label: str | None = None
        if swing_kind == "high":
            swing_label = _label(swing_price, high_price, _HIGH_LABELS)
            lower_highs = lower_highs + 1 if swing_label == "LH" else 0
            high_price, high_label = swing_price, swing_label
        elif swing_kind == "low":
            swing_label = _label(swing_price, low_price, _LOW_LABELS)
            higher_lows = higher_lows + 1 if swing_label == "HL" else 0
            low_price, low_label = swing_price, swing_label
        if swing_kind is not None:
            pivots.append(
                Pivot(
                    bar=pivot_bar,
                    confirmed=bar,
                    kind=swing_kind,
                    label=swing_label,
                    price=swing_price,
                )
            )
        next_state = state
        if state == _DOWN:
            if bar_close > pre_high:
                emit(
                    _BREAK_UP,
                    bar,
                    height=pre_high - low_price,
                    level=pre_high,
                    margin=bar_close - pre_high,
                    stop=low_price,
                    swings=pre_lower,
                )
                next_state, break_level, break_stop = _TURNING_UP, pre_high, low_price
                carried = pre_lower
            elif swing_label == "HH" and swing_kind == "high":
                next_state = _NONE
        elif state == _UP:
            if bar_close < pre_low:
                emit(
                    _BREAK_DOWN,
                    bar,
                    height=high_price - pre_low,
                    level=pre_low,
                    margin=pre_low - bar_close,
                    stop=high_price,
                    swings=pre_higher,
                )
                next_state, break_level, break_stop = _TURNING_DOWN, pre_low, high_price
                carried = pre_higher
            elif swing_label == "LL" and swing_kind == "low":
                next_state = _NONE
        elif state == _TURNING_UP:
            if bar_close < break_stop:
                emit(
                    _FAIL_UP,
                    bar,
                    height=break_level - break_stop,
                    level=break_stop,
                    margin=break_stop - bar_close,
                    stop=break_stop,
                    swings=carried,
                )
                next_state = _DOWN
            elif swing_kind == "low" and swing_price > break_stop:
                emit(
                    _CONFIRM_UP,
                    bar,
                    height=high_price - swing_price,
                    level=swing_price,
                    margin=swing_price - break_stop,
                    stop=swing_price,
                    swings=carried,
                )
                next_state = _UP
            elif swing_kind == "low":
                emit(
                    _FAIL_UP,
                    bar,
                    height=break_level - break_stop,
                    level=break_stop,
                    margin=break_stop - swing_price,
                    stop=break_stop,
                    swings=carried,
                )
                next_state = _DOWN
        elif state == _TURNING_DOWN:
            if bar_close > break_stop:
                emit(
                    _FAIL_DOWN,
                    bar,
                    height=break_stop - break_level,
                    level=break_stop,
                    margin=bar_close - break_stop,
                    stop=break_stop,
                    swings=carried,
                )
                next_state = _UP
            elif swing_kind == "high" and swing_price < break_stop:
                emit(
                    _CONFIRM_DOWN,
                    bar,
                    height=swing_price - low_price,
                    level=swing_price,
                    margin=break_stop - swing_price,
                    stop=swing_price,
                    swings=carried,
                )
                next_state = _DOWN
            elif swing_kind == "high":
                emit(
                    _FAIL_DOWN,
                    bar,
                    height=break_stop - break_level,
                    level=break_stop,
                    margin=swing_price - break_stop,
                    stop=break_stop,
                    swings=carried,
                )
                next_state = _UP
        if next_state == _NONE:
            if high_label == "LH" and low_label == "LL":
                next_state = _DOWN
            elif high_label == "HH" and low_label == "HL":
                next_state = _UP
        if next_state != state:
            state, since = next_state, bar
        states.append(state)
    return Walk(
        last_high=None if math.isnan(high_price) else high_price,
        last_low=None if math.isnan(low_price) else low_price,
        pivots=pivots,
        signals=signals,
        since=since,
        state=STATES[state],
        states=[STATES[code] for code in states],
    )
