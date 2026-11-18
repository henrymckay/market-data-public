"""The fetch use case: fetch, complete, validate, store and record one run."""

import collections.abc
import datetime

import polars

from market_data.code import port, transform


def _fetch_period(
    tickers: collections.abc.Sequence[str], period: port.Period, *, fetch: port.Fetch
) -> port.Fetched:
    """Fetch the tickers for the period, or answer empty without a request."""
    if tickers:
        return fetch(tickers, period)
    return port.Fetched(bars=polars.DataFrame(schema=port.BARS), failed=(), requests=0)


def fetch_bars(
    tickers: collections.abc.Sequence[str],
    *,
    fetch: port.Fetch,
    full: bool,
    now: collections.abc.Callable[[], datetime.datetime],
    sink: port.Sink,
    tolerance: int,
    universe: polars.DataFrame,
) -> transform.Run:
    """Fetch the tickers, store what validates and record the run.

    Each instrument's last month is fetched, and its whole history where
    `transform.plan_fetch` says so or the month contradicts the store. Instruments
    that answered nothing usable keep their rows; when none answered, nothing is
    replaced and a failed run is recorded.

    :param tickers: The instruments to fetch, each in the universe.
    :param fetch: Fetches the tickers' bars from the source for a period.
    :param full: Whether every instrument gets its whole history.
    :param now: The clock, returning an aware UTC time.
    :param sink: Where the stored days are read and the results written.
    :param tolerance: Failed instruments a night may absorb and stay stored.
    :param universe: The universe, stored beside the bars.
    :returns: The run's manifest row, already appended to the sink.
    """
    started = now()
    today = started.astimezone(datetime.UTC).date()
    plan = transform.plan_fetch(
        list(tickers), full=full, last_days=sink.read_last_days(), today=today
    )
    month = plan.filter(polars.col("period").eq("1mo")).get_column("ticker").to_list()
    recent = _fetch_period(month, "1mo", fetch=fetch)
    recent_bars = transform.keep_complete(recent.bars, today=today)
    first_day: datetime.date | None = recent_bars.select(polars.col("day").min()).item()
    restated = (
        transform.find_disagreements(
            fetched=recent_bars, stored=sink.read_overlap(month, first_day)
        )
        if first_day is not None
        else []
    )
    whole = sorted(set(tickers) - set(month) | set(restated))
    entire = _fetch_period(whole, "max", fetch=fetch)
    bars = polars.concat(
        [
            recent_bars.filter(~polars.col("ticker").is_in(restated)),
            transform.keep_complete(entire.bars, today=today),
        ]
    )
    valid, rejected = transform.validate_bars(bars, universe=universe)
    answered = tuple(sorted(valid.get_column("ticker").unique().to_list()))
    kept = rejected.filter(polars.col("ticker").is_in(answered))
    failed_items = len(tickers) - len(answered)
    outcome = transform.judge_outcome(
        answered=len(answered), failed_items=failed_items, tolerance=tolerance
    )
    stored = outcome is not transform.Outcome.FAILED
    if stored:
        sink.replace(
            port.Load(
                bars=valid,
                fetched=started,
                rejected=kept,
                since=transform.build_since(
                    list(answered), recent=recent_bars, whole=whole
                ),
                universe=universe,
            )
        )
    last_day = today - datetime.timedelta(days=1)
    run = transform.Run(
        day=last_day,
        ended=now(),
        failed_items=failed_items,
        last_day=last_day,
        outcome=outcome,
        rejected=kept.height if stored else 0,
        requests=max(recent.requests, entire.requests),
        rows=valid.height if stored else 0,
        source="yahoo",
        started=started,
    )
    sink.append_run(run)
    return run
