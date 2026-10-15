"""Builds the game catalog.

Console games are identified by CRC32 against libretro's ``metadat/maxusers`` DATs, which give each
known dump its official No-Intro name and maximum player count. A game is kept when it supports 3+
simultaneous players, or is a hand-picked 2-player classic (see ``curated``). When a CRC doesn't match
-- notably NES, whose DAT CRCs cover NES 2.0 headers that ordinary dumps lack -- the normalised title
is matched instead. One entry is kept per game, preferring the USA release.
"""
from __future__ import annotations

import array
import json
import logging
import os
import re
import urllib.parse
import urllib.request
import zipfile
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path

from . import curated
from .config import Config, SystemConfig

log = logging.getLogger(__name__)

MAXUSERS_URL = "https://raw.githubusercontent.com/libretro/libretro-database/master/metadat/maxusers/{}.dat"
REGION_PREFERENCE = ("(USA)", "(USA, Europe)", "(World)", "(USA,", "(Europe)", "(Japan, USA)")
_ALLOWED_REGION = re.compile(r"usa|world|europe", re.IGNORECASE)
_BAD_DUMP = re.compile(r"\((J|E|G|F|S|I|Beta|Proto|Hack|PD|Unl)\b|\[(b|h|t|o|a|f|p)\d*\]|hack", re.IGNORECASE)
_NON_RELEASE = re.compile(r"\((Beta|Proto|Demo|Sample|Kiosk|Pirate|Unl)", re.IGNORECASE)

# Genesis Plus GX / Snes9x libretro device ids for multitap adapters.
SNES_MULTITAP = 257                    # RETRO_DEVICE_JOYPAD_MULTITAP, port 2 -> players 2-5
MD_4WAYPLAY, MD_TEAMPLAYER = 1025, 1537  # EA 4-Way Play (both ports) / Sega Team Player (port 1)


@dataclass
class Game:
    id: int
    system: str
    name: str
    players: int
    coop: bool
    path: str
    core: str
    thumb_system: str
    set_name: str | None = None

    @property
    def title(self) -> str:
        """Display title: no region/revision tags, 'Legend of X, The' -> 'The Legend of X'."""
        t = re.sub(r"\s*\([^)]*\)", "", self.name).strip()
        m = re.match(r"^(.*), The( - .*)?$", t)
        return f"The {m.group(1)}{m.group(2) or ''}" if m else t


# --- name helpers -------------------------------------------------------------------------------

