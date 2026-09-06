"""
Shared base class for all combat participants (Player, NPC).

Provides:
  - _init_resistances(): initialises resistance and status-resistance dicts from
    a single canonical definition so the values never drift between classes.
  - is_alive(), cycle_states(), get_equipped_items(): methods whose logic is
    identical across Player and NPC.
  - exp_needed_for_level(): the single leveling curve shared by the Player and
    ally NPC progression.
  - the ``_pending_animation`` channel's attribute and key names, single-sourced
    for the engine (src/moves/_base.py) and the API (src/api/combat_adapter.py)
    that share the channel — see the comment block below.
  - wire_handle()/find_by_handle()/index_by_handle(): the opaque per-object
    identity the API gives the client for ANY entity it names, and the lookups
    that resolve one back. ``wire_handle``'s docstring carries the ONE list of
    what gets a handle — see it rather than restating the list here, and
    ``grep -rn "wire_handle(" src/`` for the live call sites. It lives here
    rather than in src/api/ because the combat half (issue #511) predates the
    rest (issue #518) and the engine-side attribute it mints hangs off
    Combatant; nothing in the engine reads it.

Usage (in each subclass __init__):
    self._init_resistances()
"""


import math
import uuid
import weakref

# Move stages, in the order Move.advance walks them. 0/1 are "not resolved
# yet" (the move's effect is still coming); 2/3 are aftermath.
MOVE_STAGE_PREP = 0
MOVE_STAGE_EXECUTE = 1
MOVE_STAGE_RECOIL = 2
MOVE_STAGE_COOLDOWN = 3

#: ── The ``_pending_animation`` channel's names, single-sourced ──────────────
#:
#: ``entity._pending_animation`` is the per-combatant animation channel: a dict
#: the API adapter arms at cast time, the engine publishes resolutions into,
#: and ``Combatant.__getstate__`` below strips at pickle time. Its attribute
#: name and its two engine-written keys are therefore MIRRORED across the
#: engine/API boundary -- ``src.moves._base.publish_outcome`` writes ``outcome``
#: and ``outcome_target``; ``src.api.combat_adapter`` arms, snapshots, emits and
#: deletes the dict. Spelled as bare literals on both sides, a rename or a typo
#: on either one is silent: the channel simply stops resolving, with no error
#: and no failing test. Naming them once here removes that failure mode.
#:
#: This module is the home rather than ``src/moves/_base.py`` because
#: ``moves/_base`` already imports this module -- defining them there and
#: importing them back would be an import cycle. Both sides of the boundary
#: already import ``src.combatant``, and ``Combatant`` is what the attribute
#: actually hangs off.
#:
#: The channel's full lifecycle -- every writer, all three deletion points, and
#: what each key means -- is documented in one block in
#: ``src/api/combat_adapter.py``. Nothing in the engine reads
#: ``REPORTED_BEAT_KEY`` (it is adapter bookkeeping), but it is minted here too
#: so the channel's whole key vocabulary has a single home.
PENDING_ANIMATION_ATTR = "_pending_animation"
OUTCOME_KEY = "outcome"
OUTCOME_TARGET_KEY = "outcome_target"
REPORTED_BEAT_KEY = "_reported_beat"

#: ── The entity wire handle ────────────────────────────────────────
#:
#: Every combatant carries an opaque, stable identity token used as its wire id
#: by ``CombatantSerializer.stream_id`` (``player`` / ``ally_<handle>`` /
#: ``enemy_<handle>``). The scheme used to interpolate ``id(combatant)`` --
#: CPython's heap address -- which was wrong twice over (issue #511):
#:
#:   1. it shipped raw process addresses to the client in every combat poll,
#:      log line and socket emission, and
#:   2. ``id()`` values are RECYCLED. A combatant that dies leaves
#:      ``combat_list`` and can be freed, so a later-spawned NPC can inherit its
#:      address -- and every client-held reference to the dead one
#:      (``last_move_target_id``, animation ``target_id``s, death-chain
#:      bookkeeping) then silently points at a different combatant. The same
#:      recycling hazard had already been found and fixed *inside* the adapter
#:      during #506, where an "already announced" set held ``id(enemy)`` and so
#:      skipped a reinforcement that reused a dead enemy's address.
#:
#: ``uuid4`` rather than a per-combat counter: combatants outlive the process
#: they were minted in (allies and the player are pickled into saves), so a
#: counter would have to be persisted and restored globally or a loaded
#: combatant and a freshly spawned one would collide on the same small integer
#: -- exactly the aliasing this replaces. A uuid needs no coordination, no
#: global mutable state, and is unique across processes and saves by
#: construction. It also carries no ordering or population information.
#:
#: Issue #518 widened the scheme past combat: the room, inventory, shop and
#: event payloads minted their wire ids the same discarded way
#: (``str(id(entity))``), so the *same* Slime shipped as ``enemy_<handle>`` on
#: the combat wire and as a heap address in ``get_current_room``. There is now
#: ONE handle per object (``wire_handle``, whose docstring carries the one list
#: of which kinds of object those are) and the attribute name is kept spelled
#: ``_combat_handle`` so handles already persisted in saves written since #511
#: survive the widening.
COMBAT_HANDLE_ATTR = "_combat_handle"

