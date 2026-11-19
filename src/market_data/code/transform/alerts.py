"""Choose the alerts a night owes, compose their messages and judge health.

Composing a message is rendering: the rows of a few frames are read once, in the
function that writes their words, as `use-polars` allows at a boundary.
"""

import dataclasses
import datetime
import typing
import urllib.parse

import polars

from market_data.code.transform import rules as rules_
from market_data.code.transform import status as status_

type Row = dict[str, typing.Any]
type Kind = typing.Literal["push", "digest", "health"]
type HealthState = typing.Literal["healthy", "unhealthy"]

ALERTS = polars.Schema(
    {
        "id": polars.String,
        "kind": polars.String,
        "message": polars.String,
        "sent": polars.Datetime(time_zone="UTC"),
        "title": polars.String,
    }
)

TITLE_BYTES = 60
PUSH_LINES = 4
PUSH_BYTES = 300
DIGEST_LINES = 12
DIGEST_BYTES = 1500
PUSH_PRIORITY = 4
DIGEST_PRIORITY = 3
HEALTH_PRIORITY = 5
RECOVERY_PRIORITY = 3
ACTIONS_PER_DIGEST = 3
MISSING_SHOWN = 3
MIN_CHART_BARS = 20

_TIMEFRAME_WORDS = {"d": "daily", "w": "weekly", "m": "monthly"}
_TIMEFRAME_UNITS = {"d": "day", "w": "week", "m": "month"}
_RANGES = {"d": "1Y", "w": "5Y", "m": "Max"}
_HIGHER = {"d": "w", "w": "m"}
_EVENT_WORDS = {
    "break_up": "first higher high",
    "confirm_up": "first higher low",
    "fail_up": "failed first higher high",
    "break_down": "first lower low",
    "confirm_down": "first lower high",
    "fail_down": "failed first lower low",
}
_CLASS_LABELS = {
    "commodity": "Commodities",
    "crypto": "Crypto",
    "etf": "ETFs",
    "fx": "Currencies",
    "index": "Indices",
    "rate": "Rates",
    "stock": "Stocks",
}
_GRADE_RANK = {"A": 0, "B": 1, "C": 2}
_VERDICT_RANK = {"failed": 0, "partial": 1, "stale": 2}
_LOWER_GRADE = "C"
_NO_EDGE = 0.02


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Action:
    """A button under a message that opens a page."""

    label: str
    url: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class ChartRequest:
    """What a push's image shows: the signal's timeframe, level and stop."""

    asset_class: str
    direction: str
    level: float
    signal_day: datetime.date
    stop: float
    ticker: str
    timeframe: str
    title: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Message:
    """One message for the owner, as the channel carries it."""

    actions: tuple[Action, ...]
    attachment: str | None
    chart: ChartRequest | None
    click: str | None
    kind: Kind
    message: str
    priority: int
    signals: tuple[str, ...]
    tags: tuple[str, ...]
    title: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Health:
    """The pipeline's state, and the message that would announce it."""

    detail: str
    message: Message
    state: HealthState


def slug_of(ticker: str) -> str:
    """Return the ticker as a lower-case word fit for a file name."""
    return "".join(character for character in ticker.lower() if character.isalnum())


def _clip(text: str, limit: int) -> str:
    """Return the text cut to at most `limit` bytes, ending in an ellipsis if cut."""
    if len(text.encode()) <= limit:
        return text
    return text.encode()[: limit - 3].decode(errors="ignore").rstrip() + "..."


def _fit(lines: list[str], *, limit: int, max_lines: int) -> str:
    """Join the lines, dropping the last ones until the lines and bytes fit."""
    kept = lines[:max_lines]
    while len(kept) > 1 and len("\n".join(kept).encode()) > limit:
        kept.pop()
    return _clip("\n".join(kept), limit)


def format_price(value: float, asset_class: str) -> str:
    """Return a price as the page writes it: places by class, thousands separated."""
    if asset_class == "fx":
        digits = 3 if value >= 20 else 4
    else:
        digits = 4 if abs(value) < 1 else 2
    return f"{value:,.{digits}f}"


