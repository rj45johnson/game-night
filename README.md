# Game Night

A couch-friendly front end for [RetroArch](https://www.retroarch.com/) that answers one question:
**what can the four of us play right now?**

Point it at a ROM library and it builds a catalog of only the games worth playing together —
3–4 player **co-op** first, then **4+ player versus/party** games, then hand-picked **2-player
classics** — with box art, title screens and in-game shots. Browse it from the couch with a
controller and launch any game in one press.

## Features

- **Multiplayer-aware catalog.** Console games are identified by CRC32 against libretro's
  [`maxusers`](https://github.com/libretro/libretro-database/tree/master/metadat/maxusers) DATs, which give
  each known dump its official name and maximum player count. Take-turns titles (golf, board games,
  strategy…) that those counts include are filtered out; one entry is kept per game, preferring USA releases.
- **Multitap set up for you.** For 3+ player games it writes RetroArch per-game remaps that attach the
  right adapter: SNES Multitap, Sega Team Player or EA 4-Way Play (Mega Drive), PS1 Multitap. NES Four
  Score (Mesen) and TurboGrafx multitap are handled by the cores.
- **Verified arcade list.** Arcade romsets differ subtly between MAME/FinalBurn Neo versions — a set can be
  on disk yet miss one file the core needs. `gamenight verify` boots each curated set **headless** (no window,
  audio or input) and only verified sets are listed, so nobody hits a "missing files" screen mid-party.
- **Controller-first UI.** D-pad to browse, A to play, LB/RB to switch systems; the selected game's title
  screen and in-game shot stay pinned at the top while you scroll. Works with mouse and keyboard too.
- **Thumbnails on demand** from [thumbnails.libretro.com](https://thumbnails.libretro.com), cached locally,
  with fuzzy name matching for curated titles.
- **Zero dependencies.** Python 3.11+ standard library only.

## Quick start

1. Install RetroArch and the cores listed in `config.example.toml` (Online Updater → Core Downloader),
   plus `fbneo` for arcade. Put the BIOS files your systems need in RetroArch's `system` folder.
2. Lay out your library as `<rom_root>/<System folder>/ROMs/…`.
3. Configure, build, run:

```bash
cp config.example.toml config.toml        # then edit paths
python -m gamenight verify                # optional: headless-check arcade sets
python -m gamenight build                 # scan the library -> data/games.json
python -m gamenight serve                 # opens http://127.0.0.1:8777/
```

Re-run `build` after adding games. `verify` results persist in `data/arcade_verified.json`; pass set
names (`python -m gamenight verify tmnt mslug3`) to re-check just those.

## How it works

```
gamenight/
  config.py      TOML config (paths, systems); refuses non-loopback bind addresses
  catalog.py     ROM scan -> CRC/title match -> multiplayer filter -> dedupe -> games.json
  curated.py     knowledge the databases lack: 2P classics, co-op titles, take-turns filter, arcade/CD lists
  verify.py      headless arcade boot check (parses FinalBurn Neo's "… is required" log lines)
  retroarch.py   launching (interactive + headless) and handing the game window focus
  thumbnails.py  libretro thumbnail lookup + disk cache
  server.py      tiny HTTP API + static UI
  web/index.html the UI (vanilla JS, Gamepad API)
```

Design notes:

- **Matching.** CRCs are tried on the raw image and with a copier/iNES/A78 header stripped; N64 `.v64`/`.n64`
  dumps are byte-swapped to `.z64` first. The NES DAT's CRCs cover NES 2.0 headers that ordinary dumps lack,
  so when no CRC matches, the normalised title is matched instead (skipping hacks, betas and bad dumps).
- **Window focus.** The game is spawned by a background process, and Windows won't let such windows take
  focus — the game would run without receiving any controller input. The launcher waits for RetroArch's
  window and hands it focus. The UI likewise ignores the gamepad unless it is the active window, so a button
  press during a game can't relaunch it.
- **Paths.** Content paths are passed with Windows separators: FinalBurn Neo and MAME derive the romset
  folder by splitting on `\`, and fail to find the set with forward slashes.

## Security

The server can start programs, so it binds to loopback only (enforced in `config.py`), launches games
only by catalog id — never a client-supplied path — and never exposes filesystem paths to the page.

## Development

```bash
python -m unittest discover -s tests -t .
```

## Legal

This project contains **no games, BIOS files or artwork**. You need your own legally obtained dumps.
Thumbnails are fetched from the libretro thumbnail service at runtime and are not redistributed.

## License

MIT — see [LICENSE](LICENSE).
