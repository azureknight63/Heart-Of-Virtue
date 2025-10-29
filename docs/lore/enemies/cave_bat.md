# Cave Bat
Cave Bats are small, nocturnal flyers that inhabit dark caverns and narrow tunnels. They appear as leathery-winged mammals with dark fur, sharp fangs, and small, glowing eyes. Their silent flight and nimble movement make them a classic nuisance enemy — dangerous mainly because they strike from the air in groups and exploit cramped spaces.

## Appearance
- Small, bat-like body with membranous wings and short, hooked claws.
- Dark brown to black fur; eyes sometimes show a faint glow in the dark.
- Often seen in loose clusters clinging to cave ceilings or flitting between stalactites.

## Behavior
- Nocturnal and crepuscular: most active in dim light and darkness.
- Use echolocation to navigate complete darkness; rarely stray into open daylight.
- Tend to swarm: individual bats are fragile, but they harass and overwhelm targets by numbers.

## Special Abilities & Traits
- Echolocation: allows movement and targeting in total darkness (used as a flavor mechanic in maps and encounters).
- Flight Agility: high mobility in three dimensions; can avoid ground-only attacks and reposition quickly.
- Swarm Tactics: prefer group engagement — multiple individuals coordinate to harry a single target.
- Screech: a high-pitched vocalization that can disorient or interrupt (represented in some NPC variants as a minor debuff or interrupt).
- Vampiric / Drain effects (variant): some bat variants or named individuals have a small life-drain on bite, restoring a little HP when they hit.

## Tactics
- Hit-and-run: use `Advance` to close, strike with `NpcAttack`, then reposition; rely on numbers rather than single-target durability.
- Harass fragile targets: they pressure spellcasters and lightly armored characters by keeping distance and using mobility.
- Pairing: commonly paired with slower, heavier enemies (e.g., Rock Rumblers) to flank or distract while the heavy foe engages the party.

## Example Stats (from code)
- HP: low (fragile individually)
- Damage: low-to-moderate per-hit, sometimes with a small life-drain effect on variants
- Awareness: moderate — they detect movement and sound but avoid bright light
- Aggro: usually True for cavern-spawned instances (will engage if the player enters their space)
- XP Award: low per individual; grouped encounters scale challenge
- Typical move set: `NpcAttack` (primary), `Advance` (close), `Withdraw`/`Dodge` (reposition)

## Encounter & Lore Notes
- Common in cave systems, abandoned mines, and ruins with large open caverns or many overhangs.
- Use them to create dynamic vertical threats: attacks from above or flitting through pillars and stalactites.
- Flavor description: emphasize soft wing beats, the metallic scent of guano, and the echoing squeaks that precede a swarm.

## DM / Designer Tips
- Use Cave Bats to teach players about area control and crowding: one bat is a minor nuisance, a flock becomes a tactical challenge.
- Place them in numbers in wide caverns or as ambushes from above in multi-tier maps to punish standing still.
- Combine with heavier foes to split the party's attention and create interesting combat priorities.

## References
- Code: `src/npc.py` (see bat/cave variants)
- Moves: `src/moves.py` (`NpcAttack`, `Advance`, `Withdraw`, `Dodge`)
```