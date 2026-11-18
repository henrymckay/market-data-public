# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Draw a push's chart: the last bars of a timeframe with the signal marked."""

import datetime
import io

import polars
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from market_data.code import error, transform

_WIDTH, _HEIGHT, _DPI = 12, 6, 100
_SURFACE = "#fcfcfb"
_SUNKEN = "#efeeea"
_TEXT = "#0b0b0b"
_MUTED = "#66655f"
_GRID = "#e1e0d9"
_AXIS = "#c3c2b7"
_UP = "#2a78d6"
_DOWN = "#e34948"
_ACCENT = "#2a78d6"
_MAX_BYTES = 200_000
_PAD = 0.07
_TICKS = 7
_BODY = 0.62
_SUBTITLE = {"d": "daily", "w": "weekly", "m": "monthly"}
_DATE_FORMAT = {"d": "%d %b %Y", "w": "%d %b %Y", "m": "%b %Y"}


def _frame_axes(figure: Figure) -> Axes:
    """Return the plot's axes, drawn in the house light tokens."""
    axes = figure.add_axes((0.065, 0.12, 0.79, 0.70), facecolor=_SURFACE)
    for side in ("top", "right", "left"):
        axes.spines[side].set_visible(False)
    axes.spines["bottom"].set_color(_AXIS)
    axes.grid(axis="y", color=_GRID, linewidth=0.8)
    axes.set_axisbelow(True)
    axes.tick_params(colors=_MUTED, length=0, labelsize=10)
    return axes


def _draw_candles(axes: Axes, bars: polars.DataFrame) -> None:
    """Draw each bar as a wick and a body, blue when it closed up, red when down."""
    opens = (
        bars.select(
            polars.when(polars.col("open").is_finite())
            .then(polars.col("open"))
            .otherwise(polars.col("close").shift(n=1).fill_null(polars.col("close")))
        )
        .to_series()
        .to_list()
    )
    closes = bars.get_column("close").to_list()
    for index, (open_, high, low, close) in enumerate(
        zip(
            opens,
            bars.get_column("high").to_list(),
            bars.get_column("low").to_list(),
            closes,
            strict=True,
        )
    ):
        colour = _UP if close >= open_ else _DOWN
        axes.vlines(index, low, high, color=colour, linewidth=1.1, zorder=3)
        axes.bar(
            index,
            max(abs(close - open_), (high - low) * 0.01),
            bottom=min(open_, close),
            width=_BODY,
            color=colour,
            zorder=4,
        )


def _y_limits(
    bars: polars.DataFrame, request: transform.ChartRequest
) -> tuple[float, float]:
    """Return the price range: the bars, the level, and the stop when near."""
    low = float(bars.get_column("low").min())  # type: ignore[arg-type]
    high = float(bars.get_column("high").max())  # type: ignore[arg-type]
    span = high - low
    prices = [request.level]
    if min(abs(request.stop - low), abs(request.stop - high)) <= span or (
        low <= request.stop <= high
    ):
        prices.append(request.stop)
    floor, ceiling = min(low, *prices), max(high, *prices)
    margin = (ceiling - floor) * _PAD
    return floor - margin, ceiling + margin


def _tag(
    axes: Axes, price: float, text: str, *, colour: str, limits: tuple[float, float]
) -> None:
    """Write a price tag in the right margin, level with its line or at the edge."""
    inside = limits[0] <= price <= limits[1]
    axes.text(
        1.012,
        price if inside else limits[0 if price < limits[0] else 1],
        text if inside else f"{text} (off chart)",
        color=colour,
        fontsize=10,
        fontweight="bold",
        transform=axes.get_yaxis_transform(),
        va="center",
    )


def _draw_lines(
    axes: Axes,
    request: transform.ChartRequest,
    *,
    limits: tuple[float, float],
) -> None:
    """Draw the level dashed in the accent and the stop dotted in the other colour."""
    other = _DOWN if request.direction == "up" else _UP
    level = transform.format_price(request.level, request.asset_class)
    stop = transform.format_price(request.stop, request.asset_class)
    axes.axhline(request.level, color=_ACCENT, linestyle="--", linewidth=1.3, zorder=2)
    if limits[0] <= request.stop <= limits[1]:
        axes.axhline(request.stop, color=other, linestyle=":", linewidth=1.6, zorder=2)
    if abs(request.level - request.stop) <= (limits[1] - limits[0]) * 0.04:
        _tag(axes, request.level, f"Level {level}", colour=_ACCENT, limits=limits)
        axes.text(
            1.012,
            request.level,
            "\nInvalid below" if request.direction == "up" else "\nInvalid above",
            color=other,
            fontsize=9,
            transform=axes.get_yaxis_transform(),
            va="top",
        )
        return
    _tag(axes, request.level, f"Level {level}", colour=_ACCENT, limits=limits)
    _tag(axes, request.stop, f"Invalid {stop}", colour=other, limits=limits)


