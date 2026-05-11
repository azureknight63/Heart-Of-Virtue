# Talus Hound

A lean, shaggy pack hunter of the eastern slope — a territorial quadruped roughly the size of a large dog with extraordinary agility and coordination. Talus Hounds are dangerous in numbers due to their flanking tactics and hit-and-run coordination. When hunting alone, they exhibit defensive, cautious behavior. When in a pack, they become a coordinated predatory force capable of overwhelming prey through tactical positioning.

## Appearance
- Lean, shaggy quadruped roughly the size of a large dog
- Layered hide — thick, close-lying fur over a leathery undercoat
- Mottled grey-brown coloration, camouflaged for rocky terrain
- Heavily muscled legs suggesting explosive speed on rough terrain
- Broad, low-set head with pale amber eyes adapted for detecting movement at distance
- Alert posture; constantly scanning for prey and threats

## Behavior
- Territorial hunters; will aggressively defend territory but respect significant threats
- Coordinated pack behavior; individuals adapt tactics based on pack size
- Patient stalkers; will shadow prey, looking for weakness or isolation
- Explosive burst speed despite lean build; dangerous at any range
- Pack hierarchy: when multiple hounds fight together, they coordinate flanking and hit-and-run tactics
- Highly aware of surroundings (awareness: 30); difficult to ambush

## Special Abilities & Traits
- **Pack Awareness**: Each Talus Hound's tactics adapt based on how many allies are present — solo behavior differs radically from pack behavior
- **Flanking Maneuver**: Signature move that positions the hound for coordinated attacks; significantly more effective with allies nearby
- **Hit-and-Run Tactics**: Uses `Withdraw` strategically to disengage and reset positioning, maintaining distance advantages
- **Explosive Movement**: High base damage (damage: 14) and good awareness despite modest HP
- **Evasion**: Relies on dodging rather than armor; trained movement is their defense
- **Coordination**: Pack members adjust move priorities based on total pack size:
  - **Large pack (3+)**: Emphasizes flanking, coordinated strikes, and aggressive positioning
  - **Small pack (2)**: Balance of hit-and-run tactics and occasional flanking attempts
  - **Solo**: Extreme emphasis on withdrawal and evasion; acts as a skirmisher

## Tactics

### Pack Tactics (3+ hounds)
- **Coordinated assault**: Multiple hounds advance together, using flanking maneuvers for bonus damage
- **Overwhelming pressure**: Attacks come from multiple angles; difficult for a single opponent to defend
- **Rotation**: Hounds rotate in and out, maintaining pressure while recovering
- **Encirclement**: Attempts to surround prey, limiting retreat options

### Small Pack Tactics (2 hounds)
- **Hit-and-run cycles**: One hound attacks while the other prepares to retreat and reset
- **Balanced flanking**: Occasional flanking attempts when both hounds coordinate
- **Mutual support**: One hound can distract while the other delivers crushing damage

### Solo Tactics (1 hound)
- **Defensive skirmishing**: Prioritizes withdrawal and dodge, striking and retreating
- **Maintain distance**: Refuses to commit to sustained melee; hits and backs away
- **Evasion focus**: Solo hounds are warier; they prioritize avoiding damage over dealing it
- **Selective strikes**: Only attacks when certain of solid hits

## Example Stats (from code)
- HP: moderate (maxhp=50)
- Damage: moderate (damage=14)
- Protection: light (protection=8)
- Awareness: good (awareness=30) — hard to surprise
- Aggro: True — will engage on sight
- XP Award: moderate (exp_award=80)
- Move set: `NpcAttack`, `Advance`, `Withdraw` (prioritized in solo hunts), `FlankingManeuver` (prioritized in packs), `Dodge`, `NpcIdle`

## Pack Behavior Algorithm

The Talus Hound's `select_move()` method includes sophisticated pack-aware AI:

- **Count pack members**: Determines living TalusHounds in the same combat
- **Adjust weights dynamically**: Move priorities shift based on pack composition
  - Large packs: `FlankingManeuver` weight +6, `Advance` weight +3, `Withdraw` weight -2
  - Small packs: `Withdraw` weight +4, `Flanking Maneuver` weight +2, `Dodge` weight +1
  - Solo: `Withdraw` weight +5, `Dodge` weight +3, `FlankingManeuver` weight -3
- **Fatigue management**: If unable to attack due to fatigue, will rest if possible
- **Viable move selection**: Ensures selected moves have sufficient fatigue budget and can be executed

## Resistances & Vulnerabilities

### Damage Resistances
- No explicit resistances or vulnerabilities — relies on movement and positioning rather than armor

### Status Resistances
- No explicit status resistances — designed to be fast-moving rather than status-resistant

## Encounter & Lore Notes
- Talus Hounds are found on the eastern slopes and rocky highlands
- Danger scales significantly with pack size; a lone hound is manageable, but a coordinated pack is formidable
- Often encountered in open terrain where their speed and flanking tactics are most effective
- Pack structure mirrors real wolf/dog packs; hierarchy and coordination are natural to them
- Are not mindlessly aggressive; they assess threats and withdraw if significantly outmatched
- Environmental storytelling: tracks, scat, and kills can indicate pack presence and size

## DM / Designer Tips
- **Communicate pack dynamics**: Describe coordinated movements and flanking attempts so players understand the threat
- **Reward separation**: Isolating a single hound from the pack removes its most dangerous tactics
- **AoE potential**: Area-of-effect abilities can disrupt pack coordination by hitting multiple enemies simultaneously
- **Terrain utilization**: Rocky, open terrain favors hounds; tight spaces limit their movement advantage
- **Flee mechanics**: Solo hounds should flee if seriously wounded; packs are more committed
- **Scaling encounters**: Use 1-3 hounds to create encounter variety without requiring new NPC types
- **Threat assessment**: Hounds are intelligent enough to recognize when they're outmatched; they hunt strategically, not suicidally
- **Narrative impact**: A pack's territory and hunting patterns can be woven into the world; dead prey, dens, etc.

## Character Notes
- Talus Hounds are not evil, merely territorial predators; they can be avoided or reasoned with in some contexts
- Represents a natural threat vs. corrupted/supernatural threats; adds ecosystem realism to the world

## References
- Code: [`TalusHound` class](src/npc/_enemies.py) — includes `select_move()` pack-aware AI and `_count_pack_members()` helper
- Moves: [`NpcAttack`](src/moves/_npc.py), [`Advance`](src/moves/_movement.py), [`Withdraw`](src/moves/_movement.py), [`FlankingManeuver`](src/moves/_npc.py), [`Dodge`](src/moves/_movement.py)
- AI: [NPCAIConfig](src/npc_ai_config.py) — optional weighted move bonus system
