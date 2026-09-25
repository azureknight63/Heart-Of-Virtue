"""Issue #688: the advisor must not recommend an attack that cannot do damage.

The adapter publishes a per-target ``damage_preview {min, max, lethal}`` on
every Offensive move's ``viable_targets`` (``_build_target_entry``, straight
from the engine's ``Move.preview_damage``). The fallback scorer priced every
Offensive move off the heat band alone and its target pick ranked enemies
without reading the preview, so with a Shortsword drawn against a Stone
Creature (0-0) beside a Slime (31-46, lethal) it recommended Attack 85 AT the
Stone Creature -- 150 times in a row in the QA run.

The hand-built contexts pin the scorer's rules; the adapter-level class drives
the real engine (CorruptedStoneCreature + Shortsword) so the preview the rules
read is the one the game actually publishes.
"""

from unittest.mock import patch

import pytest

from ai.combat_strategist import CombatStrategist


class _NoLLM:
    def available(self):
        return False


@pytest.fixture
def strategist():
    return CombatStrategist(client=_NoLLM())


STONE = {"id": "e_stone", "name": "Stone Creature", "hp": 20, "max_hp": 96,
         "stats": {"damage": 10}, "fatigue": 50, "max_fatigue": 50,
         "status_effects": []}
SLIME = {"id": "e_slime", "name": "Slime", "hp": 40, "max_hp": 40,
         "stats": {"damage": 5}, "fatigue": 50, "max_fatigue": 50,
         "status_effects": []}


def _target(enemy, lo, hi, lethal=False):
    return {"id": enemy["id"], "name": enemy["name"], "distance": 3,
            "hit_chance": 90,
            "damage_preview": {"min": lo, "max": hi, "lethal": lethal}}


def _ctx(moves, enemies=(STONE, SLIME), fatigue=100):
    return {
        "player": {"id": "player", "hp": 100, "max_hp": 100,
                   "fatigue": fatigue, "max_fatigue": 100, "heat": 1.0,
                   "stats": {"evasion": 20, "defense": 15},
                   "status_effects": []},
        "enemies": [dict(e) for e in enemies],
        "available_moves": moves,
    }


def _attack(*targets, name="Attack"):
    return {"name": name, "category": "Offensive", "available": True,
            "targeted": True, "viable_targets": list(targets)}


TURN = {"name": "Turn", "category": "Maneuver", "available": True}
REST = {"name": "Rest", "category": "Miscellaneous", "available": True}
SWAP = {"name": "Swap Weapon", "category": "Utility", "available": True}


def _scores(strategist, ctx):
    state = strategist._derive_tactical_state(ctx)
    return {
        m["name"]: strategist._score_move(m, state)
        for m in ctx["available_moves"]
    }


class TestTargetPickReadsThePreview:
    def test_a_harmless_target_is_not_picked_when_another_takes_damage(
        self, strategist
    ):
        """The QA fight: the Stone Creature is the weaker by HP%, so the
        ranking alone picks it -- and the swing does nothing to it."""
        ctx = _ctx([_attack(_target(STONE, 0, 0), _target(SLIME, 31, 46, True)),
                    TURN])
        [top] = strategist._get_fallback_suggestions(ctx, 1)
        assert top["move_name"] == "Attack"
        assert top["target_id"] == SLIME["id"], (
            "Attack was aimed at a target its own damage_preview says it "
            "cannot hurt"
        )

    def test_the_harmless_target_is_still_picked_when_it_is_the_only_one(
        self, strategist
    ):
        """Filtering must not empty the viable set: a targeted move whose every
        target is harmless keeps a target (it is scored down, not dropped)."""
        ctx = _ctx([_attack(_target(STONE, 0, 0))], enemies=(STONE,))
        [top] = strategist._get_fallback_suggestions(ctx, 1)
        assert top["target_id"] == STONE["id"]


