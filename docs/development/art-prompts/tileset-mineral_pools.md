# Tileset: Grondelith Mineral Pools

Region key: `mineral_pools`  
Deliver as `tileset__mineral_pools.png` (1 row x 7 tiles).

Tile order and the variant key each one becomes:

1. `polished_stone` -- polished pale stone floor with carved swirling channels, three variations
2. `luminous_pool` -- a basin of glowing milky-blue spring water
3. `corrupted_slime` -- a thick sheet of iridescent green corrupted slime, acid-pitted stone beneath
4. `basin_rim` -- a raised carved basin rim, one step up
5. `mineral_spire` -- a fractured crystalline mineral spire, impassable
6. `channel_wall` -- a carved stone channel wall, top-down
7. `chasm` -- a dissolved hole in the floor, edges acid-pitted

```text
SUBJECT: terrain tileset for Grondelith Mineral Pools: polished Golemite stone basins holding luminous milky-blue spring water, turning to sickly iridescent green slime where corrupted.

TILES, in this order: 1. polished pale stone floor with carved swirling channels, three variations [polished_stone], 2. a basin of glowing milky-blue spring water [luminous_pool], 3. a thick sheet of iridescent green corrupted slime, acid-pitted stone beneath [corrupted_slime], 4. a raised carved basin rim, one step up [basin_rim], 5. a fractured crystalline mineral spire, impassable [mineral_spire], 6. a carved stone channel wall, top-down [channel_wall], 7. a dissolved hole in the floor, edges acid-pitted [chasm].

LAYOUT: a single PNG containing a strict 1 x 7 row of equal square tiles (7 tiles, left to right, in the order listed), hairline gaps of solid magenta (#FF00FF) between tiles and a solid magenta background wherever a tile is transparent (the drop / chasm tiles are fully opaque). Each tile must be seamless with its own copies on all four sides (the floor tiles especially). Top-down 3/4 view matching the sprite sheets: the ground is seen from above at about 60 degrees, raised features show a lit top face and a short shaded front face.

STYLE: 16-bit pixel art tileset, crisp pixels, no anti-aliasing, no blur, no text. Muted desaturated palette; the region's accent colour appears only where the description says so. Every tile must read at 40 px on a dark #0a0a0a field and must stay legible under a 75%-size character sprite standing on it -- keep floor tiles low-contrast and features high-contrast.
```
