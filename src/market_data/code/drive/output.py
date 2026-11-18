"""Render a run's manifest row as CSV on standard output."""

import collections.abc
import sys

import polars

from market_data.code import operate, transform

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


def display_changes(changes: transform.Changes) -> None:
    """Write the counts of tickers a universe sync added and removed as CSV."""
    sys.stdout.write(
        polars.DataFrame(
            {"added": [len(changes.added)], "removed": [len(changes.removed)]}
        ).write_csv()
    )


def display_rates(rates: polars.DataFrame, *, table: bool) -> None:
    """Write the base rates as CSV, or as columns aligned for a person.

    :param rates: The rates, one row per event, timeframe and horizon.
    :param table: Whether to align the columns, rather than write CSV.
    """
    if not table:
        sys.stdout.write(rates.write_csv(float_precision=4))
        return
    cells = [
        [f"{value:.4f}" if isinstance(value, float) else str(value) for value in row]
        for row in [rates.columns, *rates.iter_rows()]
    ]
    widths = [
        max(len(row[index]) for row in cells) for index in range(len(rates.columns))
    ]
    for row in cells:
        sys.stdout.write(
            "  ".join(
                cell.rjust(width) for cell, width in zip(row, widths, strict=True)
            )
            + "\n"
        )


def display_results(results: collections.abc.Sequence[operate.Result]) -> None:
    """Write one CSV row per message sent: `kind,title,signals,status`."""
    sys.stdout.write(
        polars.DataFrame(
            {
                "kind": [result.kind for result in results],
                "title": [result.title for result in results],
                "signals": [result.signals for result in results],
                "status": [result.status for result in results],
            },
            schema={
                "kind": polars.String,
                "title": polars.String,
                "signals": polars.Int64,
                "status": polars.String,
            },
        ).write_csv()
    )


def _actions_text(message: transform.Message) -> str:
    """Return the message's buttons as `label=url` pairs."""
    return " | ".join(f"{action.label}={action.url}" for action in message.actions)


def display_messages(
    messages: collections.abc.Sequence[transform.Message], *, table: bool
) -> None:
    """Write every message whole: as CSV, or laid out as a person would read it.

    :param messages: What a run would send.
    :param table: Whether to lay each message out as text, rather than write CSV.
    """
    if not table:
        sys.stdout.write(
            polars.DataFrame(
                {
                    "kind": [message.kind for message in messages],
                    "title": [message.title for message in messages],
                    "message": [message.message for message in messages],
                    "priority": [message.priority for message in messages],
                    "tags": [",".join(message.tags) for message in messages],
                    "click": [message.click or "" for message in messages],
                    "actions": [_actions_text(message) for message in messages],
                    "attachment": [message.attachment or "" for message in messages],
                    "signals": [len(message.signals) for message in messages],
                },
                schema={
                    "kind": polars.String,
                    "title": polars.String,
                    "message": polars.String,
                    "priority": polars.Int64,
                    "tags": polars.String,
                    "click": polars.String,
                    "actions": polars.String,
                    "attachment": polars.String,
                    "signals": polars.Int64,
                },
            ).write_csv()
        )
        return
    for message in messages:
        lines = [
            f"{message.kind} (priority {message.priority}): {message.title}",
            *(f"  {line}" for line in message.message.splitlines()),
            f"  tags: {', '.join(message.tags)}",
            *([f"  click: {message.click}"] if message.click else []),
            *(f"  button {action.label}: {action.url}" for action in message.actions),
            *([f"  image: {message.attachment}"] if message.attachment else []),
        ]
        sys.stdout.write("\n".join(lines) + "\n\n")
