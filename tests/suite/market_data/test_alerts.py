import datetime
import urllib.parse

import polars
import pytest

from market_data.code import transform
from market_data.code.adapt import rules as rules_adapter
from pytest_ import alerting


@pytest.fixture
def packaged():
    return rules_adapter.read_rules()


def _due(packaged, *rows, sent=None, tickers=None, today=alerting.TODAY):
    return transform.select_due(
        rules=packaged,
        sent=sent if sent is not None else alerting.nothing_sent(),
        signals=alerting.signals_of(*rows),
        tickers=tickers
        if tickers is not None
        else alerting.tickers_of(
            ("NVDA", "stock"), ("AMD", "stock"), ("BTC-USD", "crypto")
        ),
        today=today,
    )


def _plan(packaged, *rows, stats=None, structure=None, **kwargs):
    due = _due(packaged, *rows, **kwargs)
    context = transform.attach_context(
        due,
        rules=packaged,
        stats=stats if stats is not None else alerting.stats_of(alerting.stat()),
        structure=structure
        if structure is not None
        else alerting.structure_of(("NVDA", "m", "up")),
    )
    return transform.plan_messages(context, rules=packaged)


def test_when_selecting_due_then_only_recent_wanted_unmuted_unsent_signals_remain(
    packaged,
):
    today = alerting.TODAY
    recent = alerting.signal("NVDA", known=today - datetime.timedelta(days=4))
    old = alerting.signal("AMD", known=today - datetime.timedelta(days=5))
    failure = alerting.signal("NVDA", event="fail_up", day=datetime.date(2026, 11, 2))
    sent = alerting.signal("NVDA", day=datetime.date(2026, 11, 2))
    unknown = alerting.signal("ZZZ")
    muted = packaged.model_copy(
        update={
            "alerts": packaged.alerts.model_copy(
                update={"muted_asset_classes": ("crypto",)}
            )
        }
    )
    coin = alerting.signal("BTC-USD")

    due = _due(
        packaged,
        recent,
        old,
        failure,
        sent,
        unknown,
        sent=polars.DataFrame({"id": [sent["id"]]}),
    )
    unmuted = _due(muted, coin, recent)

    assert due.get_column("id").to_list() == [recent["id"]]
    assert unmuted.get_column("ticker").to_list() == ["NVDA"]


def test_when_the_class_has_enough_signals_then_its_own_base_rate_is_shown(packaged):
    stats = alerting.stats_of(
        alerting.stat(n=412, hit_rate=0.66),
        alerting.stat(asset_class="all", n=900, hit_rate=0.5),
    )

    [push] = _plan(packaged, alerting.signal(), stats=stats)

    assert "Base rate: 66% rose within 13 weeks (n 412); any week 61%." in push.message


def test_when_the_class_has_too_few_signals_then_every_class_is_used_and_said(packaged):
    stats = alerting.stats_of(
        alerting.stat(n=29, hit_rate=0.9),
        alerting.stat(asset_class="all", n=900, hit_rate=0.5),
    )

    [push] = _plan(packaged, alerting.signal(), stats=stats)

    assert "Base rate: 50% rose within 13 weeks (n 900, all classes)" in push.message


def test_when_no_base_rate_exists_then_the_push_says_none_yet(packaged):
    [push] = _plan(packaged, alerting.signal(), stats=alerting.stats_of())

    assert push.message.splitlines()[-1] == "Base rate: none yet."


def test_when_a_signal_is_a_grade_a_break_then_the_push_follows_the_interface(packaged):
    [push] = _plan(packaged, alerting.signal())

    assert push.title == "NVDA weekly: first higher high (A)"
    assert push.message.splitlines() == [
        "Closed 145.30 above the lower high 142.10 (+0.6 ATR) after 4 lower highs.",
        "Invalid below 128.40 (-11.6%). Volume 1.8x. Monthly trend up.",
        "Base rate: 66% rose within 13 weeks (n 412); any week 61%.",
    ]
    assert push.priority == 4
    assert push.tags == ("chart_with_upwards_trend", "stock")
    assert push.signals == ("NVDA|w|break_up|2026-11-09",)
    assert push.attachment == "nvda-w.png"


