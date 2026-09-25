"""Tests for lint_qa_config.py: offline, against the real src/ tree."""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[5]
for p in (str(SCRIPTS), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import lint_qa_config as lint  # noqa: E402

KING_SLIME_LEG = """[game]
skipdialog = False
startmap = grondia
startposition = 7, 9
starting_story_flags = king_slime_defeated
starting_party_members = Gorran
starting_equipment = Shortsword:0, LeatherArmor:0
starting_items = Restorative, Antidote{extra}
"""


def write(tmp_path, text, name="config_qa_test.ini"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def statuses(results):
    return [status for status, _ in results]


def failures(results):
    return [msg for status, msg in results if status == "FAIL"]


# --- check 1: seeded flags vs. what their event grants ----------------------

def test_derived_flag_map_is_nonempty_and_knows_king_slime():
    cogrants = lint.derive_flag_cogrants()
    assert cogrants, "derivation found no flag writers in src/story at all"
    writers = cogrants["king_slime_defeated"]
    assert any(w["event"] == "AfterDefeatingKingSlime" and "MineralFragment" in w["items"]
               for w in writers)
    # The key is written as self.GATE_KEY, so this also proves class-attribute resolution.
    assert all(w["where"].startswith("src/story/ch02.py:") for w in writers)


def test_king_slime_without_fragment_fails(tmp_path):
    results = lint.lint(write(tmp_path, KING_SLIME_LEG.format(extra="")))
    fails = failures(results)
    assert len(fails) == 1
    assert "king_slime_defeated" in fails[0]
    assert "MineralFragment" in fails[0]
    assert "AfterKingSlimeReturn" in fails[0]  # the beat that waits for it
    assert "src/story/ch02.py:" in fails[0]


def test_king_slime_with_fragment_passes(tmp_path):
    results = lint.lint(write(tmp_path, KING_SLIME_LEG.format(extra=", MineralFragment")))
    assert failures(results) == []
    assert ("PASS", "flag 'king_slime_defeated': everything AfterDefeatingKingSlime grants is seeded") in results


def test_fragment_already_handed_over_is_not_a_fail(tmp_path):
    """Seeding Votha Krr's hand-over as done means the fragment was consumed."""
    text = KING_SLIME_LEG.format(extra="").replace(
        "king_slime_defeated", "king_slime_defeated, votha_krr_response_given")
    assert failures(lint.lint(write(tmp_path, text))) == []


def test_the_fail_depends_on_the_derivation(tmp_path, monkeypatch):
    """Mutation check: with an empty derived map the bad config slips through,
    so the FAIL above comes from the derivation, not from something hard-coded."""
    bad = write(tmp_path, KING_SLIME_LEG.format(extra=""))
    assert failures(lint.lint(bad))
    monkeypatch.setattr(lint, "derive_flag_cogrants", lambda: {})
    assert failures(lint.lint(bad)) == []


def test_flag_nothing_mentions_is_warned(tmp_path):
    text = KING_SLIME_LEG.format(extra=", MineralFragment").replace(
        "king_slime_defeated", "king_slime_defeated, no_such_flag_xyz")
    results = lint.lint(write(tmp_path, text))
    assert any(s == "WARN" and "no_such_flag_xyz" in m and "nothing in src/" in m for s, m in results)


# --- check 2: starting_exp across a level boundary ----------------------------

def test_exp_curve_matches_the_engine():
    from src.combatant import exp_needed_for_level
    from src.player import Player

    player = Player()
    first = player.exp_to_level
    second = first + exp_needed_for_level(2, player.intelligence)

    assert lint.simulate_start(first - 1, 1, "even")[1:] == (1, 0, False)
    boundary, level, pending, crossed = lint.simulate_start(first, 1, "even")
    assert (boundary, level, crossed) == (first, 2, True) and pending > 0
    assert lint.simulate_start(second - 1, 1, "even")[1] == 2
    assert lint.simulate_start(second, 1, "even")[1] == 3


def test_starting_exp_over_boundary_fails(tmp_path):
    text = KING_SLIME_LEG.format(extra=", MineralFragment") + "starting_exp = 8000\n"
    fails = failures(lint.lint(write(tmp_path, text)))
    assert len(fails) == 1 and "starting_exp 8000" in fails[0] and "LEVEL UP" in fails[0]


def test_starting_level_even_opens_no_modal(tmp_path):
    text = KING_SLIME_LEG.format(extra=", MineralFragment") + "starting_level = 4\n"
    assert failures(lint.lint(write(tmp_path, text))) == []


# --- check 3: skipdialog ---------------------------------------------------------

def test_skipdialog_fails(tmp_path):
    text = KING_SLIME_LEG.format(extra=", MineralFragment").replace(
        "skipdialog = False", "skipdialog = True")
    fails = failures(lint.lint(write(tmp_path, text)))
    assert len(fails) == 1 and "skipdialog" in fails[0]


# --- check 4: previous_tile-gated arrival on the start tile -------------------

def test_previous_tile_events_are_derived():
    scopes = lint.derive_story_scopes()
    assert scopes["GorranGestureEvent"].reads_previous_tile


def test_starting_on_a_previous_tile_gate_warns(tmp_path):
    gate = next(pos for pos, tile in lint._map_tiles("eastern-descent").items()
                if any(e.get("__class__") == "GorranGestureEvent" for e in tile.get("events", [])))
    text = ("[game]\nskipdialog = False\nstartmap = eastern-descent\n"
            f"startposition = {gate[0]}, {gate[1]}\nstarting_party_members = Gorran\n")
    results = lint.lint(write(tmp_path, text))
    assert any(s == "WARN" and "previous_tile" in m and "GorranGestureEvent" in m for s, m in results)
    # Seeded as already done, the event is retired and the warning goes away.
    seeded = lint.lint(write(tmp_path, text + "starting_story_flags = gorran_gesture_done\n", "b.ini"))
    assert not any("previous_tile" in m and "GorranGestureEvent" in m for _, m in seeded)


# --- a clean config, and the CLI --------------------------------------------------

def test_clean_config_passes(tmp_path, capsys):
    path = write(tmp_path, KING_SLIME_LEG.format(extra=", MineralFragment") + "starting_level = 3\n")
    assert set(statuses(lint.lint(path))) <= {"PASS", "INFO"}
    assert lint.main([str(path)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_cli_exits_nonzero_on_fail(tmp_path, capsys):
    assert lint.main([str(write(tmp_path, KING_SLIME_LEG.format(extra="")))]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_missing_start_tile_fails(tmp_path):
    text = KING_SLIME_LEG.format(extra=", MineralFragment").replace("7, 9", "99, 99")
    assert any("not a tile of grondia" in m for m in failures(lint.lint(write(tmp_path, text))))
