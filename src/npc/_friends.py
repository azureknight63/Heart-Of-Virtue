"""
Friendly NPC classes — allies, companions, and Grondite citizens.

All classes inherit from Friend (or NPC via Friend).  Mynx additionally
inherits MynxLLMMixin for LLM-driven ambient behaviour.  The Grondite
citizen classes communicate only through gesture and sound (no human speech).
"""

import random
from pathlib import Path

import functions  # type: ignore
import genericng  # type: ignore
import moves  # type: ignore
from neotermcolor import colored  # type: ignore

from ._base import Friend
from ._chat_llm import HumanNPCLLMMixin
from ._llm import MynxLLMMixin

_HUMAN_NPC_DIR = Path(__file__).resolve().parent.parent.parent / "ai" / "npc" / "human"


# Mynx: a friendly, non-combatant monkey-cat hybrid NPC with LLM-driven interaction hooks.
class Mynx(MynxLLMMixin, Friend):
    """A small, nimble forest creature (mynx) that is friendly to the player and cannot fight.

    Behavior and interaction methods are provided as stubs so an LLM can be integrated later.
    """

    def __init__(self, name: str = None, description: str | None = None):
        if name is None:
            name = "Mynx " + genericng.generate(1, 3)
        if description is None:
            description = (
                "A small, nimble creature with spotted fur, a prehensile tufted tail, and bright curious eyes. "
                "It chirrs and chatters but cannot speak human words."
            )
        # Damage is zero and aggro False; exp_award 0 since it's non-combatant
        super().__init__(
            name=name,
            description=description,
            damage=0,
            aggro=False,
            exp_award=0,
            inventory=None,
            maxhp=30,
            protection=1,
            speed=18,
            finesse=16,
            awareness=20,
            maxfatigue=50,
            endurance=8,
            strength=4,
            charisma=14,
            intelligence=12,
            faith=6,
            hidden=False,
            hide_factor=0,
            combat_range=(0, 0),
            idle_message=" flicks its tail.",
            alert_message="startles and chatters!",
            discovery_message="a curious mynx.",
        )

        # Mynx-specific traits
        self.pronouns = {
            "personal": "it",
            "possessive": "its",
            "reflexive": "itself",
            "intensive": "itself",
        }
        self.keywords = ["talk", "pet", "play"]

        # Ensure the mynx never enters combat
        self.in_combat = False
        self._combat_disabled = True

        # Minimal move set (no attacks)
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []

        # Basic state useful for LLM-driven behavior
        self._llm_last_response = None
        # Lazy-initialized LLM adapter
        self._llm_adapter = None
        # Cached player (Jean) advisor data
        self._jean_advisor = None
        # Short LLM interaction history: list of {'prompt': str, 'response': str}, most recent last
        self._llm_history: list[dict] = []

    def combat_engage(self, player):
        """Override to prevent the mynx from entering combat.
        This intentionally does nothing; mynx can never be attacked or enter combat by design.
        """
        # Keep flags consistent but do not add to player's combat lists
        self.in_combat = False
        return

    def can_enter_combat(self) -> bool:
        return False

    # Override talk to use the interaction framework
    def talk(self, player, prompt: str | None = None, structured: bool = False):
        try:
            return self.interact_with_player(
                player, prompt=prompt, structured=structured
            )
        except Exception:
            print(f"{self.name} tilts its head and makes a confused chitter.")
            return None

    def pet(self, player=None, structured: bool = False):
        return self.interact_with_player(player, prompt="pet", structured=structured)

    def play(self, player=None, item=None, structured: bool = False):
        prompt = "play"
        if item:
            prompt = f"play with {str(item)}"
        return self.interact_with_player(player, prompt=prompt, structured=structured)