def test_when_a_push_is_composed_then_its_click_opens_the_ticker_at_the_signal(
    packaged,
):
    [push] = _plan(packaged, alerting.signal("BTC-USD", timeframe="m"))

    assert push.click is not None
    link = urllib.parse.urlparse(push.click)
    query = urllib.parse.parse_qs(link.query)
    assert f"{link.scheme}://{link.netloc}{link.path}" == packaged.alerts.site_url
    assert query == {
        "view": ["ticker"],
        "t": ["BTC-USD"],
        "tf": ["m"],
        "range": ["Max"],
        "sig": ["2026-11-09.break_up"],
    }
    assert [(action.label, action.url) for action in push.actions[:1]] == [
        ("Chart", push.click)
    ]


def test_when_a_push_is_composed_then_a_second_button_opens_the_signals_screen(
    packaged,
):
    [push] = _plan(packaged, alerting.signal())

    label, url = push.actions[1].label, push.actions[1].url
    assert label == "All signals"
    assert urllib.parse.parse_qs(urllib.parse.urlparse(url).query) == {
        "view": ["signals"],
        "cls": ["stock"],
        "day": ["2026-11-17"],
    }


@pytest.mark.parametrize(
    ("event", "direction", "words", "first"),
    [
        ("break_up", "up", "first higher high", "Closed"),
        ("confirm_up", "up", "first higher low", "Higher low"),
        ("break_down", "down", "first lower low", "Closed"),
        ("confirm_down", "down", "first lower high", "Lower high"),
    ],
)
def test_when_each_event_is_pushed_then_the_owners_words_name_it(
    packaged, event, direction, words, first
):
    [push] = _plan(
        packaged,
        alerting.signal(event=event, direction=direction, stop=160.0),
        stats=alerting.stats_of(alerting.stat(event=event)),
    )

    assert push.title == f"NVDA weekly: {words} (A)"
    assert push.message.startswith(first)
    assert ("Invalid above" if direction == "down" else "Invalid below") in push.message
    assert ("fell" if direction == "down" else "rose") in push.message
    assert push.tags[0] == f"chart_with_{direction}wards_trend"


def test_when_a_ticker_and_price_are_long_then_the_push_stays_within_its_bounds(
    packaged,
):
    long = alerting.signal(
        "^STOXX50E", close=1234567.891, level=1234000.1, stop=987654.3, trend_swings=12
    )
    tickers = alerting.tickers_of(("^STOXX50E", "index"))

    [push] = _plan(packaged, long, tickers=tickers)

    assert len(push.title.encode()) <= 60
    assert len(push.message.splitlines()) <= 4
    assert len(push.message.encode()) <= 300


def test_when_a_push_overflows_its_bounds_then_it_is_cut_to_them(packaged):
    ticker = "X" * 40
    overflowing = alerting.signal(
        ticker, close=1.234567e40, level=1.23e40, stop=9.87e39, trend_swings=12
    )

    [push] = _plan(
        packaged,
        overflowing,
        tickers=alerting.tickers_of((ticker, "index")),
        structure=alerting.structure_of((ticker, "m", "up")),
    )

    assert push.title.endswith("...")
    assert len(push.title.encode()) <= 60
    assert len(push.message.splitlines()) < 3
    assert len(push.message.encode()) <= 300


def test_when_a_signal_has_no_volume_then_the_push_leaves_volume_out(packaged):
    [push] = _plan(packaged, alerting.signal(volume_ratio=None))

    assert (
        push.message.splitlines()[1]
        == "Invalid below 128.40 (-11.6%). Monthly trend up."
    )


def test_when_the_rules_send_a_failure_then_its_push_names_the_stop(packaged):
    rules = packaged.model_copy(
        update={
            "alerts": packaged.alerts.model_copy(
                update={"events": (*packaged.alerts.events, "fail_up")}
            )
        }
    )

    [push] = _plan(rules, alerting.signal(event="fail_up"))

    assert push.title == "NVDA weekly: failed first higher high (A)"
    assert push.message.splitlines()[0] == "Closed beyond the stop 142.10."


@pytest.mark.parametrize(
    ("value", "asset_class", "written"),
    [
        (1.08342, "fx", "1.0834"),
        (154.1234, "fx", "154.123"),
        (0.51234, "crypto", "0.5123"),
        (98765.432, "stock", "98,765.43"),
    ],
)
def test_when_a_price_is_formatted_then_its_places_follow_its_class(
    value, asset_class, written
):
    assert transform.format_price(value, asset_class) == written


def test_when_one_digest_line_is_longer_than_the_digest_then_it_folds_into_the_count(
    packaged,
):
    ticker = "Y" * 1600
    row = alerting.signal(ticker, grade="B", score=2)

    [digest] = _plan(packaged, row, tickers=alerting.tickers_of((ticker, "stock")))

    assert digest.message == "+1 more on the Signals screen"
    assert digest.signals == (row["id"],)


