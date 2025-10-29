# Rock Rumbler

A hulking, quadrupedal behemoth covered in jagged, stone-like plates. The Rock Rumbler looks like a stout, armored crocodile with a low, broad body and a heavy tail used to crush foes. Its eyes glow faintly from crevices in the carapace, and loose grit and pebbles fall from its hide with each ponderous step.

## Appearance
- Thick rocky armor composed of interlocking plates and mineral deposits.
- Short, powerful limbs and a heavy club-like tail.
- Small, deep-set glowing eyes and a maw full of blunt teeth.
- Size and gait suggest brute strength rather than agility.

## Behavior
- Territorial and aggressive when surprised or cornered; will charge and attempt to break opponents.
- Moves deliberately — it closes distance methodically rather than flitting about.
- Not a skirmisher: prefers to stand its ground and trade heavy blows.
- Often found in rocky caverns and tunnel junctions (see [src/tilesets/verdette_caverns.py](src/tilesets/verdette_caverns.py)) and is used in early chapter encounters (see [src/story/ch01.py](src/story/ch01.py) and the AfterTheRumblerFight event).

## Special Abilities & Traits
- Natural heavy protection and brute force damage — designed as a durable frontline enemy.
- Armor interactions:
  - Highly resistant to slashing and piercing strikes and to many elemental attacks (see [`RockRumbler`](src/npc.py) resistance settings).
  - Significantly affected by crushing attacks — its bulk makes it susceptible to weapons that deliver concentrated blunt force.
- Combat repertoire reflects its tactics:
  - Uses direct attacks (`NpcAttack`) as primary offense.
  - Includes mobility moves to change engagement distance (`Advance`, `Withdraw`) allowing it to close or create space as needed.
  - Tends not to rely on complex status effects; instead, it is mechanically simple and physically dominant.
- Non-unique name generation: instances are named like "Rock Rumbler X" using the game's generator so multiple individuals look similar in the world.

## Tactics
- Close and hold: it will close distance with `Advance` and use heavy melee attacks to pressure single targets.
- If pressured or outnumbered it can back off with `Withdraw` to reorganize or exploit range.
- Best engaged with blunt/crushing weapons or abilities that bypass or exploit its heavy carapace.

## Example Stats (from code)
- HP: moderate (constructed with maxhp around 30 in the implementation)
- Damage: heavy (damage ~22)
- Protection: high (protection ~30)
- Awareness: decent (awareness ~25)
- Aggro: True — will engage when encountering the player
- XP Award: moderate (exp_award ~100)
See the implementation in [src/npc.py](src/npc.py) for the canonical values and move set.

## Encounter & Lore Notes
- The Rock Rumbler class is used as an early threatening encounter; the player meets similar creatures in cavern tiles described in the Verdette caverns tileset and story scenes (see [src/tilesets/verdette_caverns.py](src/tilesets/verdette_caverns.py) and [src/story/ch01.py](src/story/ch01.py)).
- Its carapace and slow speech/gestures are echoed in the friendly Gorran / "Rock-Man" NPC in the same chapter; narrative code reuses the rocky motif to connect combat encounters and NPC story beats.

## DM / Designer Tips
- Encourage players to switch to crushing weapons or moves when facing Rock Rumblers to make encounters feel tactical.
- Use narrow cavern geometry to emphasize their ability to block passages and force difficult choices.
- Consider pairing them with faster, flanking enemies (e.g., bats or lurkers) to negate the Rumbler's slow pace.

## References
- Code: [`RockRumbler` class](src/npc.py)  
- Moves: [`Advance`](src/moves.py), [`Withdraw`](src/moves.py), [`NpcAttack`](src/moves.py)  
- Story: [AfterTheRumblerFight event](src/story/ch01.py)  
- Tile examples: [Verdette caverns tileset](src/tilesets/verdette_caverns.py)
// ...existing code...