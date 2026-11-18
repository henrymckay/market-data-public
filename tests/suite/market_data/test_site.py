import datetime

import polars
import pytest

from market_data.code import transform


def _days(count: int) -> list[datetime.date]:
    start = datetime.date(2026, 1, 5)
    return [start + datetime.timedelta(days=offset) for offset in range(count)]


@pytest.fixture
def site_bars(make_bars):
    rows = [
        ("AAA", day, {"adj_close": 100.0 + i, "close": 100.0 + i})
        for i, day in enumerate(_days(70))
    ]
    rows += [("^TNX", day, {"adj_close": 4.0, "close": 4.0}) for day in _days(5)]
    return make_bars(*rows)


@pytest.fixture
def site_metrics(site_bars):
    return transform.build_metrics(site_bars)


@pytest.fixture
def no_rejections():
    return polars.DataFrame(
        {"ticker": ["AAA"], "rejected": [2]},
        schema={"ticker": polars.String, "rejected": polars.Int64},
    )


@pytest.fixture
def overview(small_universe, site_metrics, site_bars, no_rejections):
    return transform.build_overview(
        bars=site_bars,
        metrics=site_metrics,
        rejected=no_rejections,
        tickers=small_universe,
    )


@pytest.mark.parametrize(
    ("ticker", "slug"),
    [
        ("^GSPC", "gspc"),
        ("EURUSD=X", "eurusdx"),
        ("BRK.B", "brkb"),
        ("BTC-USD", "btc-usd"),
    ],
)
def test_when_slugging_then_symbols_are_lowercased_without_punctuation(ticker, slug):
    assert transform.slug(ticker) == slug


def test_when_overview_built_then_one_row_per_instrument_in_ticker_order(overview):
    assert overview.get_column("ticker").to_list() == ["AAA", "BBB", "^TNX"]


def test_when_overview_built_then_metrics_are_columns_with_their_values(overview):
    row = overview.filter(polars.col("ticker") == "AAA").row(0, named=True)
    assert row["last_close"] == 169.0
    assert row["return_1d"] == pytest.approx(169 / 168 - 1)


def test_when_overview_built_then_spark_is_the_last_63_adjusted_closes(overview):
    spark = overview.filter(polars.col("ticker") == "AAA").row(0, named=True)["spark"]
    assert spark == [float(100 + i) for i in range(7, 70)]


def test_when_history_is_short_then_spark_holds_every_bar(overview):
    row = overview.filter(polars.col("ticker") == "^TNX").row(0, named=True)
    assert len(row["spark"]) == 5


def test_when_overview_built_then_coverage_columns_are_stated(overview):
    row = overview.filter(polars.col("ticker") == "AAA").row(0, named=True)
    assert (row["first_day"], row["last_day"]) == (_days(70)[0], _days(70)[-1])
    assert (row["bar_count"], row["rejected"], row["slug"]) == (70, 2, "aaa")


def test_when_an_instrument_has_no_bars_then_it_stays_with_nulls_and_zero_count(
    overview,
):
    row = overview.filter(polars.col("ticker") == "BBB").row(0, named=True)
    assert (row["bar_count"], row["rejected"], row["last_close"]) == (0, 0, None)
    assert row["spark"] is None


def test_when_a_return_is_absent_then_its_column_is_null_not_missing(overview):
    assert "return_5y" in overview.columns


def test_when_build_overview_then_figures_keep_seven_digits_and_the_spark_five(
    small_universe, no_rejections, make_bars
):
    bars = make_bars(
        *(
            ("AAA", day, {"adj_close": 100.0 / 3 + i, "close": 100.0 / 3 + i})
            for i, day in enumerate(_days(70))
        )
    )

    overview = transform.build_overview(
        bars=bars,
        metrics=transform.build_metrics(bars),
        rejected=no_rejections,
        tickers=small_universe,
    ).filter(polars.col("ticker").eq("AAA"))

    assert overview.item(0, "last_close") == pytest.approx(100.0 / 3 + 69, rel=1e-6)
    assert len(repr(overview.item(0, "last_close"))) <= 10
    assert max(len(repr(value)) for value in overview.item(0, "spark")) <= 8
