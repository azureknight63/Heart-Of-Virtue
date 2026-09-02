# Tileset: Wailing Badlands

Region key: `wailing_badlands`  
Deliver as `tileset__wailing_badlands.png` (1 row x 7 tiles).

Tile order and the variant key each one becomes:

1. `dust_flat` -- hard-packed grey dust flat, three variations
2. `rust_rubble` -- rust-red loose rubble
3. `dust_sink` -- a sink of fine choking dust
4. `block_top` -- the flat top of a fallen inscribed stone block, one step up
5. `fallen_block` -- a massive fallen stone block with half-legible inscriptions, impassable
6. `stone_spire` -- the base of a cracked stone spire, top-down
7. `crevasse` -- a hidden crevasse in the flat

```text
SUBJECT: terrain tileset for Wailing Badlands: gray-and-rust wind-scoured badlands under a dust haze; shattered stone spires, rust-stained rock.

TILES, in this order: 1. hard-packed grey dust flat, three variations [dust_flat], 2. rust-red loose rubble [rust_rubble], 3. a sink of fine choking dust [dust_sink], 4. the flat top of a fallen inscribed stone block, one step up [block_top], 5. a massive fallen stone block with half-legible inscriptions, impassable [fallen_block], 6. the base of a cracked stone spire, top-down [stone_spire], 7. a hidden crevasse in the flat [crevasse].

LAYOUT: a single PNG containing a strict 1 x 7 row of equal square tiles (7 tiles, left to right, in the order listed), hairline gaps of solid magenta (#FF00FF) between tiles and a solid magenta background wherever a tile is transparent (the drop / chasm tiles are fully opaque). Each tile must be seamless with its own copies on all four sides (the floor tiles especially). Top-down 3/4 view matching the sprite sheets: the ground is seen from above at about 60 degrees, raised features show a lit top face and a short shaded front face.

STYLE: 16-bit pixel art tileset, crisp pixels, no anti-aliasing, no blur, no text. Muted desaturated palette; the region's accent colour appears only where the description says so. Every tile must read at 40 px on a dark #0a0a0a field and must stay legible under a 75%-size character sprite standing on it -- keep floor tiles low-contrast and features high-contrast.
```
