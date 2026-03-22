# Dark Grotto — Map Audit Report

**Focus**: New player orientation and atmosphere
**Date**: 2026-03-20 (implemented 2026-03-22)
**Map file**: `src/resources/maps/dark-grotto.json`

---

## Implementation Status (2026-03-22)

All High and Medium priority items from the original audit have been implemented in `src/resources/maps/dark-grotto.json`.

| # | Item | Status |
|---|---|---|
| 1 | Add search affordance to (2,2) description ("loose stones heaped at its base") | ✅ Done |
| 2 | Differentiate Wall Depression at (5,2) — new description/idle/announce referencing the ledge gap | ✅ Done |
| 3 | Move clue fragment to early path — WallInscription (torn page, Aldric Day 18) at (2,3) | ✅ Done |
| 4 | Reduce (2,2) exits from 7 to 5 — bidirectional removal with explanatory prose on (1,1) and (1,3) | ✅ Done |
| 5 | Give each empty corridor tile one concrete detail | ✅ Done — (1,1) copper coin + Gold item; (3,1) stone/red smear; (6,1) Rumbler claw-marks; (6,3) iron ring; (6,4) wax drippings; (1,3) heel-print + closed crack note |
| 6 | Signal Ferdie's interactivity — tile description updated | ✅ Done |
| 7 | Add cave→ledge transition tile | ⏭ Deferred — requires new tile and topology changes |
| 8 | Rewrite (5,5) alcove description | ✅ Done |
| 9 | Strip Ferdie's loot table | ✅ Done |
| 10 | Add memory fragment trigger at altar | ⏭ Deferred — depends on event system |
| 11 | Explain blocked exits in descriptions | ✅ Partially done — (2,2), (1,1), (1,3) covered as part of exit removal |
| 12 | Player-facing map name | ⏭ Deferred — frontend work |

---

## Current State Analysis

### Tile Inventory
| Coord | Internal Title | Notable Content |
|-------|---------------|-----------------|
| (2,2) | JeanGameStartTile | Iron Key (hidden), 7 exits |
| (2,1) | EmptyCave | WallInscription (Jeremiah 29:11) |
| (1,1) | EmptyCave | Empty |
| (3,1) | EmptyCave | Empty |
| (6,1) | EmptyCave | Empty |
| (7,1) | EmptyCave | Wooden Chest (locked), Ch01ChestRumblerBattle |
| (1,2) | EmptyCave | Pale mushrooms |
| (3,2) | FirstPuzzle | Wall Depression (WallSwitch) → opens east exit |
| (4,2) | RockLedgeWest | Ferdie (Mynx NPC), daylight/river |
| (5,2) | RockLedgeEast | Wall Depression → Ch01BridgeWall |
| (6,2) | EmptyCave | Empty |
| (1,3) | EmptyCave | Empty |
| (2,3) | EmptyCave | Gold (27) + Restorative item |
| (6,3) | EmptyCave | Empty |
| (7,3) | EmptyCave | Steel Lockbox (hidden) → DullMedallion |
| (5,4) | EmptyCave | Empty |
| (6,4) | EmptyCave | Empty |
| (5,5) | EmptyCave | Remains → Tattered Journal, DullMedallion, 133 Gold, Cloth Boots |

**Total tiles**: 18
**Named objects/NPCs**: 7 interactive elements across 18 tiles
**Combat encounters**: 1 (Rumbler at (7,1), event-driven)
**Hidden items**: 2 (Iron Key at (2,2), Steel Lockbox at (7,3))

### Map Topology (ASCII)
```
     1     2     3     4     5     6     7
1  [  ]  [IN]  [  ]              [  ]  [CH]
2       [ST]  [PZ]  [FD]  [BW]  [  ]
3  [  ]  [GO]              [  ]  [  ]  [LB]
4                        [  ]  [  ]
5                        [RM]
```
`ST`=Start, `IN`=Inscription, `PZ`=Puzzle/Wall Depression, `FD`=Ferdie,
`BW`=BridgeWall, `GO`=Gold+Restorative, `CH`=Chest+Rumbler, `LB`=Lockbox, `RM`=Remains

