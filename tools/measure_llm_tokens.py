"""Token-budget baseline for every LLM call path in the game.

Free-tier providers meter on tokens, not requests: Cerebras caps the free tier
at ~1M tokens/day and an 8k context window, Groq at ~6k tokens/minute. Both
count prompt + completion together. This script measures what a round trip
actually costs so those ceilings can be reasoned about instead of guessed at.

Prompts are measured exactly -- it drives the real builders
(``ConversationalNPCMixin._build_system_prompt``, ``NpcChatLLMAdapter``'s
generate_* methods, ``CombatStrategist._build_user_prompt``) against the real
world_facts.json and character configs, so the numbers track the shipping
prompts and move when those move.

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
"""

import importlib.util
import json
import logging
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "src"))

try:
    import tiktoken
except ImportError:
    sys.exit("tiktoken is required: pip install tiktoken")

ENC = tiktoken.get_encoding("o200k_base")

# The adapters log a warning every time the stubbed _call_llm returns None.
# That is the expected path here, so keep it out of the report.
logging.disable(logging.WARNING)


def ntok(s):
    return len(ENC.encode(s or ""))


# Chat-template overhead: role headers and separators, ~4 tokens per message
# plus a few for the reply primer. Consistent across the OpenAI, Llama and
# Qwen templates to within a token or two.
OVERHEAD = 4 * 2 + 3

ROWS = []
DUMP = []


def record(path, call, system, user, max_tokens, note=""):
    s, u = ntok(system), ntok(user)
    DUMP.append((system, user))
    ROWS.append({
        "path": path, "call": call,
        "sys_tok": s, "user_tok": u,
        "in_tok": s + u + OVERHEAD,
        "max_out": max_tokens,
        "worst_rt": s + u + OVERHEAD + max_tokens,
        "sys_chars": len(system), "user_chars": len(user),
        "note": note,
    })


# ---------------------------------------------------------------------------
# Load ai/llm_client.py the same way the game does (by path, not by package)
# ---------------------------------------------------------------------------
_spec = importlib.util.spec_from_file_location(
    "llm_client", os.path.join(REPO, "ai", "llm_client.py"))
llm = importlib.util.module_from_spec(_spec)
sys.modules["llm_client"] = llm
_spec.loader.exec_module(llm)

from src.npc._chat_llm import ConversationalNPCMixin  # noqa: E402

HUMAN_DIR = os.path.join(REPO, "ai", "npc", "human")


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


# The adapter's generate_* methods build the user prompt and hand it to
# _call_llm. Swapping _call_llm for a recorder captures the exact pair that
# would have gone over the wire, with no network and no mocked HTTP layer.
CAPTURED = {}


def _capture(self, system_prompt, user_prompt, max_tokens=512, temperature=0.7):
    CAPTURED.update(sys=system_prompt, user=user_prompt, max_tokens=max_tokens)
    return None


llm.NpcChatLLMAdapter._call_llm = _capture
adapter = llm.NpcChatLLMAdapter.__new__(llm.NpcChatLLMAdapter)
adapter._world_facts = json.load(
    open(os.path.join(HUMAN_DIR, "world_facts.json"), encoding="utf-8"))
adapter.provider, adapter.model, adapter.enabled = "openrouter", "x", True


def cap(path, call, note=""):
    record(path, call, CAPTURED["sys"], CAPTURED["user"], CAPTURED["max_tokens"], note)


# A representative exchange. _format_history caps at the last 8, so history
# beyond that does not grow the prompt.
_TURN = {
    "jean": "You've been out past the ridge line. What did you see there?",
    "npc": "Dust, mostly. And tracks that didn't belong to any herd I know.",
}


def hist(n):
    return [dict(_TURN) for _ in range(n)]


# ---------------------------------------------------------------------------
# 1. NPC chat
# ---------------------------------------------------------------------------
nomad = make_npc(personality={
    "given_name": "Ren", "voice": "sparse, declarative",
    "knowledge": ["water routes", "herd sickness"], "loquacity_base": 65})
