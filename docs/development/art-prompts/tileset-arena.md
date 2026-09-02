# Tileset: Proving Grounds (testing arena)

Region key: `arena`  
Deliver as `tileset__arena.png` (1 row x 7 tiles).

Tile order and the variant key each one becomes:

1. `arena_floor` -- smooth pale stone floor slab, three subtle variations
2. `rubble` -- loose grey stone rubble scattered on the floor
3. `slime` -- a puddle of translucent green slime
4. `stone_shelf` -- a raised stone shelf top, one step up, with a lit front edge
5. `boulder` -- a single rounded grey boulder
6. `stone_wall` -- a solid dressed-stone wall block, top-down
7. `drop` -- a black drop-off into nothing, edge lit

```text
SUBJECT: terrain tileset for Proving Grounds (testing arena): a clean dreamlike training floor: pale grey stone slabs, soft even light, no debris.

TILES, in this order: 1. smooth pale stone floor slab, three subtle variations [arena_floor], 2. loose grey stone rubble scattered on the floor [rubble], 3. a puddle of translucent green slime [slime], 4. a raised stone shelf top, one step up, with a lit front edge [stone_shelf], 5. a single rounded grey boulder [boulder], 6. a solid dressed-stone wall block, top-down [stone_wall], 7. a black drop-off into nothing, edge lit [drop].

LAYOUT: a single PNG containing a strict 1 x 7 row of equal square tiles (7 tiles, left to right, in the order listed), hairline gaps of solid magenta (#FF00FF) between tiles and a solid magenta background wherever a tile is transparent (the drop / chasm tiles are fully opaque). Each tile must be seamless with its own copies on all four sides (the floor tiles especially). Top-down 3/4 view matching the sprite sheets: the ground is seen from above at about 60 degrees, raised features show a lit top face and a short shaded front face.

STYLE: 16-bit pixel art tileset, crisp pixels, no anti-aliasing, no blur, no text. Muted desaturated palette; the region's accent colour appears only where the description says so. Every tile must read at 40 px on a dark #0a0a0a field and must stay legible under a 75%-size character sprite standing on it -- keep floor tiles low-contrast and features high-contrast.
```