#: Handles for entities that cannot hold an attribute of their own (spec'd test
#: doubles and class objects, mostly). Keyed by the object itself and weak, so
#: an entry dies with the entity it names -- unlike an ``id()``-keyed cache,
#: which is the very recycling hazard this module closes.
_FALLBACK_HANDLES = weakref.WeakKeyDictionary()


def _side_table_handle(entity, handle=None):
    """Mint into the weak side table, for an entity that cannot hold its own.

    Last resort: an object that has no usable instance dict and refuses
    ``setattr`` (or, for a class, must not be *allowed* to hold one -- see
    ``wire_handle``). ``setdefault`` is atomic under the GIL here too, so two
    threads racing still agree on one handle.
    """
    if handle is None:
        handle = uuid.uuid4().hex
    try:
        return _FALLBACK_HANDLES.setdefault(entity, handle)
    except TypeError:
        # Neither settable nor weak-referenceable: nothing left to hang the
        # handle on. Unreachable for real engine entities; better an unstable
        # id than an exception out of a serializer.
        return handle


def wire_handle(entity):
    """Return ``entity``'s stable opaque handle, minting one if needed.

    THE list of what gets a handle lives here and nowhere else. Every other
    mention of it in this repo points at this docstring rather than restating
    it, because a hand-maintained enumeration drifts silently -- CLAUDE.md
    records exactly that failure for ``to_hit_chance``, whose docstring list
    was wrong twice before being deleted in favour of a grep. The kinds are:
    **combatants, room NPCs, floor items, inventory rows, container contents,
    world objects, merchants, shop stock, buyback ledger entries and events.**
    For the live call sites rather than this prose,
    ``grep -rn "wire_handle(" src/``.

    Events are the one kind whose handle is *not* what the API resolves a
    client-supplied id through -- ``process_event_input`` matches
    ``api_event_id`` instead, and the handle serves the client's event dedupe.
    ``src/api/serializers/event_serializer.py`` documents why.

    All of them share this one function and one handle
    per object, deliberately (issue #518): a Slime standing in
    ``tile.npcs_here`` is the *same instance* the fight puts in
    ``combat_list``, so giving it a second, room-scoped id would mean the
    client holds two names for one entity and every cross-reference between
    them (attacking the NPC you are looking at) needs a translation table.
    The combat wire id is this handle plus a side prefix
    (``CombatantSerializer.stream_id``); nothing else decorates it.

    Minting is lazy rather than done in each subclass ``__init__`` so there is
    exactly ONE code path: a combatant restored from a save written before
    #511 has no handle, and takes the same branch a freshly spawned one takes
    the first time its identity is asked for. An eager mint would leave the
    lazy path as a rarely-exercised special case for old saves.

    The handle is a plain ``str`` in ``__dict__``, so it pickles with the rest
    of the entity (``Combatant.__getstate__`` strips only the transient
    animation channel) and survives a save/load round trip. Nothing in the
    engine reads it -- it exists solely as the API's entity identity.

    The mint goes through ``__dict__.setdefault`` rather than ``setattr``
    because it is racy otherwise: the combat poll and the socket beat emitter
    run on different threads, and two threads that both find no handle would
    each mint one, the second ``setattr`` silently overwriting the id the
    first had already shipped to the client -- leaving the client holding an
    id that resolves to nobody. ``dict.setdefault`` is atomic under the GIL,
    so the first writer wins and every caller sees that same handle.

    The *read* goes through the instance dict for the same reason it must not
    go through ``getattr``: attribute lookup resolves through the CLASS, so an
    entity whose class carries ``_combat_handle`` would report the class's
    handle as its own and every instance of that class would answer to one
    wire id -- see the ``isinstance(entity, type)`` branch below for how a
    class comes to carry one.
    """
    if isinstance(entity, dict):
        # ``ObjectSerializer`` also accepts a plain mapping as a world object,
        # and a buyback ledger entry is a dict too. A mapping has no instance
        # dict and is not weak-referenceable, so the branches below would
        # remint on every call -- an id that changes between two polls is
        # worse than the address it replaced. Mint into the mapping itself
        # instead; ``setdefault`` is atomic here too.
        existing = entity.get(COMBAT_HANDLE_ATTR)
        if isinstance(existing, str) and existing:
            return existing
        return entity.setdefault(COMBAT_HANDLE_ATTR, uuid.uuid4().hex)

    if isinstance(entity, type):
        # A class is not an instance, and must never be stamped: its
        # ``__dict__`` is a read-only ``mappingproxy``, so the instance branch
        # below cannot mint into it and would fall through to ``setattr`` --
        # putting the handle on the CLASS. After that every instance of that
        # class with no own handle resolves *through* the class to that one
        # id, so a single wire id would name every Slime in the game. That is
        # precisely the aliasing #511/#518 exist to remove, and it would be
        # silent. Classes do reach a serializer in principle:
        # ``Universe._deserialize_saved_instance`` returns bare class objects
        # for ``__class_type__`` markers. Give the class its own handle in the
        # weak side table, where nothing can inherit it.
        return _side_table_handle(entity)

    own = getattr(entity, "__dict__", None)
    if isinstance(own, dict):
        existing = own.get(COMBAT_HANDLE_ATTR)
        if isinstance(existing, str) and existing:
            return existing
        return own.setdefault(COMBAT_HANDLE_ATTR, uuid.uuid4().hex)

    # No usable instance dict (``__slots__``): read and write through the
    # attribute protocol instead. A slot and a class attribute of the same
    # name cannot coexist, and nothing stamps classes any more, so the
    # class-inheritance hazard above does not apply on this path.
    existing = getattr(entity, COMBAT_HANDLE_ATTR, None)
    if isinstance(existing, str) and existing:
        return existing
    handle = uuid.uuid4().hex
    try:
        setattr(entity, COMBAT_HANDLE_ATTR, handle)
        return handle
    except (AttributeError, TypeError):
        pass
    return _side_table_handle(entity, handle)


