# Eastern Descent — Map Design Document

**Map ID:** `eastern-descent`
**Region:** Eastern Approach
**File:** `src/resources/maps/eastern-descent.json`
**Tile Count:** 35
**Chapter:** 3 (opening zone)
**Player Level Range:** 4–7
**BGM:** TBD (transitional — mountain cold giving way to open air)

---

## Executive Summary

The Eastern Descent is the rocky mountain slope Jean traverses immediately after Grondia's Eastern Gate closes behind him. It is the first open-air map of Chapter 3 — the exhale after the enclosed Golemite city, and the first step of the Anger arc. The route drops south through a chaotic field of boulders to the eastern bank of the river, where the nomad camp of Mara, Devet, and Liss offers rest and resupply before the crossing west.

Gorran joins Jean's party permanently at the end of Chapter 2. He walks here for the first time as a companion. He does not speak. Jean notices.

The map has two layers: the **main path** (a winding south-descending trail that curves toward the river) and the **labyrinth** (a maze of boulder-cut nooks that rewards exploration with enemies, stashes, and two lore finds). A stubbed exit east — the road to the Resolute Plains — is sealed by a repeating narrative event. Jean is not going that way.

---

## Design Philosophy

**Grief Stage:** The very opening of Chapter 3 (Anger). Jean has defeated the King Slime and returned to Votha Krr. The mountain exerts a last claim as he departs — cold air, uneven ground, nothing assured. The open sky after Grondia's stone halls should feel enormous and slightly disorienting. This map is Jean taking his first breath outside.

**Tone:** Raw, exposed, territorial. Wind and loose rock. The smell of lichen and cold stone giving way, slowly, to earth and grass as the descent progresses. The boulder maze is maze-like by design — a player who pushes east finds harder enemies and better rewards, but the throughline is always south.

**Progression Flow:**
- **Entry (Zone 1 — Gate Approach):** Controlled, narrative. The gate seals. Gorran's gesture. The first wide sky.
- **Upper descent (Zone 2 — Upper Boulder Field):** Rock Rumblers on familiar terrain. Branching paths open up. The labyrinth begins.
- **Mid-labyrinth (Zone 3 — Deep Labyrinth):** New enemies. The east stub. Hidden lore in the far reaches.
- **Lower slope (Zone 4 — Lower Slope):** Terrain softens. Grass breaks through scree. The river is audible before it's visible.
- **River bank (Zone 5 — Nomad Camp):** Mara, Devet, Liss. Warmth, smoke, human voices after stone and wind.

**Reward Structure:**

| Type | Location | Contents |
|------|----------|----------|
| Small cache | The Tilted Slab (4,1) | 15–25 gold + minor provision |
| Small cache | The Rain Catch (3,2) | Provisions only |
| Small cache | The Moss Shelf (1,3) | Herb or minor item |
| Medium cache | The Far Reach (5,3) | 30–50 gold + equipment item |
| Lore 1 | The Waymarker Stone (3,0) | Golemite inscription (wall carving) |
| Lore 2 | The Far Reach (5,3) | Weathered merchant's satchel (document item) |

---

## Zone Overview

### Map Grid

```
X→   0        1        2        3        4        5
Y↓ ┌──────────────────────────────────────────────────┐
0  │ [GTE]   [RDG]   [WBK]   [WMK]   [CRW]   [PRC]  │  ← Zone 1
1  │ [SW1]   [UB1]   [UB2]   [UB3]   [UB4]   [UB5]  │  ← Zone 2
2  │ [DES]   [MB1]   [MB2]   [MB3]   [ETH]  [EST*]  │  ← Zone 2/3
3  │ [BND]   [MB4]   [MB5]   [MB6]   [DCK]   [FAR]  │  ← Zone 3
4  │ [FOT]   [LS1]   [LS2]   [LS3]   [LS4]   [ASH]  │  ← Zone 4
5  │ [BNK]   [RV1]  [RV2†]  [RV3]   [RV4]   [---]  │  ← Zone 5
   └──────────────────────────────────────────────────┘

* EST (5,2) — East Stub. Repeating event fires on entry; player returned west to (4,2).
† RV2 (2,5) — Main nomad camp tile. Mara and Devet present.

Main path:    (0,0)→(0,1)→(0,2)→(0,3)→(0,4)→(0,5)→(1,5)→(2,5)
East stub:    ...→(3,2)→(4,2)→(5,2) [event fires; player returned to (4,2)]
Far reach:    ...→(4,3)→(5,3)→(5,4)
```

### Zone Summary

| Zone | Name | Tiles | Encounters | Notes |
|------|------|-------|------------|-------|
| 1 | Gate Approach | 6 | None | Narrative; Gorran gesture; first sky |
| 2 | Upper Boulder Field | 10 | Rock Rumblers ×2 | Maze entry; first side paths |
| 3 | Deep Labyrinth | 10 | Talus Hounds ×3, Scarp Adders ×2 | East stub; Lore 1 & 2 |
| 4 | Lower Slope | 6 | Scarp Adder ×1 | Terrain softens; river audible |
| 5 | Nomad Camp | 5 | None | Mara, Devet, Liss; rest/resupply |

