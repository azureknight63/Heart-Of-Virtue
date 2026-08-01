"""
Eastern Descent — Nomad Camp NPCs.

Generic background characters for the nomad camp on the river's east bank,
plus Anvil, Kaelen & Vespera's named Scree Strider pack animal. These are
ambient presences — not story principals — and follow the same
narrated-exchange pattern as the Grondite citizen classes in _friends.py.

All communicate in brief, practical terms (Anvil communicates only through
gesture and sound — he's an animal, not a person). None overreach their tier.
"""

import random

from ._base import Friend, NonCombatantMixin
from ._chat_llm import ConversationalNPCMixin
from src.narration import narrate
import src.moves as moves

# ─────────────────────────────────────────────────────────────────────────────
# Eastern Descent — Nomad Camp NPCs
# ─────────────────────────────────────────────────────────────────────────────


class Anvil(NonCombatantMixin, Friend):
    """Kaelen & Vespera's Scree Strider — the pack bird that hauls Iron &
    Oath's anvil, weapon racks, armor stock, and canvas whenever the Nomad
    Camp relocates along the river route. See
    ``docs/lore/character-profiles/anvil.md`` and
    ``docs/lore/creatures/scree-strider.md`` for the full lore.

    Non-speaking, non-combatant — communicates through gesture and sound
    only, following the same narrated-exchange pattern as the Grondite
    citizen classes in this module. Cannot be drawn into combat (see
    ``NonCombatantMixin``), the same design used for Mynx.
    """

    _TALK_LINES = [
        "Anvil's head swings toward Jean, quill ridge lifting a fraction — "
        "not alarm, just assessment. He decides Jean isn't touching the "
        "harness and goes back to tearing at a patch of scrub.",
        "Vespera rests a hand against Anvil's neck without looking up from "
        "her ledger. He leans into it, eyes half-closed, radiating the "
        "specific contentment of an animal that trusts exactly one person "
        "completely.",
        "Kaelen pats Anvil's flank on his way past the stall. Anvil tolerates "
        "it with the flat, unimpressed patience of a very old grudge.",
        "A low, chest-deep boom rolls out of Anvil — the same subsonic call "
        "his wild cousins use to keep track of each other across broken "
        "ground. Here, it just means he's noticed something worth noticing.",
        "Anvil's splayed feet shift against the packed dirt, testing it the "
        "way he tests riverbed silt before committing weight. Habit, not "
        "necessity — the ground here isn't going anywhere.",
        "His quill ridge is lying flat. Whatever Jean is doing, Anvil has "
        "decided it isn't worth the effort of caring.",
        "Anvil watches Jean's hands more than his face — an old instinct, "
        "the kind that keeps a pack animal's cargo intact for years.",
        "Kaelen calls over, 'Careful — he's not fond of strangers near the "
        "crates.' Anvil, for his part, hasn't moved, but one eye has fixed "
        "on Jean with unmistakable attention.",
    ]

    _PET_LINES = [
        "Anvil allows it — a brief, tolerant stillness rather than any real "
        "warmth — then shifts his weight to signal he's done being touched.",
        "Anvil's quill ridge rises sharply and a low hiss builds in his "
        "throat. Vespera doesn't look up. 'He doesn't do that for anyone "
        "but me,' she says, not unkindly. Jean gets the message.",
        "He tolerates the contact for exactly as long as it takes him to "
        "decide it isn't food, then turns his attention back to the scrub "
        "at his feet.",
        "Anvil goes very still — the particular stillness of an animal "
        "deciding whether something is worth reacting to. He decides it isn't.",
    ]

    def __init__(self):
        description = (
            "A heavy-boned Scree Strider, dust-brown and ochre in his "
            "mottled plumage, standing taller than Kaelen at the shoulder "
            "when his neck is raised. A harness of oiled leather straps runs "
            "across his back and flanks, anchoring crated tools and folded "
            "canvas. His quill ridge lies flat while he's at ease, but it "
            "rises the instant someone gets careless near the straps."
        )
        super().__init__(
            name="Anvil",
            description=description,
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=150,
            protection=8,
            speed=6,
            finesse=6,
            awareness=15,
            maxfatigue=120,
            endurance=14,
            strength=18,
            charisma=6,
            combat_range=(0, 0),
            idle_message=" is tearing at a patch of scrub, harness creaking.",
            alert_message=" swings his head around, quill ridge lifting.",
            discovery_message="a heavy-set pack bird harnessed with crates and folded canvas.",
        )
        self.keywords = ["talk", "pet"]
        self.pronouns = {
            "personal": "he",
            "possessive": "his",
            "reflexive": "himself",
            "intensive": "himself",
        }
        self._init_idle_moves()
        # Cargo infrastructure, not a combatant — never enters combat, see NonCombatantMixin.
        self.in_combat = False

    def talk(self, player):
        narrate(random.choice(self._TALK_LINES))

    def pet(self, player=None):
        narrate(random.choice(self._PET_LINES))


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
        "After a few nights you stop hearing it. Then when you leave, you notice it\\'s gone.'",
        "He sets his pack upright and leans it against a stone with the care of someone "
        "who has done this in many different places. He doesn't explain why he\\'s here or "
        "where he\\'s headed. He doesn\\'t seem to think it requires explanation.",
        "'Crossing\\'s not bad this time of year,' he says, not looking up. 'Ask the "
        "woman by the water before you go. She knows the timing.'",
        "He feeds the fire a piece of wood without ceremony. 'You\\'re not from the "
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
        self._init_idle_moves()
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
        self._init_idle_moves()
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
        self._init_idle_moves()
        self._chat_config_path = None
        self._init_chat_attrs()

    def talk(self, player):
        """Terminal fallback — static dialogue. Web uses chat_open/chat_respond via the API."""
        narrate(random.choice(self._TALK_LINES))


