# King Slime

A colossal mass of pulsating green slime, studded with mineral fragments it has consumed over centuries. The King Slime is the Chapter 1 boss and the final corruption of the Grondelith Mineral Pools — a living embodiment of the pools' degradation and the source of the corruption spreading through the land. It moves with slow, terrible certainty, its massive body capable of devastating area attacks that Jean must learn to evade.

## Appearance
- Colossal, pulsating mass of deep green slime
- Body studded with mineral fragments, shards of crystalline deposits, and corroded stone
- Size suggests centuries of growth and consumption
- Moves with a slow, terrible certainty — each movement reshapes the surrounding space
- Pulses at the center of the pool, a heart of corruption
- Rears upward with a deep, resonant churn when alerted

## Behavior
- Ancient and aware; possesses a terrible intelligence despite its gelatinous form
- Moves slowly due to immense size; each action is deliberate and consequential
- Aggressive and territorial; will not tolerate intrusion into the pools
- The culmination of all corruption in the pools; defeating it is meant to purify the waters
- Serves as the climax of Chapter 1's narrative arc

## Special Abilities & Traits
- **Tidal Surge**: A boss-scale version of the Elder Slime's Slime Volley. Uses the same telegraphed pattern players learned earlier, but at much greater scale and power
- **Massive HP**: Among the highest HP values in the game (maxhp=200) — designed for extended boss battles
- **Crushing Presence**: Heavy protection and damage output; its bulk is a weapon
- **Mineral Domination**: Contains countless minerals; highly resistant to damage types that don't exploit its weaknesses
- **Regal Resistance**: Heavily resistant to slashing and piercing attacks; crushes through shield work
- **Movement**: Uses `Advance` to close distance with inevitable determination, and `NpcIdle` to prepare devastating surges
- **Fatigue**: Can rest and recover, making it a marathon boss rather than a burst threat

## Tactics

- **Telegraphed devastation**: Use `TidalSurge` as the primary attack—same mechanic as Elder Slime, but massively scaled and more devastating
- **Inevitable advance**: Slowly close distance with `Advance`; the creature's weight is inexorable; no amount of kiting can avoid eventual engagement
- **Rhythm and recovery**: Attack in patterns, with deliberate `NpcIdle` recovery periods. This creates a discernible rhythm—moments where Jean can heal, reposition, and prepare for the next surge
- **Pattern mastery as victory**: The fight is designed to *teach* Jean through repeated exposure. The Tidal Surge telegraph is consistent; learning it transforms overwhelming odds into manageable rhythm
- **Attrition strategy**: Win through accumulated damage and resource management, not through bursts. Force Jean to think strategically, not tactically
- **Fatigue irrelevance**: Unlike lesser enemies, the King Slime's fatigue doesn't limit it—it simply rests and continues. This underscores that raw endurance won't win; only mastery of the pattern will

## Example Stats (from code)
- HP: very high (maxhp=200) — a true boss
- Damage: high (damage=50)
- Protection: moderate-high (protection=15) — thick gelatinous armor
- Awareness: moderate (awareness=30)
- Speed: very slow (speed=6) — slow, terrible certainty
- Aggro: True — will engage
- XP Award: massive (exp_award=500) — defeating the boss grants tremendous experience
- Loot: level 1 treasure drops — typically includes unique or high-tier items
- Idle message: "pulses at the centre of the pool"
- Alert message: "rears upward with a deep, resonant churn!"
- Move set: `NpcAttack`, `TidalSurge` (signature move), `Advance`, `NpcIdle`

## Resistances & Vulnerabilities

### Damage Resistances
- **Slashing (0.65)**: Resistant — slashing attacks disperse through gelatinous mass
- **Piercing (0.65)**: Resistant — piercing attacks lose momentum in slime
- **Crushing (1.2)**: Weak — crushing damage is highly effective
- **Fire (1.5)**: Weak — fire is extremely dangerous to the slime
- **Earth (0.9)**: Slightly resistant — mineral affinity

### Status Resistances
- **Poison (1.0)**: Immune — no flesh to poison
- **Slimed (1.0)**: Immune — already made of slime

## Encounter & Lore Notes

**Location & Chapter**: The King Slime dwells in the **heart of the Grondelith Mineral Pools (Chapter 1, final boss)**. It is the source and embodiment of the corruption that has degraded the pools from a sacred site into a festering wound.

**Narrative Significance**: This encounter marks the culmination of Chapter 1. Defeating the King Slime is not merely a mechanical victory but a statement: Jean has learned to recognize corruption's patterns, to persist through overwhelming odds, and to strike at the heart of darkness itself. The victory is earned through pattern mastery learned from Elder Slimes—a reward for earlier patience and observation.

**Jean's Arc Connection (Oblique)**: The King Slime represents the weight of accumulated corruption—corruption that has consumed centuries, layers upon layers of degradation. Jean faces a creature that embodies overwhelming force, yet defeats it not through raw strength but through learning its patterns and maintaining conviction despite the darkness's apparent inevitability. This encounter teaches Jean that corruption, for all its ancient weight, is not invincible. It can be understood. It can be overcome.

## DM / Designer Tips
- **Boss pacing**: The King Slime is designed for a long, demanding fight. Ensure players have healing items and stamina management tools
- **Mechanic payoff**: Players who learned to dodge Slime Volley from Elder Slimes will feel rewarded when they master Tidal Surge
- **Environmental use**: The pool itself can be part of the encounter — limiting terrain, shifting water levels, or creating hazards
- **Resource drain**: The long battle tests resource management; players must use optimal weapons and abilities
- **Victory moment**: Defeating the King Slime should be momentous — a clear boss defeat with visual/audio cues
- **Post-boss narrative**: The purification of the pools (or lack thereof) should have story consequences downstream
- **Weakness emphasis**: Fire and crushing damage should feel distinctly more effective than other damage types
- **Healing access**: Ensure players have opportunities to heal between surges; battles should test strategy, not just raw HP

## Character Growth Notes
- Jean's combat skills should feel significantly improved after learning the Tidal Surge pattern in the Elder Slime encounter
- This boss represents the transition from early-game encounters (slimes, bats) to more complex threats
- Defeating the King Slime establishes Jean as capable of facing the larger world and the deeper corruption

## References
- Code: [`KingSlime` class](src/npc/_enemies.py)
- Moves: [`TidalSurge`](src/moves/_npc.py), [`NpcAttack`](src/moves/_npc.py), [`Advance`](src/moves/_movement.py), [`NpcIdle`](src/moves/_npc.py)
- Related: [Elder Slime](elder_slime.md) — the mini-boss tutorial for this encounter
- Loot: [Level 1 treasure](src/npc/_loot.py)
- Chapter: Chapter 1 — Grondelith Mineral Pools Arc
