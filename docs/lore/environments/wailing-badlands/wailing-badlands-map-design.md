# The Wailing Badlands — Map Design Document

## 1. Executive Summary

The Wailing Badlands are the physical and emotional manifestation of Jean's unprocessed rage, marking the Anger stage of his grief arc. This region of broken stone, wind-carved canyons, and relentless acoustic violence serves as both a literal passage between the Resolute Plains and the eastern steppes, and a psychological crucible where Jean must survive—not conquer—his fury. The environment itself is hostile, offering few respites and numerous hazards. By navigating the badlands, Jean exhausts his acute rage and begins the slow transition toward acceptance.

**Tone**: Oppressive, disorienting, acoustically violent. Visually monotonous (gray and rust palette). Emotionally: Jean is increasingly isolated, increasingly angry, increasingly aware that anger alone won't restore what he's lost.

**Lore Connection**: The badlands echo with the grief of a catastrophic Golemite failure at the Broken Gate—a failed attempt to contact the divine. Elder Korash and Mara the Scavenger are refugees living in this landscape, offering paths toward understanding rather than resolution.

---

## 2. Design Philosophy

**Intent**: Create a space where environmental hazards, acoustic design, and thematic pacing make the player *feel* the Anger stage rather than merely witnessing it. The map should be challenging but not punishing; exhausting but not soul-crushing.

**Progression Flow**:
- **Early badlands** (Shattered Spires, Ravager encounters): Introduction to hostility; navigation challenges; player learns to be cautious
- **Mid badlands** (Keening Canyon, Broken Gate): Intensity peaks; the wail is loudest; Ravager packs escalate; player feels trapped and overwhelmed
- **Late badlands** (eastern pass, hidden grotto, exits): Player adapts; encounters taper; narrative beats shift toward moving through rather than conquering
- **Breathing room** (hidden grotto in Bleeding Scar): A sanctuary moment that respects the player's emotional endurance