adapter.generate_turn(nomad._build_system_prompt(_Player()), [], is_opening=True)
cap("NPC chat", "generate_turn (generic nomad, opening)")

# Largest character config on disk -- the realistic upper bound for the block.
BIG = max((f for f in os.listdir(HUMAN_DIR)
           if f.endswith(".json") and f != "world_facts.json"),
          key=lambda f: os.path.getsize(os.path.join(HUMAN_DIR, f)))

story_npc = make_npc(config_path=os.path.join(HUMAN_DIR, BIG))
sys_story = story_npc._build_system_prompt(_Player())
adapter.generate_turn(sys_story, hist(6), is_opening=False,
                      jean_text="Then whose tracks were they? You'd know if it were bandits.")
cap("NPC chat", "generate_turn (story NPC %s, 6-turn history)" % BIG)

ally = make_npc(
    config_path=os.path.join(HUMAN_DIR, BIG), growth=True, level=15,
    moves=[_Move("Rending Arc", "A wide sweeping strike that carries through multiple foes."),
           _Move("Ironhold", "Plant and absorb an incoming blow, converting it to counter-pressure."),
           _Move("Quicken", "Shorten the wind-up on the next technique at the cost of stability."),
           _Move("Sunder Guard", "A precise thrust aimed at a gap in the opponent's defense."),
           _Move("Second Wind", "Recover breath and footing after a punishing exchange.")])
adapter.generate_turn(ally._build_system_prompt(_Player()), hist(12), is_opening=False,
                      jean_text="You've changed since the caves. Tell me plainly what you can do now.")
cap("NPC chat", "generate_turn (WORST: ally, full history)", "upper bound")

adapter.generate_personality("weathered nomad herder")
cap("NPC chat", "generate_personality (one-shot)")

adapter.generate_npc_turn(sys_story, hist(6), is_opening=False,
                          jean_text="Then whose tracks were they?")
cap("NPC chat", "generate_npc_turn (legacy split 1/2)")

adapter.generate_jean_options(
    "Mara", "wary, speaks in short bursts",
    "Dust, mostly. And tracks that didn't belong to any herd I know.", hist(6), 7)
cap("NPC chat", "generate_jean_options (legacy split 2/2)")

# ---------------------------------------------------------------------------
# 2. Mynx
# ---------------------------------------------------------------------------
mynx = llm.MynxLLMAdapter.__new__(llm.MynxLLMAdapter)
mynx._advisor = mynx._load_mynx_advisor()
mynx._allowed_actions = set(
    mynx._advisor.get("behavior_profile", {}).get("typical_actions", []) or ["investigate_object"])
mynx._example_struct = mynx._advisor.get("example_structured_response", {})
mynx_sys = mynx._advisor.get("system_prompt_snippet", "")
mynx_ctx = ("Jean is resting by a low fire in a rock hollow. The mynx has eaten recently, "
            "is not alarmed, and a loose strap on Jean's pack is within reach.")
record("Mynx", "generate_structured", mynx_sys, mynx._build_user_prompt(mynx_ctx, True), 1024)
record("Mynx", "generate_plain", mynx_sys, mynx._build_user_prompt(mynx_ctx, False), 256)

# ---------------------------------------------------------------------------
# 3. Combat tactical advisor
# ---------------------------------------------------------------------------
from ai.combat_strategist import CombatStrategist  # noqa: E402

strat = CombatStrategist.__new__(CombatStrategist)
# A stub client, not None: CombatStrategist falls back to constructing a real
# GenericLLMClient, whose __init__ runs OpenRouter model discovery and a live
# validation chat. Measuring prompt sizes must not spend free-tier requests.
CombatStrategist.__init__(strat, client=type("_Stub", (), {"available": lambda self: False})())


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
    _move("Heavy Swing", "Offensive", 12, "A slow, powerful overhead blow with high damage.",
          ("Rumbler",)),
    _move("Dodge", "Defensive", 0, "Evade the next incoming attack entirely."),
    _move("Parry", "Defensive", 3, "Block an incoming blow and counter if the timing lands."),
    _move("Withdraw", "Defensive", 4, "Disengage and open distance from the nearest threat."),
    _move("Advance", "Maneuver", 0, "Move one tile toward the selected target."),
    _move("Rest", "Miscellaneous", 0, "Recover fatigue while remaining vulnerable."),
    _move("Use Item", "Miscellaneous", 0, "Consume an item from the quick-use belt."),
]

