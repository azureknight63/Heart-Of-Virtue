# WailWraith

A ghastly presence native to the Wailing Badlands — not a hazard alongside the region's ever-present wail, but its source. Where the Corrupted Stone Creature is corruption's failed attempt to *build*, the WailWraith is grief given voice and left to wander: a shape woven from sound and absence, more heard than seen, that arrived somewhere in the Keening Canyon and never stopped keening. It does not attack out of hunger or territory. It attacks because it cannot stop making the sound, and the sound takes something from whatever is near enough to hear it.

## Appearance
- A ragged, indistinct shape — closer to a distortion in the air than a body
- No stable silhouette; edges blur and shift like heat haze or a sound made visible
- Occasionally coheres into something almost humanoid, then dissolves again
- Trails a low, wearing note wherever it moves — the source of the Keening Canyon's name
- Air around it feels thinner; sound behaves strangely near it (echoes arrive early, voices drop out)
- No discernible eyes or face — it does not need to see Jean to find him

## Behavior
- Drawn to living presence rather than sight; reacts to proximity and to grief-adjacent conditions in the canyon (Auditory Strain accumulation, per the map design doc)
- Does not stalk or ambush in the conventional sense — it arrives, the way weather arrives
- Relentless once engaged: it does not disengage, retreat far, or lose interest
- Patient in a way that reads as cruelty: it does not need to win quickly. Every beat it survives, it is winning
- Immune to being reasoned with, frightened off, or out-toughed through brute force — this is the encounter's central lesson

## Special Abilities & Traits
- **Keening Toll** (primary): a wearing note that saps fatigue directly rather than dealing HP damage. Higher move weight than Wail Strike — this is what the WailWraith reaches for most, and it's the real threat: attrition, not burst damage
- **Wail Strike** (telegraphed secondary): a harder, slower, more visible sonic attack — extended wind-up gives a genuine dodge window, but landing it hits hard and ignores protection entirely (sonic damage bypasses armor), with a chance to leave the target Resonant (armor-bypassing damage-over-time, Finesse -25%)
- **Death Knell** (execute): only usable once the target's fatigue has already been worn down below 10% of max FP by Keening Toll. A landed, unparried Death Knell is an immediate, forced kill — not a chance-based status effect the target might resist
- **Conventional immunity**: slashing, piercing, and crushing damage do nothing. Physical weapons alone cannot bring it down
- **Elemental/magical vulnerability**: Pure and Light damage land at double effect; Dark lands at half; Fire, Ice, Shock, Earth, and Spiritual all land normally. The player needs an appropriately enchanted weapon (or the right spell/ability) to make real progress — this is not a fight brute force wins

## Tactics
- **Open with Keening Toll, repeatedly**: the WailWraith leans on fatigue drain far more than on Wail Strike, grinding the target toward the execute threshold over the course of the fight rather than racing to burst them down
- **Wail Strike as punctuation**: used less often, but its long telegraph is a deliberate tell — a player who's paying attention can Dodge it, so the WailWraith isn't relying on it landing every time; it's pressure, not the plan
- **Death Knell the moment it opens up**: as soon as the target's FP crosses below 10%, Death Knell becomes viable and the WailWraith will reach for it — this is the fight's real climax, and the player's fatigue management (not their HP bar) is what decides whether they see it
- **No retreat, no yield**: `can_yield = False`. The WailWraith does not flee when wounded and never offers the player an easy out
- **Physical attacks are a waste of a turn**: without elemental/magical damage, Jean cannot meaningfully hurt it — the encounter is designed to force a gear or ability check, not a longer fight