#: Combat-facing spelling of :func:`wire_handle`, kept as the name issue #511
#: introduced and the combat serializer/adapter import. It is an alias, not a
#: parallel scheme: one entity has exactly one handle whichever name mints it.
combatant_handle = wire_handle


def index_by_handle(entities, handle):
    """Return ``(entity, index)`` for the first handle match, else ``(None, None)``.

    The positional twin of :func:`find_by_handle`, for the callers that need
    the row number as well as the object (the inventory routes address items
    by index too). It exists so those callers do not re-inline the comparison
    just to keep the index, and so recovering the index afterwards with
    ``list.index()`` -- which compares by equality, not identity, and would
    silently return the wrong row for a stacked duplicate the day an ``Item``
    defines ``__eq__`` -- is never necessary.

    Scanning mints a handle for each candidate it passes. That is deliberate
    and harmless: the mint is idempotent, and every entity reachable from a
    lookup is one the matching serializer would have minted for anyway.

    A falsy ``handle`` matches nothing -- an absent id must not resolve to the
    first entity in the room.
    """
    if not handle:
        return None, None
    for index, entity in enumerate(entities or ()):
        if wire_handle(entity) == handle:
            return entity, index
    return None, None


def find_by_handle(entities, handle):
    """Return the first entity in ``entities`` whose wire handle is ``handle``.

    The inverse of :func:`wire_handle`, and the way the API turns a
    client-supplied id back into an object. It is written once here, rather
    than re-inlined at each lookup, because the lookup is the half of the
    scheme that silently breaks: a site left comparing ``id(entity)`` after
    the mint moved to handles does not raise, it just answers "not found" --
    which is how the serializer half of this change, applied on its own, broke
    every room interaction.

    Two shapes of caller legitimately do more than call this, and neither
    re-implements the comparison: those that need the row index go through
    :func:`index_by_handle`, and those that must exclude candidates before
    matching (the shop's ``name != "Gold"`` filter, the combat adapter's
    ``enemy_``/``ally_`` prefix strip) narrow their arguments and then call
    this. If you find yourself writing ``wire_handle(x) == some_id`` anywhere
    else, one of these two is the tool you want.

    A falsy ``handle`` matches nothing -- an absent id must not resolve to the
    first entity in the room.
    """
    return index_by_handle(entities, handle)[0]


