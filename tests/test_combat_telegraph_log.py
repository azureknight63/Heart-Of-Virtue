"""Issue #586: a heavy enemy wind-up is its own combat-log entry type.

King Slime's Tidal Surge (then 2.5x, 84-134 damage against a 114 HP Jean;
retuned to 1.8x by part B of the same issue) was
announced by one uncoloured line in the scrolling log. The move's inline
``colored(..., "yellow")`` never survives ``narrate`` (src/narration.py only
honours the ``color=`` keyword) and the API never forwards narration colour
anyway -- CombatLog.jsx colours by ``entry.type`` alone, and every NPC line
reached it as ``"combat"``.

So the wind-up line of a move whose ``telegraph_severity`` is not "normal" is
minted ``"telegraph"`` instead. The type is the wire contract CombatLog.jsx's
``LOG_ENTRY_COLORS`` keys on (CombatLog.test.jsx derives the vocabulary from
combat_adapter.py), which is why these tests spell the literals and hold them
to the engine's constants in one place.

Every fight here is built from real engine objects through
``tests/_combat_fixtures`` and seeded: nothing asserts on an unseeded roll.
"""

import inspect
from unittest.mock import patch

import pytest

from src.api import combat_adapter
from src.api.combat_adapter import summarize_recent_log
from src.moves import NpcAttack, TidalSurge
from src.npc._enemies import KingSlime, Slime
from tests._combat_fixtures import (
    forced_roll,
    make_adapter,
    make_npc,
    make_player,
    seeded,
)

TELEGRAPH = "telegraph"
COMBAT = "combat"

#: ``Move`` stages run 0 wind-up, 1 hit, 2 recoil, 3 cooldown. A move that has
#: reached the recoil has narrated its hit line.
_RECOIL_STAGE = 2


@pytest.fixture
def build_fight():
    """Real adapter over a real Jean and the given enemies/allies.

    ``CombatStrategist`` spins up background AI machinery unrelated to the log
    under test; every adapter test patches it the same way.
    """
    def _build(enemies, allies=()):
        with patch("src.api.combat_adapter.CombatStrategist"):
            player = make_player()
            with seeded():
                adapter = make_adapter(player, enemies=enemies, allies=allies)
        # initialize_combat may already have run a faster enemy's first turn;
        # start the log and the NPC from a known state.
        player.combat_log = []
        adapter._invalidate_log_key_index()
        return player, adapter
    return _build


def _beat(adapter, npc):
    """One real ``_process_npc`` beat through the adapter's own capture path.

    Seeded, with the to-hit roll forced, so nothing here rides on dice.
    """
    with seeded(), forced_roll(1), adapter._capture_output():
        adapter._process_npc(npc)


def _cast(adapter, npc, move_cls):
    """Drive ``npc`` through one real beat, casting ``move_cls``.

    ``select_move`` is pinned rather than the roster patched so the cast goes
    through the adapter's own capture path -- the code under test -- exactly
    as a weighted selection would.
    """
    move = move_cls(npc)
    npc.current_move = None
    npc.combat_delay = 0

    def pin_move():
        npc.current_move = move

    npc.select_move = pin_move
    _beat(adapter, npc)
    return move


def _entries(player, containing):
    return [e for e in player.combat_log if containing in e["message"]]


def _assert_log_type(player, containing, expected_type):
    """Every log line containing ``containing`` carries ``expected_type``.

    At least one such line must exist, or the type check is vacuous.
    """
    entries = _entries(player, containing)
    assert entries, [e["message"] for e in player.combat_log]
    assert {e["type"] for e in entries} == {expected_type}


class TestHeavyWindupLogType:
    def test_the_literals_here_are_the_engines_constants(self):
        """The literals above are the wire vocabulary; hold them to the
        engine's names so neither can drift alone. ``_add_log_entry`` keeps
        the literal ``"combat"`` in its signature because CombatLog.test.jsx
        reads that default by regex, so it is held here too."""
        assert TELEGRAPH == combat_adapter.TELEGRAPH_LOG_TYPE
        assert COMBAT == combat_adapter.COMBAT_LOG_TYPE
        default = inspect.signature(
            combat_adapter.ApiCombatAdapter._add_log_entry
        ).parameters["entry_type"].default
        assert default == combat_adapter.COMBAT_LOG_TYPE

    def test_tidal_surge_prep_line_is_minted_telegraph(self, build_fight):
        player, adapter = build_fight(enemies=[KingSlime()])
        [king] = player.combat_list

        _cast(adapter, king, TidalSurge)

        _assert_log_type(player, "about to surge", TELEGRAPH)

    def test_only_the_windup_is_tagged(self, build_fight):
        """The hit and recoil lines of the SAME move stay "combat": the type
        marks the moment the player can still react, not the whole move."""
        player, adapter = build_fight(enemies=[KingSlime()])
        [king] = player.combat_list
        # Jean must survive the surge for the recoil line to be reachable.
        player.hp = player.maxhp = 100000

        move = _cast(adapter, king, TidalSurge)
        # The surge winds up for 13 beats (NpcAttack's prep plus
        # _EXTRA_PREP_BEATS, re-applied by evaluate()); the cap is slack, the
        # stage check is what ends the loop.
        with seeded(), forced_roll(1), adapter._capture_output():
            for _ in range(30):
                if move.current_stage >= _RECOIL_STAGE:
                    break
                adapter._process_npc(king)

        _assert_log_type(player, "slams into", COMBAT)
        _assert_log_type(player, "about to surge", TELEGRAPH)

    def test_a_routine_npc_attack_windup_stays_combat(self, build_fight):
        """Negative control: NpcAttack narrates a wind-up too. It must NOT be
        marked, or the glyph marks every enemy every beat and warns of
        nothing."""
        player, adapter = build_fight(enemies=[Slime()])
        [slime] = player.combat_list

        _cast(adapter, slime, NpcAttack)

        _assert_log_type(player, "coils in preparation", COMBAT)

    def test_an_allys_heavy_windup_is_not_a_warning(self, build_fight):
        """The type is a threat cue for Jean. A friendly combatant charging a
        heavy move is not something the player has to get clear of."""
        ally = make_npc(name="Bulwark")
        player, adapter = build_fight(enemies=[Slime()], allies=[ally])

        _cast(adapter, ally, TidalSurge)

        _assert_log_type(player, "about to surge", COMBAT)

    def test_telegraph_lines_survive_into_the_last_move_summary(self):
        """``last_move_summary`` (the wire's ``last_move_outcome`` and the
        strategist's ``last_move``) keeps only whitelisted types. A new type
        that is not on that list drops the single most important line of the
        fight from both -- the regression the fix could cause."""
        log = [
            {"type": COMBAT, "message": "Jean swings."},
            {"type": TELEGRAPH, "message": "It is about to surge."},
            {"type": "animation", "message": "bookkeeping"},
            {"type": "player_action", "message": "Jean prepares Dodge."},
        ]
        assert summarize_recent_log(log) == (
            "Jean swings. It is about to surge. Jean prepares Dodge."
        )

    def test_summary_keeps_the_newest_lines_and_skips_blank_ones(self):
        """The summary is a window over the END of the log, and an entry with
        no message (a degraded save can carry one) contributes nothing rather
        than an empty token or a KeyError."""
        log = [{"type": COMBAT, "message": f"line {i}"} for i in range(10)]
        log.append({"type": COMBAT})
        log.append({"type": COMBAT, "message": ""})
        window = combat_adapter.SUMMARY_LOG_LINES
        assert summarize_recent_log(log) == " ".join(
            f"line {i}" for i in range(10 - window, 10)
        )
