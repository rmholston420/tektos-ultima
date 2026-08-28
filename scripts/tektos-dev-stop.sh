#!/usr/bin/env bash
# tektos-dev-stop.sh — Stop the full Tektos dev stack.
# Usage: ./scripts/tektos-dev-stop.sh

set -euo pipefail

GREEN='\033[0;32m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $*"; }

log "Stopping Tektos dev stack..."

# Kill tmux session
if tmux has-session -t "tektos-dev" 2>/dev/null; then
    log "Killing tmux session 'tektos-dev'..."
    tmux kill-session -t "tektos-dev"
fi

# Kill any remaining processes
if pgrep -f "tektos.main" > /dev/null 2>&1; then
    log "Killing Tektos backend..."
    pkill -f "tektos.main" 2>/dev/null || true
fi

if lsof -ti:5174 > /dev/null 2>&1; then
    log "Killing Vite on port 5174..."
    lsof -ti:5174 | xargs kill -9 2>/dev/null || true
fi

if pgrep -f "electron.*--type=zygote" > /dev/null 2>&1; then
    log "Killing Electron..."
    pkill -f "electron.*--type=zygote" 2>/dev/null || true
    pkill -f "electron.*renderer" 2>/dev/null || true
fi

# Clean up PID files
rm -f /tmp/tektos-backend.pid /tmp/tektos-vite.pid

log "All Tektos dev processes stopped."
