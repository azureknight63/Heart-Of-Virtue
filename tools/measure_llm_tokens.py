"""Token-budget baseline for every LLM call path in the game.

Free-tier providers meter on tokens, not requests: Cerebras caps the free tier
at ~1M tokens/day and an 8k context window, Groq at ~6k tokens/minute. Both
count prompt + completion together. This script measures what a round trip
actually costs so those ceilings can be reasoned about instead of guessed at.

Prompts are measured exactly -- it drives the real builders
(``ConversationalNPCMixin._build_system_prompt``, ``NpcChatLLMAdapter``'s
generate_* methods, ``MynxLLMAdapter``, ``CombatStrategist._build_user_prompt``
plus ``wrap_suggestions_prompt``) against the real world_facts.json and
character configs, so the numbers track the shipping prompts and move when
those move. Nothing here restates a prompt fragment or re-implements a
constructor: a measurement of a copy is a measurement of nothing.

Completions cannot be measured without live calls, so the ``--outputs`` table
tokenizes hand-written responses that satisfy each path's validator, at the
length its prompt asks for ("1-3 sentences", "8-20 words"). Those are the
realistic case, not the ``max_tokens`` ceiling.

Counting uses tiktoken's ``o200k_base`` -- the tokenizer family behind
gpt-oss-120b, and within ~5-10% of the Llama-3 and Qwen-3 BPEs used by the
other free models. Treat the totals as accurate to about a tenth.

Usage:
    pip install tiktoken
    python tools/measure_llm_tokens.py              # prompt token table
    python tools/measure_llm_tokens.py --outputs    # + realistic completions
    python tools/measure_llm_tokens.py --dump       # + full prompts to disk
    python tools/measure_llm_tokens.py --json out.json

Note: tiktoken downloads the o200k_base BPE file over the network on first
use and caches it afterward (TIKTOKEN_CACHE_DIR overrides the location) --
the measurement itself makes no LLM calls and spends no quota.
"""

import argparse
import contextlib
import json
import logging
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

_ENCODING = None


def _encoding():
    """Load the BPE lazily.

    ``tiktoken.get_encoding`` reads (and on a cold cache downloads) a large
    file. At import time that bill was paid by ``--help`` and by an argparse
    error too.
    """
    global _ENCODING
    if _ENCODING is None:
        try:
            import tiktoken
        except ImportError:
            sys.exit("tiktoken is required: pip install tiktoken")
        _ENCODING = tiktoken.get_encoding("o200k_base")
    return _ENCODING


def ntok(s):
    return len(_encoding().encode(s or ""))


# Chat-template overhead: role headers and separators, ~4 tokens per message
# plus a few for the reply primer. Consistent across the OpenAI, Llama and
# Qwen templates to within a token or two.
_TOKENS_PER_MESSAGE_HEADER = 4  # role header + separator tokens, per message
_MESSAGE_COUNT = 2  # system prompt + user prompt sent per call
_REPLY_PRIMER_TOKENS = 3  # tokens reserved for the assistant's reply primer
OVERHEAD = _TOKENS_PER_MESSAGE_HEADER * _MESSAGE_COUNT + _REPLY_PRIMER_TOKENS


def record(rows, path, call, system, user, max_tokens, key, note=""):
    """Append one measured call to ``rows``.

    ``key`` is the join key against :data:`OUTPUTS` in the completion table.
    It is an explicit argument because it used to be derived by splitting the
    human-readable ``call`` label on ``" ("`` -- so renaming a label silently
    detached the two tables and printed a confident ``0.0x`` margin.
    """
    s, u = ntok(system), ntok(user)
    rows.append(
        {
            "path": path,
            "call": call,
            "key": key,
            "sys_tok": s,
            "user_tok": u,
            "in_tok": s + u + OVERHEAD,
            "max_out": max_tokens,
            "worst_rt": s + u + OVERHEAD + max_tokens,
            "sys_chars": len(system),
            "user_chars": len(user),
            "note": note,
            # Kept on the row itself rather than in a parallel DUMP list
            # indexed by position -- an invariant nothing declared and
            # nothing checked.
            "system": system,
            "user": user,
        }
    )


