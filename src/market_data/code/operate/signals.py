"""The signals use case: find swings, signals and base rates and record the run."""

import collections.abc
import datetime
import logging

import polars

from market_data.code import error, port, transform

_LOGGER = logging.getLogger(__name__)


def find_signals(
    *,
    bars: polars.DataFrame,
    now: collections.abc.Callable[[], datetime.datetime],
    rules: transform.Rules,
    store: port.SignalsStore,
) -> transform.Computed:
    """Return every pivot, signal, outcome, base rate and structure, writing nothing.

    :param bars: Every stored daily bar, read once for the whole night.
    :param now: The clock, returning an aware UTC time; its UTC date is `today`.
    :param rules: The rules.
    :param store: Where period bars and the universe are read.
    :returns: The five tables.
    """
    return transform.build_signals(
        bars=bars,
        periods=store.read_period_bars(),
        rules=rules,
        rules_id=transform.hash_rules(rules),
        tickers=store.read_tickers(),
        today=now().astimezone(datetime.UTC).date(),
    )


def compute_signals(
    *,
    bars: polars.DataFrame,
    now: collections.abc.Callable[[], datetime.datetime],
    rules: transform.Rules,
    store: port.SignalsStore,
) -> transform.Run:
    """Recompute everything `find_signals` returns, replace it and record the run.

    A store failure while replacing is logged and recorded as a failed run, so the
    stages after it still run over yesterday's tables; a store with no bars records
    a failed run and replaces nothing.

    :param bars: Every stored daily bar, read once for the whole night.
    :param now: The clock, returning an aware UTC time.
    :param rules: The rules.
    :param store: Where period bars and the universe are read and results written.
    :returns: The run's manifest row, already appended.
    """
    started = now()
    rows = 0
    stored = False
    if not bars.is_empty():
        computed = find_signals(
            bars=bars, now=lambda: started, rules=rules, store=store
        )
        try:
            store.replace_signals(computed)
            rows, stored = computed.count_signals(), True
        except error.StoreError as failure:
            _LOGGER.error("The signals stage failed: %s", failure)
    last_day = started.astimezone(datetime.UTC).date() - datetime.timedelta(days=1)
    run = transform.Run(
        day=last_day,
        ended=now(),
        failed_items=0,
        last_day=last_day,
        outcome=transform.Outcome.STORED if stored else transform.Outcome.FAILED,
        rejected=0,
        requests=0,
        rows=rows,
        source="signals",
        started=started,
    )
    store.append_run(run)
    return run
