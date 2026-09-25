"""World object serialization for API responses."""

from typing import Dict, Any, List

from src.api.serializers.item_serializer import ItemSerializer
from src.combatant import wire_handle


class ObjectSerializer:
    """Serialize world objects to JSON-safe dictionaries."""

    @staticmethod
    def locked_for(obj: Any, player: Any = None) -> bool:
        """Whether ``obj`` is locked, as ``player`` would find it.

        The key lock (``locked``) or, given a player, a story gate the engine
        holds it by -- ``story_locked``, the side-effect-free half of
        ``Passageway.crossing_locked`` (issue #718: the Eastern Gate read
        ``locked: false`` while refusing to open). Without a player a story
        gate cannot be judged and only the key lock counts.
        """
        if isinstance(obj, dict):
            return bool(obj.get("locked", False))
        if getattr(obj, "locked", False):
            return True
        story_locked = getattr(obj, "story_locked", None)
        return bool(player is not None and callable(story_locked) and story_locked(player))

    @staticmethod
    def _serialize_base(obj: Any, player: Any = None) -> Dict[str, Any]:
        """Internal method for basic object serialization to avoid recursion."""
        if not obj:
            return {}

        is_dict = isinstance(obj, dict)

        def get_attr(attr_name: str, default: Any = None) -> Any:
            if is_dict:
                return obj.get(attr_name, default)
            return getattr(obj, attr_name, default)

        def has_attr(attr_name: str) -> bool:
            if is_dict:
                return attr_name in obj
            return hasattr(obj, attr_name)

        # The object's id is its opaque handle, unconditionally — the same rule
        # the other six entity serializers follow, and the id
        # ``interact_with_target`` resolves through ``find_by_handle``.
        #
        # An explicit ``id`` attribute used to win over the handle. Nothing in
        # the engine sets one (no class in src/objects.py has an ``id``, and no
        # object entry in any map JSON carries the key — both checked), so the
        # branch's only effect was on test doubles, where it published an id
        # that ``find_by_handle`` cannot accept: the client would get "Target
        # not found." for that object and nothing would log a reason. That is
        # exactly the half-move #518 exists to make impossible, so the branch
        # is gone rather than being taught to the resolver.
        obj_data = {
            "id": wire_handle(obj),
            "name": get_attr("name", "Unknown"),
            "type": get_attr("type", "dict" if is_dict else type(obj).__name__),
            "description": get_attr("description", ""),
            "aliases": get_attr("aliases", []),
            "action_aliases": get_attr("action_aliases", []),
        }

        # Passability and state
        if has_attr("is_passable"):
            obj_data["is_passable"] = get_attr("is_passable")

        # Hidden/discovery info
        if has_attr("hidden"):
            obj_data["hidden"] = get_attr("hidden")
        if has_attr("hide_factor"):
            obj_data["hide_factor"] = get_attr("hide_factor")

        # Interaction keywords
        if has_attr("keywords"):
            obj_data["keywords"] = get_attr("keywords")

        # Specific object states. A story gate counts only when there is a
        # player to judge it by (#718); a passageway without one reports none.
        if has_attr("locked"):
            obj_data["locked"] = get_attr("locked")
        if player is not None and callable(get_attr("story_locked")):
            obj_data["locked"] = ObjectSerializer.locked_for(obj, player)

        # Handle state/opened flag consistently
        if has_attr("state"):
            obj_state = get_attr("state")
            obj_data["state"] = obj_state
            obj_data["opened"] = obj_state == "opened"
        elif has_attr("opened"):
            obj_data["opened"] = get_attr("opened")

        # Ensure keywords are consistent with dynamic state
        if "keywords" in obj_data and isinstance(obj_data["keywords"], list):
            has_locked = has_attr("locked")
            has_opened_attr = has_attr("opened") or has_attr("state")

            if has_locked or has_opened_attr:
                current_k = obj_data["keywords"]
                # The KEY lock only: UNLOCK is a verb a key answers, and a
                # story gate (#718) has no key -- advertising it would be a
                # button that can never work.
                is_locked = bool(get_attr("locked", False))
                is_opened = obj_data.get("opened", False)

                # Filter out state-dependent keywords to avoid duplicates or inconsistencies
                new_k = [k for k in current_k if k not in ("open", "unlock")]

                if is_locked:
                    # If locked, only show unlock
                    if "unlock" not in new_k:
                        new_k.append("unlock")
                elif not is_opened:
                    # If closed and unlocked, show open
                    if "open" not in new_k:
                        new_k.append("open")

                obj_data["keywords"] = new_k

        # After the state rewrite, so an "open"/"unlock" it appends joins the
        # group of any authored synonym instead of becoming a second button.
        if not is_dict and isinstance(obj_data.get("keywords"), list):
            obj_data["keywords"] = ObjectSerializer.collapse_synonyms(
                obj, obj_data["keywords"]
            )

        if has_attr("open_message"):
            obj_data["open_message"] = get_attr("open_message")
        if has_attr("idle_message"):
            obj_data["idle_message"] = get_attr("idle_message")

        # Passageway direct-click flag
        if has_attr("passthrough"):
            obj_data["passthrough"] = get_attr("passthrough")

        return obj_data

    @staticmethod
    def collapse_synonyms(obj: Any, keywords: List[Any]) -> List[Any]:
        """One button per distinct call: drop keywords that resolve to the
        same handler as an earlier one (issue #615).

        ``resolve_interaction`` is the single authority on what a keyword
        calls, so grouping is by its answer. The Ferry Landing's ``ferry`` and
        ``landing`` resolve to ``enter`` itself, and render as ENTER alone.
        Handlers compare with ``==``: every lookup mints a fresh bound method,
        so ``is`` would never match.

        The group's verb is its first AUTHORED keyword -- keyword order is the
        author's (and ``Passageway.__init__``'s) statement of which verb leads,
        and it is stable across requests. ``__name__`` would relabel a
        ``KEYWORD_METHOD_ALIASES`` verb (a Book's READ as USE). The one
        exception is a keyword in ``action_aliases``: the client hides those,
        so one is the verb only when the whole group is aliases.

        Kept untouched: a keyword resolving to nothing (the API refuses it in
        fiction, or a passageway crosses on its type), and anything the
        resolver cannot look up. Separate one-line delegator methods are
        distinct handlers and stay separate buttons (#626). Returns a new
        list; the engine's own ``keywords`` -- which the API's advertised-verb
        check reads -- is never touched.
        """
        from src.objects import resolve_interaction

        hidden = getattr(obj, "action_aliases", None)
        if not isinstance(hidden, (list, tuple, set, frozenset)):
            hidden = ()  # a degraded object never breaks the row
        groups = []  # [handler, [keywords in authored order]]
        placed = []  # per keyword: its group, or None when kept as-is
        for keyword in keywords:
            try:
                handler = resolve_interaction(obj, keyword)
            except Exception:
                handler = None
            group = None
            if handler is not None:
                group = next((g for g in groups if g[0] == handler), None)
                if group is None:
                    group = [handler, []]
                    groups.append(group)
                group[1].append(keyword)
            placed.append(group)

        def primary(group):
            return next((k for k in group[1] if k not in hidden), group[1][0])

        result = []
        emitted = []
        for keyword, group in zip(keywords, placed):
            if group is None:
                result.append(keyword)
            elif not any(group is g for g in emitted):
                emitted.append(group)
                result.append(primary(group))
        return result

    @staticmethod
    def serialize(obj: Any, player: Any = None) -> Dict[str, Any]:
        """Serialize a single world object.

        Args:
            obj: World object to serialize (Container, Chest, Door, Shrine, etc.)
            player: The viewing player, when known -- a story-gated lock
                depends on their story (see ``locked_for``).

        Returns:
            Dictionary with object data
        """
        if not obj:
            return {}

        # Check if it's a container and use container serialization if so
        from src.objects import Container

        if isinstance(obj, Container):
            return ObjectSerializer.serialize_container(obj, player)

        return ObjectSerializer._serialize_base(obj, player)

    @staticmethod
    def serialize_list(objects: List[Any], player: Any = None) -> List[Dict[str, Any]]:
        """Serialize multiple world objects.

        Args:
            objects: List of world objects
            player: The viewing player, when known (see ``serialize``)

        Returns:
            List of serialized object dictionaries
        """
        if not objects:
            return []

        return [ObjectSerializer.serialize(obj, player) for obj in objects]

    @staticmethod
    def serialize_container(obj: Any, player: Any = None) -> Dict[str, Any]:
        """Serialize a container object with its contents.

        Args:
            obj: Container object (Chest, Container, etc.)

        Returns:
            Dictionary with container data and items
        """
        obj_data = ObjectSerializer._serialize_base(obj, player)

        # Container-specific info
        obj_data["is_container"] = True

        # Serialize contents
        if hasattr(obj, "inventory") and obj.inventory:
            obj_data["contents"] = ItemSerializer.serialize_list(obj.inventory)
            obj_data["item_count"] = len(obj.inventory)
        elif hasattr(obj, "contents") and obj.contents:
            obj_data["contents"] = ItemSerializer.serialize_list(obj.contents)
            obj_data["item_count"] = len(obj.contents)
        elif hasattr(obj, "items_here") and obj.items_here:
            obj_data["contents"] = ItemSerializer.serialize_list(obj.items_here)
            obj_data["item_count"] = len(obj.items_here)
        else:
            obj_data["contents"] = []
            obj_data["item_count"] = 0

        # Container capacity if applicable
        if hasattr(obj, "capacity"):
            obj_data["capacity"] = obj.capacity

        return obj_data
