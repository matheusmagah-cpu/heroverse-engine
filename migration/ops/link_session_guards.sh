#!/usr/bin/env bash
# Hookify reads rules from ./.claude of the session's working directory. Sessions that open the three HeroVerse
# repositories start in their parent folder, where the engine's rules and permissions would not load. This links
# them there. Safe to run more than once.
set -euo pipefail
engine="$(cd "$(dirname "$0")/../.." && pwd)"
root="${1:-$(dirname "$engine")}"
[ "$root" = "$engine" ] && { echo "session root is the engine: nothing to link"; exit 0; }
mkdir -p "$root/.claude"
for f in "$engine"/.claude/hookify.*.local.md "$engine"/.claude/settings.json "$engine"/.claude/claude-security-guidance.md; do
  ln -sf "$f" "$root/.claude/"
done
ls "$root/.claude"
