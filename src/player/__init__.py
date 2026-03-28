"""Player package — Jean Claire, the crusader protagonist.

The Player class is composed from focused mixin modules:

  _leveling.py    — gain_exp, level_up, learn_skill
  _combat.py      — attack, death, heat, move management
  _inventory.py   — equip, use, take, weight, gold stacking
  _movement.py    — map navigation, teleport, flee, party recall
  _exploration.py — look, view, search, view_map
  _ui.py          — skill menu, status display, HP/FP bars
  _world.py       — merchant refresh
  _debug.py       — cheat/debug commands

External callers continue to use ``from player import Player`` or
``from player import Player, generate_output_grid`` unchanged.
"""

# These are intentionally re-exported from the package namespace so that tests
# can patch them at the player package level (e.g. @patch('player.random.uniform')).
# The actual usage lives in the mixin files (_combat.py, _movement.py, etc.), but
# unittest.mock resolves patches against the module where the name is looked up,
# which is here. Do not remove these imports — the patch targets will break.
import random  # noqa: F401
import time  # noqa: F401

import items  # type: ignore
import functions  # type: ignore
import moves  # type: ignore
import skilltree  # type: ignore
from combatant import Combatant

from ._leveling import PlayerLevelingMixin
from ._combat import PlayerCombatMixin
from ._inventory import PlayerInventoryMixin
from ._movement import PlayerMovementMixin
from ._exploration import PlayerExplorationMixin
from ._ui import PlayerUIMixin, generate_output_grid
from ._world import PlayerWorldMixin
from ._debug import PlayerDebugMixin

__all__ = ["Player", "generate_output_grid"]


