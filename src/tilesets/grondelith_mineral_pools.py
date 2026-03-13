"""
Tile classes for the Grondelith Mineral Pools dungeon.
This area covers four distinct zones:
  Zone 1  — Sacred Atrium     (tiles: GrondelithEntry, GrondelithRitualChamber,
                                       GrondelithAtrium, GrondelithAlcove,
                                       GrondelithPoolEast, GrondelithHighBasin)
  Zone 2  — Corrupted Channels (tiles: GrondelithChannelEntry, GrondelithCrevice,
                                        GrondelithChannelNorth, GrondelithNorthPocket,
                                        GrondelithDeepWest, GrondelithDeepEast,
                                        GrondelithDeepPocket, GrondelithNarrowPass,
                                        GrondelithFloodedPass)
  Zone 3  — Secret Luminous Grotto (tile: GrondelithGrotto)
  Zone 4  — Boss Approach + Arena  (tiles: GrondelithApproach, GrondelithArena)
"""
from src.tiles import *


# ---------------------------------------------------------------------------
# Zone 1: Sacred Atrium
# ---------------------------------------------------------------------------

class GrondelithEntry(MapTile):
    """Entry transition from Grondia — top of the descent path."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "The path descends here, carved smooth by centuries of Golemite feet. "
            "The air changes abruptly — cool and damp, carrying a mineral freshness "
            "that feels almost ceremonial. Far below, a faint blue luminescence "
            "pulses steadily from the pools."
        ))
        self.symbol = '▽'


class GrondelithRitualChamber(MapTile):
    """Small side chamber off the descent path. Covered in Golemite ritual markings."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "A small chamber off the descent path, its angles too precise to be natural. "
            "Every surface is covered in careful Golemite markings — row upon row of etched "
            "script in a language Jean cannot read. At the chamber's centre, a shallow carved "
            "basin sits worn smooth. It was regularly used; that much is clear from the "
            "texture of the stone around it."
        ))
        self.symbol = '□'


class GrondelithAtrium(MapTile):
    """Main vaulted atrium. Sacred heart of the Grondelith Mineral Pools."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "A vaulted natural cathedral stops Jean mid-step. Dozens of spring-fed pools "
            "fill the basin below, their water a luminous, milky blue — almost alive — "
            "flowing in precise, swirling channels carved into polished stone over countless "
            "generations. Golemite tools line the walls in careful rows: stone picks, broad "
            "chisels, flat-headed rammers. All recently used. All reverently set aside. "
            "This place was tended. This place was loved."
        ))
        self.symbol = '≈'


class GrondelithAlcove(MapTile):
    """Quiet west-wing alcove. Worn smooth by generations of Golemite prayer."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "A quiet alcove barely touched by visitors. The stone is worn perfectly smooth — "
            "polished by generations of Golemite hands in prayer or grief. A shallow basin "
            "holds a thin film of pristine water. Along the basin's lip, small smooth stones "
            "are laid in careful rows, featureless from decades of water — grief stones, "
            "placed here by those who had lost someone."
        ))
        self.symbol = '○'


class GrondelithPoolEast(MapTile):
    """East extension of the atrium. Large, clear central pool with Golemite record etchings."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "The main atrium opens into a wider basin to the east. The central pool here is "
            "the largest in the complex — impossibly clear, with a mineral sandy floor visible "
            "ten feet down. The silence is complete except for a faint trickle from a spring "
            "above. On the far wall, more tool racks. Near them, etchings that record dates "
            "or intervals — the marks of Golemite years, counting an unbroken history of tending."
        ))
        self.symbol = '≈'


class GrondelithHighBasin(MapTile):
    """Easternmost atrium alcove. Highest point of the complex; the oldest pool."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "The easternmost reach of the atrium. A natural stone shelf lifts the floor "
            "several feet, and a smaller basin sits here, fed by a trickle from above. "
            "The water is marginally clearer than the rest — the oldest pool, fed by the "
            "oldest spring. The stone shelf edge is worn smooth from long use."
        ))
        self.symbol = '○'


# ---------------------------------------------------------------------------
# Zone 2: Corrupted Channels
# ---------------------------------------------------------------------------

class GrondelithChannelEntry(MapTile):
    """The first corrupted tile. Sharp visual contrast with the atrium."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "The colour changes here. The milky-blue water turns a sickly iridescent green; "
            "thick slime coats the walls and floor, and the air turns greasy and sour. "
            "On the west wall, barely visible beneath a coat of goop, a narrow crevice "
            "breathes a ghost of clean air — as though something pristine holds the "
            "corruption at bay from the other side."
        ))
        self.symbol = '%'


class GrondelithCrevice(MapTile):
    """Narrow hidden passage between the Corrupted Channels and the Luminous Grotto."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "A gap barely wide enough to squeeze through. The slime here is thin — "
            "reluctant, almost repelled. Beyond: cold, clean air, sharp with minerals. "
            "Silence. Whatever is inside, the corruption has not reached it."
        ))
        self.symbol = '─'