def _day(day: datetime.date) -> str:
    """Return a day as `17 Nov 2026`."""
    return f"{day.day} {day:%b} {day.year}"


def _percent(fraction: float) -> str:
    """Return a fraction as a whole percentage."""
    return f"{fraction * 100:.0f}%"


def _click(site_url: str, row: Row) -> str:
    """Return the link that opens the ticker view at a signal."""
    query = urllib.parse.urlencode(
        {
            "view": "ticker",
            "t": row["ticker"],
            "tf": row["timeframe"],
            "range": _RANGES[row["timeframe"]],
            "sig": f"{row['day']}.{row['event']}",
        }
    )
    return f"{site_url}?{query}"


def _signals_url(site_url: str, *, asset_class: str, day: datetime.date) -> str:
    """Return the link that opens the Signals screen on a class and a day."""
    query = urllib.parse.urlencode({"view": "signals", "cls": asset_class, "day": day})
    return f"{site_url}?{query}"


def primary_horizon(rules: rules_.Rules, timeframe: str) -> int:
    """Return the middle horizon of a timeframe, the one base rates are read at."""
    horizons = rules.horizons.at(timeframe)
    return horizons[len(horizons) // 2]


def select_due(
    *,
    rules: rules_.Rules,
    sent: polars.DataFrame,
    signals: polars.DataFrame,
    tickers: polars.DataFrame,
    today: datetime.date,
) -> polars.DataFrame:
    """Return the signals owed a message: recent, wanted, unmuted and not yet sent.

    A signal is recent when its `known` day is within `window-days` of `today`.

    :param rules: The rules, whose `alerts` say what is wanted.
    :param sent: `id` of every signal a message already named.
    :param signals: Stored signals, every grade.
    :param tickers: The universe, with `asset_class` and `name`.
    :param today: The run's UTC date.
    :returns: The signals' columns with `asset_class` and `name`.
    """
    alerts = rules.alerts
    return (
        signals.filter(
            polars.col("known").ge(today - datetime.timedelta(days=alerts.window_days)),
            polars.col("event").is_in(alerts.events),
        )
        .join(sent.select("id"), on="id", how="anti")
        .join(
            tickers.select("asset_class", "name", "ticker"),
            on="ticker",
            how="inner",
            validate="m:1",
        )
        .filter(~polars.col("asset_class").is_in(alerts.muted_asset_classes))
    )


def attach_context(
    due: polars.DataFrame,
    *,
    rules: rules_.Rules,
    stats: polars.DataFrame,
    structure: polars.DataFrame,
) -> polars.DataFrame:
    """Add each signal's base rate and its higher timeframe's trend.

    The base rate is the grade `all` row of the signal's asset class, event and
    timeframe at the timeframe's primary horizon, or the row of every asset class
    where that holds fewer than `base-rate-min-n` signals.

    :param due: Signals with `asset_class`.
    :param rules: The rules.
    :param stats: `signal_stats` rows.
    :param structure: `structure` rows.
    :returns: The signals with `base_baseline`, `base_hit`, `base_horizon`,
        `base_n`, `base_scope` (`class` or `all`) and `higher_state`.
    """
    horizons = polars.DataFrame(
        {
            "timeframe": ["d", "w", "m"],
            "horizon": [primary_horizon(rules, name) for name in ("d", "w", "m")],
        },
        schema={"timeframe": polars.String, "horizon": polars.Int32},
    )
    rates = (
        stats.filter(polars.col("grade").eq("all"))
        .join(horizons, on=["horizon", "timeframe"], how="inner")
        .select(
            "asset_class",
            "event",
            "timeframe",
            polars.col("baseline_hit").alias("base_baseline"),
            polars.col("hit_rate").alias("base_hit"),
            polars.col("horizon").alias("base_horizon"),
            polars.col("n").alias("base_n"),
        )
    )
    own = rates.rename(lambda name: f"own_{name}" if name.startswith("base_") else name)
    every = (
        rates.filter(polars.col("asset_class").eq("all"))
        .drop("asset_class")
        .rename(lambda name: f"all_{name}" if name.startswith("base_") else name)
    )
    enough = polars.col("own_base_n").ge(rules.alerts.base_rate_min_n)
    chosen = ["baseline", "hit", "horizon", "n"]
    higher = structure.select(
        polars.col("state").alias("higher_state"),
        "ticker",
        polars.col("timeframe").alias("higher_timeframe"),
    )
    return (
        due.join(
            own, on=["asset_class", "event", "timeframe"], how="left", validate="m:1"
        )
        .join(every, on=["event", "timeframe"], how="left", validate="m:1")
        .with_columns(
            polars.when(enough)
            .then(polars.lit("class"))
            .when(polars.col("all_base_n").is_not_null())
            .then(polars.lit("all"))
            .alias("base_scope"),
            *(
                polars.when(enough)
                .then(polars.col(f"own_base_{name}"))
                .otherwise(polars.col(f"all_base_{name}"))
                .alias(f"base_{name}")
                for name in chosen
            ),
            polars.col("timeframe")
            .replace_strict(_HIGHER, default=None, return_dtype=polars.String)
            .alias("higher_timeframe"),
        )
        .join(
            higher,
            on=["ticker", "higher_timeframe"],
            how="left",
            validate="m:1",
        )
        .drop(
            "higher_timeframe",
            *(f"own_base_{name}" for name in chosen),
            *(f"all_base_{name}" for name in chosen),
        )
    )


def rank_signals(signals: polars.DataFrame, *, rules: rules_.Rules) -> polars.DataFrame:
    """Order signals by score, then the timeframe's weight, then margin, then id."""
    weights = {name: rules.score.timeframe.at(name) for name in ("d", "w", "m")}
    return signals.sort(
        polars.col("score"),
        polars.col("timeframe").replace_strict(weights, return_dtype=polars.Int64),
        polars.col("margin_atr").abs(),
        "id",
        descending=[True, True, True, False],
        nulls_last=True,
    )


def _headline(row: Row) -> str:
    """Return the first line: what closed or confirmed, and the evidence."""
    price = format_price(row["level"], row["asset_class"])
    close = format_price(row["close"], row["asset_class"])
    margin = row["margin_atr"]
    swings = row["trend_swings"] or 0
    match row["event"]:
        case "break_up":
            run = f" after {swings} lower highs" if swings >= 2 else ""
            return (
                f"Closed {close} above the lower high {price} ({margin:+.1f} ATR){run}."
            )
        case "break_down":
            run = f" after {swings} higher lows" if swings >= 2 else ""
            return (
                f"Closed {close} below the higher low {price} ({margin:+.1f} ATR){run}."
            )
        case "confirm_up":
            return f"Higher low {price} confirmed, {margin:.1f} ATR above the last low."
        case "confirm_down":
            return (
                f"Lower high {price} confirmed, {margin:.1f} ATR below the last high."
            )
        case _:
            return f"Closed beyond the stop {price}."


def _stop_line(row: Row) -> str:
    """Return the second line: the invalidation, the volume and the higher trend."""
    side = "below" if row["direction"] == "up" else "above"
    stop = format_price(row["stop"], row["asset_class"])
    away = (row["stop"] / row["close"] - 1) * 100
    parts = [f"Invalid {side} {stop} ({away:+.1f}%)."]
    if row["volume_ratio"] is not None:
        parts.append(f"Volume {row['volume_ratio']:.1f}x.")
    higher = row["higher_state"]
    if row["timeframe"] in _HIGHER and higher not in (None, "none"):
        word = _TIMEFRAME_WORDS[_HIGHER[row["timeframe"]]].capitalize()
        parts.append(f"{word} trend {higher.replace('_', ' ')}.")
    return " ".join(parts)


def _base_line(row: Row) -> str:
    """Return the base rate beside the any-bar baseline, or that there is none."""
    if row["base_n"] is None:
        return "Base rate: none yet."
    moved = "rose" if row["direction"] == "up" else "fell"
    unit = _TIMEFRAME_UNITS[row["timeframe"]]
    scope = ", all classes" if row["base_scope"] == "all" else ""
    flat = abs(row["base_hit"] - row["base_baseline"]) < _NO_EDGE
    verdict = ", no edge" if flat else ""
    return (
        f"Base rate: {_percent(row['base_hit'])} {moved} within "
        f"{row['base_horizon']} {unit}s (n {row['base_n']}{scope}); "
        f"any {unit} {_percent(row['base_baseline'])}{verdict}."
    )


def _direction_tag(direction: str) -> str:
    """Return the emoji short code for a rise or a fall."""
    return (
        "chart_with_upwards_trend"
        if direction == "up"
        else "chart_with_downwards_trend"
    )


def compose_push(row: Row, *, rules: rules_.Rules) -> Message:
    """Return the push for one signal, with the chart it carries.

    :param row: A signal with `asset_class`, `name`, the base rate and the trend.
    :param rules: The rules, for the site's address.
    :returns: A message of at most four lines and 300 bytes, a title of at most 60.
    """
    site = rules.alerts.site_url
    title = _clip(
        f"{row['ticker']} {_TIMEFRAME_WORDS[row['timeframe']]}: "
        f"{_EVENT_WORDS[row['event']]} ({row['grade']})",
        TITLE_BYTES,
    )
    click = _click(site, row)
    return Message(
        actions=(
            Action(label="Chart", url=click),
            Action(
                label="All signals",
                url=_signals_url(
                    site, asset_class=row["asset_class"], day=row["known"]
                ),
            ),
        ),
        attachment=f"{slug_of(row['ticker'])}-{row['timeframe']}.png",
        chart=ChartRequest(
            asset_class=row["asset_class"],
            direction=row["direction"],
            level=row["level"],
            signal_day=row["day"],
            stop=row["stop"],
            ticker=row["ticker"],
            timeframe=row["timeframe"],
            title=title,
        ),
        click=click,
        kind="push",
        message=_fit(
            [_headline(row), _stop_line(row), _base_line(row)],
            limit=PUSH_BYTES,
            max_lines=PUSH_LINES,
        ),
        priority=PUSH_PRIORITY,
        signals=(row["id"],),
        tags=(_direction_tag(row["direction"]), row["asset_class"]),
        title=title,
    )


def _digest_line(row: Row) -> str:
    """Return one signal's line in a digest."""
    base = (
        f"base {_percent(row['base_hit'])} vs {_percent(row['base_baseline'])}"
        if row["base_n"] is not None
        else "no base"
    )
    level = format_price(row["level"], row["asset_class"])
    return (
        f"{row['grade']} {row['ticker']} {row['timeframe'].upper()} "
        f"{_EVENT_WORDS[row['event']]} {level}, {base}"
    )


def _digest_tail(*, folded: int, lower: int) -> str | None:
    """Return the last line, counting what the digest leaves to the Signals screen."""
    parts = [
        *([f"+{folded} more"] if folded else []),
        *([f"+{lower} graded {_LOWER_GRADE}"] if lower else []),
    ]
    return f"{', '.join(parts)} on the Signals screen" if parts else None


def _digest_body(lines: list[str], *, lower: int) -> tuple[str, int]:
    """Return the digest's text and how many signal lines it folded away."""
    for shown in range(len(lines), 0, -1):
        folded = len(lines) - shown
        tail = _digest_tail(folded=folded, lower=lower)
        kept = [*lines[:shown], *([tail] if tail else [])]
        text = "\n".join(kept)
        if len(kept) <= DIGEST_LINES and len(text.encode()) <= DIGEST_BYTES:
            return text, folded
    return _digest_tail(folded=len(lines), lower=lower) or "", len(lines)


def compose_digest(rows: list[Row], *, lower: int, rules: rules_.Rules) -> Message:
    """Return the digest of one asset class's signals, ranked best first.

    :param rows: The class's signals graded B or better, best first.
    :param lower: How many signals graded C the class has on the digest's day.
    :param rules: The rules, for the site's address.
    :returns: A message of at most 12 lines and 1,500 bytes; lines it cannot fit
        are counted in its last line.
    """
    site = rules.alerts.site_url
    asset_class = rows[0]["asset_class"]
    day: datetime.date = max(row["known"] for row in rows)
    best = sum(row["grade"] == "A" for row in rows)
    count = f"{len(rows)} signal{'s' if len(rows) != 1 else ''}"
    graded = f", {best} graded A" if best else ""
    text, _ = _digest_body([_digest_line(row) for row in rows], lower=lower)
    return Message(
        actions=tuple(
            Action(label=row["ticker"], url=_click(site, row))
            for row in rows[:ACTIONS_PER_DIGEST]
        ),
        attachment=None,
        chart=None,
        click=_signals_url(site, asset_class=asset_class, day=day),
        kind="digest",
        message=text,
        priority=DIGEST_PRIORITY,
        signals=tuple(row["id"] for row in rows),
        tags=("bar_chart", asset_class),
        title=_clip(
            f"{_CLASS_LABELS[asset_class]}: {count} on {_day(day)}{graded}",
            TITLE_BYTES,
        ),
    )


def plan_messages(due: polars.DataFrame, *, rules: rules_.Rules) -> tuple[Message, ...]:
    """Return the pushes, then the digests, a night owes.

    A push goes for each signal of the push grade or better, the best
    `push-cap` of them; each asset class with a signal of the digest grade or
    better gets one digest, unless it would only repeat this night's pushes.

    :param due: `select_due`'s signals with `attach_context`'s columns.
    :param rules: The rules.
    :returns: The messages, pushes first.
    """
    alerts = rules.alerts
    ranked = rank_signals(due, rules=rules)
    grade = polars.col("grade").replace_strict(_GRADE_RANK, return_dtype=polars.Int64)
    pushed = ranked.filter(grade.le(_GRADE_RANK[alerts.push_grade])).head(
        alerts.push_cap
    )
    worthy = ranked.filter(grade.le(_GRADE_RANK[alerts.digest_grade]))
    pushed_ids = set(pushed.get_column("id").to_list())
    pushes = tuple(
        compose_push(row, rules=rules) for row in pushed.iter_rows(named=True)
    )
    digests: list[Message] = []
    for asset_class in sorted(worthy.get_column("asset_class").unique().to_list()):
        rows = list(
            worthy.filter(polars.col("asset_class").eq(asset_class)).iter_rows(
                named=True
            )
        )
        if all(row["id"] in pushed_ids for row in rows):
            continue
        day = max(row["known"] for row in rows)
        lower = ranked.filter(
            polars.col("asset_class").eq(asset_class),
            polars.col("known").eq(day),
            grade.gt(_GRADE_RANK[alerts.digest_grade]),
        ).height
        digests.append(compose_digest(rows, lower=lower, rules=rules))
    return (*pushes, *digests)


def signals_stored(runs: polars.DataFrame) -> bool:
    """Return whether the latest `signals` run stored its tables."""
    latest = runs.filter(polars.col("source").eq("signals")).sort("ended")
    return not latest.is_empty() and latest.row(-1, named=True)["outcome"] == "stored"


def _names(missing: tuple[str, ...]) -> str:
    """Return the first few instruments without bars and a count of the rest."""
    shown = ", ".join(missing[:MISSING_SHOWN])
    rest = len(missing) - MISSING_SHOWN
    return f"{shown} +{rest}" if rest > 0 else shown


def build_health(
    *,
    missing: tuple[str, ...],
    run_url: str | None,
    runs: polars.DataFrame,
    status: status_.Status,
) -> Health:
    """Describe the pipeline's state and the message announcing it.

    :param missing: Active instruments with no bars.
    :param run_url: The page of the Actions run, for the message's click.
    :param runs: The manifest rows.
    :param status: What `build_status` judged from them.
    :returns: The state, a one-line detail and the message for a change to it.
    """
    stale = dict(status.rows)["stale"] == "true"
    latest = (
        runs.sort("ended").group_by("source", maintain_order=True).last()
        if not runs.is_empty()
        else runs
    )
    rows = list(latest.sort("source").iter_rows(named=True))
    unstored = [row for row in rows if row["outcome"] != "stored"]
    stored = [row["source"] for row in rows if row["outcome"] == "stored"]
    if status.healthy:
        return Health(
            detail="Every stage stored and the data is fresh.",
            message=Message(
                actions=(),
                attachment=None,
                chart=None,
                click=run_url,
                kind="health",
                message="Every stage stored and the data is fresh.",
                priority=RECOVERY_PRIORITY,
                signals=(),
                tags=("white_check_mark",),
                title="Market data: healthy again",
            ),
            state="healthy",
        )
    verdicts = [
        *(row["outcome"] for row in unstored),
        *(["stale"] if stale else []),
    ]
    verdict = min(verdicts or ["stale"], key=lambda name: _VERDICT_RANK.get(name, 3))
    problems = [
        f"{row['source']} {row['outcome']}"
        + (f": {row['failed_items']} failed" if row["failed_items"] else "")
        for row in unstored
    ]
    if stale:
        problems.append("no stored yahoo run in the last two days")
    if missing:
        problems.append(f"no bars for {_names(missing)}")
    detail = "; ".join(problems) or "no runs recorded"
    ok = f"{' and '.join(stored)} stored." if stored else ""
    return Health(
        detail=detail,
        message=Message(
            actions=(),
            attachment=None,
            chart=None,
            click=run_url,
            kind="health",
            message=_fit(
                [f"{detail}.", *([ok] if ok else [])],
                limit=PUSH_BYTES,
                max_lines=PUSH_LINES,
            ),
            priority=HEALTH_PRIORITY,
            signals=(),
            tags=("warning",),
            title=f"Market data: nightly {verdict}",
        ),
        state="unhealthy",
    )


def health_change(previous: str | None, health: Health) -> Message | None:
    """Return the message a change of state earns, or none when it is unchanged.

    :param previous: The recorded state, or none before any.
    :param health: The state now.
    :returns: The message; a first healthy reading earns none.
    """
    if health.state == "unhealthy":
        return health.message if previous != "unhealthy" else None
    return health.message if previous == "unhealthy" else None


def build_alert_rows(
    message: Message, *, ntfy_id: str, sent: datetime.datetime
) -> polars.DataFrame:
    """Return the `alerts` rows a sent message earns, one per signal it named."""
    ids = message.signals or ("health",)
    return polars.DataFrame(
        {
            "id": list(ids),
            "kind": [message.kind] * len(ids),
            "message": [ntfy_id] * len(ids),
            "sent": [sent] * len(ids),
            "title": [message.title] * len(ids),
        },
        schema=ALERTS,
    )


def keep_complete_bars(
    bars: polars.DataFrame, *, timeframe: str, today: datetime.date
) -> polars.DataFrame:
    """Drop bars with no price, and weekly or monthly ones not ended by `today`."""
    day = polars.col("day")
    end = (
        day.dt.offset_by("6d")
        if timeframe == "w"
        else day.dt.month_end()
        if timeframe == "m"
        else day
    )
    priced = bars.filter(
        polars.col("close").is_finite(),
        polars.col("high").is_finite(),
        polars.col("low").is_finite(),
    )
    return priced.filter(end.lt(today)) if timeframe != "d" else priced


def chart_is_sound(bars: polars.DataFrame) -> bool:
    """Return whether the bars can show a chart: enough of them, most with a range.

    Some instruments, futures above all, carry many flat or empty bars; a chart
    of them shows candles that are not there, so the push goes as text.
    """
    ranged = bars.filter(polars.col("high").gt(polars.col("low"))).height
    return bars.height >= MIN_CHART_BARS and ranged * 2 >= bars.height
