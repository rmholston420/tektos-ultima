# Tektos-Ultima systemd user units

Idempotent, dependency-ordered systemd **user** units for the four-service
Tektos stack. Bring the whole stack up with a single command, and it
survives reboots (assuming `loginctl enable-linger`).

## Services

| Unit                        | Port  | Depends on                    | Restart policy       |
|-----------------------------|-------|-------------------------------|----------------------|
| `tektos-backend.service`    | 8020  | `network-online.target`       | on-failure, 5s       |
| `tektos-gateway.service`    | 8765  | `tektos-backend` (Requires=)  | on-failure, 3s       |
| `tektos-hindsight.service`  | 9000  | `network-online.target`       | on-failure, 3× / 2m  |
| `tektos-frontend.service`   | 5556  | backend + gateway (Wants=)    | on-failure, 3s       |
| `tektos.target`             | —     | Wants= all four               | —                    |

**Design notes**:

- `tektos.target` uses `Wants=`, not `Requires=`, so a failing hindsight
  does not cascade into backend/gateway/frontend failure.
- Every service is `PartOf=tektos.target`, so `systemctl --user stop tektos.target`
  cleanly stops the whole stack.
- `KillMode=mixed` sends SIGTERM to the main PID and SIGKILL to the rest
  of the cgroup. This prevents the zombie/orphan situation that occurred
  during the PR #43 consolidation, where an old uvicorn survived kill and
  kept serving stale code from a deleted directory.
- Gateway uses `Requires=tektos-backend.service` (hard dep) because it
  proxies to :8020; frontend uses `Wants=` (soft) because it retries API
  calls if backend/gateway momentarily drop.
- Hindsight has `StartLimitBurst=3 / StartLimitIntervalSec=120` — if it
  can't start (usually a missing env var), it will stop retrying after
  three failures so the log stays quiet until an operator fixes the config.

## Install

```bash
cd ~/dev/tektos-ultima-v1
deploy/systemd/user/install.sh
```

The installer:
1. Symlinks the five units into `~/.config/systemd/user/` (so `git pull`
   picks up unit-file changes without a re-copy).
2. `daemon-reload`s the systemd user manager.
3. `enable`s `tektos.target` for auto-start on next login/boot.

It does **not** start the services. Kick off manually:

```bash
systemctl --user start tektos.target
systemctl --user status 'tektos-*.service' tektos.target
```

## Prerequisites

- **Lingering must be enabled** so user services survive logout:
  ```bash
  sudo loginctl enable-linger $USER
  loginctl show-user $USER | grep Linger    # Linger=yes
  ```
- **`.env` at `~/dev/tektos-ultima-v1/.env`** — every unit `EnvironmentFile=`s
  this. Missing keys surface as clean startup errors in the journal.
- **`.venv` at `~/dev/tektos-ultima-v1/.venv`** — units call
  `.venv/bin/python` and `.venv/bin/hindsight-api` directly (no venv
  activation needed).
- **Frontend build present** — `deploy/systemd/user/tektos-frontend.service`
  runs `npm run start` (Next.js production). Run `npm run build` in
  `frontend/` at least once before starting the frontend unit.

## Environment variables the units read (from `.env`)

- `TEKTOS_HOST` (default `127.0.0.1`) — override to `0.0.0.0` to expose backend on LAN.
- `TEKTOS_PORT` (default `8020`).
- `TEKTOS_LOG_LEVEL` (default `info`).
- `TEKTOS_GATEWAY_PORT` (default `8765`).
- `HINDSIGHT_API_LLM_API_KEY` — **required** for hindsight; the daemon
  refuses to start without it.
- Any other `HINDSIGHT_API_*` keys the hindsight config expects.

## Common commands

```bash
# Whole stack
systemctl --user start tektos.target
systemctl --user restart tektos.target
systemctl --user stop tektos.target
systemctl --user status 'tektos-*.service' tektos.target

# One service (e.g. after editing gateway_proxy.py)
systemctl --user restart tektos-gateway

# Logs
journalctl --user -u 'tektos-*' -f      # all services combined
journalctl --user -u tektos-backend -f  # one service
journalctl --user -u tektos-backend -n 200 --no-pager   # last 200 lines
```

## Upgrading

Because the units are symlinks into the repo, a `git pull` that touches
`deploy/systemd/user/*.service` takes effect after:

```bash
systemctl --user daemon-reload
systemctl --user restart tektos.target
```

## Uninstall

```bash
systemctl --user stop tektos.target
systemctl --user disable tektos.target
rm ~/.config/systemd/user/tektos-*.service ~/.config/systemd/user/tektos.target
systemctl --user daemon-reload
```