def base_title(name: str) -> str:
    """Region/flag-free, punctuation-free key: 'Contra (U) [!]' and 'Contra (USA)' -> 'contra'."""
    s = re.sub(r"\s*[\(\[].*$", "", name).lower().replace("&", "and")
    s = re.sub(r"^the |, the$", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def region_rank(name: str) -> int:
    return min((i for i, r in enumerate(REGION_PREFERENCE) if r in name), default=len(REGION_PREFERENCE))


def first_tag(name: str) -> str:
    m = re.search(r"\(([^)]*)\)", name)
    return m.group(1) if m else ""


def is_couch_multiplayer_candidate(name: str) -> bool:
    """False for take-turns games, non-Western-only releases and unlicensed/pirate dumps."""
    return (not curated.TURN_BASED.search(name)
            and bool(_ALLOWED_REGION.search(first_tag(name)))
            and not re.search(r"\((pirate|unl)", name, re.IGNORECASE))


# --- ROM identification -------------------------------------------------------------------------

def rom_crcs(data: bytes, header_bytes: int) -> set[str]:
    """CRC32 of the image, plus the CRC with a copier/iNES/A78 header stripped when one may be present."""
    crcs = {f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"}
    if header_bytes and len(data) > header_bytes and (len(data) % 1024 == header_bytes % 1024 or header_bytes in (16, 128)):
        crcs.add(f"{zlib.crc32(data[header_bytes:]) & 0xFFFFFFFF:08X}")
    return crcs


def n64_to_z64(data: bytes) -> bytes:
    """Normalise byte-swapped (.v64) and little-endian (.n64) dumps to big-endian .z64 for lookup."""
    magic = data[:4]
    if magic == b"\x37\x80\x40\x12":
        a = array.array("H", data); a.byteswap(); return a.tobytes()
    if magic == b"\x40\x12\x37\x80":
        a = array.array("I", data); a.byteswap(); return a.tobytes()
    return data


def read_rom(path: Path) -> bytes:
    """The ROM image itself: the largest member of a zip, or the file contents."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            member = max((i for i in z.infolist() if not i.is_dir()), key=lambda i: i.file_size)
            return z.read(member)
    return path.read_bytes()


@dataclass
class DatIndex:
    by_crc: dict[str, tuple[str, int]]
    by_title: dict[str, tuple[str, int]]


def load_maxusers_dat(database: str, cache_dir: Path) -> DatIndex:
    cache = cache_dir / f"{database}.dat"
    if not cache.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        log.info("downloading maxusers DAT: %s", database)
        urllib.request.urlretrieve(MAXUSERS_URL.format(urllib.parse.quote(database)), cache)
    text = cache.read_text(encoding="utf-8", errors="replace")
    by_crc: dict[str, tuple[str, int]] = {}
    by_title: dict[str, tuple[str, int]] = {}
    for m in re.finditer(r'comment "(.*?)"\s+users (\d+)\s+rom \( crc ([0-9A-Fa-f]{8}) \)', text):
        entry = (m.group(1), int(m.group(2)))
        by_crc[m.group(3).upper()] = entry
        if _NON_RELEASE.search(entry[0]):
            continue
        key = base_title(entry[0])
        if key not in by_title or region_rank(entry[0]) < region_rank(by_title[key][0]):
            by_title[key] = entry
    return DatIndex(by_crc, by_title)


# --- per-system scan ----------------------------------------------------------------------------

def scan_system(cfg: Config, system: SystemConfig, dat: DatIndex) -> list[dict]:
    rom_dir = cfg.rom_root / system.folder / "ROMs"
    if not rom_dir.is_dir():
        log.warning("no ROM folder for %s: %s", system.short, rom_dir)
        return []
    classics = curated.CLASSICS_2P.get(system.short, ())
    best: dict[str, tuple[tuple, dict]] = {}
    for path in sorted(rom_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() in (".txt", ".srm", ".sav", ".dsv"):
            continue
        try:
            data = read_rom(path)
        except (zipfile.BadZipFile, OSError, ValueError) as exc:
            log.warning("unreadable %s: %s", path.name, exc)
            continue
        if system.short == "N64":
            data = n64_to_z64(data)
        hit = next((dat.by_crc[c] for c in rom_crcs(data, system.header_bytes) if c in dat.by_crc), None)
        matched_by_crc = hit is not None
        if hit is None and not _BAD_DUMP.search(path.stem):
            hit = dat.by_title.get(base_title(path.stem))
        if hit is None:
            continue
        name, players = hit
        if not is_couch_multiplayer_candidate(name):
            continue
        if players < 3 and not (players == 2 and any(s in name.lower() for s in classics)):
            continue
        score = (region_rank(name), 0 if matched_by_crc else 1, 0 if "[!]" in path.name else 1)
        entry = dict(system=system.short, name=name, players=players, path=path,
                     core=cfg.core_path(system.core), thumb_system=system.database, remap_dir=system.remap_dir)
        key = base_title(name)
        if key not in best or score < best[key][0]:
            best[key] = (score, entry)
    found = [e for _, e in best.values()]
    log.info("%-12s %4d games", system.short, len(found))
    return found


# --- RetroArch per-game settings ----------------------------------------------------------------

def write_multitap_remap(cfg: Config, entry: dict) -> None:
    """Per-game RetroArch remap enabling the system's multitap, keyed by content file name."""
    lname = entry["name"].lower()
    if entry["system"] == "SNES":
        body = f'input_libretro_device_p2 = "{SNES_MULTITAP}"\n'
    elif any(k in lname for k in curated.EA_FOUR_WAY_PLAY):
        body = f'input_libretro_device_p1 = "{MD_4WAYPLAY}"\ninput_libretro_device_p2 = "{MD_4WAYPLAY}"\n'
    else:
        body = f'input_libretro_device_p1 = "{MD_TEAMPLAYER}"\n'
    folder = cfg.retroarch_dir / "config" / "remaps" / entry["remap_dir"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{Path(entry['path']).stem}.rmp").write_text(body, encoding="ascii")


def prepare_disc(path: Path) -> Path:
    """Raw .bin/.img dumps need a cue sheet for the PlayStation core."""
    if path.suffix.lower() not in (".bin", ".img"):
        return path
    cue = path.with_suffix(".cue")
    if not cue.exists():
        cue.write_text(f'FILE "{path.name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n', encoding="ascii")
    return cue


def enable_ps1_multitap(cfg: Config, content: Path) -> None:
    folder = cfg.retroarch_dir / "config" / "SwanStation"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{content.stem}.opt").write_text('swanstation_ControllerPorts_MultitapMode = "Port1Only"\n', encoding="ascii")


# --- build --------------------------------------------------------------------------------------

def is_coop(name: str, players: int) -> bool:
    lname = name.lower()
    return players >= 3 and any(k in lname for k in curated.COOP_KEYWORDS)


def build(cfg: Config, arcade_verified: dict[str, str | None] | None = None) -> list[Game]:
    """`arcade_verified` maps curated arcade sets to the romset that boots (itself or a clone) or None."""
    """Scan the library and return the catalog, co-op games first, then alphabetical."""
    cache = cfg.data_dir / "cache"
    entries: list[dict] = []
    for system in cfg.systems:
        found = scan_system(cfg, system, load_maxusers_dat(system.database, cache))
        for e in found:
            if e["players"] >= 3 and e["remap_dir"]:
                write_multitap_remap(cfg, e)
        entries += found

    verified = arcade_verified or {}
    for g in curated.ARCADE + curated.CD_GAMES:
        path = cfg.rom_root / g.relpath
        if g.set_name and verified:
            working = verified.get(g.set_name)
            if not working:
                continue  # once `verify` has run, only arcade games it confirmed are listed
            path = path.with_name(f"{working}.zip")  # may be a regional variant of the curated set
        if not path.exists():
            continue
        content = prepare_disc(path)
        if g.multitap:
            enable_ps1_multitap(cfg, content)
        entries.append(dict(system=g.system, name=g.title, players=g.players, path=content,
                            core=cfg.core_path(g.core), thumb_system=g.database, set_name=g.set_name))

    def sort_key(e: dict) -> tuple:
        return (not is_coop(e["name"], e["players"]), re.sub(r"^the ", "", e["name"].lower()), e["system"])

    games = []
    for i, e in enumerate(sorted(entries, key=sort_key)):
        games.append(Game(
            id=i, system=e["system"], name=e["name"], players=e["players"], coop=is_coop(e["name"], e["players"]),
            # Windows separators matter: FBNeo / MAME derive the romset folder by splitting on '\'.
            path=os.path.normpath(str(e["path"])), core=os.path.normpath(str(e["core"])),
            thumb_system=e["thumb_system"], set_name=e.get("set_name"),
        ))
    return games


def save(games: list[Game], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(g) for g in games], indent=1, ensure_ascii=False), encoding="utf-8")


def load(path: Path) -> list[Game]:
    return [Game(**g) for g in json.loads(path.read_text(encoding="utf-8"))]
