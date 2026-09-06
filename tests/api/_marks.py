"""Pytest markers shared across the ``tests/api`` modules.

``NO_QUEST_SYSTEM`` lives here, once, because three places have to agree about
the same fact and would otherwise drift apart the day a quest blueprint lands:

* ``test_routes_critical.py`` marks its quest family with it,
* ``test_routes_tier2.py`` marks three quest classes with it,
* ``test_route_prefix_contract.py`` allow-lists the quest URL prefixes and
  builds its reasons out of :data:`NO_QUEST_SYSTEM_REASON`, and refuses a
  quest-prefixed request that is not made under this marker.

A plain module rather than ``conftest.py``: conftest is loaded by pytest for
its fixtures and hooks and is not conventionally imported from, so a shared
constant put there reads as a fixture file being abused as a library.
"""

import pytest


#: Why every ``/api/quests/*``, ``/api/quest-chains/*`` and
#: ``/api/npc/quests/*`` URL 404s. Stated once; the route-contract guard
#: quotes this string rather than restating the fact.
NO_QUEST_SYSTEM_REASON = (
    "No quest system exists in this tree: no quest, quest-chain or "
    "npc-quest blueprint is registered in src/api/routes/, GameService "
    "carries no quest method, and src/ defines no Quest class -- so every "
    "/api/quests/*, /api/quest-chains/* and /api/npc/quests/* URL 404s."
)

#: Applied to every test in the quest family. ``strict=True`` so the day a
#: quest blueprint lands, the unexpected pass fails the suite and forces the
#: marker off instead of quietly masking a working feature.
NO_QUEST_SYSTEM = pytest.mark.xfail(reason=NO_QUEST_SYSTEM_REASON, strict=True)
