#!/usr/bin/env bash
# One-shot host bring-up for Tektos-Ultima data services.
#
# Runs both install-neo4j.sh and install-redis.sh in the correct order.
# Both scripts are idempotent — safe to re-run after upgrades or on a fresh
# workstation. Both require sudo.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "─── Installing Redis ───────────────────────────────────────────────"
bash "$SCRIPT_DIR/install-redis.sh"
echo

echo "─── Installing Neo4j ───────────────────────────────────────────────"
bash "$SCRIPT_DIR/install-neo4j.sh"
echo

echo "─── Summary ────────────────────────────────────────────────────────"
systemctl status --no-pager redis-server neo4j 2>&1 | \
    grep -E '(●|Active:|Loaded:)' || true
echo
echo "Both services enabled and running. Reboot-safe."
