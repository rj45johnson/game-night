"""Box art / title screen / in-game thumbnails from thumbnails.libretro.com, fetched on demand and
cached on disk.

Thumbnails are published per system under the official game name with a few characters replaced.
Curated titles don't always match exactly, so lookups fall back to the server's directory listing
(cached too) and pick the closest normalised name, preferring USA/World releases.
"""
from __future__ import annotations

import difflib
import json
import logging
import re
import threading
import urllib.parse
import urllib.request
from pathlib import Path

from .catalog import Game, base_title

log = logging.getLogger(__name__)
BASE_URL = "https://thumbnails.libretro.com"
KINDS = ("Named_Boxarts", "Named_Titles", "Named_Snaps")
_REGION_PREFERENCE = ("(USA)", "(USA, Europe)", "(World)", "(World ", "(US ", "(Euro", "(Europe)", "(Japan, USA)")


def server_file_name(name: str) -> str:
    """libretro replaces these characters in thumbnail file names."""
    return re.sub(r'[&*/:`<>?\\|"]', "_", name)


class ThumbnailCache:
    def __init__(self, cache_dir: Path) -> None:
        self.dir = cache_dir
        self._listings: dict[tuple[str, str], list[str]] = {}
        self._lock = threading.Lock()

    def get(self, game: Game, kind: str) -> bytes | None:
        if kind not in KINDS:
            raise ValueError(kind)
        # Keyed by name rather than id: ids are reassigned whenever the catalog is rebuilt.
        path = self.dir / game.thumb_system / kind / (re.sub(r"[^\w\- ]", "_", game.name)[:150] + ".png")
        miss = path.with_suffix(".none")
        if path.exists():
            return path.read_bytes()
        if miss.exists():
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        data = None
        remote = self._resolve(game, kind)
        if remote:
            try:
                data = _fetch(f"{BASE_URL}/{urllib.parse.quote(game.thumb_system)}/{kind}/{urllib.parse.quote(remote)}.png")
            except OSError as exc:
                log.info("thumbnail fetch failed for %s: %s", game.name, exc)
                return None  # transient: don't cache the miss
        if data:
            path.write_bytes(data)
        else:
            miss.touch()
        return data

    def _resolve(self, game: Game, kind: str) -> str | None:
        names = self._listing(game.thumb_system, kind)
        exact_name = server_file_name(game.name)
        if exact_name in names:
            return exact_name
        want = base_title(game.name)
        candidates = [n for n in names if base_title(n) == want]
        if not candidates:
            by_key: dict[str, list[str]] = {}
            for n in names:
                by_key.setdefault(base_title(n), []).append(n)
            close = difflib.get_close_matches(want, list(by_key), n=1, cutoff=0.8)
            candidates = by_key[close[0]] if close else []
        if not candidates:
            return None
        return min(candidates, key=lambda n: (min((i for i, r in enumerate(_REGION_PREFERENCE) if r in n),
                                                   default=99), len(n)))

    def _listing(self, system: str, kind: str) -> list[str]:
        key = (system, kind)
        with self._lock:
            if key in self._listings:
                return self._listings[key]
        cache = self.dir / "_listings" / f"{system}__{kind}.json"
        if cache.exists():
            names = json.loads(cache.read_text(encoding="utf-8"))
        else:
            try:
                html = _fetch(f"{BASE_URL}/{urllib.parse.quote(system)}/{kind}/").decode("utf-8", "replace")
                names = [urllib.parse.unquote(h)[:-4] for h in re.findall(r'href="([^"]+\.png)"', html)]
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps(names), encoding="utf-8")
            except OSError as exc:
                log.warning("thumbnail listing unavailable for %s/%s: %s", system, kind, exc)
                names = []
        with self._lock:
            self._listings[key] = names
        return names


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()
