# Resolute Plains — Environment Profile

Overview
--------
The Resolute Plains lie directly east of Grondia. Wide, rolling grasslands intersected by long, winding dirt caravan roads make this region the natural trade corridor between Grondia and the settlements further east. The open landscape favors visibility but also provides cover for opportunistic threats: bandit encampments tucked off the road, and nomadic human communities who move across the plain with the seasons.

Geography & Connections
-----------------------
- West: Grondia's eastern gates and carved passages descend into the plains.
- East: Routes continue toward distant settlements and trade hubs (to be expanded later).
- South: A vast desert expanse; dunes and arid wastes begin here and can be explored in a later design pass.
- North / Northwest / West: A tall mountain range rings the plains on the far edges, acting as a natural barrier and a route for shepherded herds and hidden passes.

Roads & Travel
--------------
- Caravan Routes: The primary dirt roads are long and winding, built to avoid marshy patches and to follow fresh water and grazing points. These roads are maintained intermittently by caravan companies and local authorities but still see many travelers with varied defenses.
- Roadside Features: Taverns, rest posts, broken wagons, and small shrines are common along the route. They provide stopover narrative beats and potential small quests.

Factions & Dwellers
-------------------
- Bandit Encampments: Small but organized bands of brigands use the plains as hunting ground. Their camps are typically set just off-trail near choke points, gullies, or clusters of scrub where caravans slow. They prefer raids on poorly defended caravans and send scouts to monitor traffic.
- Nomadic Human Encampment (The Wayfarers): A semi-permanent nomadic community that moves seasonally across the plains. Their leader might trade, barter, or trade safe passage for a favor. The nomads are skilled trackers and storytellers; they keep memory-objects and heirlooms that may be tied to Jean's past.
- Caravans & Merchants: Large caravans travel the roads under armed escort; they are potential allies and quest-givers.

Key Hooks & Story Beats
----------------------
- Bandit Base Threat: Design an off-road bandit encampment that functions as a secondary dungeon — stealth approaches and social infiltration are viable alternatives to frontal assault.
- Memory Token Beat: The nomadic encampment should hold an item or story that resonates with Jean's life (a lullaby, a child's ribbon, a worn energy token) — a plausible but ambiguous piece of evidence that Amelia and Regina might be alive. This token can be used to push Jean's emotional arc forward and create moral complexity.
- Caravan Escort: Missions to protect, guide, or rescue caravans create emergent encounters and let players choose mercantile or moral outcomes.
- Nomad Diplomacy: The player can gain favor with the Wayfarers through tasks (healing, trade runs, storytelling), which may yield information about wider routes and the desert border.

Encounters & Mechanics
----------------------
- Bandit Ambushes: Randomized road encounters with bandit scouts leading to a possible ambush; scale difficulty with caravan size and escort presence.
- Hiding Camps: Bandit camps use camouflage; a tracking or perception check can reveal access paths and watch posts.
- Nomadic Market: Temporary trade opportunities with unique items, local lore, and quests; good place for Jean to trade or pick up clues.
- Memory Mechanic: The memory token is tied to a small scene or dialog event that temporarily stabilizes Jean's morale (or misleads him depending on later reveals).

Design Notes & Balance
----------------------
- Placement: Place bandit camps off the main road but close enough to intercept — design them around chokepoints and environmental features rather than open plains where ambushes are too obvious.
- Stealth & Choice: Offer stealth and social options; players should be able to avoid combat with planning and dialog.
- Emotional Stakes: The memory token should be narratively charged but ambiguous — avoid making it definitive evidence. Use it as a character-driven lever rather than a simple plot device.

Implementation Pointers
----------------------
- Map tiles: Create a regional map JSON similar to other maps (tile grid keyed by coordinates), and use `symbol` metadata to mark roads, encampments, nomad sites, and landmarks.
- Encampment design: Model camp tiles as small multi-tile areas with patrol routes and an optional stealth entrance (e.g., a gully tile with lower awareness penalties).
- Memory token: Implement the token as an item with a readable description and a small dialog branch when presented to Jean or others; keep it possible to later re-evaluate its authenticity.

Next Steps & Expansion
----------------------
- Flesh out caravan waypoints (inns, shrines) and link them to small local side quests.
- Define the nomad leader and several named characters with distinct personalities and trade goods.
- Expand the southern desert region into a full environment profile with desert-specific hazards and politics.

References
----------
- Geographic placement: East of `src/resources/maps/grondia.json` (Grondia's eastern gate).
