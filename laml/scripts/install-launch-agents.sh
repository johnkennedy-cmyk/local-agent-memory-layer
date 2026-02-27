#!/bin/bash
# Install LaunchAgents so LAML HTTP API and Dashboard start at login.
# Run from repo root: laml/scripts/install-launch-agents.sh
# Or: bash /path/to/local-agent-memory-layer/laml/scripts/install-launch-agents.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPO_HOME="${HOME}"
LAUNCH_AGENTS_DIR="$REPO_HOME/Library/LaunchAgents"
LOG_DIR="$REPO_HOME/Library/Logs/LAML"
SOURCE_DIR="$SCRIPT_DIR/launchd"

echo "LAML LaunchAgents installer"
echo "  Repo root: $REPO_ROOT"
echo "  LaunchAgents: $LAUNCH_AGENTS_DIR"
echo "  Logs: $LOG_DIR"
echo ""

mkdir -p "$LOG_DIR"
mkdir -p "$LAUNCH_AGENTS_DIR"

for plist in com.laml.http-api.plist com.laml.dashboard.plist; do
  src="$SOURCE_DIR/$plist"
  dest="$LAUNCH_AGENTS_DIR/$plist"
  sed -e "s|REPO_ROOT|$REPO_ROOT|g" -e "s|REPO_HOME|$REPO_HOME|g" "$src" > "$dest"
  echo "Installed $plist"
done

# Load (or reload) so they start now and at next login
for plist in com.laml.http-api.plist com.laml.dashboard.plist; do
  launchctl unload "$LAUNCH_AGENTS_DIR/$plist" 2>/dev/null || true
  launchctl load "$LAUNCH_AGENTS_DIR/$plist"
  echo "Loaded $plist"
done

echo ""
echo "Done. LAML HTTP API (port 8082) and Dashboard (port 5173) are starting."
echo "They will also start automatically at every login."
echo "Logs: $LOG_DIR"
echo "To stop: launchctl unload ~/Library/LaunchAgents/com.laml.http-api.plist"
echo "         launchctl unload ~/Library/LaunchAgents/com.laml.dashboard.plist"
