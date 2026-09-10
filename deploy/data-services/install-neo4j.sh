#!/usr/bin/env bash
# Install Neo4j Community for Tektos-Ultima on Ubuntu / Kubuntu.
#
# Idempotent — safe to re-run. Uses the official Neo4j Debian repository.
# Configures the service to:
#   - listen only on 127.0.0.1 (Bolt :7687, HTTP :7474)
#   - start on boot via system systemd
#   - use a pinned initial password (default: neo4j_local_dev), settable via
#     the NEO4J_INITIAL_PASSWORD environment variable
#
# Requires sudo. Not run automatically by tektos.target — this is a one-time
# host bring-up. After running, Neo4j is up on port 7474/7687 for tektos code
# and survives reboots.

set -euo pipefail

NEO4J_INITIAL_PASSWORD="${NEO4J_INITIAL_PASSWORD:-neo4j_local_dev}"
NEO4J_CONF="/etc/neo4j/neo4j.conf"
KEY_PATH="/etc/apt/keyrings/neotechnology.gpg"
LIST_PATH="/etc/apt/sources.list.d/neo4j.list"

log() { printf '\033[1;36m[neo4j]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[neo4j]\033[0m %s\n' "$*" >&2; }

if [[ $EUID -eq 0 ]]; then
    SUDO=""
else
    SUDO="sudo"
fi

# ------------------------------------------------------------------------
# 1. APT repository
# ------------------------------------------------------------------------
if [[ ! -f "$KEY_PATH" ]]; then
    log "Adding Neo4j GPG key"
    $SUDO mkdir -p /etc/apt/keyrings
    curl -fsSL https://debian.neo4j.com/neotechnology.gpg.key \
        | $SUDO gpg --dearmor -o "$KEY_PATH"
    $SUDO chmod a+r "$KEY_PATH"
else
    log "GPG key already present"
fi

if [[ ! -f "$LIST_PATH" ]] || ! grep -q 'debian.neo4j.com' "$LIST_PATH"; then
    log "Adding Neo4j APT source"
    echo "deb [signed-by=$KEY_PATH] https://debian.neo4j.com stable latest" \
        | $SUDO tee "$LIST_PATH" > /dev/null
else
    log "APT source already present"
fi

log "Refreshing APT metadata"
$SUDO apt-get update -qq

# ------------------------------------------------------------------------
# 2. Package install
# ------------------------------------------------------------------------
if ! dpkg -s neo4j >/dev/null 2>&1; then
    log "Installing neo4j package"
    $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y neo4j
else
    log "neo4j package already installed ($(dpkg -s neo4j | awk '/^Version:/ {print $2}'))"
fi

# ------------------------------------------------------------------------
# 3. Configure listen address to 127.0.0.1 (loopback only)
# ------------------------------------------------------------------------
log "Locking listen address to 127.0.0.1"
# Neo4j 5.x / 2026.x setting name is server.default_listen_address.
# The default is 0.0.0.0 — we override for local-first, single-user use.
if ! grep -q '^server.default_listen_address=127.0.0.1' "$NEO4J_CONF"; then
    # Comment out any existing binding line, then append ours.
    $SUDO sed -i 's/^server.default_listen_address=/#&/' "$NEO4J_CONF"
    echo 'server.default_listen_address=127.0.0.1' \
        | $SUDO tee -a "$NEO4J_CONF" > /dev/null
fi

# ------------------------------------------------------------------------
# 4. Initial password (must be set BEFORE first start)
# ------------------------------------------------------------------------
# Neo4j stores an auth marker file once initialized. If the marker exists we
# skip — resetting the password on a live DB requires a different procedure
# and isn't idempotent from this script.
AUTH_MARKER="/var/lib/neo4j/data/dbms/auth.ini"
if [[ ! -f "$AUTH_MARKER" ]] && ! $SUDO test -f "$AUTH_MARKER"; then
    log "Setting initial neo4j password"
    $SUDO neo4j-admin dbms set-initial-password "$NEO4J_INITIAL_PASSWORD"
else
    log "Neo4j already initialized — leaving password alone (edit manually if needed)"
fi

# ------------------------------------------------------------------------
# 5. Enable + start
# ------------------------------------------------------------------------
log "Enabling neo4j.service on boot"
$SUDO systemctl enable neo4j >/dev/null 2>&1 || true

log "(Re)starting neo4j.service"
$SUDO systemctl restart neo4j

# ------------------------------------------------------------------------
# 6. Readiness check
# ------------------------------------------------------------------------
log "Waiting for Neo4j to accept HTTP on 127.0.0.1:7474"
for i in {1..30}; do
    if curl -sfo /dev/null --max-time 2 http://127.0.0.1:7474/; then
        log "Ready. Bolt: bolt://127.0.0.1:7687   HTTP: http://127.0.0.1:7474"
        log "User: neo4j   Password: (as set above; default = $NEO4J_INITIAL_PASSWORD)"
        exit 0
    fi
    sleep 1
done
warn "Neo4j did not become ready in 30s — check: journalctl -u neo4j -n 60 --no-pager"
exit 1