**Total: 35 tiles**

### Connection Map

Main path connections (N↔S along column 0, then E along row 5):
```
(0,0)↔(0,1)↔(0,2)↔(0,3)↔(0,4)↔(0,5)↔(1,5)↔(2,5)↔(3,5)
```

East-west connections from main path into boulder field (per row):
```
Row 1: (0,1)↔(1,1)↔(2,1)↔(3,1)↔(4,1)↔(5,1)
Row 2: (0,2)↔(1,2)↔(2,2)↔(3,2)↔(4,2)↔(5,2)[stub]
Row 3: (0,3)↔(1,3)↔(2,3)↔(3,3)↔(4,3)↔(5,3)
Row 4: (0,4)↔(1,4)↔(2,4)↔(3,4)↔(4,4)  (5,4) via (5,3)↓
```

North-south connections within boulder field (selective — not every cell connects):
```
Col 1: (1,0)↔(1,1)↔(1,2)↔(1,3)↔(1,4)↔(1,5)
Col 2: (2,0)↔(2,1)↔(2,2)↔(2,3)↔(2,4)↔(2,5)
Col 3: (3,0)↔(3,1)↔(3,2)↔(3,3)↔(3,4)↔(3,5)
Col 4: (4,0)↔(4,1)↔(4,2)↔(4,3)↔(4,4)
Col 5: (5,0)↔(5,1)↔(5,2)[stub],  (5,3)↔(5,4)
```

**Blocked/absent connections (large boulders):**
- No direct (1,2)↔(1,3) — boulders force detour through (0,2)/(0,3)
- No direct (2,3)↔(2,4) — scree drop; must go via (1,3)↔(1,4) or (3,3)↔(3,4)
- No direct (4,4)↔(4,5) — steep bank; lower slope meets river only via col 0–3
- (5,2) has no south exit — the stub is a dead-end finger with the event

---

## Room-by-Room Specifications

### Zone 1 — Gate Approach

---

#### (0,0) Grondia's Eastern Gate

**Exits:** W → [Grondia], S → (0,1), E → (1,0)

**Description:**
> The mountain air hits without warning — cold, thin, carrying the smell of raw stone and something older than either. Behind Jean, the Eastern Gate of Grondia has drawn itself shut: a slow grinding of counterweights that finishes with a sound like a word being swallowed. The rock face here is dressed stone giving way to undressed rock within a few paces. A worn path descends south along the bluff's edge.

**Objects:** None.

**Event:** `GorranGestureEvent` — one-shot narrative event. Fires once on first entry when Jean arrives from the west (from Grondia). Text:

> *Gorran pauses at the gate as it seals. His palm rests flat against the stone — one breath, maybe two. Then he turns without a word and follows.*
>
> *Jean does not ask him.*

**Implementation note:** Does not repeat. Fires only when the player's previous tile was the Grondia Eastern Gate. Should not fire on re-entry from the south.

---

#### (1,0) The High Ledge

**Exits:** W → (0,0), E → (2,0), S → (1,1)

**Description:**
> A narrow ledge of pale grey rock juts east from the gate bluff, swept clean by the wind that funnels up the mountain's eastern face. The sky is enormous here — a shock after weeks of stone ceilings. Far below and to the south, the land is visible: a dark river threading through pale ground, and beyond it, nothing defined yet.

**Encounters:** Rock Rumbler ×1. Territorial; present at the ledge's east end, near the drop to (1,1).

**Notes:** First encounter on the map. Re-introduces the Rock Rumbler from Dark Grotto in new context. Sparse; no reinforcements.

---

#### (2,0) The Windbreak

**Exits:** W → (1,0), E → (3,0), S → (2,1)

**Description:**
> Two boulders the size of cart horses lean against each other, forming a rough shelter where the constant wind off the peak cannot follow. The ground between them is scoured clean. Someone — something — has slept here: a dark stain on the lee-side rock that might be old fire, might be older.

**Encounters:** None. Breathing room between Rock Rumbler and the Waymarker.

---

#### (3,0) The Waymarker Stone

**Exits:** W → (2,0), E → (4,0), S → (3,1)

**Description:**
> A boulder taller than Jean stands alone at a widening in the path, as though placed rather than fallen. Its south face has been worked — not carved with skill, but with patience. Marks run in a vertical column down the stone: angular, deliberate.

**Objects:** `WallInscription` — **"Carved Stone Marker"** (Lore Reward 1)

- `description`: "The marks are Golemite script — older than the current Ecumerium district by at least two generations, if Jean's rough reading is right. It names this point *Veth Orak* — 'the eastern watch.' Below the name, a tally: forty-three vertical strokes in groups of five, then a single horizontal slash. Forty-four rotations of the watch, then nothing. At the bottom, a single glyph Jean doesn't recognize — it looks like the Golemite symbol for *door*, but inverted."
- `idle_message`: "Marks have been cut into the stone's south face."
- `keywords`: ["read", "examine", "look"]
- `hidden`: false

**Notes:** The inverted-door glyph is a detail to leave unexplained — a seed, not a payoff.

