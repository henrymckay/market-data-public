"""Judge the health of the pipeline from its run history."""

import collections.abc
import dataclasses
import datetime

import polars

_STALE_AFTER = datetime.timedelta(days=2)
_SECONDS_PER_HOUR = 3600


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Status:
    """The key and value rows `status` shows, and whether the job is healthy."""

    healthy: bool
    rows: tuple[tuple[str, str], ...]


def build_status(
    runs: polars.DataFrame,
    *,
    missing: collections.abc.Sequence[str],
    now: datetime.datetime,
) -> Status:
    """Judge the runs: healthy when every source's last run stored and is fresh.

    A source is stale when its last stored `yahoo` run ended over two days ago.

    :param runs: The manifest rows, with `ended`, `failed_items`, `outcome`, `source`.
    :param missing: The active instruments that have no bars.
    :param now: The clock, aware UTC.
    :returns: The status rows and the verdict.
    """
    if runs.is_empty():
        return Status(
            healthy=False,
            rows=(
                ("last_run", ""),
                ("outcome", "none"),
                ("age_hours", ""),
                ("failed_items", ""),
                ("missing", ";".join(missing)),
                ("stale", "true"),
            ),
        )
    latest = runs.sort("ended").group_by("source", maintain_order=True).last()
    last = runs.sort("ended").row(-1, named=True)
    last_ended: datetime.datetime = last["ended"]
    stored_yahoo = runs.filter(
        (polars.col("source") == "yahoo") & (polars.col("outcome") == "stored")
    )
    stored_ends: list[datetime.datetime] = stored_yahoo.get_column("ended").to_list()
    stale = not stored_ends or now - max(stored_ends) > _STALE_AFTER
    age = (now - last_ended).total_seconds() / _SECONDS_PER_HOUR
    all_stored = latest.get_column("outcome").eq("stored").all()
    return Status(
        healthy=bool(all_stored) and not stale,
        rows=(
            ("last_run", last_ended.strftime("%Y-%m-%dT%H:%M:%SZ")),
            ("outcome", last["outcome"]),
            ("age_hours", f"{age:.1f}"),
            ("failed_items", str(last["failed_items"])),
            ("missing", ";".join(missing)),
            ("stale", str(stale).lower()),
        ),
    )
