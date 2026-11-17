"""Render a run's manifest row as CSV on standard output."""

import sys

import polars

from market_data.code import transform

_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def build_manifest(run: transform.Run) -> polars.DataFrame:
    """Return the run as a one-row frame, columns in the manifest's order."""
    return polars.DataFrame(
        {
            "day": [run.day],
            "ended": [run.ended],
            "failed_items": [run.failed_items],
            "last_day": [run.last_day],
            "outcome": [str(run.outcome)],
            "rejected": [run.rejected],
            "requests": [run.requests],
            "rows": [run.rows],
            "source": [run.source],
            "started": [run.started],
        }
    )


def display_manifest(run: transform.Run) -> None:
    """Write the run's manifest row, with its header, to standard output."""
    sys.stdout.write(build_manifest(run).write_csv(datetime_format=_TIME_FORMAT))