class GrondelithChannelNorth(MapTile):
    """Northern channel branch. Stone bridge over slime; eastern pocket ahead."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "A narrow stone walkway bridges a channel of slime too thick to be called liquid. "
            "The stone underfoot has a faint give — the corruption eating through from below. "
            "To the east, a sealed chamber echoes with something feeding."
        ))
        self.symbol = '%'


class GrondelithNorthPocket(MapTile):
    """Sealed mini-boss pocket. Dense slimes cluster around a stone shelf."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "A sealed pocket of concentrated corruption. Every surface is sheeted in thick "
            "slime. A stone shelf juts from the east wall above the slime line, its surface "
            "worn smooth — this pocket was once a workroom or storage area, before the "
            "infestation claimed it."
        ))
        self.symbol = '!'


class GrondelithDeepWest(MapTile):
    """Main spine of the deep channels. Acid pitting, bats, the rumbling grows louder."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "The corruption grows denser. The walls show deep acid pitting — stone dissolved "
            "rather than worn. A walkway above a near-stationary pool connects to the passages "
            "east and south. From the ceiling, a leathery chittering — something nesting above, "
            "disturbed by movement. The rumbling from the south is unmistakable now."
        ))
        self.symbol = '%'


class GrondelithDeepEast(MapTile):
    """Eastern deep channel. First Elder Slime encounter. Older, layered corruption."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "The eastern branch of the channels opens into a wider cavern. The slime here "
            "is layered and old — it has been feeding on the stone for longer. The walls "
            "show dissolution down to raw mineral. Near the far wall, something large and "
            "deliberate shifts in the muck."
        ))
        self.symbol = '%'


class GrondelithDeepPocket(MapTile):
    """Far eastern dead-end. Collapsed ceiling; older, drier corruption sealing off the space."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "A low chamber where the ceiling has partially collapsed. The rubble is coated "
            "in old, dry slime — this back pocket was sealed off from the main infestation "
            "early, and the corruption here is older, quieter, more settled. The collapsed "
            "stone exposes raw mineral beneath."
        ))
        self.symbol = '!'


class GrondelithNarrowPass(MapTile):
    """Narrow choke point. Arm-width passage with slime-coated walls. Connects to flooded loop."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "The main passage narrows here — the walls close to arm's width for a stretch "
            "of twenty feet, the slime coating them making passage distinctly unpleasant. "
            "The south end opens abruptly into a larger space where the rumbling is now "
            "overwhelming."
        ))
        self.symbol = '%'


class GrondelithFloodedPass(MapTile):
    """Flooded loop passage. Second Elder Slime encounter. Stone islands over dissolved floor."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "The floor has dissolved here — slime ate through the stone, leaving a flooded "
            "passage crossed by a series of irregular stone islands. The walls show the "
            "water line from before the dissolution: a clean band of stone above, corrupted "
            "wreckage below."
        ))
        self.symbol = '%'


# ---------------------------------------------------------------------------
# Zone 3: Secret Luminous Grotto
# ---------------------------------------------------------------------------

class GrondelithGrotto(MapTile):
    """
    Hidden puzzle room. Completely untouched by corruption.
    Contains the GeminateGeode puzzle object and rewards EnchantedGolemitePauldron.
    """

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "The sourness of the channels disappears the moment Jean steps through. "
            "The air is cold and clean — sharp with minerals, with something older underneath. "
            "Mineral veins run through every surface, pulsing with a tricolor glow: "
            "blue-white, amber-gold, pale silver-grey. The light is steady and quiet."
        ))
        self.symbol = '✦'


# ---------------------------------------------------------------------------
# Zone 4: Boss Approach + Arena
# ---------------------------------------------------------------------------

class GrondelithApproach(MapTile):
    """Pre-boss approach. Rhythmic pulse underfoot. The passage south opens on the arena."""

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "The cavern narrows again. The rumbling is a physical presence now — coming up "
            "through Jean's boots in slow, rhythmic pulses, each one slightly stronger than "
            "the last. The green slime on the walls shudders with each pulse, as if breathing. "
            "The passage south opens into a vast space full of pulsing verdant light."
        ))
        self.symbol = '▼'


class GrondelithArena(MapTile):
    """
    King Slime boss arena. Circular cavern; single clean stone island at centre.
    Description updates after the boss is defeated via AfterDefeatingKingSlime event.
    """

    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description=(
            "A circular cavern cathedral-wide. An immense pool of pulsating green slime "
            "fills the chamber from wall to wall, leaving only a single island of clean "
            "stone at the centre. Something colossal shifts beneath the surface — "
            "a mountain of corrupted mass, slowly rising."
        ))
        self.symbol = '@'
