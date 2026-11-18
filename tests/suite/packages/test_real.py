import polars
import pytest

from market_data.code.adapt import yahoo


@pytest.mark.real
def test_when_fetch_bars_from_yahoo_then_long_histories_arrive_for_each_class():
    constants = yahoo.read_constants()
    requests = yahoo.Requests()
    history = yahoo.build_history(constants, requests=requests)

    fetched = yahoo.fetch_bars(
        ["^GSPC", "AAPL", "EURUSD=X", "BTC-USD"],
        "max",
        history=history,
        requests=requests,
    )

    counts = fetched.bars.group_by("ticker").len()
    assert fetched.failed == ()
    assert counts.filter(polars.col("len").gt(4000)).height == 4


@pytest.mark.real
def test_when_fetch_bars_for_a_month_then_far_fewer_bars_than_max_arrive():
    constants = yahoo.read_constants()
    requests = yahoo.Requests()
    history = yahoo.build_history(constants, requests=requests)

    fetched = yahoo.fetch_bars(
        ["AAPL", "BTC-USD"], "1mo", history=history, requests=requests
    )

    counts = fetched.bars.group_by("ticker").len()
    assert fetched.failed == ()
    assert counts.filter(polars.col("len").is_between(15, 33)).height == 2
