"""The compute use case: derive the metrics from the stored bars and record the run."""

import collections.abc
import datetime

import polars

from market_data.code import port, transform


def compute_metrics(
    *,
    bars: polars.DataFrame,
    now: collections.abc.Callable[[], datetime.datetime],
    store: port.MetricsStore,
    tolerance: int,
    universe: polars.DataFrame,
) -> transform.Run:
    """Recompute every metric from the bars, replacing metrics and overview.

    Active instruments with no bars are failed items; when none has bars,
    nothing is replaced and a failed run is recorded.

    :param bars: Every stored bar, read once for the whole night.
    :param now: The clock, returning an aware UTC time.
    :param store: Where the rejected counts, universe and structure are read and the
        metrics, overview and run written.
    :param tolerance: Failed instruments a night may absorb and stay stored.
    :param universe: The universe, whose active rows should each have bars.
    :returns: The run's manifest row, already appended to the store.
    """
    started = now()
    metrics = transform.build_metrics(bars)
    measured = set(metrics.get_column("ticker").to_list())
    active = set(transform.active_tickers(universe))
    answered = len(active & measured)
    failed_items = len(active - measured)
    outcome = transform.judge_outcome(
        answered=answered, failed_items=failed_items, tolerance=tolerance
    )
    stored = outcome is not transform.Outcome.FAILED
    if stored:
        overview = transform.build_overview(
            bars=bars,
            metrics=metrics,
            rejected=store.read_rejected_counts(),
            structure=store.read_structure(),
            tickers=store.read_tickers(),
        )
        store.replace_metrics(metrics, overview)
    last_day = started.astimezone(datetime.UTC).date() - datetime.timedelta(days=1)
    run = transform.Run(
        day=last_day,
        ended=now(),
        failed_items=failed_items,
        last_day=last_day,
        outcome=outcome,
        rejected=0,
        requests=0,
        rows=metrics.height if stored else 0,
        source="metrics",
        started=started,
    )
    store.append_run(run)
    return run
