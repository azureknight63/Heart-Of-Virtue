"""
Combat states to be used within combat module. May also spill over to the standard game.
 States are objects applied to a player/npc that hang around until they expire or are removed.
"""

from typing import Optional


def map_name_for_tile(tile) -> Optional[str]:
    """Return the map name ``tile`` belongs to, or ``None`` if unknown.

    Every real ``MapTile`` sets ``self.map`` to the same dict its owning map's
    tiles all share (``src/tiles.py``, ``src/universe.py``). The single place
    this derivation should live — used by ``tile_identity`` below,
    ``GameService._map_name_for_tile`` (which namespaces persisted tile-state
    keys, issue #528), and story-event arrival guards (e.g.
    ``GorranGestureEvent``, issue #547) that need to know which map a
    ``previous_tile`` belonged to. It used to be reimplemented independently
    at all three call sites.
    """
    tile_map = getattr(tile, "map", None)
    return tile_map.get("name") if isinstance(tile_map, dict) else None


def tile_identity(tile):
    """Stable ``(map name, x, y)`` identity for a tile, or ``None`` if unknown.

    Used to scope combat-effect events to the fight/room they were armed in
    (issue #506). Object identity is useless here — events outlive their tile
    objects across a save/load — and ``Event.tile`` is not usable either:
    ``GameService.trigger_combat_events`` rebinds it to the player's *current*
    room before every evaluation, so an event that leaked into another fight
    reports that fight's tile as its own.

    Returns ``None`` for anything that is not a real positioned tile (a missing
    tile, or a test double whose coordinates are not integers). Callers must
    read ``None`` as *unknown* and fall back to their permissive behaviour
    rather than guessing that two tiles differ.
    """
    x = getattr(tile, "x", None)
    y = getattr(tile, "y", None)
    if not isinstance(x, int) or not isinstance(y, int):
        return None
    return (map_name_for_tile(tile), x, y)


def purge_orphaned_combat_events(player, current_tile=None):
    """Drop combat-effect events armed in a room the player is no longer in.

    ``player.combat_events`` is process-wide and was never cleared by any
    teardown path, so a chain armed in one fight stayed armed forever and its
    gates — pure global predicates like "combat_list is empty" — fired in
    whatever unrelated fight came next (issue #506).

    Purging is by *origin room mismatch*, never blanket-clearing: an event
    legitimately mid-fight must survive a wave transition, which reaches
    teardown-adjacent code with ``reinit=True``. Events whose origin or the
    current room cannot be identified are left alone.

    Returns the list of events removed.
    """
    events = getattr(player, "combat_events", None)
    if not events:
        return []
    if current_tile is None:
        current_tile = getattr(player, "current_room", None)
    here = tile_identity(current_tile)
    if here is None:
        return []
    removed = []
    for event in list(events):
        if not getattr(event, "combat_effect", False):
            continue
        origin = getattr(event, "origin_tile_key", None)
        if origin is None or origin == here:
            continue
        try:
            events.remove(event)
        except ValueError:  # pragma: no cover - concurrent removal
            continue
        removed.append(event)
    return removed


#: The value a set story gate holds. Gates are set-or-absent; ``"1"`` is how
#: the story dict has always spelled "set", so saves written before these
#: helpers read the same.
GATE_SET = "1"


def _story_or_none(player):
    """``player``'s story dict, or None when there is none to read or write
    -- no universe, no story yet, or a story that is not a dict."""
    story = getattr(getattr(player, "universe", None), "story", None)
    return story if isinstance(story, dict) else None


def story_gates(player):
    """The story-gate dict ``player`` carries, or ``{}`` when there is none.

    Read the story dict through this rather than reaching through
    ``player.universe.story`` by hand: the hand-rolled ``getattr`` chains it
    replaced disagreed about a missing story (``None``, a throwaway ``{}``,
    or ``AttributeError``). The real dict is returned even when it is empty,
    so a caller holding it sees a gate written a moment later. Read-only by
    intent: write through ``set_story_gate``.
    """
    story = _story_or_none(player)
    return {} if story is None else story


def set_story_gate(player, key, value=GATE_SET):
    """Write one story-state value on ``player``; returns whether it did.

    The writer's half of ``story_gates``: a player with no story to record
    into has the write skipped rather than landed in a throwaway dict.
    ``value`` defaults to ``GATE_SET``; a staged counter passes its own.
    """
    story = _story_or_none(player)
    if story is None:
        return False
    story[key] = value
    return True


