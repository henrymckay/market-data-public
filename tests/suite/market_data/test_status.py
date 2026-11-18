import datetime

import polars
import pytest

from market_data.code import transform

_NOW = datetime.datetime(2026, 11, 17, 12, 0, tzinfo=datetime.UTC)


def _runs(*rows):
    return polars.DataFrame(
        [
            {
                "ended": ended,
                "failed_items": failed,
                "outcome": outcome,
                "source": source,
            }
            for ended, failed, outcome, source in rows
        ],
        schema={
            "ended": polars.Datetime(time_zone="UTC"),
            "failed_items": polars.Int64,
            "outcome": polars.String,
            "source": polars.String,
        },
    )


def _hours_ago(hours):
    return _NOW - datetime.timedelta(hours=hours)


def _value(status, key):
    return dict(status.rows)[key]


def test_when_the_latest_runs_are_stored_and_recent_then_status_is_healthy():
    runs = _runs(
        (_hours_ago(10), 0, "stored", "yahoo"),
        (_hours_ago(9), 0, "stored", "metrics"),
    )

    status = transform.build_status(runs, missing=(), now=_NOW)

    assert status.healthy
    assert _value(status, "outcome") == "stored"
    assert _value(status, "age_hours") == "9.0"
    assert _value(status, "failed_items") == "0"
    assert _value(status, "missing") == ""


def test_when_the_last_run_was_partial_then_status_is_unhealthy_and_names_missing():
    runs = _runs(
        (_hours_ago(10), 1, "partial", "yahoo"),
        (_hours_ago(9), 1, "partial", "metrics"),
    )

    status = transform.build_status(runs, missing=("ZZZZ", "QQQQ"), now=_NOW)

    assert not status.healthy
    assert _value(status, "outcome") == "partial"
    assert _value(status, "missing") == "ZZZZ;QQQQ"


def test_when_the_last_stored_yahoo_run_is_over_two_days_old_then_it_is_stale():
    runs = _runs((_hours_ago(49), 0, "stored", "yahoo"))

    status = transform.build_status(runs, missing=(), now=_NOW)

    assert not status.healthy
    assert _value(status, "stale") == "true"


def test_when_a_failed_run_follows_an_old_stored_one_then_it_is_unhealthy():
    runs = _runs(
        (_hours_ago(30), 0, "stored", "yahoo"),
        (_hours_ago(6), 90, "failed", "yahoo"),
    )

    status = transform.build_status(runs, missing=(), now=_NOW)

    assert not status.healthy
    assert _value(status, "stale") == "false"


@pytest.mark.parametrize("missing", [(), ("ZZZZ",)])
def test_when_no_run_exists_then_status_is_unhealthy(missing):
    status = transform.build_status(_runs(), missing=missing, now=_NOW)

    assert not status.healthy
    assert _value(status, "outcome") == "none"


def test_when_the_signals_stage_failed_then_the_job_is_unhealthy():
    runs = _runs(
        (_hours_ago(10), 0, "stored", "yahoo"),
        (_hours_ago(9), 0, "failed", "signals"),
        (_hours_ago(8), 0, "stored", "metrics"),
    )

    status = transform.build_status(runs, missing=[], now=_NOW)

    assert status.healthy is False


def test_when_every_stage_including_signals_stored_then_healthy():
    runs = _runs(
        (_hours_ago(10), 0, "stored", "yahoo"),
        (_hours_ago(9), 0, "stored", "signals"),
        (_hours_ago(8), 0, "stored", "metrics"),
    )

    status = transform.build_status(runs, missing=[], now=_NOW)

    assert status.healthy is True
