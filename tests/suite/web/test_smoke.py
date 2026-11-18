import json
import urllib.request

import playwright.sync_api
import pytest

pytestmark = pytest.mark.slow

_READY = "html[data-ready='1']"


def _open(page, served, query=""):
    page.goto(f"{served[0]}{query}")
    try:
        page.wait_for_selector(_READY, timeout=30_000)
    except playwright.sync_api.TimeoutError:
        pytest.fail(f"never ready: {page.errors}")


def test_when_markets_opens_then_tiles_charts_and_table_draw_without_error(
    page, served
):
    _open(page, served)

    assert page.locator("main h2").all_inner_texts()[0].startswith("Stocks by sector")
    assert page.get_by_text("S&P 500").first.is_visible()
    assert page.locator("tbody tr").count() == 100
    assert page.locator("button[aria-label^='NVDA']").count() == 1
    assert page.errors == []


def test_when_the_table_is_paged_then_next_shows_the_following_hundred(page, served):
    _open(page, served)
    nav = page.get_by_role("navigation", name="Pages of instruments")

    assert nav.get_by_text("1\N{EN DASH}100 of").is_visible()
    nav.get_by_role("button", name="Next").click()

    assert nav.get_by_text("101\N{EN DASH}200 of").is_visible()
    assert page.locator("tbody tr").count() == 100
    assert nav.get_by_role("button", name="Previous").is_enabled()


def test_when_the_period_changes_then_the_treemap_title_follows(page, served):
    _open(page, served)

    page.get_by_role("group", name="Period").get_by_role("button", name="1M").click()
    page.wait_for_selector(_READY)

    assert "return over 1M" in page.locator("main h2").first.inner_text()
    assert "period=1m" in page.url


def test_when_a_ticker_opens_then_candles_and_figures_draw_without_error(page, served):
    _open(page, served, "?view=ticker&t=AAPL")

    assert page.locator("canvas").count() >= 2
    assert page.get_by_text("Last close").is_visible()
    assert page.get_by_role("heading", name="Monthly returns (%)").is_visible()
    assert page.errors == []


def test_when_a_hyphenated_ticker_opens_then_its_bars_load(page, served):
    _open(page, served, "?view=ticker&t=BTC-USD")

    assert page.get_by_text("Last close").is_visible()
    assert "/api/bars/btc-usd" in served[1].requests
    assert page.errors == []


def test_when_an_instrument_is_picked_in_search_then_its_screen_opens(page, served):
    _open(page, served)

    page.keyboard.press("/")
    page.get_by_placeholder("Search by ticker or name").fill("tsla")
    page.keyboard.press("Enter")
    page.wait_for_selector(_READY)

    assert "t=TSLA" in page.url
    assert page.get_by_role("heading", level=1, name="Tesla TSLA").is_visible()


def test_when_compare_opens_then_series_statistics_and_correlations_draw(page, served):
    _open(page, served, "?view=compare")

    assert page.get_by_label("Instruments compared").locator("li").count() == 5
    assert page.get_by_role("table", name="Correlation matrix").is_visible()
    assert page.locator("canvas").count() >= 1
    assert page.errors == []


def test_when_an_instrument_is_removed_from_compare_then_the_link_follows(page, served):
    _open(page, served, "?view=compare")

    page.get_by_role("button", name="Remove ^NDX").click()
    page.wait_for_selector(_READY)

    assert "c=%5EGSPC" in page.url or "c=^GSPC" in page.url
    assert "^NDX" not in page.url.split("c=")[1]


def test_when_runs_opens_then_the_last_run_and_coverage_show(page, served):
    _open(page, served, "?view=runs")

    assert page.get_by_text("Stored").first.is_visible()
    assert page.get_by_role("heading", name="Coverage by instrument").is_visible()
    assert page.errors == []


def test_when_a_bars_file_fails_then_the_card_says_so_and_the_page_still_works(
    page, served
):
    page.route("**/api/bars/aapl*", lambda route: route.abort())

    _open(page, served, "?view=ticker&t=AAPL")

    assert (
        page.get_by_role("alert")
        .get_by_text("Couldn\u2019t load AAPL\u2019s prices")
        .is_visible()
    )
    assert page.get_by_text("Last close").is_visible()


def test_when_there_are_no_runs_then_runs_says_the_first_nightly_writes_here(
    page, served
):
    page.route(
        "**/api/runs*",
        lambda route: route.fulfill(
            body="[]",
            content_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        ),
    )

    _open(page, served, "?view=runs")

    assert page.get_by_text(
        "No runs yet \u2014 the first nightly writes here."
    ).is_visible()


def test_when_the_api_is_down_then_the_page_says_so_and_a_retry_recovers(page, served):
    down = {"on": True}

    def handler(route):
        if down["on"]:
            route.abort()
        else:
            route.continue_()

    page.route("**/api/overview*", handler)

    _open(page, served)
    alert = page.get_by_role("alert").get_by_text("the API didn\u2019t answer").first
    assert alert.is_visible()

    down["on"] = False
    page.get_by_role("button", name="Try again").first.click()
    page.wait_for_selector("tbody tr")

    assert page.locator("tbody tr").count() >= 80


def test_when_the_api_is_slow_then_the_page_says_it_is_still_loading(page, served):
    held = []
    page.route("**/api/overview*", lambda route: held.append(route))

    page.goto(served[0])
    page.get_by_role("status").get_by_text("Still loading").wait_for(timeout=10_000)
    for route in held:
        route.continue_()
    page.wait_for_selector(_READY, timeout=30_000)

    assert page.get_by_text("Still loading").count() == 0


