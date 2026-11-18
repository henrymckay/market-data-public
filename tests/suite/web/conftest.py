import datetime
import functools
import http.server
import pathlib
import shutil
import threading

import numpy
import playwright.sync_api
import polars
import pytest
import typer.testing

from market_data.code import port, transform
from market_data.code.adapt import motherduck
from market_data.code.drive import cli

_WEB = pathlib.Path(__file__).parents[3] / "web"
_LAST_DAY = datetime.date(2026, 11, 16)


def _walk(ticker: str, days: list[datetime.date], rng: numpy.random.Generator):
    steps = rng.normal(0.0003, 0.012, len(days))
    close = 50.0 * numpy.exp(numpy.cumsum(steps))
    return polars.DataFrame(
        {
            "adj_close": close,
            "close": close,
            "day": days,
            "dividend": numpy.where(numpy.arange(len(days)) % 90 == 0, 0.2, 0.0),
            "high": close * 1.01,
            "low": close * 0.99,
            "open": close * 1.001,
            "split": numpy.zeros(len(days)),
            "ticker": ticker,
            "volume": rng.integers(1_000_000, 9_000_000, len(days)),
        },
        schema=port.BARS,
    )


@pytest.fixture(scope="session")
def site_data(
    tmp_path_factory: pytest.TempPathFactory, real_universe_session
) -> pathlib.Path:
    """The site data of a synthetic year for every instrument, exported by the CLI."""
    root = tmp_path_factory.mktemp("site")
    database = str(root / "market.duckdb")
    rng = numpy.random.default_rng(7)
    days = [
        _LAST_DAY - datetime.timedelta(days=offset) for offset in range(540, -1, -1)
    ]
    days = [day for day in days if day.weekday() < 5]
    tickers = real_universe_session.get_column("ticker").to_list()
    bars = polars.concat([_walk(ticker, days, rng) for ticker in tickers])
    connection = motherduck.connect(database)
    store = motherduck.Store(connection)
    started = datetime.datetime(2026, 11, 17, 2, 17, tzinfo=datetime.UTC)
    store.replace(
        port.Load(
            answered=tuple(tickers),
            bars=bars,
            fetched=started,
            rejected=polars.DataFrame(schema=port.REJECTED),
            universe=real_universe_session,
        )
    )
    metrics = transform.build_metrics(bars)
    store.replace_metrics(
        metrics,
        transform.build_overview(
            bars=bars,
            metrics=metrics,
            rejected=store.read_rejected_counts(),
            tickers=store.read_tickers(),
        ),
    )
    for source, rows in (("yahoo", bars.height), ("metrics", 1958)):
        store.append_run(
            transform.Run(
                day=_LAST_DAY,
                ended=datetime.datetime.now(datetime.UTC),
                failed_items=0,
                last_day=_LAST_DAY,
                outcome=transform.Outcome.STORED,
                rejected=0,
                requests=0,
                rows=rows,
                source=source,
                started=started,
            )
        )
    connection.close()
    out = root / "data"
    import os

    os.environ["MARKET_DATA_DATABASE"] = database
    try:
        result = typer.testing.CliRunner().invoke(
            cli.app, ["export", "--output", str(out)]
        )
    finally:
        del os.environ["MARKET_DATA_DATABASE"]
    assert result.exit_code == 0, result.stderr
    return out


@pytest.fixture(scope="session")
def real_universe_session() -> polars.DataFrame:
    from market_data.code.adapt import universe

    return universe.read_universe()


def _serve(directory: pathlib.Path):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return None

    handler = functools.partial(Quiet, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture(scope="session")
def served(tmp_path_factory: pytest.TempPathFactory, site_data: pathlib.Path):
    """The built dashboard over the synthetic site data, on a free loopback port."""
    dist = _WEB / "dist"
    if not (dist / "index.html").exists():
        pytest.fail(
            "web/dist is missing: run `uv run npm --prefix web run build` first"
        )
    root = tmp_path_factory.mktemp("served")
    shutil.copytree(
        dist, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns("data")
    )
    shutil.copytree(site_data, root / "data")
    server = _serve(root)
    yield f"http://127.0.0.1:{server.server_address[1]}/", root
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def browser():
    import os

    with playwright.sync_api.sync_playwright() as play:
        chrome = os.environ.get("CHROME")
        if chrome is None:
            instance = play.chromium.launch()
        else:
            instance = play.chromium.launch(
                args=["--disable-background-networking", "--disable-component-update"],
                executable_path=chrome,
            )
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"height": 900, "width": 1440})
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.errors = errors  # type: ignore[attr-defined]
    yield page
    context.close()
