# Sprite sheets: Mara (nomad ally)

Slug: `mara`  
Side: ally

One image per clip. Deliver each as the file name shown; the intake tool slices it by the stated grid and normalises frames to 64x64.

## idle -- deliver as `mara__idle.png` (3 rows x 4 cols)

```text
SUBJECT: Mara, a lean nomad woman in her late twenties, below average height, dark auburn curly hair cut to the shoulder and tied back loosely, sharp green eyes. Layered olive and brown travel gear, a blue-grey scarf, pack straps across the chest, laced boots; a worn crucifix on a knotted cord at her neck. Fights with a dagger in hand and a short bow slung across her back. Watchful, unhurried. Accent colour: blue-grey scarf.

ANIMATION: 'idle' -- breathing / weight-shift loop used whenever the combatant is waiting. Exactly 4 frames per row, a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end sequence otherwise. The pose must be recognisably the same character in all 12 cells.

LAYOUT: a single PNG containing a strict 3 x 4 grid of equal square cells (3 rows, 4 columns), every cell the same size, with hairline gaps of solid magenta (#FF00FF) between cells and a solid magenta background behind every cell. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## walk -- deliver as `mara__walk.png` (3 rows x 6 cols)

```text
SUBJECT: Mara, a lean nomad woman in her late twenties, below average height, dark auburn curly hair cut to the shoulder and tied back loosely, sharp green eyes. Layered olive and brown travel gear, a blue-grey scarf, pack straps across the chest, laced boots; a worn crucifix on a knotted cord at her neck. Fights with a dagger in hand and a short bow slung across her back. Watchful, unhurried. Accent colour: blue-grey scarf.

ANIMATION: 'walk' -- movement loop used while advancing, withdrawing or flanking. Exactly 6 frames per row, a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end sequence otherwise. The pose must be recognisably the same character in all 18 cells.

LAYOUT: a single PNG containing a strict 3 x 6 grid of equal square cells (3 rows, 6 columns), every cell the same size, with hairline gaps of solid magenta (#FF00FF) between cells and a solid magenta background behind every cell. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## attack -- deliver as `mara__attack.png` (3 rows x 6 cols)

```text
SUBJECT: Mara, a lean nomad woman in her late twenties, below average height, dark auburn curly hair cut to the shoulder and tied back loosely, sharp green eyes. Layered olive and brown travel gear, a blue-grey scarf, pack straps across the chest, laced boots; a worn crucifix on a knotted cord at her neck. Fights with a dagger in hand and a short bow slung across her back. Watchful, unhurried. Accent colour: blue-grey scarf.

ANIMATION: 'attack' -- one committed strike: wind-up (first third of the frames), swing/impact (middle third), recoil (last third). Exactly 6 frames per row, a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end sequence otherwise. The pose must be recognisably the same character in all 18 cells.

LAYOUT: a single PNG containing a strict 3 x 6 grid of equal square cells (3 rows, 6 columns), every cell the same size, with hairline gaps of solid magenta (#FF00FF) between cells and a solid magenta background behind every cell. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## cast -- deliver as `mara__cast.png` (3 rows x 6 cols)

```text
SUBJECT: Mara, a lean nomad woman in her late twenties, below average height, dark auburn curly hair cut to the shoulder and tied back loosely, sharp green eyes. Layered olive and brown travel gear, a blue-grey scarf, pack straps across the chest, laced boots; a worn crucifix on a knotted cord at her neck. Fights with a dagger in hand and a short bow slung across her back. Watchful, unhurried. Accent colour: blue-grey scarf.

ANIMATION: 'cast' -- a focused non-weapon action: raising a hand, gathering energy, bracing a shout; used for buffs, specials and supernatural moves. Exactly 6 frames per row, a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end sequence otherwise. The pose must be recognisably the same character in all 18 cells.

LAYOUT: a single PNG containing a strict 3 x 6 grid of equal square cells (3 rows, 6 columns), every cell the same size, with hairline gaps of solid magenta (#FF00FF) between cells and a solid magenta background behind every cell. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## defend -- deliver as `mara__defend.png` (3 rows x 4 cols)

```text
SUBJECT: Mara, a lean nomad woman in her late twenties, below average height, dark auburn curly hair cut to the shoulder and tied back loosely, sharp green eyes. Layered olive and brown travel gear, a blue-grey scarf, pack straps across the chest, laced boots; a worn crucifix on a knotted cord at her neck. Fights with a dagger in hand and a short bow slung across her back. Watchful, unhurried. Accent colour: blue-grey scarf.

ANIMATION: 'defend' -- guard raised: parry / dodge stance held, then relaxed. Exactly 4 frames per row, a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end sequence otherwise. The pose must be recognisably the same character in all 12 cells.

LAYOUT: a single PNG containing a strict 3 x 4 grid of equal square cells (3 rows, 4 columns), every cell the same size, with hairline gaps of solid magenta (#FF00FF) between cells and a solid magenta background behind every cell. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## hurt -- deliver as `mara__hurt.png` (3 rows x 3 cols)

```text
SUBJECT: Mara, a lean nomad woman in her late twenties, below average height, dark auburn curly hair cut to the shoulder and tied back loosely, sharp green eyes. Layered olive and brown travel gear, a blue-grey scarf, pack straps across the chest, laced boots; a worn crucifix on a knotted cord at her neck. Fights with a dagger in hand and a short bow slung across her back. Watchful, unhurried. Accent colour: blue-grey scarf.

ANIMATION: 'hurt' -- flinch from a hit: recoil, hold, recover. Exactly 3 frames per row, a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end sequence otherwise. The pose must be recognisably the same character in all 9 cells.

LAYOUT: a single PNG containing a strict 3 x 3 grid of equal square cells (3 rows, 3 columns), every cell the same size, with hairline gaps of solid magenta (#FF00FF) between cells and a solid magenta background behind every cell. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## death -- deliver as `mara__death.png` (3 rows x 6 cols)

```text
SUBJECT: Mara, a lean nomad woman in her late twenties, below average height, dark auburn curly hair cut to the shoulder and tied back loosely, sharp green eyes. Layered olive and brown travel gear, a blue-grey scarf, pack straps across the chest, laced boots; a worn crucifix on a knotted cord at her neck. Fights with a dagger in hand and a short bow slung across her back. Watchful, unhurried. Accent colour: blue-grey scarf.

ANIMATION: 'death' -- collapse to the ground; final frame is the resting corpse (it is held on screen). Exactly 6 frames per row, a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end sequence otherwise. The pose must be recognisably the same character in all 18 cells.

LAYOUT: a single PNG containing a strict 3 x 6 grid of equal square cells (3 rows, 6 columns), every cell the same size, with hairline gaps of solid magenta (#FF00FF) between cells and a solid magenta background behind every cell. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```