**Reward Structure**:
- **Small rewards** scattered through the map: provisions (food, water), lesser loot dropped by Ravagers, journal entries from past travelers
- **Medium rewards** in hazardous locations: artifacts at the Broken Gate ruins (tied to Mara's quest), unique equipment dropped by Ravager alphas
- **Major rewards**: Artifact from Elder Korash (Auditory Strain resistance), access to the hidden grotto, and narrative closure with a memory of acceptance

---

## 3. Zone Breakdown

### Zone 1: The Shattered Spires (20 tiles)
**Purpose**: Introduce the badlands' disorientation and danger. Navigation puzzle as primary mechanic; small Ravager skirmishes as secondary threat.

**Tone**: Gray stone needles reaching toward a pale sky. Wind howls but is not yet piercing. Paths are tangled; visual similarity creates a maze effect.

**Approximate Tiles**: 18–20

**Key Encounter**: Solo Ravagers or pairs; navigation puzzle (use subtle landmark cues to avoid dead ends)

**Connections**: Entry from Resolute Plains (west); exit to Keening Canyon (east/southeast)

**ASCII Layout**:
```
        W (from Plains)
        |
    ┌───┴───┐
    │ SPIRE │  North arm (dead end with small cache)
    │ MAZE  │
    └───┬───┘
        │
        E (to Keening Canyon)
```

---

### Zone 2: The Keening Canyon (25 tiles)
**Purpose**: Peak intensity. Auditory Strain is primary hazard; the wail is constant and piercing. Linear but treacherous passage; combat encounters are chaotic and frantic.

**Tone**: Narrow chasm with canyon walls rising 200+ feet. Wind funnels through, generating a high-pitched wail that distorts speech. The canyon floor is a dry riverbed with stagnant pools and loose rock.

**Approximate Tiles**: 22–25

**Key Encounter**: Ravager ambush in narrow passages; environmental hazard (wind gusts, unstable overhangs); Auditory Strain accumulation

**Connections**: Entry from Shattered Spires (west); exit to Broken Gate (southeast)

**ASCII Layout**:
```
    W ────────────────────────── E
    │                            │
    │ Narrow canyon              │
    │ Treacherous path           │
    │ Wind gusts + wail          │
    │                            │
    │ (Ravager ambush midway)    │
    │                            │
    └────────────────────────────┘
```

---

### Zone 3: The Broken Gate (15 tiles)
**Purpose**: Environmental storytelling and narrative anchor. Central location with scattered ruins, evidence of a Golemite archive, and Mara/Korash encounter opportunities.

**Tone**: Massive scattered stone blocks, some carved with half-legible inscriptions. A dry fountain basin. Silhouettes of grand architecture now broken and buried.

**Approximate Tiles**: 12–15

**Key Encounter**: Guardian of the Gate (optional boss); puzzle to recover archive records (tied to Korash quest); Mara encounter (tied to artifact collection)

**Connections**: Entry from Keening Canyon (northwest); exit to Bleeding Scar (southeast); hidden path to grotto (south, requires specific clue)

**ASCII Layout**:
```
        NW (from Canyon)
        │
    ┌───┴───────┐
    │ Scattered │
    │ ruins &   │  Archive chamber (center, with Guardian)
    │ blocks    │  Mara's camp (south)
    └───┬───────┘
        │
        SE (to Bleeding Scar)
```

---

### Zone 4: The Bleeding Scar & Hidden Grotto (20 tiles)
**Purpose**: Optional sanctuary and lore deepening. Contrast to the harshness of the main badlands; a breathing room moment.

**Tone**: Vertical cliff faces stained rust-red with mineral deposits. Hidden crevasse leading down into a pristine grotto: still water, soft light, moss, and life-signs.

**Approximate Tiles**: 15–20 (grotto itself is small; passages to reach it are the bulk)

**Key Encounter**: Puzzle to discover grotto (observation-based); sanctuary within (no combat, restoration moment)

**Connections**: Access from Broken Gate (via specific clue); hidden exit to eastern pass (north, high difficulty navigation)

**ASCII Layout**:
```
        Cliff faces (rust-red)
        │
    ┌───┴───────────────┐
    │ Crevasse passages │
    │   (puzzle)        │  Hidden grotto (center, sanctuary)
    │                   │  Still water, light, peace
    └───┬───────────────┘
        │
        N (hidden exit to eastern pass)
```

---

### Zone 5: The Eastern Pass (12 tiles)
**Purpose**: Exit corridor; transitional zone. The wail diminishes gradually; the landscape opens toward future content (Sanctuary of Illusions).

**Tone**: Narrow winding passage between spires, gradually widening. Sky visible overhead; wind becomes less focused.

**Approximate Tiles**: 10–12

**Key Encounter**: Rare solo Ravager (as a final test); mostly navigation and pacing

**Connections**: Entry from Broken Gate (direct) or from Bleeding Scar grotto (high-difficulty hidden route); exit toward Sanctuary of Illusions (east)

---

## 4. Room-by-Room Specifications

### Zone 1: The Shattered Spires

#### (1, 1) — Western Entry
**Title**: BadlandEntryPoint
**Description**: The wind changes here. Behind you, the Resolute Plains smell of grass and water. Ahead: the air tastes of dust and stone. Gray spires rise like broken teeth, and the sound—a distant keening—carries across the landscape. This is the threshold. Once you pass, the badlands claim you.

**Exits**: E, NE, SE
**Block Exits**: W (to Plains—can't go back)
**Encounters**: None
**Items**: None
**NPCs**: None
**Objects**: Waystone (inscribed with Wayfarer warning: "Turn back—this passage is folly")
**Design Notes**: Narrative anchor. Player cannot reverse back to Plains. Sets tone for irreversibility of grief's journey.

---

#### (2, 1) — Spire Maze (Start)
**Title**: EmptySpire
**Description**: Stone needles surround you, creating a claustrophobic maze despite the open sky above. Each spire looks identical: gray, weathered, slightly leaning. Moss grows on the northern faces—the only landmark. Wind here is unpredictable, sometimes gentle, sometimes sharp enough to sting exposed skin.

**Exits**: N, E, S, W
**Block Exits**: None
**Encounters**: Solo Ravager (chance to learn combat mechanics before packs); exploration puzzle (use moss as compass to avoid dead ends)
**Items**: Dried Rations (hidden, mark `hidden: true`; discovery message: "beneath loose stones, a cache of travel provisions")
**NPCs**: None
**Objects**: None
**Design Notes**: First true encounter with disorientation. Moss-on-north-side landmark is teaching moment for navigation puzzle ahead.

---

#### (3, 1) — Dead End (North Arm)
**Title**: EmptySpire
**Description**: The spire maze has led you to a narrow cul-de-sac. Stone walls rise on three sides, converging overhead. The silence here is slightly deeper than elsewhere—the wind doesn't penetrate as far. Something feels old about this place. Scratches on the wall—deliberate marks—suggest someone once sheltered here.

**Exits**: S
**Block Exits**: None
**Encounters**: None (shelter location)
**Items**: Tattered cloak (abandoned, suggests a previous traveler took shelter and moved on)
**NPCs**: None
**Objects**: Carved marks on wall (player can EXAMINE; reveals a date: "—247 years gone. Still here." Thematic: speaks to the badlands' eternal nature)
**Design Notes**: Safe room. Rewards careful exploration. Environmental storytelling.

---

#### (2, 2) — Spire Maze (Central)
**Title**: EmptySpire
**Description**: You've circled back to what feels like a familiar passage. Or is it? Every spire is the same. The wind here pulls from multiple directions, creating eddies and strange currents. You feel untethered.

**Exits**: N, E, S, W, NE, NW, SE, SW
**Block Exits**: SW (recent landslide blocks this exit)
**Encounters**: Ravager pair (emerges from NW); navigation decision (which exit to take?)
**Items**: None
**NPCs**: None
**Objects**: Fallen boulder (blocks SW exit; player can observe it's recent)
**Design Notes**: Central hub. Multiple exits create illusion of choice but most lead in circles. Encourages use of moss-compass strategy. Combat here is tight due to boulder obstacles.

---

#### (3, 2) — Spire Maze (Eastern Exit)
**Title**: EmptySpire
**Description**: The spires begin to open. The maze is loosening its grip. Ahead, the sound changes—a sharper, more focused wail. The canyon approaches.

**Exits**: W, E
**Block Exits**: None
**Encounters**: None (transition tile)
**Items**: None
**NPCs**: None
**Objects**: None
**Design Notes**: Bridge between Shattered Spires and Keening Canyon. No encounter; player should feel relief (maze is solved) mixed with apprehension (canyon awaits).

---

### Zone 2: The Keening Canyon

#### (4, 2) — Canyon Entry
**Title**: CanyonEntrance
**Description**: The chasm drops before you with sudden, vertiginous force. Walls of rust-stained stone rise 200 feet overhead. The air screams. A high-pitched wail funnels through the canyon, so loud it seems to vibrate your bones. Breathing becomes deliberate. Speaking is nearly impossible. The canyon floor—a dry riverbed scattered with smooth stones and stagnant pools—is your path.

**Exits**: E, W
**Block Exits**: None
**Encounters**: Ravager ambush (2–3 Ravagers emerge from alcoves); Auditory Strain begins to accumulate
**Items**: None
**NPCs**: None
**Objects**: None
**Design Notes**: Peak intensity entry. Auditory Strain condition introduced here. Prose emphasizes the *sound* as a character—inescapable, oppressive, disorienting.

---

#### (5, 2) — Canyon Passage (Mid)
**Title**: CanyonPassage
**Description**: You wade through stagnant pools that reflect a gray sky. The wail continues, unbroken, relentless. Your thoughts scatter like birds. A moment ago, you tried to remember your sister's voice—but the canyon's scream drowns even memory. You are alone here, in your own head, with no refuge.

**Exits**: W, E
**Block Exits**: None
**Encounters**: None (but Auditory Strain intensifies)
**Items**: Broken spear (from a previous traveler; suggests past violence)
**NPCs**: None
**Objects**: Unstable overhang (marked as hazardous; loud noises risk collapse)
**Design Notes**: Quieter tile but emotionally heavier. Prose turns inward—Jean's thoughts fragmenting. The broken spear is environmental storytelling: someone fought here and didn't survive.

---

#### (6, 2) — Canyon Passage (East Exit)
**Title**: CanyonExit
**Description**: The canyon walls begin to widen. The wail softens—not gone, but fractionally less piercing. Your ears ring. The stone below shifts from smooth river-polished rocks to broken, jagged terrain. Ahead, the landscape opens.

**Exits**: E, W
**Block Exits**: None
**Encounters**: Solo Ravager (final test of Canyon)
**Items**: None
**NPCs**: None
**Objects**: None
**Design Notes**: Transition to Broken Gate. Relief is palpable (wail softens) but not comfortable (terrain is now hazardous).

---

### Zone 3: The Broken Gate

#### (7, 2) — Broken Gate Entry
**Title**: RuinsPlaza
**Description**: The canyon opens into a vast plaza littered with fallen stone. Massive blocks—some carved with half-legible inscriptions—lie scattered like toys of a frustrated god. In the center distance, a weathered foundation outlines what was once a grand structure. The wail here is distant, background. In the silence-ish, you hear the whisper of wind across carved stone, the soft skitter of loose gravel.

**Exits**: N, S, E, W
**Block Exits**: None
**Encounters**: None (exploration tile)
**Items**: None
**NPCs**: Mara the Scavenger (encountered here; can initiate "Fragments of the Archive" quest)
**Objects**: Carved stone blocks (player can READ inscriptions; flavor text from Golemite archive)
**Design Notes**: Lore anchor. Mara provides quest hook and merchant opportunity. Inscriptions hint at the archive's original purpose (contact with the divine, now forbidden history).

---

#### (7, 3) — Central Plaza (Archive Chamber)
**Title**: ArchiveRuins
**Description**: Here, at the heart of the broken plaza, lie the scattered remains of what was once an archive. Stone shelves are toppled; records are scattered and weathered beyond reading. But some survive, preserved in sealed containers or buried beneath protective stones. The sense of loss is palpable: knowledge, destroyed; history, shattered.

**Exits**: N, S, E, W
**Block Exits**: None (unless Guardian blocks passage—see below)
**Encounters**: Guardian of the Gate (boss encounter); or stealth/puzzle alternative (can avoid combat by solving archive puzzle)
**Items**: Archive Fragment #1–#3 (collectible, tied to Mara's quest and Korash's quest)
**NPCs**: Elder Korash (may appear here if certain conditions met; dialogue about the archive's purpose)
**Objects**: Guardian construct (statue or golem-like; comes to life if player disturbs the archive)
**Design Notes**: Central boss arena. Mechanically, player can either fight Guardian directly or solve the archive puzzle to appease it. Environmental hazards include unstable shelves and collapsing structures.

---

#### (8, 2) — Eastern Archive
**Title**: ArchiveVault
**Description**: A partially intact vault, its stone door hanging open. Inside, shelves still hold fragile scrolls and tablets, preserved by luck and stone's patience. The air is cool and dry here—untouched. Dust motes drift in faint light. This chamber feels sacred, even in ruin.

**Exits**: W
**Block Exits**: None
**Encounters**: Puzzle to safely retrieve archive fragments without triggering collapse
**Items**: Archive Fragment #2, Restorative potion, journal (from a previous scholar, written in archaic hand: meditation on loss)
**NPCs**: None
**Objects**: Delicate shelving (unstable; requires careful movement or risk destruction)
**Design Notes**: Reward room. Safe-feeling (no combat) but mechanically challenging (puzzle). The journal is environmental storytelling: echoes of Korash's own loss.

---

### Zone 4: The Bleeding Scar & Hidden Grotto

#### (7, 4) — Bleeding Scar Entry
**Title**: CliffFace
**Description**: The stone here is stained rust-red and ochre, like old blood dried into the earth. Vertical cliffs rise without mercy, carved by ancient waterfalls that no longer flow. The air is cold and mineral-rich. Hidden crevasses scar the landscape; one wrong step could be fatal.

**Exits**: N (to Broken Gate), S (deeper into scar)
**Block Exits**: None
**Encounters**: Environmental hazard (loose rock, unstable ground); puzzle to locate hidden grotto entrance
**Items**: None
**NPCs**: None
**Objects**: Carved markers on cliff (player must observe and interpret; indicate path to grotto)
**Design Notes**: Observation puzzle. Rewards careful reading of environment. Prose emphasizes the geological violence that created this landscape.

---

#### (7, 5) — Hidden Grotto Crevasse
**Title**: CrevassePath
**Description**: You've found a narrow crevasse and begun to descend. The wail above fades. The air smells different: damp, living, clean. Your eyes adjust to diminishing light. Ahead, a faint glow—bioluminescent moss—marks a way forward.

**Exits**: U (up, back to cliff), D (down, to grotto)
**Block Exits**: None
**Encounters**: None
**Items**: None
**NPCs**: None
**Objects**: Moss (glowing, marks safe path)
**Design Notes**: Transitional tile. Sensory shift from harsh to gentle. Music/sound design should soften here.

---

#### (7, 6) — The Hidden Grotto (Sanctuary)
**Title**: LuminousGrotto
**Description**: You step into a small, pristine cavern. Still water reflects bioluminescent moss that gilds the stone in soft green and blue. The constant wail of the badlands is muffled here—so quiet you can hear your own breathing. The air is cool, fresh, untouched. For the first time since entering the badlands, you feel safe.

**Exits**: U (back to crevasse), N (hidden exit to eastern pass, high difficulty)
**Block Exits**: None initially (high-difficulty exit requires specific mechanics/items)
**Encounters**: None (sanctuary; restoration point)
**Items**: Restorative potion, clean water (item), meditation journal (flavor text about acceptance)
**NPCs**: Elder Korash (may retreat here; optional conversation about the Broken Gate, loss, acceptance)
**Objects**: Still pool (can drink, restore health); moss (can observe, grants sense of peace)
**Design Notes**: Breathing room moment. No combat, no pressure. This space is earned through exploration. Music should shift to something calm and reflective.

---

### Zone 5: The Eastern Pass

#### (8, 3) — Eastern Pass Entry
**Title**: PassageEast
**Description**: The landscape is opening. Spires that once felt like walls now stand at a distance. The wail has become background noise—still present, but no longer oppressive. Your ears ring. The sky ahead is clearer, the air fresher. This passage is winding but deliberate, leading away from the badlands' core.

**Exits**: E, W
**Block Exits**: None
**Encounters**: Solo Ravager (final test of Canyon)
**Items**: None
**NPCs**: None
**Objects**: None
**Design Notes**: Transition tile. Relief is palpable (wail softens) but not comfortable (terrain is now hazardous).

---

#### (9, 3) — Eastern Pass (Mid)
**Title**: PassageMid
**Description**: The pass narrows again, but only briefly. Stone walls on either side are smoothly carved—recent geological work, or perhaps ancient water erosion. Carved into one wall: an arrow, crude but intentional. Someone marked this path. You're not the first to flee the badlands. You won't be the last.

**Exits**: W, E
**Block Exits**: None
**Encounters**: None
**Items**: None
**NPCs**: None
**Objects**: Arrow carving (can READ; "onward")
**Design Notes**: Encouragement. The carving suggests community across time—other travelers have passed this way and marked it for future survivors.

---

#### (10, 3) — Eastern Pass Exit
**Title**: PassageExit
**Description**: The badlands release you. The spires fall away. The wail fades to a whisper—so faint now that you almost forget it was ever there. Ahead, a new landscape opens: rolling hills, scattered vegetation, the promise of water. Behind, the Wailing Badlands recede like a terrible dream. You are exhausted. Your anger, having raged for so long, has burned itself out. You are not healed, but you have survived. You have *walked through* your fury and emerged—changed, diminished in some ways, fortified in others.

**Exits**: W, E (toward Sanctuary of Illusions, future content)
**Block Exits**: None
**Encounters**: None (narrative moment; optional memory of the Anger stage)
**Items**: None
**NPCs**: None
**Objects**: Waystone (marking exit point; can be READ: "The badlands will always be behind you")
**Design Notes**: Final narrative anchor. This tile should trigger a brief cinematic or internal monologue reflecting on Jean's passage through Anger. No combat. Player should feel relief mixed with the weight of what they've endured.

---

## 5. Progression & Flow

**Difficulty Curve**:
- **Spires (tiles 1–3)**: Low threat, navigation-focused. Solo Ravagers as learning encounters.
- **Canyon (tiles 4–6)**: Medium-high threat, environmental hazard focus. Auditory Strain as primary mechanic. Ravager packs escalate.
- **Broken Gate (tiles 7–8)**: High threat (Guardian boss option), lore-heavy, quest anchors.
- **Bleeding Scar/Grotto (tiles 7–7.6)**: Medium threat, exploration puzzle, then zero threat (sanctuary).
- **Eastern Pass (tiles 8–10)**: Low threat, pacing wind-down, narrative focus.

**Pacing**:
- Early badlands: Fast-paced, disorienting, frequent encounters
- Mid badlands: Intense and overwhelming (Canyon); emotional low point
- Late badlands: Encounters taper; breathing room (Grotto); transition toward acceptance (Pass)

**Gate Mechanics**:
- Spires → Canyon: No gate; direct progression
- Canyon → Broken Gate: No gate; natural transition
- Broken Gate → Grotto: Optional; requires careful observation of environmental clues
- Broken Gate → Eastern Pass: Direct route; or hidden high-difficulty route via Grotto

**Optional Content**:
- Guardian boss (can be bypassed via stealth/puzzle)
- Korash and Mara encounters (quests unlock lore)
- Hidden grotto (rewards exploration; grants emotional respite)
- Archive fragments (collectible; tied to side quests)

---

## 6. Puzzle & Encounter Map

### Navigation Puzzles

**Shattered Spires Maze**:
- **Mechanic**: Use moss (north-facing) as compass to navigate maze without getting lost in circular passages.
- **Solution**: Observe moss growth pattern; use cardinal directions mindfully.
- **Reward**: Reaching eastern exit without excessive backtracking avoids extra Ravager encounters.

**Keening Canyon**:
- **Mechanic**: Navigate narrow passage while managing Auditory Strain and avoiding unstable overhangs.
- **Solution**: Move deliberately; avoid loud combat if possible (or trigger collapse strategically to block Ravager pursuit).
- **Reward**: Reach exit with minimal health loss.

**Bleeding Scar Crevasse Discovery**:
- **Mechanic**: Read carved markers on cliffs; follow subtle environmental clues to hidden crevasse.
- **Solution**: Observe cliff faces; interpret ancient Golemite glyphs or simple arrow markers.
- **Reward**: Access hidden grotto; restoration moment; alternate exit to Eastern Pass.

**Archive Vault Puzzle**:
- **Mechanic**: Safely retrieve archive fragments without triggering shelf collapse; or solve environmental puzzle to appease Guardian construct.
- **Solution**: Interact with environment carefully; piece together lore clues about what items/knowledge the archive intended to preserve.
- **Reward**: Archive fragments for Mara; conversation with Korash; unique artifact.

### Combat Encounters

**Solo Ravagers** (Spires, early):
- 1 Ravager, HP 35–45
- Abilities: Claw attack (medium damage), territorial roar (alerts nearby enemies)
- Loot: Ravager hide, minor gold
- Arena: Spire corridors (tight, obstacles block movement)

**Ravager Pairs** (Spires, central hub):
- 2 Ravagers, HP 35–45 each
- Abilities: Pack tactics (coordinated strikes), pincer movement
- Loot: Minor gold, bone tools
- Arena: Central plaza with boulder obstacles

**Ravager Packs** (Canyon):
- 3–5 Ravagers with 1 alpha (higher HP, damage, and intelligence)
- Abilities: Alpha uses roar to coordinate pack; flanking maneuvers
- Loot: Ravager alpha trophy, minor equipment, gold
- Arena: Canyon bottom with wind gusts affecting movement; unstable overhangs risk collapse

**Guardian of the Gate** (Boss):
- HP: 200+, high protection, moderate damage
- Abilities: Stone strike (AOE, moderate damage), structural damage (triggers overhang collapse, damages all combatants), restoration (regenerates HP in later rounds)
- Loot: Unique artifact ("Guardian's Aegis" — grants temporary invulnerability; thematic: the Guardian protects, even in defeat)
- Arena: Archive ruins with environmental hazards (collapsing shelves, unstable platforms, scattered stone blocks as cover)
- Bypass mechanic: Solve archive puzzle instead of fighting; Guardian stands down if player proves respectful of archive's sanctity

**Optional Ravager (Eastern Pass)**:
- 1 alpha Ravager, HP 50–60
- Abilities: Final gauntlet; more aggressive than standard pack Ravagers
- Loot: Ravager fang (crafting material), minor gold
- Arena: Open passage with minimal cover (forces direct combat or evasion)

### Environmental Hazards

**Wind Gusts**:
- Occur randomly in open areas (Spires, Canyon, Broken Gate)
- Effect: Knockback (push player 1–2 tiles), risk of falling into crevasse or against sharp stone
- Mitigation: Seek shelter, use heavy equipment to anchor, move carefully

**Auditory Strain** (Condition):
- Accumulates during exposure to the wail (primarily in Canyon and Shattered Spires)
- Effect: Impairs hearing-based abilities; NPC dialogue becomes muffled; some audio-based puzzles fail
- Threshold: At 75% strain, Jean experiences brief memory fragment (rage-related)
- Mitigation: Rest in quiet areas (grotto), consume specific items (quiet potion), or move to lower-wail zones

**Exhaustion** (Condition):
- Accumulates from exposure to harsh conditions (extreme wind, cold, lack of shelter)
- Effect: Reduces max health; stamina regenerates slowly
- Mitigation: Find shelter, consume food/water items, rest

**Unstable Structures**:
- Marked in description (loose boulders, cracking overhangs, leaning spires)
- Trigger: Loud noises (combat, shouted commands) or direct impact
- Effect: Collapse damages all nearby combatants; can block exits or create new passage
- Mitigation: Avoid loud combat, or deliberately trigger collapse to trap enemies

---

## 7. Lore Integration Checklist

- [x] **Thematic alignment**: Badlands embody Anger stage of grief arc; Jean's rage mirrors environmental hostility
- [x] **Character presence**: Elder Korash (Golemite exile, penance, lost knowledge); Mara the Scavenger (pragmatic historian)
- [x] **Faction flavor**: Golemite failure and shame at Broken Gate; hint at forbidden history; Votha Krr's evasiveness ties to this region
- [x] **Environmental storytelling**: Carved markers, journal fragments, previous travelers' remains, archive ruins
- [x] **Theological echo**: Divine contact attempt (Golemites' hubris); acceptance through surviving exhaustion (not conquering through force)
- [x] **Memory integration**: Memory fragments tied to rage moments; reflection on loss and powerlessness
- [x] **Spiritual journey**: Anger stage moves toward Acceptance; player learns that rage is justified but unsustainable

---

## 8. Asset Needs & Dependencies

### New Item Types Required

**None — all can be reused from existing inventory.**

- Provisions (Dried Rations, clean water) already exist
- Restorative potions can be standard type
- Archive fragments are story items (text-based, no new mechanics needed)
- Ravager trophy/fang: crafting materials, standard drop mechanic

### New NPCs Required

**Elder Korash (Golemite Exile)**
- **Role**: Quest-giver, lore-keeper, emotional anchor
- **Archetype**: Scholarly Golemite like Gorran; aged, burdened by knowledge
- **Purpose**: Reveals the Broken Gate's history; provides context for Golemite shame; offers acceptance wisdom
- **Dialogue hooks**:
  - "The Gate was where we reached too far. Now we live with the consequence."
  - "You carry anger as I do, Jean. The badlands teach it cannot be carried forever."
- **Lore connection**: Exiled Golemite; survived the catastrophe at the Broken Gate; seeks penance through solitude
- **Mechanical role**: Quest-giver ("The Archivist's Burden"); dialogue grants temporary resistance to Auditory Strain; unique NPC in terms of direct Jean-to-NPC emotional conversation about grief
- **Stats**: Low combat (retired, elderly); high charisma, intelligence, faith
- **Effort**: **Medium** — new NPC requires character profile, dialogue, quest logic

**Mara the Scavenger (Human)**
- **Role**: Merchant, quest-giver, pragmatist
- **Archetype**: Itinerant trader; opportunistic but not cruel
- **Purpose**: Facilitates artifact collection quest; provides merchant services; hints at deeper lore about lost civilization
- **Dialogue hooks**:
  - "The Broken Gate holds the past. What you do with it is your future."
  - "Each fragment is a story. Stories are currency in a broken world."
- **Lore connection**: Moves between Badlands and Resolute Plains; trades in history; theorizes about pre-current-age civilization
- **Mechanical role**: Merchant (buys artifacts, sells provisions); quest-giver ("Fragments of the Archive"); can provide hints for navigation puzzles
- **Stats**: Medium combat (self-sufficient); high charisma, wisdom
- **Effort**: **Medium** — new NPC requires character profile, dialogue, quest logic, merchant inventory

### New Enemy Types Required

**Ravagers**
- **Role**: Primary antagonist; territorial creatures; represent environmental hostility
- **Combat profile**:
  - Solo: 35–45 HP, damage 8–12, medium aggression
  - Alpha (pack leader): 50–60 HP, damage 12–16, high aggression + pack coordination
- **Abilities**: Claw attack, territorial roar (alerts nearby enemies), pack tactics (coordinated strikes)
- **Loot**: Ravager hide, bones, minor gold, alpha trophy (unique drops)
- **Narrative role**: Embody the Anger stage; aggressive, defensive, territorial; not intelligent enough to parley
- **Effort**: **Medium-High** — requires new combat mechanics (pack AI, coordination), animation/description, drop tables

### New Object Types Required

**Guardian of the Gate Construct** (Interactive/Boss)
- **Mechanic**: Animated construct; activates if archive is disturbed; can be defeated in combat or appeased via puzzle
- **Properties**: High HP (200+), cannot leave arena, regional damage (collapsing structures), regeneration (later combat rounds)
- **Why needed**: Thematically anchors the Broken Gate; boss-level encounter; tie-in to Golemite lore (construct created to protect archive)
- **Effort**: **High** — new boss archetype, AI behavior, arena hazards, victory/defeat dialogue

### Dependency Summary

- [x] New item types: **None** (reuse existing)
- [x] New NPCs: **2** (Korash, Mara) — **Medium effort each**
- [x] New enemies: **Ravagers** (new type) — **Medium-High effort**
- [x] New object types: **Guardian construct** (boss) — **High effort**
- [x] Story events: Anger stage triggers (memory fragments); "Fragments of the Archive" quest logic; "Archivist's Burden" quest logic
- [x] Faction mechanics: **Golemite history reveal** (tie-in to existing Conclave lore)
- [x] Puzzle mechanics: Navigation (moss compass), archive vault (safe retrieval), grotto discovery (observation)
- [x] Environmental effects: **Auditory Strain condition** (new mechanic); **Exhaustion condition** (variation on existing); wind gusts (environmental hazard)

**Load Assessment**: Moderate to High. Ravagers + Korash + Mara + Guardian construct + Auditory Strain mechanic = significant but cohesive work block. Can be phased: Phase 1 (map + Ravagers + basic encounters), Phase 2 (NPCs + quests), Phase 3 (Guardian + advanced mechanics).

---

## 9. Implementation Notes for Agents

### JSON Map Structure

```json
{
  "metadata": {
    "bgm": "wailing_badlands_wail",
    "name": "wailing-badlands",
    "region": "badlands",
    "chapter": 3
  },
  "(1, 1)": {
    "id": "tile_1_1",
    "title": "BadlandEntryPoint",
    "description": "[prose as specified in room-by-room section]",
    "exits": ["E", "NE", "SE"],
    "block_exit": ["W"],
    "events": [
      {
        "__class__": "Ch03BadlandEntry",
        "__module__": "story.ch03",
        "props": { "name": "Ch03_Badland_Entry", ... }
      }
    ],
    "items": [],
    "npcs": [],
    "objects": [
      {
        "__class__": "WallInscription",
        "__module__": "objects",
        "props": {
          "name": "Waystone",
          "description": "A weathered stone marker inscribed with a Wayfarer warning...",
          ...
        }
      }
    ]
  },
  ...
}
```

### Common Patterns to Follow

**Safe Rooms**:
- (3, 1) — Spire dead-end: shelter, previous traveler evidence, narrative clue
- (8, 2) — Archive vault: preserved knowledge, restoration potion, minimal threat
- (7, 6) — Grotto: sanctuary, zero combat, restoration point

**Reward Clustering**:
- Minor loot scattered through Spires and Canyon (Dried Rations, broken spear, bone tools)
- Medium loot at Broken Gate (archive fragments, unique equipment from alpha Ravagers)
- Major loot: Guardian artifact, Korash gift, access to grotto

**Container Mechanics**:
- Archive vault has delicate shelving (puzzle: retrieve items without collapse)
- Guardian construct is not a container but an interactive boss entity

**NPC Placement**:
- Mara at Broken Gate (7, 2) — active scavenging, merchant services
- Korash at Broken Gate (7, 3) or Grotto (7, 6) — optional, tied to quest completion

**Hidden Items**:
- Dried Rations at (2, 1) — marked `hidden: true`, discovery message describes location
- Archive Fragment #2 at (8, 2) — requires vault puzzle solution
- Clean water at (7, 6) — available within grotto (not hidden, but earned through exploration)

**Event Triggers**:
- Ch03BadlandEntry at (1, 1) — narrative framing
- Ch03MemoryFragment — trigger during Canyon combat or exposure threshold
- Ch03GuardianAwakens — trigger when archive is disturbed at (7, 3)
- Ch03RageExhausted — trigger at Eastern Pass exit; narrative reflection on Anger stage

### Testing Gates

- [ ] All tiles connect without orphans; exits form playable graph (Spires loop-back is intentional; Canyon is linear; Broken Gate hub connects to 4 zones)
- [ ] Block exits release appropriately (W exit at entry only blocks until game allows progression; high-difficulty Grotto exit unlocks after specific conditions)
- [ ] Guardian encounter is defeatable or bypassable; arena hazards affect all combatants equally
- [ ] At least two secrets are genuinely discoverable: (3, 1) dead-end cache, (7, 5–7, 6) hidden grotto
- [ ] Movement flow prevents frustrating dead-ends (Spires maze can be circled, but cardinal navigation allows escape)
- [ ] Auditory Strain mechanic meaningfully impacts gameplay (not just flavor)
- [ ] Difficulty ramp: Spires (low threat) → Canyon (peak threat) → Broken Gate (medium-high) → Grotto (zero) → Pass (low)
- [ ] NPC encounters (Mara, Korash) trigger appropriately and don't block progression
- [ ] Archive fragments are collectible but optional (player can complete map without all three)
- [ ] Environmental storytelling is consistent (previous travelers, Golemite history, Jean's emotional state reflected in prose)

---

## 10. Visual Reference

**Zoomed-Out World Map Context**:

```
                    ┌─────────────────────┐
                    │  Sanctuary of       │
                    │  Illusions          │
                    │  (future content)   │
                    └─────────────────────┘
                            ↑
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
    [Hidden Grotto] — [Eastern Pass] (exit)    │
        │                   │                   │
        │      [Wailing Badlands]              │
        │      - Shattered Spires              │
        │      - Keening Canyon                │
        │      - Broken Gate                   │
        │      - Bleeding Scar                 │
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                    [Spires entry]
                            │
                ┌───────────┴──────────┐
                │                      │
        [Resolute Plains]       [Future Content]
        (Wayfarers, nomads)     (Eastern Steppes)
```

---

## Authorship & Status

**Designed**: March 18, 2026 (via map-design skill)
**Status**: **Ready for Implementation**
**Effort Estimate**: **8–12 weeks** for full implementation (phased approach recommended)
**Priority**: **High** — Critical to Jean's emotional arc (Anger stage)

---

## Implementation Phases

**Phase 1 (Weeks 1–3)**: Create map JSON with all tiles and basic encounters (Ravagers, environmental hazards)

**Phase 2 (Weeks 4–6)**: Implement NPCs (Korash, Mara) with dialogue and quests

**Phase 3 (Weeks 7–12)**: Add Guardian boss, Auditory Strain mechanic, advanced environmental effects, testing and refinement

For lore questions and design intent, refer to [wailing-badlands-profile.md](wailing-badlands-profile.md) (the conceptual thematic profile that preceded this design document).
