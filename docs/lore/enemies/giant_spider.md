# Giant Spider

An enormous arachnid covered in jet-black, wiry hairs, skittering about with predatory hunger. The Giant Spider is a primal ambush predator with sharp, poisonous mandibles and a propensity for venom. Its presence in dark caves and tunnel systems makes it a formidable foe for those who stumble into its web.

## Appearance
- Humongous spider with a body the size of a small dog or larger
- Covered in black, wiry hairs that bristle and twitch constantly
- Sharp, poisonous mandibles that flex with eager anticipation
- Spills toxic drool that leaves a glowing green trail in its wake
- Multiple gleaming eyes adapted for hunting in darkness
- Long, jointed legs allow rapid movement and climbing on any surface

## Behavior
- Aggressive predator; will hunt and attack living prey without hesitation
- Uses terrain to its advantage — climbs walls and ceilings to ambush from unexpected angles
- Coordinated and intelligent hunter; patient when stalking, explosive when striking
- Often found in webs or nest chambers in dark, damp places
- Aggro: True — will engage the player on sight

## Special Abilities & Traits
- **Spider Bite**: A signature venomous bite attack that deals poison damage and can apply poison status effects
- **Poison Affinity**: Naturally produces and weaponizes venom; immune to poison damage
- **Ambush Predator**: High awareness (awareness: 30) allows it to spot prey from distance
- **Agility**: Uses movement abilities to close distance and maintain advantage
- **Endurance**: Moderate endurance (endurance: 10) — designed for burst combat rather than prolonged battles
- **Movement**: Uses `Advance` to close distance and `Withdraw` to reset positioning; prioritizes maintaining optimal range for bite attacks

## Tactics
- **Venom strategy**: Prioritizes `SpiderBite` to apply poison and deal ongoing damage
- **Close and engage**: Uses `Advance` to close distance quickly, putting prey at a disadvantage
- **Tactical retreat**: Uses `Withdraw` to reposition and avoid heavy counterattacks
- **Evasion**: Dodging is employed when necessary to reset positioning
- **Bite focus**: Most dangerous when given the opportunity to land repeated `SpiderBite` attacks; poison wears down enemies over time

## Example Stats (from code)
- HP: moderate-high (maxhp=110)
- Damage: moderate (damage=22)
- Protection: none (protection=0) — relies on agility and poison damage
- Awareness: decent (awareness=30) — good at spotting prey
- Endurance: low (endurance=10) — prefers quick, decisive strikes
- Aggro: True — will attack on sight
- XP Award: moderate (exp_award=120)
- Move set: `NpcAttack`, `SpiderBite` (prioritized), `Advance`, `Withdraw`, `NpcIdle`, `Dodge`

## Resistances & Vulnerabilities

### Damage Resistances
- **Fire (-0.5)**: Takes increased damage from fire — heat and flames damage the creature

### Status Resistances
- **Poison (1.0)**: Immune to poison — it manufactures its own venom

## Encounter & Lore Notes

**Location & Distribution**: Giant Spiders inhabit dark, sheltered biomes throughout **Chapter 3 and beyond**: deep forests where canopy shadows create perpetual twilight, swamp caverns and underground chambers, cliff-face caves, and corrupted ruins where webs overtake ancient stonework. They are not found in open plains or deserts—they require cover, moisture, and darkness to thrive.

**Corrupted or Natural?**: The true nature of Giant Spiders remains ambiguous. Some scholars argue they are natural predators bloated to unnatural size by corruption. Others insist they are something summoned or created by the darkness itself. The spiders offer no clear answer: they hunt with unnatural intelligence yet follow patterns that seem wholly animal. This ambiguity is their defining characteristic.

**Danger & Lethality**: Their venom carries a quality that feels almost *intentional*—as if each drop is specifically designed to weaken prey. Poison accumulates in wounds, and victims who escape often find the venom continues to work long after the encounter, suggesting it was crafted rather than evolved.

**Jean's Arc Connection (Oblique)**: Jean must learn to distinguish between natural threats and corruption spreading through the world. Giant Spiders present a test of this judgment: are they evil things to be destroyed, or are they simply predators in a corrupted land? The ambiguity mirrors Jean's own struggle to understand what must be fought and what must merely be accepted as part of a fallen world.

## DM / Designer Tips
- **Emphasize poison danger**: Make poison damage meaningful in encounters; healing items and poison resistance become valuable
- **Use terrain**: Spider encounters benefit from vertical or complex terrain where the spider's climbing and positioning abilities shine
- **Venom delay**: The poison damage from `SpiderBite` should be telegraphed so players understand they're being worn down
- **Fire as solution**: Emphasize fire damage as a counter to spiders — torches, fire spells, burning areas
- **Web atmosphere**: Describe sticky webs, the smell of venom, the sound of chittering — make the encounter visceral
- **Pairing**: Spiders work well with other cave dwellers (bats, slimes) to create layered encounters

## References
- Code: [`GiantSpider` class](src/npc/_enemies.py)
- Moves: [`SpiderBite`](src/moves/_npc.py), [`NpcAttack`](src/moves/_npc.py), [`Advance`](src/moves/_movement.py), [`Withdraw`](src/moves/_movement.py), [`Dodge`](src/moves/_movement.py)