---

#### (4,0) Crow's Perch

**Exits:** W → (3,0), E → (5,0), S → (4,1)

**Description:**
> The path narrows to a ledge barely wide enough for two abreast, the drop on the south side steeper here than anywhere above. A cluster of large black birds occupy the rock above, watching with no particular urgency. Their droppings have whitened the stone below their roost. The smell is sharp.

**Encounters:** None. Atmospheric only.

---

#### (5,0) The Precipice

**Exits:** W → (4,0), S → (5,1)

**Description:**
> The ledge ends in open air. There is no path east — the mountain face drops away in a sheer crack, the bottom invisible. But standing here and looking south and southeast, the land below is laid out without obstruction: the boulder field filling the slope, the dark thread of the river, and beyond, so far it might be cloud, the pale open expanse of the Resolute Plains.

**Encounters:** None. Dead end east. Panorama payoff.

---

### Zone 2 — Upper Boulder Field

---

#### (0,1) The First Switchback

**Exits:** N → (0,0), S → (0,2), E → (1,1)

**Description:**
> The main path bends here, forced south by a shelf of rock that angles across the slope. The ground is loose: flat stones stacked by frost and time, shifting underfoot. The boulder field begins in earnest to the east — shapes too large and too numerous to count, crowded together with narrow dark passages between them.

---

#### (1,1) The Boulder Gate

**Exits:** N → (1,0), W → (0,1), E → (2,1), S → (1,2)

**Description:**
> Two boulders flank the only clear passage east — not a gate anyone built, but one the mountain made. The rock faces on either side are close enough that pack and shoulders brush both at once. Beyond, the maze opens into irregular chambers of stone.

---

#### (2,1) The Scree Shelf

**Exits:** N → (2,0), W → (1,1), E → (3,1), S → (2,2)

**Description:**
> A wide shelf of loose flat stones tilts gently southward — the accumulated wreckage of a larger boulder that shattered at some point, its pieces spreading. The footing here is treacherous: each step shifts what's below. The scree is scored with claw marks wider than Jean's palm.

**Encounters:** Rock Rumbler ×1. Hides behind the eastern boulder cluster; charges on entry from the west.

---

#### (3,1) The Hound's Warren

**Exits:** N → (3,0), W → (2,1), E → (4,1), S → (3,2)

**Description:**
> A cluster of medium boulders has collapsed inward, forming a rough hollow at ground level — low-ceilinged, littered with old bone fragments and tufts of coarse grey fur snagged on the rock edges. The entrance faces west. The smell is animal.

**Encounters:** Talus Hound ×2. First Talus Hound encounter. One guards the entrance, one circles from the east.

---

#### (4,1) The Tilted Slab

**Exits:** N → (4,0), W → (3,1), E → (5,1), S → (4,2)

**Description:**
> A single enormous slab of grey stone leans against its neighbors at a steep angle, creating a sheltered wedge of shadow underneath. The space beneath is just large enough to crawl into. The rock face of the slab is streaked with pale mineral deposits in roughly vertical lines.

**Objects:** Hidden `Container` — **"Rocky Crevice"** (Treasure Cache 1)

- `hidden`: true, `hide_factor`: 2
- `discovery_message`: "Wedged into the darkest corner of the space beneath the slab, wrapped in oilskin that has seen better years: a small bundle."
- `idle_message`: "The shadow under the tilted slab is deep."
- `keywords`: ["search", "look under", "crawl", "check"]
- Contents: 15–25 gold + 1× Iron Ration

---

#### (5,1) The Lookout Crack

**Exits:** N → (5,0), W → (4,1), S → (5,2)

**Description:**
> A vertical crack splits the rock face here, wide enough to stand in sideways. Inside, the stone amplifies the wind into a low, sustained note. From the eastern lip of the crack, the eastern horizon is fully visible: the plains far beyond, and the road that would lead there.

**Notes:** Last tile before East Stub (5,2). Seeds the east road visually.

---

#### (0,2) The Long Descent

**Exits:** N → (0,1), S → (0,3), E → (1,2)

**Description:**
> The main path continues its long pull southward. The slope is more pronounced here; the path is worn into two shallow ruts by generations of something — Golemite scouts, animals, erosion. The boulder field crowds close on the east side. To the west, the mountain face is bare and vertical.

---

#### (1,2) The Rubble Path

**Exits:** N → (1,1), W → (0,2), E → (2,2) [south blocked — large debris]

**Description:**
> The passage between boulders here is choked with smaller rubble — the residue of older boulders worn down to knee-height chunks. Progress east or west requires careful footing. A wall of stacked debris closes the southern direction entirely.

**Encounters:** Rock Rumbler ×1 (patrolling between (1,2) and (2,2) — implementation may treat as a single encounter spanning both tiles).

**Notes:** South exit blocked. Players must use main path col 0 or detour through other tiles.

---

#### (2,2) The Hollow

**Exits:** N → (2,1), W → (1,2), E → (3,2), S → (2,3)

