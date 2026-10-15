"""Configuration: a small TOML file describing where RetroArch and the ROM library live."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.toml"


@dataclass(frozen=True)
class SystemConfig:
    """One console in the ROM library and how to identify/launch its games."""

    folder: str            # sub-folder of library.rom_root, e.g. "Super Nintendo"
    short: str             # display label, e.g. "SNES"
    database: str          # libretro database / thumbnail system name
    core: str              # libretro core base name, e.g. "snes9x"
    header_bytes: int = 0  # copier/iNES header size to also try stripping before CRC matching
    remap_dir: str | None = None  # RetroArch remap folder name, for systems needing a multitap device


@dataclass(frozen=True)
class Config:
    retroarch_exe: Path
    rom_root: Path
    data_dir: Path
    host: str = "127.0.0.1"
    port: int = 8777
    systems: tuple[SystemConfig, ...] = field(default_factory=tuple)

    @property
    def retroarch_dir(self) -> Path:
        return self.retroarch_exe.parent

    def core_path(self, core: str) -> Path:
        return self.retroarch_dir / "cores" / f"{core}_libretro.dll"

    @property
    def catalog_path(self) -> Path:
        return self.data_dir / "games.json"


def load(path: Path = DEFAULT_CONFIG) -> Config:
    """Load and validate the config file. Relative paths resolve against the file's folder."""
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    base = path.resolve().parent

    def resolve(p: str) -> Path:
        q = Path(p)
        return q if q.is_absolute() else (base / q).resolve()

    systems = tuple(
        SystemConfig(
            folder=s["folder"], short=s["short"], database=s["database"], core=s["core"],
            header_bytes=int(s.get("header_bytes", 0)), remap_dir=s.get("remap_dir"),
        )
        for s in raw.get("systems", [])
    )
    server = raw.get("server", {})
    host = server.get("host", "127.0.0.1")
    if host not in ("127.0.0.1", "localhost", "::1"):
        # The API can start processes on this machine; it must never be reachable from the network.
        raise ValueError(f"server.host must be a loopback address, got {host!r}")
    return Config(
        retroarch_exe=resolve(raw["retroarch"]["exe"]),
        rom_root=resolve(raw["library"]["rom_root"]),
        data_dir=resolve(raw["library"].get("data_dir", "data")),
        host=host,
        port=int(server.get("port", 8777)),
        systems=systems,
    )