class TestAPointlessAttackIsScoredAsOne:
    def test_an_attack_that_hurts_nobody_is_not_the_top_pick(self, strategist):
        ctx = _ctx([_attack(_target(STONE, 0, 0)), TURN], enemies=(STONE,))
        [top] = strategist._get_fallback_suggestions(ctx, 1)
        assert top["move_name"] != "Attack"

        score, reason = _scores(strategist, ctx)["Attack"]
        assert score <= 20
        assert "can't hurt" in reason and "Stone Creature" in reason, reason
        assert "baseline damage" not in reason

    def test_swap_weapon_outranks_rest_and_turn_when_no_attack_can_hurt(
        self, strategist
    ):
        """Fatigue low enough that Rest bids 72 -- the stalemate in the report
        alternated Attack and Rest while fatigue ran to zero."""
        ctx = _ctx([_attack(_target(STONE, 0, 0)), SWAP, REST, TURN],
                   enemies=(STONE,), fatigue=40)
        suggestions = strategist._get_fallback_suggestions(ctx, 3)
        assert suggestions[0]["move_name"] == "Swap Weapon", suggestions
        reason = suggestions[0]["reasoning"]
        # weapon_options carries no per-weapon preview, so the advice must
        # not promise the other weapon works -- only that this one does not.
        assert "Stone Creature" in reason
        assert "preview" in reason.lower(), reason

    def test_swap_weapon_is_not_raised_while_some_attack_can_hurt(
        self, strategist
    ):
        ctx = _ctx([_attack(_target(STONE, 0, 0), _target(SLIME, 5, 9)),
                    SWAP, TURN])
        scores = _scores(strategist, ctx)
        assert scores["Swap Weapon"][0] < scores["Attack"][0]
        assert scores["Attack"][0] == 85, "a partly-useful attack keeps its score"

    def test_moves_without_previews_score_exactly_as_before(self, strategist):
        """No viable_targets / no damage_preview -> no opinion. Existing
        strategist tests pass Offensive moves in exactly this shape."""
        bare = {"name": "Slash", "category": "Offensive", "available": True}
        nulled = _attack({"id": "e_stone", "name": "Stone Creature",
                          "distance": 3, "damage_preview": None}, name="Jab")
        ctx = _ctx([bare, nulled, SWAP])
        scores = _scores(strategist, ctx)
        assert scores["Slash"][0] == 85
        assert scores["Jab"][0] == 85
        assert scores["Swap Weapon"][0] == 40


class TestRealEngineStoneCreature:
    """The measured fight, on real engine objects: Shortsword (slashing)
    against CorruptedStoneCreature, whose slashing resistance and protection
    zero the blade, beside a Slime it cuts through."""

    @staticmethod
    def _fight(enemies):
        from src.items import RustedIronMace, Shortsword
        from tests._combat_fixtures import make_adapter, make_player, seeded

        with patch("builtins.print"), \
                patch("src.api.combat_adapter.CombatStrategist"):
            player = make_player()
            sword, mace = Shortsword(), RustedIronMace()
            player.inventory += [sword, mace]
            player.equip_item(item_object=sword)
            with seeded():
                adapter = make_adapter(player, enemies=enemies)
        for e in player.combat_list:
            player.combat_proximity[e] = 3
            e.combat_proximity[player] = 3
        with patch("builtins.print"):
            ctx, _ = adapter._build_strategist_context(None)
        return player, ctx

    def test_preview_is_zero_on_the_stone_creature(self):
        """Guards the premise: if this ever stops being 0 the tests below
        prove nothing about harmless attacks."""
        from src.npc._enemies import CorruptedStoneCreature

        _, ctx = self._fight([CorruptedStoneCreature()])
        attack = next(m for m in ctx["available_moves"] if m["name"] == "Attack")
        [t] = attack["viable_targets"]
        assert t["damage_preview"]["max"] == 0

    def test_attack_is_aimed_at_the_slime_not_the_stone(self, strategist):
        from src.npc._enemies import CorruptedStoneCreature, Slime

        player, ctx = self._fight([CorruptedStoneCreature(), Slime()])
        stone_id = next(e["id"] for e in ctx["enemies"]
                        if "Stone" in e["name"])
        for s in strategist._get_fallback_suggestions(ctx, 3):
            if s["move_name"] == "Attack":
                assert s["target_id"] != stone_id

    def test_swap_weapon_leads_when_only_the_stone_is_left(self, strategist):
        from src.npc._enemies import CorruptedStoneCreature

        _, ctx = self._fight([CorruptedStoneCreature()])
        suggestions = strategist._get_fallback_suggestions(ctx, 3)
        assert suggestions[0]["move_name"] == "Swap Weapon", suggestions
        assert all(s["move_name"] != "Attack" for s in suggestions[:1])


