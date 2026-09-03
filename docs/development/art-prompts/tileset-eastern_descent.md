# Tileset: Eastern Descent

Region key: `eastern_descent`  
Deliver as `tileset__eastern_descent.png` (1 row x 7 tiles).

Tile order and the variant key each one becomes:

1. `mountain_rock` -- pale grey undressed mountain rock ground, three variations
2. `scree` -- loose grey scree and gravel
3. `thornbrush` -- a low tangle of dry thorn scrub
4. `ledge` -- a raised rock ledge, one step up, lit front edge
5. `boulder` -- a cart-horse-sized pale grey boulder with lichen, impassable
6. `rock_face` -- a sheer rock face block, top-down
7. `cliff_edge` -- the edge of a cliff falling away to haze below

```text
SUBJECT: terrain tileset for Eastern Descent: open-air pale grey mountain rock under a cold blue-white sky; lichen green, dun scrub, wind-scoured.

TILES, in this order: 1. pale grey undressed mountain rock ground, three variations [mountain_rock], 2. loose grey scree and gravel [scree], 3. a low tangle of dry thorn scrub [thornbrush], 4. a raised rock ledge, one step up, lit front edge [ledge], 5. a cart-horse-sized pale grey boulder with lichen, impassable [boulder], 6. a sheer rock face block, top-down [rock_face], 7. the edge of a cliff falling away to haze below [cliff_edge].

LAYOUT: a single PNG containing a strict 1 x 7 row of equal square tiles (7 tiles, left to right, in the order listed), hairline gaps of solid magenta (#FF00FF) between tiles and a solid magenta background wherever a tile is transparent (the "cliff_edge" tile is fully opaque). Each tile must be seamless with its own copies on all four sides (the floor tiles especially). Top-down 3/4 view matching the sprite sheets: the ground is seen from above at about 60 degrees, raised features show a lit top face and a short shaded front face.

STYLE: 16-bit pixel art tileset, crisp pixels, no anti-aliasing, no blur, no text. Muted desaturated palette; the region's accent colour appears only where the description says so. Every tile must read at 40 px on a dark #0a0a0a field and must stay legible under a 75%-size character sprite standing on it -- keep floor tiles low-contrast and features high-contrast.
```
