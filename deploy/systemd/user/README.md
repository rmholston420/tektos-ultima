# Tektos-Ultima systemd user units — RETIRED

**Stage 14.2 (ADR-141 exit gate / ADR-144 follow-on, 2026-09-26):** every
unit in this directory is retired. The standalone Tektos-Ultima stack is
shut down — its functionality lives in the Kosmos-LMS kernel
(`/home/rmholston/dev/kosmos-lms`, `:8000`), ported endpoint-for-endpoint
per the ADR-141 functionality-preservation audit (131 P / 23 D / 0 T).

| Retired unit | Port | Final state |
|---|---|---|
| `tektos-backend.service` | 8020 | `systemctl --user disable --now`; symlink removed from `~/.config/systemd/user/` |
| `tektos.target` | — | disabled; last live member was the backend |
| `tektos-hindsight.service` | 9000 | already `not-found`/undeployed; unit deleted |
| `tektos-llm-hindsight.service` | 8095 | already `not-found`/undeployed; unit deleted |
| `install.sh` | — | deleted (nothing left to install) |

Earlier retirements for the record:

- **Stage 9.5 (ADR-113):** `tektos-frontend.service` (:5556) +
  `tektos-gateway.service` (:8765).
- **Stage 14.1 (ADR-144):** the kernel-side ADR-109 gateway proxy
  (`/api/tektos-ultima/gateway/*`) — kernel CSP middleware preserved at
  `kernel/csp.py`.

The live hindsight lane is the **Kosmos** unit
`kosmos-hindsight.service` (:9178) in the kosmos-lms repo — it never
depended on anything in this directory.

Recovery, if ever needed: `git log --oneline -- deploy/systemd/user/`
and `git show <sha>:deploy/systemd/user/tektos-backend.service` (the
donor tree's git history is intact; the GitHub remote retains every
commit).