# ---------------------------------------------------------------------------
# Import ai/llm_client.py as the canonical package module. Loading it by path
# under a bare "llm_client" key created a SECOND module object the moment
# `from ai.combat_strategist import ...` (below) pulled in `ai.llm_client` --
# the exact mutually-unaware-copies bug issue #380 fixed in the engine.
# ---------------------------------------------------------------------------
import ai.llm_client as llm  # noqa: E402

from src.npc._chat_llm import ConversationalNPCMixin  # noqa: E402
import src.npc._chat_guard as chat_guard  # noqa: E402
from ai.combat_strategist import (  # noqa: E402
    CombatStrategist,
    _DEFENSIVE_WINDOW_BEATS,
    wrap_suggestions_prompt,
)
import src.moves as moves  # noqa: E402
import src.states as states  # noqa: E402
from src.api.serializers.combat import (  # noqa: E402
    CombatantSerializer,
    StateEffectSerializer,
)

# ai.llm_client owns the NPC-chat character directory. Hand-rolling
# os.path.join(REPO, "ai", "npc", "human") here made a fifth copy of a path
# that the loader can move at any time. Tolerates the constant being promoted
# to a public name.
HUMAN_DIR = getattr(llm, "NPC_CHAT_HUMAN_DIR", None) or llm._NPC_CHAT_HUMAN_DIR


class _Universe:
    def __init__(self, chapter, gorran):
        self.story = {"chapter": chapter, "gorran_language_stage": gorran}


class _Player:
    def __init__(self, chapter="3", gorran="2"):
        self.universe = _Universe(chapter, gorran)


class _Move:
    def __init__(self, name, desc):
        self.name, self.description = name, desc


def make_npc(config_path=None, personality=None, growth=False, level=1, moves=()):
    class _N(ConversationalNPCMixin):
        pass

    n = _N()
    n._chat_config_path = config_path
    n._init_chat_attrs()
    if personality:
        n._chat_personality = personality
    if growth:
        n.growth_profile = {"tier": "ally"}
        n.level = level
        n.known_moves = list(moves)
    return n


def _biggest_npc_config():
    """Largest character config on disk -- the realistic upper bound for the
    story-NPC prompt block."""
    return max(
        (
            f
            for f in os.listdir(HUMAN_DIR)
            if f.endswith(".json") and f != "world_facts.json"
        ),
        key=lambda f: os.path.getsize(os.path.join(HUMAN_DIR, f)),
    )


# The adapter's generate_* methods build the user prompt and hand it to the
# transport. Swapping the transport for a recorder captures the exact pair
# that would have gone over the wire, with no network and no mocked HTTP
# layer -- and, crucially, without re-implementing any of the assembly.
CAPTURED = {}


def _capture_call_llm(self, system_prompt, user_prompt, max_tokens=512, **_ignored):
    """Stand-in for ``NpcChatLLMAdapter._call_llm``.

    ``**_ignored`` rather than a restated signature: mirroring every keyword
    of the real method meant a new one (or a renamed one) raised TypeError
    here instead of being harmlessly absorbed.
    """
    # clear() first so a generate_* path that returns before reaching the
    # transport makes capture_call() raise KeyError instead of silently
    # re-reporting the previous call's numbers.
    CAPTURED.clear()
    CAPTURED.update(sys=system_prompt, user=user_prompt, max_tokens=max_tokens)
    return None


# GenericLLMClient hardcodes these in its OpenRouter/Ollama payload builders
# (`1024 if structured else 256`) rather than taking them as an argument, so
# _dispatch_chat cannot report them and they are restated here. If those
# literals move, these must move with them.
_GENERIC_MAX_TOKENS = {True: 1024, False: 256}


