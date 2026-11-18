"""Outcomes and base rates: what followed each signal, and what followed any bar."""

import numpy
import polars

OUTCOMES = polars.Schema(
    {
        "end_day": polars.Date,
        "held": polars.Boolean,
        "horizon": polars.Int32,
        "id": polars.String,
        "mae": polars.Float64,
        "mfe": polars.Float64,
        "return": polars.Float64,
        "signed_return": polars.Float64,
    }
)

_CHUNK = 20_000


def build_forward_returns(
    bars: polars.DataFrame, *, atr_bars: int, horizon: int
) -> polars.DataFrame:
    """Return every bar's adjusted-close return `horizon` bars on, where it exists.

    Only bars from the first with an ATR count, as the swings do.

    :param bars: One timeframe's bars with `asset_class`, `adj_close`, `day`,
        `ticker`, sorted by ticker and day.
    :param atr_bars: The ATR's length, which says where an instrument's swings start.
    :param horizon: How many bars ahead.
    :returns: `asset_class` and `return`, one row per bar with a complete horizon.
    """
    return (
        bars.select(
            polars.col("asset_class"),
            polars.col("adj_close")
            .shift(n=-horizon)
            .truediv(polars.col("adj_close"))
            .sub(1)
            .over("ticker", order_by="day")
            .alias("return"),
            polars.int_range(polars.len())
            .over("ticker", order_by="day")
            .ge(atr_bars - 1)
            .alias("counted"),
        )
        .filter(polars.col("counted"), polars.col("return").is_not_null())
        .drop("counted")
    )


def build_baseline(
    bars: polars.DataFrame, *, atr_bars: int, horizons: dict[str, tuple[int, ...]]
) -> polars.DataFrame:
    """Return how any bar did at each horizon, per asset class and timeframe.

    :param bars: Bars of every timeframe with `asset_class`, `adj_close`, `day`,
        `ticker`, `timeframe`.
    :param atr_bars: The ATR's length.
    :param horizons: Each timeframe's horizons, in bars.
    :returns: Per asset class, `all` included, timeframe and horizon: the mean
        return and the shares of bars that rose and fell.
    """
    parts: list[polars.DataFrame] = []
    for timeframe, steps in horizons.items():
        group = bars.filter(polars.col("timeframe").eq(timeframe)).sort("ticker", "day")
        for horizon in steps:
            forward = build_forward_returns(group, atr_bars=atr_bars, horizon=horizon)
            pooled = polars.concat(
                [forward, forward.with_columns(asset_class=polars.lit("all"))]
            )
            parts.append(
                pooled.group_by("asset_class")
                .agg(
                    polars.col("return").mean().alias("baseline_return"),
                    polars.col("return").gt(0).mean().alias("share_up"),
                    polars.col("return").lt(0).mean().alias("share_down"),
                )
                .with_columns(
                    horizon=polars.lit(horizon, polars.Int32),
                    timeframe=polars.lit(timeframe),
                )
            )
    return polars.concat(parts)


def _suffix_extremes(
    closes: numpy.ndarray, bounds: list[tuple[int, int]]
) -> tuple[numpy.ndarray, numpy.ndarray]:
    """Return each bar's lowest and highest close through its group's last bar."""
    lowest = numpy.empty_like(closes)
    highest = numpy.empty_like(closes)
    for start, end in bounds:
        window = closes[start:end][::-1]
        lowest[start:end] = numpy.minimum.accumulate(window)[::-1]
        highest[start:end] = numpy.maximum.accumulate(window)[::-1]
    return lowest, highest


def build_to_date(
    signals: polars.DataFrame,
    *,
    adj_close: numpy.ndarray,
    bounds: list[tuple[int, int]],
    close: numpy.ndarray,
) -> polars.DataFrame:
    """Return each signal's return and whether its stop held, as of the last bar.

    :param signals: `id`, `row`, `end`, `direction` and `stop`, one row per signal.
    :param adj_close: Every bar's adjusted close, in the frame's order.
    :param bounds: Each group's first row and one past its last.
    :param close: Every bar's split-adjusted close.
    :returns: `id`, `held_to_date` and `return_to_date`.
    """
    lowest, highest = _suffix_extremes(close, bounds)
    rows = signals.get_column("row").to_numpy()
    ends = signals.get_column("end").to_numpy()
    later = rows + 1 < ends
    after = numpy.minimum(rows + 1, ends - 1)
    up = signals.get_column("direction").eq("up").to_numpy()
    stops = signals.get_column("stop").to_numpy()
    held = numpy.where(
        later,
        numpy.where(up, lowest[after] >= stops, highest[after] <= stops),
        True,
    )
    return_to_date = adj_close[ends - 1] / adj_close[rows] - 1
    return polars.DataFrame(
        {
            "held_to_date": held,
            "id": signals.get_column("id"),
            "return_to_date": return_to_date,
        }
    )


def _outcome_chunk(
    signals: polars.DataFrame,
    *,
    adj_close: numpy.ndarray,
    close: numpy.ndarray,
    high: numpy.ndarray,
    horizon: int,
    low: numpy.ndarray,
) -> dict[str, numpy.ndarray]:
    """Return one horizon's figures for signals whose horizon is complete."""
    rows = signals.get_column("row").to_numpy()
    window = rows[:, None] + numpy.arange(1, horizon + 1)
    up = signals.get_column("direction").eq("up").to_numpy()
    stops = signals.get_column("stop").to_numpy()
    start = close[rows]
    highest = high[window].max(axis=1)
    lowest = low[window].min(axis=1)
    closes = close[window]
    held = numpy.where(
        up,
        (closes >= stops[:, None]).all(axis=1),
        (closes <= stops[:, None]).all(axis=1),
    )
    change = adj_close[rows + horizon] / adj_close[rows] - 1
    return {
        "held": held,
        "mae": numpy.where(up, lowest / start - 1, 1 - highest / start),
        "mfe": numpy.where(up, highest / start - 1, 1 - lowest / start),
        "return": change,
        "signed_return": numpy.where(up, change, -change),
    }


