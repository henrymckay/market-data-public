import json
import urllib.parse

import pytest

from market_data.code import error, transform
from market_data.code.adapt import ntfy
from pytest_ import ntfy_stub

TOPIC = "md-secret-topic-xyz"


def _message(**changes):
    values = {
        "actions": (transform.Action(label="Chart", url="https://site/?view=ticker"),),
        "attachment": "nvda-w.png",
        "chart": None,
        "click": "https://site/?view=ticker",
        "kind": "push",
        "message": "line one\nline two ü",
        "priority": 4,
        "signals": ("a",),
        "tags": ("chart_with_upwards_trend", "stock"),
        "title": "NVDA weekly: first higher high (A)",
    }
    return transform.Message(**(values | changes))


def _constants(stub, *, waits=(5.0, 20.0)):
    return ntfy.Constants(base_url=stub.url, pause=1.0, retry_waits=waits, timeout=2.0)


def test_when_a_text_message_is_sent_then_json_goes_to_the_root_with_every_field():
    with ntfy_stub.Stub() as stub:
        ntfy_id = ntfy.send_message(
            _message(), None, constants=_constants(stub), topic=TOPIC
        )

    [seen] = stub.seen
    body = json.loads(seen.body)
    assert (ntfy_id, seen.method, seen.path) == ("abc123", "POST", "/")
    assert body == {
        "topic": TOPIC,
        "title": "NVDA weekly: first higher high (A)",
        "message": "line one\nline two ü",
        "tags": ["chart_with_upwards_trend", "stock"],
        "priority": 4,
        "click": "https://site/?view=ticker",
        "actions": [
            {"action": "view", "label": "Chart", "url": "https://site/?view=ticker"}
        ],
    }
    assert "authorization" not in seen.headers


def test_when_an_image_is_sent_then_the_png_is_put_with_its_text_in_the_query():
    with ntfy_stub.Stub() as stub:
        ntfy.send_message(
            _message(), b"\x89PNGdata", constants=_constants(stub), topic=TOPIC
        )

    [seen] = stub.seen
    link = urllib.parse.urlparse(seen.path)
    query = urllib.parse.parse_qs(link.query)
    assert (seen.method, link.path, seen.body) == ("PUT", f"/{TOPIC}", b"\x89PNGdata")
    assert seen.headers["filename"] == "nvda-w.png"
    assert query["message"] == ["line one\nline two ü"]
    assert query["title"] == ["NVDA weekly: first higher high (A)"]
    assert (query["priority"], query["tags"]) == (
        ["4"],
        ["chart_with_upwards_trend,stock"],
    )
    assert json.loads(query["actions"][0])[0]["label"] == "Chart"
    assert "authorization" not in seen.headers


def test_when_the_server_fails_then_it_is_tried_again_after_each_wait():
    waits: list[float] = []
    with ntfy_stub.Stub([503, 429]) as stub:
        ntfy_id = ntfy.send_message(
            _message(),
            None,
            constants=_constants(stub),
            sleep=waits.append,
            topic=TOPIC,
        )

    assert (ntfy_id, waits, len(stub.seen)) == ("abc123", [5.0, 20.0], 3)


def test_when_every_try_fails_then_send_error_names_no_address():
    waits: list[float] = []
    with (
        ntfy_stub.Stub([500, 500, 500]) as stub,
        pytest.raises(error.SendError) as raised,
    ):
        ntfy.send_message(
            _message(),
            None,
            constants=_constants(stub),
            sleep=waits.append,
            topic=TOPIC,
        )

    assert "3 tries" in str(raised.value)
    assert TOPIC not in str(raised.value)
    assert "127.0.0.1" not in str(raised.value)
    assert waits == [5.0, 20.0]


def test_when_the_request_is_refused_then_it_is_not_tried_again():
    waits: list[float] = []
    with (
        ntfy_stub.Stub([400]) as stub,
        pytest.raises(error.SendError, match="HTTP 400"),
    ):
        ntfy.send_message(
            _message(),
            None,
            constants=_constants(stub),
            sleep=waits.append,
            topic=TOPIC,
        )

    assert waits == []
    assert len(stub.seen) == 1


def test_when_nothing_listens_then_send_error_follows_the_waits():
    waits: list[float] = []
    constants = ntfy.Constants(
        base_url="http://127.0.0.1:9", pause=0, retry_waits=(1.0,), timeout=0.5
    )

    with pytest.raises(error.SendError) as raised:
        ntfy.send_message(
            _message(), None, constants=constants, sleep=waits.append, topic=TOPIC
        )

    assert waits == [1.0]
    assert TOPIC not in str(raised.value)


def test_when_the_constants_are_read_then_they_hold_the_plans_numbers():
    constants = ntfy.read_constants()

    assert (
        constants.base_url,
        constants.timeout,
        constants.retry_waits,
        constants.pause,
    ) == (
        "https://ntfy.sh",
        10.0,
        (5.0, 20.0),
        1.0,
    )
