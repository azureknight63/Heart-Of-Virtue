# Lurker

Lurkers are corrupted crusaders — former warriors of faith and conviction who descended into the Verdette Caverns and were remade by the darkness dwelling there. They are vaguely humanoid creatures with long, spindly arms ending in razor-sharp, poisonous claws. They strike from shadow with surgical precision, then retreat into the darkness that birthed them. Few who encounter a Lurker understand what it once was. Fewer still care.

## Appearance
- Vaguely humanoid body, though twisted and unnatural
- Long, spindly arms ending in razor-sharp, poisonous claws
- Prefers darkness and shadow; excellent at hiding in dim environments
- Eyes that glow faintly in the dark
- Exudes an aura of dread and malice

## Behavior
- Highly aware and perceptive (awareness: 60); senses living things through darkness itself
- Hunts with precision born from combat training, but now twisted into something alien
- Prefers absolute darkness and solitude; waits motionless for prey, sometimes for hours
- Recognizes other humanoids; may circle them with something resembling curiosity before striking
- Shows no fear of death—in fact, seems unconcerned with its own mortality (immunity to death and doom statuses)
- Speaks rarely, but when it does, uses fragmented speech mixing current moment with distorted memories
- The creature remembers being human, but confuses what it remembers with what actually was

## Special Abilities & Traits
- **Venom Claws**: Lurkers can deliver venomous strikes through their sharp claws, inflicting poison damage and status effects
- **Soul Drain**: A supernatural ability that drains life force and deals dark damage
- **Dark Affinity**: Highly resistant to dark magic; vulnerable to fire and light
- **Death Immunity**: Resistant to instant-death and doom effects; these creatures are already touched by darkness
- **Movement**: Uses both aggressive `Advance` tactics and strategic `Withdraw` to position itself optimally in combat
- **Evasion**: Dodging is a key tactic, especially when facing multiple opponents or superior firepower

## Tactics

- **Surgical strikes**: Attack with precision, using `Advance` to close distance and deliver high-damage blows in rapid succession
- **Kite and retreat**: After striking, use `Withdraw` to reset distance, maintaining advantage through superior darkness affinity
- **Venom strategy**: Prioritize `VenomClaw` for accumulating poison damage; wear down prey over time rather than seeking instant victory
- **Life drain**: Use `SoulDrain` to recover health while dealing supernatural damage; sustain through attrition
- **Darkness exploitation**: Fight primarily in absolute darkness where it has complete advantage; avoid open light
- **Evasion focus**: Prioritize `Dodge` when outnumbered or facing heavy hitters; never commit to sustained melee
- **Psychological warfare**: Occasionally speak in fragmented, unsettling sentences mixing past and present, confusing prey

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

**Origin & Location**: Lurkers are found in the deepest reaches of the **Verdette Caverns (Chapter 2)**. The caverns are a place where corruption runs deep—not sudden or violent, but patient and insidious. A Lurker is what a crusader becomes when he enters seeking redemption and finds only darkness waiting with seductive whispers.

**The Nature of Corruption**: Unlike the King Slime's rapid consumption or the CorruptedStoneCreature's mindless animation, a Lurker represents corruption as *seduction*. The darkness doesn't steal the crusader's identity—it convinces him that his identity was always an illusion. Over months of isolation, prayer turns to conversation with shadow. Faith dissolves into recognition. The crusader realizes he has become the darkness, and there is a terrible peace in that surrender.

**Psychological Threat**: A Lurker is dangerous not merely as a combat encounter but as a philosophical question made flesh. Jean, himself a crusader walking into darkness, will recognize something of himself in its movements. The Lurker is what a crusader becomes when conviction fails—when he stops believing light is real and accepts that darkness was always honest. This encounter should unsettle Jean in ways combat rarely does.

**Memory & Agency**: Lurkers occasionally speak in fragmented sentences, mixing past and present: "the torch burned" and "the torch is burning" used interchangeably, as if time has collapsed. This unreliable memory suggests the creature retains some awareness of its former self, trapped behind layers of corruption. Whether this makes it tragic or simply more dangerous is a question left to the player.

## DM / Designer Tips
- **Philosophical weight**: Lurker encounters should feel *heavy* narratively. This is not merely a combat threat but a mirror. Jean will see in the Lurker what he could become if faith fails him.
- **Light as salvation, darkness as seduction**: Describe the darkness speaking to the creature—whispering that light is a lie, that surrender is peace. This should unsettle Jean in ways violence alone cannot.
- **Arena design**: Cluttered, dark cavern spaces favor Lurkers. Consider encounters in areas where light sources are rare or fail unexpectedly.
- **Pacing & Resource drain**: The Lurker's high HP means extended combat. More importantly, the encounter should drain emotional/philosophical resources, not just tactical ones.
- **Recognition moment**: When Jean first sees a Lurker, give him a moment to recognize the humanoid shape, the arms, the *wrongness* of what was once a being like himself. This recognition is the real danger.
- **Combination encounters**: Pair rarely with lesser enemies; Lurkers hunt alone. When multiple Lurkers appear, they are coordinated hunters, not a coincidence.
- **Speech patterns**: If the Lurker speaks, use fragmented, confused language mixing past and present. This highlights the philosophical horror more than pure silence.

## References
- Code: [`Lurker` class](src/npc/_enemies.py)
- Moves: [`VenomClaw`](src/moves/_npc.py), [`SoulDrain`](src/moves/_npc.py), [`NpcAttack`](src/moves/_npc.py), [`Advance`](src/moves/_movement.py), [`Withdraw`](src/moves/_movement.py), [`Dodge`](src/moves/_movement.py)
- Loot: [Level 1 treasure](src/npc/_loot.py)
- Origin: [Lurker Origin Story](lurker-origin-story.md) — The philosophical tragedy of a crusader lost to darkness
- Location: Verdette Caverns (Chapter 2)