class Gorran(Friend):  # The "rock-man" that helps Jean at the beginning of the game.
    def __init__(self):
        description = """
A massive creature that somewhat resembles a man,
except he is covered head-to-toe in rock-like armor. He seems a bit clumsy and his
speech is painfully slow and deep. He seems to prefer gestures over actual speech,
though this makes his intent a bit difficult to interpret. At any rate, he seems
friendly enough to Jean.
"""
        super().__init__(
            name="Rock-Man",
            description=description,
            maxhp=200,
            damage=55,
            awareness=20,
            speed=5,
            aggro=True,
            exp_award=0,
            combat_range=(0, 7),
            idle_message=" is bumbling about.",
            alert_message=" lets out a deep and angry rumble!",
        )
        self.add_move(moves.NpcAttack(self), 4)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.GorranClub(self), 3)
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Parry(self), 2)
        self.keywords = ["talk"]
        self.battle_symbol = "G"  # distinguish from Rock Rumblers (R)
        self.pronouns = {
            "personal": "he",
            "possessive": "his",
            "reflexive": "himself",
            "intensive": "himself",
        }

    @property
    def name(self):
        story = None
        if hasattr(self, "current_room") and self.current_room is not None:
            if hasattr(self.current_room, "universe"):
                story = self.current_room.universe.story
        elif hasattr(self, "player_ref") and self.player_ref is not None:
            if hasattr(self.player_ref, "universe"):
                story = self.player_ref.universe.story

        if story and (
            story.get("gorran_first", "0") == "1"
            or story.get("gorran_language_stage", "0") != "0"
        ):
            return "Gorran"

        return getattr(self, "_name", "Rock-Man")

    @name.setter
    def name(self, value):
        self._name = value

    def wounded_flavor(self):
        msgs = [
            self.name + " moves with an uneven gait, stone scraping faintly.",
            "A low subsonic pressure radiates from "
            + self.name
            + ". He pushes forward without comment.",
            self.name + " pauses for a moment. His jaw shifts. He continues.",
            "The cracks along "
            + self.name
            + "'s shoulder have widened. He gives no sign of noticing.",
            self.name
            + " produces a small stone chip from somewhere and rolls it in his palm. Keeps moving.",
        ]
        return random.choice(msgs)

    def talk(self, player):
        if self.current_room.universe.story["gorran_first"] == "0":
            print(
                colored(
                    "The Rock-Man turns toward you slowly. His massive form shifts, and he "
                    "raises one broad hand — not a greeting, but a direction. He begins to move.",
                    "yellow",
                )
            )
            self.current_room.events_here.append(
                functions.seek_class("AfterGorranIntro", "story")(
                    player, self.current_room, None, False
                )
            )
            self.current_room.universe.story["gorran_first"] = "1"
            return

        stage = int(self.current_room.universe.story.get("gorran_language_stage", "0"))

        if stage == 0:
            # Stage 0: gesture and sound only — no words
            responses = [
                "Gorran turns toward you. A long, low vibration moves through the stone floor. "
                "He holds your gaze for a moment, then looks ahead.",
                "Gorran raises one hand — not a wave, not a greeting. A brief, deliberate "
                "acknowledgment. He faces forward again.",
                "Gorran makes a sound — low, even, the kind that doesn't require translation. "
                "He doesn't add to it.",
                "Gorran looks at you. His jaw shifts. Whatever he was considering, he keeps it.",
                "A subsonic pressure moves through the stone at your feet. Gorran does not turn. "
                "He is still here. That is the message.",
            ]
            print(colored(random.choice(responses), "yellow"))

        elif stage == 1:
            # Stage 1: gesture and sound only — same as Stage 0, but the silence
            # now has a different texture. He has spoken once. He knows he can.
            # He is choosing not to.
            responses = [
                "Gorran meets your gaze. His jaw shifts — something almost happens. "
                "Then he looks away. The stone is quiet.",
                "Gorran turns toward you slowly. A long pause. He doesn't fill it. "
                "He faces forward again.",
                "A low sound from Gorran — steady, not urgent. He holds your gaze "
                "for a moment, then lets it go.",
                "Gorran looks at you the way stone looks at water. Patient. Present. "
                "Whatever he considered, he keeps it.",
                "Gorran doesn't speak. But the silence feels different than it did before — "
                "deliberate, not empty.",
            ]
            print(colored(random.choice(responses), "yellow"))

        elif stage == 2:
            # Stage 2: single words, said simply and without elaboration
            responses = [
                colored('"Good."', "green") + " He says it once and doesn't repeat it.",
                (
                    "Gorran turns. He looks at you — really looks — and says your name: "
                    + colored('"Jean."', "green")
                    + "\n\nThen he faces forward. That was the whole of it."
                ),
                (
                    "A pause. "
                    + colored('"No."', "green")
                    + " Clear and final. He's already past whatever he refused."
                ),
            ]
            print(random.choice(responses))

        else:
            # Stage 3 and 4: short phrases, said with effort
            responses = [
                (
                    "Gorran studies the way ahead. After a moment: "
                    + colored('"Passage. Safe."', "green")
                    + "\n\nHe's checked."
                ),
                colored('"Still here,"', "green")
                + " he says. He settles his weight and waits.",
                (
                    "He tilts his head. "
                    + colored('"Heavy."', "green")
                    + " He doesn't look at you when he says it."
                ),
            ]
            print(random.choice(responses))


