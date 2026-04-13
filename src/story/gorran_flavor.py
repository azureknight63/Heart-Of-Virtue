"""
Gorran ambient flavor text — stage-aware.

Two entry points:
  - maybe_combat_flavor(player, beat, cooldown)  -> int  (returns updated cooldown)
  - maybe_explore_flavor(player)                 -> None

Both are no-ops when Gorran is absent. Neither crashes on unexpected state.

Gorran's language acquisition arc runs across four stages (story flag
"gorran_language_stage"). Each stage adds spoken lines on top of the
Stage 0 narrated-gesture base. Spoken lines are rare by design — Gorran
conserves language. At Stage 1 he has one word ("Stop"); by Stage 4 he
has short earned sentences. The narrated pools never go away; they remain
the primary texture throughout the game.

Stage 0 — no words; all narrated gesture and sound
Stage 1 — "Back!" in hurt contexts only; otherwise still silent
Stage 2 — single-word directions in general rotation; name possible
Stage 3 — short functional phrases; physical vocabulary for emotion
Stage 4 — shorthand, very sparse, each line earned
"""

import logging
import random

from neotermcolor import colored

# ──────────────────────────────────────────────────────────────────────────────
# Stage 0 — Narrated base pools (present at all stages)
# ──────────────────────────────────────────────────────────────────────────────

# Fires at any point during a normal combat beat
_COMBAT_GENERAL = [
    "Gorran's eyes sweep the room between strikes — counting, measuring.",
    "A low, grinding sound issues from Gorran's chest. It might be concentration.",
    "Gorran doesn't look at Jean. His attention is on the next threat.",
    "Gorran braces. The stone floor under his feet gives a faint crack.",
    "Gorran makes a sound — short, clipped — that might be satisfaction.",
    "The stone of Gorran's forearms is darker where it's taken hits. He doesn't check it.",
    "For a half-second Gorran is perfectly still. Then he's back in it.",
    "Gorran exhales — a pressured, grinding sound — and settles his weight.",
    "Gorran catches Jean's eye for a half-second. Something passes between them that isn't language.",
    "Gorran fights the way stone moves downhill: with momentum, not urgency.",
    "Gorran doesn't celebrate when a blow lands. He is already looking for the next one.",
    "A short, deep rumble from Gorran. Whatever it means, it doesn't sound worried.",
    "Gorran's attention is on the fight — not the nearest enemy, but the whole room.",
    "A low sound from Gorran, rhythmic, almost deliberate. He might be counting.",
    "Gorran's jaw is set. Whatever he's thinking, he keeps it to himself.",
]

# Fires when Jean's HP drops below 40%
_COMBAT_JEAN_HURT = [
    "Gorran's attention snaps to Jean. He hasn't stopped fighting, but now he's watching.",
    "A short, urgent sound from Gorran. His eyes are on Jean now.",
    "Gorran doesn't speak. His focus narrows on Jean.",
    "Two short rumbles from Gorran — low, clipped. He's found Jean in the chaos.",
    "Gorran makes a sound — quick, sharp. His eyes track Jean across the field.",
]

# Fires when Gorran himself just took a hit (his HP dropped this beat)
_COMBAT_GORRAN_HURT = [
    "Gorran absorbs the blow without flinching. He looks at whatever hit him as though mildly interested.",
    "Gorran takes the hit full. He doesn't flinch. He doesn't stop.",
    "Gorran makes a sound — deep, measured — that might be acknowledgement. Then he's back in it.",
    "Gorran reaches up and brushes dust from the strike site. It's a casual motion. Almost contemptuous.",
]

# Fires during exploration (main game loop, not in combat)
_EXPLORE = [
    "Gorran runs a hand along the tunnel wall without slowing, reading the stone with his fingers.",
    "Gorran stops briefly. Presses his palm flat against the rock. Lifts it. Moves on.",
    "Gorran crouches to look at something in the path Jean had already passed. He doesn't pick it up — just looks, then straightens.",
    "For a moment Gorran stands completely still, head tilted. Whatever he was listening for, it seems to answer. He continues.",
    "Gorran ducks at a low overhang, well before he reaches it.",
    "Gorran pauses at a junction and turns his head — one way, then the other — before moving on.",
    "Gorran makes three short sounds. Jean doesn't know what they mean.",
    "Gorran notices Jean noticing him. He makes a brief rolling gesture with one hand. Jean has no idea what it means.",
    "Gorran moves through the dark without hesitation, one hand never straying far from the walls.",
    "Gorran places one heavy foot with unusual care on a stretch of floor, then steps around it.",
    "Something in the passage makes Gorran produce a sound that is — almost certainly — a chuckle.",
    "Gorran slows. Not stopping — just slowing. Something ahead is different. Then he picks up the pace again.",
    "Gorran rests a hand briefly on the ceiling as he passes below a low arch, steadying himself or greeting the stone. Hard to say which.",
    "Gorran glances back at Jean once, then ahead again.",
]


