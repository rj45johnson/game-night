"""Command line: ``python -m gamenight {build,verify,serve}``."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from . import catalog, config, verify
from .server import serve


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="gamenight", description=__doc__)
    parser.add_argument("--config", type=Path, default=config.DEFAULT_CONFIG, help="path to config.toml")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="scan the ROM library and write the catalog")
    v = sub.add_parser("verify", help="headless-check that curated arcade romsets load")
    v.add_argument("sets", nargs="*", help="only these romset names")
    s = sub.add_parser("serve", help="run the web UI")
    s.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = config.load(args.config)
    if args.command == "build":
        games = catalog.build(cfg, verify.load_results(cfg))
        catalog.save(games, cfg.catalog_path)
        logging.info("catalog: %d games (%d co-op) -> %s", len(games), sum(g.coop for g in games), cfg.catalog_path)
    elif args.command == "verify":
        results = verify.verify_arcade(cfg, set(args.sets) or None)
        logging.info("%d of %d arcade games load", sum(1 for v in results.values() if v), len(results))
    elif args.command == "serve":
        serve(cfg, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