---

## Six-Dimension Audit

### 1. Thematic Coherence — B

**What works**: The start tile's altar + silver light correctly frames Jean awakening into something between death and purpose. The Jeremiah 29:11 inscription ("plans for welfare and not for evil, to give you a future and a hope") is the right scripture for a man in a coma who believes he's made a catastrophic mistake. It's quietly devastating if the player finds it. The dead merchant's journal adds pathos without over-explaining.

**What doesn't**: The cave is called "Dark Grotto" but plays as a neutral, non-threatening space. The name suggests something ominous; the experience is more "mysterious but safe." This gap is fine for a tutorial zone — but it should be *intentional* and *signed*. Right now it reads as unnamed: nothing in the writing distinguishes this grotto from any other cave in the game.

The "EmptyCave" interior title on 15 of 18 tiles is a design-side symptom of a real problem: **the grotto has no identity arc**. A player moving through it experiences a flat succession of atmospheric cave descriptions without a sense of moving *through* something with a beginning, middle, and end.

---

### 2. Environmental Storytelling — B−

**What works**: The Tattered Journal at (5,5) is excellent. Aldric's diary is specific, dated, emotionally credible, and mechanically useful — it tells you where the key is, which gives it functional weight beyond flavor. The Remains container's prose ("the old remains of a poor traveler, leaning against the rock wall") is understated and effective. The inscription at (2,1) is perfect for Jean's spiritual condition.

**What doesn't work**:

**The journal-to-key loop is broken for most players.** The Iron Key is at the start tile (2,2), hidden. The journal that reveals the key's location is at (5,5), the deepest alcove of the map. A new player who explores naturally (north or east from start) will reach the locked chest at (7,1), fail to open it, and have no obvious lead. The journal clue only lands *after* the player has already been frustrated by the chest. Worse, the hidden key at (2,2) has nothing in the tile description that invites searching — "an altar of cold rock" with "ancient dust swirling" does not signal "search here."

**The Inscription at (2,1)** is the single most thematically powerful object in the grotto, but nothing in the tile description creates a reason to linger. "Shallow scratches form wavering lines on one wall, / like someone traced a thought they dared not speak" — this is good setup for the inscription, but the player needs to understand that READ is an available action. The object does include "You think you can make out the words if you READ closely" — but only after examining it. The tile description itself should create more pull toward the wall.

**The hidden Steel Lockbox at (7,3)** is in a dead-end pocket with "wet earth and something faintly floral." Nothing in the description suggests searching. Hidden items without environmental foreshadowing feel like gambling rather than discovery.

---

### 3. NPC Balance — B+

**What works**: Ferdie (the Mynx) is charming — the tail-flick idle message is exactly right. Placing the first living creature the player meets on a ledge with daylight, wind, and "mountain silhouettes" is a strong tonal contrast to the cave interior. The blocked northwest exit on the ledge creates appropriate mystery about what's beyond the mountains.

**What doesn't**: Ferdie's discovery moment is underserved. The `talk` / `pet` / `play` keywords are there but nothing in the tile description signals that Ferdie is *remarkable* or that interaction yields anything. "A small creature watches, tail flicking to some private melody of the river" is nice flavor but tells the player nothing about what they can *do* here. For a player who doesn't know to type `talk`, Ferdie is just scenery.

Ferdie also drops loot (Gold, Restorative, Draught, Equipment_0_1) — but `friend: true` and `damage: 0` imply Ferdie cannot be fought. The loot table is presumably a copy-paste artifact. This is a minor inconsistency but could confuse a player inspecting Ferdie's stats.

---

### 4. Puzzle Quality & Discoverability — C+

This is the weakest dimension and the primary focus of the audit.

