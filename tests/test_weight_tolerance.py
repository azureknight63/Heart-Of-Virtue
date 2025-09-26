import sys
import os
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
if os.path.join(repo_root, 'src') not in sys.path:
    sys.path.insert(0, os.path.join(repo_root, 'src'))

from src.player import Player
import src.functions as functions


def test_weight_tolerance_is_not_stacked_on_refresh():
    p = Player()
    # initial base
    base = p.weight_tolerance_base
    # call refresh twice
    functions.refresh_stat_bonuses(p)
    first = p.weight_tolerance
    functions.refresh_stat_bonuses(p)
    second = p.weight_tolerance
    # must not increase between refreshes
    assert first == second
    # also must equal base + attribute bonus
    expected = base + round((p.strength + p.endurance) / 2, 2)
    assert first == expected