def _capture_dispatch(self, system_prompt, user_prompt, structured=False, **_ignored):
    """Stand-in for ``GenericLLMClient._dispatch_chat`` (the Mynx path)."""
    CAPTURED.clear()
    CAPTURED.update(
        sys=system_prompt,
        user=user_prompt,
        max_tokens=_GENERIC_MAX_TOKENS[bool(structured)],
    )
    return None


@contextlib.contextmanager
def _patched(owner, name, replacement):
    """Temporarily replace ``owner.name``, restoring it on the way out."""
    original = getattr(owner, name)
    setattr(owner, name, replacement)
    try:
        yield
    finally:
        setattr(owner, name, original)


def capture_call(rows, path, call, key, note=""):
    record(
        rows, path, call, CAPTURED["sys"], CAPTURED["user"], CAPTURED["max_tokens"],
        key, note,
    )


# A representative exchange. _format_history caps at the last 8, so history
# beyond that does not grow the prompt.
_TURN = {
    "jean": "You've been out past the ridge line. What did you see there?",
    "npc": "Dust, mostly. And tracks that didn't belong to any herd I know.",
}


def hist(n):
    return [dict(_TURN) for _ in range(n)]


def _move(name, cat, cost, desc, targets=()):
    m = {"name": name, "available": True, "category": cat, "fatigue_cost": cost,
         "description": desc, "targeted": bool(targets)}
    if targets:
        m["viable_targets"] = [{"name": t, "id": "enemy_%d" % i, "distance": 2 + i}
                               for i, t in enumerate(targets)]
    return m


MOVES = [
    _move("Slash", "Offensive", 5, "A quick slashing strike with the equipped blade.",
          ("Rumbler", "Cave Bat")),
    _move("Thrust", "Offensive", 7, "A committed thrust that trades guard for reach.",
          ("Rumbler", "Cave Bat")),
    _move("Heavy Swing", "Offensive", 12,
          "A slow, powerful overhead blow with high damage.", ("Rumbler",)),
    _move("Dodge", "Defensive", 0, "Evade the next incoming attack entirely."),
    _move("Parry", "Defensive", 3,
          "Block an incoming blow and counter if the timing lands."),
    _move("Withdraw", "Defensive", 4,
          "Disengage and open distance from the nearest threat."),
    _move("Advance", "Maneuver", 0, "Move one tile toward the selected target."),
    _move("Rest", "Miscellaneous", 0, "Recover fatigue while remaining vulnerable."),
    _move("Use Item", "Miscellaneous", 0, "Consume an item from the quick-use belt."),
]


class _StatusTarget:
    """Just enough combatant for a State's ``__init__`` to compute its modifiers."""

    name = "Jean"
    in_combat = True
    hp = maxhp = 120
    fatigue = maxfatigue = 100
    finesse = protection = speed = strength = 100
    endurance = faith = charisma = intelligence = 20

    def __init__(self):
        self.states = []
        self.status_resistance = {}
        self.resistance = {}


def _status(state_cls, beats_left):
    """One status effect in the shape the real serializer emits.

    Built from the real ``State`` and run through the real
    ``StateEffectSerializer``, for the same reason nothing else in this file
    restates a prompt fragment: these entries carry ``tactical_mechanics``, the
    engine-owned mechanical summary the strategist renders beside its tactical
    note, and that text is the bulk of the status block's cost. The fixtures
    here used to be hand-typed ``{"name": ..., "duration": ...}`` pairs — a key
    the strategist does not read, with no mechanics at all — so every status
    line was measured at a fraction of its real width.
    """
    payload = StateEffectSerializer.serialize_state(state_cls(_StatusTarget()))
    payload["beats_left"] = beats_left
    return payload


# Names drawn from _STATUS_TACTICAL_NOTES so the mechanical + tactical note
# lines actually render; unknown names collapse to a bare label and understate
# the real cost of this block.
PLAYER_SE = [_status(states.Poisoned, 4), _status(states.Disoriented, 3)]
ENEMY_SE = [_status(states.Enflamed, 3)]

