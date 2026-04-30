---
name: mockup
version: 1.0.0
description: |
  UI mockup designer for Heart of Virtue. Generates self-contained HTML mockup files
  that match the project's retro terminal design language, saves them to docs/development/,
  commits, and pushes so the user can view them on the remote branch immediately.
  Use when asked to "show a mockup", "design a card", "mock up a UI component", or
  "show me what X would look like before implementation".
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
---

# /mockup: UI Mockup Designer

You are a UI designer specialising in retro terminal game interfaces. Your job is to
produce self-contained HTML mockup files that look like they belong in Heart of Virtue's
React frontend, save them to `docs/development/`, and push to the remote branch so the
user can view them without checking out code locally.

**The mockup must be on the remote branch** before reporting it as done. A local file
the user cannot see is not a finished deliverable.

---

## Preamble

```bash
git branch --show-current
git status --short
```

If on `master` or `main`, stop immediately:

> This skill must not run on master/main. Please switch to a feature branch first.

Note whether the working tree is dirty — you will need to stash or commit before
pushing later.

---

## Step 1: Parse the Request

Identify from the user's message:

| Field | Description |
|-------|-------------|
| **Component** | What UI element(s) to mock up (card, panel, modal, tray, tooltip…) |
| **States** | Which states to show (collapsed/expanded, hover, empty, loading, error…) |
| **Context** | Where it sits in the layout (LeftPanel, GamePage, overlay, etc.) |
| **Data** | Sample data to populate (move names, beat counts, icons, etc.) |

If the request is ambiguous about states or context, use `AskUserQuestion` to clarify
before generating anything.

---

## Step 2: Read Design Tokens

Read `frontend/src/styles/theme.js` to get current color, spacing, shadow, and font
constants. Do not hard-code values — derive them from the token file.

Key palette (as of writing, confirm from theme.js):

| Token | Value | Use |
|-------|-------|-----|
| `colors.primary` | `#00ff88` | Borders, accents, Maneuver category |
| `colors.secondary` | `#ffaa00` | Warnings, Attack accents |
| `colors.danger` | `#ff4444` | Damage, Attack category |
| `colors.info` / accent | `#00ccff` | Supernatural category |
| `colors.special` | `#9944ff` | Special category |
| `colors.gold` | `#ffcc00` | Miscellaneous / system |
| `colors.bg.main` | `#0a0a0a` | Page background |
| `colors.text.main` | `#e0e0e0` | Body text |
| `colors.text.muted` | `#888888` | Labels, secondary text |
| Font | `'Courier New', monospace` | All text |

Move category → color mapping (from `BattlefieldGrid.jsx`):

| Category | Border / Text color |
|----------|---------------------|
| Attack | `#ff4444` |
| Maneuver | `#00ff88` |
| Special | `#9944ff` |
| Supernatural | `#00ccff` |
| Miscellaneous | `#ffcc00` |

---

## Step 3: Check for Related Components

Before designing, grep for components the new element will sit beside:

```bash
grep -r "ComponentName" frontend/src/components/ --include="*.jsx" -l
```

Read any directly adjacent components (e.g. `HeroPanel.jsx` if mocking something
below it) so padding, border styles, and spacing match exactly.

---

## Step 4: Generate the HTML Mockup

Produce a **single self-contained HTML file** with all CSS inline or in a `<style>`
block. No external dependencies, no CDN links — the file must render correctly
when opened directly from `docs/development/` without a server.

### Required sections

Every mockup must include:

1. **In-context placement** — show the new component inside its parent container
   (e.g. inside a LeftPanel shell) so spacing and scale are obvious.

2. **State variations** — at minimum the states listed in the request, plus any
   edge cases (empty state, max items, long text overflow).

3. **Component close-up** — each distinct state enlarged, with annotations labelling
   key dimensions, colors, and interactive behaviour.

4. **Category/variant matrix** (if applicable) — all color variants side by side.

### Design rules

- Background: `#0a0a0a`
- Font: `'Courier New', monospace` throughout
- Borders: 1–2px solid with category color at 50–60% alpha
- Box shadows: `0 0 6–12px` with category color at 20–30% alpha
- Hover states: slightly brighter border + background tint
- Retro glow class: `box-shadow: 0 0 25px -5px rgba(0,255,136,0.3)` on panels
- Never use rounded corners larger than `8px`
- Text sizes: labels `0.65rem`, secondary `0.75rem`, body `0.875rem`, headings `1rem`

### Annotations

Use orange (`#ffaa00`) annotation text below each section to describe:
- What triggers the state change (hover, click, beat tick)
- What data drives dynamic values (beat count formula, progress bar formula)
- Any behaviour that isn't obvious from the visual

---

## Step 5: Take a Screenshot

After writing the file, render it with Python Playwright and show the result:

```bash
python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
        args=['--no-sandbox','--disable-setuid-sandbox']
    )
    page = browser.new_page(viewport={'width': 960, 'height': 1200})
    page.goto('file:///home/user/Heart-Of-Virtue/docs/development/FILENAME.html')
    page.screenshot(path='/tmp/FILENAME.png', full_page=True)
    browser.close()
"
```

Read the PNG with the `Read` tool so the user can see it.

If Playwright is unavailable, note it clearly and proceed to Step 6 — the pushed
file is still a valid deliverable.

---

## Step 6: Commit and Push

**The user cannot view a local file.** Push is mandatory before reporting done.

```bash
git add docs/development/FILENAME.html
git commit -m "docs: add COMPONENT mockup for issue #NNN

Brief description of what states are shown.

https://claude.ai/code/session_01D2KjqfjqimzVjTbu6ttnHs"
git push -u origin $(git branch --show-current)
```

If the push fails due to network error, retry up to 4 times with exponential
backoff (2s, 4s, 8s, 16s).

If the push fails for any other reason, report the exact error to the user and
stop — do not mark the task complete.

---

## Step 7: Report

Tell the user:

- The screenshot (if captured in Step 5)
- The file path: `docs/development/FILENAME.html`
- The branch and that it is now on remote
- A one-sentence summary of what states / variants are shown
- Explicitly confirm: "Ready for implementation approval."

Do not suggest implementation steps unless the user asks — this skill is
design-only.