def build_outcomes(
    signals: polars.DataFrame,
    *,
    adj_close: numpy.ndarray,
    close: numpy.ndarray,
    high: numpy.ndarray,
    horizons: dict[str, tuple[int, ...]],
    last_day: polars.Series,
    low: numpy.ndarray,
) -> polars.DataFrame:
    """Return one row per signal and horizon whose bars all exist.

    Returns use adjusted close; the excursions and the stop use the stored highs,
    lows and closes against the signal bar's close.

    :param signals: `id`, `row`, `end`, `direction`, `stop` and `timeframe`, one row
        per signal.
    :param adj_close: Every bar's adjusted close, in the frame's order.
    :param close: Every bar's split-adjusted close.
    :param high: Every bar's split-adjusted high.
    :param horizons: Each timeframe's horizons, in bars.
    :param last_day: Every bar's last trading day, in the frame's order.
    :param low: Every bar's split-adjusted low.
    :returns: Rows in `OUTCOMES`.
    """
    parts: list[polars.DataFrame] = []
    for timeframe, steps in horizons.items():
        group = signals.filter(polars.col("timeframe").eq(timeframe))
        for horizon in steps:
            complete = group.filter(
                polars.col("row").add(horizon).lt(polars.col("end"))
            )
            for offset in range(0, complete.height, _CHUNK):
                chunk = complete.slice(offset, _CHUNK)
                figures = _outcome_chunk(
                    chunk,
                    adj_close=adj_close,
                    close=close,
                    high=high,
                    horizon=horizon,
                    low=low,
                )
                parts.append(
                    polars.DataFrame(figures).with_columns(
                        last_day.gather(
                            chunk.get_column("row").to_numpy() + horizon
                        ).alias("end_day"),
                        horizon=polars.lit(horizon, polars.Int32),
                        id=chunk.get_column("id"),
                    )
                )
    return (
        polars.concat(parts).select(list(OUTCOMES))
        if parts
        else polars.DataFrame(schema=OUTCOMES)
    )


def build_stats(
    *,
    baseline: polars.DataFrame,
    outcomes: polars.DataFrame,
    rules_id: str,
    signals: polars.DataFrame,
) -> polars.DataFrame:
    """Return how signals did at each horizon against any bar, per group.

    Each outcome counts under its own asset class and grade and again under `all`
    for either or both, so every row is one base rate.
    The baseline is signed the event's way: an up event is compared with the share
    of bars that rose, a down event with the share that fell.

    :param baseline: `build_baseline`'s rows.
    :param outcomes: Rows in `OUTCOMES`.
    :param rules_id: The rules' hash.
    :param signals: `asset_class`, `direction`, `event`, `grade`, `id`, `timeframe`.
    :returns: Rows in `signal_stats`' columns.
    """
    variants = (
        outcomes.join(
            signals.select(
                "asset_class", "direction", "event", "grade", "id", "timeframe"
            ),
            on="id",
            how="inner",
            validate="m:1",
        )
        .with_columns(
            asset_class=polars.concat_list(
                polars.col("asset_class").fill_null("unknown"), polars.lit("all")
            ),
            grade=polars.concat_list(polars.col("grade"), polars.lit("all")),
        )
        .explode("asset_class")
        .explode("grade")
    )
    return (
        variants.group_by("asset_class", "event", "grade", "horizon", "timeframe")
        .agg(
            polars.col("direction").first(),
            polars.col("held").mean().alias("held_rate"),
            polars.col("signed_return").gt(0).mean().alias("hit_rate"),
            polars.col("mae").median().alias("mae_median"),
            polars.col("signed_return").mean().alias("mean_return"),
            polars.col("signed_return").median().alias("median_return"),
            polars.col("mfe").median().alias("mfe_median"),
            polars.len().cast(polars.Int64).alias("n"),
        )
        .join(
            baseline,
            on=["asset_class", "horizon", "timeframe"],
            how="left",
            validate="m:1",
        )
        .with_columns(
            polars.when(polars.col("direction").eq("up"))
            .then(polars.col("baseline_return"))
            .otherwise(polars.col("baseline_return").neg())
            .alias("baseline_mean"),
            polars.when(polars.col("direction").eq("up"))
            .then(polars.col("share_up"))
            .otherwise(polars.col("share_down"))
            .alias("baseline_hit"),
        )
        .with_columns(
            polars.col("mean_return").sub(polars.col("baseline_mean")).alias("edge"),
            polars.lit(rules_id).alias("rules"),
        )
        .select(
            "asset_class",
            "baseline_hit",
            "baseline_mean",
            "edge",
            "event",
            "grade",
            "held_rate",
            "hit_rate",
            "horizon",
            "mae_median",
            "mean_return",
            "median_return",
            "mfe_median",
            "n",
            "rules",
            "timeframe",
        )
        .sort("asset_class", "event", "grade", "horizon", "timeframe")
    )