# The move a charging enemy is winding up. `beats_until_resolve` is the
# engine's own countdown (``Move.beats_until_resolve``) and the only field
# ``_incoming_beats`` reads — the fixture used to spell it
# ``beats_until_impact``, the name of a helper the strategist deleted, so it
# measured a prompt with no Charging line and no INCOMING alert in it at all.
# Pinned to the strategist's alert threshold so the alert block is inside the
# measurement, which is the upper bound this table exists to report.
#
# `damage_multiplier` is read off a real move class through the real serializer
# helper (no instance needed — it is a class attribute), so retuning the move
# moves the measured estimate with it.
_CHARGING_MOVE = {
    "name": "Club Strike",
    "beats_until_resolve": _DEFENSIVE_WINDOW_BEATS,
    "damage_multiplier": CombatantSerializer._serialize_damage_multiplier(
        moves.GorranClub
    ),
}


def _enemy(i, name):
    return {"id": "enemy_%d" % i, "name": name, "hp": 40 - 6 * i, "max_hp": 55,
            "fatigue": 22, "max_fatigue": 80, "distance": 2 + i,
            "position": {"x": 2 + i, "y": 3, "facing": "S"},
            "stats": {"damage": 11, "evasion": 8, "defense": 4, "accuracy": 78,
                      "speed": 5},
            "move_in_process": dict(_CHARGING_MOVE),
            "status_effects": [dict(se) for se in ENEMY_SE]}


def ctx_for(n_enemies, n_allies, n_history, moves, player_se):
    return {
        "player": {
            "name": "Jean", "hp": 58, "max_hp": 120, "fatigue": 41,
            "max_fatigue": 100,
            "heat": 1.45, "position": {"x": 2, "y": 2, "facing": "N"},
            "attributes": {"strength": 16, "finesse": 14, "endurance": 13,
                           "resistance": 11, "charisma": 10, "intelligence": 12,
                           "faith": 15},
            "stats": {"evasion": 12, "defense": 7, "accuracy": 84, "speed": 5},
            "passives": ["Strategic Insight", "Steady Hand", "Crusader's Resolve"],
            "status_effects": player_se,
            "consumables": [{"name": "Restorative Draught", "qty": 3},
                            {"name": "Antitoxin", "qty": 1}],
            "equipment": {"armor": {"defense": 9}},
        },
        "enemies": [_enemy(i, n) for i, n in
                    enumerate(["Rumbler", "Cave Bat", "Slime", "Bandit"][:n_enemies])],
        "allies": [{"id": "ally_%d" % i, "name": nm, "hp": 70, "max_hp": 90,
                    "fatigue": 60, "max_fatigue": 90, "distance": 1,
                    "position": {"x": 1, "y": 2}, "stats": {"damage": 9},
                    "status_effects": []}
                   for i, nm in enumerate(["Gorran", "Mara"][:n_allies])],
        "history": [["Jean's Slash struck the Rumbler for 14 damage.",
                     "The Cave Bat lunged at Jean and missed.",
                     "Gorran shielded Jean from the Rumbler's charge."][i % 3]
                    for i in range(n_history)],
        "last_move": "Slash",
        "available_moves": moves,
        "defensive_cooldowns": {"Dodge": 2, "Parry": 1},
    }


# base_suggested_move_count defaults to 1 (src/player/__init__.py) and is read
# verbatim as get_suggestions's max_suggestions argument
# (src/api/combat_adapter.py, ~line 1884) with no call site overriding it, so 1
# is the realistic value here, not just a placeholder.
_MAX_SUGGESTIONS = 1


