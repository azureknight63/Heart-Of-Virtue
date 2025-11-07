# Corrupted Channels — Area Profile

Purpose & Tone
---------------
The Corrupted Channels are the game's primary traversal challenge for the Mineral Pools. The channels should feel claustrophobic, slick, and dangerous compared to the Atrium. Design for movement puzzles, emergent combat, and incremental difficulty increases as players progress toward the Heart.

Tile Types & Design
-------------------
- Slimed Floor (standard): Tiles that slow movement slightly and have a minor "slime" damage or sticky status if the player stands too long.
- Slime Water (shallow): Passable tiles that occasionally spawn small slimes or cause slipping checks. Use these to create risk/reward traversal.
- Slime Bridges (narrow): Walkable tiles with lower width (design as narrow connections) that can be fouled by slime; require careful movement or timed crossings.
- Pulsing Gland (hazard): A stationary environmental object that periodically ejects projectiles or spawns small slimes; provides tactical cover and timing puzzles.
- Dissolving Stone (weak tiles): Tiles that will collapse after N steps or upon certain triggers; opens alternate routes or creates urgency.

Encounter & Enemy Placement
---------------------------
- Progressive difficulty: Start with small slimes and ambushes; scale to spitter/medium slimes near glands and larger aggregations approaching the Heart.
- Ambush design: Use narrow corridors and slime bridges to funnel players into small-group combat encounters.
- Patrols & Intelligence: Band together slimes with roaming behaviors that follow scent-trail heuristics (simple pathing toward the player when within X tiles).

Traversal Mechanics
------------------
- Traction checks: When crossing Slime Bridges or Slime Water, use a simple skill check (player.finesse or a roll) to avoid slipping; slipping may move the player into adjacent slime tiles or cause a short stun.
- Timed crossing: For some bridges, require timing (toggled by a Pulsing Gland) or create sequences of safe tiles that appear/disappear.

Map & Tile Notes
----------------
- Layout: Design the channels as interconnected caverns with branching dead ends that reward exploration. Use environmental cues (color shifts, echo changes) to hint at proximity to the Heart.
- Symbols: Use `symbol: "s"` for slimed floor, `symbol: "="` for slime bridges, and `symbol: "g"` for pulsing glands in map JSON.
- Events: Implement `GlandEruptEvent` objects with timers and clear telegraphs (visual pulses) so players can plan crossings.

Implementation Pointers
---------------------
- Reuse or extend existing move/AI classes for slime behavior; ensure spawn caps per region to control performance.
- For dissolving stone, store a tile property `integrity:int` that decrements when stepped on and triggers a `CollapseEvent` when it hits zero.
- Provide a fallback path or recovery item; avoid total soft-locks where a player cannot progress without dying.

Testing & Balancing
-------------------
- Create unit tests for Pulsing Gland timing and CollapseEvent triggers. Test different player stat levels to ensure skill checks are meaningful but not punitive.
- Balance enemy density so that corridor fights are tense but not overwhelming; provide small safe niches for recovery.