# ──────────────────────────────────────────────────────────────────────────────
# Stage 1 — spoken additions (Jean hurt only; costs everything he has)
# ──────────────────────────────────────────────────────────────────────────────

_COMBAT_S1_JEAN_HURT = [
    # "Back!" — the same mechanism as "Stop." One word, flat, hard.
    "Gorran's eyes find Jean across the field. One word cuts through everything: \"Back.\" He doesn't stop moving.",
]


# ──────────────────────────────────────────────────────────────────────────────
# Stage 2 — single-word directions (general + hurt)
# ──────────────────────────────────────────────────────────────────────────────

_COMBAT_S2_GENERAL = [
    # Words used rarely; each one costs something, even now.
    "Gorran points — a single gesture at a position to Jean's left. \"Here.\" He doesn't wait to see if Jean moves.",
    "A short break in Gorran's attention. He meets Jean's eyes. \"Good.\" Then back to the fight.",
    "Gorran's hand comes up once — firm, brief. \"No.\" He's already past the thing he's refusing.",
]

_COMBAT_S2_JEAN_HURT = [
    # "Back!" costs less now. He has the word established.
    '"Back!" — sharp, without hesitation. He has said this before.',
    # Name. First time he uses it in the chaos.
    'Gorran says the name — "Jean" — and nothing else. His eyes don\'t leave the threat between them.',
]


# ──────────────────────────────────────────────────────────────────────────────
# Stage 3 — short phrases, physical vocabulary for emotion
# ──────────────────────────────────────────────────────────────────────────────

_COMBAT_S3_GENERAL = [
    '"I take left." Gorran is already moving before he finishes saying it.',
    'Gorran catches Jean\'s eye across the field. "Stand. I hold them."',
    '"Done." He says it once, quietly, when the last one falls.',
    # Physical vocabulary — player learns to read this alongside Jean.
    'A sound from Gorran — low, even. Then: "Heavy." He is looking at something above them.',
    '"Rough." Said under his breath. It might mean something other than the terrain.',
    '"Jean — behind. Two." He\'s already adjusting before Jean can turn.',
]

_COMBAT_S3_JEAN_HURT = [
    '"Jean. Behind." He says it plainly, like pointing at a fact.',
    '"Jean — left. Now."',
]


# ──────────────────────────────────────────────────────────────────────────────
# Stage 4 — shorthand, earned, very sparse
# ──────────────────────────────────────────────────────────────────────────────

_COMBAT_S4_GENERAL = [
    '"I see it." He does not elaborate. He moves.',
    '"Go. I follow."',
    # "Good." said rarely at Stage 4 lands completely differently than at Stage 2.
    '"Good." He says it once, quietly, at the end. It is not a small thing anymore.',
    '"Still here." He doesn\'t look at Jean when he says it.',
]


# ──────────────────────────────────────────────────────────────────────────────
# Stage 2–4 explore additions
# ──────────────────────────────────────────────────────────────────────────────

_EXPLORE_S2 = [
    'Gorran slows at a fork. After a moment: "Here." He moves left.',
    'Something ahead stops Gorran. He holds one hand out — steady, don\'t move — and listens. "Wait." Then continues.',
]

_EXPLORE_S3 = [
    'Gorran pauses at a section of wall and presses his palm flat against it. "Cold," he says. Not to Jean. To the stone.',
    '"Passage. Weight. Wrong." He steps around a particular stretch of floor rather than across it.',
    'At an intersection, Gorran looks both ways. "Rough," he says, indicating the left path. He takes the right.',
]

_EXPLORE_S4 = [
    'Gorran moves through the passage without slowing. "Still," he says once. Jean isn\'t sure if it means the space or something in Gorran.',
    '"Here." Gorran stops at a specific point and holds it, scanning ahead. Then moves.',
]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _find_gorran(player):
    """Return the Gorran ally if he is in the party, otherwise None."""
    try:
        for ally in player.combat_list_allies:
            if ally is not player and getattr(ally, "name", "") == "Gorran":
                return ally
    except Exception:
        pass
    return None