# ─────────────────────────────────────────────────────────────────────────────
# Grondite citizens — Grondia city map population
# Regular Grondite folk do not speak human language.
# All talk() implementations narrate gesture and sound only.
# ─────────────────────────────────────────────────────────────────────────────


class GronditePasserby(Friend):
    """A generic Grondite citizen moving through the city.

    Non-hostile, non-speaking. Used in arcology concourses, market, and
    residential lanes. TALK produces narrated gesture/sound — never words.
    """

    _TALK_LINES = [
        "The Grondite meets your gaze. A low subsonic vibration moves through the floor "
        "beneath your feet. He turns away and continues.",
        "The Grondite stops and looks at you — really looks, tilting his head slowly. "
        "Then he makes a sound like two stones sliding together and moves on.",
        "The Grondite produces three short, percussive sounds from somewhere in his chest. "
        "He does not wait for a response.",
        "The Grondite gestures — a single, deliberate downward press of one hand. "
        "Jean isn't sure what it means. The Grondite continues walking.",
        "The Grondite makes no sound. He places a fist briefly against his own sternum, "
        "then turns away.",
        "A low grinding tone rises from the Grondite's chest — short, even, and then "
        "gone. He does not slow his pace.",
        "The Grondite regards Jean with an unhurried stillness, then tilts his head toward "
        "the path ahead and moves on.",
    ]

    def __init__(self):
        super().__init__(
            name="Grondite",
            description=(
                "A broad, heavily-built figure of living stone, unhurried and deliberate. "
                "His surface is a mosaic of grey and ochre rock, worn smooth at the joints "
                "from centuries of movement. He acknowledges Jean with a slow lateral turn "
                "of his head — enough to register, not enough to invite."
            ),
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=80,
            protection=10,
            speed=4,
            finesse=8,
            awareness=14,
            idle_message=" moves past with measured, heavy steps.",
            alert_message=" shifts his weight and watches.",
            discovery_message="a broad, stone-skinned Grondite.",
        )
        self.keywords = ["talk"]
        self.pronouns = {
            "personal": "he",
            "possessive": "his",
            "reflexive": "himself",
            "intensive": "himself",
        }
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []

    def talk(self, player):
        print(random.choice(self._TALK_LINES))


class GronditeWorker(Friend):
    """A Grondite artisan, found near the Fabricarium and workshop areas.

    Non-hostile, non-speaking. TALK produces narrated gesture/sound only.
    """

    _TALK_LINES = [
        "The worker pauses his task and straightens. He makes a low, measured sound — "
        "not unfriendly — and returns to what he was doing.",
        "The Grondite does not look up but raises one finger briefly, as if asking Jean "
        "to wait. Then the sound he's working out of the rock fills the silence again.",
        "He looks at Jean with an expression that is — possibly — patience. He holds up "
        "whatever he is working on. Jean doesn't know what he is supposed to understand from this.",
        "The worker turns his head toward Jean without stopping his motion. A low percussive "
        "sound. Then he looks back at the work.",
        "The Grondite sets his tool down deliberately, regards Jean for a moment, makes a "
        "single short vowel sound, and picks the tool back up.",
    ]

    def __init__(self):
        super().__init__(
            name="Grondite Worker",
            description=(
                "A Grondite whose stone-skin is darkened at the hands and forearms — "
                "mineral dust worked into the grain over long practice. "
                "He moves with the focused economy of someone partway through a task."
            ),
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=80,
            protection=8,
            speed=4,
            finesse=10,
            awareness=12,
            idle_message=" is occupied with something near the floor.",
            alert_message=" pauses his work and watches.",
            discovery_message="a Grondite working at something.",
        )
        self.keywords = ["talk"]
        self.pronouns = {
            "personal": "he",
            "possessive": "his",
            "reflexive": "himself",
            "intensive": "himself",
        }
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []

    def talk(self, player):
        print(random.choice(self._TALK_LINES))


