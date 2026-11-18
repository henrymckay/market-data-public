"""A stand-in for the Worker: the API's fixed queries run over a DuckDB file (D63)."""

import http.server
import json
import pathlib
import threading
import typing

import duckdb

_QUERIES = pathlib.Path(__file__).parents[2] / "api" / "src" / "queries"
_DATA = {"latest", "overview", "runs", "signals", "stats"}
_PREFIX = "/api/bars/"


def _error(status: int, message: str) -> tuple[int, str]:
    return status, json.dumps({"code": "not_found", "error": message})


class Stub:
    """Answers `/api/*` as the Worker does, for a page served from another origin."""

    def __init__(self, connection: duckdb.DuckDBPyConnection) -> None:
        self._connection = connection
        self._lock = threading.Lock()
        self.requests: list[str] = []

    def _body(self, name: str, *params: str) -> str:
        sql = (_QUERIES / f"{name}.sql").read_text()
        with self._lock:
            row = self._connection.cursor().execute(sql, list(params)).fetchone()
        assert row is not None
        return str(row[0])

    def answer(self, path: str) -> tuple[int, str]:
        """Return the status and JSON body for a request path, query string removed."""
        self.requests.append(path)
        name = path.removeprefix("/api/")
        if path.startswith("/api/") and name in _DATA:
            return 200, self._body(name)
        if path.startswith(_PREFIX):
            slug = path.removeprefix(_PREFIX)
            tickers = json.loads(self._body("slugs"))
            if slug in tickers:
                return 200, self._body("bars", tickers[slug])
            return _error(404, f"No instrument with slug '{slug}'")
        return _error(404, f"No such path '{path}'")


def serve(stub: Stub, port: int) -> http.server.ThreadingHTTPServer:
    """Serve the stub on a loopback port with CORS open, in a daemon thread."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            status, body = stub.answer(self.path.split("?")[0])
            payload = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: typing.Any) -> None:
            return None

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