**Description:**
> The boulders open briefly into a rough oval clearing — not large, but large enough to see the sky directly overhead. The ground here is darker than the surrounding scree: earth and old leaf litter carried by the wind over years. Deep scratches mark the boulders on all sides at roughly hip height.

**Encounters:** Talus Hound ×2. Active territory — they patrol the clearing.

---

#### (3,2) The Rain Catch

**Exits:** N → (3,1), W → (2,2), E → (4,2), S → (3,3)

**Description:**
> A natural basin in the rock — barely the size of a wash basin — holds a few inches of standing water, cold and perfectly clear. Pale green algae lines the basin edge. A faint smell of mineral water. The mud at the basin's edge holds overlapping prints.

**Objects:** Hidden `Container` — **"Muddy Ledge"** (Treasure Cache 2)

- `hidden`: true, `hide_factor`: 3
- `discovery_message`: "Behind the basin, wedged into a crack below the waterline: a wax-sealed clay pot, still intact."
- `idle_message`: "The rock around the water basin is slick with moisture."
- `keywords`: ["search", "look", "check basin", "examine"]
- Contents: 1× Iron Ration + 1× minor provision

---

### Zone 3 — Deep Labyrinth

---

#### (4,2) The Eastern Trailhead

**Exits:** N → (4,1), W → (3,2), E → (5,2), S → (4,3)

**Description:**
> The boulders part just enough here to reveal what was once a proper trail heading east — more worn than the surrounding rock, edged on both sides by stones set deliberately in the ground, though many have shifted or sunk over time. The trail looks maintained for longer than it looks abandoned.

**Notes:** Gateway to the East Stub. The deliberately-set edging stones establish that this was a real road once — not a game trail.

---

#### (5,2) The Road East *(East Stub — Repeating Event)*

**Exits:** N → (5,1), W → (4,2) [no east exit — event intercepts before one is needed]

**Description:**
> The trail widens here into something that was, unmistakably, a road. The ground is level, the verge cleared. Ahead, the mountain's eastern shoulder drops away and the land opens — genuinely open, in a way Jean hasn't seen in weeks. The Resolute Plains begin somewhere out there in the haze. The road leads to them.

**Event:** `EasternRoadTurnbackEvent` — **repeating**. Fires on every entry. Text:

> *Jean stands at the edge of the road east.*
>
> *The Plains are out there — open ground, light, the kind of distance you could just keep walking into. For a moment the road pulls at him in a way he doesn't examine.*
>
> *Then Gorran's boots scrape gravel behind him, and whatever the feeling was, it passes.*
>
> *South. That's where this goes.*

**Mechanical effect:** On event completion, move player west to (4,2). No fight, no item cost. The east exit on this tile is present in description only — the event fires before movement resolves.

**Implementation note:** Use a repeating `SceneEvent` (or equivalent) that triggers `move_player` west on completion. This tile is intentionally unrewarding to re-enter — the event text can shorten on repeat visits if the engine supports it, but the pushback always fires.

---

#### (0,3) The Lower Bend

**Exits:** N → (0,2), S → (0,4), E → (1,3)

**Description:**
> The path bends again, this time eastward before resuming its southward fall. The slope here is steep enough that the path is cut into the hillside in a shallow ledge. A large flat rock juts from the west face like a shelf; it has been used as a seat by something — the surface is worn smooth.

---

#### (1,3) The Moss Shelf

**Exits:** N → (1,2) [blocked], W → (0,3), E → (2,3), S → (1,4)

**Description:**
> A wide horizontal surface of rock, perhaps two metres above the path, extends along the boulder face. Reaching it requires a short scramble. The surface is covered in a thick, damp moss — vivid green against the grey, incongruous this high on the slope. Something small lives in the moss; the surface is dimpled with tiny burrow-openings.

**Objects:** Hidden `Container` — **"Mossy Crack"** (Treasure Cache 3)

- `hidden`: true, `hide_factor`: 3
- `discovery_message`: "In a crack running along the base of the moss shelf: a small bundle, damp but intact. Someone left this deliberately — the crack is too regular to be accidental."
- `idle_message`: "The moss surface is cool and dense underfoot."
- `keywords`: ["search", "look", "check", "climb"]
- Contents: 1× herb (e.g., Bitterroot or equivalent restorative ingredient) + minor gold (5–10)

**Notes:** North exit to (1,2) blocked by debris — consistent with (1,2)'s south being blocked.

---

#### (2,3) The Nest Hollow

**Exits:** N → (2,2), W → (1,3), E → (3,3), S → (2,4) [blocked — scree drop]

**Description:**
> A low hollow beneath an overhang, barely deep enough to shelter in. The floor is dry and pale — shed scales, dozens of them, layered over each other in the dust. The scales are large: each one roughly the size of a playing card, dark grey with silver edges that catch the light at certain angles.

**Encounters:** Scarp Adder ×1. Ambush — the adder is coiled motionless against the back wall of the hollow. Awareness check required; players who do not notice it are struck first.

**Notes:** The shed scales remain after combat — durable evidence of habitation. South blocked (scree drop); must detour.

---

#### (3,3) The Den Rock