# ═════════════════════════════════════════════════════════════════════════════
# Young nomad personality bank — shared by NomadBoy and NomadGirl
# ═════════════════════════════════════════════════════════════════════════════

_YOUNG_NOMAD_PERSONALITIES = [
    {
        "given_name": "Neri",
        "voice": "eager, talks quickly when excited, trails off when uncertain",
        "knowledge": ["camp stories", "what travelers carry", "river crossings by hearsay"],
        "attitude_to_strangers": "curious but shy",
        "speech_sample": "Are you going across? Everyone who comes here goes across. Except the ones who don't.",
        "loquacity_base": 35,
    },
    {
        "given_name": "Sila",
        "voice": "quiet, speaks only after a pause, each word considered",
        "knowledge": ["animal tracks near the river", "weather signs", "which plants are safe"],
        "attitude_to_strangers": "watchful",
        "speech_sample": "There was a bird here earlier. It watched the river for a long time and then it left.",
        "loquacity_base": 28,
    },
    {
        "given_name": "Dorn",
        "voice": "blunt, impatient with questions he considers obvious",
        "knowledge": ["the eastern settlements", "what's dangerous on the road", "packing for travel"],
        "attitude_to_strangers": "indifferent",
        "speech_sample": "You're heading west. That's what the gear says. Don't need to tell me anything else.",
        "loquacity_base": 40,
    },
    {
        "given_name": "Yara",
        "voice": "bright, asks questions as much as she answers them",
        "knowledge": ["traveler gossip", "Badlands rumors", "what different packs mean"],
        "attitude_to_strangers": "open and curious",
        "speech_sample": "Someone came through yesterday with a sword like yours. Not the same. But like it. Where'd you get it?",
        "loquacity_base": 48,
    },
    {
        "given_name": "Pell",
        "voice": "shy, speaks in fragments, looks at the ground between sentences",
        "knowledge": ["foraging near the water", "what the river washes up", "camp routines"],
        "attitude_to_strangers": "nervous",
        "speech_sample": "The river brings things. Sometimes useful things. Sometimes just things.",
        "loquacity_base": 25,
    },
    {
        "given_name": "Tess",
        "voice": "watchful, learned to read people early, observant without being intrusive",
        "knowledge": ["people-reading", "camp dynamics", "who to trust and who to avoid"],
        "attitude_to_strangers": "assessing",
        "speech_sample": "You're not from the settlements. I can tell. Most people can't tell, but I can.",
        "loquacity_base": 38,
    },
    {
        "given_name": "Corin",
        "voice": "restless, answers in bursts, always looking toward the horizon",
        "knowledge": ["the western road by reputation", "what travelers carry", "river currents"],
        "attitude_to_strangers": "eager",
        "speech_sample": "Is it different out there? Past the river? People say things but nobody says the same thing.",
        "loquacity_base": 45,
    },
    {
        "given_name": "Mira",
        "voice": "practical, speaks like someone who's been helping with camp work since she could walk",
        "knowledge": ["camp craft", "cooking over a fire", "mending packs and straps"],
        "attitude_to_strangers": "polite but busy",
        "speech_sample": "If you're staying, there's food. If you're crossing, there's advice. Which one?",
        "loquacity_base": 32,
    },
]


# ═════════════════════════════════════════════════════════════════════════════
# NomadBoy — young nomad, variable age, conversational
# ═════════════════════════════════════════════════════════════════════════════