def test_when_more_signals_than_the_cap_are_due_then_the_rest_go_in_the_digest(
    packaged,
):
    rows = [
        alerting.signal(f"T{index:02d}", score=3 + index % 3, margin_atr=0.1 + index)
        for index in range(13)
    ]
    tickers = alerting.tickers_of(*((row["ticker"], "stock") for row in rows))  # type: ignore[arg-type]

    messages = _plan(packaged, *rows, tickers=tickers)

    pushes = [message for message in messages if message.kind == "push"]
    [digest] = [message for message in messages if message.kind == "digest"]
    assert len(pushes) == 10
    assert len(digest.signals) == 13
    lowest = {pushed.signals[0] for pushed in pushes}
    left_out = set(digest.signals) - lowest
    assert {row["id"] for row in rows if row["score"] == 3} >= left_out


def test_when_scores_tie_then_the_longer_timeframe_and_the_wider_margin_come_first(
    packaged,
):
    daily = alerting.signal("AMD", timeframe="d", score=4, margin_atr=9.0)
    weekly = alerting.signal("NVDA", timeframe="w", score=4, margin_atr=0.5)
    wider = alerting.signal("BTC-USD", timeframe="w", score=4, margin_atr=0.9)
    tickers = alerting.tickers_of(
        ("NVDA", "stock"), ("AMD", "stock"), ("BTC-USD", "stock")
    )

    messages = _plan(packaged, daily, weekly, wider, tickers=tickers)

    assert [message.signals[0].split("|")[0] for message in messages[:3]] == [
        "BTC-USD",
        "NVDA",
        "AMD",
    ]


def test_when_a_class_has_a_grade_b_signal_then_it_gets_a_digest_with_its_lines(
    packaged,
):
    best = alerting.signal("NVDA")
    other = alerting.signal(
        "AMD",
        grade="B",
        score=2,
        timeframe="d",
        day=datetime.date(2026, 11, 17),
        event="confirm_down",
        direction="down",
        level=151.2,
        stop=151.2,
        margin_atr=1.4,
    )
    stats = alerting.stats_of(
        alerting.stat(),
        alerting.stat(event="confirm_down", timeframe="d", horizon=20, hit_rate=0.58),
    )

    messages = _plan(packaged, best, other, stats=stats)

    [digest] = [message for message in messages if message.kind == "digest"]
    assert digest.title == "Stocks: 2 signals on 17 Nov 2026, 1 graded A"
    assert digest.message.splitlines() == [
        "A NVDA W first higher high 142.10, base 66% vs 61%",
        "B AMD D first lower high 151.20, base 58% vs 61%",
    ]
    assert digest.priority == 3
    assert [action.label for action in digest.actions] == ["NVDA", "AMD"]
    assert urllib.parse.parse_qs(urllib.parse.urlparse(digest.click or "").query) == {
        "view": ["signals"],
        "cls": ["stock"],
        "day": ["2026-11-17"],
    }


def test_when_a_digest_would_only_repeat_the_pushes_then_none_is_sent(packaged):
    messages = _plan(packaged, alerting.signal())

    assert [message.kind for message in messages] == ["push"]


def test_when_a_class_has_only_grade_c_signals_then_nothing_is_sent_for_it(packaged):
    messages = _plan(packaged, alerting.signal(grade="C", score=1))

    assert messages == ()


def test_when_a_digest_has_too_many_lines_then_the_last_ones_fold_into_a_count(
    packaged,
):
    rows = [
        alerting.signal(f"T{index:02d}", grade="B", score=2, margin_atr=index / 10)
        for index in range(30)
    ]
    rows.append(alerting.signal("CCC", grade="C", score=1))
    tickers = alerting.tickers_of(*((row["ticker"], "stock") for row in rows))  # type: ignore[arg-type]

    [digest] = _plan(packaged, *rows, tickers=tickers)

    lines = digest.message.splitlines()
    assert len(lines) <= 12
    assert len(digest.message.encode()) <= 1500
    assert lines[-1] == "+19 more, +1 graded C on the Signals screen"
    assert len(digest.signals) == 30
    assert len(digest.title) <= 60


def test_when_nothing_is_folded_then_the_last_line_counts_grade_c_only(packaged):
    rows = [
        alerting.signal("NVDA", grade="B", score=2),
        alerting.signal("AMD", grade="C", score=1),
        alerting.signal("BTC-USD", grade="C", score=1),
    ]
    tickers = alerting.tickers_of(
        ("NVDA", "stock"), ("AMD", "stock"), ("BTC-USD", "stock")
    )

    [digest] = _plan(packaged, *rows, tickers=tickers)

    assert digest.message.splitlines()[-1] == "+2 graded C on the Signals screen"
    assert digest.signals == ("NVDA|w|break_up|2026-11-09",)


