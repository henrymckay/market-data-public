"""Score and grade a signal, and read the structure one timeframe up."""

import polars

from market_data.code.transform import rules as rules_

_NEXT_UP = {"d": "w", "w": "m"}
_UP_STATES = ("up", "turning_up")
_DOWN_STATES = ("down", "turning_down")


def map_attach_alignment(
    signals: polars.DataFrame, states: polars.DataFrame
) -> polars.DataFrame:
    """Add `aligned`: the next timeframe up pointed the signal's way before it.

    The structure read is that of the latest bar one timeframe up whose last
    trading day is before the signal's `day`, so no signal sees a bar that was
    still forming; monthly signals have none, and a daily or weekly one with no
    earlier bar up is not aligned.

    :param signals: `day`, `direction`, `id`, `ticker` and `timeframe`.
    :param states: `last_day`, `state`, `ticker` and `timeframe` of weekly and
        monthly bars.
    :returns: The signals with `aligned`.
    """
    parts: list[polars.DataFrame] = []
    for timeframe in rules_.TIMEFRAMES:
        group = signals.filter(polars.col("timeframe").eq(timeframe)).sort("day")
        if timeframe == "m":
            parts.append(group.with_columns(aligned=polars.lit(None, polars.Boolean)))
            continue
        above = (
            states.filter(polars.col("timeframe").eq(_NEXT_UP[timeframe]))
            .select("last_day", "state", "ticker")
            .sort("last_day")
        )
        parts.append(
            group.join_asof(
                above,
                allow_exact_matches=False,
                by="ticker",
                check_sortedness=False,
                left_on="day",
                right_on="last_day",
                strategy="backward",
            )
            .with_columns(
                aligned=polars.when(polars.col("direction").eq("up"))
                .then(polars.col("state").is_in(_UP_STATES))
                .otherwise(polars.col("state").is_in(_DOWN_STATES))
                .fill_null(value=False)
            )
            .drop("last_day", "state")
        )
    return polars.concat(parts)


def map_score(signals: polars.DataFrame, rules: rules_.Rules) -> polars.DataFrame:
    """Add `score` and `grade` from the rules' points.

    :param signals: `aligned`, `event`, `margin_atr`, `timeframe`, `trend_swings`
        and `volume_ratio`.
    :param rules: The rules.
    :returns: The signals with `grade` and `score`.
    """
    score = rules.score
    is_break = polars.col("event").str.starts_with("break")
    is_confirm = polars.col("event").str.starts_with("confirm")
    margin = polars.col("margin_atr")
    margin_met = (is_break & margin.ge(score.margin_atr.break_)) | (
        is_confirm & margin.ge(score.margin_atr.confirm)
    )
    points = (
        polars.col("timeframe")
        .replace_strict(
            {name: score.timeframe.at(name) for name in rules_.TIMEFRAMES},
            return_dtype=polars.Int32,
        )
        .add(
            polars.col("aligned")
            .fill_null(value=False)
            .cast(polars.Int32)
            .mul(score.aligned)
        )
        .add(
            polars.col("trend_swings")
            .ge(score.trend_swings.at_least)
            .fill_null(value=False)
            .cast(polars.Int32)
            .mul(score.trend_swings.points)
        )
        .add(
            polars.col("volume_ratio")
            .ge(score.volume_ratio.at_least)
            .fill_null(value=False)
            .cast(polars.Int32)
            .mul(score.volume_ratio.points)
        )
        .add(
            margin_met.fill_null(value=False)
            .cast(polars.Int32)
            .mul(score.margin_atr.points)
        )
    )
    return signals.with_columns(points.alias("score")).with_columns(
        polars.when(polars.col("score").ge(rules.grades.A))
        .then(polars.lit("A"))
        .when(polars.col("score").ge(rules.grades.B))
        .then(polars.lit("B"))
        .otherwise(polars.lit("C"))
        .alias("grade")
    )
