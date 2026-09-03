# Sprite sheets: King Slime (boss)

Slug: `kingslime`  
Side: enemy

One image per clip. Deliver each as the file name shown; the intake tool slices it by the stated grid and normalises frames to 64x64.

## idle -- deliver as `kingslime__idle.png` (3 rows x 4 cols)

```text
SUBJECT: The King Slime: a colossal mass of pulsating deep-green slime, its body studded with crystalline shards and corroded stone fragments consumed over centuries. It rears upward for its attack like a wave about to break, churns and glows when it casts, and collapses outward in a spreading pool when it dies. It should fill its cell edge to edge -- larger than any other combatant. Accent colour: deep green with crystal shards.

ANIMATION: 'idle' -- breathing / weight-shift loop used whenever the combatant is waiting. Exactly 4 frames per row, a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end sequence otherwise. The pose must be recognisably the same character in all 12 cells.

LAYOUT: a single PNG containing a strict 3 x 4 grid of equal square cells (3 rows, 4 columns), every cell the same size, with hairline gaps of solid magenta (#FF00FF) between cells and a solid magenta background behind every cell. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## walk -- deliver as `kingslime__walk.png` (3 rows x 6 cols)

```text
SUBJECT: The King Slime: a colossal mass of pulsating deep-green slime, its body studded with crystalline shards and corroded stone fragments consumed over centuries. It rears upward for its attack like a wave about to break, churns and glows when it casts, and collapses outward in a spreading pool when it dies. It should fill its cell edge to edge -- larger than any other combatant. Accent colour: deep green with crystal shards.

ANIMATION: 'walk' -- movement loop used while advancing, withdrawing or flanking. Exactly 6 frames per row, a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end sequence otherwise. The pose must be recognisably the same character in all 18 cells.

LAYOUT: a single PNG containing a strict 3 x 6 grid of equal square cells (3 rows, 6 columns), every cell the same size, with hairline gaps of solid magenta (#FF00FF) between cells and a solid magenta background behind every cell. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## attack -- deliver as `kingslime__attack.png` (3 rows x 6 cols)

```text
SUBJECT: The King Slime: a colossal mass of pulsating deep-green slime, its body studded with crystalline shards and corroded stone fragments consumed over centuries. It rears upward for its attack like a wave about to break, churns and glows when it casts, and collapses outward in a spreading pool when it dies. It should fill its cell edge to edge -- larger than any other combatant. Accent colour: deep green with crystal shards.

ANIMATION: 'attack' -- one committed strike: wind-up (first third of the frames), swing/impact (middle third), recoil (last third). Exactly 6 frames per row, a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end sequence otherwise. The pose must be recognisably the same character in all 18 cells.

LAYOUT: a single PNG containing a strict 3 x 6 grid of equal square cells (3 rows, 6 columns), every cell the same size, with hairline gaps of solid magenta (#FF00FF) between cells and a solid magenta background behind every cell. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## cast -- deliver as `kingslime__cast.png` (3 rows x 6 cols)

```text
SUBJECT: The King Slime: a colossal mass of pulsating deep-green slime, its body studded with crystalline shards and corroded stone fragments consumed over centuries. It rears upward for its attack like a wave about to break, churns and glows when it casts, and collapses outward in a spreading pool when it dies. It should fill its cell edge to edge -- larger than any other combatant. Accent colour: deep green with crystal shards.

ANIMATION: 'cast' -- a focused non-weapon action: raising a hand, gathering energy, bracing a shout; used for buffs, specials and supernatural moves. Exactly 6 frames per row, a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end sequence otherwise. The pose must be recognisably the same character in all 18 cells.

LAYOUT: a single PNG containing a strict 3 x 6 grid of equal square cells (3 rows, 6 columns), every cell the same size, with hairline gaps of solid magenta (#FF00FF) between cells and a solid magenta background behind every cell. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## defend -- deliver as `kingslime__defend.png` (3 rows x 4 cols)

```text
SUBJECT: The King Slime: a colossal mass of pulsating deep-green slime, its body studded with crystalline shards and corroded stone fragments consumed over centuries. It rears upward for its attack like a wave about to break, churns and glows when it casts, and collapses outward in a spreading pool when it dies. It should fill its cell edge to edge -- larger than any other combatant. Accent colour: deep green with crystal shards.

ANIMATION: 'defend' -- guard raised: parry / dodge stance held, then relaxed. Exactly 4 frames per row, a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end sequence otherwise. The pose must be recognisably the same character in all 12 cells.

LAYOUT: a single PNG containing a strict 3 x 4 grid of equal square cells (3 rows, 4 columns), every cell the same size, with hairline gaps of solid magenta (#FF00FF) between cells and a solid magenta background behind every cell. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## hurt -- deliver as `kingslime__hurt.png` (3 rows x 3 cols)

```text
SUBJECT: The King Slime: a colossal mass of pulsating deep-green slime, its body studded with crystalline shards and corroded stone fragments consumed over centuries. It rears upward for its attack like a wave about to break, churns and glows when it casts, and collapses outward in a spreading pool when it dies. It should fill its cell edge to edge -- larger than any other combatant. Accent colour: deep green with crystal shards.

ANIMATION: 'hurt' -- flinch from a hit: recoil, hold, recover. Exactly 3 frames per row, a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end sequence otherwise. The pose must be recognisably the same character in all 9 cells.

LAYOUT: a single PNG containing a strict 3 x 3 grid of equal square cells (3 rows, 3 columns), every cell the same size, with hairline gaps of solid magenta (#FF00FF) between cells and a solid magenta background behind every cell. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```

## death -- deliver as `kingslime__death.png` (3 rows x 6 cols)

```text
SUBJECT: The King Slime: a colossal mass of pulsating deep-green slime, its body studded with crystalline shards and corroded stone fragments consumed over centuries. It rears upward for its attack like a wave about to break, churns and glows when it casts, and collapses outward in a spreading pool when it dies. It should fill its cell edge to edge -- larger than any other combatant. Accent colour: deep green with crystal shards.

ANIMATION: 'death' -- collapse to the ground; final frame is the resting corpse (it is held on screen). Exactly 6 frames per row, a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end sequence otherwise. The pose must be recognisably the same character in all 18 cells.

LAYOUT: a single PNG containing a strict 3 x 6 grid of equal square cells (3 rows, 6 columns), every cell the same size, with hairline gaps of solid magenta (#FF00FF) between cells and a solid magenta background behind every cell. One sprite per cell, centred, feet on the same baseline in every cell, identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the animation frames in order, left to right. Do not draw anything outside the cells.

STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view (camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly desaturated palette with one strong accent colour per character. Dark-fantasy tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. No text, no labels, no watermark, no drop shadow (the game draws its own).
```