class GronditeElder(Friend):
    """An older, senior Grondite. Found in or near the Conclave and Citadel.

    Notably still; inspects Jean with deliberate attention.
    Non-hostile, non-speaking. TALK produces narrated gesture/sound only.
    """

    _TALK_LINES = [
        "The Elder turns. He looks at Jean the way a geologist looks at a particular "
        "stratum — with genuine, slow interest. Then he makes a single sound, deep and "
        "resonant, and returns his gaze to the middle distance.",
        "The Elder does not speak. He places a hand on Jean's shoulder — briefly, a weight, "
        "an anchor — and removes it. Then he is still again.",
        "The Elder considers Jean for a long moment. He produces a subsonic resonance Jean "
        "feels in his sternum before he hears it. Then he gestures toward the Conclave and "
        "turns away.",
        "Two sounds: one short, one long, with a pause between them. The Elder makes them "
        "without looking at Jean, then waits — as if for a response Jean doesn't know how "
        "to give.",
        "The Elder's attention is unhurried and complete. He takes Jean in from boots to "
        "face, then makes a low grinding sound that rises and resolves. Then he is still.",
    ]

    def __init__(self):
        super().__init__(
            name="Grondite Elder",
            description=(
                "This Grondite is older — his stone-skin more cracked and mineral-threaded, "
                "grey and iron-veined. He moves slowly, not from frailty, but from the "
                "unhurried certainty of one who has been exactly where he is "
                "for a very long time."
            ),
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=120,
            protection=15,
            speed=2,
            finesse=6,
            awareness=20,
            idle_message=" stands in quiet contemplation.",
            alert_message=" turns slowly to watch.",
            discovery_message="a weathered, ancient-looking Grondite.",
        )
        self.keywords = ["talk"]
        self.pronouns = {
            "personal": "he",
            "possessive": "his",
            "reflexive": "himself",
            "intensive": "himself",
        }
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []

    def talk(self, player):
        print(random.choice(self._TALK_LINES))


class GronditeConclaveElder(Friend):
    """The Elder in the Conclave side chamber at (9,3). A stubbed side-quest giver.

    In the future, this NPC will initiate a formal side quest retrieving a
    lost clan token. For now, talk() presents the opening stub interaction and
    a placeholder acknowledgment that the quest is not yet available.
    """

    _INTRO_RUN_KEY = "conclave_elder_intro"

    def __init__(self):
        super().__init__(
            name="Conclave Elder",
            description=(
                "An Elder Grondite who stands each day at the center of this chamber, "
                "facing the plinth. His stone-skin has the deep cracking and vivid mineral "
                "banding of great age. Unlike the other Elders you have seen, he does not "
                "merely tolerate your presence — he seems to have been expecting someone."
            ),
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=150,
            protection=20,
            speed=2,
            finesse=6,
            awareness=25,
            idle_message=" stands before the plinth, still as carved stone.",
            alert_message=" slowly turns his gaze toward you.",
            discovery_message="a Grondite Elder standing before the plinth.",
        )
        self.keywords = ["talk"]
        self.pronouns = {
            "personal": "he",
            "possessive": "his",
            "reflexive": "himself",
            "intensive": "himself",
        }
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []

    def talk(self, player):
        import time

        # Check if intro has already fired this session
        story = getattr(getattr(player, "universe", None), "story", {})
        first_time = story.get(self._INTRO_RUN_KEY, "0") == "0"

        if first_time:
            print(
                "\nThe Elder turns before Jean says anything. He had already turned — "
                "waiting — before he reached the plinth."
            )
            time.sleep(1.5)
            print(
                "He studies him. Then he reaches into the folds of his stone-mantle and "
                "produces something: a small disc, cracked cleanly in half, one piece "
                "missing. He holds it out toward Jean."
            )
            time.sleep(1.5)
            print(
                "He makes a sound: low, deliberate, with a rising inflection at the end. "
                "The sound of a question."
            )
            time.sleep(1)
            print(
                "Jean doesn't know what he is asking. But the broken disc is clearly "
                "meant to show him."
            )
            time.sleep(1)
            print(
                "\n[A side quest would begin here — the Elder is looking for a missing "
                "clan token. This quest is not yet available.]"
            )
            time.sleep(0.5)
            print(
                "\nThe Elder lowers the broken disc. He makes one short sound — patient, "
                "not disappointed — and turns back to the plinth."
            )
            universe_story = getattr(getattr(player, "universe", None), "story", None)
            if universe_story is not None:
                universe_story[self._INTRO_RUN_KEY] = "1"
        else:
            lines = [
                "The Elder turns and regards Jean for a moment. Then he produces the broken "
                "disc again and holds it in the space between them.",
                "The Elder makes the same rising sound as before. The question hasn't changed.",
                "The Elder looks at Jean. Looks at the plinth. Looks at Jean again.",
            ]
            print(random.choice(lines))