**The Wall Depression problem**:
Both (3,2) and (5,2) have objects named "Wall Depression" with *identical* descriptions: "A small depression in the wall. You may be able to PRESS on it." They are in different parts of the map and trigger different events (one opens a wall, one triggers the bridge). When a player presses the first one and a wall opens, they learn the mechanic. When they find the second one and press it, they expect the same mechanic — but `Ch01BridgeWall` presumably does something different. The identical framing will cause confusion and possibly read as a bug.

**The Iron Key discoverability**:
The key is hidden at the most-visited tile in the game (the start tile). This is either a gift or a trap: if the player searches early, they find it immediately; if they never search, they never find it. The tile description gives no affordance for searching. The journal clue only reaches players who've already explored south to (5,5) — by which point they may have given up on the chest.

**Suggested discovery order fix**: Move the journal clue earlier in the likely exploration path (north corridor, near (2,1) or (1,1)), or add a subtle search affordance to (2,2)'s description (e.g., "loose stones are piled at the base of the altar" — something natural that invites interaction).

**The BridgeWall puzzle**:
(5,2) has three blocked exits (east, northeast, southeast) and a Wall Depression. The tile description ("The ledge narrows and kisses a sealed wall seam. Mountain silhouettes haze the distance...") does explain there's a wall seam — that's good. But the blocked exits all facing the same direction (east/further out) with no visible bridge is unclear. Players may not immediately understand they're meant to press the depression to *build* a bridge rather than open a passage in the wall.

---

### 5. Pacing & Flow — B−

**Start tile overload**: (2,2) has 7 exits. For a player's very first tile in the game, this is disproportionate. It communicates "you can go anywhere" rather than "there's a story unfolding." Compare the organic feel of (1,2)'s mushrooms or (2,3)'s abandoned footprints — these feel like places to stumble across, not portal rooms. The start tile exits should feel inviting without being overwhelming.

**No gradual tension build**: The only combat is at (7,1), accessed early if the player goes north. A new player might walk straight into a Rumbler encounter with no items, no orientation, and no understanding of the combat system. This is a difficulty spike without context.

**The southern route is richer but buried**: The most meaningful content — the Remains, the Journal, the narrative of Aldric — is in the southwest quadrant. But the start tile's exits and the locked chest in the northeast will pull most players north and east first. The south quadrant reads as optional exploration rather than the emotional heart of the zone.

**Dead end tiles**: (1,1), (1,3), (3,1), (6,1), (6,3), (6,4) are empty corridors with no purpose beyond padding the map footprint. Several exist only to enable diagonal movement between more interesting tiles. Every tile should do at least one thing.

---

### 6. Lore Depth — A−

**What works**: The map punches above its weight lore-wise. Jeremiah 29:11 at (2,1) is theologically apt — it's the scripture of exile and hope, exactly where Jean sits. The Tattered Journal is specific and human. The "faint comfort, stubborn and warm" at (2,1) that complements the inscription creates a micro-atmosphere distinct from the rest of the cave. Ferdie's presence on a ledge with daylight hints at a larger world beyond.

**What could be better**: Jean's coma condition and crusader identity aren't yet echoed in the grotto's environmental storytelling. The cave could hold more of Jean's inner life — brief sensory intrusions that mirror the memory fragment system described in `chapter-summaries.md`. The grotto is the womb from which Jean emerges; it should carry traces of his psyche, not just generic cave atmosphere.

---

## Improvement Suggestions

### High Priority

**1. Add search affordance to the start tile description**
The Iron Key is hidden at (2,2) but "an altar of cold rock" does not invite the player to search. Change the description to include a physical detail that suggests the altar's base is worth examining — something like "loose stones are heaped at its base, as if piled there deliberately." This doesn't give the key away, but it creates a naturalistic invitation.

```
Before: "An altar of cold rock. Ancient dust swirls in the beam, whispering of secrets buried in shadow."

After: "An altar of cold rock, loose stones heaped at its base as if piled there deliberately. Ancient dust swirls in the beam."
```

**2. Differentiate the two Wall Depressions**
Rename or redescribe (5,2)'s Wall Depression so it reads differently from (3,2)'s. The first depression opens a wall — its description should emphasize the wall seam. The second concerns a bridge — its description should reference the gap, the drop, the far ledge. Players should read the object and understand *what* might be affected, even if not *how*.

