# LLM Topology — Hermes vs. Direct

Tektos-Ultima supports two LLM deployment layouts on Colossus. Choose one in
`.env`; the code defaults still point at the direct layout so `.env.example`
is the source of truth for which is active in a given checkout.

## Ports at a glance

| Port | Service                     | Managed by       | Notes                                                       |
| ---- | --------------------------- | ---------------- | ----------------------------------------------------------- |
| 8090 | llama-server (Qwen3.8-27B)  | systemd `--user` | Primary coder on RTX 5090                                   |
| 8091 | llama-server (embedder)     | systemd `--user` | Qwen3-Embedding-0.6B, CPU                                   |
| 8092 | llama-server (Granite 4.1)  | systemd `--user` | Fallback coder, CPU. **Known wedge under streaming teardown — see below.** |
| 8093 | Hermes proxy                | systemd `--user` | Owns 8090→8092 failover; single stable endpoint for clients |
| 8094 | llama-server (Qwen3-VL-4B)  | systemd `--user` | Vision, CPU                                                 |

## Topology A — Hermes proxy (recommended default)

```
Tektos backend :8020 ──► Hermes :8093 ──┬─► Qwen  :8090  (primary, GPU)
                                          └─► Granite :8092  (fallback, CPU)
```

`.env`:

```
TEKTOS_LLM_BASE_URL=http://127.0.0.1:8093/v1
TEKTOS_LLM_MODEL=qwen3.8-27b-code
TEKTOS_LLM_FAILOVER_ENABLED=false
TEKTOS_PROMPT_TIMEOUT_SECONDS=120
```

Why this is the default:

- Tektos only ever talks to ONE endpoint, so its own failover logic stays off.
  Only Hermes has to reason about primary vs. fallback state, which eliminates
  a whole class of double-failover races.
- Hermes uses `http.client` (sync, single-shot connections) with no keepalive.
  It has been running for 3+ days without wedging, whereas the Granite 4.1 8B
  llama-server wedges under streaming teardown — abandoned SSE requests leave
  inference threads spinning and CLOSE-WAIT sockets that never drain, and
  granite serializes requests, so once one is stuck the rest queue behind it
  forever. Isolating that pathology inside Hermes (its usual home) means it
  cannot take Tektos down with it.
- Reproduces outside Tektos too — plain `httpx.AsyncClient.stream()` in a
  40-line script hits the same wedge. So the bug is in the granite
  llama-server config on Colossus, not in Tektos or its HTTP client.

## Topology B — Direct llama-server (bring-up / debugging)

```
Tektos backend :8020 ──┬─► Qwen  :8090  (primary, GPU)
                        └─► Granite :8092  (fallback, CPU)
                        (Tektos owns the failover routing)
```

`.env`:

```
TEKTOS_LLM_BASE_URL=http://127.0.0.1:8090/v1
TEKTOS_LLM_MODEL=qwen3.8-27b-code
TEKTOS_LLM_FALLBACK_URL=http://127.0.0.1:8092/v1
TEKTOS_LLM_FALLBACK_MODEL=granite4.1-8b-instruct
TEKTOS_LLM_FAILOVER_ENABLED=true
TEKTOS_LLM_FAILOVER_COOLDOWN_SECONDS=30
TEKTOS_PROMPT_TIMEOUT_SECONDS=120
```

Only use this layout when:

- Hermes is down or being debugged.
- You are stress-testing the Tektos-side failover code (`llm_client.py`) and
  want the primary/fallback boundary visible to the backend.

The immune system will BLOCK `TEKTOS_LLM_BASE_URL=http://127.0.0.1:8090` if it
sees the assignment in a `bash` tool call — you have to set it in `.env` or
export it in your shell before starting uvicorn.

## Prompt timeout

`TEKTOS_PROMPT_TIMEOUT_SECONDS` (default 120) applies to both topologies. When
a single prompt exceeds this wall-clock budget, `_stream_llm` aborts, marks
the session `failed`, and fires the `session.fail` hook with
`outcome="timeout"`. This was introduced in PR #9 to prevent one stalled
upstream from wedging the whole SDK. Increase it (e.g. to 300s) when you know
you're driving a long-generating task.

## Known issue — Granite 4.1 8B wedge

**Symptom:** After 1–2 streaming requests that are cancelled mid-stream, the
Granite llama-server on 8092 stops responding to any new requests for
minutes. Direct `curl -sN` to `127.0.0.1:8092/v1/chat/completions` returns 0
bytes after the full timeout. `ss -tnp` shows CLOSE-WAIT sockets held by the
llama-server process and CPU usage 6–8× wall clock even at idle.

**Reproduction:** Independent of Tektos. A 40-line asyncio script using
`httpx.AsyncClient.stream()` triggers it on the first iteration once granite
has been used once and torn down.

**Workaround:** Topology A. Hermes uses sync single-shot HTTP connections,
which do not exercise the wedge pattern (though granite still wedges if you
cancel an in-flight Hermes stream, so it will remain a fallback-only concern
until we replace the CPU fallback model).

**Follow-up work:** Benchmark alternative CPU fallbacks and swap one into
Hermes's `UPSTREAMS` tuple. Candidates:

- Qwen2.5-7B-Instruct Q4
- Phi-3.5-mini
- Llama-3.2-3B

Zero Tektos code changes needed — just update
`/home/rmholston/.local/lib/hermes-qwen-ha/proxy.py` `UPSTREAMS` and the model
alias, then `systemctl --user restart hermes-qwen-ha.service`.

## Verification snippets

Health-check the whole stack in one shot (Topology A):

```bash
curl -s http://127.0.0.1:8093/v1/models | head -c 200; echo
curl -sN -X POST http://127.0.0.1:8093/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Say hi."}],"stream":true,"max_tokens":10}' | head -c 400
```

Two sequential prompts through Tektos:

```bash
for i in 1 2; do
  sid=$(curl -s -X POST http://127.0.0.1:8020/api/sessions \
    -H 'Content-Type: application/json' -d '{"cwd":"/tmp"}' \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
  echo "--- prompt $i (session ${sid:0:8}) ---"
  timeout 180 curl -sN -X POST http://127.0.0.1:8020/api/prompt/sse \
    -H 'Content-Type: application/json' \
    -d "{\"session_id\":\"$sid\",\"prompt\":\"Say hi in five words.\"}" \
    | wc -c
done
```

Expect two responses in the tens of KB. See the 2026-09-09 bring-up trace
for the reference numbers (28 KB / 63 s, 53 KB / 65 s).
