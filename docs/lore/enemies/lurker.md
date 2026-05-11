# Lurker

A grisly demon of the dark — a vaguely humanoid creature with long, thin arms ending in sharp, poisonous claws. Lurkers prefer to hide and strike from darkness, making them difficult to spot until they choose to attack. They are predatory, intelligent, and extremely dangerous.

## Appearance
- Vaguely humanoid body, though twisted and unnatural
- Long, spindly arms ending in razor-sharp, poisonous claws
- Prefers darkness and shadow; excellent at hiding in dim environments
- Eyes that glow faintly in the dark
- Exudes an aura of dread and malice

## Behavior
- Highly intelligent and aware of surroundings (awareness: 60)
- Predatory hunter; strikes with precision and cruelty
- Prefers isolation and darkness; can hide and wait for the perfect moment to strike
- Aggressive when provoked; will pursue prey relentlessly
- Possesses an almost supernatural resistance to death and despair (immunity to death and doom statuses)

## Special Abilities & Traits
- **Venom Claws**: Lurkers can deliver venomous strikes through their sharp claws, inflicting poison damage and status effects
- **Soul Drain**: A supernatural ability that drains life force and deals dark damage
- **Dark Affinity**: Highly resistant to dark magic; vulnerable to fire and light
- **Death Immunity**: Resistant to instant-death and doom effects; these creatures are already touched by darkness
- **Movement**: Uses both aggressive `Advance` tactics and strategic `Withdraw` to position itself optimally in combat
- **Evasion**: Dodging is a key tactic, especially when facing multiple opponents or superior firepower

## Tactics
- **Surgical strikes**: Lurkers attack with precision, using `Advance` to close distance and deliver high-damage attacks
- **Kite and retreat**: After striking, they use `Withdraw` to reposition, keeping distance and using darkness to their advantage
- **Venom strategy**: They favor `VenomClaw` for poison damage over raw physical attacks, wearing down enemies over time
- **Life drain**: Uses `SoulDrain` to recover health and deal supernatural damage simultaneously
- **Evasion focus**: Dodging is prioritized, especially when outnumbered or facing heavy hitters

## Example Stats (from code)
- HP: very high (maxhp=450) — one of the toughest enemies in the game
- Damage: high (damage=35)
- Protection: none (protection=0) — they rely on evasion, not armor
- Awareness: exceptional (awareness=60) — extremely hard to surprise
- Endurance: good (endurance=20)
- Aggro: True — will engage the player on sight
- XP Award: substantial (exp_award=950) — a significant threat
- Loot: level 1 treasure drops
- Move set: `NpcAttack`, `VenomClaw`, `SoulDrain`, `Advance`, `Withdraw`, `Dodge` (with higher dodge weight)

## Resistances & Vulnerabilities

### Damage Resistances
- **Dark (0.5)**: Highly resistant to dark magic — feeds on shadow
- **Fire (-0.5)**: Takes increased damage from fire — light and heat weaken it
- **Light (-2.0)**: Extremely vulnerable to light — its power diminishes in brightness

### Status Resistances
- **Death (1.0)**: Immune to instant-death effects
- **Doom (1.0)**: Immune to doom/despair effects

## Encounter & Lore Notes
- Lurkers are mid-to-late game threats, encountered in dark, confined spaces where their evasion and darkness affinity are maximized
- Their high HP and intelligence make them dangerous bosses or lieutenant-tier enemies
- Often found in corrupted areas or places touched by shadow and desolation
- Can be used as solo threats (their high awareness means they're hard to ambush) or in small numbers

## DM / Designer Tips
- **Reward light sources**: Encounters with Lurkers should emphasize the value of light magic, fire spells, and illumination items
- **Arena design**: Cluttered, dark spaces favor Lurkers; open areas with light sources favor the player
- **Pacing**: Their high HP means extended combat — ensure the player has healing and sustainable damage sources
- **Story weight**: Lurkers should feel like significant threats; their lore suggests they are demons or corrupted beings, not mere monsters
- **Combination encounters**: Pair with lesser enemies (slimes, bats) to force the player to manage multiple threats while facing the Lurker's hit-and-run tactics

## References
- Code: [`Lurker` class](src/npc/_enemies.py)
- Moves: [`VenomClaw`](src/moves/_npc.py), [`SoulDrain`](src/moves/_npc.py), [`NpcAttack`](src/moves/_npc.py), [`Advance`](src/moves/_movement.py), [`Withdraw`](src/moves/_movement.py), [`Dodge`](src/moves/_movement.py)
- Loot: [Level 1 treasure](src/npc/_loot.py)