**Exits:** N → (3,2), W → (2,3), E → (4,3), S → (3,4)

**Description:**
> A massive boulder sits apart from its neighbors, with a cleared space around it on all sides. The ground near the boulder is heavily disturbed — earth churned up, smaller rocks displaced, a shallow scrape-pit worn into the dirt on the western side. It smells strongly of musk.

**Encounters:** Talus Hound ×3. Pack leader + two. Largest Talus Hound encounter on the map; most challenging group fight.

**Notes:** The scrape-pit is a territorial marking behavior — durable after encounter.

---

#### (4,3) The Deep Crack

**Exits:** N → (4,2), W → (3,3), E → (5,3), S → (4,4)

**Description:**
> A deep vertical crack runs through the rock here — not wide enough to enter, but deep enough that no light reaches the bottom. The crack smells faintly of sulfur, or something like it. The rock around the crack's edges is slightly discoloured — a pale orange band, as though heat once passed through here.

**Encounters:** Scarp Adder ×1. Emerges from the crack itself — the adder uses the crack as a den. Ambush on entry if player fails awareness.

**Notes:** The discolouration and sulfur smell are durable environmental details.

---

#### (5,3) The Far Reach

**Exits:** W → (4,3), S → (5,4)

**Description:**
> The easternmost point accessible on this slope — a narrow platform of rock where the boulder maze butts up against the raw cliff face, creating a dead end open to the sky. Wind moves through constantly. At the base of the cliff face, a dark gap suggests a shallow recess, large enough to have sheltered someone.

**Objects:**

