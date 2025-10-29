# Slime
Slimes are viscous, gelatinous creatures that ooze through caverns, dungeons, and damp ruins. They are simple organisms, more a sentient puddle than a traditional monster — amorphous, silent, and disturbingly persistent. Up close they look like shimmering blobs of semi-translucent goo, sometimes flecked with mineral grains or trapped detritus.

## Appearance
- Amorphous, gelatinous body; color varies from pale green to murky gray depending on environment and diet.
- No obvious limbs, but rippling surfaces and occasional pseudopod-like bulges let them creep along floors and squeeze through cracks.
- Often contains swallowed stones, insect chitin, or other debris that clinks when disturbed.

## Behavior
- Slow-moving and undirected by nature, slimes react primarily to vibrations, light, and sudden disturbances.
- They are aggressive when provoked and will converge on nearby living things to consume organic material or overwhelm prey by sheer volume.
- Simple creatures: they lack complex tactics and rely on persistence, numbers, and the ability to soak damage.

## Special Abilities & Traits
- Amorphous: Slimes can flow into tight spaces and are often used to block passages in narrow tunnels.
- Corrosive Touch: their goo can sometimes damage or irritate on contact, representing low but persistent threat over time.
- Splitting (variant): larger slimes or specially keyed slimes may split into smaller individuals when damaged (not every Slime class does this in code; check implementation).
- Low cognition: unlikely to use complex status abilities; typically perform basic attacks and movement (see [`NpcAttack`, `Advance`, `Dodge`] in the code).

## Tactics
- Mob pressure: slimes are most dangerous in groups — they gang up and wear down single targets through repeated attacks.
- Close and engulf: they move forward (`Advance`) and use simple attacks to harry foes; if the party lacks blunt or high-damage single-target options, slimes can become a nuisance.
- Vulnerable to area and high-precision damage: because they are fragile individually, area-of-effect spells or weapons that deal concentrated damage handle them well.

## Example Stats (from code)
- Source: `src/npc.py` — `class Slime` (constructor values)
- HP: 10 (maxhp=10)
- Damage: 20 (damage=20) — note: this value in code represents the NPC damage parameter and may be scaled by moves/attacks
- Awareness: 12 (awareness=12)
- Aggro: True — will engage the player on sight
- XP Award: 1 (exp_award=1)
- Typical move set: `NpcAttack` (primary), `Advance` (to close distance), `NpcIdle`, `Dodge` (see `src/npc.py`)

> Implementation note: the numbers above are taken directly from the `Slime` class in `src/npc.py`. The damage value may seem high compared to HP because NPC damage and weapon/player damage scales are separate and handled in the combat system.

## Encounter & Lore Notes
- Common in damp caverns, sewers, and ruins; slimes are ideal low-level encounters or environmental hazards that punish careless exploration.
- Because of their amorphous shape, they can be found seeping from cracks in walls or pooling under ledges. Maps and spawners may produce several at once (see `NPCSpawnerEvent` in `src/story/effects.py`).

## DM / Designer Tips
- Use slimes to teach players about crowd control and area damage: a single Slime is easy, but a cluster forces more thoughtful resource use.
- Place slimes in chokepoints or alongside harder single foes (e.g., a Rock Rumbler) to create layered encounters.
- Flavor them: describe the smell, the sound of grit within them, and how light refracts through their gelatinous bodies to make a simple enemy feel atmospheric.

## References
- Code: `src/npc.py` (see `class Slime`)
- Moves: `src/moves.py` (`NpcAttack`, `Advance`, `Dodge`)
- Spawner: `src/story/effects.py` (`NPCSpawnerEvent`)