def _health(runs, *, missing=(), url="https://example.test/run/1", hours=0):
    now = alerting.NOW + datetime.timedelta(hours=hours)
    status = transform.build_status(runs, missing=missing, now=now)
    return transform.build_health(
        missing=missing, run_url=url, runs=runs, status=status
    )


def test_when_a_source_is_partial_then_the_health_message_names_what_failed():
    runs = alerting.runs_of(
        ("yahoo", "stored", 0, datetime.timedelta(hours=25)),
        ("yahoo", "partial", 7, datetime.timedelta(hours=1)),
        ("signals", "stored", 0, datetime.timedelta(hours=1)),
        ("metrics", "stored", 0, datetime.timedelta(hours=1)),
    )

    health = _health(runs, missing=("ABC", "DEF", "GHI", "JKL"))

    assert health.state == "unhealthy"
    assert health.message.title == "Market data: nightly partial"
    assert health.message.message == (
        "yahoo partial: 7 failed; no bars for ABC, DEF, GHI +1.\n"
        "metrics and signals stored."
    )
    assert health.message.priority == 5
    assert health.message.click == "https://example.test/run/1"


def test_when_a_night_never_ran_then_the_verdict_is_stale():
    runs = alerting.runs_of(("yahoo", "stored", 0, datetime.timedelta(hours=60)))

    health = _health(runs)

    assert health.state == "unhealthy"
    assert health.message.title == "Market data: nightly stale"
    assert "no stored yahoo run in the last two days" in health.message.message


def test_when_every_stage_stored_then_the_health_message_is_the_recovery():
    runs = alerting.runs_of(("yahoo", "stored", 0, datetime.timedelta(hours=1)))

    health = _health(runs)

    assert health.state == "healthy"
    assert (health.message.title, health.message.priority) == (
        "Market data: healthy again",
        3,
    )


@pytest.mark.parametrize(
    ("previous", "unhealthy", "sends"),
    [
        (None, True, True),
        ("healthy", True, True),
        ("unhealthy", True, False),
        (None, False, False),
        ("healthy", False, False),
        ("unhealthy", False, True),
    ],
)
def test_when_the_state_is_judged_then_a_message_goes_only_on_a_change(
    previous, unhealthy, sends
):
    age = datetime.timedelta(hours=60 if unhealthy else 1)
    health = _health(alerting.runs_of(("yahoo", "stored", 0, age)))

    change = transform.health_change(previous, health)

    assert (change is not None) is sends


def test_when_the_latest_signals_run_failed_then_signals_are_not_stored():
    stored = alerting.runs_of(("signals", "stored", 0, datetime.timedelta(hours=2)))
    failed = alerting.runs_of(
        ("signals", "stored", 0, datetime.timedelta(hours=26)),
        ("signals", "failed", 0, datetime.timedelta(hours=2)),
    )

    assert transform.signals_stored(stored)
    assert not transform.signals_stored(failed)


def test_when_a_message_is_sent_then_one_alerts_row_names_each_signal():
    [push] = _plan_without_context()

    rows = transform.build_alert_rows(push, ntfy_id="abc", sent=alerting.NOW)

    assert rows.to_dicts() == [
        {
            "id": "NVDA|w|break_up|2026-11-09",
            "kind": "push",
            "message": "abc",
            "sent": alerting.NOW,
            "title": "NVDA weekly: first higher high (A)",
        }
    ]


def _plan_without_context():
    packaged = rules_adapter.read_rules()
    return _plan(packaged, alerting.signal())


@pytest.mark.parametrize(
    ("timeframe", "day", "kept"),
    [
        ("w", "2026-11-16", False),
        ("w", "2026-11-09", True),
        ("m", "2026-10-01", True),
        ("m", "2026-11-01", False),
        ("d", "2026-11-17", True),
    ],
)
def test_when_chart_bars_are_kept_then_unfinished_periods_are_dropped(
    timeframe, day, kept
):
    bars = polars.DataFrame(
        {
            "close": [1.0],
            "day": [datetime.date.fromisoformat(day)],
            "high": [1.0],
            "low": [1.0],
        }
    )

    result = transform.keep_complete_bars(
        bars, timeframe=timeframe, today=alerting.TODAY
    )

    assert (result.height == 1) is kept
