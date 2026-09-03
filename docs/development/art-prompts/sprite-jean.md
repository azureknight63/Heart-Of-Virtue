# Sprite sheets: Jean Claire

Slug: `jean`  
Side: hero

One image per clip: run each prompt below on its own, in a fresh conversation, and keep only an image that shows that single clip (a composite of several clips, or a second grid, is a redo). Deliver each as the file name shown -- PNG preferred, JPEG/WebP accepted -- and the intake tool locates the cells, keys the magenta by hue, and normalises frames to 64x64.

## idle -- deliver as `jean__idle.png` (3 rows x 4 cols)

```text
SUBJECT: Jean Claire, a lean man of 32, slightly taller than average, short dark-brown shaggy hair, several days' stubble, heavy brow, blue-grey eyes. Wears a layered brown leather and oilcloth travelling coat with a raised collar, a grey-green wrapped neck scarf, crossed leather chest straps with brass buckles, dark trousers, worn boots. Carries a plain one-handed sword; a rosary hangs at his belt. Practical, not knightly -- a traveller who has learned to fight. Accent colour: grey-green scarf teal.

ANIMATION: 'idle' -- breathing / weight-shift loop used whenever the combatant is waiting. Exactly 4 frames per row, a seamless loop (the last frame leads back into the first). The pose must be recognisably the same character in all 12 cells.

FRAMES (left to right, the same 4 in every row): 1 = rest pose, 2 = slight rise, 3 = top of the breath, 4 = settling back.

LAYOUT: exactly one image, containing ONLY this clip: a strict 3 x 4 grid of equal square cells (3 rows, 4 columns, 12 cells in total) on a flat, uniform magenta (#FF00FF) background. Nothing else in the image: no extra cells, no second grid, no other animation, no title strip. No gridlines, borders, boxes or frames around the cells -- cells are separated only by clear magenta margins. The magenta is one flat colour everywhere: no gradient, vignette, texture or shading. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## walk -- deliver as `jean__walk.png` (3 rows x 6 cols)

```text
SUBJECT: Jean Claire, a lean man of 32, slightly taller than average, short dark-brown shaggy hair, several days' stubble, heavy brow, blue-grey eyes. Wears a layered brown leather and oilcloth travelling coat with a raised collar, a grey-green wrapped neck scarf, crossed leather chest straps with brass buckles, dark trousers, worn boots. Carries a plain one-handed sword; a rosary hangs at his belt. Practical, not knightly -- a traveller who has learned to fight. Accent colour: grey-green scarf teal.

ANIMATION: 'walk' -- movement loop used while advancing, withdrawing or flanking. Exactly 6 frames per row, a seamless loop (the last frame leads back into the first). The pose must be recognisably the same character in all 18 cells.

FRAMES (left to right, the same 6 in every row): 1 = contact, 2 = push-off, 3 = mid-stride, 4 = opposite contact, 5 = push-off, 6 = mid-stride.

