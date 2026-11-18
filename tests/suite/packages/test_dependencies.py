import datetime

import numpy
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


def test_when_join_asof_excludes_exact_matches_then_the_match_is_strictly_earlier():
    left = polars.DataFrame(
        {"day": [datetime.date(2024, 1, 8), datetime.date(2024, 1, 9)]}
    )
    right = polars.DataFrame(
        {
            "last_day": [datetime.date(2024, 1, 5), datetime.date(2024, 1, 8)],
            "v": [1, 2],
        }
    )

    joined = left.join_asof(
        right,
        allow_exact_matches=False,
        left_on="day",
        right_on="last_day",
        strategy="backward",
    )

    assert joined.get_column("v").to_list() == [1, 2]


def test_when_a_rolling_mean_meets_a_null_then_the_window_is_null_until_it_passes():
    volume = polars.Series([1.0, None, 3.0, 4.0, 5.0], dtype=polars.Float64)

    mean = volume.rolling_mean(window_size=2, min_samples=2)

    assert mean.to_list() == [None, None, None, 3.5, 4.5]


def test_when_ewm_mean_has_min_samples_then_wilders_atr_starts_at_that_observation():
    values = polars.Series([2.0, 4.0, 6.0])

    ewm = values.ewm_mean(alpha=0.5, adjust=False, min_samples=2)

    assert ewm.to_list() == [None, 3.0, 4.5]


def test_when_month_end_is_taken_then_it_is_the_last_calendar_day():
    days = polars.Series([datetime.date(2024, 2, 1), datetime.date(2023, 12, 1)])

    assert days.dt.month_end().to_list() == [
        datetime.date(2024, 2, 29),
        datetime.date(2023, 12, 31),
    ]


def test_when_argmin_runs_over_a_reversed_slice_then_the_later_tie_wins():
    lows = [5.0, 3.0, 4.0, 3.0]

    reversed_position = len(lows) - 1 - int(numpy.argmin(lows[::-1]))

    assert reversed_position == 3
