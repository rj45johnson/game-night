"""Hand-curated knowledge the databases don't carry: which 2-player games are genuine classics,
which multiplayer games are co-op, which "multiplayer" games are really take-turns, plus the
arcade and CD titles (no CRC-keyed player data exists for those)."""
from __future__ import annotations

import re
from dataclasses import dataclass

# Substrings (lower-case) of official No-Intro names, per system label.
CLASSICS_2P: dict[str, tuple[str, ...]] = {
    "SNES": ("tetris attack", "teenage mutant ninja turtles iv", "super mario kart", "street fighter ii turbo",
             "super street fighter ii", "contra iii", "mortal kombat ii", "killer instinct", "zombies ate my neighbors",
             "donkey kong country (", "donkey kong country 2", "pocky & rocky", "kirby super star", "kirby's avalanche",
             "tetris & dr. mario", "rock n' roll racing", "joe & mac", "yoshi's cookie", "sunset riders", "goof troop",
             "uniracers", "battletoads in battlemaniacs", "super double dragon", "battletoads & double dragon", "lost vikings"),
    "NES": ("contra (usa)", "super c (", "teenage mutant ninja turtles ii", "teenage mutant ninja turtles iii",
            "double dragon ii", "double dragon iii", "battletoads & double dragon", "bubble bobble (", "mario bros. (",
            "ice climber", "balloon fight", "tecmo super bowl", "tecmo bowl", "ice hockey", "blades of steel",
            "river city ransom", "dr. mario", "super dodge ball", "chip 'n dale rescue rangers (", "jackal",
            "ikari warriors (", "contra force", "pro wrestling", "excitebike"),
    "Genesis": ("streets of rage", "contra - hard corps", "hyperstone heist", "tournament fighters", "toejam & earl",
                "dr. robotnik's mean bean machine", "ultimate mortal kombat 3", "mortal kombat ii",
                "street fighter ii' - special champion", "sonic the hedgehog 2", "sonic the hedgehog 3", "golden axe",
                "gunstar heroes", "road rash ii", "columns (", "puyo puyo", "earthworm jim 2", "aladdin"),
    "N64": ("pokemon puzzle league", "mortal kombat trilogy", "1080", "killer instinct gold", "tetrisphere",
            "bust-a-move", "rush 2", "banjo-tooie", "perfect dark", "rakuga kids"),
    "TurboGrafx": ("bonk", "air zonk", "splatterhouse", "blazing lazers", "military madness", "neutopia"),
    "Atari 2600": ("combat", "warlords", "pong", "outlaw", "joust", "mario bros"),
    "Atari 7800": ("joust", "mario bros"),
}

# 3+ player games where everyone is on the same team; listed first in the UI.
COOP_KEYWORDS: tuple[str, ...] = (
    "gauntlet", "secret of mana", "seiken densetsu 3", "dungeon explorer", "swords and serpents",
    "nightmare on elm street", "teenage mutant ninja turtles", "simpsons", "x-men (", "sunset riders",
    "captain commando", "dungeons & dragons", "alien vs. predator", "vendetta", "crime fighters", "bucky o'hare",
    "warriors of fate", "cadillacs and dinosaurs", "king of dragons", "knights of the round", "rampage", "quartet",
    "mystic warriors", "gaiapolis", "hook (", "smash tv", "super smash t.v.", "zombies ate my neighbors",
    "toejam & earl",
)

# The DATs' "users N" counts take-turns games too; these aren't couch multiplayer.
TURN_BASED = re.compile(
    r"golf|bowling|\bpool\b|billiard|casino|poker|black ?jack|trivia|monopoly|chess|mahjong|shogi|\bgo\b|othello|"
    r"genghis khan|bandit kings|nobunaga|three kingdoms|uncharted waters|aerobiz|liberty or death|operation europe|"
    r"p\.t\.o|pacific theater|gemfire|wheel of fortune|jeopardy|family feud|scrabble|boggle|\brisk\b|in 1\b|party mix|"
    r"board game|slot|pachinko|pinball|darts|dominoes|quiz|hearts|solitaire|cards|caesars palace|vegas|lottery|"
    r"california games|summer games|winter games|world games|olympi|decathlon|track & field|hyper sports|"
    r"parlour games|game of life|fortune street|itadaki|clue|miracle piano|m\.u\.l\.e|might and magic|tamagotchi|"
    r"track meet|stadium events|shooting range|win, lose or draw|skins game|brunswick|exertainment|golden nugget|"
    r"pin ?bot|\+ duck hunt|\+ tetris \+|realm \(|lord of darkness",
    re.IGNORECASE,
)

