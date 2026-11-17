# /// script
# requires-python = ">=3.14"
# dependencies = ["playwright>=1.65"]
# ///
"""Screenshot each screen at two widths in both schemes."""

import os
import pathlib
import sys

import playwright.sync_api

_SIZES = {"desktop": (1440, 900), "phone": (390, 844)}
_READY = "html[data-ready='1']"
_SCHEMES = ("light", "dark")


def _launch(play: playwright.sync_api.Playwright) -> playwright.sync_api.Browser:
    """Launch the headless shell, or the installed Chrome named by CHROME."""
    chrome = os.environ.get("CHROME")
    if chrome is None:
        return play.chromium.launch()
    return play.chromium.launch(
        args=["--disable-background-networking", "--disable-component-update"],
        executable_path=chrome,
    )


def shoot(url: str, out: pathlib.Path) -> None:
    """Write one PNG per screen, width and scheme, and print what went wrong."""
    out.mkdir(parents=True, exist_ok=True)
    with playwright.sync_api.sync_playwright() as play:
        browser = _launch(play)
        for scheme in _SCHEMES:
            for size, (width, height) in _SIZES.items():
                page = browser.new_page(
                    color_scheme=scheme, viewport={"height": height, "width": width}
                )
                page.on("pageerror", lambda error: print(f"page error: {error}"))
                page.on(
                    "console",
                    lambda message: (
                        print(f"console: {message.text}")
                        if message.type == "error"
                        else None
                    ),
                )
                page.goto(url)
                page.wait_for_selector(_READY, timeout=30_000)
                views = page.eval_on_selector_all(
                    "[data-view]:not(html)", "nodes => nodes.map(n => n.dataset.view)"
                )
                for view in views or ["main"]:
                    if views:
                        page.click(f"[data-view='{view}']:not(html)")
                    page.wait_for_selector(_READY, timeout=30_000)
                    page.wait_for_load_state("networkidle")
                    wide = "document.documentElement.scrollWidth > innerWidth"
                    if page.evaluate(wide) is True:
                        print(f"sideways scroll: {view} {scheme} {size}")
                    page.screenshot(
                        full_page=True, path=out / f"{view}-{scheme}-{size}.png"
                    )
                page.close()
        browser.close()


if __name__ == "__main__":
    shoot(sys.argv[1], pathlib.Path(sys.argv[2]))
