"""The notify use case: choose what a night owes, send it and record it."""

import collections.abc
import dataclasses
import datetime
import logging
import typing

import polars

from market_data.code import error, port, transform

_LOGGER = logging.getLogger(__name__)

_CHART_BARS = 80


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Planned:
    """The messages a run would send, and the health state it would record."""

    health: transform.Health
    messages: tuple[transform.Message, ...]
    previous: str | None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Result:
    """What became of one message: its kind, title, signals named and status."""

    kind: str
    signals: int
    status: typing.Literal["sent", "failed"]
    title: str


def _plan_health(
    *,
    now: collections.abc.Callable[[], datetime.datetime],
    run_url: str | None,
    store: port.AlertsStore,
) -> tuple[Planned, polars.DataFrame]:
    """Judge the pipeline and return the plan holding its health message, if any."""
    runs = store.read_runs()
    missing = store.read_missing()
    status = transform.build_status(runs, missing=missing, now=now())
    health = transform.build_health(
        missing=missing, run_url=run_url, runs=runs, status=status
    )
    previous = store.read_alert_state()
    change = transform.health_change(previous, health)
    planned = Planned(
        health=health, messages=(change,) if change else (), previous=previous
    )
    return planned, runs


def plan_health(
    *,
    now: collections.abc.Callable[[], datetime.datetime],
    run_url: str | None,
    store: port.AlertsStore,
) -> Planned:
    """Return the health message the pipeline's state earns, writing nothing.

    :param now: The clock, aware UTC.
    :param run_url: The Actions run's page, for the message's click.
    :param store: Where runs and the recorded state are read.
    :returns: The plan, holding at most the health message.
    """
    return _plan_health(now=now, run_url=run_url, store=store)[0]


def plan_alerts(
    *,
    now: collections.abc.Callable[[], datetime.datetime],
    rules: transform.Rules,
    run_url: str | None,
    store: port.AlertsStore,
) -> Planned:
    """Return every message a night owes, writing nothing.

    The health message comes first. Signals go only when the latest `signals`
    run stored its tables, since otherwise the structure they read is old.

    :param now: The clock, aware UTC; its UTC date is `today`.
    :param rules: The rules.
    :param run_url: The Actions run's page, for the health message's click.
    :param store: Where everything is read.
    :returns: The plan.
    """
    judged, runs = _plan_health(now=now, run_url=run_url, store=store)
    if not transform.signals_stored(runs):
        _LOGGER.warning("The signals stage did not store; sending no signals")
        return judged
    today = now().astimezone(datetime.UTC).date()
    window = datetime.timedelta(days=rules.alerts.window_days)
    due = transform.select_due(
        rules=rules,
        sent=store.read_sent(),
        signals=store.read_signals(today - window),
        tickers=store.read_tickers(),
        today=today,
    )
    context = transform.attach_context(
        due,
        rules=rules,
        stats=store.read_signal_stats(),
        structure=store.read_structure(),
    )
    return dataclasses.replace(
        judged,
        messages=(*judged.messages, *transform.plan_messages(context, rules=rules)),
    )


def _draw(
    message: transform.Message,
    *,
    render: port.Render,
    store: port.AlertsStore,
    today: datetime.date,
) -> bytes | None:
    """Return the push's chart image, or none when it cannot be drawn."""
    request = message.chart
    if request is None:
        return None
    try:
        bars = transform.keep_complete_bars(
            store.read_chart_bars(request.ticker, request.timeframe, _CHART_BARS + 1),
            timeframe=request.timeframe,
            today=today,
        ).tail(_CHART_BARS)
        if not transform.chart_is_sound(bars):
            _LOGGER.warning("Too few bars with a range for %s; no chart", message.title)
            return None
        pivots = store.read_chart_pivots(request.ticker, request.timeframe)
        return render(request, bars, pivots)
    except error.ChartError as failure:
        _LOGGER.warning("No chart for %s: %s", message.title, failure)
        return None


def _deliver(
    message: transform.Message, image: bytes | None, *, send: port.Send
) -> str:
    """Send a message with its image, or as text alone if the image will not go."""
    if image is None:
        return send(message, None)
    try:
        return send(message, image)
    except error.SendError as failure:
        _LOGGER.warning("Sending %s with its chart failed: %s", message.title, failure)
        return send(message, None)


def _record_health(
    planned: Planned,
    results: collections.abc.Sequence[Result],
    *,
    now: collections.abc.Callable[[], datetime.datetime],
    store: port.AlertsStore,
) -> None:
    """Record the health state once its message went, or at once when none is due."""
    health = planned.health
    announced = [result for result in results if result.kind == "health"]
    unchanged = planned.previous == health.state
    delivered = all(result.status == "sent" for result in announced)
    if not unchanged and delivered:
        store.replace_alert_state(
            changed=now(), detail=health.detail, state=health.state
        )


def send_alerts(
    planned: Planned,
    *,
    now: collections.abc.Callable[[], datetime.datetime],
    pause: collections.abc.Callable[[], None],
    render: port.Render,
    send: port.Send,
    store: port.AlertsStore,
) -> tuple[Result, ...]:
    """Send each planned message, append its `alerts` rows and record the health.

    A message the channel refuses gets no `alerts` row, so the next night sends
    its signals again while they are still recent.

    :param planned: What `plan_alerts` returned.
    :param now: The clock, aware UTC.
    :param pause: Waits between two messages.
    :param render: Draws a push's chart.
    :param send: Delivers a message and returns the channel's id for it.
    :param store: Where `alerts` rows and the health state are written.
    :returns: One result per message, in order.
    """
    today = now().astimezone(datetime.UTC).date()
    results: list[Result] = []
    for index, message in enumerate(planned.messages):
        if index:
            pause()
        image = _draw(message, render=render, store=store, today=today)
        try:
            ntfy_id = _deliver(message, image, send=send)
        except error.SendError as failure:
            _LOGGER.error("Could not send %s: %s", message.title, failure)
            status = "failed"
        else:
            store.append_alerts(
                transform.build_alert_rows(message, ntfy_id=ntfy_id, sent=now())
            )
            status = "sent"
        results.append(
            Result(
                kind=message.kind,
                signals=len(message.signals),
                status=status,
                title=message.title,
            )
        )
    _record_health(planned, results, now=now, store=store)
    return tuple(results)
