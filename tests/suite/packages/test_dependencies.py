import pandas
import polars
import polars.exceptions
import pytest

from market_data.code import port


def test_when_match_to_schema_meets_a_missing_column_then_it_raises():
    frame = polars.DataFrame({"ticker": ["A"]})

    with pytest.raises(polars.exceptions.SchemaError):
        frame.match_to_schema(port.BARS)


def test_when_pandas_index_is_tz_aware_then_strftime_gives_the_local_date():
    index = pandas.DatetimeIndex(["2026-11-13 00:00:00-05:00"], tz="America/New_York")

    assert list(index.strftime("%Y-%m-%d")) == ["2026-11-13"]


def test_when_polars_reads_a_pandas_nan_then_it_becomes_null():
    frame = polars.DataFrame(pandas.DataFrame({"close": [1.0, float("nan")]}))

    assert frame.get_column("close").null_count() == 1
