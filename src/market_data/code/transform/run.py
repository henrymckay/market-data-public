"""The run record and the rule that judges a run's outcome."""

import dataclasses
import datetime
import enum


class Outcome(enum.StrEnum):
    """How a run ended."""

    FAILED = "failed"
    PARTIAL = "partial"
    STORED = "stored"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Run:
    """One execution of a stage, recorded as one manifest row."""

    day: datetime.date
    ended: datetime.datetime
    failed_items: int
    last_day: datetime.date
    outcome: Outcome
    rejected: int
    requests: int
    rows: int
    source: str
    started: datetime.datetime


def judge_outcome(*, answered: int, failed_items: int, tolerance: int) -> Outcome:
    """Judge a run: failed if nothing answered, partial above the tolerance.

    :param answered: Instruments with at least one valid bar.
    :param failed_items: Instruments that answered nothing usable.
    :param tolerance: Failed instruments a night may absorb and still be stored.
    :returns: The run's outcome.
    """
    if answered == 0:
        return Outcome.FAILED
    if failed_items > tolerance:
        return Outcome.PARTIAL
    return Outcome.STORED
