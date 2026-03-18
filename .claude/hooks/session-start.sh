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
