# Tektos-Ultima data services

Host-level bring-up scripts for the data services Tektos-Ultima code assumes
exist on `127.0.0.1`. These are **not** managed by the `tektos.target` user
systemd unit — they run under system systemd (root-owned) because they are
one-per-workstation host infrastructure, not per-user application processes.

## What you get

| Service    | Port(s) | Systemd unit           | Config                          |
|------------|--------:|------------------------|---------------------------------|
| PostgreSQL |    5432 | `postgresql.service`   | distro-managed (already up)     |
| Redis      |    6379 | `redis-server.service` | `/etc/redis/redis.conf`         |
| Neo4j      | 7474, 7687 | `neo4j.service`     | `/etc/neo4j/neo4j.conf`         |

All bind `127.0.0.1` only. All start on boot. All survive reboots without
further action.

## Install

Requires sudo. From the repo root:

```bash
bash deploy/data-services/install.sh
```

Or run them individually:

```bash
bash deploy/data-services/install-redis.sh
bash deploy/data-services/install-neo4j.sh
```

Both scripts are idempotent — safe to re-run after upgrades or when adding
a new workstation.

## Neo4j password

The install script sets an initial password of `neo4j_local_dev` for the
`neo4j` user if the database has never been initialized. Override with:

```bash
NEO4J_INITIAL_PASSWORD='your-choice' bash deploy/data-services/install-neo4j.sh
```

If Neo4j has already been initialized (i.e. `data/dbms/auth.ini` exists),
the script leaves the password alone. Reset it manually with:

```bash
sudo systemctl stop neo4j
sudo -u neo4j neo4j-admin dbms set-initial-password 'new-password'
sudo systemctl start neo4j
```

Set the password in application configs via `.env`:

```dotenv
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=neo4j_local_dev
REDIS_URL=redis://127.0.0.1:6379/0
```

## Verify

```bash
# Redis
redis-cli -h 127.0.0.1 ping                   # -> PONG

# Neo4j (HTTP)
curl -sf http://127.0.0.1:7474/ | head -c 80  # -> JSON banner

# Neo4j (Bolt round-trip via cypher-shell, if installed)
cypher-shell -a bolt://127.0.0.1:7687 -u neo4j -p neo4j_local_dev \
    'RETURN 1 AS ok;'

# Both units after reboot
systemctl status redis-server neo4j
```

## Hardening notes

- **Loopback only**: both scripts explicitly override any binding that
  exposes the service beyond `127.0.0.1`. Neo4j upstream default is
  `0.0.0.0`; Redis upstream default is already `127.0.0.1` but the script
  re-enforces it in case someone edited it.
- **Redis protected-mode** stays on. Even if the bind is accidentally
  widened, protected-mode rejects unauthenticated non-loopback connections.
- **Neo4j initial password** is required by NEO4J before it will serve
  queries. The install script sets it before the first startup so there is
  never a window where the default `neo4j`/`neo4j` credential works.
- If you need to expose Neo4j or Redis on another interface (e.g. for a
  second workstation), do it via SSH tunneling or a firewalled overlay,
  not by editing the bind address in `redis.conf` / `neo4j.conf` — that
  would drift from what `install.sh` re-enforces on next run.

## Uninstall

```bash
sudo systemctl stop neo4j redis-server
sudo systemctl disable neo4j redis-server
sudo apt-get remove --purge neo4j redis-server
sudo rm -f /etc/apt/sources.list.d/neo4j.list /etc/apt/keyrings/neotechnology.gpg
sudo apt-get update
# Data at /var/lib/neo4j and /var/lib/redis is preserved unless you also
# purge those directories manually.
```
