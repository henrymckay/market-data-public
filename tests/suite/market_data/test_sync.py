import polars
import pytest

from market_data.code import error, port, transform


def _universe(*rows):
    return polars.DataFrame(
        [
            {
                "active": active,
                "asset_class": asset_class,
                "featured": False,
                "name": ticker.title(),
                "quote_type": "price",
                "sector": "Old",
                "source": source,
                "ticker": ticker,
            }
            for ticker, asset_class, source, active in rows
        ],
        schema=port.UNIVERSE,
    )


def _members(count=500, **changes):
    symbols = changes.pop("symbols", [f"S{index:03d}" for index in range(count)])
    return polars.DataFrame(
        {
            "symbol": symbols,
            "name": [f"Company {symbol}" for symbol in symbols],
            "sector": ["Information Technology"] * len(symbols),
        }
    )


@pytest.fixture
def universe():
    return _universe(
        ("S000", "stock", "sp500", True),
        ("GONE", "stock", "sp500", True),
        ("BACK", "stock", "sp500", False),
        ("BTC-USD", "crypto", "curated", True),
        ("OLD", "stock", "curated", True),
    )


@pytest.fixture
def members():
    return _members(
        symbols=["S000", "S001", "BACK", *[f"X{n:03d}" for n in range(497)]]
    )


def test_when_sync_members_then_a_new_member_is_added_active_unfeatured_as_sp500(
    universe, members
):
    synced = transform.sync_members(universe, members)

    added = synced.filter(polars.col("ticker").eq("S001")).to_dicts()[0]
    assert (added["active"], added["featured"], added["source"]) == (
        True,
        False,
        "sp500",
    )
    assert (added["asset_class"], added["quote_type"]) == ("stock", "price")


def test_when_sync_members_then_information_technology_is_written_technology(
    universe, members
):
    synced = transform.sync_members(universe, members)

    sectors = synced.filter(polars.col("ticker").eq("S001")).get_column("sector")
    assert sectors.to_list() == ["Technology"]


def test_when_sync_members_then_a_leaver_is_inactive_and_a_returner_active(
    universe, members
):
    synced = transform.sync_members(universe, members)

    active = dict(synced.select("ticker", "active").iter_rows())
    assert (active["GONE"], active["BACK"]) == (False, True)


def test_when_sync_members_then_curated_rows_are_untouched(universe, members):
    synced = transform.sync_members(universe, members)

    curated = ("BTC-USD", "OLD")
    assert (
        synced.filter(polars.col("ticker").is_in(curated))
        .sort("ticker")
        .equals(universe.filter(polars.col("ticker").is_in(curated)).sort("ticker"))
    )


def test_when_sync_members_then_a_dot_in_a_symbol_becomes_a_hyphen(universe):
    members = _members(symbols=["BRK.B", *[f"X{n:03d}" for n in range(499)]])

    synced = transform.sync_members(universe, members)

    assert "BRK-B" in synced.get_column("ticker").to_list()


def test_when_sync_members_then_rows_are_sorted_by_asset_class_then_ticker(
    universe, members
):
    synced = transform.sync_members(universe, members)

    assert synced.equals(synced.sort("asset_class", "ticker"))
    assert synced.get_column("asset_class").to_list()[0] == "crypto"


def test_when_sync_members_twice_then_the_second_changes_nothing(universe, members):
    once = transform.sync_members(universe, members)

    twice = transform.sync_members(once, members)

    assert twice.equals(once)


@pytest.mark.parametrize("count", [494, 511])
def test_when_the_list_is_the_wrong_length_then_sync_members_fails(universe, count):
    with pytest.raises(error.SourceError):
        transform.sync_members(universe, _members(count))


@pytest.mark.parametrize("symbol", ["aapl", "A B", "1AB", "TOOLONGSYMBOL", "A;DROP"])
def test_when_a_symbol_is_odd_then_sync_members_fails(universe, symbol):
    members = _members(symbols=[symbol, *[f"X{n:03d}" for n in range(499)]])

    with pytest.raises(error.SourceError):
        transform.sync_members(universe, members)


def test_when_a_symbol_repeats_then_sync_members_fails(universe):
    members = _members(symbols=["AAA", "AAA", *[f"X{n:03d}" for n in range(498)]])

    with pytest.raises(error.SourceError):
        transform.sync_members(universe, members)


def test_when_diff_universe_then_added_and_removed_tickers_are_named(universe, members):
    synced = transform.sync_members(universe, members)

    changes = transform.diff_universe(universe, synced)

    assert "S001" in changes.added
    assert "BACK" in changes.added
    assert changes.removed == ("GONE",)


@pytest.mark.parametrize("text", ["x" * 101, "two\nlines", "bell\x07"])
def test_when_a_name_is_odd_then_sync_members_fails(universe, text):
    members = _members(symbols=[f"X{n:03d}" for n in range(500)]).with_columns(
        polars.lit(text).alias("name")
    )

    with pytest.raises(error.SourceError):
        transform.sync_members(universe, members)