def get_gorran_stage(player):
    """Return Gorran's current language stage as an int (0–4)."""
    try:
        return int(player.universe.story.get("gorran_language_stage", "0"))
    except Exception:
        return 0


def _combat_general_for_stage(stage):
    pool = list(_COMBAT_GENERAL)
    if stage >= 2:
        pool += _COMBAT_S2_GENERAL
    if stage >= 3:
        pool += _COMBAT_S3_GENERAL
    if stage >= 4:
        pool += _COMBAT_S4_GENERAL
    return pool


def _combat_jean_hurt_for_stage(stage):
    pool = list(_COMBAT_JEAN_HURT)
    if stage >= 1:
        pool += _COMBAT_S1_JEAN_HURT
    if stage >= 2:
        pool += _COMBAT_S2_JEAN_HURT
    if stage >= 3:
        pool += _COMBAT_S3_JEAN_HURT
    return pool


def _explore_for_stage(stage):
    pool = list(_EXPLORE)
    if stage >= 2:
        pool += _EXPLORE_S2
    if stage >= 3:
        pool += _EXPLORE_S3
    if stage >= 4:
        pool += _EXPLORE_S4
    return pool


# ──────────────────────────────────────────────────────────────────────────────
# Public entry points
# ──────────────────────────────────────────────────────────────────────────────

_COMBAT_CHANCE = 0.22  # ~1-in-5 beats
_COMBAT_COOLDOWN_BEATS = 4  # minimum beats between lines
_COMBAT_HURT_HP_THRESHOLD = 0.40

_EXPLORE_CHANCE = 0.18  # ~1-in-6 ticks
_EXPLORE_MIN_TICKS = 5  # minimum ticks between lines


def maybe_combat_flavor(player, beat, cooldown):
    """
    Possibly print a Gorran combat flavor line.

    Call once per combat beat, after the ally has acted. Returns the updated
    cooldown counter (caller must store it and pass it back next beat).

    Args:
        player:   The Player instance.
        beat:     Current combat beat number (int).
        cooldown: Remaining beats before another line can fire (int).

    Returns:
        int: Updated cooldown value for the caller to store.
    """
    if cooldown > 0:
        return cooldown - 1

    gorran = _find_gorran(player)
    if gorran is None:
        return 0

    if random.random() > _COMBAT_CHANCE:
        return 0

    try:
        stage = get_gorran_stage(player)

        hp_ratio = player.hp / max(player.max_hp, 1)
        gorran_hp = getattr(gorran, "hp", None)
        gorran_prev_hp = getattr(gorran, "_prev_hp_for_flavor", gorran_hp)

        if hp_ratio < _COMBAT_HURT_HP_THRESHOLD:
            pool = _combat_jean_hurt_for_stage(stage)
        elif (
            gorran_hp is not None
            and gorran_prev_hp is not None
            and gorran_hp < gorran_prev_hp
        ):
            pool = _COMBAT_GORRAN_HURT
        else:
            pool = _combat_general_for_stage(stage)

        line = random.choice(pool)
        print(colored(line, "yellow"))

        # _prev_hp_for_flavor: intentional dynamic attribute — tracks Gorran's
        # HP between beats so we can detect when he took a hit this beat.
        gorran._prev_hp_for_flavor = gorran_hp

        return _COMBAT_COOLDOWN_BEATS

    except Exception as e:
        logging.warning("gorran_flavor combat: %s", e)
        return 0


def maybe_explore_flavor(player):
    """
    Possibly print a Gorran exploration flavor line.

    Call once per game tick, outside of combat. No-op when Gorran is absent,
    the cooldown hasn't elapsed, or skip_dialog is set.

    Args:
        player: The Player instance.
    """
    if getattr(player, "skip_dialog", False):
        return
    gorran = _find_gorran(player)
    if gorran is None:
        return

    try:
        story = player.universe.story
        last_tick = int(story.get("gorran_explore_last_tick", -999))
        current_tick = player.universe.game_tick

        if current_tick - last_tick < _EXPLORE_MIN_TICKS:
            return
        if random.random() > _EXPLORE_CHANCE:
            return

        stage = get_gorran_stage(player)
        pool = _explore_for_stage(stage)
        line = random.choice(pool)
        print(colored(line, "yellow"))
        story["gorran_explore_last_tick"] = str(current_tick)

    except Exception as e:
        logging.warning("gorran_flavor explore: %s", e)
