"""Every branch of a multi-target damage loop must publish an outcome.

``src/moves/_base.publish_outcome`` states the rule in prose: *outcomes are per
target, not per swing* — one publication per resolution, immediately before the
line that narrates it. The rule is easy to state and easy to forget, because
forgetting it is silent. A loop that damages four enemies and publishes nothing
does not raise, does not fail a unit test and does not look wrong; the beat
simply falls through to the adapter's end-of-move fallback and the player sees
one animation with no per-target impact. Blood of Martyrs shipped that way.

So this is a **structural** guard rather than another behavioural test. It
parses every ``src/moves`` submodule, finds the loops that reduce somebody's
HP, enumerates the branches through each one, and fails when a branch that
deals damage or narrates a resolution reaches no publication. A new area move
is covered the day it lands, by nobody having to remember this file exists —
the same reason ``tests/test_facing_damage_hand_rolled_attacks.py`` globs its
module list instead of naming one.

Deliberately not an enumeration of known moves: CLAUDE.md records that every
opt-in guard in this repo has certified exactly the gap it was written to close
and nothing else, which reads as coverage while being none.
"""

import ast
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import src.moves as _moves_pkg  # noqa: E402


def _move_module_paths():
    """Every ``src/moves`` submodule, globbed rather than listed."""
    package_dir = pathlib.Path(_moves_pkg.__file__).parent
    return tuple(
        path for path in sorted(package_dir.glob("*.py")) if path.stem != "__init__"
    )


MOVE_MODULE_PATHS = _move_module_paths()

#: Calls that publish an outcome. ``publish_outcome`` is the direct form;
#: ``Move.hit``/``miss``/``parry`` and ``resolve_strike_outcome`` each publish
#: one internally, so a loop that routes through a shared pipeline is compliant
#: without naming the helper. Every shared resolver has to appear here *and* in
#: the damage signals below -- a resolver listed only as a publisher would make
#: the loops that use it invisible to the scan, which is the failure mode where
#: the guard reports green because it stopped looking.
_PUBLISH_CALLS = frozenset(
    {"publish_outcome", "hit", "miss", "parry", "resolve_strike_outcome"}
)

#: Calls that narrate a *resolution* — the line an outcome is supposed to ride
#: in front of. A branch that says something happened to an enemy but publishes
#: nothing is the exact shape of the bug: the adapter pairs each publication
#: with the next narration line, so an unpaired line is attributed to whatever
#: was published last, i.e. to the previous enemy.
_NARRATE_CALLS = frozenset({"cprint", "narrate", "print"})


def _call_names(node):
    """Every callable name reached from ``node``, attribute or bare."""
    names = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _writes_hp(node):
    """True when ``node`` reduces somebody's ``hp`` or calls ``Move.hit``.

    Four spellings, because the package genuinely uses four: ``x.hp -= n``,
    ``x.hp = max(0, ...)``, ``self.hit(damage, glance)`` and the shared
    ``resolve_strike_outcome`` (which applies the HP itself). A signal list that
    is too narrow fails in the safe-looking direction — it certifies the loops
    it cannot see — which is how the sibling facing guard shipped blind to four
    area moves.
    """
    for child in ast.walk(node):
        if isinstance(child, ast.AugAssign):
            if isinstance(child.target, ast.Attribute) and child.target.attr == "hp":
                return True
        elif isinstance(child, ast.Assign):
            if any(
                isinstance(t, ast.Attribute) and t.attr == "hp" for t in child.targets
            ):
                return True
        elif isinstance(child, ast.Call):
            func = child.func
            named = getattr(func, "id", None) or getattr(func, "attr", None)
            if named in ("hit", "resolve_strike_outcome"):
                return True
    return False


_TERMINATORS = (ast.Continue, ast.Break, ast.Return, ast.Raise)