def move_in_progress(combatant):
    """Return the current move, including a move detached for cooldown."""
    move = getattr(combatant, "current_move", None)
    if move is not None:
        return move
    return next(
        (
            candidate
            for candidate in getattr(combatant, "known_moves", [])
            if getattr(candidate, "current_stage", None)
            in (MOVE_STAGE_RECOIL, MOVE_STAGE_COOLDOWN)
        ),
        None,
    )


def exp_needed_for_level(level, intelligence):
    """Exp required to advance from `level` to the next.

    Single source of the leveling curve — used by Player._level_up_api and
    AllyProgressionMixin.exp_to_level so ally pacing always matches Jean's.
    The per-level requirement is floored at 1 so very high intelligence
    (>= 165) can't zero it and spin exp-gain loops forever.
    """
    return int(level) * max(1, 165 - int(intelligence))


# ── Canonical defaults ────────────────────────────────────────────────────────
# 1.0 = no effect, 0.5 = half damage/chance, 2.0 = double.
# Negative damage-resistance values mean the damage heals instead.
# Status-resistance values cannot be negative.

_DEFAULT_RESISTANCE = {
    "fire": 1.0,
    "ice": 1.0,
    "shock": 1.0,
    "earth": 1.0,
    "light": 1.0,
    "dark": 1.0,
    "piercing": 1.0,
    "slashing": 1.0,
    "crushing": 1.0,
    "spiritual": 1.0,
    "pure": 1.0,
}

_DEFAULT_STATUS_RESISTANCE = {
    "generic": 1.0,  # Default status type for all states
    "stun": 1.0,  # Unable to move; typically short duration
    "poison": 1.0,  # Drains HP every combat turn/game tick; persists
    "slimed": 1.0,  # Corrosive slime coating; drains HP and lowers finesse/protection; persists
    "enflamed": 1.0,  # Fire damage over time (matches State.statustype="enflamed")
    "sloth": 1.0,  # Drains Fatigue every combat turn
    "apathy": 1.0,  # Drains HEAT every combat turn
    "blind": 1.0,  # Misses physical attacks more frequently; persists
    "incoherence": 1.0,  # Miracles fail more frequently; persists
    "mute": 1.0,  # Cannot use Miracles; persists
    "enraged": 1.0,  # Double physical damage given and taken
    "enchanted": 1.0,  # Double magical damage given and taken
    "ethereal": 1.0,  # Immune to physical; 3× magical damage; persists
    "berserk": 1.0,  # Auto-attack, 1.5× physical damage
    "slow": 1.0,  # All move times doubled
    "sleep": 1.0,  # Unable to move; removed upon physical damage
    "confusion": 1.0,  # Uses random moves on random targets; removed on physical damage
    "cursed": 1.0,  # Sets luck to 1; chance of random move/target; persists
    "stop": 1.0,  # Unable to move; not removed with damage
    "stone": 1.0,  # Unable to move; immune to damage; permanent death if it persists
    "frozen": 1.0,  # Unable to move; removed with Fire magic; permanent death if it persists
    "doom": 1.0,  # Death after n turns/ticks; persists; lifted only by purification
    "death": 1.0,
    "disoriented": 1.0,  # Reduced finesse and protection
}


