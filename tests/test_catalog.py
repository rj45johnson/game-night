import array
import tempfile
import unittest
import zlib
from pathlib import Path

from gamenight import catalog, config
from gamenight.catalog import Game
from gamenight.thumbnails import server_file_name


def crc(data: bytes) -> str:
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"


class NameHelpers(unittest.TestCase):
    def test_base_title_ignores_tags_articles_and_punctuation(self):
        self.assertEqual(catalog.base_title("Contra (U) [!]"), "contra")
        self.assertEqual(catalog.base_title("Contra (USA)"), "contra")
        self.assertEqual(catalog.base_title("Legend of Zelda, The (USA)"), "legendofzelda")
        self.assertEqual(catalog.base_title("Battletoads & Double Dragon"), catalog.base_title("Battletoads and Double Dragon"))

    def test_region_rank_prefers_usa(self):
        names = ["Game (Europe)", "Game (Japan)", "Game (USA)", "Game (World)"]
        self.assertEqual(min(names, key=catalog.region_rank), "Game (USA)")

    def test_display_title(self):
        g = Game(0, "SNES", "Legend of Zelda, The - A Link to the Past (USA)", 1, False, "", "", "")
        self.assertEqual(g.title, "The Legend of Zelda - A Link to the Past")
        self.assertEqual(Game(0, "Arcade", "Metal Slug 3", 2, False, "", "", "").title, "Metal Slug 3")

    def test_couch_filter(self):
        self.assertTrue(catalog.is_couch_multiplayer_candidate("Super Bomberman (USA)"))
        self.assertFalse(catalog.is_couch_multiplayer_candidate("PGA Tour Golf (USA)"))         # take turns
        self.assertFalse(catalog.is_couch_multiplayer_candidate("Monopoly (USA)"))
        self.assertFalse(catalog.is_couch_multiplayer_candidate("Bomberman '94 (Japan)"))       # region
        self.assertFalse(catalog.is_couch_multiplayer_candidate("FIFA 99 (Unknown) (Pirate)"))
        # a title merely containing "World" must not pass the region check
        self.assertFalse(catalog.is_couch_multiplayer_candidate("Minna de Tamagotchi World (Japan)"))

    def test_server_file_name(self):
        self.assertEqual(server_file_name("Tetris & Dr. Mario (USA)"), "Tetris _ Dr. Mario (USA)")


class RomIdentification(unittest.TestCase):
    def test_header_stripped_crc(self):
        body = bytes(range(256)) * 64          # 16 KiB
        headered = b"NES\x1a" + bytes(12) + body
        self.assertIn(crc(body), catalog.rom_crcs(headered, 16))
        self.assertIn(crc(headered), catalog.rom_crcs(headered, 16))
        smc = bytes(512) + body                # SNES copier header
        self.assertIn(crc(body), catalog.rom_crcs(smc, 512))
        self.assertEqual(catalog.rom_crcs(body, 512), {crc(body)})  # no header present -> nothing stripped

    def test_n64_byte_orders_normalise_to_z64(self):
        z64 = b"\x80\x37\x12\x40" + bytes(range(252))
        v64 = array.array("H", z64); v64.byteswap()
        n64 = array.array("I", z64); n64.byteswap()
        self.assertEqual(catalog.n64_to_z64(v64.tobytes()), z64)
        self.assertEqual(catalog.n64_to_z64(n64.tobytes()), z64)
        self.assertEqual(catalog.n64_to_z64(z64), z64)


class ConfigSafety(unittest.TestCase):
    def test_rejects_non_loopback_host(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.toml"
            p.write_text("[retroarch]\nexe='ra.exe'\n[library]\nrom_root='roms'\n[server]\nhost='0.0.0.0'\n")
            with self.assertRaises(ValueError):
                config.load(p)


class BuildCatalog(unittest.TestCase):
    """End to end against a fake library + a pre-seeded DAT cache (no network)."""

    def test_build_keeps_multiplayer_dedupes_regions_and_writes_multitap(self):
        db = "Nintendo - Super Nintendo Entertainment System"
        rom_bomber, rom_bomber_eu, rom_golf, rom_solo = (bytes([i]) * 4096 for i in (1, 2, 3, 4))
        dat = "\n".join(
            f'game (\n\tcomment "{name}"\n\tusers {users}\n\trom ( crc {crc(data)} )\n)'
            for name, users, data in [("Super Bomberman (USA)", 4, rom_bomber), ("Super Bomberman (Europe)", 4, rom_bomber_eu),
                                      ("PGA Tour Golf (USA)", 4, rom_golf), ("Solo Quest (USA)", 1, rom_solo)])
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            roms = root / "lib" / "Super Nintendo" / "ROMs"; roms.mkdir(parents=True)
            for fname, data in [("sb.smc", rom_bomber), ("sb_eu.smc", rom_bomber_eu), ("golf.smc", rom_golf), ("solo.smc", rom_solo)]:
                (roms / fname).write_bytes(data)
            (root / "data" / "cache").mkdir(parents=True)
            (root / "data" / "cache" / f"{db}.dat").write_text(dat)
            (root / "RetroArch").mkdir()
            cfg_file = root / "config.toml"
            cfg_file.write_text(
                "[retroarch]\nexe = 'RetroArch/retroarch.exe'\n[library]\nrom_root = 'lib'\ndata_dir = 'data'\n"
                f"[[systems]]\nfolder = 'Super Nintendo'\nshort = 'SNES'\ndatabase = '{db}'\ncore = 'snes9x'\n"
                "header_bytes = 512\nremap_dir = 'Snes9x'\n")
            cfg = config.load(cfg_file)

            games = catalog.build(cfg)

            self.assertEqual([g.name for g in games], ["Super Bomberman (USA)"])  # golf filtered, 1P dropped, EU deduped
            self.assertNotIn("/", games[0].path)                                  # Windows separators for the cores
            remap = cfg.retroarch_dir / "config" / "remaps" / "Snes9x" / "sb.rmp"
            self.assertEqual(remap.read_text(), 'input_libretro_device_p2 = "257"\n')


if __name__ == "__main__":
    unittest.main()
