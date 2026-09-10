#!/usr/bin/env bash
# Install Tektos-Ultima systemd user units by symlinking them into
# ~/.config/systemd/user/ so `git pull` picks up unit changes without
# a re-copy. Run once (idempotent; safe to re-run).
#
# Usage:
#   deploy/systemd/user/install.sh
#
# What it does:
#   1. Verifies `loginctl Linger=yes` for the invoking user
#      (required for user services to run without a login session).
#   2. Symlinks the five units into ~/.config/systemd/user/.
#   3. Reloads the systemd user manager.
#   4. Enables tektos.target so it auto-starts on next login/boot.
#   5. Prints the manual-start command and useful journalctl invocations.
#
# It does NOT start the services — do that yourself with:
#   systemctl --user start tektos.target

set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST_DIR="${HOME}/.config/systemd/user"
UNITS=(
    tektos-backend.service
    tektos-gateway.service
    tektos-hindsight.service
    tektos-frontend.service
    tektos.target
)

echo "==> Checking prerequisites"
if ! command -v systemctl >/dev/null 2>&1; then
    echo "ERROR: systemctl not found — this script requires systemd" >&2
    exit 1
fi

linger="$(loginctl show-user "$USER" 2>/dev/null | awk -F= '/^Linger=/ {print $2}' || echo no)"
if [[ "$linger" != "yes" ]]; then
    echo "WARNING: Linger is not enabled for $USER."
    echo "         Your user services will stop when you log out."
    echo "         Enable with: sudo loginctl enable-linger $USER"
fi

echo "==> Installing units to $DST_DIR"
mkdir -p "$DST_DIR"
for unit in "${UNITS[@]}"; do
    src="$SRC_DIR/$unit"
    dst="$DST_DIR/$unit"
    if [[ ! -f "$src" ]]; then
        echo "ERROR: source unit missing: $src" >&2
        exit 1
    fi
    ln -sfn "$src" "$dst"
    echo "  linked: $unit"
done

echo "==> Reloading systemd user manager"
systemctl --user daemon-reload

echo "==> Enabling tektos.target (auto-start on next login/boot)"
systemctl --user enable tektos.target

cat <<EOF

==> Done. Units installed:

$(for u in "${UNITS[@]}"; do echo "    $DST_DIR/$u"; done)

Manual commands:

    # Start the whole stack now
    systemctl --user start tektos.target

    # Check status of every service
    systemctl --user status 'tektos-*.service' tektos.target

    # Follow logs (any single service)
    journalctl --user -u tektos-backend -f
    journalctl --user -u tektos-gateway -f
    journalctl --user -u tektos-hindsight -f
    journalctl --user -u tektos-frontend -f

    # Follow all Tektos logs at once
    journalctl --user -u 'tektos-*' -f

    # Restart just one service (e.g. after a code change to gateway_proxy)
    systemctl --user restart tektos-gateway

    # Stop the whole stack
    systemctl --user stop tektos.target

    # Disable auto-start
    systemctl --user disable tektos.target

Notes:

  * Hindsight is optional. If it fails to start (e.g. missing
    HINDSIGHT_API_LLM_API_KEY in .env), it will retry 3 times, then stop.
    Backend/gateway/frontend will still run. Fix the config and run:
        systemctl --user restart tektos-hindsight

  * Ports (adjust in .env if these conflict):
      backend       127.0.0.1:8020
      gateway       0.0.0.0:8765   (WebSocket, LAN-reachable)
      hindsight     127.0.0.1:9000
      frontend      0.0.0.0:5556   (Next.js prod)

EOF
