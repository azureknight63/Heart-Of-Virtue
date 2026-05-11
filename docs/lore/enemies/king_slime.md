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
- **Telegraphed devastation**: Uses `TidalSurge` as its primary attack — the same mechanic as Elder Slime, but massively scaled
- **Inevitable advance**: Slowly closes distance with `Advance`; there is nowhere to run, only to dodge and resist
- **Rhythm and pattern**: Moves follow a discernible rhythm that gives players time to heal and prepare between surges
- **Fatigue management**: Will occasionally rest (`NpcIdle`) to recover, giving players brief respites
- **Overwhelming force**: Designed to be beaten through learning patterns, optimal damage selection, and resource management — not through raw stats

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
- The King Slime is the culmination of Chapter 1 — its defeat marks a major narrative turning point
- The Tidal Surge attack is the key mechanic players must master; it's telegraphed the same way as Elder Slime, teaching reward for earlier encounters
- Serves as environmental storytelling; the pools' corruption is literally embodied in this creature
- Defeating it should feel like a genuine victory after a long, grinding battle of attrition and pattern recognition
- The creature's minerals suggest it is not purely slime but a hybrid of consumed land and gelatinous corruption

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
