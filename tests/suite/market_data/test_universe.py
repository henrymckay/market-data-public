import polars

from market_data.code import port, transform


def test_when_read_universe_then_it_has_about_ninety_unique_tickers(real_universe):
    assert real_universe.schema == port.UNIVERSE
    assert 85 <= real_universe.height <= 95
    assert real_universe.get_column("ticker").is_unique().all()


def test_when_read_universe_then_every_asset_class_is_a_known_one(real_universe):
    known = {"index", "etf", "stock", "rate", "fx", "commodity", "crypto"}

    assert set(real_universe.get_column("asset_class")) == known


def test_when_read_universe_then_only_rates_quote_a_yield(real_universe):
    yields = real_universe.filter(polars.col("quote_type").eq("yield"))

    assert set(yields.get_column("asset_class")) == {"rate"}
    assert real_universe.filter(polars.col("asset_class").eq("rate")).get_column(
        "quote_type"
    ).unique().to_list() == ["yield"]


def test_when_read_universe_then_every_instrument_is_active(real_universe):
    assert len(transform.active_tickers(real_universe)) == real_universe.height