# Electronic Arts titles use the EA 4-Way Play adapter on the Mega Drive; everything else the Sega Team Player.
EA_FOUR_WAY_PLAY: tuple[str, ...] = (
    "nhl", "madden", "fifa", "nba live", "general chaos", "gauntlet iv", "rugby", "pga tour", "mutant league",
    "bill walsh", "jordan vs bird", "coach k", "college football's", "nba showdown", "lakers versus celtics",
    "bulls versus", "team usa basketball", "triple play", "nhlpa",
)


@dataclass(frozen=True)
class CuratedGame:
    """A game with no CRC-keyed metadata: identified by file, described by hand."""

    system: str        # display label
    relpath: str       # path relative to library.rom_root
    title: str         # official title, used for thumbnail lookup
    players: int
    core: str
    database: str      # thumbnail system
    multitap: bool = False
    set_name: str | None = None  # arcade romset name


def _arcade(set_name: str, title: str, players: int, core: str = "fbneo") -> CuratedGame:
    return CuratedGame("Arcade", f"Arcade/ROMs/{set_name}.zip", title, players, core, "MAME", set_name=set_name)


# Arcade candidates. Romset revisions vary between libraries, so the catalog only includes sets that
# `python -m gamenight verify` has confirmed FinalBurn Neo can load (see verify.py). Capcom CPS2 titles
# additionally need their decryption .key files inside the zip.
ARCADE: tuple[CuratedGame, ...] = (
    _arcade("tmnt", "Teenage Mutant Ninja Turtles (World 4 Players)", 4),
    _arcade("tmnt2", "Teenage Mutant Ninja Turtles - Turtles in Time (4 Players ver UAA)", 4),
    _arcade("ssriders", "Sunset Riders (4 Players ver EAC)", 4),
    _arcade("simpsons", "The Simpsons (4 Players World, set 1)", 4),
    _arcade("xmen", "X-Men (4 Players ver EBA)", 4),
    _arcade("xmen6p", "X-Men (6 Players ver ECB)", 6),
    _arcade("captcomm", "Captain Commando (World 911202)", 4),
    _arcade("ddsom", "Dungeons & Dragons - Shadow over Mystara (Euro 960619)", 4),
    _arcade("ddtod", "Dungeons & Dragons - Tower of Doom (Euro 940412)", 4),
    _arcade("avsp", "Alien vs. Predator (Euro 940520)", 3),
    _arcade("gauntlet", "Gauntlet (rev 14)", 4),
    _arcade("gaunt2", "Gauntlet II", 4),
    _arcade("vendetta", "Vendetta (World 4 Players ver. T)", 4),
    _arcade("wwfwfest", "WWF WrestleFest (US set 1)", 4),
    _arcade("nbajam", "NBA Jam (rev 3.01 04-07-93)", 4),
    _arcade("nbajamte", "NBA Jam TE (rev 4.0 03-23-94)", 4),
    _arcade("nbahangt", "NBA Hangtime (rev L1.1 04-16-96)", 4),
    _arcade("mystwarr", "Mystic Warriors (ver EAA)", 4),
    _arcade("quartet", "Quartet (Rev A, 8751 317-0010)", 4),
    _arcade("wof", "Warriors of Fate (World 921031)", 3),
    _arcade("kod", "The King of Dragons (World 910711)", 3),
    _arcade("gaiapols", "Gaiapolis (ver EAF)", 3),
    _arcade("knights", "Knights of the Round (World 911127)", 3),
    _arcade("dino", "Cadillacs and Dinosaurs (World 930201)", 3),
    _arcade("bucky", "Bucky O'Hare (World version EA)", 4),
    _arcade("hook", "Hook (World)", 4),
    _arcade("rampage", "Rampage (revision 3)", 3),
    _arcade("crimfght", "Crime Fighters (World 2 players)", 2),
    _arcade("punisher", "The Punisher (World 930422)", 2),
    _arcade("ffight", "Final Fight (World)", 2),
    _arcade("spf2t", "Super Puzzle Fighter II Turbo (Euro 960529)", 2),
    _arcade("pzloop2", "Puzz Loop 2 (Euro 010302)", 2),
    _arcade("ssf2t", "Super Street Fighter II Turbo (World 940223)", 2),
    _arcade("sf2ce", "Street Fighter II' - Champion Edition (World 920513)", 2),
    _arcade("sfa3", "Street Fighter Alpha 3 (Euro 980904)", 2),
    _arcade("sfiii3", "Street Fighter III 3rd Strike - Fight for the Future (Euro 990608)", 2),
    _arcade("mvsc", "Marvel Vs. Capcom - Clash of Super Heroes (Euro 980123)", 2),
    _arcade("xmvsf", "X-Men Vs. Street Fighter (Euro 961004)", 2),
    _arcade("msh", "Marvel Super Heroes (Euro 951024)", 2),
    _arcade("19xx", "19XX - The War Against Destiny", 2),
    _arcade("progear", "Progear", 2),
    _arcade("1943", "1943 - The Battle of Midway", 2),
    _arcade("mario", "Mario Bros.", 2),
    _arcade("umk3", "Ultimate Mortal Kombat 3", 2),
    _arcade("ddonpach", "DoDonPachi", 2),
    _arcade("bbakraid", "Battle Bakraid - Unlimited Version", 2),
    _arcade("dbreed", "Dragon Breed", 2),
    _arcade("3countb", "3 Count Bout", 2),
    _arcade("pbobblen", "Puzzle Bobble", 2),
    _arcade("pbobble2", "Puzzle Bobble 2", 2),
    _arcade("aliens", "Aliens (World set 1)", 2),
    _arcade("bublbobl", "Bubble Bobble", 2),
    _arcade("joust", "Joust", 2),
    _arcade("mk2", "Mortal Kombat II", 2),
    _arcade("pang", "Pang (World)", 2),
    _arcade("snowbros", "Snow Bros. - Nick & Tom", 2),
    _arcade("twinbee", "TwinBee", 2),
    _arcade("mslug", "Metal Slug - Super Vehicle-001", 2),
    _arcade("mslug2", "Metal Slug 2 - Super Vehicle-001/II", 2),
    _arcade("mslugx", "Metal Slug X - Super Vehicle-001", 2),
    _arcade("mslug3", "Metal Slug 3", 2),
    _arcade("mslug4", "Metal Slug 4", 2),
    _arcade("mslug5", "Metal Slug 5", 2),
    _arcade("kof98", "The King of Fighters '98 - The Slugfest", 2),
    _arcade("kof2002", "The King of Fighters 2002", 2),
    _arcade("garou", "Garou - Mark of the Wolves", 2),
    _arcade("samsho2", "Samurai Shodown II", 2),
    _arcade("wjammers", "Windjammers", 2),
    _arcade("neobombe", "Neo Bomberman", 2),
    _arcade("shocktro", "Shock Troopers", 2),
)

