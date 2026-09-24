"""Prayer: the out-of-combat cure for Hollowed (issue #646).

Hollowed (``src/states.py``) is inflicted by the Lurker's SoulDrain and had no
active cure once ``items.Relic`` left Jean's starting kit. The maintainer's
call was a Pray action: the engine owns it (``Player.pray``), GameService
adapts it (``GameService.pray``), ``POST /api/pray`` exposes it, and the
COMMANDS panel offers it. These tests pin each layer against the real engine.
"""

from unittest.mock import patch

import pytest
from flask import Flask

import src.states as states
from src.api.services.game_service import GameService, _NOT_DURING_COMBAT_MESSAGE
from src.player import Player


def _hollowed_player():
    player = Player()
    player.healthy_faith = player.faith  # test-only marker, read back below
    hollowed = states.Hollowed(player)
    player.states.append(hollowed)
    hollowed.on_application(player)
    return player


def _is_hollowed(player):
    return any(isinstance(s, states.Hollowed) for s in player.states)


# ---------------------------------------------------------------------------
# Engine: Player.pray
# ---------------------------------------------------------------------------


class TestPlayerPray:
    def test_prayer_clears_hollowed_and_costs_the_named_fatigue(self):
        player = _hollowed_player()
        assert player.faith < player.healthy_faith
        cost = player.prayer_fatigue_cost()
        assert cost == max(1, int(player.maxfatigue * Player.PRAYER_FATIGUE_COST_PCT))
        before = player.fatigue

        outcome = player.pray()

        assert outcome["prayed"] is True
        assert outcome["cleared"] == ["Hollowed"]
        assert outcome["fatigue_cost"] == cost
        assert outcome["refusal"] is None
        assert not _is_hollowed(player)
        assert player.fatigue == before - cost
        # The stat penalty goes with the state, not just the list entry.
        assert player.faith == player.healthy_faith

    def test_prayer_narrates_through_the_sink(self):
        from src.narration import capture_narration

        player = _hollowed_player()
        with capture_narration() as msgs:
            player.pray()
        text = " ".join(m["text"] for m in msgs)
        assert "Jean" in text
        # Hollowed's own on_removal line runs, so the lift is visible.
        assert "hollowness" in text.lower()
        # Every number is explainable: the cost is said, not just deducted.
        assert f"{player.prayer_fatigue_cost()} fatigue" in text
        assert "Jerusalem" not in text

    def test_prayer_without_hollowed_is_free_and_changes_nothing(self):
        player = Player()
        before = player.fatigue

        outcome = player.pray()

        assert outcome == {
            "prayed": True, "cleared": [], "fatigue_cost": 0, "refusal": None,
        }
        assert player.fatigue == before

    def test_prayer_is_refused_without_enough_fatigue(self):
        player = _hollowed_player()
        cost = player.prayer_fatigue_cost()
        player.fatigue = cost - 1

        outcome = player.pray()

        assert outcome["prayed"] is False
        assert outcome["cleared"] == []
        assert outcome["fatigue_cost"] == 0
        assert str(cost) in outcome["refusal"]
        assert _is_hollowed(player)
        assert player.fatigue == cost - 1


# ---------------------------------------------------------------------------
# API adapter: GameService.pray
# ---------------------------------------------------------------------------


class TestGameServicePray:
    def test_success_returns_the_narration_and_the_new_fatigue(self):
        player = _hollowed_player()
        cost = player.prayer_fatigue_cost()
        full = player.fatigue

        result = GameService().pray(player)

        assert result["success"] is True
        assert result["cleared"] == ["Hollowed"]
        assert result["fatigue_cost"] == cost
        assert result["fatigue"] == full - cost
        assert result["max_fatigue"] == player.maxfatigue
        assert result["message"]
        assert result["messages"] and all(isinstance(m, str) for m in result["messages"])
        assert not _is_hollowed(player)

    def test_refused_mid_fight_with_the_shared_message(self):
        player = _hollowed_player()
        player.in_combat = True
        before = player.fatigue

        result = GameService().pray(player)

        assert result == {"success": False, "error": _NOT_DURING_COMBAT_MESSAGE}
        assert _is_hollowed(player)
        assert player.fatigue == before

    def test_refused_without_fatigue_surfaces_the_engine_refusal(self):
        player = _hollowed_player()
        player.fatigue = 0

        result = GameService().pray(player)

        assert result["success"] is False
        assert str(player.prayer_fatigue_cost()) in result["error"]
        assert _is_hollowed(player)


# ---------------------------------------------------------------------------
# Route: POST /api/pray
# ---------------------------------------------------------------------------


@pytest.fixture
def pray_app(make_stub_session, make_stub_session_manager):
    from src.api.routes.player import player_bp

    def _build(player):
        session = make_stub_session(session_id="sid_001")
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(player_bp, url_prefix="/api")
        app.session_manager = make_stub_session_manager(session, player)
        app.game_service = GameService()
        return app

    return _build


AUTH = {"Authorization": "Bearer sid_001"}


