#!/usr/bin/env bash
# Install Redis for Tektos-Ultima on Ubuntu / Kubuntu.
#
# Idempotent. Uses the distro Ubuntu package (recent Redis 7.x on 24.04+).
# Default upstream config already:
#   - binds 127.0.0.1 only
#   - enables protected-mode (rejects non-loopback anonymous connections)
#   - persists RDB snapshots to /var/lib/redis
#   - starts on boot via system systemd
#
# We verify those defaults haven't been overridden and enforce them if needed.

set -euo pipefail

CONF="/etc/redis/redis.conf"

log() { printf '\033[1;36m[redis]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[redis]\033[0m %s\n' "$*" >&2; }

if [[ $EUID -eq 0 ]]; then
    SUDO=""
else
    SUDO="sudo"
fi

# ------------------------------------------------------------------------
# 1. Package install
# ------------------------------------------------------------------------
if ! dpkg -s redis-server >/dev/null 2>&1; then
    log "Installing redis-server package"
    $SUDO apt-get update -qq
    $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y redis-server
else
    log "redis-server already installed ($(dpkg -s redis-server | awk '/^Version:/ {print $2}'))"
fi

# ------------------------------------------------------------------------
# 2. Enforce local-only binding + protected-mode + supervised systemd
# ------------------------------------------------------------------------
log "Verifying redis.conf hardening (bind 127.0.0.1, protected-mode yes, supervised systemd)"

# supervised: distro package usually sets this to `systemd` already, but
# older config files ship with `no` which produces a "Redis is starting"
# status flap on boot.
if ! grep -qE '^supervised systemd\b' "$CONF"; then
    $SUDO sed -i 's/^supervised .*/supervised systemd/' "$CONF"
    grep -qE '^supervised ' "$CONF" \
        || echo 'supervised systemd' | $SUDO tee -a "$CONF" > /dev/null
fi

# bind: must include 127.0.0.1; must NOT include 0.0.0.0 or public IPs.
if ! grep -qE '^bind .*127\.0\.0\.1' "$CONF"; then
    $SUDO sed -i 's/^bind .*/bind 127.0.0.1 -::1/' "$CONF"
fi
if grep -qE '^bind .*(0\.0\.0\.0|::0)' "$CONF"; then
    warn "redis.conf has a public bind — replacing with loopback only"
    $SUDO sed -i 's/^bind .*/bind 127.0.0.1 -::1/' "$CONF"
fi

# protected-mode: must be yes.
if ! grep -qE '^protected-mode yes' "$CONF"; then
    $SUDO sed -i 's/^protected-mode .*/protected-mode yes/' "$CONF"
    grep -qE '^protected-mode ' "$CONF" \
        || echo 'protected-mode yes' | $SUDO tee -a "$CONF" > /dev/null
fi

# ------------------------------------------------------------------------
# 3. Enable + start
# ------------------------------------------------------------------------
log "Enabling redis-server.service on boot"
$SUDO systemctl enable redis-server >/dev/null 2>&1 || true

log "(Re)starting redis-server.service"
$SUDO systemctl restart redis-server

# ------------------------------------------------------------------------
# 4. Readiness check
# ------------------------------------------------------------------------
log "Pinging redis on 127.0.0.1:6379"
for i in {1..15}; do
    if redis-cli -h 127.0.0.1 -p 6379 ping 2>/dev/null | grep -q '^PONG$'; then
        log "Ready. URL: redis://127.0.0.1:6379/0"
        exit 0
    fi
    sleep 1
done
warn "Redis did not respond to PING in 15s — check: journalctl -u redis-server -n 40 --no-pager"
exit 1
