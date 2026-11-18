"""Configure logging to standard error, with the MotherDuck token redacted."""

import collections.abc
import functools
import logging
import sys

_REDACTED = "[redacted]"


class _RedactingFormatter(logging.Formatter):
    """A formatter that never lets a secret reach a line."""

    def __init__(self, *, secrets: collections.abc.Iterable[str]) -> None:
        """Remember the secrets to hide."""
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")
        self._secrets = tuple(secrets)

    def format(self, record: logging.LogRecord) -> str:
        """Format the record, then replace any occurrence of a secret."""
        return functools.reduce(
            lambda line, secret: line.replace(secret, _REDACTED),
            self._secrets,
            super().format(record),
        )


def configure(*, level: int, secrets: collections.abc.Iterable[str]) -> None:
    """Route application logs to standard error at the level.

    :param level: The lowest level shown.
    :param secrets: Values to replace with a placeholder in every line.
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_RedactingFormatter(secrets=secrets))
    logging.basicConfig(force=True, handlers=[handler], level=level)
    for dependency in ("httpcore", "httpx", "peewee", "urllib3", "yfinance"):
        logging.getLogger(dependency).setLevel(logging.WARNING)