class Mara(HumanNPCLLMMixin, Friend):
    """Scavenger, ferry operator, and guide. First human Jean encounters outside any
    institutional context. Sardonic, watchful, practical. Skilled in precision combat,
    positioning, and tactical awareness. Fights with the same observant efficiency as
    she moves through the world.
    """

    def __init__(self):
        description = (
            "A woman in her late twenties, lean and self-contained. She stands with "
            "the efficiency of someone who wastes no motion. Dark auburn hair, cut to "
            "the shoulder and tied back. Her eyes are sharp and green — the first thing "
            "you notice is that she's already noticed you. She wears layered travel gear, "
            "well-maintained. Around her neck, on a knotted cord, hangs a worn crucifix."
        )
        super().__init__(
            name="Mara",
            description=description,
            maxhp=95,
            damage=38,
            protection=12,
            speed=8,
            finesse=8,
            awareness=35,
            aggro=False,
            exp_award=0,
            combat_range=(0, 5),
            idle_message=" stands off to the side, sorting through her samples.",
            alert_message=" straightens, hand moving to her weapon.",
            discovery_message="a scavenger woman by the campfire.",
        )
        self.keywords = ["talk", "trade"]
        self.pronouns = {
            "personal": "she",
            "possessive": "her",
            "reflexive": "herself",
            "intensive": "herself",
        }
        # Mara's combat style: precision, positioning, and tactical awareness
        # She switches between bow (medium/long range) and dagger (close range)
        self.add_move(moves.NpcAttack(self), 5)  # Dagger attacks at close range
        self.add_move(moves.Advance(self), 3)
        self.add_move(moves.Withdraw(self), 3)  # Tactical retreat to reset
        self.add_move(moves.FlankingManeuver(self), 2)  # Positioning for better angles
        self.add_move(moves.Dodge(self), 3)  # High finesse means good evasion
        self.add_move(moves.Parry(self), 2)  # Defensive positioning
        self.add_move(moves.NpcIdle(self), 1)

        self.battle_symbol = "M"

        # Equipment state tracking for weapon switching
        self.preferred_range = None  # Will be set dynamically based on combat distance
        self.bow_range = (8, 25)  # Bow effective range
        self.dagger_range = (0, 3)  # Dagger effective range
        self._chat_config_path = str(_HUMAN_NPC_DIR / "mara.json")
        self._init_chat_attrs()

    def wounded_flavor(self):
        msgs = [
            "Mara moves with precision, though she favors her right side.",
            "Mara tears a strip from her pack cloth and binds something beneath her sleeve."
            " She says nothing.",
            "Mara exhales slowly. Her pace doesn't change.",
            "Mara's eyes move to Jean once, assess, and return forward. She doesn't comment.",
            "Mara adjusts her grip on her bag — a small, deliberate motion. She keeps moving.",
        ]
        return random.choice(msgs)

    def talk(self, player):
        """Mara's dialogue is sparse, practical, observant."""
        lines = [
            "Mara glances up from what she's doing. Her gaze finds Jean briefly, takes in what "
            "it needs to, and returns to her work.",
            "Mara nods once. She doesn't elaborate.",
            "Mara says, 'The river's crossable this time of year. Careful of the current at "
            "the bend.'",
            "Mara's eyes narrow slightly as she studies Jean. Then she returns to her sorting.",
        ]
        print(random.choice(lines))

    def _get_optimal_range_to_target(self):
        """Determine what range Mara should maintain based on nearest enemy (not allies)."""
        if not hasattr(self, "combat_proximity") or not self.combat_proximity:
            return None

        # Filter proximity dict to only include enemies, not allies
        enemy_distances = {}
        if hasattr(self, "player_ref") and self.player_ref:
            enemies = getattr(self.player_ref, "combat_list", [])
            for enemy in enemies:
                if enemy in self.combat_proximity:
                    enemy_distances[enemy] = self.combat_proximity[enemy]

        if not enemy_distances:
            return None

        nearest_distance = min(enemy_distances.values())

        # Bow range (8-25): stay at medium-long range for precision archery
        if nearest_distance >= self.bow_range[0]:
            return "bow"
        # Dagger range (0-3): close quarters with evasion and precision strikes
        elif nearest_distance <= self.dagger_range[1]:
            return "dagger"
        # Transition zone (4-7): decide based on fatigue and health
        else:
            # If hurt or fatigued, maintain bow range; otherwise close to dagger range
            health_percent = self.hp / self.maxhp
            fatigue_percent = self.fatigue / self.maxfatigue
            if health_percent < 0.6 or fatigue_percent < 0.4:
                return "bow"
            else:
                return "dagger"

    def select_move(self):
        """Mara's move selection reflects her nature: precise, observant, tactical.
        She switches between bow (medium/long range) and dagger (close range) based on
        combat distance, maintaining optimal positioning for her current weapon.
        """
        available_moves = self.refresh_moves()

        # Initialize AI config if we have a player reference (combat started)
        if (
            (not hasattr(self, "ai_config") or self.ai_config is None)
            and hasattr(self, "player_ref")
            and self.player_ref
        ):
            try:
                from npc_ai_config import NPCAIConfig

                self.ai_config = NPCAIConfig(self.player_ref)
            except ImportError:
                pass

        # Determine optimal weapon range based on current situation
        optimal_range = self._get_optimal_range_to_target()

        # Mara favors tactical positioning over raw aggression
        weighted_moves = []
        for move in available_moves:
            weight = move.weight

            # Core tactical moves that apply to both bow and dagger modes
            if move.name == "Dodge":
                weight += 3  # High finesse means constant opportunistic evasion
            elif move.name == "Flanking Maneuver":
                weight += 2  # Seeks advantageous angles

            # Weapon-specific positioning
            if optimal_range == "bow":
                # Bow mode: maintain distance, retreat if enemies close in
                if move.name == "Withdraw":
                    weight += 4  # Actively maintain bow range
                elif move.name == "Advance":
                    weight -= 2  # Don't advance in bow mode unless necessary
                elif move.name == "NpcAttack":
                    weight += 1  # Bow strikes when at optimal range
                elif move.name == "Parry":
                    weight -= 1  # Less relevant when staying at range
            elif optimal_range == "dagger":
                # Dagger mode: close quarters, precision, evasion
                if move.name == "Advance":
                    weight += 3  # Close the distance for dagger work
                elif move.name == "Withdraw":
                    weight += 1  # Tactical retreat to dodge and reset
                elif move.name == "NpcAttack":
                    weight += 3  # Aggressive dagger strikes at close range
                elif move.name == "Parry":
                    weight += 2  # Parrying matters in close quarters

            # Apply AI config bonuses
            if hasattr(self, "ai_config") and self.ai_config:
                weight += self.ai_config.get_weighted_move_bonus(self, move.name)

            weight = max(1, weight)
            for _ in range(weight):
                weighted_moves.append(move)

        if not weighted_moves:
            return

        # Fatigue management
        can_attack = any(
            getattr(m, "category", "") == "Offensive"
            and m.fatigue_cost <= self.fatigue
            and m.viable()
            for m in available_moves
        )
        if not can_attack and self.fatigue < self.maxfatigue:
            can_advance = any(
                getattr(m, "name", "") == "Advance" for m in available_moves
            )
            if not can_advance:
                self.current_move = moves.NpcRest(self)
                return

        num_choices = len(weighted_moves) - 1
        max_attempts = 20
        attempts = 0
        choice = 0

        while self.current_move is None and attempts < max_attempts:
            attempts += 1
            choice = random.randint(0, num_choices)
            if (weighted_moves[choice].fatigue_cost <= self.fatigue) and weighted_moves[
                choice
            ].viable():
                self.current_move = weighted_moves[choice]

        # Hard fallback
        if self.current_move is None:
            self.current_move = moves.NpcRest(self)
            return


