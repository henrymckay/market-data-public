"""Configure logging to standard error, with the MotherDuck token redacted."""

import logging
import sys

_REDACTED = "[redacted]"


class _RedactingFormatter(logging.Formatter):
    """A formatter that never lets a secret reach a line."""

    def __init__(self, *, secret: str | None) -> None:
        """Remember the secret to hide, if any."""
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")
        self._secret = secret

    def format(self, record: logging.LogRecord) -> str:
        """Format the record, then replace any occurrence of the secret."""
        line = super().format(record)
        return line if not self._secret else line.replace(self._secret, _REDACTED)


def configure(*, level: int, secret: str | None) -> None:
    """Route application logs to standard error at the level.

    :param level: The lowest level shown.
    :param secret: A value to replace with a placeholder in every line.
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_RedactingFormatter(secret=secret))
    logging.basicConfig(force=True, handlers=[handler], level=level)
    for dependency in ("httpcore", "httpx", "peewee", "urllib3", "yfinance"):
        logging.getLogger(dependency).setLevel(logging.WARNING)
