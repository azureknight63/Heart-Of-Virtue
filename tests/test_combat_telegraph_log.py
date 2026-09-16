"""Issue #586: a heavy enemy wind-up is its own combat-log entry type.

King Slime's Tidal Surge (2.5x, 84-134 damage against a 114 HP Jean) was
announced by one uncoloured line in the scrolling log. The move's inline
``colored(..., "yellow")`` never survives ``narrate`` (src/narration.py only
honours the ``color=`` keyword) and the API never forwards narration colour
anyway -- CombatLog.jsx colours by ``entry.type`` alone, and every NPC line
reached it as ``"combat"``.

So the wind-up line of a move whose ``telegraph_severity`` is not "normal" is
minted ``"telegraph"`` instead. The type is the wire contract CombatLog.jsx's
``LOG_ENTRY_COLORS`` keys on (CombatLog.test.jsx derives the vocabulary from
combat_adapter.py), which is why these tests spell the literal.

Every fight here is built from real engine objects through
``tests/_combat_fixtures`` and seeded: nothing asserts on an unseeded roll.
"""

from unittest.mock import patch

import pytest

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


def _cast(adapter, npc, move_cls):
    """Drive ``npc`` through one real ``_process_npc`` beat, casting ``move_cls``.

    ``select_move`` is pinned rather than the roster patched so the cast goes
    through the adapter's own capture path -- the code under test -- exactly
    as a weighted selection would.
    """
    move = move_cls(npc)
    npc.current_move = None
    npc.combat_delay = 0
    npc.select_move = lambda: setattr(npc, "current_move", move)
    with seeded(), forced_roll(1), adapter._capture_output():
        adapter._process_npc(npc)
    return move


def _entries(player, containing):
    return [e for e in player.combat_log if containing in e["message"]]


class TestHeavyWindupLogType:
    def test_tidal_surge_prep_line_is_minted_telegraph(self, build_fight):
        player, adapter = build_fight(enemies=[KingSlime()])
        [king] = player.combat_list

        _cast(adapter, king, TidalSurge)

        prep = _entries(player, "about to surge")
        assert prep, [e["message"] for e in player.combat_log]
        assert {e["type"] for e in prep} == {TELEGRAPH}

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
        for _ in range(30):
            if move.current_stage >= 2:
                break
            with seeded(), forced_roll(1), adapter._capture_output():
                adapter._process_npc(king)

        hit = _entries(player, "slams into")
        assert hit, [e["message"] for e in player.combat_log]
        assert {e["type"] for e in hit} == {"combat"}
        assert {e["type"] for e in _entries(player, "about to surge")} == {
            TELEGRAPH
        }

    def test_a_routine_npc_attack_windup_stays_combat(self, build_fight):
        """Negative control: NpcAttack narrates a wind-up too. It must NOT be
        marked, or the glyph marks every enemy every beat and warns of
        nothing."""
        player, adapter = build_fight(enemies=[Slime()])
        [slime] = player.combat_list

        _cast(adapter, slime, NpcAttack)

        prep = _entries(player, "coils in preparation")
        assert prep, [e["message"] for e in player.combat_log]
        assert {e["type"] for e in prep} == {"combat"}

    def test_an_allys_heavy_windup_is_not_a_warning(self, build_fight):
        """The type is a threat cue for Jean. A friendly combatant charging a
        heavy move is not something the player has to get clear of."""
        ally = make_npc(name="Bulwark")
        player, adapter = build_fight(enemies=[Slime()], allies=[ally])

        _cast(adapter, ally, TidalSurge)

        prep = _entries(player, "about to surge")
        assert prep, [e["message"] for e in player.combat_log]
        assert {e["type"] for e in prep} == {"combat"}

    def test_telegraph_lines_survive_into_the_last_move_summary(self):
        """``last_move_summary`` (the wire's ``last_move_outcome`` and the
        strategist's ``last_move``) keeps only whitelisted types. A new type
        that is not on that list drops the single most important line of the
        fight from both -- the regression the fix could cause."""
        from src.api.combat_adapter import summarize_recent_log

        log = [
            {"type": "combat", "message": "Jean swings."},
            {"type": TELEGRAPH, "message": "It is about to surge."},
            {"type": "animation", "message": "bookkeeping"},
            {"type": "player_action", "message": "Jean prepares Dodge."},
        ]
        assert summarize_recent_log(log) == (
            "Jean swings. It is about to surge. Jean prepares Dodge."
        )
