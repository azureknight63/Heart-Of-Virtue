# Tileset: Verdette Caverns

Region key: `verdette_caverns`  
Deliver as `tileset__verdette_caverns.png` (1 row x 7 tiles).

Tile order and the variant key each one becomes:

1. `cavern_floor` -- wet grey-violet cave floor with faint pink crystal glow, three variations
2. `shallow_water` -- ankle-deep dark still water mirroring pink crystal light
3. `slime` -- a sheet of sweet-putrid green slime clinging to the floor
4. `rock_shelf` -- a raised natural rock shelf, one step up, lit front edge
5. `crystal_cluster` -- a cluster of jutting rose-pink crystals, impassable
6. `crystal_wall` -- a cave wall shot through with pink crystal veins, top-down
7. `chasm` -- a black crevasse in the cave floor, edge lit faintly pink

```text
SUBJECT: terrain tileset for Verdette Caverns: a damp limestone cave lit by veins of living rose-pink crystal; cool grey-violet wet stone, teal-green lichen, bone-white guano stains.

TILES, in this order: 1. wet grey-violet cave floor with faint pink crystal glow, three variations [cavern_floor], 2. ankle-deep dark still water mirroring pink crystal light [shallow_water], 3. a sheet of sweet-putrid green slime clinging to the floor [slime], 4. a raised natural rock shelf, one step up, lit front edge [rock_shelf], 5. a cluster of jutting rose-pink crystals, impassable [crystal_cluster], 6. a cave wall shot through with pink crystal veins, top-down [crystal_wall], 7. a black crevasse in the cave floor, edge lit faintly pink [chasm].

LAYOUT: a single PNG containing a strict 1 x 7 row of equal square tiles (7 tiles, left to right, in the order listed), hairline gaps of solid magenta (#FF00FF) between tiles and a solid magenta background wherever a tile is transparent (the "chasm" tile is fully opaque). Each tile must be seamless with its own copies on all four sides (the floor tiles especially). Top-down 3/4 view matching the sprite sheets: the ground is seen from above at about 60 degrees, raised features show a lit top face and a short shaded front face.

STYLE: 16-bit pixel art tileset, crisp pixels, no anti-aliasing, no blur, no text. Muted desaturated palette; the region's accent colour appears only where the description says so. Every tile must read at 40 px on a dark #0a0a0a field and must stay legible under a 75%-size character sprite standing on it -- keep floor tiles low-contrast and features high-contrast.
```