class TestPrayRoute:
    def test_success_returns_json_and_saves_the_session(self, pray_app):
        player = _hollowed_player()
        app = pray_app(player)

        rv = app.test_client().post("/api/pray", headers=AUTH)

        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert data["cleared"] == ["Hollowed"]
        assert isinstance(data["message"], str) and data["message"]
        assert data["fatigue"] == player.fatigue
        app.session_manager.save_session.assert_called_once_with("sid_001")

    def test_mid_fight_is_a_400_with_the_refusal(self, pray_app):
        player = _hollowed_player()
        player.in_combat = True
        app = pray_app(player)

        rv = app.test_client().post("/api/pray", headers=AUTH)

        assert rv.status_code == 400
        assert rv.get_json() == {"success": False, "error": _NOT_DURING_COMBAT_MESSAGE}
        app.session_manager.save_session.assert_not_called()

    def test_requires_auth(self, pray_app):
        rv = pray_app(Player()).test_client().post("/api/pray")
        assert rv.status_code == 401

    def test_an_unexpected_failure_is_a_500_without_detail(self, pray_app):
        app = pray_app(Player())
        with patch.object(GameService, "pray", side_effect=RuntimeError("boom")):
            rv = app.test_client().post("/api/pray", headers=AUTH)
        assert rv.status_code == 500
        assert "boom" not in rv.get_data(as_text=True)


# ---------------------------------------------------------------------------
# UI affordance: the command is advertised wherever COMMANDS is
# ---------------------------------------------------------------------------


def test_pray_is_advertised_in_the_tile_command_set():
    from unittest.mock import MagicMock

    from src.tiles import MapTile

    universe = MagicMock()
    universe.testing_mode = False
    tile = MapTile(universe, {"name": "m"}, 0, 0)

    names = [a.name for a in tile.available_actions(player=None)]

    assert "Pray" in names


def test_hollowed_tells_the_player_prayer_lifts_it():
    """The status tooltip is where a player learns how Hollowed ends."""
    player = Player()
    hollowed = states.Hollowed(player)
    assert "pray" in hollowed.description.lower()
    assert "pray" in (states.Hollowed.__doc__ or "").lower()


def _every_engine_state(player):
    """One instance of every concrete ``State`` in ``src/states.py``.

    Extra required constructor arguments (``StoneBulwarkState``'s ``amount``)
    get a placeholder 1, so no class is skipped.
    """
    import inspect

    out = []
    for _name, cls in inspect.getmembers(states, inspect.isclass):
        if not issubclass(cls, states.State) or cls is states.State:
            continue
        if cls.__module__ != states.__name__:
            continue
        params = list(inspect.signature(cls.__init__).parameters.values())[2:]
        extra = [1 for p in params if p.default is inspect.Parameter.empty]
        out.append(cls(player, *extra))
    return out


def test_only_states_prayer_cures_tell_the_player_to_pray():
    """A tooltip that says "pray to lift it" on a state prayer cannot lift is
    a lie the player acts on (Fervent claimed it; prayer lifts apathy only)."""
    player = Player()
    all_states = _every_engine_state(player)
    mentions = [
        s for s in all_states if "pray" in (getattr(s, "description", "") or "").lower()
    ]
    assert any(isinstance(s, states.Hollowed) for s in mentions)  # non-vacuous
    wrong = [
        type(s).__name__ for s in mentions
        if not player._prayer_cures(s)
    ]
    assert not wrong, wrong


def test_apathy_statustype_is_one_constant():
    """Hollowed declares the statustype prayer lifts."""
    assert states.Hollowed(Player()).statustype == states.APATHY_STATUSTYPE
    assert Player()._prayer_cures(states.Hollowed(Player()))


def test_the_oath_lock_and_prayer_share_one_apathy_rule(monkeypatch):
    """Both sites ask ``states.is_apathy`` rather than restating the match:
    change the rule once and both follow it (round-2 scrub). Checked by
    behaviour, not by grepping the source for a spelling."""
    from src.moves._base import UnavailableReason
    from src.moves._utility import CrusaderOath

    player = Player()
    player.in_combat = True
    marker = type("Marker", (), {"statustype": "other"})()  # the real rule says no
    player.states = [marker]
    player.faith = 99
    oath = CrusaderOath(player)
    assert states.is_apathy(marker) is False
    assert player._prayer_cures(marker) is False
    assert oath.viable() is True  # non-vacuous: nothing else locks the Oath

    monkeypatch.setattr(states, "is_apathy", lambda state: state is marker)
    assert player._prayer_cures(marker) is True
    assert oath._unavailability_code() is UnavailableReason.APATHY
    assert oath.viable() is False


def test_a_raising_on_removal_does_not_abort_a_paid_prayer():
    """Fatigue is spent before the states come off; one state's broken
    teardown must not strand the others or lose the outcome."""
    player = _hollowed_player()

    class _Broken(states.Hollowed):
        def on_removal(self, target):
            raise RuntimeError("teardown bug")

    broken = _Broken(player)
    player.states.insert(0, broken)
    before = player.fatigue
    cost = player.prayer_fatigue_cost()

    outcome = player.pray()

    assert outcome["prayed"] is True
    assert outcome["cleared"] == ["Hollowed", "Hollowed"]
    assert player.fatigue == before - cost
    assert not _is_hollowed(player)
    assert player.faith == player.healthy_faith


def test_fervent_still_says_it_fades():
    """Dropping the prayer claim from Fervent's tooltip must not drop the true
    half: it runs out on its own (``beats_max``)."""
    fervent = states.Fervent(Player())
    assert fervent.beats_max > 0
    assert "fades with time" in fervent.description.lower()
