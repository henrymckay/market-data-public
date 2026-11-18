# /// script
# requires-python = ">=3.14"
# dependencies = ["playwright>=1.65"]
# ///
"""Measure the dashboard: cold-load readiness, transfer size, and control latencies."""

import gzip
import os
import statistics
import sys

import playwright.sync_api

_TEXT = ("javascript", "css", "html", "json", "svg")

_TIMED = """
async (selector) => {
  const el = document.querySelector(selector);
  const t0 = performance.now();
  el.click();
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  return performance.now() - t0;
}
"""

_SWITCH = """
async (name) => {
  const t0 = performance.now();
  document.documentElement.dataset.ready = '0';
  const done = new Promise((resolve) => {
    const check = () => {
      const h1 = document.querySelector('h1');
      if (document.documentElement.dataset.ready === '1' && h1 && h1.textContent.includes(name)) resolve();
    };
    new MutationObserver(check).observe(document.documentElement, { attributes: true });
    check();
  });
  return done.then(() => performance.now() - t0);
}
"""


def run(url: str, throttle: bool) -> None:
    with playwright.sync_api.sync_playwright() as play:
        chrome = os.environ.get("CHROME")
        browser = play.chromium.launch(
            args=["--disable-background-networking"], executable_path=chrome
        )
        context = browser.new_context(viewport={"height": 900, "width": 1440})
        page = context.new_page()
        if throttle:
            cdp = context.new_cdp_session(page)
            cdp.send("Network.enable")
            cdp.send(
                "Network.emulateNetworkConditions",
                {
                    "downloadThroughput": 1_600_000 / 8,
                    "latency": 150,
                    "offline": False,
                    "uploadThroughput": 750_000 / 8,
                },
            )
        sizes: dict[str, int] = {}

        def on_response(response: playwright.sync_api.Response) -> None:
            try:
                body = response.body()
            except Exception:
                return
            kind = response.headers.get("content-type", "")
            sizes[response.url] = (
                len(gzip.compress(body, 6))
                if any(t in kind for t in _TEXT)
                else len(body)
            )

        page.on("response", on_response)
        page.goto(url)
        page.wait_for_selector("html[data-ready='1']", timeout=60_000)
        ready = page.evaluate("performance.now()")
        total = sum(sizes.values())
        label = "Fast 4G (1.6 Mbit/s, 150 ms)" if throttle else "loopback"
        print(
            f"[{label}] Markets ready {ready:.0f} ms; transferred {total / 1024:.0f} KB compressed"
        )
        for u, n in sorted(sizes.items(), key=lambda kv: -kv[1])[:6]:
            print(f"    {n / 1024:7.1f} KB  {u.rsplit('/', 1)[-1]}")
        if throttle:
            browser.close()
            return

        def median(selector: str, reset: str | None = None) -> float:
            values = []
            for _ in range(5):
                values.append(page.evaluate(_TIMED, selector))
                if reset:
                    page.evaluate(_TIMED, reset)
            return statistics.median(values)

        g = "[role=group][aria-label=Period]"
        print(
            f"period toggle (1M, 1Y): {median(f'{g} button:nth-child(3)', f'{g} button:nth-child(6)'):.0f} ms"
        )
        print(
            f"asset-class chip (Stocks, All): {median('[role=group][aria-label="Asset class"] button:nth-child(4)', '[role=group][aria-label="Asset class"] button:nth-child(1)'):.0f} ms"
        )
        print(
            f"table sort (1D header): {median('thead th:nth-child(4) button'):.0f} ms"
        )
        # instrument switch: Ticker screen, then each of five instruments
        page.click("[data-view='ticker']:not(html)")
        page.wait_for_selector("html[data-ready='1']")
        switches = []
        for ticker, name in (
            ("AAPL", "Apple"),
            ("^NDX", "Nasdaq 100"),
            ("BTC-USD", "Bitcoin"),
            ("GC=F", "Gold futures"),
            ("MSFT", "Microsoft"),
        ):
            page.keyboard.press("/")
            page.get_by_placeholder("Search by ticker or name").fill(ticker)
            page.wait_for_timeout(int(os.environ.get("DWELL_MS", "0")))
            switches_t = page.evaluate("() => performance.now()")
            page.keyboard.press("Enter")
            elapsed = page.evaluate(_SWITCH, name)
            switches.append(elapsed + 0)
            _ = switches_t
        print(
            "instrument switch (ms): "
            + ", ".join(f"{s:.0f}" for s in switches)
            + f"; median {statistics.median(switches):.0f}"
        )
        r = "[role=group][aria-label=Range]"
        print(
            f"range toggle (1M, 1Y): {median(f'{r} button:nth-child(1)', f'{r} button:nth-child(5)'):.0f} ms"
        )
        browser.close()


if __name__ == "__main__":
    run(sys.argv[1], throttle=False)
    run(sys.argv[1], throttle=True)