def _paths(statements):
    """Every straight-line branch through ``statements``, as a node list.

    Splits at each ``if`` (both arms, including an absent ``else``), inlines a
    nested loop's body, and follows a ``try``'s happy path. A branch that ends
    in ``continue``/``break``/``return``/``raise`` stops there rather than
    concatenating the statements that follow it — that is what keeps a range
    filter (``if dist > arc_range: continue``) from reading as a resolution
    branch that forgot to publish.

    Exception handlers are skipped on purpose: they are error recovery, not a
    combat resolution, and requiring a publication inside one would push moves
    to report an outcome for a swing that never resolved.
    """
    if not statements:
        return [[]]
    head, rest = statements[0], statements[1:]

    if isinstance(head, ast.If):
        branches = [head.body, head.orelse]
    elif isinstance(head, (ast.For, ast.While)):
        branches = [head.body]
    elif isinstance(head, (ast.Try, ast.TryStar) if hasattr(ast, "TryStar") else (ast.Try,)):
        branches = [head.body + head.orelse + head.finalbody]
    elif isinstance(head, ast.With):
        branches = [head.body]
    else:
        branches = None

    if branches is None:
        prefixes = [[head]]
    else:
        prefixes = []
        for branch in branches:
            for sub in _paths(branch):
                prefixes.append([head.test] if isinstance(head, ast.If) else [])
                prefixes[-1] = prefixes[-1] + sub

    paths = []
    for prefix in prefixes:
        if any(isinstance(node, _TERMINATORS) for node in prefix):
            paths.append(prefix)
            continue
        for tail in _paths(rest):
            paths.append(prefix + tail)
    return paths


def _damage_loops():
    """``(module, qualified name, loop node)`` for every HP-reducing loop.

    Scans *every* function in the package rather than only ``execute``: a
    damage loop extracted into a helper is the same contract, and a guard that
    only looked at ``execute`` would hand anyone a one-line way around it.
    """
    loops = []
    for path in MOVE_MODULE_PATHS:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        stack = [(tree, "")]
        while stack:
            node, prefix = stack.pop()
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    stack.append((child, f"{prefix}{child.name}."))
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = f"{prefix}{child.name}"
                    for inner in ast.walk(child):
                        if isinstance(inner, (ast.For, ast.While)) and _writes_hp(
                            inner
                        ):
                            loops.append((path.name, name, inner))
                else:
                    stack.append((child, prefix))
    return loops


DAMAGE_LOOPS = _damage_loops()


def test_the_scan_actually_finds_the_multi_target_loops():
    """A structural guard that silently matches nothing is worse than none.

    These are the loops that exist today across four different shapes: a
    per-enemy arc, a full-circle spin, a per-strike flurry against one target,
    and the map-wide detonation this guard was written after.
    """
    found = {f"{module}:{name}" for module, name, _ in DAMAGE_LOOPS}
    for expected in (
        "_polearm.py:Sweep.execute",
        "_polearm.py:HalberdSpin.execute",
        "_scythe.py:Reap.execute",
        "_pick.py:ChipAway.execute",
        "_sword.py:WhirlAttack.execute",
        "_npc.py:SeismicSlam.execute",
        "_mastery.py:BloodOfMartyrs.execute",
        "_mastery.py:LightningAssault.execute",
    ):
        assert expected in found, f"{expected} vanished from the scan: {sorted(found)}"


@pytest.mark.parametrize(
    "module, name, loop",
    [(m, n, loop) for m, n, loop in DAMAGE_LOOPS],
    ids=[f"{m}:{n}@{loop.lineno}" for m, n, loop in DAMAGE_LOOPS],
)
def test_every_branch_of_a_damage_loop_publishes_an_outcome(module, name, loop):
    """No branch of a damage loop may resolve against a combatant in silence.

    "Resolve" means one of two things, and both count: the branch reduces HP,
    or it narrates a line about what happened. Either one is a resolution the
    client has to be told about; a branch that does one without publishing is
    a target that never flashes (damage with no publication) or a line
    attributed to the previous enemy (narration with no publication).
    """
    offenders = []
    for path in _paths(loop.body):
        published = set()
        damaged = False
        narrated = set()
        for node in path:
            names = _call_names(node)
            published |= names & _PUBLISH_CALLS
            narrated |= names & _NARRATE_CALLS
            damaged = damaged or _writes_hp(node)
        if (damaged or narrated) and not published:
            offenders.append(
                "damage" if damaged else "narration " + ", ".join(sorted(narrated))
            )
    assert not offenders, (
        f"{module}:{name} (loop at line {loop.lineno}) has "
        f"{len(offenders)} branch(es) that resolve against a combatant without "
        f"publishing an outcome: {offenders}. Publish one per target, "
        "immediately before that target's own narration line -- see "
        "src/moves/_base.publish_outcome."
    )
