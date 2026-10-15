"""HTTP API + static page, bound to loopback only.

    GET  /                      the UI (web/index.html)
    GET  /api/games             catalog (display fields only -- no filesystem paths)
    GET  /api/thumb?id=&kind=   cached thumbnail PNG (404 when none exists)
    GET  /api/status            {"running": bool}
    POST /api/launch {"id": n}  start game n (by catalog id; never an arbitrary path)
    POST /api/stop              close the running game
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import catalog
from .config import Config
from .retroarch import Launcher
from .thumbnails import KINDS, ThumbnailCache

log = logging.getLogger(__name__)
WEB_DIR = Path(__file__).resolve().parent / "web"
MAX_BODY = 1024


class App:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.games = {g.id: g for g in catalog.load(cfg.catalog_path)}
        self.thumbs = ThumbnailCache(cfg.data_dir / "thumbs")
        self.launcher = Launcher(cfg.retroarch_exe)

    def public_catalog(self) -> list[dict]:
        return [dict(id=g.id, sys=g.system, name=g.title, players=g.players, coop=g.coop) for g in self.games.values()]


def make_handler(app: App) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "GameNight"

        def log_message(self, fmt: str, *args) -> None:  # route access logs through logging
            log.debug("%s - " + fmt, self.address_string(), *args)

        def _send(self, status: HTTPStatus, body: bytes = b"", ctype: str = "application/json", max_age: int = 0) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            if max_age:
                self.send_header("Cache-Control", f"max-age={max_age}")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, status: HTTPStatus = HTTPStatus.OK) -> None:
            self._send(status, json.dumps(obj).encode())

        def do_GET(self) -> None:
            url = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(url.query)
            if url.path in ("/", "/index.html"):
                return self._send(HTTPStatus.OK, (WEB_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
            if url.path == "/api/games":
                return self._json(app.public_catalog())
            if url.path == "/api/status":
                return self._json({"running": app.launcher.running})
            if url.path == "/api/thumb":
                try:
                    game = app.games[int(query["id"][0])]
                    kind = query.get("kind", [KINDS[0]])[0]
                    data = app.thumbs.get(game, kind)
                except (KeyError, ValueError):
                    return self._send(HTTPStatus.BAD_REQUEST)
                if not data:
                    return self._send(HTTPStatus.NOT_FOUND)
                return self._send(HTTPStatus.OK, data, "image/png", max_age=7 * 24 * 3600)
            self._send(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            url = urllib.parse.urlparse(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            body = self.rfile.read(length)
            if url.path == "/api/launch":
                try:
                    game = app.games[int(json.loads(body)["id"])]
                except (KeyError, ValueError, TypeError, json.JSONDecodeError):
                    return self._send(HTTPStatus.BAD_REQUEST)
                app.launcher.launch(game.core, game.path)
                return self._json({"ok": True, "name": game.title})
            if url.path == "/api/stop":
                app.launcher.stop()
                return self._json({"ok": True})
            self._send(HTTPStatus.NOT_FOUND)

    return Handler


def serve(cfg: Config, open_browser: bool = True) -> None:
    url = f"http://{cfg.host}:{cfg.port}/"
    try:
        httpd = ThreadingHTTPServer((cfg.host, cfg.port), make_handler(App(cfg)))
    except OSError:
        log.info("already running at %s", url)  # e.g. the shortcut was clicked twice
        if open_browser:
            webbrowser.open(url)
        return
    log.info("serving %s", url)
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
