# Corrupted Stone Creature

Animated mineral sediment from the Grondelith Mineral Pools — a failed golemite formation. Not a true sentient creature, not an awakened earth spirit, but rather corrupted mineral mass reacting blindly to intrusion. A manifestation of the pools' degradation — mindless stone animated by the same corruption that spawned the King Slime, moving without hesitation and trailing a grey slurry that hardens on contact.

## Appearance
- A mass of mineral sediment loosely bound into a lurching, humanoid-vague shape
- Surface composed of fragments, pebbles, and crystalline shards held together by corrupted slurry
- Moves without hesitation, trailing a grey hardening slurry in its wake
- Ground beneath it slowly solidifies where the slurry pools
- No discernible features; occasionally a shape that might be an eye or mouth, but never clearly
- Crackles and grinds audibly as it moves; stone scrapes against stone with each step
- Emits the scent of mineral dust and corruption

## Behavior
- Mindless and reactive; no intelligence beyond hunger and territorial aggression
- Responds to vibration and proximity rather than visual stimuli
- Attacks anything living that enters its territory without hesitation
- Slow and deliberate movement; not agile, but inexorable
- Will pursue Jean relentlessly within its territory but lacks the intelligence to track fleeing prey far beyond its domain
- Immune to persuasion, negotiation, or tactical maneuvering — it is simply stone reacting to intrusion

## Special Abilities & Traits
- **Mineral Spit**: Sprays corrupted mineral slurry at range; hardens on contact, potentially slowing or impeding targets
- **Crushing Bulk**: Trades speed for durability; moves slowly but is difficult to stop once engaged
- **Stone Affinity**: Born from the pools' corruption; naturally resistant to earth magic
- **Fragility to Precision**: Despite its bulk, the creature is loosely bound; slashing and piercing attacks exploit the gaps between mineral fragments
- **Fire Weakness**: Heat destabilizes the slurry binding; fire is particularly effective
- **Geological Slowness**: Very low speed (speed: 5); every movement is ponderous and deliberate
- **Slurry Trail**: Leaves hardening slurry; visual indicator of the corruption's spread

## Tactics
- **Mineral Spit strategy**: Opens combat with `MineralSpit` at range, attempting to slow or disable Jean
- **Advance methodically**: Closes distance with determined `Advance` moves despite slow speed
- **Overwhelming presence**: Relies on sheer mass and hitpoint pool to grind down enemies through attrition
- **Tactical retreat**: Uses `Withdraw` rarely, only when heavily damaged; prefers to stand ground
- **Idle positioning**: Uses `NpcIdle` to recover and reset stance between assaults
- **Persistence**: Continues attacking until destroyed; will never flee or disengage

## Example Stats (from code)
- HP: moderate (maxhp=60)
- Damage: moderate (damage=22)
- Protection: moderate (protection=18) — bulk provides substantial defense
- Awareness: low (awareness=15) — reacts to proximity rather than detection
- Speed: very slow (speed=5) — ponderous, mineral-heavy movement
- Aggro: True — will attack on sight
- XP Award: low (exp_award=18) — minimal threat relative to encounters in the Pools
- Idle message: "scrapes slowly across the stone floor"
- Alert message: "lurches toward Jean, mineral slurry trailing behind it!"
- Move set: `NpcAttack`, `MineralSpit` (signature move), `Advance`, `Withdraw`, `NpcIdle`

## Resistances & Vulnerabilities

### Damage Resistances
- **Slashing (0.4)**: Weak — slashing attacks exploit gaps in the stone
- **Piercing (0.4)**: Weak — piercing attacks separate mineral fragments
- **Crushing (1.6)**: Resistant — crushing compacts the creature rather than damaging it
- **Fire (1.4)**: Weak — heat destabilizes the slurry binding
- **Earth (0.5)**: Resistant — mineral affinity with earth magic

### Status Resistances
- **Stone (0.0)**: Immune — the creature is already made of stone; petrification has no effect
- **Slow (-0.5)**: Vulnerable — slow effects are extra effective against the already-ponderous creature

## Encounter & Lore Notes
- Corrupted Stone Creatures are found in the deeper chambers of the Grondelith Mineral Pools
- Represent failed animations; evidence of corruption attempting and failing to create true awakened guardians
- Scattered throughout the pools like grave markers of failed experiments in corrupted creation
- Their presence indicates heavy corruption; areas with multiple creatures are deeply tainted
- The slurry trails they leave behind harden slowly, altering the landscape and creating hazards
- Sometimes found guarding resource-rich mineral deposits or contested territory within the pools
- Are not natural; they are symptoms of corruption, not native to the world

## DM / Designer Tips
- **Corruption marker**: Their presence indicates the severity of the pools' degradation
- **Terrain alteration**: Hardening slurry creates dynamic obstacles; multiple creatures can reshape maps over time
- **Slow but inevitable**: Emphasize that the creature is implacable; speed is not its weakness
- **Fire focus**: Encourage fire-based damage as the optimal counter
- **AoE vulnerability**: The creature is large and slow; area-of-effect abilities are particularly effective
- **Slurry hazard**: Describe the hardening slurry as a visual/mechanical threat; stepping in it slows Jean
- **Mindless narrative**: Unlike intelligent enemies, this creature deserves no mercy dialogue — it is pure corruption
- **Low reward**: Defeating a Stone Creature grants minimal experience; it is a hazard more than a genuine challenge
- **Environmental story**: The slurry trails tell a story; map designers can use them to show creature movement and territory

## Lore Implications
- Stone Creatures are evidence that the corruption is attempting to create constructs and guardians
- Their failure suggests that true awakening (like Golemites) is difficult or impossible under corruption
- They represent the pools' "immune system" gone wrong — the land itself attacking intruders
- Destruction of many creatures might be part of purifying the pools or proving Jean's power over corruption

## References
- Code: [`CorruptedStoneCreature` class](src/npc/_enemies.py)
- Moves: [`MineralSpit`](src/moves/_npc.py), [`NpcAttack`](src/moves/_npc.py), [`Advance`](src/moves/_movement.py), [`Withdraw`](src/moves/_movement.py), [`NpcIdle`](src/moves/_npc.py)
- Related: [King Slime](king_slime.md) — another manifestation of pools corruption
- Lore context: Grondelith Mineral Pools, Chapter 1 corruption arc
