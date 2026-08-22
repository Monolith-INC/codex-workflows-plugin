#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TARGET="${1:-codex}"
PROFILE="${2:-generic}"

case "$TARGET" in
  codex)
    OUTPUT_PATH="$PROJECT_ROOT/.codex/hooks.json"
    ;;
  gemini)
    OUTPUT_PATH="$PROJECT_ROOT/.gemini/settings.json"
    ;;
  antigravity)
    OUTPUT_PATH="$PROJECT_ROOT/.agents/hooks.json"
    ;;
  claude)
    OUTPUT_PATH="$PROJECT_ROOT/.claude/settings.json"
    ;;
  cursor)
    OUTPUT_PATH="$PROJECT_ROOT/.cursor/hooks.json"
    ;;
  universal|all-agents)
    OUTPUT_PATH=""
    ;;
  *)
    echo "Unsupported target: $TARGET"
    exit 1
    ;;
esac

echo "=== Codex Workflows Installer ==="
echo "Target: $TARGET"
echo "Profile: $PROFILE"
if [ -n "$OUTPUT_PATH" ]; then
  echo "Output: $OUTPUT_PATH"
else
  echo "Output: (shared assets only)"
fi

cd "$PROJECT_ROOT"
if [ -n "$OUTPUT_PATH" ]; then
  python3 -m scripts.installer.cli --target "$TARGET" --profile "$PROFILE" --output "$OUTPUT_PATH"
else
  python3 -m scripts.installer.cli --target "$TARGET" --profile "$PROFILE"
fi

echo "Setup complete!"