# ---------------------------------------------------------------------------
# Realistic completions (see module docstring -- these are written, not measured)
# ---------------------------------------------------------------------------
_turn_out = {
    "npc_text": "Not bandits. Bandits leave fire rings and they leave them careless. "
                "Whatever walked that ridge line took pains not to be followed.",
    "npc_flavor": "She turns the strap of her pack over once, then lets it fall.",
    "conversation_quality": "neutral", "reputation_delta": 1, "loquacity_delta": -7,
    "jean_options": [
        {"tone": "direct",
         "text": "Then say what you think it was. I can carry an ugly answer."},
        {"tone": "guarded",
         "text": "Tracks are tracks. I'd rather not borrow trouble from a ridge "
                 "line."},
        {"tone": "open",
         "text": "You sound like someone who has seen this before. When?"},
    ],
}
_ta_out = {"suggestions": [
    {"move_name": "Parry", "target_id": None, "score": 88,
     "reasoning": "The Rumbler's Gore lands in two beats for an estimated 14; Parry "
                  "both blunts it and sets up a counter while Dodge is still on "
                  "cooldown."},
    {"move_name": "Slash", "target_id": "enemy_1", "score": 71,
     "reasoning": "The Cave Bat is at 34 HP and your heat is 1.45x, so a cheap "
                  "5-fatigue strike preserves the streak without overcommitting."},
    {"move_name": "Rest", "target_id": None, "score": 54,
     "reasoning": "Fatigue at 41/100 is approaching the threshold where Heavy Swing "
                  "becomes unavailable, but resting now surrenders the heat bonus."}]}

_J = lambda o: json.dumps(o, ensure_ascii=False)  # noqa: E731

