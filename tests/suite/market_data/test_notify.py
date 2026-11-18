import datetime

import polars
import pytest

from market_data.code import error, operate
from market_data.code.adapt import rules as rules_adapter
from pytest_ import alerting, fake

HOUR = datetime.timedelta(hours=1)


class Channel:
    """A recording sender that fails the titles it is told to."""

    def __init__(self, *, refuse=(), refuse_images=False):
        self.refuse, self.refuse_images = set(refuse), refuse_images
        self.sent: list[tuple[str, bool]] = []

    def __call__(self, message, image):
        if message.title in self.refuse or (image and self.refuse_images):
            raise error.SendError("refused")
        self.sent.append((message.title, image is not None))
        return f"id{len(self.sent)}"


def _render(request, bars, pivots):
    return b"\x89PNG"


def _failing_render(request, bars, pivots):
    raise error.ChartError("no chart")


def _healthy_runs():
    return alerting.runs_of(
        ("yahoo", "stored", 0, HOUR),
        ("signals", "stored", 0, HOUR),
        ("metrics", "stored", 0, HOUR),
    )


@pytest.fixture
def rules():
    return rules_adapter.read_rules()


@pytest.fixture
def ledger():
    return fake.AlertsLedger(
        runs=_healthy_runs(),
        signals=alerting.signals_of(
            alerting.signal("NVDA"),
            alerting.signal("AMD", grade="B", score=2),
            alerting.signal("OLD", known=datetime.date(2026, 11, 1)),
        ),
        stats=alerting.stats_of(alerting.stat()),
        structure=alerting.structure_of(("NVDA", "m", "up")),
        tickers=alerting.tickers_of(
            ("NVDA", "stock"), ("AMD", "stock"), ("OLD", "stock")
        ),
    )


def _run(ledger, rules, *, channel=None, render=_render):
    channel = channel or Channel()
    planned = operate.plan_alerts(
        now=lambda: alerting.NOW, rules=rules, run_url="https://run", store=ledger
    )
    results = operate.send_alerts(
        planned,
        now=lambda: alerting.NOW,
        pause=lambda: None,
        render=render,
        send=channel,
        store=ledger,
    )
    return channel, results


def test_when_notify_runs_then_one_push_and_one_digest_go_and_rows_are_appended(
    ledger, rules
):
    channel, results = _run(ledger, rules)

    assert [(result.kind, result.status) for result in results] == [
        ("push", "sent"),
        ("digest", "sent"),
    ]
    assert channel.sent == [
        ("NVDA weekly: first higher high (A)", True),
        ("Stocks: 2 signals on 17 Nov 2026, 1 graded A", False),
    ]
    rows = polars.concat(ledger.alerts)
    assert sorted(rows.get_column("id").unique().to_list()) == [
        "AMD|w|break_up|2026-11-09",
        "NVDA|w|break_up|2026-11-09",
    ]


def test_when_notify_runs_twice_then_the_second_run_sends_nothing(ledger, rules):
    _run(ledger, rules)

    channel, results = _run(ledger, rules)

    assert channel.sent == []
    assert results == ()


def test_when_the_channel_refuses_a_message_then_its_signals_get_no_row(ledger, rules):
    _channel, results = _run(
        ledger, rules, channel=Channel(refuse={"NVDA weekly: first higher high (A)"})
    )

    assert [result.status for result in results] == ["failed", "sent"]
    assert polars.concat(ledger.alerts).get_column("kind").unique().to_list() == [
        "digest"
    ]


def test_when_the_image_is_refused_then_the_push_goes_as_text(ledger, rules):
    channel, _ = _run(ledger, rules, channel=Channel(refuse_images=True))

    assert channel.sent[0] == ("NVDA weekly: first higher high (A)", False)


def test_when_the_chart_cannot_be_drawn_then_the_push_goes_as_text(ledger, rules):
    channel, results = _run(ledger, rules, render=_failing_render)

    assert channel.sent[0][1] is False
    assert results[0].status == "sent"


def test_when_the_signals_stage_failed_then_only_health_is_considered(ledger, rules):
    ledger.runs = alerting.runs_of(
        ("yahoo", "stored", 0, HOUR),
        ("signals", "failed", 0, HOUR),
        ("metrics", "stored", 0, HOUR),
    )

    _channel, results = _run(ledger, rules)

    assert [result.kind for result in results] == ["health"]
    assert ledger.states == ["unhealthy"]


def test_when_health_changes_then_one_message_goes_and_the_state_is_recorded(
    ledger, rules
):
    ledger.runs = alerting.runs_of(
        ("yahoo", "stored", 0, 25 * HOUR),
        ("yahoo", "partial", 9, HOUR),
        ("signals", "stored", 0, HOUR),
    )

    _, first = _run(ledger, rules)
    _, second = _run(ledger, rules)

    assert next(result.kind for result in first) == "health"
    assert "health" not in [result.kind for result in second]
    assert ledger.states == ["unhealthy"]


def test_when_the_pipeline_recovers_then_a_healthy_again_message_goes(ledger, rules):
    ledger.state = "unhealthy"

    _, results = _run(ledger, rules)

    assert results[0].title == "Market data: healthy again"
    assert ledger.states == ["healthy"]


def test_when_the_health_message_is_refused_then_the_state_is_not_recorded(
    ledger, rules
):
    ledger.state = "unhealthy"

    _run(ledger, rules, channel=Channel(refuse={"Market data: healthy again"}))

    assert ledger.states == []


def test_when_the_first_reading_is_healthy_then_the_state_is_recorded_silently(
    ledger, rules
):
    _, results = _run(ledger, rules)

    assert "health" not in [result.kind for result in results]
    assert ledger.states == ["healthy"]


def test_when_only_health_is_planned_then_no_signal_is_read(ledger, rules):
    ledger.state = "unhealthy"

    planned = operate.plan_health(now=lambda: alerting.NOW, run_url=None, store=ledger)

    assert [message.kind for message in planned.messages] == ["health"]
