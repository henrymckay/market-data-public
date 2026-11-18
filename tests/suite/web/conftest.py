import datetime
import functools
import http.server
import pathlib
import threading

import duckdb
import numpy
import playwright.sync_api
import polars
import pytest

from market_data.code import operate, port, transform
from market_data.code.adapt import motherduck, rules
from pytest_ import fake, stub_api

_WEB = pathlib.Path(__file__).parents[3] / "web"
_LAST_DAY = datetime.date(2026, 11, 16)
_API_PORT = 8788
_API_URL = f"http://127.0.0.1:{_API_PORT}"


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
def database(tmp_path_factory: pytest.TempPathFactory, real_universe_session) -> str:
    """A store holding a synthetic year for every instrument, as `compute` leaves it."""
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
            since=fake.whole(tickers),
            bars=bars,
            fetched=started,
            rejected=polars.DataFrame(schema=port.REJECTED),
            universe=real_universe_session,
        )
    )
    operate.compute_signals(
        bars=bars,
        now=lambda: started + datetime.timedelta(minutes=3),
        rules=rules.read_rules(),
        store=store,
    )
    metrics = transform.build_metrics(bars)
    store.replace_metrics(
        metrics,
        transform.build_overview(
            bars=bars,
            metrics=metrics,
            rejected=store.read_rejected_counts(),
            structure=store.read_structure(),
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
    return database


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
def stub(database: str):
    """The API's queries over the synthetic store, where the built page looks for it."""
    connection = duckdb.connect(database, read_only=True)
    stub = stub_api.Stub(connection)
    try:
        server = stub_api.serve(stub, _API_PORT)
    except OSError:
        pytest.fail(f"port {_API_PORT} is taken: the smokes' stub API needs it")
    yield stub
    server.shutdown()
    server.server_close()
    connection.close()


@pytest.fixture(scope="session")
def served(stub: stub_api.Stub):
    """The built dashboard on a free loopback port, with the stub API running."""
    dist = _WEB / "dist"
    if not (dist / "index.html").exists():
        pytest.fail(
            "web/dist is missing: run "
            f"`VITE_API_URL={_API_URL} uv run npm --prefix web run build` first"
        )
    if _API_URL not in "".join(p.read_text() for p in dist.rglob("*.js")):
        pytest.fail(
            f"web/dist was built for another API: rebuild with VITE_API_URL={_API_URL}"
        )
    server = _serve(dist)
    yield f"http://127.0.0.1:{server.server_address[1]}/", stub
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
