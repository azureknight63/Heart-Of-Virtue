# Luminous Grotto — Area Profile (Secret)

Purpose & Tone
---------------
The Luminous Grotto is a hidden sanctuary inside the corrupted area — a small pocket of the original, pure pools preserved from the infestation. It's intended as an exploration reward: quiet, beautiful, and containing the geode puzzle that yields a culturally significant artifact.

Entrance & Discovery
--------------------
- Hidden Crevice Tile: The entrance is masked in a thick layer of goop in the Corrupted Channels. Players must notice a subtle change in wall texture, follow a faint clean scent, or clear a small slime plug to reveal the crevice.
- Discovery Checks: Use perception or a simple environmental interaction (e.g., pour a restorative vial's water or use a small item) to clear the plug and open the path.

Puzzle — The Geode Depressions
------------------------------
- Layout: A central geode on a pedestal with three mineral depressions arranged before it. The grotto walls show pulsing veined minerals whose colors and shapes correspond to the correct stones.
- Clues & Integration: Clues are etched subtly in the Sacred Atrium's ritual panels (three symbols in sequence) and mirrored in the patterns of the glowing veins in the grotto. Players who observe both areas can solve without trial and error.
- Mechanics: Players collect candidate mineral fragments throughout the pools (e.g., light shard, blue vein chip, amber sliver). Placing correct minerals in order triggers the geode. Incorrect placements could either reset the puzzle or briefly spawn small slimes as a penalty.

Rewards & Lore
--------------
- Artifact: The geode contains a Golemite-crafted item (armor piece or weapon) imbued with pool energy; the item should feel culturally resonant and not just mechanically superior.
- Insight: Solving the puzzle yields a short lore text about Golemite rites and the importance of the pools; store this as a journal entry for the player.

Implementation Pointers
---------------------
- Geode puzzle object: Implement `GeodePedestal` with state for `slots[3]`, `accepted_minerals`, and a `validate()` method that checks order and types.
- Clue flags: Add a world flag `saw_atrium_clues` if the player has inspected the ritual panel in the Sacred Atrium; if this flag is set, the game can provide a subtle UI hint or a smaller hint cost for the puzzle.
- Testing: Unit test the pedestal validation logic (correct order, incorrect penalties) and that the artifact is granted once and logged in the player's journal.

Map Notes
---------
- Make the grotto compact (3–6 tiles) and visually distinct — bright veins, still water, and the pedestal center.
- Mark the grotto entrance with `symbol: "grot"` or similar in the main map JSON to allow designers to flag secret areas during layout.