# Names drawn from _STATUS_TACTICAL_NOTES so the mechanical + tactical note
# lines actually render; unknown names collapse to a bare label and understate
# the real cost of this block.
PLAYER_SE = [{"name": "Poisoned", "duration": 4}, {"name": "Disoriented", "duration": 3}]
ENEMY_SE = [{"name": "Enflamed", "duration": 3}]


def _enemy(i, name):
    return {"id": "enemy_%d" % i, "name": name, "hp": 40 - 6 * i, "max_hp": 55,
            "fatigue": 22, "max_fatigue": 80, "distance": 2 + i,
            "position": {"x": 2 + i, "y": 3, "facing": "S"},
            "stats": {"damage": 11, "evasion": 8, "defense": 4, "accuracy": 78, "speed": 5},
            "move_in_process": {"name": "Gore", "beats_until_impact": 2,
                                "estimated_damage": 14},
            "status_effects": list(ENEMY_SE)}


def ctx_for(n_enemies, n_allies, n_history, moves, player_se):
    return {
        "player": {
            "name": "Jean", "hp": 58, "max_hp": 120, "fatigue": 41, "max_fatigue": 100,
            "heat": 1.45, "position": {"x": 2, "y": 2, "facing": "N"},
            "attributes": {"strength": 16, "finesse": 14, "endurance": 13, "resistance": 11,
                           "charisma": 10, "intelligence": 12, "faith": 15},
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


for _label, _ctx, _note in [
    ("get_suggestions (light: 1 enemy, 0 allies, 4 moves)",
     ctx_for(1, 0, 5, MOVES[:4], []), ""),
    ("get_suggestions (typical: 2 enemies, 1 ally, 9 moves)",
     ctx_for(2, 1, 20, MOVES, PLAYER_SE), ""),
    ("get_suggestions (WORST: 4 enemies, 2 allies, 9 moves)",
     ctx_for(4, 2, 20, MOVES, PLAYER_SE), "upper bound"),
]:
    record("Combat TA", _label, strat.system_prompt, strat._build_user_prompt(_ctx), 1024, _note)

# ---------------------------------------------------------------------------
# Realistic completions (see module docstring -- these are written, not measured)
# ---------------------------------------------------------------------------
_turn_out = {
    "npc_text": "Not bandits. Bandits leave fire rings and they leave them careless. "
                "Whatever walked that ridge line took pains not to be followed.",
    "npc_flavor": "She turns the strap of her pack over once, then lets it fall.",
    "conversation_quality": "neutral", "reputation_delta": 1, "loquacity_delta": -7,
    "jean_options": [
        {"tone": "direct", "text": "Then say what you think it was. I can carry an ugly answer."},
        {"tone": "guarded", "text": "Tracks are tracks. I'd rather not borrow trouble from a ridge line."},
        {"tone": "open", "text": "You sound like someone who has seen this before. When?"},
    ],
}
_ta_out = {"suggestions": [
    {"move_name": "Parry", "target_id": None, "score": 88,
     "reasoning": "The Rumbler's Gore lands in two beats for an estimated 14; Parry both blunts "
                  "it and sets up a counter while Dodge is still on cooldown."},
    {"move_name": "Slash", "target_id": "enemy_1", "score": 71,
     "reasoning": "The Cave Bat is at 34 HP and your heat is 1.45x, so a cheap 5-fatigue strike "
                  "preserves the streak without overcommitting."},
    {"move_name": "Rest", "target_id": None, "score": 54,
     "reasoning": "Fatigue at 41/100 is approaching the threshold where Heavy Swing becomes "
                  "unavailable, but resting now surrenders the heat bonus."}]}

_J = lambda o: json.dumps(o, ensure_ascii=False)  # noqa: E731

OUTPUTS = [
    ("NPC chat", "generate_turn", _J(_turn_out)),
    ("NPC chat", "generate_personality", _J({
        "given_name": "Ren",
        "voice": "sparse and declarative, with long pauses between thoughts",
        "knowledge": ["seasonal water routes", "herd sickness"],
        "attitude_to_strangers": "wary",
        "speech_sample": "Water's three days east if the spring hasn't turned. If it has, you walk.",
        "loquacity_base": 62})),
    ("NPC chat", "generate_npc_turn (legacy)", _J({
        "npc_text": _turn_out["npc_text"], "conversation_quality": "neutral",
        "conversation_end": False, "reputation_delta": 1})),
    ("NPC chat", "generate_jean_options (legacy)", _J(_turn_out["jean_options"])),
    ("Mynx", "generate_structured", _J({
        "action": "investigate_object", "intensity": "low",
        "description": "The mynx noses the loose strap, batting it once before losing interest.",
        "duration_seconds": 3, "audible": "soft chitter"})),
    ("Mynx", "generate_plain",
     "The mynx noses the loose strap, bats it once, then settles back on its haunches."),
    ("Combat TA", "get_suggestions (1 suggestion)",
     _J({"suggestions": _ta_out["suggestions"][:1]})),
    ("Combat TA", "get_suggestions (3 suggestions)", _J(_ta_out)),
]


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def table(rows, cols, widths):
    print("  ".join(
        h.ljust(w) if i == 1 else h.rjust(w)
        for i, (h, w) in enumerate(zip(cols, widths))))
    print("-" * (sum(widths) + 2 * (len(widths) - 1)))
    last = None
    for r in rows:
        if last and r[0] != last:
            print()
        last = r[0]
        print("  ".join(str(v).ljust(w) if i < 2 else str(v).rjust(w)
                        for i, (v, w) in enumerate(zip(r, widths))))


W = max(len(r["call"]) for r in ROWS)
table([(r["path"], r["call"], r["sys_tok"], r["user_tok"], r["in_tok"],
        r["max_out"], r["worst_rt"]) for r in ROWS],
      ["PATH", "CALL", "sys", "user", "IN", "max_out", "CEILING"],
      [9, W, 6, 6, 6, 7, 7])

_chars = sum(r["sys_chars"] + r["user_chars"] for r in ROWS)
_toks = sum(r["sys_tok"] + r["user_tok"] for r in ROWS)
print("\nCalibration: %d chars / %d tokens = %.2f chars per token"
      % (_chars, _toks, _chars / _toks))

if "--outputs" in sys.argv:
    print()
    OW = max(len(c) for _, c, _ in OUTPUTS)
    caps = {r["call"].split(" (")[0]: r["max_out"] for r in ROWS}
    rows = []
    for path, call, text in OUTPUTS:
        cap_ = caps.get(call.split(" (")[0], 0)
        t = ntok(text)
        rows.append((path, call, t, cap_, "%.1fx" % (cap_ / t) if t else "-"))
    table(rows, ["PATH", "CALL", "real", "max_out", "margin"], [9, OW, 6, 7, 7])
    print("\n'real' completions are written to schema, not measured from live calls.")

if "--dump" in sys.argv:
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_prompt_dump")
    os.makedirs(d, exist_ok=True)
    for i, r in enumerate(ROWS):
        slug = "".join(c if c.isalnum() else "_" for c in r["call"])[:60]
        with open(os.path.join(d, "%02d_%s.txt" % (i, slug)), "w", encoding="utf-8") as f:
            f.write("### SYSTEM (%d tok)\n%s\n\n### USER (%d tok)\n%s\n"
                    % (r["sys_tok"], DUMP[i][0], r["user_tok"], DUMP[i][1]))
    print("\nDumped %d prompts to %s" % (len(ROWS), d))

if "--json" in sys.argv:
    dest = sys.argv[sys.argv.index("--json") + 1]
    json.dump(ROWS, open(dest, "w"), indent=2)
    print("\nWrote %s" % dest)