class NomadBoy(ConversationalNPCMixin, Friend):
    """A young nomad boy at the east-bank camp, age ranging from child to
    young adult. Personality and appearance are randomized on instantiation.
    Conversational via LLM with deterministic fallback. Low loquacity.
    """

    _DESCRIPTIONS = [
        (
            "A small boy crouched near the fire ring with the careful intensity of "
            "someone learning to tend a flame. His hands are smudged with ash and he "
            "watches the coals like they might tell him something."
        ),
        (
            "A lean boy, not quite old enough to carry his own gear but old enough "
            "to know the weight of everyone else's. He sits near a pack that isn't his, "
            "watching the camp with the quiet alertness of a child who travels."
        ),
        (
            "A boy with restless hands, winding a piece of twine around his fingers "
            "in a pattern that might be a game or might be practice for something "
            "he'll need later."
        ),
        (
            "A lanky teenager sharpening a knife with more focus than the task "
            "demands. He's at the age where every small skill is being tested "
            "against the road."
        ),
        (
            "A young man who's nearly grown into his shoulders. His pack is worn at "
            "the straps and he carries himself with the careful awareness of someone "
            "who's crossed the river more than once."
        ),
        (
            "A boy in patched clothing, old enough to run errands but young enough to "
            "still be sent on them. He looks up at Jean without the guardedness "
            "adults wear."
        ),
        (
            "A boy with wind-tangled hair watching the far bank of the river. He's "
            "been sitting there long enough that his stillness has become deliberate "
            "— waiting, or deciding, or just looking."
        ),
    ]

    _TALK_LINES = [
        (
            "The boy glances at Jean's pack with undisguised interest. 'That's a lot "
            "of gear,' he says. He doesn't ask what's in it, but he's clearly wondering."
        ),
        (
            "He's winding twine around a stick with intense concentration. Without "
            "looking up: 'Going west?' He doesn't wait for an answer."
        ),
        (
            "'The river's lower today than yesterday,' he says. 'Devet says that means "
            "rain up north. Or it doesn't. He wasn't sure.'"
        ),
        (
            "He says, 'Someone came through yesterday. Had a sword.' A pause. 'A "
            "different sword. But similar.' He returns to what he was doing, apparently "
            "satisfied with this contribution."
        ),
        (
            "The boy is quiet for a long moment. Then: 'I've crossed the river twice. "
            "Once with the group. Once by myself.' He doesn't explain further, and "
            "something in his tone suggests he won't."
        ),
        (
            "He looks toward the far bank with the particular stillness of someone "
            "calculating something. 'The west is supposed to be different,' he says. "
            "'Nobody says how.'"
        ),
        (
            "'Are you with the stone one?' he asks. 'The Golemite? He doesn't talk "
            "much either.' The boy seems to find this acceptable."
        ),
        (
            "The boy studies Jean's gear with the careful attention of someone "
            "learning to read strangers by their luggage. He doesn't say what he's "
            "concluded."
        ),
        (
            "'Mara says the Badlands change people. She wouldn't say how.' He looks "
            "toward the far bank. 'People always stop explaining at the interesting part.'"
        ),
        (
            "He says, 'If you're looking for Devet, he's by the fire. If you're looking "
            "for Mara, she's probably already seen you.' He says this like it's simply true."
        ),
        (
            "The boy feeds a twig to the fire ring with the casual expertise of someone "
            "who's done it a thousand times. 'Camp's been here three weeks. Maybe four. "
            "You lose track after a while.'"
        ),
        (
            "He's watching a bird on the far bank. His expression doesn't change, but "
            "he's been watching it for a while. 'Things look different from this side,' "
            "he says eventually."
        ),
    ]

    def __init__(self):
        description = random.choice(self._DESCRIPTIONS)
        personality = random.choice(_YOUNG_NOMAD_PERSONALITIES)

        super().__init__(
            name="Nomad Boy",
            description=description,
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=30,
            protection=1,
            speed=9,
            finesse=7,
            awareness=10,
            charisma=10,
            idle_message=" is sitting near the fire ring, watching the camp.",
            alert_message=" looks up, startled.",
            discovery_message="a young nomad boy at the camp.",
        )
        self.keywords = ["talk"]
        self.pronouns = {
            "personal": "he",
            "possessive": "his",
            "reflexive": "himself",
            "intensive": "himself",
        }
        self.wisdom = 8
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []
        self._chat_config_path = None
        self._init_chat_attrs()
        # Override with randomized personality (set after _init_chat_attrs so
        # _ensure_personality finds it already populated and skips LLM/fallback).
        self._chat_personality = personality

    def talk(self, player):
        """Terminal fallback — static dialogue. Web uses chat_open/chat_respond via the API."""
        narrate(random.choice(self._TALK_LINES))


# ═════════════════════════════════════════════════════════════════════════════
# NomadGirl — young nomad, variable age, conversational
# ═════════════════════════════════════════════════════════════════════════════

