#!/usr/bin/env bash
# tektos-dev-start.sh — Start the full Tektos dev stack with one command.
# Usage: ./scripts/tektos-dev-start.sh
#
# Starts:
#   1. Tektos backend (port 8020)
#   2. Vite dev server (port 5174)
#   3. Electron dev app (reads from Vite)
#
# All processes are managed in a single tmux session for easy control.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEKTOS_ROOT="$(dirname "$SCRIPT_DIR")"
DESKTOP_ROOT="$SCRIPT_DIR/../hermes-tektos/hermes-agent/apps/desktop"
TMUX_SESSION="tektos-dev"

# ── Colors ──────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $*"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] WARN:${NC} $*"; }
err() { echo -e "${RED}[$(date +%H:%M:%S)] ERROR:${NC} $*" >&2; }

# ── Kill existing stack ─────────────────────────────────────────────
kill_existing() {
    log "Checking for existing processes..."

    # Kill Tektos backend
    if pgrep -f "tektos.main" > /dev/null 2>&1; then
        log "Stopping Tektos backend..."
        pkill -f "tektos.main" 2>/dev/null || true
        sleep 1
    fi

    # Kill Vite on port 5174
    if lsof -ti:5174 > /dev/null 2>&1; then
        log "Stopping Vite dev server..."
        lsof -ti:5174 | xargs kill -9 2>/dev/null || true
        sleep 1
    fi

    # Kill Electron
    if pgrep -f "electron.*--type=zygote" > /dev/null 2>&1; then
        log "Stopping Electron..."
        pkill -f "electron.*--type=zygote" 2>/dev/null || true
        pkill -f "electron.*renderer" 2>/dev/null || true
        sleep 1
    fi

    log "Clean slate ready."
}

# ── Start Tektos backend ────────────────────────────────────────────
start_tektos() {
    log "Starting Tektos backend on port 8020..."
    cd "$TEKTOS_ROOT"
    python -m tektos.main &
    TEKTOS_PID=$!
    echo "$TEKTOS_PID" > /tmp/tektos-backend.pid

    # Wait for backend to be ready
    for i in $(seq 1 30); do
        if curl -s http://localhost:8020/api/health > /dev/null 2>&1; then
            log "Tektos backend ready (PID $TEKTOS_PID)."
            return 0
        fi
        sleep 0.5
    done

    warn "Tektos backend may not be ready yet (timeout waiting for /api/health)."
    return 1
}

# ── Start Vite dev server ───────────────────────────────────────────
start_vite() {
    log "Starting Vite dev server on port 5174..."
    cd "$DESKTOP_ROOT"
    npm run dev:renderer &
    VITE_PID=$!
    echo "$VITE_PID" > /tmp/tektos-vite.pid

    # Wait for Vite to be ready
    for i in $(seq 1 30); do
        if curl -s http://localhost:5174/ > /dev/null 2>&1; then
            log "Vite dev server ready (PID $VITE_PID)."
            return 0
        fi
        sleep 0.5
    done

    warn "Vite dev server may not be ready yet (timeout waiting for port 5174)."
    return 1
}

# ── Start Electron ──────────────────────────────────────────────────
start_electron() {
    log "Starting Electron dev app..."
    cd "$DESKTOP_ROOT"
    npm run dev:electron
}

# ── Main ────────────────────────────────────────────────────────────
main() {
    # Check if already running in tmux
    if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
        warn "Tektos dev session '$TMUX_SESSION' already exists."
        echo "  Attach with: tmux attach -t $TMUX_SESSION"
        echo "  Or kill and restart: tmux kill-session -t $TMUX_SESSION"
        exit 0
    fi

    kill_existing

    log "Starting Tektos dev stack..."
    log "  Tektos backend:  http://localhost:8020"
    log "  Vite dev server: http://localhost:5174"
    log "  Tektos dashboard: http://localhost:5174/tektos"
    echo ""

    # Start in tmux for persistent management
    tmux new-session -d -s "$TMUX_SESSION" -n "backend" -x 200 -y 50
    tmux send-keys -t "$TMUX_SESSION:backend" "cd $TEKTOS_ROOT && python -m tektos.main" Enter

    tmux new-window -t "$TMUX_SESSION" -n "vite"
    tmux send-keys -t "$TMUX_SESSION:vite" "cd $DESKTOP_ROOT && npm run dev:renderer" Enter

    tmux new-window -t "$TMUX_SESSION" -n "electron"
    tmux send-keys -t "$TMUX_SESSION:electron" "cd $DESKTOP_ROOT && npm run dev:electron" Enter

    # Set the first window as default
    tmux select-window -t "$TMUX_SESSION:backend"

    log "Stack started in tmux session '$TMUX_SESSION'."
    echo ""
    echo "  Attach:    tmux attach -t $TMUX_SESSION"
    echo "  Kill all:  tmux kill-session -t $TMUX_SESSION"
    echo "  Restart:   $0"
    echo ""
    log "Done."
}

main "$@"
