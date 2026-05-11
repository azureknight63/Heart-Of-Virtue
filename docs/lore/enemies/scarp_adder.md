# Scarp Adder

A thick-bodied ambush serpent of the eastern slope — a solitary, patient predator that strikes with precision and venom. The Scarp Adder is 1.5–2 meters in length with scales layered like flakes of split shale, dark grey with silver edges. Nearly invisible against stone when coiled, it waits motionless for prey to stumble within striking distance, then delivers a venomous bite.

## Appearance
- Thick-bodied serpent, 1.5–2 meters in length
- Scales layered like flakes of split shale — dark grey with silver edges
- Naturally camouflaged against rocky terrain and stone surfaces
- Broad, triangular head with heat-sensing pits along the jaw
- Heat-sensing organs allow detection of warm-blooded prey in darkness
- Pale blue tongue that flickers constantly, tasting the air
- Coiled at rest, nearly invisible — appears only as a pile of stones until it strikes
- Moves with liquid grace when hunting

## Behavior
- Solitary hunter; territorial and defensive rather than gregarious
- Patient predator; will wait hours or days in optimal positions for prey to approach
- Ambush-focused; prefers to strike from concealment rather than engage openly
- Intelligent and cautious; avoids unnecessary combat with creatures much larger than itself
- Uses stone and terrain as camouflage and cover
- Aggressive when defending territory or after being provoked

## Special Abilities & Traits
- **Venom Claws**: Delivers venomous strikes that inflict poison damage and status effects
- **Ambush Predator**: High awareness (awareness: 40) and superior position detection allows it to strike from surprise
- **Stone Affinity**: Born from rocky slopes; slightly resistant to earth magic and earth-aligned damage
- **Fragile Scales**: Despite defensive posture, the serpent's scales are brittle against crushing attacks
- **Heat Sensing**: Can detect warm-blooded creatures even in darkness or through obscuring terrain
- **Tactical Positioning**: Uses terrain and stealth to advantage; prefers fights fought on its terms
- **Withdrawal**: Uses `Withdraw` to reposition and reset after striking, maintaining evasion

## Tactics
- **Ambush and strike**: Uses superior positioning to deliver the first `VenomClaw` attack before Jean can react
- **Venom strategy**: Prioritizes `VenomClaw` to apply poison and deal ongoing damage rather than raw attacks
- **Terrain exploitation**: Coils in rocky areas, disappears into stone, emerges to strike
- **Hit and withdraw**: Strikes with `VenomClaw` or `NpcAttack`, then uses `Withdraw` to reset distance
- **Patience**: Not aggressive in extended combat; prefers to outlast through poison damage and strategic disengagement
- **Evasion**: Uses `Dodge` sparingly; relies on positioning and movement rather than defensive actions

## Example Stats (from code)
- HP: moderate (maxhp=38)
- Damage: moderate (damage=20)
- Protection: light (protection=5) — minimal armor, relies on speed and positioning
- Awareness: high (awareness=40) — excellent at detecting prey
- Aggro: True — will engage on sight, especially if territory is threatened
- XP Award: moderate (exp_award=95)
- Move set: `NpcAttack`, `VenomClaw` (prioritized), `Withdraw`, `NpcIdle`, `Dodge`

## Resistances & Vulnerabilities

### Damage Resistances
- **Earth (0.8)**: Slightly resistant — stone affinity with earth magic
- **Crushing (1.2)**: Weak — brittle scales are vulnerable to blunt force
- **Slashing (1.1)**: Weak — scales are fragile and can be torn by sharp attacks

### Status Resistances
- No explicit status immunities — relies on positioning to avoid status effects

## Encounter & Lore Notes
- Scarp Adders are found on rocky slopes and in stone-filled areas of the eastern regions
- Dangerous when encountered in rocky terrain where their camouflage and heat-sensing give maximum advantage
- Often found in caves, rocky outcrops, or stone passages
- Multiple adders rarely occupy the same territory; solitary creatures by nature
- Are intelligent enough to flee from overwhelming odds; not suicidal predators
- Tracks and shed scales can indicate adder presence
- Local settlements may have folklore about territorial adders guarding sacred stone

## DM / Designer Tips
- **Terrain advantage**: Encounters should emphasize rocky terrain; open areas reduce the adder's tactical advantage
- **Surprise attacks**: First round advantage should feel meaningful; ambushed players are at a disadvantage
- **Poison strategy**: Emphasize poison damage and status effects; healing items become valuable
- **Fragility trade-off**: Despite weak defenses, the adder's positioning means it rarely takes direct hits
- **Crushing counter**: Blunt weapons and crushing attacks should feel distinctly more effective than slashing
- **Sensory descriptions**: Emphasize heat-sensing, camouflage, and the moment when coiled stone suddenly becomes a striking serpent
- **Solo threat**: Adders work best as solo encounters; they're not pack hunters and multiple adders are rarely encountered together
- **Evasion challenge**: Players who rely on landing hits must learn the adder's patterns; tactical positioning matters more than raw stats
- **Retreat mechanic**: A wounded adder that can safely withdraw may disengage and disappear into stone

## Character Notes
- Scarp Adders are natural predators, not corrupted creatures; they deserve respect and understanding
- Jean may recognize them as territorial dangers to avoid rather than enemies requiring destruction
- In some contexts, adder venom might be harvestable for alchemy or poisons

## References
- Code: [`ScarpAdder` class](src/npc/_enemies.py)
- Moves: [`VenomClaw`](src/moves/_npc.py), [`NpcAttack`](src/moves/_npc.py), [`Withdraw`](src/moves/_movement.py), [`Dodge`](src/moves/_movement.py)
- Related: [Lurker](lurker.md) — another venom-using enemy with different tactics and lore