Example for (5,2): *"A shallow indentation in the rock beside the gap. A mechanism, perhaps, for something that once bridged this ledge."*

**3. Move a journal-clue fragment northward**
The Tattered Journal is the only document that tells the player about the hidden key and the chest. It sits at (5,5), the deepest alcove. Add a torn page, a short inscription, or a loose note at (2,3) or (1,3) — somewhere in the natural early-exploration path — that references the prospector Aldric and mentions "the altar." Players who explore south will get the full journal; players who go north will at least have a lead.

**4. Reduce start tile exits from 7 to 4-5**
Seven exits on the first tile communicates "open world sandbox" when the zone is actually a linear tutorial with hidden structure. Removing the northwest and potentially the southwest exit from (2,2) would funnel the player into more meaningful early encounters (the Inscription to the north, the mushrooms to the northwest) without breaking access to any content.

---

### Medium Priority

**5. Give every empty corridor tile one small thing**
(1,1), (3,1), (6,1), (1,3), (6,3), (6,4) are purely atmospheric. Each needs at least one of: a small item (a coin, a shard, a scrap of cloth), an interactive detail (a crack to peer through, a sound to identify), or a navigational landmark. Not gameplay-critical — but a cave where every empty room is atmospherically distinct feels explored rather than padded.

**6. Signal Ferdie's interactivity in the tile description**
"A small creature watches, tail flicking" doesn't signal that this is an NPC you can `talk` or `pet`. Replace "a small creature watches" with something that places the mynx slightly above furniture — a held gaze, a responding gesture, something that implies awareness of Jean's presence. New players need the tile description to carry the hint that interaction is possible.

Example: *"A small, sharp-eyed creature perches at the ledge edge, flicking its tail. It turns to watch as you approach — not alarmed, just waiting."*

**7. Add an atmospheric transition tile between cave interior and ledge**
The move from cave tile (3,2) to rock ledge (4,2) jumps from enclosed stone to open sky with no transition. One tile describing increasing light, the sound of water growing louder, a smell of outside air — would make the ledge feel earned rather than sudden.

**8. Give the southern alcove (5,5) a stronger anchor description**
The remains of Aldric deserve better ceremony in the tile description. Currently: "a sense of nostalgic sadness, or perhaps weariness, which hangs in the air like a faded tapestry adorns the wall of a dusty attic." The simile is strained and abstract. The space should feel specific — as if the stone remembers the man who died here.

Example direction: describe the alcove as a closed place — low ceiling, no through-draft, the kind of corner a man would choose to rest in if he had no better options. Make the reader feel what Aldric felt in his last days.

**9. Strip Ferdie's loot table**
`friend: true`, `damage: 0`, `combat_range: [0,0]`. Ferdie cannot be fought. The loot table (Gold, Restorative, Equipment_0_1) is a copy-paste artifact that is never reachable. Remove it to avoid confusion in combat debug tools.

---

### Nice-to-Have

**10. Add one Jean-specific intrusion at the start tile or altar**
Per the memory fragment system in `chapter-summaries.md`, early location-based memory triggers should fire at domestic-adjacent spaces (a hearth, an altar, anything that rhymes with home). The altar at (2,2) — a place of ritual, of prayer, of kneeling — is exactly the kind of space where Jean's devotional life might surface. A brief memory flash on first entry (a candle, a Sunday morning, Amelia's voice) would make the start tile resonate beyond "you woke up here."

**11. Distinguish blocked exits with environmental detail**
Several blocked exits have no explanation in the tile description (e.g., (6,1) southwest blocked, (7,1) southwest blocked). If a passage is impassable, the description should say why — a rockfall, a narrow crack too tight to pass, a drop with no way up. Blocked exits without environmental justification feel like invisible walls.

