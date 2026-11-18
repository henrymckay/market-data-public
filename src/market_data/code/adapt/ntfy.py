"""Send messages to the owner's ntfy.sh topic with the standard library."""

import dataclasses
import json
import logging
import time
import typing
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from importlib import resources

import yaml

from market_data.code import error, transform

_LOGGER = logging.getLogger(__name__)

_RETRY_FROM_STATUS = 500
_TOO_MANY = 429
_AGENT = "market-data-monitor"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Constants:
    """The channel's per-source constants, from the package's YAML."""

    base_url: str
    pause: float
    retry_waits: tuple[float, ...]
    timeout: float


def read_constants() -> Constants:
    """Return the constants in `data/adapt/ntfy.yaml`."""
    document = yaml.safe_load(
        resources.files("market_data").joinpath("data/adapt/ntfy.yaml").read_text()
    )
    return Constants(
        base_url=document["base-url"],
        pause=float(document["pause"]),
        retry_waits=tuple(float(wait) for wait in document["retry-waits"]),
        timeout=float(document["timeout"]),
    )


class _Retry(Exception):  # noqa: N818
    """A failure worth trying again, with a short reason that holds no address."""


def _actions(message: transform.Message) -> list[dict[str, str]]:
    """Return the message's buttons as ntfy writes them."""
    return [
        {"action": "view", "label": action.label, "url": action.url}
        for action in message.actions
    ]


def _text_request(
    message: transform.Message, *, constants: Constants, topic: str
) -> urllib.request.Request:
    """Return the JSON POST that publishes a message as text."""
    body: dict[str, object] = {
        "topic": topic,
        "title": message.title,
        "message": message.message,
        "tags": list(message.tags),
        "priority": message.priority,
    }
    if message.click:
        body["click"] = message.click
    if message.actions:
        body["actions"] = _actions(message)
    return urllib.request.Request(
        f"{constants.base_url}/",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": _AGENT},
        method="POST",
    )


def _image_request(
    message: transform.Message, image: bytes, *, constants: Constants, topic: str
) -> urllib.request.Request:
    """Return the PUT that publishes a message with its image attached."""
    query = {
        "message": message.message,
        "priority": str(message.priority),
        "tags": ",".join(message.tags),
        "title": message.title,
    }
    if message.click:
        query["click"] = message.click
    if message.actions:
        query["actions"] = json.dumps(_actions(message), separators=(",", ":"))
    return urllib.request.Request(
        f"{constants.base_url}/{urllib.parse.quote(topic, safe='')}"
        f"?{urllib.parse.urlencode(query)}",
        data=image,
        headers={
            "Content-Type": "image/png",
            "Filename": message.attachment or "chart.png",
            "User-Agent": _AGENT,
        },
        method="PUT",
    )


def _attempt(request: urllib.request.Request, *, timeout: float) -> str:
    """Send the request once and return the message id ntfy answers with.

    :raises SendError: With a fixed text, never the request's address.
    """
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            answer: object = json.load(response)
    except urllib.error.HTTPError as failure:
        code = failure.code
        failure.close()
        if code == _TOO_MANY or code >= _RETRY_FROM_STATUS:
            raise _Retry(f"HTTP {code}") from None
        raise error.SendError(f"ntfy refused the message with HTTP {code}") from None
    except (OSError, ValueError) as failure:
        raise _Retry(type(failure).__name__) from None
    ntfy_id = (
        typing.cast("dict[str, object]", answer).get("id")
        if isinstance(answer, dict)
        else None
    )
    if not isinstance(ntfy_id, str) or not ntfy_id:
        raise error.SendError("ntfy answered without a message id")
    return ntfy_id


def send_message(
    message: transform.Message,
    image: bytes | None,
    *,
    constants: Constants,
    sleep: Callable[[float], None] = time.sleep,
    topic: str,
) -> str:
    """Publish a message to the topic, trying again after each wait on a fault.

    A message with an image goes as a PUT whose text rides in the query, any
    other as a JSON POST. A timeout, a connection fault, a 429 or a 5xx is
    tried again after each of `retry_waits` seconds; any other refusal is not.

    :param message: What to send.
    :param image: A PNG to attach, or none.
    :param constants: The channel's address, timeout and waits.
    :param sleep: Waits between tries.
    :param topic: The secret topic.
    :returns: ntfy's id for the message.
    :raises SendError: If every try failed; the text never holds the address.
    """
    request = (
        _text_request(message, constants=constants, topic=topic)
        if image is None
        else _image_request(message, image, constants=constants, topic=topic)
    )
    reason = ""
    for wait in (*constants.retry_waits, None):
        try:
            return _attempt(request, timeout=constants.timeout)
        except _Retry as failure:
            reason = str(failure)
        if wait is not None:
            _LOGGER.warning("ntfy failed (%s); trying again in %.0f s", reason, wait)
            sleep(wait)
    raise error.SendError(
        f"ntfy did not accept the message after {len(constants.retry_waits) + 1} "
        f"tries (last: {reason})"
    )