def gate_is_set(player, key):
    """True when the story gate ``key`` is set on ``player``."""
    return story_gates(player).get(key) == GATE_SET


class Event:  # master class for all events
    """
    Events are added to tiles much like NPCs and items. These are evaluated each game loop to see if the conditions
    of the event are met. If so, execute the 'process' function, else pass.
    Events can also be added to the combat loop.
    Set repeat to True to automatically repeat for each game loop
    params is a list of additional parameters, None if omitted.

    """

    # Issue #463: authored-placeholder metadata. `player`/`tile` are always
    # runtime backrefs; `thread`/`has_run`/`referenceobj`/`completed`/
    # `api_event_id`/`needs_input` are pure session bookkeeping (the exact
    # set that was leaking into map JSON as a full-instance dump before this
    # change) and are excluded here, unconditionally, for every Event
    # subclass -- there is deliberately no MAP_AUTHORED_OVERRIDES entry for
    # any of them.
    MAP_AUTHORED_PARAMS = {
        "name", "repeat", "params", "combat_effect", "delay_duration",
        "delay_mode",
    }

    #: The story gate a one-shot beat writes when it finishes. The default
    #: ``check_conditions`` retires the event once it is set; other events
    #: read it as ``<Beat>.GATE_KEY``, so no reader can drift from the
    #: writer. None on events that are not such beats.
    #:
    #: The RETIREMENT path reads it off the class --
    #: ``type(self).GATE_KEY`` in ``retire_if_gate_set`` and in the default
    #: ``check_conditions`` -- because events are pickled into saves, so an
    #: instance ``__dict__`` restored from one could otherwise decide which
    #: gate takes a beat off its tile. A beat naming its OWN gate
    #: (``self.set_story_gate(self.GATE_KEY)``, and the guards beside it in
    #: src/story/) reads it through the instance like any other class
    #: attribute; that is the common spelling and is not being deprecated
    #: here. Same split as ``Passageway.DEMO_ENDED_FLAG``.
    GATE_KEY = None

    def __init__(
        self,
        name,
        player=None,
        tile=None,
        repeat=False,
        params=None,
        combat_effect: bool = False,
        delay_duration: int = 3000,
        delay_mode: Optional[str] = "combat",
    ):
        self.name = name
        self.player = player
        self.tile = tile
        self.repeat = repeat
        self.thread = None
        self.has_run = False
        self.params = params
        self.referenceobj = (
            None  # objects being referenced for special conditions can be put here
        )
        self.combat_effect = combat_effect
        self.delay_duration = delay_duration
        self.delay_mode = (
            delay_mode  # "exploration", "combat", or "both" (None means no delay)
        )
        self.completed = False
        self.api_event_id = None
        self.needs_input = False
        # Room this event was armed in, captured before anything can rebind
        # `self.tile` (issue #506). See tile_identity() for why the raw tile
        # reference cannot serve this purpose.
        self.origin_tile_key = tile_identity(tile)

    # The story-gate methods below call the module-level functions of the
    # same names, not themselves: a method body resolves bare names against
    # module globals, never the class. They exist because story events read
    # and write gates on nearly every call, always for ``self.player``.
    #
    # Each delegates through a private alias bound at class-body time rather
    # than naming the module function directly: inside the class body the
    # method name already shadows it, so a one-token edit (an added ``self.``,
    # or a decorator that changes the lookup) would turn the body into
    # unbounded recursion with nothing to read as wrong.
    _module_story_gates = staticmethod(story_gates)
    _module_set_story_gate = staticmethod(set_story_gate)
    _module_gate_is_set = staticmethod(gate_is_set)

    def story_gates(self):
        """The story-gate dict this event's player carries, or ``{}``."""
        return self._module_story_gates(self.player)

    def set_story_gate(self, key, value=GATE_SET):
        """Write one story-state value on this event's player; returns
        whether it did (see the module-level ``set_story_gate``)."""
        return self._module_set_story_gate(self.player, key, value)

    def gate_is_set(self, key):
        """True when the story gate ``key`` is set on this event's player."""
        return self._module_gate_is_set(self.player, key)

    def retire_if_gate_set(self, key=None):
        """True -- and this event taken off its tile -- once ``key`` (this
        event's ``GATE_KEY`` by default) is set.

        How a one-shot story beat opens ``check_conditions``: the gate it
        writes when it finishes is also what retires any copy of it still
        attached to a tile.
        """
        # ``type(self)``, not ``self``: a pickled save carries a ``__dict__``,
        # and an instance attribute named GATE_KEY would otherwise choose
        # which gate retires this beat. Same reasoning as
        # ``Passageway.end_demo``'s ``type(self).DEMO_ENDED_FLAG``.
        gate = type(self).GATE_KEY if key is None else key
        if not gate_is_set(self.player, gate):
            return False
        events = getattr(self.tile, "events_here", None)
        if events is not None and self in events:
            events.remove(self)
        return True

    def pass_conditions_to_process(self):
        self.process()
        # If the event requires input, we don't want to remove it yet;
        # it will be removed once it's completed or on subsequent check
        if not self.repeat and not getattr(self, "needs_input", False):
            if self in self.tile.events_here:
                self.tile.events_here.remove(
                    self
                )  # if this is a one-time event, kill it after it executes
            elif self in self.player.combat_events:
                self.player.combat_events.remove(self)

    def check_conditions(self):
        """Run the event -- unless it is a one-shot beat whose ``GATE_KEY`` is
        already set, which retires it instead."""
        if type(self).GATE_KEY is not None and self.retire_if_gate_set():
            return
        self.pass_conditions_to_process()

    def process(self):
        """
        to be overwritten by an event subclass
        """


