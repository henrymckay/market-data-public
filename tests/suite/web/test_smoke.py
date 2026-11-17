import pathlib

import pytest

pytestmark = pytest.mark.slow

_READY = "html[data-ready='1']"


def _open(page, served, query=""):
    page.goto(f"{served[0]}{query}")
    page.wait_for_selector(_READY, timeout=30_000)


def test_when_markets_opens_then_tiles_charts_and_table_draw_without_error(
    page, served
):
    _open(page, served)

    assert page.locator("main h2").all_inner_texts()[0].startswith("Stocks by sector")
    assert page.get_by_text("S&P 500").first.is_visible()
    assert page.locator("tbody tr").count() >= 80
    assert page.locator("button[aria-label^='NVDA']").count() == 1
    assert page.errors == []


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
    page.route("**/bars/aapl.parquet*", lambda route: route.abort())

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
    import polars

    empty = pathlib.Path(served[1]) / "data" / "runs.parquet"
    original = empty.read_bytes()
    polars.read_parquet(empty).head(0).write_parquet(empty, compression="snappy")
    try:
        _open(page, served, "?view=runs")
        assert page.get_by_text(
            "No runs yet — the first nightly writes here."
        ).is_visible()
    finally:
        empty.write_bytes(original)


def test_when_the_scheme_is_toggled_then_it_is_kept_across_a_reload(page, served):
    _open(page, served)

    page.get_by_role("button", name="Switch to the dark scheme").click()
    page.reload()
    page.wait_for_selector(_READY)

    assert page.evaluate("document.documentElement.classList.contains('dark')") is True
