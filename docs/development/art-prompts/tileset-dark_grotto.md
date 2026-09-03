# Tileset: Dark Grotto

Region key: `dark_grotto`  
Deliver as `tileset__dark_grotto.png` (1 row x 7 tiles).

Tile order and the variant key each one becomes:

1. `grotto_floor` -- wet black-grey limestone floor, three variations
2. `rubble` -- pale grit and fallen ceiling rubble
3. `slime` -- a slick of dark green slime
4. `rock_shelf` -- a raised limestone shelf, one step up
5. `fallen_rock` -- a large fallen rock slab, impassable
6. `grotto_wall` -- wet black limestone wall, top-down
7. `chasm` -- a black hole in the floor

```text
SUBJECT: terrain tileset for Dark Grotto: near-black wet limestone; slow drips, pale grit, ghost-white dew-beaded mushrooms, a thin silver shaft of daylight.

TILES, in this order: 1. wet black-grey limestone floor, three variations [grotto_floor], 2. pale grit and fallen ceiling rubble [rubble], 3. a slick of dark green slime [slime], 4. a raised limestone shelf, one step up [rock_shelf], 5. a large fallen rock slab, impassable [fallen_rock], 6. wet black limestone wall, top-down [grotto_wall], 7. a black hole in the floor [chasm].

LAYOUT: a single PNG containing a strict 1 x 7 row of equal square tiles (7 tiles, left to right, in the order listed), hairline gaps of solid magenta (#FF00FF) between tiles and a solid magenta background wherever a tile is transparent (the "chasm" tile is fully opaque). Each tile must be seamless with its own copies on all four sides (the floor tiles especially). Top-down 3/4 view matching the sprite sheets: the ground is seen from above at about 60 degrees, raised features show a lit top face and a short shaded front face.

STYLE: 16-bit pixel art tileset, crisp pixels, no anti-aliasing, no blur, no text. Muted desaturated palette; the region's accent colour appears only where the description says so. Every tile must read at 40 px on a dark #0a0a0a field and must stay legible under a 75%-size character sprite standing on it -- keep floor tiles low-contrast and features high-contrast.
```