class CombatEvent(Event):
    """
    Event that initiates parameterized combat using a CombatEventConfig.
    """

    # Issue #463: `config` is already a clean, fully-authored dataclass (see
    # CombatEventConfig) with zero runtime leakage -- the best existing
    # example of the pattern this issue generalizes. name/repeat/etc. are
    # inherited from Event.
    MAP_AUTHORED_PARAMS = {"config"}

    def __init__(self, name, player=None, tile=None, repeat=False, config=None):
        """
        Args:
            config (CombatEventConfig): Configuration for the combat encounter
        """
        super().__init__(name, player, tile, repeat, params=[config])
        self.config = config

        # Declare input requirements for API mode
        self.needs_input = True
        self.input_type = "choice"
        self.input_prompt = "Prepare for combat!"
        self.input_options = [{"value": "combat_start", "label": "FIGHT FOR YOUR LIFE"}]

        # Use narrative text from config if available, otherwise use a default
        if hasattr(self.config, "narrative_text") and self.config.narrative_text:
            self.description = self.config.narrative_text
        else:
            self.description = (
                f"As you move forward, the air grows cold... {name} begins!"
            )

    def process(self, user_input=None):
        """
        Initiates combat with the configured parameters.
        """
        # If API input is "combat_start", we prepare the NPCs for GameService to pick up.
        if user_input == "combat_start":
            # Spawn the configured NPCs onto the tile
            if self.config and hasattr(self.config, "enemy_list"):
                for enemy_name, count in self.config.enemy_list:
                    for _ in range(count):
                        npc = self.tile.spawn_npc(enemy_name)
                        if npc:
                            # Force aggro and in_combat so they are picked up immediately
                            npc.aggro = True

            # Spawn configured allies as full AI-controlled combatants for this
            # fight only (issue #427) — not the player's persistent party.
            # `event_temp_ally` marks them so post-combat cleanup drops them
            # from combat_list_allies instead of letting them follow Jean.
            if self.config and getattr(self.config, "ally_list", None):
                if not hasattr(self.player, "combat_list_allies"):
                    self.player.combat_list_allies = [self.player]
                for ally_name, count in self.config.ally_list:
                    for _ in range(count):
                        ally = self.tile.spawn_npc(ally_name)
                        if ally:
                            ally.friend = True
                            ally.aggro = False
                            ally.event_temp_ally = True
                            if ally not in self.player.combat_list_allies:
                                self.player.combat_list_allies.append(ally)

            # Stash this encounter's scenario/grid overrides on the player so
            # ApiCombatAdapter.initialize_combat can honor them instead of its
            # usual heuristic (issue #427). Cleared after use.
            if self.config and getattr(self.config, "scenario_type", None):
                self.player._pending_scenario_type = self.config.scenario_type
            if self.config and getattr(self.config, "grid_size_override", None):
                self.player._pending_grid_size_override = (
                    self.config.grid_size_override
                )
            if self.config and getattr(self.config, "on_victory_text", None):
                self.player._pending_victory_narrative = self.config.on_victory_text

            # Return a signal that combat is ready to be initialized
            if not self.repeat:
                if self in self.tile.events_here:
                    self.tile.events_here.remove(self)

            self.needs_input = False
            self.completed = True

            return {"combat_ready": True}

        # The web client always sends "combat_start" (the sole input option).
        # Any other input is a no-op — there is no terminal combat loop to fall
        # back to.
        return {"combat_ready": False}


