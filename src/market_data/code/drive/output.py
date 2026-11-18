"""Render a run's manifest row as CSV on standard output."""

import collections.abc
import sys

import polars

from market_data.code import transform

_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def build_manifest(runs: collections.abc.Sequence[transform.Run]) -> polars.DataFrame:
    """Return the runs as a frame of one row each, in the manifest's columns."""
    return polars.DataFrame(
        {
            "day": [run.day for run in runs],
            "ended": [run.ended for run in runs],
            "failed_items": [run.failed_items for run in runs],
            "last_day": [run.last_day for run in runs],
            "outcome": [str(run.outcome) for run in runs],
            "rejected": [run.rejected for run in runs],
            "requests": [run.requests for run in runs],
            "rows": [run.rows for run in runs],
            "source": [run.source for run in runs],
            "started": [run.started for run in runs],
        }
    )


def display_manifest(*runs: transform.Run) -> None:
    """Write the runs' manifest rows, under one header, to standard output."""
    sys.stdout.write(build_manifest(runs).write_csv(datetime_format=_TIME_FORMAT))


def display_status(status: transform.Status) -> None:
    """Write the status as `key,value` rows to standard output."""
    sys.stdout.write(
        polars.DataFrame(status.rows, schema=["key", "value"], orient="row").write_csv()
    )