# ---------------------------------------------------------------------------
# Scrub of #688: the harmless rule's reach.
# ---------------------------------------------------------------------------


class TestTheHarmlessRuleCoversEveryDamagingMove:
    def test_a_harmless_mastery_move_is_scored_down_too(self, strategist):
        # Mastery moves deal damage and carry previews like Offensive ones.
        mastery = _attack(_target(STONE, 0, 0), name="Whirlwind Mastery")
        mastery["category"] = "Mastery"
        score, reason = _scores(strategist, _ctx([mastery, TURN]))["Whirlwind Mastery"]
        assert score == 15
        assert "0" in reason

    def test_the_nearest_fallback_never_picks_a_target_it_just_ruled_out(
        self, strategist
    ):
        # No enemy records to rank by -> the nearest-viable-target fallback.
        # The nearest target is the harmless one; the pick must skip it.
        near_stone = dict(_target(STONE, 0, 0), distance=1)
        far_slime = dict(_target(SLIME, 20, 30), distance=4)
        suggestions = [{"move_name": "Attack", "score": 85, "target_id": "nobody"}]
        ctx = _ctx([_attack(near_stone, far_slime)], enemies=())
        strategist._ensure_target_ids(suggestions, ctx)
        assert suggestions[0]["target_id"] == "e_slime"


class _ScriptedLLM:
    """An available LLM client that proposes a fixed suggestion list."""

    def __init__(self, suggestions):
        self._suggestions = suggestions

    def available(self):
        return True

    def generate_structured(self, _system, _user):
        return {"suggestions": [dict(s) for s in self._suggestions]}


class TestTheLLMPathCannotRecommendAHarmlessAttack:
    def test_an_llm_attack_that_cannot_hurt_anyone_is_clamped(self):
        # The #688 score-down lived only on the heuristic path; with the LLM
        # on, its own 90 for a 0-damage Attack won the sort.
        llm = _ScriptedLLM([
            {"move_name": "Attack", "score": 90, "reasoning": "Hit it.", "target_id": "e_stone"},
            {"move_name": "Swap Weapon", "score": 40, "reasoning": "Maybe."},
        ])
        strategist = CombatStrategist(client=llm)
        ctx = _ctx([_attack(_target(STONE, 0, 0)), SWAP], enemies=(STONE,))
        top = strategist.get_suggestions(ctx, max_suggestions=2)
        by_name = {s["move_name"]: s for s in top}
        assert by_name["Attack"]["score"] == 15
        assert "0" in by_name["Attack"]["reasoning"]
        assert top[0]["move_name"] == "Swap Weapon"

    def test_the_llm_path_raises_swap_weapon_when_no_attack_can_hurt(self):
        # #688 asks the advisor to point at Swap Weapon when every attack is at
        # 0; on the LLM path the model may not propose it at all.
        from ai.combat_strategist import _SWAP_WHEN_HARMLESS_SCORE

        llm = _ScriptedLLM([
            {"move_name": "Attack", "score": 90, "reasoning": "Hit it.", "target_id": "e_stone"},
            {"move_name": "Rest", "score": 60, "reasoning": "Breathe."},
        ])
        strategist = CombatStrategist(client=llm)
        ctx = _ctx([_attack(_target(STONE, 0, 0)), REST, SWAP], enemies=(STONE,))
        top = strategist.get_suggestions(ctx, max_suggestions=1)
        assert top[0]["move_name"] == "Swap Weapon"
        assert top[0]["score"] == _SWAP_WHEN_HARMLESS_SCORE
