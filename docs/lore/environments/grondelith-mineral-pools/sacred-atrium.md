# Sacred Atrium — Area Profile

Purpose & Tone
---------------
The Sacred Atrium is the ceremonial antechamber that greets the player on approach to the Grondelith Mineral Pools. It should read as calm, venerable, and slightly mournful — a place of ritual habit disrupted by recent corruption elsewhere. The Atrium offers a narrative breathing space before the player enters the dangerous channels.

Suggested Sub-Areas / Tiles
--------------------------
- Entrance Ramp (tile): Wide sloping stone path from Grondia; gradual lighting changes and cooler air cues the descent.
- Central Pool Cluster (3–5 tiles): Small, spring-fed basins with milky-blue water; these can serve as small regain/heal tiles or safe zones.
- Ritual Benches and Tools Alcove (1–2 tiles): Shelves with chisels, arranged tools, and offerings; used as visual storytelling props and for a small NPC interaction or loot seed.
- Guardian Nook (1 tile): A quiet alcove with a carved effigy or small statue—can hold a minor environmental event or a short memory beat.

Encounters & Gameplay
---------------------
- Low combat presence: Keep enemy density low in the Atrium. This area is for exploration, exposition, and smaller puzzles.
- Healing tile optional: Allow one tile (or an event) to provide a minor restorative effect if the player performs a small ritual (collect an offering, recite a phrase — can be a simple flag check).
- Memory beat placement: Ideal spot to deposit a short, poignant memory flash or a clue about the Golemite rituals tied to the geode puzzle.

Map Design Notes
----------------
- Lighting: Use soft, diffuse light from crystals or veins; reflections on water should be distinct from the sickly green sheen later in Corrupted Channels.
- Flow: Place the Entrance Ramp so it funnels players toward a clear exit into the Corrupted Channels; avoid multiple confusing branches here.
- Tile markers: Use `symbol: "~"` for safe water tiles and `symbol: "A"` for the atrium entry in map JSON to help designers locate the area quickly.

Implementation Pointers
---------------------
- Tile metadata: include `title`, `description`, `exits`, `events`, and `objects` (e.g., `Golemite Tools` object with `inspect` interaction).
- Event hooks: Add an `AtriumPeaceEvent` that triggers optional lore dialog and can set a flag enabling the grotto puzzle later.
- Testing: Create a small automated script or unit test that spawns the player at the Entrance Ramp and verifies `AtriumPeaceEvent` triggers and that Central Pool tiles are non-hostile.

References & Cross-links
----------------------
- Geode clues will reference carvings in the Atrium; link to `grondelith-mineral-pools-profile.md` and the Luminous Grotto profile for clue consistency.