class Player(
    PlayerDebugMixin,
    PlayerWorldMixin,
    PlayerUIMixin,
    PlayerExplorationMixin,
    PlayerMovementMixin,
    PlayerInventoryMixin,
    PlayerCombatMixin,
    PlayerLevelingMixin,
    Combatant,
):
    """Player character Jean Claire. Composed from focused mixin modules.

    All game state is initialised in ``__init__``. Behavioural methods live in
    the mixin files listed in the package docstring above.
    """

    def __init__(self):
        self.inventory = [
            items.Gold(15),
            items.TatteredCloth(),
            items.ClothHood(),
            items.JeanWeddingBand(),
        ]
        # Equip starting gear
        for item in self.inventory:
            if item.name in ["Tattered Cloth", "Cloth Hood"]:
                item.isequipped = True
                if "equip" in item.interactions:
                    item.interactions.remove("equip")
                if "unequip" not in item.interactions:
                    item.interactions.append("unequip")

        # Note: refresh_stat_bonuses is called at the end of __init__ after all base stats are defined
        self.username = None
        self.name = "Jean"
        self.name_long = "Jean Claire"
        self.pronouns = {
            "personal": "he",
            "possessive": "his",
            "reflexive": "himself",
            "intensive": "himself",
        }
        self.hp = 100
        self.maxhp = 100
        self.maxhp_base = 100
        self.base_suggested_move_count = 1
        self.last_move_data = (
            {}
        )  # Stores { "name": ..., "target_id": ..., "params": ... }
        self.last_move_summary = ""  # Text summary of the last move outcome
        self.fatigue = 150  # cannot perform moves without enough of this stuff
        self.maxfatigue = 150
        self.maxfatigue_base = 150
        self.strength = 10  # attack damage with strength-based weapons, parry rating, armor efficacy, influence ability
        self.strength_base = 10
        self.finesse = (
            10  # attack damage with finesse-based weapons, parry and dodge rating
        )
        self.finesse_base = 10
        self.speed = 10  # dodge rating, combat action frequency, combat cooldown
        self.speed_base = 10
        self.endurance = 10  # combat cooldown, fatigue rate
        self.endurance_base = 10
        self.charisma = 10  # influence ability, yielding in combat
        self.charisma_base = 10
        self.intelligence = 10  # sacred arts, influence ability, parry and dodge rating
        self.intelligence_base = 10
        self.faith = 10  # sacred arts, influence ability, dodge rate
        self.faith_base = 10
        # Resistance dicts are defined canonically in Combatant (combatant.py).
        # This also fixes the "inflamed" → "enflamed" key to match State.statustype.
        self._init_resistances()
        self.weight_tolerance = 20.00
        self.weight_tolerance_base = 20.00
        self.weight_current = 0.00
        self.fists = items.Fists()
        self.eq_weapon = self.fists
        self.combat_exp = {
            "Basic": 0,
            "Unarmed": 0,
        }  # place to pool all exp gained from a
        # single combat before distribution
        self.exp = 0  # exp to be gained from doing stuff rather than killing things
        self.skill_exp = {
            "Basic": 0,
            "Unarmed": 0,
        }  # pools exp gained in combat or otherwise to be
        # spent on learning skills
        self.skilltree = skilltree.Skilltree(self)
        for (
            subtype
        ) in (
            self.skilltree.subtypes.keys()
        ):  # initialize an exp pool for each skill subtype
            self.skill_exp[subtype] = 0
        self.level = 1
        self.exp_to_level = 100
        self.location_x, self.location_y = (0, 0)
        self.prev_location_x, self.prev_location_y = (
            0,
            0,
        )  # Track previous position for map display
        self.current_room = None
        self.victory = False
        # API-safe leveling/attribute spending
        self.pending_attribute_points = 0
        self.known_moves = [  # this should contain ALL known moves, regardless of whether they are
            # viable (moves will check their own conditions)
            moves.Check(self),
            moves.Wait(self),
            moves.Rest(self),
            moves.Turn(self),
            moves.UseItem(self),
            moves.Advance(self),
            moves.Withdraw(self),
            moves.Attack(self),
            moves.Dodge(self),
            moves.Parry(self),
            moves.Jab(self),
        ]
        self.current_move = None
        self.heat = 1.0
        self.protection = 0
        self.states = []
        self.in_combat = False
        self.combat_events = (
            []
        )  # list of pending events in combat. If non-empty, combat will be paused
        # while an event happens
        self.combat_log = []  # List of combat messages
        self.combat_list = (
            []
        )  # populated by enemies currently being encountered. Should be empty outside of combat
        self.combat_list_allies = [
            self
        ]  # friendly NPCs in combat that either help the player or just stand
        # there looking pretty
        self.combat_proximity = (
            {}
        )  # dict for unit proximity: {unit: distance}; Range for most melee weapons is 5,
        # ranged is 20. Distance is in feet (for reference)
        self.combat_position = None  # CombatPosition object; None outside combat. Source of truth for positioning
        self.default_proximity = 50
        self.savestat = None
        self.saveuniv = None
        self.universe = None
        self.map = None
        self.main_menu = False  # escape switch to get to the main menu; setting to True jumps out of the play loop
        self.time_elapsed = 0  # total seconds of gameplay
        self.skip_dialog = False  # if True, skips sequence dialogue and prints (typically handled in ini file)
        self.testing_mode = False  # test mode flag from config
        self.use_colour = True  # whether to use colored terminal output
        self.enable_animations = True  # whether to enable visual animations
        self.animation_speed = 1.0  # animation speed multiplier
        self.game_config = None  # full GameConfig object for access to all settings
        self.preferences = {
            "arrow": "Wooden Arrow"
        }  # player defined preferences will live here; for example, "arrow" = "Wooden Arrow"
        self.explored_tiles = {}  # key: "x,y", value: {items, npcs, objects, exits}
        self.combat_idle_msg = [
            "Jean breathes heavily. ",
            "Jean swallows forcefully. ",
            "Jean sniffs.",
            "Jean licks his lips in anticipation. ",
            "Jean grimaces for a moment.",
            "Jean anxiously shifts his weight back and forth. ",
            "Jean stomps his foot impatiently. ",
            "Jean carefully considers his enemy. ",
            "Jean spits on the ground. ",
            "A bead of sweat runs down Jean's brow. ",
            "Jean becomes conscious of his own heart beating loudly. ",
            "In a flash, Jean remembers the face of his dear, sweet Amelia smiling at him. ",
            "With a smug grin, Jean wonders how he got himself into this mess. ",
            "Sweat drips into Jean's eye, causing him to blink rapidly. ",
            "Jean misses the sound of his daughter laughing happily. ",
            "Jean recalls the sensation of consuming the Eucharist and wonders when - if - that might happen again. ",
            "Jean mutters a quick prayer under his breath. ",
            "Jean briefly recalls his mother folding laundry and humming softly to herself. ",
        ]

        self.combat_hurt_msg = [
            "Jean tastes blood in his mouth and spits it out. ",
            "Jean winces in pain. ",
            "Jean grimaces. ",
            "There's a loud ringing in Jean's ears. ",
            "Jean staggers for a moment. ",
            "Jean's body shudders from the abuse it's received. ",
            "Jean coughs spasmodically. ",
            "Jean falls painfully to one knee, then quickly regains his footing. ",
            "Jean fumbles a bit before planting his feet. ",
            "Jean suddenly becomes aware that he is losing a lot of blood. ",
            """Jean's face suddenly becomes pale as he realizes this could be his last battle. """,
            "A throbbing headache sears into Jean's consciousness. ",
            "Jean's vision becomes cloudy and unfocused for a moment. ",
            "Jean vomits blood and bile onto the ground. ",
            """Jean whispers quietly, "Amelia... Regina..." """,
            '''Jean shouts loudly, "No, not here! I have to find them!"''',
            """A ragged wheezing escapes Jean's throat. """,
            """A searing pain lances Jean's side. """,
            """A sense of panic wells up inside of Jean. """,
            """For a brief moment, a wave of fear washes over Jean. """,
        ]

        self.prayer_msg = [
            "A warm sense of peace fills Jean's heart.",
            "Jean frowns impatiently.",
            "Jean shudders slightly.",
            "Jean sees his wife's face for a brief moment and lets out a barely audible sigh. \n"
            + "The memory of her auburn braids swinging as she walked remains like a retinal burn. \n"
            + "Her other features are painfully mercurial and induce a burning sense of guilt.",
            "Jean grits his teeth and focuses hard on praying for his wife and daughter.",
            "Jean anxiously shifts his weight back and forth.",
            "Jean can still remember the look on the courier's face on that fateful day. "
            "He can still see the clothes he was wearing. \n"
            + "He can still smell the warm spring air. \nHe will never forget that day or the pain and anger "
            "that came with it.",
            "In spite of himself, Jean wonders just what, exactly, this is supposed to accomplish.",
            "Jean makes the sign of the cross.",
            """Jean prays quietly,

Je vous salue, Marie, pleine de grâce, Le Seigneur est avec vous.
Vous êtes bénie entre toutes les femmes, et Jésus, le fruit de vos entrailles, est béni.
Sainte Marie, Mère de Dieu, priez pour nous, pauvres pécheurs,
maintenant et à l'heure de notre mort. Amen.""",
            "Jean becomes conscious of his own heart beating loudly.",
            "His little girl is laughing and running through a field of grass. "
            "Jean remembers how they would play together. \n"
            'She would tease him, calling him "Gros Glouton." He would call her "Paresseux Passereau."',
            "Jean feels the silence around him to be very heavy.",
            "An intense groaning makes its way through Jean's stomache.",
            "The smell of fresh, sweet lillies dances in Jean's memory. \nThey were Regina's favorite.",
        ]

        # Apply stat bonuses from equipped items now that all base stats are initialized
        functions.refresh_stat_bonuses(self)

        # Ensure player starts at full health and fatigue
        self.hp = self.maxhp
        self.fatigue = self.maxfatigue

    def apply_starting_experience(self, exp_value: int):
        """Apply starting experience to all skill categories if exp_value > 0.

        Args:
            exp_value: The experience value to set for each skill category
        """
        if exp_value > 0 and hasattr(self, "skilltree") and hasattr(self, "skill_exp"):
            for category in self.skilltree.subtypes.keys():
                self.skill_exp[category] = exp_value

    def apply_state(self, state):
        """Apply a status effect, compounding or refreshing an existing one if present."""
        player_has_state = False
        if hasattr(state, "target"):
            state.target = self
        for player_state in self.states:
            if player_state.name == state.name:
                player_has_state = True
                if player_state.compounding:
                    player_state.compound(self)
                else:
                    self.states.remove(
                        player_state
                    )  # state is non-compounding; remove the existing state and
                    # replace with the new one (refreshes the state)
                    self.states.append(state)
                break
        if not player_has_state:
            self.states.append(state)

    def __getstate__(self):
        """Return picklable state, stripping API-layer attributes that are not serializable.

        Known non-picklable attributes attached by the web layer:
          _combat_adapter — holds a threading.Lock and a closure; removed before
                            pickle.dumps in game_service.save_game as a belt-and-suspenders
                            measure, but also excluded here so the Player class is
                            self-documenting about its pickle contract.

        If you attach a new non-picklable attribute to Player from the API layer,
        add it to the exclusion list below rather than only patching the save path.
        """
        state = self.__dict__.copy()
        state.pop("_combat_adapter", None)
        return state

    def get_hp_pcnt(self):
        """Return the player's remaining HP as a decimal fraction."""
        curr = float(self.hp)
        maxhp = float(self.maxhp)
        return curr / maxhp
