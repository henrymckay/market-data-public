import datetime
import pathlib
import re

import polars
import pytest

from market_data.code import port, transform
from market_data.code.adapt import motherduck
from pytest_ import fake

_README = pathlib.Path(__file__).parents[3] / "README.md"
_DAY = datetime.date(2026, 11, 16)
_STARTED = datetime.datetime(2026, 11, 17, 2, 17, tzinfo=datetime.UTC)


def _queries() -> list[str]:
    return re.findall(r"```sql\n(.*?)```", _README.read_text(), re.DOTALL)


@pytest.fixture
def store(tmp_path, make_bars, small_universe):
    store = motherduck.Store(motherduck.connect(str(tmp_path / "market.duckdb")))
    store.replace(
        port.Load(
            since=fake.whole(("AAA",)),
            bars=make_bars(("AAA", _DAY, {"close": 10.0})),
            fetched=_STARTED,
            rejected=polars.DataFrame([], schema=port.REJECTED),
            universe=small_universe,
        )
    )
    store.append_run(
        transform.Run(
            day=_DAY,
            ended=_STARTED + datetime.timedelta(minutes=2),
            failed_items=0,
            last_day=_DAY,
            outcome=transform.Outcome.STORED,
            rejected=0,
            requests=1,
            rows=1,
            source="yahoo",
            started=_STARTED,
        )
    )
    return store


def test_when_the_readme_is_read_then_it_documents_queries():
    assert len(_queries()) >= 4


@pytest.mark.parametrize("query", _queries())
def test_when_a_readme_query_runs_on_a_loaded_store_then_it_succeeds(store, query):
    rows = store.connection.execute(query).fetchall()

    assert isinstance(rows, list)


def test_when_the_first_readme_query_runs_then_it_counts_the_stored_bars(store):
    first = _queries()[0]

    assert store.connection.execute(first).fetchall() == [(1, 1)]