class Combatant:
    """Base class for Player and NPC.  Do not instantiate directly."""

    def __getstate__(self):
        """Picklable state, minus the adapter's animation channel.

        ``_pending_animation`` is transient API-layer state stamped onto the
        acting combatant for one beat; its ``outcome_target`` is a LIVE
        combatant object (written by ``src.moves._base.publish_outcome``), so
        pickling it drags that enemy's whole object graph into the save. A
        mid-wind-up NPC holds exactly this channel at autosave time. Player
        adds further API-layer exclusions of its own on top by delegating to
        this method (see ``Player.__getstate__``), so a strip added here
        reaches every combatant structurally.

        ``COMBAT_HANDLE_ATTR`` is deliberately NOT stripped: the wire handle is
        persisted combatant identity (issue #511), and dropping it would remint
        a fresh one on load -- breaking any id a client still holds across a
        save/load and reintroducing, per reload, the aliasing it replaced.
        """
        state = self.__dict__.copy()
        state.pop(PENDING_ANIMATION_ATTR, None)
        return state

    def _init_resistances(self):
        """Initialise resistance and status-resistance dicts to canonical defaults."""
        self.resistance = dict(_DEFAULT_RESISTANCE)
        self.resistance_base = dict(_DEFAULT_RESISTANCE)
        self.status_resistance = dict(_DEFAULT_STATUS_RESISTANCE)
        self.status_resistance_base = dict(_DEFAULT_STATUS_RESISTANCE)

    def _set_status_resistance(self, key, value):
        """Override a status-resistance value on both the base and live dicts.

        `status_resistance` is only re-synced from `status_resistance_base` on
        the next `reset_stats()`/`refresh_stat_bonuses()` call (combat start,
        item equip, etc.) — a subclass `__init__` that only sets the `_base`
        dict leaves the live value stale (e.g. immune-to-own-effect checks run
        via `functions.inflict()` right after construction, before any combat
        loop has had a chance to sync it).
        """
        self.status_resistance_base[key] = value
        self.status_resistance[key] = value

    # ── Shared methods ────────────────────────────────────────────────────────

    def is_alive(self):
        return self.hp > 0

    def check_revive(self):
        """Consult revive-capable states (e.g. PhoenixRevive) before death is
        finalized. Returns True if a state revived this combatant, in which
        case the caller must not proceed with death handling."""
        for state in self.states[:]:
            try_revive = getattr(state, "try_revive", None)
            if try_revive and try_revive(self):
                return True
        return False

    def cycle_states(self):
        """Process all active states.  Iterates over a snapshot so states that
        remove themselves during process() do not cause skipped entries."""
        for state in self.states[:]:
            state.process(self)

    def is_stunned(self):
        """True if any active state blocks move selection for this beat
        (e.g. WarCryStunned). Checked by combat orchestration, not by
        select_move() itself, so it applies even to NPC subclasses that
        override select_move() entirely."""
        return any(getattr(state, "_stunned", False) for state in self.states)

    def get_equipped_items(self):
        """Return all items in inventory that are currently equipped."""
        return [item for item in self.inventory if getattr(item, "isequipped", False)]

    def refresh_moves(self):
        """Return the subset of known_moves that are currently viable."""
        return [move for move in self.known_moves if move.viable()]

    def get_hp_pcnt(self):
        """Return remaining HP as a decimal fraction (0.0–1.0).

        Guards against maxhp <= 0 (fuzzer/extreme-stat case) so the divide
        never raises ZeroDivisionError in the combat loop.
        """
        maxhp = getattr(self, "maxhp", 0)
        try:
            maxhp = float(maxhp)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(maxhp) or maxhp <= 0:
            return 0.0
        return float(self.hp) / maxhp

    # ── Numeric guards (issue #296 hardening) ─────────────────────────────────
    # A missing resistance key (direct dict indexing) and non-finite values
    # (NaN/inf) were both confirmed to crash the combat damage path — the former
    # with KeyError, the latter with a ValueError inside int(damage). These
    # helpers are the single, shared choke point that keeps damage finite and
    # HP bounded for both Player and NPC (never duplicated in subclasses).

    def get_resistance(self, damage_type, default=1.0):
        """Return a sanitized damage-resistance multiplier for `damage_type`.

        Thin wrapper over :func:`functions.combat_resistance` (the single shared
        implementation the combat damage path also calls directly, so the
        sanitization is defined once): resolves a missing key to the base-dict
        value or `default` and coerces a non-finite value (NaN/inf) to `default`.
        """
        import src.functions as functions
        return functions.combat_resistance(self, damage_type, default)

    def get_status_resistance(self, status_type, default=0.0):
        """Return a sanitized status-resistance fraction, clamped to [0.0, 1.0].

        Thin wrapper over :func:`functions.combat_status_resistance`. A missing
        key falls back to `default`; NaN/inf/out-of-range values are coerced into
        [0, 1] so the resulting application chance stays sane.
        """
        import src.functions as functions
        return functions.combat_status_resistance(self, status_type, default)

    def clamp_hp(self):
        """Clamp ``hp`` into [0, maxhp], coercing non-finite hp/maxhp to 0.

        Combat damage and heal paths mutate ``hp`` directly; calling this right
        after such a mutation keeps the HP-never-NaN/inf and HP-in-[0, maxhp]
        invariants without every call site repeating the bounds logic. Returns
        the clamped hp.
        """
        maxhp = getattr(self, "maxhp", 0)
        try:
            maxhp = float(maxhp)
            if not math.isfinite(maxhp) or maxhp < 0:
                maxhp = 0.0
        except (TypeError, ValueError):
            maxhp = 0.0
        hp = getattr(self, "hp", 0)
        try:
            hp = float(hp)
        except (TypeError, ValueError):
            hp = 0.0
        if not math.isfinite(hp):
            hp = 0.0
        self.hp = int(max(0.0, min(hp, maxhp)))
        return self.hp
