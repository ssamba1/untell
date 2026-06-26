#!/usr/bin/env sh
# One-line installer for the untell Claude Code skill.
#   curl -fsSL https://raw.githubusercontent.com/ssamba1/untell/main/install.sh | sh
set -e

REPO="https://github.com/ssamba1/untell"
DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/untell"
TMP="$(mktemp -d)"

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

if ! command -v git >/dev/null 2>&1; then
  echo "error: git is required." >&2
  exit 1
fi

echo "Fetching untell..."
git clone --depth 1 "$REPO" "$TMP/untell" >/dev/null 2>&1

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
cp -r "$TMP/untell/untell" "$DEST"

echo ""
echo "  Installed the untell skill -> $DEST"
echo ""
echo "  Use it in Claude Code:   /untell <your text or a file path>"
echo "  Real detector ensemble:  see https://github.com/ssamba1/untell#tiers"
echo ""
