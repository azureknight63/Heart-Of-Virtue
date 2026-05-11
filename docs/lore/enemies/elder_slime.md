# Elder Slime

A vastly larger and more deliberate cousin of the common slime. The Elder Slime is slow, methodical, and possesses something that might be intelligence — an awareness of its surroundings that belies its gelatinous nature. It is a mid-tier threat in the Grondelith Mineral Pools, capable of devastating telegraphed surges that observant players can learn to read and dodge.

## Appearance
- Vastly larger than a common slime; roughly the size of a small cart
- Slow, deliberate movement — heavy and ponderous
- More defined structure than a common slime; thicker consistency with visible mineral inclusions
- Color ranges from murky green to brownish tones, studded with mineral fragments
- Occasionally shifts and ripples as if considering the world around it
- Moves with a cold, deliberate focus

## Behavior
- More intelligent and aware than common slimes (awareness: 20)
- Slower movement (speed: 8) — reflects its massive size and weight
- Deliberate and methodical; watches Jean with apparent comprehension
- Aggressive but not frenzied; takes measured actions
- Often encountered as a solo or paired threat, never in large groups

## Special Abilities & Traits
- **Slime Volley**: A devastating telegraphed directional surge attack. Players who learn to read the tell can dodge to avoid the worst of it
- **Crushing Weight**: The creature's mass makes it resistant to certain types of damage
- **Mineral Affinity**: Contains and resists mineral/earth magic
- **Absorption**: More resistant to slashing and piercing attacks due to its thick, gelatinous body
- **Movement**: Uses `Advance` to close distance despite slow speed, and employs `NpcIdle` between actions
- **Predictable**: Once learned, the Slime Volley telegraph becomes a key mechanic for players to master

## Tactics
- **Telegraphed surge**: Uses `SlimeVolley` as a primary offense — deals heavy damage in a pattern that players learn to evade
- **Advance methodically**: Closes distance with `Advance` moves, establishing dominating position
- **Idle between attacks**: Uses `NpcIdle` to recover and reset positioning; appears to be "charging"
- **Persistent pressure**: Relies on the threat of `SlimeVolley` to keep players mobile and defensive
- **Endurance strategy**: Designed for mid-length battles; not a quick threat, but a grinding one

## Example Stats (from code)
- HP: moderate-high (maxhp=70)
- Damage: moderate (damage=28)
- Protection: moderate (protection=12) — its bulk offers some defense
- Awareness: low (awareness=20) — relies on distance rather than precision
- Speed: very slow (speed=8) — heavy and ponderous
- Aggro: True — will engage on sight
- XP Award: moderate (exp_award=45)
- Idle message: "shifts slowly in the muck"
- Alert message: "fixes Jean with a cold, deliberate focus!"
- Move set: `NpcAttack`, `SlimeVolley` (signature move), `Advance`, `NpcIdle`

## Resistances & Vulnerabilities

### Damage Resistances
- **Slashing (0.65)**: Resistant — slashing attacks slide through gelatinous flesh
- **Piercing (0.65)**: Resistant — piercing attacks disperse without clean cuts
- **Crushing (1.25)**: Weak — crushing weapons deal concentrated damage effectively
- **Fire (1.4)**: Weak — fire damages and hardens the slime
- **Earth (0.85)**: Slightly resistant — mineral affinity with earth magic

### Status Resistances
- **Poison (1.0)**: Immune — no flesh to poison
- **Slimed (1.0)**: Immune — already made of slime

## Encounter & Lore Notes
- Elder Slimes are found deeper in the Grondelith Mineral Pools, in chambers with mineral deposits and stagnant water
- Represents an evolutionary step toward the Chapter 1 boss (King Slime); players encounter Elder Slimes to learn mechanics they'll later need against the King
- The Slime Volley telegraph serves as a tutorial in reading boss patterns and timing dodges
- Often guarding chokepoints or resource-rich areas in the pools

## DM / Designer Tips
- **Telegraph mechanics**: The Slime Volley attack should be visually and mechanically distinct — it announces itself before executing
- **Rewards learning**: Players who successfully dodge the surge should feel like they've mastered a mechanic
- **Progression indicator**: Place Elder Slimes before the King Slime encounter to teach the core dodge pattern
- **Positioning matters**: Encounters should have enough space for players to maneuver and reposition
- **Crushing focus**: Emphasize to players that blunt/crushing weapons are effective against slimes
- **Pair strategically**: Elder Slimes work well as solo threats or paired with lesser slimes to create layered encounters

## References
- Code: [`ElderSlime` class](src/npc/_enemies.py)
- Moves: [`SlimeVolley`](src/moves/_npc.py), [`NpcAttack`](src/moves/_npc.py), [`Advance`](src/moves/_movement.py), [`NpcIdle`](src/moves/_npc.py)
- Related: [King Slime](king_slime.md) — the boss evolution of this enemy