## Example Stats (from code)
- HP: moderate for its tier (maxhp=190) — a ghost, not a brick; the threat is attrition and the execute condition, not raw HP to chew through
- Damage: moderate direct (damage=30), most of the real pressure comes from fatigue drain rather than HP damage
- Protection: none (protection=0) — it isn't armored, it's simply untouchable by the wrong tools
- Awareness: high (awareness=55)
- Speed: high (speed=35) — evasive, hard to pin down
- Finesse: high (finesse=40) — hard to land physical attacks on even when they'd do nothing anyway
- Endurance: moderate (endurance=15)
- Aggro: True
- XP Award: significant (exp_award=650) — comparable to a Chapter-gating threat like the Lurker
- Idle message: "drifts at the edge of hearing"
- Alert message: "turns toward Jean, and the keening begins"
- Move set: `KeeningToll` (weight 5, primary), `WailStrike` (weight 3, telegraphed secondary), `DeathKnell` (weight 4, execute — gated by `viable()` on the target's FP), `Advance`, `Withdraw`, `NpcIdle`, `Dodge` (weight 2)

## Resistances & Vulnerabilities

### Damage Resistances
- **Slashing (0.0)**: Immune — conventional edged weapons do nothing
- **Piercing (0.0)**: Immune — conventional piercing weapons do nothing
- **Crushing (0.0)**: Immune — conventional blunt weapons do nothing
- **Pure (2.0)**: 2x weakness — pure damage is the cleanest counter
- **Light (2.0)**: 2x weakness — light burns through whatever it's made of
- **Dark (0.5)**: Resistant — half damage; the WailWraith is grief, not malice, and doesn't fear the dark the way it fears being seen
- **Fire, Ice, Shock, Earth, Spiritual (1.0 each)**: Land normally — no special-case, these are viable if the player has nothing better

### Status Resistances
- **Death (1.0)**: Fully resistant to death being inflicted *on the WailWraith* — unrelated to Death Knell, which it inflicts on its target. The move's own effect bypasses the target's resistance entirely (`force=True`) rather than depending on it, so this stat only matters if something else ever tries to kill the Wraith via a death-type effect
- **Doom (1.0)**: Fully resistant, same reasoning as above

## Encounter & Lore Notes

**Location & Chapter**: The WailWraith is the Keening Canyon's signature threat (Zone 2 of the Wailing Badlands, per the map design doc) — a later-chapter encounter, tiered above the Grondelith-area enemies. The canyon's environmental hazard, Auditory Strain ("accumulates during exposure to the wail... at 75% strain, Jean experiences a brief memory fragment (rage-related)"), was written before the WailWraith existed as a creature. This profile makes the Wraith retroactively *the source* of that hazard, not just a monster that happens to live somewhere loud.

**The Broken Spear**: the map design doc places a broken spear at (5, 2) — "environmental storytelling: someone fought here and didn't survive." The WailWraith is the intended author of that scene: a previous traveler who tried to fight it the conventional way, dealt no damage no matter how hard they swung, and was worn down by Keening Toll until Death Knell finished it. The spear is what's left. Nothing about the WailWraith needs to say this out loud — the room already does.

**Anger Stage of Grief**: the Wailing Badlands embody the Anger stage of Jean's grief arc. The WailWraith fits that register precisely: it is not cruelty, not malice, not a monster with a plan. It is grief that never resolved into anything else, still making the same sound, still taking from whoever gets close enough to hear it. Fighting it is not a contest of strength — it's an argument about whether raw force is ever going to be enough to make grief stop, and the game's mechanics (immune to conventional damage, weak only to Pure/Light) answer that question before the player even swings.

**Why the target must already be weary**: Death Knell's gate — under 10% max FP — means the WailWraith cannot simply end the fight on its own terms from full health. The player has to already be spent for the execute to become live. Thematically: grief doesn't kill the strong outright. It waits for exhaustion.

## DM / Designer Tips
- **Gear/ability check, not a DPS check**: signal early (dialogue, environmental description, a failed physical hit that visibly does nothing) that conventional weapons won't work here, so the player isn't left guessing why their sword swings through it
- **FP is the real health bar**: consider surfacing this to the player clearly in the UI/narration during the fight — the HP bar matters less than watching fatigue creep toward the 10% line
- **Telegraph Wail Strike generously**: its whole design point is a dodge window; don't undercut that with vague or late narration
- **Keening Toll should feel relentless, not spammy**: vary the narration (`refresh_announcements`) enough that repeated casts don't read as a stuck loop — the note is the same, but describe it landing differently each time if extending the flavor text later
- **Death Knell should land as a genuine "oh no" beat**: it's rare (gated), so when it fires, let the narration carry weight — this is the moment the fight has been building toward, not a random status proc
- **Loot**: currently inherits `loot.lev1` (Lurker's tier) with no unique drop yet — a signature item (thematically: something that quiets sound, or a fragment tied to the canyon's grief) is a natural follow-up but out of scope for this pass

## Lore Implications
- The WailWraith confirms that Auditory Strain in the Keening Canyon has an actual source, not just ambient hazard design — the canyon's "constant, piercing" wail (per the map doc) is this creature, felt before it's seen
- It's evidence that not every threat in Aurelion is corruption in the Grondelith sense — this is something native to grief itself, independent of the Slime/mineral-pool corruption arc
- Its immunity to conventional damage is a deliberate mechanical argument: some things cannot be fought the way Jean has been fighting everything else so far. The Badlands as a whole are where his combat toolkit (and his coping mechanism — force, directness, hitting the problem until it stops) gets tested and found insufficient on its own

## References
- Code: [`WailWraith` class](src/npc/_enemies.py)
- Moves: [`KeeningToll`, `WailStrike`, `DeathKnell`](src/moves/_npc.py), [`Advance`/`Withdraw`/`Dodge`](src/moves/_movement.py)
- State: [`Death`](src/states.py) — the one-shot kill Death Knell inflicts
- Map design: [Wailing Badlands map design doc](../environments/wailing-badlands/wailing-badlands-map-design.md), Zone 2 (The Keening Canyon)
- Design discussion: GitHub issue #350
