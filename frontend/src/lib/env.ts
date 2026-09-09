/**
 * Runtime-safe environment resolution. Uses NEXT_PUBLIC_* so values are
 * bundled at build time and available in the browser.
 *
 * Two distinct endpoints:
 *   - Gateway WebSocket (JSON-RPC 2.0) — served by tektos.gateway_proxy on
 *     port 8765 by default. Handles prompt.submit / session.interrupt /
 *     event streaming.
 *   - Backend HTTP (REST) — served by tektos.main FastAPI on port 8020
 *     by default. Handles /api/sessions, /api/directory_list, /api/logs,
 *     /api/skills/*, /api/dreamtime/*, /api/hooks/*, /api/voice/stt, etc.
 *
 * The `TEKTOS_PORT` / `NEXT_PUBLIC_TEKTOS_PORT` alias remains as a
 * back-compat shim mirroring `TEKTOS_HTTP_PORT`.
 */
export const TEKTOS_HOST =
  process.env.NEXT_PUBLIC_TEKTOS_HOST ?? "localhost";

export const TEKTOS_HTTP_PORT = Number(
  process.env.NEXT_PUBLIC_TEKTOS_HTTP_PORT ??
    process.env.NEXT_PUBLIC_TEKTOS_PORT ??
    "8020",
);

export const TEKTOS_WS_PORT = Number(
  process.env.NEXT_PUBLIC_TEKTOS_WS_PORT ?? "8765",
);

export const TEKTOS_WS_PROTOCOL =
  process.env.NEXT_PUBLIC_TEKTOS_WS_PROTOCOL ?? "ws";

/** Back-compat alias — mirrors TEKTOS_HTTP_PORT. Prefer the split names. */
export const TEKTOS_PORT = TEKTOS_HTTP_PORT;

export const wsUrl = (path = "/") =>
  `${TEKTOS_WS_PROTOCOL}://${TEKTOS_HOST}:${TEKTOS_WS_PORT}${path}`;

export const httpUrl = (path = "/") =>
  `http${TEKTOS_WS_PROTOCOL === "wss" ? "s" : ""}://${TEKTOS_HOST}:${TEKTOS_HTTP_PORT}${path}`;
