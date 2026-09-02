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

from tests._moves_scan import (  # noqa: E402
    move_module_paths,
    writes_hp as _writes_hp,
)

MOVE_MODULE_PATHS = move_module_paths()

#: Calls that publish an outcome. ``publish_outcome`` is the direct form;
#: ``Move.hit``/``miss``/``parry``, ``resolve_strike_outcome`` and
#: ``resolve_pipeline_strike`` each publish one internally, so a loop that
#: routes through a shared pipeline is compliant without naming the helper.
#: Every shared resolver has to appear here *and* in
#: ``tests/_moves_scan.DAMAGE_SIGNALS``/``writes_hp`` -- a resolver listed
#: only as a publisher would make the loops that use it invisible to the
#: scan, which is the failure mode where the guard reports green because it
#: stopped looking.
_PUBLISH_CALLS = frozenset(
    {
        "publish_outcome",
        "hit",
        "miss",
        "parry",
        "resolve_strike_outcome",
        "resolve_pipeline_strike",
    }
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


# ``_writes_hp`` is the shared ``tests/_moves_scan.writes_hp`` (imported
# above): the AST twin of ``DAMAGE_SIGNALS``, with the shared resolvers named
# once. A signal list that is too narrow fails in the safe-looking direction
# — it certifies the loops it cannot see — which is how the sibling facing
# guard shipped blind to four area moves.


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

    The tail expansion ``_paths(rest)`` is computed once and shared across
    every non-terminated prefix — the earlier version recomputed it inside
    the prefix loop, re-expanding the exponential suffix tree once per
    branch of every head.
    """
    if not statements:
        return [[]]
    head, rest = statements[0], statements[1:]

    if isinstance(head, ast.If):
        branches = [head.body, head.orelse]
        prefix_head = [head.test]
    elif isinstance(head, (ast.For, ast.While)):
        branches = [head.body]
        prefix_head = []
    elif isinstance(head, (ast.Try, ast.TryStar) if hasattr(ast, "TryStar") else (ast.Try,)):
        branches = [head.body + head.orelse + head.finalbody]
        prefix_head = []
    elif isinstance(head, ast.With):
        branches = [head.body]
        prefix_head = []
    else:
        branches = None
        prefix_head = []

    if branches is None:
        prefixes = [[head]]
    else:
        prefixes = [
            prefix_head + sub for branch in branches for sub in _paths(branch)
        ]

    tails = None
    paths = []
    for prefix in prefixes:
        if any(isinstance(node, _TERMINATORS) for node in prefix):
            paths.append(prefix)
            continue
        if tails is None:
            tails = _paths(rest)
        for tail in tails:
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


def _loop_variable_names(loop):
    """The names bound by a ``for`` loop's target (``enemy``, or every name
    in a tuple target like ``enemy, distance``). Empty for ``while``."""
    names = set()
    if isinstance(loop, ast.For):
        for node in ast.walk(loop.target):
            if isinstance(node, ast.Name):
                names.add(node.id)
    return names


def _iterates_combatants(loop):
    """False for a per-strike counter loop (``for _ in range(...)``): its
    loop variable is a strike index, not the combatant being resolved, so
    the target-attribution rule below does not apply to it."""
    if not isinstance(loop, ast.For):
        return False
    it = loop.iter
    if isinstance(it, ast.Call):
        named = getattr(it.func, "id", None) or getattr(it.func, "attr", None)
        if named == "range":
            return False
    return True


def _explicit_publish_target(name, call):
    """The explicit target argument of a publishing call, or None when the
    call attributes implicitly (``hit``/``miss``/``parry``/
    ``resolve_pipeline_strike`` resolve against ``move.target``)."""
    if name == "publish_outcome":
        if len(call.args) >= 3:
            return call.args[2]
        for kw in call.keywords:
            if kw.arg == "target":
                return kw.value
    if name == "resolve_strike_outcome" and len(call.args) >= 2:
        return call.args[1]
    return None


def _branch_offences(loop):
    """Every rule violation across the branches of one damage loop.

    Three rules, in the order they were learned:

    * **Publish at all.** A branch that reduces HP or narrates a resolution
      and publishes nothing falls through to the adapter's end-of-move
      fallback (the Blood of Martyrs shipping bug).
    * **Publish first.** The adapter pairs each publication with the *next*
      narration line, so a line narrated before its branch's first
      publication is attributed to the previous enemy.
    * **Publish against the enemy in hand.** In a loop over combatants, a
      publishing call that names an explicit target must name the loop
      variable — publishing ``self.target`` from inside a per-enemy loop
      reattributes every resolution to whatever the move's committed target
      happens to be.
    """
    offences = []
    loop_names = _loop_variable_names(loop)
    combatant_loop = _iterates_combatants(loop) and loop_names
    for path in _paths(loop.body):
        published = set()
        first_publish = None
        first_narrate = None
        damaged = False
        narrated = set()
        misattributed = []
        for index, node in enumerate(path):
            names = _call_names(node)
            hits = names & _PUBLISH_CALLS
            if hits and first_publish is None:
                first_publish = index
            published |= hits
            if names & _NARRATE_CALLS and first_narrate is None:
                first_narrate = index
            narrated |= names & _NARRATE_CALLS
            damaged = damaged or _writes_hp(node)
            if combatant_loop:
                for child in ast.walk(node):
                    if not isinstance(child, ast.Call):
                        continue
                    called = getattr(child.func, "id", None) or getattr(
                        child.func, "attr", None
                    )
                    if called not in _PUBLISH_CALLS:
                        continue
                    target_arg = _explicit_publish_target(called, child)
                    if target_arg is None:
                        continue
                    arg_names = {
                        n.id
                        for n in ast.walk(target_arg)
                        if isinstance(n, ast.Name)
                    }
                    if not (arg_names & loop_names):
                        misattributed.append(ast.dump(target_arg))
        if (damaged or narrated) and not published:
            offences.append(
                "silent resolution: "
                + (
                    "damage"
                    if damaged
                    else "narration " + ", ".join(sorted(narrated))
                )
            )
        elif (
            published
            and first_narrate is not None
            and (first_publish is None or first_narrate < first_publish)
        ):
            offences.append(
                "narrates before publishing -- the line is attributed to "
                "the previous enemy"
            )
        offences.extend(
            f"publishes against a fixed target inside a per-enemy loop: {arg}"
            for arg in misattributed
        )
    return offences


def test_the_scan_actually_finds_the_multi_target_loops():
    """A structural guard that silently matches nothing is worse than none.

    A count floor plus two stable anchors, rather than an exact-name
    enumeration: the old eight-string list broke on every refactor that
    moved a loop between helpers, and each fix re-encoded the package's
    private structure here. The anchors are the two loops least likely to
    ever stop being loops -- the map-wide detonation this guard was written
    after, and one arc swing.
    """
    found = {f"{module}:{name}" for module, name, _ in DAMAGE_LOOPS}
    assert len(found) >= 8, sorted(found)
    for anchor in (
        "_mastery.py:BloodOfMartyrs.execute",
        "_scythe.py:Reap.execute",
    ):
        assert anchor in found, f"{anchor} vanished from the scan: {sorted(found)}"


@pytest.mark.parametrize(
    "module, name, loop",
    [(m, n, loop) for m, n, loop in DAMAGE_LOOPS],
    ids=[f"{m}:{n}@{loop.lineno}" for m, n, loop in DAMAGE_LOOPS],
)
def test_every_branch_of_a_damage_loop_publishes_an_outcome(module, name, loop):
    """No branch of a damage loop may resolve against a combatant in silence,
    after its narration, or against the wrong combatant — see
    ``_branch_offences`` for the three rules and their reasons.
    """
    offences = _branch_offences(loop)
    assert not offences, (
        f"{module}:{name} (loop at line {loop.lineno}) has "
        f"{len(offences)} offending branch(es): {offences}. Publish one "
        "outcome per target, immediately before that target's own narration "
        "line -- see src/moves/_base.publish_outcome."
    )


# ---------------------------------------------------------------------------
# Positive controls: the walker must actually flag the shapes it exists for
# ---------------------------------------------------------------------------


def _loop_of(snippet):
    tree = ast.parse(snippet)
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            return node
    raise AssertionError("control snippet contains no loop")


class TestTheWalkerCatchesWhatItExistsToCatch:
    """A structural guard with no positive control can go inert without a
    single failure -- these are the exact bug shapes, synthesised."""

    def test_flags_a_damage_loop_that_never_publishes(self):
        loop = _loop_of(
            "for enemy in enemies:\n"
            "    enemy.hp -= 5\n"
            "    cprint(f'{enemy.name} is struck!')\n"
        )
        offences = _branch_offences(loop)
        assert offences and "silent resolution" in offences[0], offences

    def test_does_not_flag_the_publishing_version(self):
        loop = _loop_of(
            "for enemy in enemies:\n"
            "    publish_outcome(self.user, 'hit', enemy)\n"
            "    cprint(f'{enemy.name} is struck!')\n"
            "    enemy.hp -= 5\n"
        )
        assert _branch_offences(loop) == []

    def test_flags_narration_that_precedes_the_publication(self):
        loop = _loop_of(
            "for enemy in enemies:\n"
            "    cprint(f'{enemy.name} is struck!')\n"
            "    publish_outcome(self.user, 'hit', enemy)\n"
            "    enemy.hp -= 5\n"
        )
        offences = _branch_offences(loop)
        assert offences and "narrates before publishing" in offences[0], offences

    def test_flags_a_publish_against_a_fixed_target_in_an_enemies_loop(self):
        loop = _loop_of(
            "for enemy in enemies:\n"
            "    publish_outcome(self.user, 'hit', self.target)\n"
            "    cprint(f'{enemy.name} is struck!')\n"
            "    enemy.hp -= 5\n"
        )
        offences = _branch_offences(loop)
        assert offences and "fixed target" in offences[0], offences

    def test_a_per_strike_counter_loop_may_publish_the_committed_target(self):
        """Chip Away's shape: the loop variable is a strike index, so
        ``self.target`` is exactly right there."""
        loop = _loop_of(
            "for i in range(3):\n"
            "    resolve_strike_outcome(self, self.target, damage, chance,\n"
            "                           hit_line='h', parry_line='p',\n"
            "                           miss_line='m')\n"
        )
        assert _branch_offences(loop) == []

    def test_a_range_filter_continue_is_not_a_silent_branch(self):
        loop = _loop_of(
            "for enemy in enemies:\n"
            "    if distance > arc_range:\n"
            "        continue\n"
            "    publish_outcome(self.user, 'hit', enemy)\n"
            "    cprint('struck')\n"
            "    enemy.hp -= 5\n"
        )
        assert _branch_offences(loop) == []
