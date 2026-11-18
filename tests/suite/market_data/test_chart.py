import datetime
import struct

import polars
import pytest

from market_data.code import error, transform
from market_data.code.adapt import chart


def _bars(count=80):
    start = datetime.date(2026, 1, 5)
    days = [start + datetime.timedelta(days=7 * n) for n in range(count)]
    closes = [100 + (n % 9) * 2 - n * 0.2 for n in range(count)]
    return polars.DataFrame(
        {
            "close": closes,
            "day": days,
            "high": [value + 2 for value in closes],
            "low": [value - 2 for value in closes],
            "open": [value + 0.5 for value in closes],
        }
    )


def _request(bars, **changes):
    values = {
        "asset_class": "stock",
        "direction": "up",
        "level": 95.0,
        "signal_day": bars.get_column("day")[-1],
        "stop": 80.0,
        "ticker": "NVDA",
        "timeframe": "w",
        "title": "NVDA weekly: first higher high (A)",
    }
    return transform.ChartRequest(**(values | changes))


def _pivots(bars):
    return polars.DataFrame(
        {
            "day": [bars.get_column("day")[10]],
            "kind": ["high"],
            "label": ["LH"],
            "price": [bars.get_column("high")[10]],
        }
    )


def test_when_a_chart_is_drawn_then_it_is_a_1200_by_600_png_under_200_kb():
    bars = _bars()

    image = chart.draw_chart(_request(bars), bars, _pivots(bars))

    width, height = struct.unpack(">II", image[16:24])
    assert image[:8] == b"\x89PNG\r\n\x1a\n"
    assert (width, height) == (1200, 600)
    assert len(image) < 200_000


@pytest.mark.parametrize(
    "changes",
    [
        {"direction": "down", "level": 120.0, "stop": 125.0},
        {"level": 90.0, "stop": 90.0},
        {"stop": 1.0},
    ],
)
def test_when_level_and_stop_vary_then_a_chart_is_still_drawn(changes):
    bars = _bars()

    image = chart.draw_chart(_request(bars, **changes), bars, _pivots(bars))

    assert image[:4] == b"\x89PNG"


def test_when_the_signal_bar_is_not_among_the_bars_then_the_chart_is_still_drawn():
    bars = _bars()

    image = chart.draw_chart(
        _request(bars, signal_day=datetime.date(2020, 1, 1)), bars, _pivots(bars)
    )

    assert image[:4] == b"\x89PNG"


def test_when_there_are_no_bars_then_chart_error_is_raised():
    full = _bars()

    with pytest.raises(error.ChartError):
        chart.draw_chart(_request(full), full.head(0), _pivots(full))
