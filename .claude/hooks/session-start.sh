#!/bin/bash
set -euo pipefail

# Only run in Claude Code cloud/remote sessions
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# ── Python dependencies ───────────────────────────────────────────────────────
pip install -q --break-system-packages --ignore-installed -r "$CLAUDE_PROJECT_DIR/requirements.txt"
pip install -q --break-system-packages --ignore-installed -r "$CLAUDE_PROJECT_DIR/requirements-api.txt"

# ── Frontend dependencies ─────────────────────────────────────────────────────
if [ -f "$CLAUDE_PROJECT_DIR/frontend/package.json" ]; then
  npm install --prefix "$CLAUDE_PROJECT_DIR/frontend" --silent
fi

# ── Install Bun (required by gstack) ─────────────────────────────────────────
if ! command -v bun &> /dev/null; then
  curl -fsSL https://bun.sh/install | bash
  export PATH="$HOME/.bun/bin:$PATH"
  echo "export PATH=\"$HOME/.bun/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
fi

# ── Install gstack globally ───────────────────────────────────────────────────
GSTACK_DIR="$HOME/.claude/skills/gstack"

if [ ! -d "$GSTACK_DIR" ]; then
  git clone --depth=1 https://github.com/garrytan/gstack.git "$GSTACK_DIR"
fi

# Always run setup to ensure binary and skills are up to date
# Playwright CDN may be blocked in some environments; non-fatal since other skills still work
cd "$GSTACK_DIR" && ./setup || echo "Warning: gstack setup finished with errors (Playwright CDN may be unreachable — /qa command may not work)"

# ── Playwright Chromium fallback ──────────────────────────────────────────────
# If the CDN was unreachable, gstack may have a cached older version that can be
# symlinked into the path the current version expects.
EXPECTED_SHELL="$HOME/.cache/ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-linux64/chrome-headless-shell"
if [ ! -e "$EXPECTED_SHELL" ]; then
  CACHED=$(find "$HOME/.cache/ms-playwright" -name "headless_shell" 2>/dev/null | sort | tail -1)
  if [ -n "$CACHED" ]; then
    mkdir -p "$(dirname "$EXPECTED_SHELL")"
    ln -sf "$CACHED" "$EXPECTED_SHELL"
    echo "Playwright: symlinked $(basename $(dirname $(dirname $CACHED))) binary → v1208 path"
  fi
fi
