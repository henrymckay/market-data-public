import polars

from market_data.code import port, transform


def test_when_read_universe_then_it_has_about_680_unique_tickers(real_universe):
    assert real_universe.schema == port.UNIVERSE
    assert 650 <= real_universe.height <= 720
    assert real_universe.get_column("ticker").is_unique().all()


def test_when_read_universe_then_every_asset_class_is_a_known_one(real_universe):
    known = {"index", "etf", "stock", "rate", "fx", "commodity", "crypto"}

    assert set(real_universe.get_column("asset_class")) == known


def test_when_read_universe_then_every_class_but_rate_has_at_least_15_active(
    real_universe,
):
    counts = (
        real_universe.filter(polars.col("active"))
        .group_by("asset_class")
        .len()
        .filter(polars.col("asset_class").ne("rate"))
    )

    assert counts.get_column("len").min() >= 15


def test_when_read_universe_then_only_rates_quote_a_yield(real_universe):
    yields = real_universe.filter(polars.col("quote_type").eq("yield"))

    assert set(yields.get_column("asset_class")) == {"rate"}
    assert real_universe.filter(polars.col("asset_class").eq("rate")).get_column(
        "quote_type"
    ).unique().to_list() == ["yield"]


def test_when_read_universe_then_at_least_650_are_active(real_universe):
    assert len(transform.active_tickers(real_universe)) >= 650


def test_when_read_universe_then_the_first_89_are_featured_and_every_row_has_a_source(
    real_universe,
):
    featured = real_universe.filter(polars.col("featured"))

    assert featured.height == 89
    assert set(real_universe.get_column("source")) == {"curated", "sp500"}


def test_when_read_universe_then_no_sector_is_information_technology(real_universe):
    assert "Information Technology" not in set(real_universe.get_column("sector"))


def test_when_read_universe_then_a_sync_would_change_nothing_but_its_order(
    real_universe,
):
    assert real_universe.equals(real_universe.sort("asset_class", "ticker")), (
        "universe.csv is sorted by asset class then ticker"
    )
