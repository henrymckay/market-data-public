"""Pivots, signals, outcomes, base rates and structure from every stored bar."""

import dataclasses
import datetime

import polars

from market_data.code.transform import outcomes, period, score, structure
from market_data.code.transform import rules as rules_

PIVOTS = polars.Schema(
    {
        "confirmed": polars.Date,
        "day": polars.Date,
        "kind": polars.String,
        "label": polars.String,
        "price": polars.Float64,
        "ticker": polars.String,
        "timeframe": polars.String,
    }
)

SIGNALS = polars.Schema(
    {
        "aligned": polars.Boolean,
        "atr": polars.Float64,
        "close": polars.Float64,
        "day": polars.Date,
        "direction": polars.String,
        "event": polars.String,
        "grade": polars.String,
        "held_to_date": polars.Boolean,
        "id": polars.String,
        "known": polars.Date,
        "level": polars.Float64,
        "margin_atr": polars.Float64,
        "return_to_date": polars.Float64,
        "rules": polars.String,
        "score": polars.Int32,
        "stop": polars.Float64,
        "swing_atr": polars.Float64,
        "ticker": polars.String,
        "timeframe": polars.String,
        "trend_swings": polars.Int32,
        "volume_ratio": polars.Float64,
    }
)

SIGNAL_STATS = polars.Schema(
    {
        "asset_class": polars.String,
        "baseline_hit": polars.Float64,
        "baseline_mean": polars.Float64,
        "edge": polars.Float64,
        "event": polars.String,
        "grade": polars.String,
        "held_rate": polars.Float64,
        "hit_rate": polars.Float64,
        "horizon": polars.Int32,
        "mae_median": polars.Float64,
        "mean_return": polars.Float64,
        "median_return": polars.Float64,
        "mfe_median": polars.Float64,
        "n": polars.Int64,
        "rules": polars.String,
        "timeframe": polars.String,
    }
)

STRUCTURE = polars.Schema(
    {
        "last_high": polars.Float64,
        "last_low": polars.Float64,
        "since": polars.Date,
        "state": polars.String,
        "ticker": polars.String,
        "timeframe": polars.String,
    }
)

