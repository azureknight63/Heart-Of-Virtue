# map-design

Expert indie game map designer for Heart of Virtue. Generates hierarchical, lore-integrated map design documents or audits existing maps for improvements.

## Modes

### New Map Design
Generate a complete map design document from concept, constraints, and lore hooks.

```
/map-design
theme: "a sacred spring corrupted by infection"
size: "medium (40-50 tiles)"
chapter: 2
key_encounters: ["The Infestation Queen", "Geode Puzzle Chamber"]
npcs: ["Gorran", "Conclave Searchers"]
narrative_moment: "Jean discovers the extent of the corruption"
```

Or conversationally:
```
/map-design
Design a map for Chapter 2 where Jean enters a Golemite sacred space corrupted by slime.
```

### Map Upgrade/Audit
Audit an existing map and recommend improvements.

```
/map-design --upgrade
map: "dark-grotto"
focus: "deepen lore integration and add secrets"
```

## Output

**New Map**: Complete markdown design document with:
- Executive summary & design philosophy
- Hierarchical zone breakdown (with ASCII diagrams)
- Room-by-room specifications (coordinates, descriptions, exits, encounters, items, NPCs, objects)
- Asset needs & dependencies (new items, NPCs, enemies, objects to create)
- Implementation notes for agents
- Lore integration checklist

**Upgrade/Audit**: Markdown audit report with:
- Current state analysis
- Thematic coherence assessment
- Environmental storytelling gaps
- NPC & encounter balance evaluation
- Puzzle quality & discoverability analysis
- Pacing & flow critique
- Lore depth assessment
- Categorized improvement suggestions (High Priority / Medium / Nice-to-Have)
- Before/after comparisons where helpful

## Design Principles

- **Lore first, mechanics second**: Every tile has a reason rooted in the world
- **Sensory prose**: Descriptions invoke touch, sound, smell, not just sight
- **Environmental storytelling**: Objects, items, NPCs tell history
- **Progressive complexity**: Early zones are tight; later zones layer mechanics
- **Secrets reward curiosity**: At least one genuinely discoverable secret
- **Narrative beats embedded**: Story moments anchor to tiles, not cutscenes
- **Descriptions are permanent**: Tile descriptions persist after NPCs are killed and items are picked up. Never write present-tense NPC behaviour ("The bats are aware of Jean", "Gorran places his hand on the crystal") or direct item references ("The supplies left here") into a description. Use durable environmental evidence instead — staining, claw marks, smells, worn stone, old fire rings — things that remain true regardless of entity state.

## Quality Standards

Outputs are verified against:
- [ ] Concept clearly stated and executed
- [ ] Zone breakdown hierarchical and coherent (3-5 zones)
- [ ] Room count matches size constraints
- [ ] Each room has clear purpose (no filler)
- [ ] Exits form playable graph (no orphans, no impossible loops)
- [ ] Lore integration explicit (characters, factions, theology)
- [ ] Implementation notes specific (class names, mechanics, patterns)
- [ ] ASCII diagrams readable and accurate
- [ ] Prose evocative and fits Heart of Virtue's voice
- [ ] Rewards meaningful and thematically tied

## References

- Lore root: `docs/lore/`
- Map files: `src/resources/maps/*.json`
- Map generator: `utils/map_generator.py`
- Existing examples:
  - Mineral Pools design: `docs/lore/environments/grondelith-mineral-pools/`
  - Dark Grotto implementation: `src/resources/maps/dark-grotto.json`
  - Wailing Badlands design: `docs/lore/environments/wailing-badlands/wailing-badlands-map-design.md`
  - Universe system: `src/universe.py`