class NomadGirl(ConversationalNPCMixin, Friend):
    """A young nomad girl at the east-bank camp, age ranging from child to
    young adult. Personality and appearance are randomized on instantiation.
    Conversational via LLM with deterministic fallback. Low loquacity.
    """

    _DESCRIPTIONS = [
        (
            "A small girl sitting cross-legged with something cupped carefully in her "
            "hands — a smooth river stone, or a beetle, or something she found that "
            "matters to her. She looks up at Jean and decides, visibly, whether to "
            "show him."
        ),
        (
            "A girl with a watchful stillness, old enough to be trusted near the water "
            "but young enough to still have someone calling her name from across the camp."
        ),
        (
            "A girl in her early teens with dark hair tied back in a strip of cloth. "
            "She's sorting supplies with the careful efficiency of someone who wants "
            "to be seen doing it right."
        ),
        (
            "A girl with a traveler's tan and a direct gaze. Old enough to carry her "
            "own water, young enough to still be surprised by the weight of it."
        ),
        (
            "A young woman whose pack is organized the way experienced travelers "
            "organize — straps coiled, nothing loose. She watches Jean with the "
            "assessment of someone who's learned to read strangers."
        ),
        (
            "A girl with a smudge of ash on her forehead and a piece of colored twine "
            "braided into her hair. She's been near the fire — close enough to get the "
            "ash, not close enough to be scolded for it."
        ),
        (
            "A girl at the river's edge with her arms wrapped around her knees. She's "
            "watching the far bank with the particular stillness of someone who has "
            "imagined crossing more times than she's actually done it."
        ),
    ]

    _TALK_LINES = [
        (
            "The girl looks up from whatever she's holding in her cupped hands. 'Are "
            "you going across?' she asks. 'Everyone who comes here goes across. Except "
            "the ones who don't.'"
        ),
        (
            "She's sitting at the edge of a group of packs, watching the camp with "
            "the quiet alertness of someone who notices everything. 'Your pack is "
            "different from ours,' she says. Not an accusation. An observation."
        ),
        (
            "'The river brings things,' she says. 'Sometimes useful things. Sometimes "
            "just things.' She's holding a smooth stone, turning it over in her palm."
        ),
        (
            "She says, 'I've seen three groups cross this week. Two came back. One "
            "didn't.' She doesn't elaborate. She seems to think the numbers speak "
            "for themselves."
        ),
        (
            "The girl studies Jean directly. 'You're not from the settlements,' she "
            "says. 'I can tell.' She seems pleased with herself, but not boastful."
        ),
        (
            "She's sorting something — small items, wrapped in cloth — with the careful "
            "efficiency of someone who's been given a task and means to do it right. "
            "She doesn't look up."
        ),
        (
            "She says, 'Devet told me the Badlands used to be different. Before.' "
            "A pause. 'He didn't say before what.' She seems to have been turning "
            "this over for a while."
        ),
        (
            "The girl is watching the river with an expression that's hard to read. "
            "'The current shifts,' she says. 'Not every day. But often enough that "
            "you have to pay attention.' She says this like advice someone gave her once."
        ),
        (
            "'Are you with the Golemite?' she asks. 'I've never seen one up close. "
            "Mara says not to stare. I'm not staring.' She is definitely staring."
        ),
        (
            "She says, 'Liss asked me if the stone one eats. I told her I didn't know. "
            "Do you know?' She seems genuinely curious about the answer."
        ),
        (
            "'Someone came through last week heading east,' she says. 'Said the road "
            "past the Badlands is — ' She pauses, searching for the word. 'Different. "
            "That's all he said. Different.'"
        ),
        (
            "The girl ties off a knot on something she's mending with the practiced "
            "motion of someone who's done it many times. She bites the thread, examines "
            "her work, and sets it aside."
        ),
    ]

    def __init__(self):
        description = random.choice(self._DESCRIPTIONS)
        personality = random.choice(_YOUNG_NOMAD_PERSONALITIES)

        super().__init__(
            name="Nomad Girl",
            description=description,
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=30,
            protection=1,
            speed=9,
            finesse=7,
            awareness=10,
            charisma=10,
            idle_message=" is sitting near the fire ring, watching the camp.",
            alert_message=" looks up, startled.",
            discovery_message="a young nomad girl at the camp.",
        )
        self.keywords = ["talk"]
        self.pronouns = {
            "personal": "she",
            "possessive": "her",
            "reflexive": "herself",
            "intensive": "herself",
        }
        self.wisdom = 8
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []
        self._chat_config_path = None
        self._init_chat_attrs()
        # Override with randomized personality (set after _init_chat_attrs so
        # _ensure_personality finds it already populated and skips LLM/fallback).
        self._chat_personality = personality

    def talk(self, player):
        """Terminal fallback — static dialogue. Web uses chat_open/chat_respond via the API."""
        narrate(random.choice(self._TALK_LINES))