def _mark_signal(
    axes: Axes,
    bars: polars.DataFrame,
    request: transform.ChartRequest,
    limits: tuple[float, float],
) -> None:
    """Shade the signal bar and point at it from the side the signal came from."""
    days: list[datetime.date] = bars.get_column("day").to_list()
    if request.signal_day not in days:
        return
    index = days.index(request.signal_day)
    axes.axvspan(index - 0.5, index + 0.5, color=_SUNKEN, zorder=1)
    up = request.direction == "up"
    row = bars.row(index, named=True)
    gap = (limits[1] - limits[0]) * 0.025
    axes.annotate(
        "Signal",
        xy=(index, row["low"] - gap if up else row["high"] + gap),
        xytext=(index, row["low"] - gap * 5 if up else row["high"] + gap * 5),
        ha="center",
        va="top" if up else "bottom",
        color=_TEXT,
        fontsize=10,
        arrowprops={"arrowstyle": "-|>", "color": _TEXT, "linewidth": 1.2},
        zorder=6,
    )


def _label_pivots(axes: Axes, bars: polars.DataFrame, pivots: polars.DataFrame) -> None:
    """Write each swing's label past its extreme, in the muted colour."""
    days: list[datetime.date] = bars.get_column("day").to_list()
    for pivot in pivots.iter_rows(named=True):
        if pivot["label"] is None or pivot["day"] not in days:
            continue
        index = days.index(pivot["day"])
        high = pivot["kind"] == "high"
        axes.annotate(
            pivot["label"],
            xy=(index, pivot["price"]),
            xytext=(0, 6 if high else -6),
            textcoords="offset points",
            ha="center",
            va="bottom" if high else "top",
            color=_MUTED,
            fontsize=9,
            zorder=5,
        )


def _label_axis(axes: Axes, bars: polars.DataFrame, timeframe: str) -> None:
    """Put dates under evenly spread bars."""
    days: list[datetime.date] = bars.get_column("day").to_list()
    step = max(len(days) // _TICKS, 1)
    positions = list(range(len(days) - 1, -1, -step))[::-1]
    axes.set_xticks(positions)
    axes.set_xticklabels(
        [days[position].strftime(_DATE_FORMAT[timeframe]) for position in positions]
    )
    axes.set_xlim(-1, len(days))


def draw_chart(
    request: transform.ChartRequest, bars: polars.DataFrame, pivots: polars.DataFrame
) -> bytes:
    """Return a 1200 by 600 PNG of the bars with the signal, level and stop drawn.

    :param request: What to draw and its title, in the push's words.
    :param bars: The last bars of the timeframe: `close`, `day`, `high`, `low`, `open`.
    :param pivots: The timeframe's pivots: `day`, `kind`, `label`, `price`.
    :returns: The PNG, under 200 KB.
    :raises ChartError: If there are no bars or the image cannot be drawn.
    """
    if bars.is_empty():
        raise error.ChartError(f"No bars to draw for {request.ticker}")
    try:
        figure = Figure(figsize=(_WIDTH, _HEIGHT), dpi=_DPI, facecolor=_SURFACE)
        axes = _frame_axes(figure)
        limits = _y_limits(bars, request)
        _draw_candles(axes, bars)
        _mark_signal(axes, bars, request, limits)
        _label_pivots(axes, bars, pivots)
        _draw_lines(axes, request, limits=limits)
        axes.set_ylim(*limits)
        _label_axis(axes, bars, request.timeframe)
        figure.text(0.065, 0.93, request.title, color=_TEXT, fontsize=17, weight="bold")
        figure.text(
            0.065,
            0.875,
            f"Last {bars.height} {_SUBTITLE[request.timeframe]} bars, "
            f"swings labelled, signal bar marked",
            color=_MUTED,
            fontsize=11,
        )
        buffer = io.BytesIO()
        figure.savefig(buffer, format="png", facecolor=_SURFACE)
    except Exception as failure:
        raise error.ChartError(f"The chart for {request.ticker} failed") from failure
    image = buffer.getvalue()
    if len(image) > _MAX_BYTES:
        raise error.ChartError(f"The chart for {request.ticker} is {len(image)} bytes")
    return image