LAYOUT: exactly one image, containing ONLY this clip: a strict 3 x 6 grid of equal square cells (3 rows, 6 columns, 18 cells in total) on a flat, uniform magenta (#FF00FF) background. Nothing else in the image: no extra cells, no second grid, no other animation, no title strip. No gridlines, borders, boxes or frames around the cells -- cells are separated only by clear magenta margins. The magenta is one flat colour everywhere: no gradient, vignette, texture or shading. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## attack -- deliver as `jean__attack.png` (3 rows x 6 cols)

```text
SUBJECT: Jean Claire, a lean man of 32, slightly taller than average, short dark-brown shaggy hair, several days' stubble, heavy brow, blue-grey eyes. Wears a layered brown leather and oilcloth travelling coat with a raised collar, a grey-green wrapped neck scarf, crossed leather chest straps with brass buckles, dark trousers, worn boots. Carries a plain one-handed sword; a rosary hangs at his belt. Practical, not knightly -- a traveller who has learned to fight. Accent colour: grey-green scarf teal.

ANIMATION: 'attack' -- one committed strike: wind-up (first third of the frames), swing/impact (middle third), recoil (last third). Exactly 6 frames per row, a clean start-to-end sequence. The pose must be recognisably the same character in all 18 cells.

FRAMES (left to right, the same 6 in every row): 1 = wind-up begins, 2 = fully wound, 3 = swing, 4 = impact, 5 = follow-through, 6 = recoil back to rest.

LAYOUT: exactly one image, containing ONLY this clip: a strict 3 x 6 grid of equal square cells (3 rows, 6 columns, 18 cells in total) on a flat, uniform magenta (#FF00FF) background. Nothing else in the image: no extra cells, no second grid, no other animation, no title strip. No gridlines, borders, boxes or frames around the cells -- cells are separated only by clear magenta margins. The magenta is one flat colour everywhere: no gradient, vignette, texture or shading. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## cast -- deliver as `jean__cast.png` (3 rows x 6 cols)

```text
SUBJECT: Jean Claire, a lean man of 32, slightly taller than average, short dark-brown shaggy hair, several days' stubble, heavy brow, blue-grey eyes. Wears a layered brown leather and oilcloth travelling coat with a raised collar, a grey-green wrapped neck scarf, crossed leather chest straps with brass buckles, dark trousers, worn boots. Carries a plain one-handed sword; a rosary hangs at his belt. Practical, not knightly -- a traveller who has learned to fight. Accent colour: grey-green scarf teal.

ANIMATION: 'cast' -- a focused non-weapon action: raising a hand, gathering energy, bracing a shout; used for buffs, specials and supernatural moves. Exactly 6 frames per row, a clean start-to-end sequence. The pose must be recognisably the same character in all 18 cells.

FRAMES (left to right, the same 6 in every row): 1 = focus, 2 = raise, 3 = gather energy, 4 = peak, energy released, 5 = release fades, 6 = lower back to rest.

LAYOUT: exactly one image, containing ONLY this clip: a strict 3 x 6 grid of equal square cells (3 rows, 6 columns, 18 cells in total) on a flat, uniform magenta (#FF00FF) background. Nothing else in the image: no extra cells, no second grid, no other animation, no title strip. No gridlines, borders, boxes or frames around the cells -- cells are separated only by clear magenta margins. The magenta is one flat colour everywhere: no gradient, vignette, texture or shading. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## defend -- deliver as `jean__defend.png` (3 rows x 4 cols)

```text
SUBJECT: Jean Claire, a lean man of 32, slightly taller than average, short dark-brown shaggy hair, several days' stubble, heavy brow, blue-grey eyes. Wears a layered brown leather and oilcloth travelling coat with a raised collar, a grey-green wrapped neck scarf, crossed leather chest straps with brass buckles, dark trousers, worn boots. Carries a plain one-handed sword; a rosary hangs at his belt. Practical, not knightly -- a traveller who has learned to fight. Accent colour: grey-green scarf teal.

ANIMATION: 'defend' -- guard raised: parry / dodge stance held, then relaxed. Exactly 4 frames per row, a clean start-to-end sequence. The pose must be recognisably the same character in all 12 cells.

FRAMES (left to right, the same 4 in every row): 1 = guard comes up, 2 = guard held, 3 = guard braced, 4 = guard relaxes.

LAYOUT: exactly one image, containing ONLY this clip: a strict 3 x 4 grid of equal square cells (3 rows, 4 columns, 12 cells in total) on a flat, uniform magenta (#FF00FF) background. Nothing else in the image: no extra cells, no second grid, no other animation, no title strip. No gridlines, borders, boxes or frames around the cells -- cells are separated only by clear magenta margins. The magenta is one flat colour everywhere: no gradient, vignette, texture or shading. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## hurt -- deliver as `jean__hurt.png` (3 rows x 3 cols)

```text
SUBJECT: Jean Claire, a lean man of 32, slightly taller than average, short dark-brown shaggy hair, several days' stubble, heavy brow, blue-grey eyes. Wears a layered brown leather and oilcloth travelling coat with a raised collar, a grey-green wrapped neck scarf, crossed leather chest straps with brass buckles, dark trousers, worn boots. Carries a plain one-handed sword; a rosary hangs at his belt. Practical, not knightly -- a traveller who has learned to fight. Accent colour: grey-green scarf teal.

ANIMATION: 'hurt' -- flinch from a hit: recoil, hold, recover. Exactly 3 frames per row, a clean start-to-end sequence. The pose must be recognisably the same character in all 9 cells.

FRAMES (left to right, the same 3 in every row): 1 = recoil from the hit, 2 = hold, off balance, 3 = recover.

LAYOUT: exactly one image, containing ONLY this clip: a strict 3 x 3 grid of equal square cells (3 rows, 3 columns, 9 cells in total) on a flat, uniform magenta (#FF00FF) background. Nothing else in the image: no extra cells, no second grid, no other animation, no title strip. No gridlines, borders, boxes or frames around the cells -- cells are separated only by clear magenta margins. The magenta is one flat colour everywhere: no gradient, vignette, texture or shading. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## death -- deliver as `jean__death.png` (3 rows x 6 cols)

```text
SUBJECT: Jean Claire, a lean man of 32, slightly taller than average, short dark-brown shaggy hair, several days' stubble, heavy brow, blue-grey eyes. Wears a layered brown leather and oilcloth travelling coat with a raised collar, a grey-green wrapped neck scarf, crossed leather chest straps with brass buckles, dark trousers, worn boots. Carries a plain one-handed sword; a rosary hangs at his belt. Practical, not knightly -- a traveller who has learned to fight. Accent colour: grey-green scarf teal.

ANIMATION: 'death' -- collapse to the ground; final frame is the resting corpse (it is held on screen). Exactly 6 frames per row, a clean start-to-end sequence. The pose must be recognisably the same character in all 18 cells.

FRAMES (left to right, the same 6 in every row): 1 = struck, 2 = staggers, 3 = falls, 4 = hits the ground, 5 = settles, 6 = resting corpse (held).

LAYOUT: exactly one image, containing ONLY this clip: a strict 3 x 6 grid of equal square cells (3 rows, 6 columns, 18 cells in total) on a flat, uniform magenta (#FF00FF) background. Nothing else in the image: no extra cells, no second grid, no other animation, no title strip. No gridlines, borders, boxes or frames around the cells -- cells are separated only by clear magenta margins. The magenta is one flat colour everywhere: no gradient, vignette, texture or shading. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```
