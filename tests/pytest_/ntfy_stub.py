"""A loopback stand-in for ntfy.sh that records every request it gets."""

import dataclasses
import http.server
import json
import threading


@dataclasses.dataclass(slots=True)
class Seen:
    """One request: method, path with query, headers and body."""

    body: bytes
    headers: dict[str, str]
    method: str
    path: str


class Stub:
    """An HTTP server answering a scripted status per request, then 200."""

    def __init__(self, statuses=()):
        self.seen: list[Seen] = []
        self._statuses = list(statuses)
        stub = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _answer(self):
                length = int(self.headers.get("Content-Length", 0))
                stub.seen.append(
                    Seen(
                        body=self.rfile.read(length),
                        headers={
                            key.lower(): value for key, value in self.headers.items()
                        },
                        method=self.command,
                        path=self.path,
                    )
                )
                status = stub._statuses.pop(0) if stub._statuses else 200
                payload = json.dumps({"id": "abc123"} if status == 200 else {}).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_POST = do_PUT = _answer  # noqa: N815

            def log_message(self, format, *args):
                return

        self._server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}"

    def __enter__(self):
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()
