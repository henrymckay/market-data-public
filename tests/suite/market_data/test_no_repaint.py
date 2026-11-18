import datetime

import hypothesis
import hypothesis.strategies
import numpy
import polars

from market_data.code import transform
from market_data.code.adapt import rules as rules_adapter
from pytest_ import series

_BARS = 1600
_TRIALS = 40
_HASHED = transform.hash_rules(rules_adapter.read_rules())


def _walk(seed: int) -> list[float]:
    """Return a drifting walk whose drift changes sign every few months."""
    generator = numpy.random.default_rng(seed)
    regimes = numpy.repeat(generator.normal(0, 0.6, _BARS // 80 + 1), 80)[:_BARS]
    return list(100 + numpy.cumsum(regimes + generator.normal(0, 1.5, _BARS)) + 400)


def _frame(seed: int) -> polars.DataFrame:
    return series.daily_frame("AAA", _walk(seed))


def _universe() -> polars.DataFrame:
    return polars.DataFrame(
        {"asset_class": ["stock"], "ticker": ["AAA"]},
        schema={"asset_class": polars.String, "ticker": polars.String},
    )


def _signals(bars: polars.DataFrame, today: datetime.date) -> transform.Computed:
    rules = rules_adapter.read_rules()
    return transform.build_signals(
        bars=bars,
        periods=series.periods_of(bars),
        rules=rules,
        rules_id=_HASHED,
        tickers=_universe(),
        today=today,
    )


def _known_by(frame: polars.DataFrame, column: str, today: datetime.date):
    """Keep rows whose period had ended before `today`, as a run on it would see."""
    day = polars.col(column)
    end = (
        polars.when(polars.col("timeframe").eq("w"))
        .then(day.dt.offset_by("6d"))
        .when(polars.col("timeframe").eq("m"))
        .then(day.dt.month_end())
        .otherwise(day)
    )
    return frame.filter(end.lt(today))


_TO_DATE = ("held_to_date", "return_to_date")


def _stable(computed: transform.Computed, today: datetime.date):
    pivots = _known_by(computed.pivots, "confirmed", today).sort(
        "timeframe", "day", "kind"
    )
    signals = (
        _known_by(computed.signals, "day", today)
        .drop(*_TO_DATE)
        .sort("timeframe", "day", "event")
    )
    return pivots, signals


@hypothesis.settings(max_examples=_TRIALS, deadline=None)
@hypothesis.given(
    seed=hypothesis.strategies.integers(0, 10_000),
    cut=hypothesis.strategies.integers(700, _BARS - 2),
)
def test_when_the_history_is_cut_then_its_pivots_and_signals_are_those_of_the_whole(
    seed, cut
):
    bars = _frame(seed)
    last = bars.get_column("day")[cut]
    prefix = bars.head(cut + 1)
    today = last + datetime.timedelta(days=1)

    whole = _stable(
        _signals(bars, bars.get_column("day")[-1] + datetime.timedelta(days=1)), today
    )
    part = _stable(_signals(prefix, today), today)

    assert part[0].equals(whole[0])
    assert part[1].equals(whole[1])


def test_when_the_walks_are_generated_then_every_timeframe_reaches_signals_and_pivots():
    counts: dict[str, int] = {"d": 0, "m": 0, "w": 0}
    for seed in range(_TRIALS):
        computed = _signals(_frame(seed), datetime.date(2040, 1, 1))
        for timeframe in counts:
            counts[timeframe] += computed.signals.filter(
                polars.col("timeframe").eq(timeframe)
            ).height
        assert computed.pivots.height > 0

    assert min(counts.values()) > 0
    assert counts["d"] > _TRIALS