_FOUND_PIVOTS = polars.Schema(
    {
        "bar": polars.Int64,
        "confirmed": polars.Int64,
        "kind": polars.String,
        "label": polars.String,
        "price": polars.Float64,
        "ticker": polars.String,
        "timeframe": polars.String,
    }
)
_FOUND_SIGNALS = polars.Schema(
    {
        "atr": polars.Float64,
        "end": polars.Int64,
        "event": polars.String,
        "level": polars.Float64,
        "margin_atr": polars.Float64,
        "row": polars.Int64,
        "stop": polars.Float64,
        "swing_atr": polars.Float64,
        "ticker": polars.String,
        "timeframe": polars.String,
        "trend_swings": polars.Int32,
    }
)
_FOUND_STRUCTURE = polars.Schema(
    {
        "last_high": polars.Float64,
        "last_low": polars.Float64,
        "since": polars.Int64,
        "state": polars.String,
        "ticker": polars.String,
        "timeframe": polars.String,
    }
)
_VOLUME_WINDOW = 20
_DIRECTION = {
    "break_up": "up",
    "confirm_up": "up",
    "fail_up": "down",
    "break_down": "down",
    "confirm_down": "down",
    "fail_down": "up",
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Computed:
    """The five tables the signals stage replaces."""

    outcomes: polars.DataFrame
    pivots: polars.DataFrame
    signal_stats: polars.DataFrame
    signals: polars.DataFrame
    structure: polars.DataFrame


@dataclasses.dataclass(slots=True)
class _Found:
    """What the walks over every group found, as columns of rows."""

    pivots: dict[str, list[object]] = dataclasses.field(
        default_factory=lambda: {name: [] for name in _FOUND_PIVOTS}
    )
    signals: dict[str, list[object]] = dataclasses.field(
        default_factory=lambda: {name: [] for name in _FOUND_SIGNALS}
    )
    states_row: list[int] = dataclasses.field(default_factory=list[int])
    states: list[str] = dataclasses.field(default_factory=list[str])
    structure: dict[str, list[object]] = dataclasses.field(
        default_factory=lambda: {name: [] for name in _FOUND_STRUCTURE}
    )
    bounds: list[tuple[int, int]] = dataclasses.field(
        default_factory=list[tuple[int, int]]
    )


def _walk_groups(bars: polars.DataFrame, rules: rules_.Rules) -> _Found:
    """Walk every ticker and timeframe's bars, which are sorted and contiguous."""
    high = bars.get_column("high").to_numpy()
    low = bars.get_column("low").to_numpy()
    close = bars.get_column("close").to_numpy()
    found = _Found()
    groups = (
        bars.with_row_index("row")
        .group_by("ticker", "timeframe", maintain_order=True)
        .agg(polars.col("row").first().alias("start"), polars.len().alias("length"))
    )
    for ticker, timeframe, start, length in groups.iter_rows():
        end = start + length
        found.bounds.append((start, end))
        walked = structure.walk(
            atr_bars=rules.atr_bars,
            close=close[start:end],
            high=high[start:end],
            k=rules.swing_atr.at(timeframe),
            low=low[start:end],
        )
        for pivot in walked.pivots:
            columns = found.pivots
            columns["bar"].append(start + pivot.bar)
            columns["confirmed"].append(start + pivot.confirmed)
            columns["kind"].append(pivot.kind)
            columns["label"].append(pivot.label)
            columns["price"].append(pivot.price)
            columns["ticker"].append(ticker)
            columns["timeframe"].append(timeframe)
        for signal in walked.signals:
            columns = found.signals
            columns["atr"].append(signal.atr)
            columns["end"].append(end)
            columns["event"].append(signal.event)
            columns["level"].append(signal.level)
            columns["margin_atr"].append(signal.margin_atr)
            columns["row"].append(start + signal.bar)
            columns["stop"].append(signal.stop)
            columns["swing_atr"].append(signal.swing_atr)
            columns["ticker"].append(ticker)
            columns["timeframe"].append(timeframe)
            columns["trend_swings"].append(signal.trend_swings)
        if timeframe != "d":
            found.states_row.extend(range(start, end))
            found.states.extend(walked.states)
        columns = found.structure
        columns["last_high"].append(walked.last_high)
        columns["last_low"].append(walked.last_low)
        columns["since"].append(None if walked.since is None else start + walked.since)
        columns["state"].append(walked.states[-1] if walked.states else "none")
        columns["ticker"].append(ticker)
        columns["timeframe"].append(timeframe)
    return found


def _volume_ratio(bars: polars.DataFrame) -> polars.Series:
    """Return each bar's volume over the mean of the 20 bars before it, or null."""
    mean = (
        polars.col("volume")
        .cast(polars.Float64)
        .shift(n=1)
        .rolling_mean(window_size=_VOLUME_WINDOW, min_samples=_VOLUME_WINDOW)
        .over("ticker", "timeframe", order_by="day")
    )
    return bars.select(
        polars.when(mean.gt(0))
        .then(polars.col("volume").cast(polars.Float64).truediv(mean))
        .alias("volume_ratio")
    ).get_column("volume_ratio")


def build_signals(
    *,
    bars: polars.DataFrame,
    rules: rules_.Rules,
    rules_id: str,
    tickers: polars.DataFrame,
    today: datetime.date,
    periods: polars.DataFrame,
) -> Computed:
    """Return every pivot, signal, outcome, base rate and structure.

    The pass is deterministic and looks only backward, so the rows known on a day
    are the same whether or not later bars exist.

    :param bars: Stored daily bars.
    :param periods: The weekly and monthly bars, from the `period_bars` view.
    :param rules: The rules.
    :param rules_id: The rules' hash, stored on every signal and base rate.
    :param tickers: The stored universe, for each instrument's asset class.
    :param today: The run's UTC date; a period ending on or after it is dropped.
    :returns: The five tables.
    """
    frame = period.build_timeframe_bars(bars, periods, today=today)
    found = _walk_groups(frame, rules)
    row_day = frame.get_column("day")
    row_known = frame.get_column("last_day")
    pivots = polars.DataFrame(found.pivots, schema_overrides={"label": polars.String})
    pivots = pivots.with_columns(
        row_day.gather(pivots.get_column("bar")).alias("day"),
        row_day.gather(pivots.get_column("confirmed")).alias("confirmed"),
    ).select(list(PIVOTS))
    structured = polars.DataFrame(found.structure, schema=_FOUND_STRUCTURE)
    structured = structured.with_columns(
        row_day.gather(structured.get_column("since")).alias("since")
    )
    state_rows = polars.Series("row", found.states_row, dtype=polars.UInt32)
    states = polars.DataFrame(
        {
            "last_day": row_known.gather(state_rows),
            "state": found.states,
            "ticker": frame.get_column("ticker").gather(state_rows),
            "timeframe": frame.get_column("timeframe").gather(state_rows),
        }
    )
    ratio = _volume_ratio(frame)
    raw = polars.DataFrame(found.signals, schema=_FOUND_SIGNALS)
    raw_rows = raw.get_column("row")
    day = row_day.gather(raw_rows)
    signals = (
        raw.with_columns(
            day.alias("day"),
            row_known.gather(raw_rows).alias("known"),
            frame.get_column("close").gather(raw_rows).alias("close"),
            ratio.gather(raw_rows).alias("volume_ratio"),
            polars.col("event")
            .replace_strict(_DIRECTION, return_dtype=polars.String)
            .alias("direction"),
        )
        .with_columns(
            polars.concat_str(
                "ticker",
                "timeframe",
                "event",
                polars.col("day").cast(polars.String),
                separator="|",
            ).alias("id"),
        )
        .pipe(score.map_attach_alignment, states)
        .pipe(score.map_score, rules)
    )
    horizons = {name: rules.horizons.at(name) for name in rules_.TIMEFRAMES}
    adj_close = frame.get_column("adj_close").to_numpy()
    close = frame.get_column("close").to_numpy()
    results = outcomes.build_outcomes(
        signals,
        adj_close=adj_close,
        close=close,
        high=frame.get_column("high").to_numpy(),
        horizons=horizons,
        last_day=row_known,
        low=frame.get_column("low").to_numpy(),
    )
    to_date = outcomes.build_to_date(
        signals, adj_close=adj_close, bounds=found.bounds, close=close
    )
    stored_signals = (
        signals.with_columns(to_date.drop("id"))
        .with_columns(polars.lit(rules_id).alias("rules"))
        .select(list(SIGNALS))
        .sort("ticker", "timeframe", "day")
    )
    classes = tickers.select("asset_class", "ticker")
    baseline = outcomes.build_baseline(
        frame.select("adj_close", "day", "ticker", "timeframe").join(
            classes, on="ticker", how="left"
        ),
        atr_bars=rules.atr_bars,
        horizons=horizons,
    )
    return Computed(
        outcomes=results.sort("id", "horizon"),
        pivots=pivots.sort("ticker", "timeframe", "day", "kind"),
        signal_stats=outcomes.build_stats(
            baseline=baseline,
            outcomes=results,
            rules_id=rules_id,
            signals=stored_signals.join(classes, on="ticker", how="left"),
        ),
        signals=stored_signals,
        structure=structured.select(list(STRUCTURE)).sort("ticker", "timeframe"),
    )


def build_rates(stats: polars.DataFrame) -> polars.DataFrame:
    """Return the base rates over every asset class and grade, for a dry run.

    :param stats: `signal_stats` rows.
    :returns: `event`, `timeframe`, `horizon`, `n`, `hit_rate`, `baseline_hit`,
        `edge` and `held_rate` for asset class and grade `all`.
    """
    return (
        stats.filter(polars.col("asset_class").eq("all"), polars.col("grade").eq("all"))
        .select(
            "event",
            "timeframe",
            "horizon",
            "n",
            "hit_rate",
            "baseline_hit",
            "edge",
            "held_rate",
        )
        .sort(
            polars.col("event").replace_strict(
                {name: index for index, name in enumerate(structure.EVENTS)},
                return_dtype=polars.Int32,
            ),
            polars.col("timeframe").replace_strict(
                {"d": 0, "w": 1, "m": 2}, return_dtype=polars.Int32
            ),
            "horizon",
        )
    )