def test_when_a_ticker_opens_then_data_requests_go_to_the_api_not_parquet(page, served):
    urls: list[str] = []
    page.on("request", lambda request: urls.append(request.url))

    _open(page, served, "?view=ticker&t=AAPL")

    data = [url for url in urls if "/api/" in url or ".parquet" in url]
    assert data
    assert all(url.startswith("http://127.0.0.1:8788/api/") for url in data)
    assert not [url for url in urls if ".parquet" in url]
    assert "/api/bars/aapl" in "".join(data)


def test_when_the_scheme_is_toggled_then_it_is_kept_across_a_reload(page, served):
    _open(page, served)

    page.get_by_role("button", name="Switch to the dark scheme").click()
    page.reload()
    page.wait_for_selector(_READY)

    assert page.evaluate("document.documentElement.classList.contains('dark')") is True


def _signals(served):
    with urllib.request.urlopen("http://127.0.0.1:8788/api/signals") as response:
        return json.loads(response.read())


def _push_link(signal):
    day, event = signal["day"], signal["event"]
    tf = signal["timeframe"]
    rng = {"d": "1Y", "w": "5Y", "m": "Max"}[tf]
    return f"?view=ticker&t={signal['ticker']}&tf={tf}&range={rng}&sig={day}.{event}"


def test_when_signals_opens_then_tiles_tables_and_the_caption_draw_without_error(
    page, served
):
    _open(page, served, "?view=signals&grade=all")

    assert page.get_by_text("Graded A", exact=True).is_visible()
    assert page.get_by_role("heading", name="Recent signals").is_visible()
    assert page.locator("tbody tr").count() >= 1
    assert page.get_by_role("heading", name="Edge over any bar (pp)").is_visible()
    assert page.get_by_text("survivorship flatters the long side").is_visible()
    assert page.errors == []


def test_when_a_digest_link_opens_then_its_class_and_day_are_chosen(page, served):
    signal = next(s for s in _signals(served) if s["asset_class"] == "stock")

    _open(page, served, f"?view=signals&cls=stock&day={signal['known']}&grade=all")

    assert (
        page.get_by_role("group", name="Asset class")
        .get_by_role("button", name="Stocks")
        .get_attribute("aria-pressed")
        == "true"
    )
    assert page.locator("select").input_value() == signal["known"]


def test_when_a_timeframe_filter_is_set_then_the_link_and_rows_follow(page, served):
    _open(page, served, "?view=signals&grade=all")

    page.get_by_role("group", name="Timeframe").get_by_role("button", name="W").click()
    page.wait_for_selector(_READY)

    assert "tf=w" in page.url
    cells = (
        page.locator("table")
        .first.locator("tbody tr td:nth-child(4)")
        .all_inner_texts()
    )
    assert cells
    assert set(cells) <= {"W"}


def test_when_the_signals_are_empty_then_the_first_nightly_is_named(page, served):
    page.route(
        "**/api/signals*",
        lambda route: route.fulfill(
            body="[]",
            content_type="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        ),
    )

    _open(page, served, "?view=signals")

    assert page.get_by_text("No signals yet").first.is_visible()


def test_when_the_signals_fail_then_the_card_says_so_and_a_retry_recovers(page, served):
    down = {"on": True}

    def handler(route):
        route.abort() if down["on"] else route.continue_()

    page.route("**/api/signals*", handler)
    _open(page, served, "?view=signals")
    assert (
        page.get_by_role("alert")
        .get_by_text("Couldn\u2019t load the signals")
        .is_visible()
    )

    down["on"] = False
    page.get_by_role("button", name="Try again").click()
    page.wait_for_selector("tbody tr")


def test_when_a_signal_row_is_opened_then_the_chart_shows_its_level_and_stop(
    page, served
):
    _open(page, served, "?view=signals&grade=all")

    page.locator("tbody tr").first.click()
    page.wait_for_selector(_READY)

    assert "sig=" in page.url
    assert page.get_by_test_id("signal-note").is_visible()
    assert page.locator("[data-lines]").first.get_attribute("data-lines") in {"1", "2"}


def test_when_a_push_link_opens_then_the_level_is_drawn_and_the_signal_marked(
    page, served
):
    signal = next(s for s in _signals(served) if s["timeframe"] == "d")

    _open(page, served, _push_link(signal))

    chart = page.locator("[data-lines]").first
    assert chart.get_attribute("data-lines") in {"1", "2"}
    assert int(chart.get_attribute("data-signals")) >= 1
    assert page.get_by_test_id("signal-note").is_visible()
    assert page.errors == []


def test_when_the_timeframe_is_weekly_then_weekly_candles_and_signals_show(
    page, served
):
    _open(page, served, "?view=ticker&t=AAPL")

    page.get_by_role("group", name="Timeframe").get_by_role("button", name="W").click()
    page.wait_for_selector(_READY)

    assert "tf=w" in page.url
    assert page.get_by_role("heading", name="Apple, weekly candles").is_visible()
    assert page.get_by_role("heading", name="Signals, weekly").is_visible()
    assert page.errors == []


def test_when_markets_opens_then_each_row_has_a_trend_in_words(page, served):
    _open(page, served)

    assert page.get_by_role("columnheader", name="Trend").is_visible()
    assert page.locator("tbody tr").first.locator("text=/Daily trend/").count() == 1