**12. Name the map internally**
The BGM key is `"dark_grotto"` and the file is `dark-grotto.json` but the map has no player-facing name. When Jean first enters or when the UI displays the area, there should be a title. Consider a name that reflects Jean's psychological state on entry rather than just the geography: something like *"The Waking Dark"* or simply *"Dark Grotto"* displayed on transition. This is frontend work but worth flagging.

---

## Before/After: Key Tile Comparisons

### (2,2) Start Tile — Description

**Before**:
> This space is like dawn breaking over forgotten stone. A shaft of silver light pierces the darkness above, illuminating an altar of cold rock. Ancient dust swirls in the beam, whispering of secrets buried in shadow. The cavern breathes around you; alive, patient, waiting for you to take your first step into whatever lies beyond the light's reach.

**After** (proposed):
> A shaft of silver light falls from somewhere above onto an altar of cold rock, loose stones heaped at its base as though piled there by deliberate hands. Ancient dust turns slowly in the beam. The cavern breathes; alive, patient — waiting. Beyond the light, the dark holds its shape and gives nothing away.

*Changes*: Adds physical search affordance ("loose stones heaped at its base"), trims overwrought prose ("like dawn breaking"), keeps the breathing-cave atmosphere intact.

---

### (5,2) Wall Depression Object — Description

**Before**:
> A small depression in the wall. You may be able to PRESS on it.

**After** (proposed):
> A shallow indentation in the rock, positioned beside the gap where the ledge ends. Something mechanical, perhaps — built to bridge what the stone cannot. You may be able to PRESS it.

*Changes*: Differentiates from (3,2)'s depression, implies what pressing it *does* without stating it outright.

---

### (5,5) Southern Alcove — Tile Description

**Before** (condensed):
> ...a sense of nostalgic sadness, or perhaps weariness, which hangs in the air like a faded tapestry adorns the wall of a dusty attic.

**After** (proposed):
> The floor sags in a shallow basin where colder air pools. A faint, steady drip marks time without counting it. This place feels chosen — the low ceiling, the closed curve of stone, the corner where a man might set his back to the rock and face the dark for the last time. The quiet here is different from the quiet elsewhere. It keeps a shape.

*Changes*: Removes the strained tapestry simile. Embeds the presence of Aldric without naming him. "The corner where a man might set his back to the rock" directly echoes the remains description ("leaning against the rock wall") so the tile and the object feel continuous.

---

## Implementation Priority

| Priority | Item | Effort |
|----------|------|--------|
| High | Add search affordance to (2,2) description | Trivial — description edit |
| High | Differentiate Wall Depression at (5,2) | Trivial — description edit |
| High | Move clue about key/chest to northern path | Low — add small object to (2,3) or (1,3) |
| High | Reduce (2,2) exits from 7 to 5 | Low — remove 2 exit entries |
| Medium | Give each empty corridor tile one detail | Medium — 6 tiles to update |
| Medium | Signal Ferdie's interactivity in tile description | Trivial |
| Medium | Add cave→ledge transition tile | Medium — new tile + exits |
| Medium | Rewrite (5,5) alcove description | Trivial |
| Medium | Strip Ferdie's loot table | Trivial |
| Nice-to-have | Add memory fragment trigger at altar | Depends on event system |
| Nice-to-have | Explain blocked exits in descriptions | Low — spot description edits |
| Nice-to-have | Player-facing map name | Frontend work |

---

## Summary

The Dark Grotto is solid atmospheric work that hasn't yet committed to being a designed experience. The writing quality is consistently good; the structural logic is inconsistent. The core puzzle loop (find key → open chest) is broken by discovery order: new players will hit the chest, fail, and not know why, because the journal clue is buried at the end of the least-likely-explored corridor.

The most urgent fixes are mechanical: add a search affordance to the start tile, differentiate the two Wall Depressions, and move a clue fragment into the early exploration path. The atmospheric fixes are secondary but will make the grotto feel like a *place* rather than a collection of well-written cave rooms.

The lore potential is genuinely high. The scripture inscription, the dead merchant's journal, Ferdie on the ledge with daylight — these are the right notes. They just need structural support so players actually find them.