class LootEvent(Event):
    """
    Event that handles looting a container via a choice dialog.
    """

    def __init__(self, name, player=None, tile=None, container=None):
        super().__init__(name, player, tile, repeat=False, params=[container])
        self.container = container
        self.needs_input = True
        self.input_type = "choice"
        self.input_prompt = "Select an item to take:"
        self.description = (
            f"Jean rifles through the contents of the {container.nickname}."
        )
        self._rebuild_options()

    def _rebuild_options(self):
        self.input_options = []
        if not hasattr(self.container, "inventory") or not self.container.inventory:
            self.input_options.append({"value": "exit", "label": "Close (Empty)"})
            return

        for i, item in enumerate(self.container.inventory):
            label = f"Take {item.name}"
            if hasattr(item, "count") and item.count > 1:
                label += f" ({item.count})"
            self.input_options.append({"value": str(i), "label": label})

        self.input_options.append({"value": "all", "label": "Take All"})
        self.input_options.append({"value": "exit", "label": "Exit"})

    def process(self, user_input=None):
        if not user_input or user_input == "exit":
            self.completed = True
            self.needs_input = False
            return {"success": True, "message": "Interaction ended."}

        from src.narration import cprint

        from src.inventory_utils import transfer_item

        if user_input == "all":
            snapshot = list(self.container.inventory)
            taken_names = []
            for item in snapshot:
                qty = getattr(item, "count", 1)
                transfer_item(self.container, self.player, item, qty)
                taken_names.append(item.name)

            if taken_names:
                cprint(f"Jean takes everything: {', '.join(taken_names)}", "green")
            else:
                cprint("The container is empty.", "yellow")

            # Since everything is taken, we can end the event
            if hasattr(self.container, "refresh_description"):
                self.container.refresh_description()

            self.completed = True
            self.needs_input = False
            return {"success": True}

        if user_input.isdigit():
            idx = int(user_input)
            if 0 <= idx < len(self.container.inventory):
                item = self.container.inventory[idx]
                qty = getattr(item, "count", 1)
                transfer_item(self.container, self.player, item, qty)
                cprint(f"Jean takes the {item.name}.", "green")

                if hasattr(self.container, "refresh_description"):
                    self.container.refresh_description()

                # Rebuild options for next choice
                self._rebuild_options()
            else:
                cprint("Invalid item choice.", "red")

        # Keep pending if we didn't exit or take all
        return {"success": True}


class PassagewayTransitionEvent(Event):
    """Confirmation event shown before traversing a passageway.

    The frontend displays the "Jean steps through..." narration and a
    confirmation button.  Clicking it calls process() which performs the
    actual teleport via the passageway's stored parameters.
    """

    #: The API names each confirmation ``NAME_PREFIX + passageway name``, so
    #: the pending-event dedupe treats a re-armed confirmation for the same
    #: passageway as one event. Declared here, on the type it names, so a
    #: test or client matching confirmations reads it rather than a copy.
    NAME_PREFIX = "Passage_"

    def __init__(self, name, player=None, tile=None, passageway=None):
        super().__init__(name, player, tile, repeat=False)
        self.passageway = passageway
        self.needs_input = True
        self.input_type = "choice"
        self.input_prompt = "Step through?"
        self.input_options = [
            {"value": "continue", "label": "Step through"},
        ]

        # Build the article phrase for the description
        _n = getattr(passageway, "name", "passageway")
        _ref = passageway.build_article_phrase(_n) if passageway else _n
        self.description = f"Jean steps through {_ref}..."

    def process(self, user_input=None):
        if user_input != "continue":
            # Mark completed before raising so the event is cleaned up even
            # on invalid input — the API's process_event_input will catch
            # the ValueError and surface the error to the client.
            self.completed = True
            self.needs_input = False
            raise ValueError(
                f"Unexpected input for {self.name}: "
                f"expected 'continue', got {user_input!r}"
            )
        pw = self.passageway
        if pw and pw.teleport_map and pw.teleport_tile:
            pw._commit_teleport(self.player)
        self.completed = True
        self.needs_input = False
        return {"success": True}