1. Hidden `Container` — **"Shallow Recess"** (Treasure Cache 4 + Lore Reward 2)

   - `hidden`: true, `hide_factor`: 2
   - `discovery_message`: "Inside the recess: a merchant's satchel, leather cracked but intact. The contents have survived in better condition than the bag."
   - `idle_message`: "The base of the cliff face is in shadow."
   - `keywords`: ["search", "look", "check recess", "examine gap"]
   - Contents: 30–50 gold + 1× equipment item (implementor's choice — minor weapon or armour upgrade appropriate to Ch3 opening) + **"Merchant's Journal Fragment"** (document item, see below)

2. **"Merchant's Journal Fragment"** — document/readable item

   - Read text: *"— reached the eastern slope without incident. The gate Golemites do not turn away anyone carrying legitimate cargo, but they ask questions I am not yet comfortable answering. I have decided to camp here tonight rather than seek the gate tomorrow. The view is clear enough to watch the pass for movement.*
   *The creatures on this slope are more organized than I expected. The serpents in particular — I watched one this afternoon from this vantage point. It was not hunting. It was waiting. There is a difference. I will note the observation and move on in the morning.*
   *If you are reading this and I am not present: the gate is three hours north. The river is two hours south. The people at the river camp are decent. Tell Mara I said so."*

**Notes:** The merchant is not named and their fate is not stated. The journal's pragmatic tone and the implication they never returned are the entire payoff — do not add more context. Scarp Adder behavior note (waiting, not hunting) seeds lore without requiring a quest.

---

### Zone 4 — Lower Slope

---

#### (0,4) The Footing

**Exits:** N → (0,3), S → (0,5), E → (1,4)

**Description:**
> The gradient eases here — not flat, but no longer the lean-into-it effort of the upper slope. The rock underfoot gives way to packed earth threaded through with root systems. To the east, the boulders are smaller and more scattered, like a field thinning out. The sound of water is just barely present — more felt than heard.

---

#### (1,4) The Grass Break

**Exits:** N → (1,3), W → (0,4), E → (2,4), S → (1,5)

**Description:**
> The first real grass of the descent: not the isolated tufts that appear in crevices higher up, but a proper spread of it, ankle-high and wind-bent. It grows in the spaces between the remaining boulders, which are now sparse enough to walk between without effort. The colour is vivid after so much grey.

---

#### (2,4) The Lower Field

**Exits:** N → (2,3) [blocked — scree drop], W → (1,4), E → (3,4), S → (2,5)

**Description:**
> A broad, roughly level stretch of mixed ground — grass and exposed rock in roughly equal parts. Boulders are present but isolated, no longer a maze. The slope is gentle enough here that the river is now visible to the south as a definite dark line through lighter ground.

---

#### (3,4) The River Outlook

**Exits:** N → (3,3), W → (2,4), E → (4,4), S → (3,5)

**Description:**
> From this slightly elevated point the river is clearly visible — wide, dark-edged, moving. The sound reaches here: low, constant, without particular urgency. On the near bank, small shapes that might be structures are visible. The smell of water and woodsmoke is faint but distinct.

**Notes:** First tile where woodsmoke from the nomad camp is detectable. Foreshadows Zone 5.

---

#### (4,4) The Final Slope

**Exits:** N → (4,3), W → (3,4)

**Description:**
> The slope ends here in a steep short drop to the bank below — not climbable without finding another route. Looking south, the river bank is visible and close, but the descent requires doubling back west to the main path. Looking north, the full extent of the boulder field is visible from below: more vast than it seemed from inside.

**Notes:** Dead end south (no direct drop to river bank). Forces players back to main path to reach Zone 5.

---

#### (5,4) The Adder's Shelf

**Exits:** N → (5,3)

**Description:**
> A narrow shelf of rock, cut off from the lower slope by the same steep drop that closes the southeast corner of the mountain. The shelf is warm — it faces south and catches the sun for most of the day. Coiled things have been here: smooth depressions in the dust, old shed skins draped over a low rock like discarded clothing.

**Encounters:** Scarp Adder ×1. Basking. Less aggressive than the ambush variants above — initiates combat only if the player moves adjacent, but engages immediately.

**Notes:** Dead end north leads only back to (5,3). The warm south-facing aspect and the shed skins are durable details.

---

### Zone 5 — Nomad Camp

---

#### (0,5) The Bank Approach

**Exits:** N → (0,4), E → (1,5)

**Description:**
> The slope levels completely. Underfoot is soft river-bottom soil, damp at the edges where the bank floods seasonally. A rough track leads east — wide enough for a cart, though no cart has been through recently. The river is audible but not yet visible past the bank's low rise.

---

#### (1,5) The Eastern Bank

**Exits:** N → (1,4), W → (0,5), E → (2,5)

**Description:**
> The riverbank proper: a shelf of packed gravel and dark earth dropping perhaps a metre to the water's edge. The river itself is wide — thirty metres or more — moving with a low, unhurried strength. The water is cold-looking, grey-green, carrying occasional debris. On the far bank, the land is dark and different: lower, flatter, the beginning of something else entirely.

**Notes:** First direct river view. The far bank description should evoke difference — the Wailing Badlands lie beyond. Do not name them here.

---

#### (2,5) The Nomad Camp

**Exits:** N → (2,4), W → (1,5), E → (3,5)

**Description:**
> The camp occupies a natural hollow in the bank — sheltered from the prevailing wind, with a clear sightline upstream. The shelters are lean-tos of oiled canvas over light poles, practical to a degree that suggests long use. A fire ring sits at the centre, its stones black with years of use. The smell of woodsmoke and dried meat is warm and immediate after hours of cold rock.

**NPCs:** Mara (scavenger/ferry operator), Devet (cook). See NPC Stubs section.

**Notes:** Main camp tile. Rest and resupply available here (Devet provides food/healing; Mara provides information and passage). Tile description does not reference NPCs directly — it describes the durable camp infrastructure.

---

#### (3,5) The Camp's Edge

**Exits:** W → (2,5)

**Description:**
> The camp's east edge is defined by a line of larger stones arranged in a rough semicircle — a windbreak or boundary marker, well-established. Beyond it, the bank continues east, empty and featureless. A low post has been driven into the ground here; on it hangs a small wooden shape on a cord, turning slowly in the river wind.

**NPCs:** Liss (young, curious). See NPC Stubs section.

**Notes:** Dead end east — the camp does not extend further. The wooden shape on the post is not explained; it is a camp marker or talisman, durable regardless of Liss's presence.

---

#### (4,5) The River's Bend

**Exits:** N → (4,4) [blocked — steep bank], W → (3,5)

**Description:**
> The river curves here, and the bank curves with it. Looking west, the full width of the crossing is visible — the far bank seems both close and impossibly far. Looking north, the mountain's eastern face rises steep and bare: the slope just descended, seen all at once. A flat rock at the water's edge has been worn glass-smooth by seasonal flooding.

**Future exit:** W → [River Crossing] (stub — exit present in JSON but leads nowhere; `block_exit: ["west"]` or equivalent with description "The crossing lies west, where the ferry makes its runs.")

**Notes:** Westward river crossing is future content. This tile gives Jean (and the player) a moment to look back at the mountain and forward at the river simultaneously — a natural breathing point before the Chapter 3 journey continues.

---

## New Enemy Designs

### Talus Hound

**Class name:** `TalusHound`
**Lore name:** "Talus Hound"

**Appearance:**
A lean, shaggy quadruped roughly the size of a large dog. Its hide is layered — thick, close-lying fur over a leathery undercoat — in mottled grey-brown tones that blend almost perfectly with scree and boulder faces at rest. Its legs are heavily muscled for explosive bursts on rough terrain. The head is broad and low-set, with pale amber eyes adapted for detecting movement at distance. Its ears are small and flat; its jaw is disproportionately wide. At rest, pressed to rock, it is nearly invisible.

**Behaviour:**
Territorial pack hunter. Hunts in groups of 2–3; will not engage alone if outnumbered and can see an escape route. Circles prey before committing to attack, attempting to flank from multiple angles. Retreats when bloodied below ~30% HP if a pack mate is already dead. Does not pursue far beyond its territory.

**Combat profile:**

| Stat | Value |
|------|-------|
| HP | 45–55 |
| Damage | 12–16 |
| Protection | 8 |
| Awareness | 30 |
| XP Award | 80 |

**Moves:** `NpcAttack`, `Advance`, `Withdraw`, `Flank`

- **Flank:** If a second Talus Hound is active in the same combat, this hound gains +3 damage and +5 evasion on its next attack. Activates once per combat. Reflects pack coordination — the flanking hound strikes while the other draws attention.

**Resistances:** Moderate blunt/slashing resistance (thick hide); low fire resistance; standard piercing.

**Drops:** Rough Hide (crafting material, common), small gold (5–15).

**Lore note:** Talus Hounds are not native to the mountain's interior — they are creatures of the open slope, and their presence on the eastern face suggests the Golemite patrols that once kept this area clear have long since ceased. They are not malicious; they are territorial. Jean's intrusion into the warren at (3,1) is the provocation, not some innate aggression.

---

### Scarp Adder

**Class name:** `ScarpAdder`
**Lore name:** "Scarp Adder"

**Appearance:**
A thick-bodied serpent, 1.5–2 metres in length. Its scales are layered like flakes of split shale — dark grey with silver edges that catch the light only when the creature moves. The head is broad and triangular, with heat-sensing pits on either side of the jaw. Its tongue is pale blue. At rest in a rock crevice, coiled with its head tucked, a Scarp Adder is functionally invisible.

**Behaviour:**
Ambush predator. Entirely solitary. Selects a position and remains motionless until prey enters strike range; does not track, stalk, or pursue at distance. Once threatened or hungry, strikes with immediate aggression. If the first strike lands, it may follow with venom. If struck hard in return, it coils defensively. It will withdraw from sustained combat rather than fight to the death — a wounded adder retreating into a crack is a warning, not a surrender.

The merchant's journal observation is accurate: Scarp Adders demonstrate patience that looks purposeful. Whether this reflects intelligence or pure instinct is left open.

**Combat profile:**

| Stat | Value |
|------|-------|
| HP | 35–40 |
| Damage | 18–22 (first strike); 12–15 (subsequent) |
| Protection | 5 |
| Awareness | 40 (ambush only — does not patrol) |
| XP Award | 95 |

**Moves:** `NpcAttack`, `VenomStrike`, `Coil`, `Withdraw`

- **VenomStrike:** Applies `Poisoned` status (DoT, 3–5 damage per turn for 3 turns). Uses on second combat action if first strike landed, or as opening move if not ambushing. Cooldown: once per combat.
- **Coil:** Defensive stance — increases evasion by 15 for one turn. Used when HP drops below 40%.

**Resistances:** Low physical resistance (fragile — scales do not protect well); slight resistance to earth/physical magic (elemental affinity with rock).

**Drops:** Scarp Scale (crafting material, rare — 1–2 per adder), Adder Venom Sac (ingredient — use in poison or antidote crafting; implementation pending item system support).

**Awareness/ambush implementation note:** Scarp Adders should not be visible or announced on tile entry. They require an awareness/perception check (using Jean's relevant stat) to detect before engagement. On failure, the adder acts first with `NpcAttack` at full first-strike damage. On success, Jean has the initiative. This is the intended design; do not simplify to standard encounter announcement.

**Lore note:** Scarp Adders are not aggressive in the conventional sense — they do not chase, claim territory, or hunt in packs. They are patient. Their presence on the eastern slope is old; they have always been here. The Golemite watch marker at (3,0) predates them by unknown generations, but the adder at (5,4) has been basking on that shelf for longer than the marker has been unread.

---

## NPC Stubs — Nomad Camp

The following NPCs are drawn from the existing Eastern Approach profile. Full dialogue and quest hooks are out of scope for this document; stubs are provided for implementation placement.

---

### Mara

**Tile:** (2,5) The Nomad Camp
**Role:** Scavenger, ferry operator
**Personality:** Practical, watchful, not unfriendly. Treats strangers as potential cargo and potential trouble in roughly equal measure until proven otherwise.

**Dialogue hooks:**
- Offers river crossing (raft, fee TBD by economy system)
- Can provide information about what lies west (vague; she crosses but doesn't linger)
- References "the merchant who came through once" if Lore 2 journal has been found — acknowledges knowing them, does not elaborate

**Implementation note:** Mara should have a trade/service interaction in addition to dialogue. Exact fee and raft mechanic are deferred to river crossing implementation.

---

### Devet

**Tile:** (2,5) The Nomad Camp
**Role:** Camp cook
**Personality:** Older. Unhurried. Speaks less than Mara but asks better questions.

**Dialogue hooks:**
- Provides food/healing service (hot meal — restores HP or removes fatigue status if implemented)
- Asks where Jean has come from; reacts to "Grondia" with mild interest ("Stone city. Mara says the gate's been shut more than open lately.")
- Does not pry further

---

### Liss

**Tile:** (3,5) The Camp's Edge
**Role:** Young camp member, curious
**Personality:** Young adult. Fascinated by travellers. Asks questions Devet would not.

**Dialogue hooks:**
- Asks about Jean's sword, the crest on his armour, or Gorran (whichever is most visually distinctive)
- Will mention having seen "the big hounds" on the slope recently — corroborates Talus Hound presence without breaking fourth wall
- Potential future quest hook (errand, message delivery, or minor item fetch — TBD)

---

## Asset Needs & Dependencies

### New assets required

| Asset | Type | Status |
|-------|------|--------|
| `TalusHound` | NPC class in `npc.py` | New — design in this document |
| `ScarpAdder` | NPC class in `npc.py` | New — design in this document |
| `VenomStrike` move | Move in `moves.py` | New — applies `Poisoned` DoT |
| `Coil` move | Move in `moves.py` | New — temporary evasion buff |
| `Flank` move | Move in `moves.py` | New — conditional damage/evasion bonus |
| `Poisoned` status | Status in `states.py` | Likely exists; verify and reuse |
| `ScarpScale` | Item in `items.py` | New crafting material |
| `AdderVenomSac` | Item in `items.py` | New ingredient item |
| `RoughHide` | Item in `items.py` | New crafting material |
| `MerchantJournalFragment` | Item/document in `items.py` | New readable item |
| `eastern-descent.json` | Map file in `src/resources/maps/` | New |
| `GorranGestureEvent` | Event class | New one-shot narrative event |
| `EasternRoadTurnbackEvent` | Event class | New repeating scene + move event |

### Dependencies on existing systems

- **Gorran companion:** Must be added to Jean's party before this map is loaded. Verify party system supports permanent companion display.
- **Awareness/ambush:** Scarp Adder ambush requires a perception/awareness check at tile entry. Verify this mechanic exists or stub it.
- **`Poisoned` DoT status:** Check `states.py` — if a venom/poison status exists, reuse it. If not, create it.
- **River crossing stub:** (4,5) has a westward exit stub. Use `block_exit: ["west"]` with a descriptive message. Do not create the crossing map in this pass.
- **Mara ferry mechanic:** Deferred. For this implementation pass, Mara's dialogue can reference the crossing without a functional raft interaction.

---

## Implementation Notes

### JSON patterns

**East Stub event tile (5,2):**
```json
"(5, 2)": {
  "id": "tile_5_2",
  "title": "The Road East",
  "description": "...",
  "exits": ["north", "west"],
  "events": [
    {
      "__class__": "EasternRoadTurnbackEvent",
      "__module__": "events",
      "props": {
        "name": "EasternRoadTurnback",
        "repeat": true,
        "has_run": false,
        "params": { "return_tile": [4, 2] }
      }
    }
  ],
  "items": [],
  "npcs": [],
  "objects": []
}
```

**Gorran gesture event tile (0,0):**
```json
"events": [
  {
    "__class__": "GorranGestureEvent",
    "__module__": "events",
    "props": {
      "name": "GorranGesture",
      "repeat": false,
      "has_run": false,
      "params": { "trigger_from": "west" }
    }
  }
]
```

**Scarp Adder ambush tile (2,3 example):**
```json
"npcs": [
  {
    "__class__": "ScarpAdder",
    "__module__": "npc",
    "props": { "ambush": true, "awareness_threshold": 25 }
  }
]
```

**Hidden container example (4,1 Tilted Slab):**
```json
"objects": [
  {
    "__class__": "Container",
    "__module__": "objects",
    "props": {
      "name": "Rocky Crevice",
      "hidden": true,
      "hide_factor": 2,
      "idle_message": "The shadow under the tilted slab is deep.",
      "discovery_message": "Wedged into the darkest corner...",
      "keywords": ["search", "look under", "crawl", "check"],
      "inventory": [
        { "__class__": "Gold", "__module__": "items", "props": { "amt": 20 } },
        { "__class__": "IronRation", "__module__": "items", "props": {} }
      ]
    }
  }
]
```

### Testing gates

Before marking implementation complete, verify:

- [ ] Player can walk main path (0,0)→(0,5)→(2,5) without obstruction
- [ ] East stub fires event and returns player to (4,2) every time
- [ ] Gorran gesture fires exactly once on first gate exit
- [ ] Both Rock Rumblers, all Talus Hound packs, and all Scarp Adders spawn correctly
- [ ] Scarp Adder ambush: adder acts first on failed awareness check
- [ ] All 4 hidden containers discoverable via keyword interaction
- [ ] Lore 2 journal readable as item after pickup
- [ ] (4,4) south exit correctly blocked (steep bank)
- [ ] (4,5) west exit stubbed with message
- [ ] Mara and Devet present at (2,5); Liss at (3,5)
- [ ] Far Reach (5,3) accessible via (4,3) east
- [ ] Adder's Shelf (5,4) accessible via (5,3) south

---

## Lore Integration Checklist

- [x] Golemite eastern watch history established (Waymarker Stone, Veth Orak)
- [x] Talus Hound presence explained as consequence of patrol lapse
- [x] Scarp Adder behavior hints at unusual intelligence (journal fragment)
- [x] East road present and tempting but not Jean's path (turnback event)
- [x] Gorran's arrival as companion marked with a quiet character moment
- [x] Nomad camp introduced with named characters and distinct voices
- [x] River crossing westward stubbed for future Chapter 3 implementation
- [x] Resolute Plains visible but out of reach — narrative and spatial both
- [x] Tile descriptions contain no present-tense NPC behaviour or item references
- [x] Durable environmental evidence used throughout (claw marks, shed scales, burn stains, bone fragments)

