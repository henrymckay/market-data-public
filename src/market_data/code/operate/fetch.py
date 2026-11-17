"""The fetch use case: fetch, complete, validate, store and record one run."""

import collections.abc
import datetime

import polars

from market_data.code import port, transform


def fetch_bars(
    tickers: collections.abc.Sequence[str],
    *,
    fetch: port.Fetch,
    now: collections.abc.Callable[[], datetime.datetime],
    sink: port.Sink,
    tolerance: int,
    universe: polars.DataFrame,
) -> transform.Run:
    """Fetch the tickers' history, store what validates and record the run.

    Instruments that answered nothing usable keep last night's rows; when none
    answered, nothing is replaced and a failed run is recorded.

    :param tickers: The instruments to fetch, each in the universe.
    :param fetch: Fetches the tickers' bars from the source.
    :param now: The clock, returning an aware UTC time.
    :param sink: Where the results are written.
    :param tolerance: Failed instruments a night may absorb and stay stored.
    :param universe: The universe, stored beside the bars.
    :returns: The run's manifest row, already appended to the sink.
    """
    started = now()
    today = started.astimezone(datetime.UTC).date()
    fetched = fetch(tickers)
    valid, rejected = transform.validate_bars(
        transform.keep_complete(fetched.bars, today=today), universe=universe
    )
    answered = tuple(sorted(valid.get_column("ticker").unique().to_list()))
    kept = rejected.filter(polars.col("ticker").is_in(answered))
    outcome = transform.judge_outcome(
        answered=len(answered),
        failed_items=len(tickers) - len(answered),
        tolerance=tolerance,
    )
    stored = outcome is not transform.Outcome.FAILED
    if stored:
        sink.replace(
            port.Load(
                answered=answered,
                bars=valid,
                fetched=started,
                rejected=kept,
                universe=universe,
            )
        )
    last_day = today - datetime.timedelta(days=1)
    run = transform.Run(
        day=last_day,
        ended=now(),
        failed_items=len(tickers) - len(answered),
        last_day=last_day,
        outcome=outcome,
        rejected=kept.height if stored else 0,
        requests=fetched.requests,
        rows=valid.height if stored else 0,
        source="yahoo",
        started=started,
    )
    sink.append_run(run)
    return run