class Devet(HumanNPCLLMMixin, Friend):
    """Camp cook, older, unhurried. Quietly observant. Offers food and healing.
    Uncle or relation of Mara — exact nature left ambiguous.
    """

    def __init__(self):
        description = (
            "An older man, weathered by years on the road but settled into his own pace. "
            "He moves without urgency, each gesture economical. His hands are scarred and "
            "capable. He tends the fire with the attention of someone who has done this "
            "ten thousand times and expects to do it ten thousand more."
        )
        super().__init__(
            name="Devet",
            description=description,
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=100,
            protection=10,
            speed=4,
            finesse=5,
            awareness=30,
            idle_message=" tends the fire.",
            alert_message=" straightens from the fire.",
            discovery_message="an older man tending the campfire.",
        )
        self.keywords = ["talk"]
        self.pronouns = {
            "personal": "he",
            "possessive": "his",
            "reflexive": "himself",
            "intensive": "himself",
        }
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []
        self._chat_config_path = str(_HUMAN_NPC_DIR / "devet.json")
        self._init_chat_attrs()

    def talk(self, player):
        """Terminal fallback — static dialogue. Web uses chat_open/chat_respond via the API."""
        lines = [
            "Devet hands Jean a bowl of warm food without asking if he's hungry. It's clear "
            "this is not a question.",
            "Devet studies Jean for a long moment. Then he says, 'Jean's come from the city.' "
            "It's not a question.",
            "Devet says quietly, 'The west's not kind. But then, nowhere is, if a man's not ready "
            "for it.'",
            "Devet tends the fire. When he speaks, his voice is low. 'Jean will want to rest here. "
            "The crossing can wait until morning.'",
        ]
        print(random.choice(lines))