# (path, human label, join key into the measured rows, written completion).
OUTPUTS = [
    ("NPC chat", "generate_turn", "generate_turn", _J(_turn_out)),
    ("NPC chat", "generate_personality", "generate_personality", _J({
        "given_name": "Ren",
        "voice": "sparse and declarative, with long pauses between thoughts",
        "knowledge": ["seasonal water routes", "herd sickness"],
        "attitude_to_strangers": "wary",
        "speech_sample": "Water's three days east if the spring hasn't turned. "
                         "If it has, you walk.",
        "loquacity_base": 62})),
    ("NPC chat", "generate_npc_turn (legacy)", "generate_npc_turn", _J({
        "npc_text": _turn_out["npc_text"], "conversation_quality": "neutral",
        "conversation_end": False, "reputation_delta": 1})),
    ("NPC chat", "generate_jean_options (legacy)", "generate_jean_options",
     _J(_turn_out["jean_options"])),
    ("Mynx", "generate_structured", "generate_structured", _J({
        "action": "investigate_object", "intensity": "low",
        "description": "The mynx noses the loose strap, batting it once before "
                       "losing interest.",
        "duration_seconds": 3, "audible": "soft chitter"})),
    ("Mynx", "generate_plain", "generate_plain",
     "The mynx noses the loose strap, bats it once, then settles back on its "
     "haunches."),
    ("Combat TA", "get_suggestions (1 suggestion)", "get_suggestions",
     _J({"suggestions": _ta_out["suggestions"][:1]})),
    ("Combat TA", "get_suggestions (3 suggestions)", "get_suggestions", _J(_ta_out)),
]


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------
def _measure_npc_chat(rows):
    """Drive every NpcChatLLMAdapter path once, recording into ``rows``."""
    adapter = llm.NpcChatLLMAdapter.__new__(llm.NpcChatLLMAdapter)
    # The real loader, so this uses the real world_facts.json path and the real
    # fallback when it is missing -- a local json.load() of a hand-built path
    # was a copy of both.
    adapter._world_facts = None
    adapter._load_world_facts()
    adapter.provider, adapter.model, adapter.enabled = "openrouter", "x", True

    with _patched(llm.NpcChatLLMAdapter, "_call_llm", _capture_call_llm):
        nomad = make_npc(personality={
            "given_name": "Ren", "voice": "sparse, declarative",
            "knowledge": ["water routes", "herd sickness"], "loquacity_base": 65})
        adapter.generate_turn(
            nomad._build_system_prompt(_Player()), [], is_opening=True)
        capture_call(rows, "NPC chat", "generate_turn (generic nomad, opening)",
                     "generate_turn")

        # Largest character config on disk -- the realistic upper bound.
        big = _biggest_npc_config()

        story_npc = make_npc(config_path=os.path.join(HUMAN_DIR, big))
        sys_story = story_npc._build_system_prompt(_Player())
        adapter.generate_turn(
            sys_story, hist(6), is_opening=False,
            jean_text="Then whose tracks were they? You'd know if it were bandits.")
        capture_call(rows, "NPC chat",
                     "generate_turn (story NPC %s, 6-turn history)" % big,
                     "generate_turn")

        ally = make_npc(
            config_path=os.path.join(HUMAN_DIR, big), growth=True, level=15,
            moves=[
                _Move("Rending Arc",
                      "A wide sweeping strike that carries through multiple foes."),
                _Move("Ironhold",
                      "Plant and absorb an incoming blow, converting it to "
                      "counter-pressure."),
                _Move("Quicken",
                      "Shorten the wind-up on the next technique at the cost of "
                      "stability."),
                _Move("Sunder Guard",
                      "A precise thrust aimed at a gap in the opponent's defense."),
                _Move("Second Wind",
                      "Recover breath and footing after a punishing exchange."),
            ])
        adapter.generate_turn(
            ally._build_system_prompt(_Player()), hist(12), is_opening=False,
            jean_text="You've changed since the caves. Tell me plainly what you "
                      "can do now.")
        capture_call(rows, "NPC chat", "generate_turn (WORST: ally, full history)",
                     "generate_turn", "upper bound")

        adapter.generate_personality("weathered nomad herder")
        capture_call(rows, "NPC chat", "generate_personality (one-shot)",
                     "generate_personality")

        adapter.generate_npc_turn(sys_story, hist(6), is_opening=False,
                                  jean_text="Then whose tracks were they?")
        capture_call(rows, "NPC chat", "generate_npc_turn (legacy split 1/2)",
                     "generate_npc_turn")

        adapter.generate_jean_options(
            "Mara", "wary, speaks in short bursts",
            "Dust, mostly. And tracks that didn't belong to any herd I know.",
            hist(6), 7)
        capture_call(rows, "NPC chat", "generate_jean_options (legacy split 2/2)",
                     "generate_jean_options")

        # Guard-escalation call (211fbb4): fires only when the cheap regex
        # tripwire in src/npc/_chat_guard.py flags a turn. Drive it with a line
        # the real scanner actually flags and the guidance text it actually
        # produces, so this row is as real as the others.
        flagged_line = "Here, take this blade."
        guidance = chat_guard.guidance_for(chat_guard.scan_npc_text(flagged_line))
        adapter.revise_turn(
            sys_story,
            flagged_line,
            [
                {"tone": "direct",
                 "text": "That blade's seen more roads than I have. Where did it "
                         "come from?"},
                {"tone": "guarded",
                 "text": "I don't take gifts from strangers, not out here."},
                {"tone": "open", "text": "Tell me its story first, then we'll talk."},
            ],
            guidance,
        )
        capture_call(rows, "NPC chat", "revise_turn (guard escalation)",
                     "revise_turn")


def _make_mynx_adapter():
    """Construct the real ``MynxLLMAdapter``, with only the network suppressed.

    Building one by hand re-implemented ``__init__`` and had already diverged
    from it -- it grew an ``or ["investigate_object"]`` fallback the real
    constructor does not have, and bound the system prompt to a local instead
    of ``self._system_prompt``, so the assembly path under measurement was not
    the one that ships.

    ``MYNX_LLM_ENABLED=0`` is the single switch that keeps
    ``GenericLLMClient.__init__`` off the wire (it gates the OpenRouter model
    discovery and the live validation chat). Everything else -- the advisor
    load, the allowed-action set, the system prompt -- runs for real.
    """
    previous = os.environ.get("MYNX_LLM_ENABLED")
    os.environ["MYNX_LLM_ENABLED"] = "0"
    try:
        return llm.MynxLLMAdapter()
    finally:
        if previous is None:
            os.environ.pop("MYNX_LLM_ENABLED", None)
        else:
            os.environ["MYNX_LLM_ENABLED"] = previous


