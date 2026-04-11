"""
Friendly NPC classes — allies, companions, and Grondite citizens.

All classes inherit from Friend (or NPC via Friend).  Mynx additionally
inherits MynxLLMMixin for LLM-driven ambient behaviour.  The Grondite
citizen classes communicate only through gesture and sound (no human speech).
"""

import random

import functions  # type: ignore
import genericng  # type: ignore
import moves  # type: ignore
from neotermcolor import colored  # type: ignore

from ._base import Friend
from ._llm import MynxLLMMixin


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

    def before_death(self):
        print(
            colored(self.name, "yellow", attrs=["bold"]) + " quaffs one of his potions!"
        )
        self.fatigue /= 2
        self.hp = self.maxhp
        return False

    def talk(self, player):
        if self.current_room.universe.story["gorran_first"] == "0":
            self.current_room.events_here.append(
                functions.seek_class("AfterGorranIntro", "story")(
                    player, self.current_room, None, False
                )
            )
            self.current_room.universe.story["gorran_first"] = "1"
            return

        stage = int(
            self.current_room.universe.story.get("gorran_language_stage", "0")
        )

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
                colored('"Still here,"', "green") + " he says. He settles his weight and waits.",
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
