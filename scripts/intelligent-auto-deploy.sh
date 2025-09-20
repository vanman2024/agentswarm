#!/bin/bash
# Simplified auto-deploy: copy only runtime assets into template agentswarm directory.

set -euo pipefail

TEMPLATE_REPO_DIR=${1:?"Usage: $0 <template-repo-dir> <source-dir>"}
SOURCE_DIR=${2:?"Usage: $0 <template-repo-dir> <source-dir>"}

TARGET="$TEMPLATE_REPO_DIR/agentswarm"

echo "🚀 Syncing AgentSwarm runtime into template"
echo "   Source: $SOURCE_DIR"
echo "   Target: $TARGET"

rm -rf "$TARGET"
mkdir -p "$TARGET/src" "$TARGET/bin"

if [[ -d "$SOURCE_DIR/src" ]]; then
  rsync -a --delete "$SOURCE_DIR/src/" "$TARGET/src/"
else
  echo "⚠️  Source src/ directory not found"
fi

if [[ -f "$SOURCE_DIR/agentswarm" ]]; then
  cp "$SOURCE_DIR/agentswarm" "$TARGET/bin/agentswarm"
fi

for file in install.sh requirements.txt README.md agentswarm.yaml; do
  if [[ -f "$SOURCE_DIR/$file" ]]; then
    cp "$SOURCE_DIR/$file" "$TARGET/$file"
  fi
done

if [[ -f "$SOURCE_DIR/VERSION" ]]; then
  cp "$SOURCE_DIR/VERSION" "$TARGET/VERSION"
  cp "$SOURCE_DIR/VERSION" "$TEMPLATE_REPO_DIR/agentswarm-VERSION"
fi

echo "✅ Sync complete"
