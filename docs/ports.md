# Tektos-Ultima port registry

Canonical, human-maintained record of every localhost port claimed by
Tektos-Ultima on the Collosus workstation and any other developer machine.

Consult this file **before** choosing a new port. Update it in the same PR
that opens one.

## Loopback bindings (127.0.0.1)

Every port here binds to `127.0.0.1` unless the "Bind" column says otherwise.
No Tektos component should ever bind to `0.0.0.0` on a workstation without a
matching entry that explains why.

### Tektos-Ultima services (systemd user units)

| Port | Bind      | Service                     | Systemd unit                    | Notes |
|-----:|-----------|-----------------------------|---------------------------------|-------|
| 8020 | 127.0.0.1 | FastAPI backend             | `tektos-backend.service`        | uvicorn; no `/`, use `/openapi.json` |
| 8765 | 127.0.0.1 | Gateway WebSocket proxy     | `tektos-gateway.service`        | WS-only; plain HTTP GET returns `426 Upgrade Required` |
| 8095 | 127.0.0.1 | llama-server for Hindsight  | `tektos-llm-hindsight.service`  | Serves Granite 4.0 H Tiny Q4_K_M; OpenAI-compat `/v1` |
| 9000 | 0.0.0.0   | Hindsight API + MCP         | `tektos-hindsight.service`      | Bound to 0.0.0.0 by upstream default; `/health` for status |
| 5556 | 0.0.0.0   | Frontend (Next.js prod)     | `tektos-frontend.service`       | `next start -p 5556` |

### Local model endpoints (Hermes-managed, not tektos units)

These are the ports Tektos routes model traffic to via `ROUTING_DEFAULT_API_BASE`
and the embedder/vision environment variables. They are provisioned by Hermes
Agent, not by tektos systemd units, but tektos code assumes they exist.

| Port | Role                                | Env variable / consumer          |
|-----:|-------------------------------------|----------------------------------|
| 8090 | Hermes default LLM (routing base)   | `ROUTING_DEFAULT_API_BASE`       |
| 8091 | Embedder — Qwen3-Embedding-0.6B     | `TEKTOS_EMBEDDER`                |
| 8092 | Reserved (secondary model slot)     | —                                |
| 8093 | Reserved (secondary model slot)     | —                                |
| 8094 | Vision — Qwen3-VL-4B                | `TEKTOS_VISION`                  |

### Data services (host-managed, tektos consumers)

| Port  | Bind      | Service                         | Managed by              | Consumed by |
|------:|-----------|---------------------------------|-------------------------|-------------|
|  5432 | 127.0.0.1 | PostgreSQL 18 + pgvector 0.8.1  | `postgresql.service`    | Hindsight (`hindsight` db) |
|  7474 | 127.0.0.1 | Neo4j HTTP                      | `neo4j.service`         | Graph memory / GraphRAG |
|  7687 | 127.0.0.1 | Neo4j Bolt                      | `neo4j.service`         | Graph memory / GraphRAG |
|  6379 | 127.0.0.1 | Redis                           | `redis-server.service`  | Cache / task backend |

### Sibling installs on this workstation (not tektos, do not use)

Keep this list current so we never collide when picking a fresh port.

| Port | Owner            | Notes |
|-----:|------------------|-------|
| 9177 | Hermes Hindsight | Separate hindsight install under Hermes venv; unrelated to Tektos hindsight on :9000 |

## Change procedure

1. Pick a port ≥ 5000 that does not appear in this file, `docker ps`,
   `ss -ltnp`, or the sibling-install list.
2. Add a row to the relevant section above **in the same PR** that binds it.
3. If the port is bound by a systemd user unit, mention this file in the
   unit's `README.md` or comment header.
4. If the port is bound by a `deploy/` script (Docker, Compose, or systemd),
   verify the script only binds `127.0.0.1` unless there is a written reason
   to expose it further.
