# Heart of the Infestation — Area Profile

Purpose & Tone
---------------
The Heart of the Infestation is the climactic arena for the King Slime encounter. This space should feel vast, resonant, and threatening — a massive cavern where the central pool pulses like a living heart and the player faces the full scope of the infestation.

Arena Layout & Tile Ideas
------------------------
- Central Pool (multi-tile): A large pulsating slime surface; the King Slime uses the pool to move and spawn minions.
- Uncorrupted Platform (1 tile/large): The single, intact stone island where the main battle is staged; player must use it and surrounding platforms to avoid being overwhelmed.
- Peripheral Ledges (ring): A ring of raised stone ledges or broken columns serving as tactical positions and spawn points for minions.
- Drain Channels (hazard): Narrow flows of viscous slime that periodically surge across low tiles, forcing repositioning.

Boss Mechanics (design suggestions)
---------------------------------
- Phase 1: King Slime basic attacks — swipes, slams, and minor splashes that spawn small slimes.
- Phase 2: Pool Surge — the King slams the pool to create radial shockwaves and opens fissures that produce Pulsing Glands.
- Phase 3: Fragmented Core — the King consumes nearby mineral shards to temporarily increase size and armor; players must break shards to restore vulnerability.

Victory & Aftermath
-------------------
- Purification: On defeat, the King Slime's body collapses and the central pool rapidly clears to reveal bright, milky-blue water. Triggers `PoolPurifyEvent` to update world state and open new dialog/events.
- The Mineral Fragment: A unique, lore-rich reward is revealed (the fragment). Implement as an `Item` with descriptive text and a mechanic hook (used in later crafting/quests).
- Environmental Change: Cleaned tiles should swap to uncorrupted variants; consider unlocking access to the Luminous Grotto after purification.

Map & Implementation Notes
-------------------------
- Arena size: Make the arena large enough for movement and boss telegraphed attacks; avoid cluttering with too many hazards in early phases.
- Spawn system: Use a controlled spawn scheduler for minion slimes to avoid overwhelming CPU or the player; cap active minions and queue spawns.
- Save & Recovery: Consider allowing a short pause for recovery before the final sweep (e.g., a short safe period on the uncorrupted platform after the boss reaches a scripted threshold).

Testing
-------
- Run battle simulations at different player levels to tune HP, damage, and spawn rates. Add unit tests for `PoolPurifyEvent` and that the fragment is spawned and flagged as collectible.