_DC = "Sega - Dreamcast"
_dc = lambda name, title, players: CuratedGame(  # noqa: E731 - table helper
    "Dreamcast", f"Sega Dreamcast/games/{name}/{name}.cdi", title, players, "flycast", _DC)

CD_GAMES: tuple[CuratedGame, ...] = (
    CuratedGame("PS1", "Sony PlayStation/ROMs/Crash Team Racing.bin", "CTR - Crash Team Racing (USA)", 4,
                "swanstation", "Sony - PlayStation", multitap=True),
    CuratedGame("PS1", "Sony PlayStation/ROMs/Worms Armageddon.img", "Worms Armageddon (USA)", 4,
                "swanstation", "Sony - PlayStation"),
    CuratedGame("PS1", "Sony PlayStation/ROMs/Worms World Party.bin", "Worms World Party (USA)", 4,
                "swanstation", "Sony - PlayStation"),
    CuratedGame("PS2", "Sony PlayStation 2/ROMs/DBZ Budokai Tenkaichi 3.ISO",
                "Dragon Ball Z - Budokai Tenkaichi 3 (USA)", 2, "pcsx2", "Sony - PlayStation 2"),
    _dc("Power Stone 2", "Power Stone 2 (USA)", 4),
    _dc("Gauntlet Legends", "Gauntlet Legends (USA)", 4),
    _dc("Toy Commander", "Toy Commander (USA)", 4),
    _dc("Power Stone", "Power Stone (USA)", 2),
    _dc("Soul Calibur", "Soulcalibur (USA)", 2),
    _dc("Marvel vs Capcom", "Marvel vs. Capcom - Clash of Super Heroes (USA)", 2),
    _dc("Street Fighter 3rd Strike", "Street Fighter III - 3rd Strike (USA)", 2),
    _dc("Street Fighter Alpha 3", "Street Fighter Alpha 3 (USA)", 2),
    _dc("Ikaruga", "Ikaruga (Japan)", 2),
    _dc("Dead or Alive 2", "Dead or Alive 2 (USA)", 2),
    _dc("Bust A Move 4", "Bust-A-Move 4 (USA)", 2),
    _dc("Sonic Adventure 2", "Sonic Adventure 2 (USA)", 2),
)
