# Tileset: Grondia

Region key: `grondia`  
Deliver as `tileset__grondia.png` (1 row x 7 tiles).

Tile order and the variant key each one becomes:

1. `carved_floor` -- smooth carved grey stone floor with faint worn channels, three variations
2. `market_clutter` -- crates, rolled linen and stone counters cluttering the floor
3. `slime` -- a puddle of green slime
4. `dais` -- a raised carved stone dais, one step up
5. `stone_pillar` -- a carved stone pillar, impassable
6. `carved_wall` -- a carved stone wall with faded bas-relief, top-down
7. `drop` -- a railing-less drop to a lower terrace

```text
SUBJECT: terrain tileset for Grondia: a warm amber-lit stone city carved inside a bluff: cool grey stone floors, heat-crystal glow, carved sigils.

TILES, in this order: 1. smooth carved grey stone floor with faint worn channels, three variations [carved_floor], 2. crates, rolled linen and stone counters cluttering the floor [market_clutter], 3. a puddle of green slime [slime], 4. a raised carved stone dais, one step up [dais], 5. a carved stone pillar, impassable [stone_pillar], 6. a carved stone wall with faded bas-relief, top-down [carved_wall], 7. a railing-less drop to a lower terrace [drop].

LAYOUT: a single PNG containing a strict 1 x 7 row of equal square tiles (7 tiles, left to right, in the order listed), hairline gaps of solid magenta (#FF00FF) between tiles and a solid magenta background wherever a tile is transparent (the drop / chasm tiles are fully opaque). Each tile must be seamless with its own copies on all four sides (the floor tiles especially). Top-down 3/4 view matching the sprite sheets: the ground is seen from above at about 60 degrees, raised features show a lit top face and a short shaded front face.

STYLE: 16-bit pixel art tileset, crisp pixels, no anti-aliasing, no blur, no text. Muted desaturated palette; the region's accent colour appears only where the description says so. Every tile must read at 40 px on a dark #0a0a0a field and must stay legible under a 75%-size character sprite standing on it -- keep floor tiles low-contrast and features high-contrast.
```
