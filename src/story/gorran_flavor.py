"""
Gorran ambient flavor text.

Two entry points:
  - maybe_combat_flavor(player, beat, cooldown)  -> int  (returns updated cooldown)
  - maybe_explore_flavor(player)                 -> None

Both are no-ops when Gorran is absent. Neither crashes on unexpected state.
"""

import logging
import random

from neotermcolor import colored

# ──────────────────────────────────────────────────────────────────────────────
# Flavor pools
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

# Fires when Jean's HP drops below 40 %
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
        # Choose pool based on context
        hp_ratio = player.hp / max(player.max_hp, 1)
        gorran_hp = getattr(gorran, "hp", None)
        gorran_prev_hp = getattr(gorran, "_prev_hp_for_flavor", gorran_hp)

        if hp_ratio < _COMBAT_HURT_HP_THRESHOLD and _COMBAT_JEAN_HURT:
            pool = _COMBAT_JEAN_HURT
        elif (
            gorran_hp is not None
            and gorran_prev_hp is not None
            and gorran_hp < gorran_prev_hp
            and _COMBAT_GORRAN_HURT
        ):
            pool = _COMBAT_GORRAN_HURT
        else:
            pool = _COMBAT_GENERAL

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

        line = random.choice(_EXPLORE)
        print(colored(line, "yellow"))
        story["gorran_explore_last_tick"] = str(current_tick)

    except Exception as e:
        logging.warning("gorran_flavor explore: %s", e)