def _measure_mynx(rows):
    """Drive the Mynx adapter's two public methods, recording into ``rows``."""
    mynx = _make_mynx_adapter()
    ctx = (
        "Jean is resting by a low fire in a rock hollow. The mynx has eaten "
        "recently, is not alarmed, and a loose strap on Jean's pack is within reach."
    )
    with _patched(llm.GenericLLMClient, "_dispatch_chat", _capture_dispatch):
        mynx.generate_structured(ctx)
        capture_call(rows, "Mynx", "generate_structured", "generate_structured")

        mynx.generate_plain(ctx)
        capture_call(rows, "Mynx", "generate_plain", "generate_plain")


def _measure_combat_ta(rows):
    """Size the tactical advisor's prompt at three context sizes."""
    # A stub client, not None: CombatStrategist otherwise constructs a real
    # adapter, whose __init__ runs OpenRouter model discovery and a live
    # validation chat. Measuring prompt sizes must not spend free-tier requests.
    strat = CombatStrategist(
        client=type("_Stub", (), {"available": lambda self: False})())

    for label, ctx, note in [
        ("get_suggestions (light: 1 enemy, 0 allies, 4 moves)",
         ctx_for(1, 0, 5, MOVES[:4], []), ""),
        ("get_suggestions (typical: 2 enemies, 1 ally, 9 moves)",
         ctx_for(2, 1, 20, MOVES, PLAYER_SE), ""),
        ("get_suggestions (WORST: 4 enemies, 2 allies, 9 moves)",
         ctx_for(4, 2, 20, MOVES, PLAYER_SE), "upper bound"),
    ]:
        # get_suggestions appends the JSON-instruction wrapper to
        # _build_user_prompt's output before sending, so the bare prompt
        # understates the real wire size by ~25 tokens. Imported from the
        # strategist, not restated: this file used to keep a hand-copy of that
        # f-string with a comment admitting it "mirrors that wrapper exactly".
        record(rows, "Combat TA", label, strat.system_prompt,
               wrap_suggestions_prompt(strat._build_user_prompt(ctx),
                                       _MAX_SUGGESTIONS),
               1024, "get_suggestions", note)


def _run_measurements():
    """Drive every LLM call path once and return the measured rows."""
    rows = []
    CAPTURED.clear()
    _measure_npc_chat(rows)
    _measure_mynx(rows)
    _measure_combat_ta(rows)
    return rows


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def table(rows, cols, widths, align):
    """Render rows under headers, blank-lining whenever the PATH column
    (each row's first field) changes.

    ``align`` is an explicit per-column "l"/"r" spec, one entry per column --
    replacing the old index-based guess ("columns 0-1 are text, the rest are
    numeric") that only happened to hold because both call sites in this file
    are shaped that way.
    """

    def _pad(value, width, a):
        return str(value).ljust(width) if a == "l" else str(value).rjust(width)

    print("  ".join(_pad(h, w, a) for h, w, a in zip(cols, widths, align)))
    print("-" * (sum(widths) + 2 * (len(widths) - 1)))
    last = None
    for r in rows:
        if last and r[0] != last:
            print()
        last = r[0]
        print("  ".join(_pad(v, w, a) for v, w, a in zip(r, widths, align)))


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Token-budget baseline for every LLM call path in the game.")
    parser.add_argument(
        "--outputs", action="store_true",
        help="also print a realistic-completion margin table")
    parser.add_argument(
        "--dump", action="store_true",
        help="also write full prompts to tools/_prompt_dump/")
    parser.add_argument(
        "--json", metavar="PATH",
        help="also write the raw measurement rows to PATH as JSON")
    return parser.parse_args(argv)