class Liss(HumanNPCLLMMixin, Friend):
    """Young, openly curious, observant. Part of Mara's nomad group. At the camp's edge,
    watching the river and the world beyond.
    """

    def __init__(self):
        description = (
            "A girl about nine years old, dark-haired and open-faced. She has the restless "
            "energy of someone who hasn't yet learned to hide what she's thinking. She "
            "watches everything — Jean's gear, his bearing, the way he moves. Her curiosity "
            "is unconcealed, almost tactile in its intensity."
        )
        super().__init__(
            name="Liss",
            description=description,
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=60,
            protection=5,
            speed=8,
            finesse=6,
            awareness=28,
            idle_message=" sits near the camp's edge, watching the river.",
            alert_message=" turns to look at Jean.",
            discovery_message="a young girl at the camp's edge.",
        )
        self.keywords = ["talk"]
        self.pronouns = {
            "personal": "she",
            "possessive": "her",
            "reflexive": "herself",
            "intensive": "herself",
        }
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []
        self._chat_config_path = str(_HUMAN_NPC_DIR / "liss.json")
        self._init_chat_attrs()

    def talk(self, player):
        """Terminal fallback — static dialogue. Web uses chat_open/chat_respond via the API."""
        lines = [
            "Liss says, 'Where's Jean headed?' She doesn't wait for an answer before asking "
            "another question. 'What's beyond the Badlands? Does anyone actually know?'",
            "Liss watches Jean with open curiosity. 'Mara said he was going west. Most people "
            "don't go west unless they have nowhere else to go.'",
            "Liss says, 'I've never seen a Golemite up close before. The one with Jean — he's "
            "different, isn't he?' She doesn't elaborate on what 'different' means.",
            "Liss looks at Jean directly. 'Jean looks like he's carrying something. Not in his "
            "pack. In his — ' She makes a vague gesture, 'everything, I guess.'",
        ]
        print(random.choice(lines))
