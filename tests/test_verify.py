import tempfile
import unittest
from pathlib import Path

from gamenight.verify import FbneoDat

DAT = """<?xml version="1.0"?>
<datafile>
  <game name="xmen"><description>X-Men (4 Players ver EBA)</description></game>
  <game name="xmenj" cloneof="xmen" romof="xmen"><description>X-Men (4 Players ver JBA)</description></game>
  <game name="xmenu" cloneof="xmen" romof="xmen"><description>X-Men (4 Players ver UBB)</description></game>
  <game name="xmen2p" cloneof="xmen" romof="xmen"><description>X-Men (2 Players ver EAA)</description></game>
  <game name="xmenb" cloneof="xmen" romof="xmen"><description>X-Men (4 Players, bootleg)</description></game>
  <game name="mario"><description>Mario Bros. (US, revision G)</description></game>
  <game name="masao" cloneof="mario" romof="mario"><description>Super Mario Bros. (bootleg of Mario Bros.)</description></game>
  <game name="marioj" cloneof="mario" romof="mario"><description>Mario Bros. (Japan, revision F)</description></game>
</datafile>"""


class Variants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = Path(cls.tmp.name) / "fbneo.dat"
        path.write_text(DAT)
        cls.dat = FbneoDat(path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_same_game_same_player_count_no_bootlegs_us_first(self):
        self.assertEqual(self.dat.variants_of("xmen"), ["xmenu", "xmenj"])

    def test_different_game_filed_as_clone_is_excluded(self):
        self.assertEqual(self.dat.variants_of("mario"), ["marioj"])

    def test_unknown_parent(self):
        self.assertEqual(self.dat.variants_of("nope"), [])


if __name__ == "__main__":
    unittest.main()