def _print_prompt_table(rows):
    width = max(len(r["call"]) for r in rows)
    table([(r["path"], r["call"], r["sys_tok"], r["user_tok"], r["in_tok"],
            r["max_out"], r["worst_rt"]) for r in rows],
          ["PATH", "CALL", "sys", "user", "IN", "max_out", "CEILING"],
          [9, width, 6, 6, 6, 7, 7],
          ["l", "l", "r", "r", "r", "r", "r"])

    chars = sum(r["sys_chars"] + r["user_chars"] for r in rows)
    toks = sum(r["sys_tok"] + r["user_tok"] for r in rows)
    print("\nCalibration: %d chars / %d tokens = %.2f chars per token"
          % (chars, toks, chars / toks))


def _print_outputs_table(rows):
    width = max(len(label) for _, label, _, _ in OUTPUTS)
    # Ceilings, keyed by the explicit join key on each measured row -- not by
    # the captured system/user prompt pairs, which is what CAPTURED holds
    # mid-measurement. One letter apart in a file about token caps, so spelled
    # out in full.
    ceilings = {r["key"]: r["max_out"] for r in rows}

    out_rows = []
    missing = []
    for path, label, key, text in OUTPUTS:
        ceiling = ceilings.get(key)
        if ceiling is None:
            missing.append((label, key))
        tokens = ntok(text)
        if ceiling is None:
            margin = "?"
        elif tokens:
            margin = "%.1fx" % (ceiling / tokens)
        else:
            margin = "-"
        out_rows.append(
            (path, label, tokens, "?" if ceiling is None else ceiling, margin))

    table(out_rows, ["PATH", "CALL", "real", "max_out", "margin"],
          [9, width, 6, 7, 7], ["l", "l", "r", "r", "r"])
    print("\n'real' completions are written to schema, not measured from live calls.")
    if missing:
        # Never render a missing ceiling as 0 -- a 0.0x margin reads as a
        # measured catastrophe rather than as a broken join.
        print("\nWARNING: no measured ceiling for %s. Each OUTPUTS key must match "
              "a record(key=...) above."
              % ", ".join("%s (key %r)" % (lb, k) for lb, k in missing))


def _dump_prompts(rows):
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_prompt_dump")
    os.makedirs(d, exist_ok=True)
    for i, r in enumerate(rows):
        slug = "".join(c if c.isalnum() else "_" for c in r["call"])[:60]
        with open(os.path.join(d, "%02d_%s.txt" % (i, slug)), "w",
                  encoding="utf-8") as f:
            f.write("### SYSTEM (%d tok)\n%s\n\n### USER (%d tok)\n%s\n"
                    % (r["sys_tok"], r["system"], r["user_tok"], r["user"]))
    print("\nDumped %d prompts to %s" % (len(rows), d))


def _write_json(rows, path):
    # The prompt text itself lives on the rows now; keep it out of the JSON,
    # which is a counts artifact (--dump is the way to get the prompts).
    payload = [{k: v for k, v in r.items() if k not in ("system", "user")}
               for r in rows]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("\nWrote %s" % path)


def _print_report(rows, args):
    _print_prompt_table(rows)

    if args.outputs:
        print()
        _print_outputs_table(rows)

    if args.dump:
        _dump_prompts(rows)

    if args.json:
        _write_json(rows, args.json)


def main(argv=None):
    args = _parse_args(argv)

    # The adapters log a warning every time the stubbed transport returns
    # None. That is the expected path here, so keep it out of the report --
    # restored in the finally so calling main() from inside a larger process
    # (or more than once) never leaves the logging config worse than it
    # found it.
    _prev_disable = logging.root.manager.disable
    logging.disable(logging.WARNING)
    try:
        rows = _run_measurements()
    finally:
        logging.disable(_prev_disable)

    _print_report(rows, args)


if __name__ == "__main__":
    main()
