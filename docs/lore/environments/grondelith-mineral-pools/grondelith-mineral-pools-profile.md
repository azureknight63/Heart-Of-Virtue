# Grondelith Mineral Pools — Environment Profile

Overview
--------
The Grondelith Mineral Pools are a sacred, cavernous complex of spring-fed basins and crystalline spires beneath Grondia. Once pristine and central to Golemite ritual life, sections of the pools have been corrupted by a spreading slime infestation. The environment should communicate equal measures of awe and danger: luminous, milky-blue water and carved stone basins contrasted with sickly green slime, dissolving rock, and pulsing parasitic growths.

Key Areas
---------
- Sacred Atrium: The entry chamber — pristine pools, gentle flowing streams, and evidence of recent Golemite cleansing efforts (tools, arranged picks). A place for quiet moments and potential healing tiles.
- Corrupted Channels: A navigable maze of slime-coated passages, pulsing glands, and narrow stone platforms. Environmental traversal and hazard design live here.
- The Heart of the Infestation: A vast, circular cavern dominated by a pulsating central pool (King Slime arena) and a single uncorrupted platform for the final confrontation.
- Luminous Grotto (Secret): A hidden, pristine grotto threaded with glowing mineral veins and a geode puzzle that rewards exploration with a thematic upgrade.

Environment & Sensory Notes
---------------------------
- Visual: Milky blue pools in uncorrupted pockets contrast with iridescent, sickly-green water in corrupted areas. Crystalline spires and mineral veins reflect and fragment light into shards.
- Audio: The space mixes the gentle tinkle of clean water with the wet slosh and sticky slurp of slime; occasional resonant chimes from shifting crystals underscore larger set-pieces.
- Touch/Movement: Stone platforms can be polished and stable in clean areas; in corrupted channels, surfaces are slick and partially dissolved, requiring careful navigation or special mechanics.

Hazards & Encounters
--------------------
- Slime mobs: Multiple varieties (small, spitter, and larger aggregations) populate channels and ambush chokepoints.
- Pulsing Glands: Environmental hazards that eject projectiles or spawn smaller slimes on a timer.
- Slime Bridges & Slips: Traversal challenges that punish rash movement; some bridges may require timed crossings.
- King Slime: The central boss that holds the special mineral fragment; victory purifies the central pool and reveals unique loot.

Quests & Hooks
--------------
- "The Damp Ledger": A supplier ledger that ties Grondelith suppliers to Grondia merchants — useful for merchant-side content and Mersh/Jambo hooks.
- "Cleansing Rite": A Conclave-initiated mission to purify a corrupted channel using ritual items or by slaying certain slime nodes.
- "The Luminous Prize": A side quest to locate the hidden grotto and solve the geode puzzle for a rare Golemite artifact.

Design & Implementation Notes
-----------------------------
- Verticality & Flow: Design encounters to move the player progressively from safe, contemplative spaces to tighter, more dangerous corridors and finally to the open, dramatic boss arena.
- Reward Structure: Place smaller rewards in side niches and a thematic, meaningful drop in the Heart (the mineral fragment). The grotto reward should feel like a cultural artifact more than generic loot.
- Puzzle Integration: The geode puzzle should use environmental clues previously seen in the Sacred Atrium and tie into Golemite symbolism.
- Data Sources: Use `src/resources/maps/grondia.json` and tile definitions for canonical placements; consult `docs/lore/environments/mineral-pool-design-notes.md` for room-level description and timeline.

References
----------
- Design notes: `docs/lore/environments/mineral-pool-design-notes.md`
- Map JSON: `src/resources/maps/grondia.json`
