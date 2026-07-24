"""
Eastern Descent — Nomad Camp NPCs.

Generic background characters for the nomad camp on the river's east bank.
These are ambient presences — not story principals — and follow the same
narrated-exchange pattern as the Grondite citizen classes in _friends.py.

All three communicate in brief, practical terms. None overreach their tier.
"""

import random

import src.moves as moves  # type: ignore
from ._base import Friend
from ._chat_llm import ConversationalNPCMixin
from src.narration import narrate

# ─────────────────────────────────────────────────────────────────────────────
# Eastern Descent — Nomad Camp NPCs
# ─────────────────────────────────────────────────────────────────────────────


class NomadCamper(ConversationalNPCMixin, Friend):
    """A generic nomad resting at the east-bank camp between routes.

    Not a fighter, not a guide — someone between places, occupying the camp
    the way weather does: temporarily and without apology. Knows the river and
    the Badlands by reputation more than by experience. Non-hostile, non-speaking
    beyond brief observation. TALK produces narrated exchanges only.
    """

    _TALK_LINES = [
        "The camper is sitting near the fire, mending a strap. He doesn't look up. "
        "'Camp's good here for now. River's been steady.' A pause. 'Won't always be.'",
        "He glances at Jean from across the fire ring. 'Heading west?' He doesn't wait "
        "for an answer. 'Most people who stop here are.'",
        "He looks toward the far bank for a moment. 'Badlands are quieter than people "
        "expect.' He returns to his work. 'That's what comes back with the ones who "
        "don't go in.'",
        "The camper adjusts something on his pack without urgency. 'Came through from "
        "the eastern settlements. Three days, roughly. Nothing on that route worth "
        "the detail.'",
        "He glances at Jean once. 'River takes longer to cross than it looks. Current "
        "shifts.' He does not explain further. He seems to assume this is enough.",
        "He is watching the fire burn down. He glances at the far bank. 'Good camp.' "
        "A pause. 'Bad view.' He doesn't elaborate.",
        "'Feels like more people west-bound this year than last,' he says, folding "
        "something carefully. 'Could just be the season.' He seems prepared to leave "
        "it at that.",
        "The camper is quiet for a while. Then: 'You get used to the sound of the river. "
        "After a few nights you stop hearing it. Then when you leave, you notice it\'s gone.'",
        "He sets his pack upright and leans it against a stone with the care of someone "
        "who has done this in many different places. He doesn't explain why he\'s here or "
        "where he\'s headed. He doesn\'t seem to think it requires explanation.",
        "'Crossing\'s not bad this time of year,' he says, not looking up. 'Ask the "
        "woman by the water before you go. She knows the timing.'",
        "He feeds the fire a piece of wood without ceremony. 'You\'re not from the "
        "settlements.' Not an accusation. A quiet observation filed and set aside.",
        "The camper ties off a knot on his mending and bites the end. He studies the "
        "work briefly, then returns to his pack. He has nothing to add.",
    ]

    def __init__(self):
        super().__init__(
            name="Nomad",
            description=(
                "A weathered traveler resting at the fire ring, pack beside him in the "
                "particular way of someone who knows they'll be moving again soon. "
                "He takes Jean in briefly — not suspicion, just habit — and returns "
                "to what he was doing."
            ),
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=35,
            protection=2,
            speed=10,
            finesse=9,
            awareness=12,
            idle_message=" is resting near the fire, pack within arm's reach.",
            alert_message=" looks up and watches.",
            discovery_message="a nomad resting at the camp.",
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
        self._chat_config_path = None
        self._init_chat_attrs()

    def talk(self, player):
        """Terminal fallback — static dialogue. Web uses chat_open/chat_respond via the API."""
        narrate(random.choice(self._TALK_LINES))


class NomadScout(ConversationalNPCMixin, Friend):
    """A nomad who watches the eastern approaches and knows the terrain.

    Economical with words. Has practical knowledge of the paths between the
    foothills and the river. Reports information the way a traveler reports
    weather: useful, impersonal, without drama.
    """

    _TALK_LINES = [
        "The scout is watching the northern path. He registers Jean without turning "
        "fully. 'Quiet on the approach roads today. Foothills clear.'",
        "'Two parties came through yesterday heading east. Moving fast.' He's still "
        "watching the path. 'Didn't stop.'",
        "He looks at Jean's kit — inventory more than interest. 'Long journey.' "
        "Not a question.",
        "'River ford is passable at this hour. Current runs wider after midday.' "
        "He glances at Jean. 'Worth the early start.'",
        "'Eastern foothills are stable. There's old trouble on the northern approach "
        "but nothing recent.' He says this the way someone reports weather.",
        "'Stay on the marked line when crossing. Current tries to take the east "
        "edge.' He says this to everyone heading west.",
        "'Don't know what's past the Badlands.' He is watching the far bank. "
        "'Nobody does who's come back.' Not dramatic. Accurate.",
        "He shifts his weight slightly and rescans the approach road. 'Nothing out "
        "there right now. That can change.' He says this without alarm. It's a fact "
        "he tracks the way others track weather.",
        "'River's running a little high this week. Still crossable. Give it another "
        "day if you want an easier time of it.' He does not say whether he thinks "
        "Jean should wait.",
        "The scout doesn't speak when Jean approaches. He acknowledges Jean the way "
        "he acknowledges the wind — registers it, notes the direction, files it away.",
        "'Saw smoke to the east this morning. Probably a camp. Nothing hostile — "
        "wrong direction for that.' He returns his attention to the road.",
        "'People who come through heading west usually don't ask questions,' the "
        "scout says. 'The ones who do are either worried or prepared. Hard to tell "
        "which you are from here.'",
    ]

    def __init__(self):
        super().__init__(
            name="Nomad Scout",
            description=(
                "A lean figure at the edge of the camp, facing the approach roads. "
                "He notices Jean early and says nothing about it — just adds Jean "
                "to the list of things he is tracking."
            ),
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=40,
            protection=3,
            speed=13,
            finesse=13,
            awareness=17,
            idle_message=" is watching the approach roads.",
            alert_message=" turns and watches, hand steady.",
            discovery_message="a watchful figure at the camp's edge.",
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
        self._chat_config_path = None
        self._init_chat_attrs()

    def talk(self, player):
        """Terminal fallback — static dialogue. Web uses chat_open/chat_respond via the API."""
        narrate(random.choice(self._TALK_LINES))


class NomadTrader(ConversationalNPCMixin, Friend):
    """A nomad who barters goods picked up along the eastern routes.

    Not a full merchant — no shop, no stock list. Trades as part of nomadic
    life, opportunistically, between other work. Dry, pragmatic view of commerce
    and travel. Has an eye for the provenance of objects.
    """

    _TALK_LINES = [
        "The trader looks up from a bundle she's sorting. 'Looking for anything "
        "specific?' She doesn't gesture toward her pack. It's more general than that.",
        "'Came up from the river settlements.' She is going through a bundle of "
        "wrapped items methodically. 'Good route. Foothills are slow.'",
        "'Four trades this week already. River camps move more than people expect.' "
        "She doesn't say what she traded. She wraps something back up.",
        'She looks up briefly. "You\'re not from the settlements." Not a question. '
        "She returns to her bundle.",
        "'Not many travelers come through this far east,' she says, wrapping something. "
        "'The ones who do are usually going somewhere specific.'",
        "'Badlands have a reputation that keeps the routes clear.' A pause. "
        "'Good for travel. Bad for trade.'",
        "'If you need anything, best to ask before crossing.' She is speaking from "
        "experience. 'Supply's thin on the other side.'",
        "She holds up two items side by side, considers them, sets one down. The "
        "other gets wrapped and returned to the bundle. She does not explain what "
        "distinguished them.",
        "'Most of what I carry came through the eastern settlements. Some of it "
        "came further.' She ties off a bundle. 'Provenance matters to some people. "
        "Not most.'",
        "She glances at Jean's pack. Brief, professional. Then back to her work. "
        "She doesn't make an offer. She files the assessment somewhere.",
        "'Trade tends to move before trouble does,' she says. 'If the routes start "
        "going quiet, that's the sign. They're not quiet yet.'",
        "She sets her bundle down and straightens her back. Looks at Jean directly "
        "for a moment. 'You've got that look. Going west.' She picks the bundle "
        "back up. 'Good luck with it.'",
    ]

    def __init__(self):
        super().__init__(
            name="Nomad Trader",
            description=(
                "A compact woman surrounded by a small arrangement of wrapped bundles, "
                "each one tied differently — a cataloguing system entirely her own. "
                "She has the manner of someone who has assessed Jean's trade potential "
                "and filed the result without interrupting what she was doing."
            ),
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=30,
            protection=1,
            speed=10,
            finesse=11,
            awareness=14,
            charisma=13,
            idle_message=" is sorting through a bundle of wrapped goods.",
            alert_message=" looks up, watchful.",
            discovery_message="a woman with goods arranged around her.",
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
        self._chat_config_path = None
        self._init_chat_attrs()

    def talk(self, player):
        """Terminal fallback — static dialogue. Web uses chat_open/chat_respond via the API."""
        narrate(random.choice(self._TALK_LINES))
