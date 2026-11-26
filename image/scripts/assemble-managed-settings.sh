#!/bin/bash
# assemble-managed-settings.sh - Assemble Claude Code managed-settings.json from modules
#
# Installs the base security hooks as the managed settings.
# Called during post-create to configure Claude Code hooks dynamically.
# Optional feature modules can be merged in here, gated by environment variables.

set -e

BASE_DIR="/etc/claude-code"
OUTPUT="$BASE_DIR/managed-settings.json"
HOOKS_DIR="$BASE_DIR/hooks"

# Start with base security hooks
cp "$HOOKS_DIR/managed-settings.base.json" "$OUTPUT"

echo "Using base security hooks only"
