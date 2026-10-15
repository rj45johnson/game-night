"""Headless check that each curated arcade game loads in FinalBurn Neo -- and if the parent romset
doesn't, which regional variant (clone) does.

Romset contents differ between MAME/FBNeo versions, so a set on disk may still miss a file the core
requires (FBNeo then shows a white "missing files" screen). Often a clone in the same library -- the
US or Japanese revision -- matches FBNeo exactly. Candidates are picked from FBNeo's DAT (same
title, same player count, no bootlegs) and boot-tested headless: FBNeo logs each missing file as
"... is required", which makes the log a reliable verdict.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from . import curated
from .config import Config
from .retroarch import headless_log

log = logging.getLogger(__name__)
FBNEO_DAT_URL = ("https://raw.githubusercontent.com/libretro/FBNeo/master/dats/"
                 "FinalBurn%20Neo%20(ClrMame%20Pro%20XML,%20Arcade%20only).dat")
_MISSING = re.compile(r"with name (\S+) and CRC \S+ is required")
_NOT_THE_REAL_THING = re.compile(r"bootleg|hack|prototype|location test|demo", re.IGNORECASE)
_PLAYERS = re.compile(r"(\d+) Players?", re.IGNORECASE)


class FbneoDat:
    """Romset names, descriptions and parent/clone links from FinalBurn Neo's DAT."""

    def __init__(self, path: Path) -> None:
        root = ET.parse(path).getroot()
        self.description = {g.get("name"): g.findtext("description") or "" for g in root.iter("game")}
        self.cloneof = {g.get("name"): g.get("cloneof") for g in root.iter("game")}

    def variants_of(self, parent: str) -> list[str]:
        """Clones that are the same game: same title (region tags aside), same player count, and not
        a bootleg/hack. (Clone lists also hold bootlegs and even different games, e.g. a Super Mario
        Bros. bootleg filed under Mario Bros.)"""
        want = self.description.get(parent, "")
        title = re.sub(r"\s*\(.*$", "", want).strip().lower()
        players = _PLAYERS.findall(want)
        out = []
        for name, parent_name in self.cloneof.items():
            d = self.description[name]
            if (parent_name == parent and not _NOT_THE_REAL_THING.search(d)
                    and re.sub(r"\s*\(.*$", "", d).strip().lower() == title
                    and _PLAYERS.findall(d) == players):
                out.append(name)
        return sorted(out, key=lambda n: (_region_rank(self.description[n]), n))


def _region_rank(description: str) -> int:
    """US/World first, then Europe, then the rest. Konami encodes region in a version code
    ("ver UBB" = US, "ver EAA" = Europe, "ver JBA" = Japan)."""
    if re.search(r"\b(USA|US|World)\b|\bver U", description):
        return 0
    if re.search(r"\b(Euro|Europe)\b|\bver E", description):
        return 1
    return 2


def _load_dat(cfg: Config) -> FbneoDat:
    path = cfg.data_dir / "cache" / "fbneo_arcade.dat"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        log.info("downloading FinalBurn Neo DAT")
        urllib.request.urlretrieve(FBNEO_DAT_URL, path)
    return FbneoDat(path)


def _boots(cfg: Config, core: str, zip_path: Path) -> tuple[bool, list[str]]:
    text = headless_log(cfg.retroarch_exe, str(cfg.core_path(core)), str(zip_path))
    missing = _MISSING.findall(text)
    return bool(text) and not missing and "Failed to load content" not in text, missing


def verify_arcade(cfg: Config, only: set[str] | None = None) -> dict[str, str | None]:
    """Map each curated arcade set to the romset that boots (itself or a clone), or None."""
    results_path = cfg.data_dir / "arcade_verified.json"
    results: dict[str, str | None] = load_results(cfg)
    dat = _load_dat(cfg)
    rom_dir = cfg.rom_root / "Arcade" / "ROMs"
    for game in curated.ARCADE:
        if only and game.set_name not in only:
            continue
        if not (rom_dir / f"{game.set_name}.zip").exists():
            continue
        candidates = [game.set_name] + [c for c in dat.variants_of(game.set_name) if (rom_dir / f"{c}.zip").exists()]
        working, first_missing = None, []
        for i, name in enumerate(candidates):
            ok, missing = _boots(cfg, game.core, rom_dir / f"{name}.zip")
            if i == 0:
                first_missing = missing
            if ok:
                working = name
                break
        results[game.set_name] = working
        if working == game.set_name:
            log.info("%-10s OK", game.set_name)
        elif working:
            log.info("%-10s OK via %s", game.set_name, working)
        else:
            log.info("%-10s FAIL  missing: %s  (%d variants tried)", game.set_name, ", ".join(first_missing[:4]), len(candidates))
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(json.dumps(results, indent=1))
    return results


def load_results(cfg: Config) -> dict[str, str | None]:
    p = cfg.data_dir / "arcade_verified.json"
    if not p.exists():
        return {}
    raw = json.loads(p.read_text())
    # results written by the first version stored booleans
    return {k: (k if v is True else None if v is False else v) for k, v in raw.items()}
