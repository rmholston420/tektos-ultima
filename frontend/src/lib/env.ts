/**
 * Runtime-safe environment resolution. Uses NEXT_PUBLIC_* so values are
 * bundled at build time and available in the browser.
 */
export const TEKTOS_HOST =
  process.env.NEXT_PUBLIC_TEKTOS_HOST ?? "localhost";
export const TEKTOS_PORT = Number(
  process.env.NEXT_PUBLIC_TEKTOS_PORT ?? "8020",
);
export const TEKTOS_WS_PROTOCOL =
  process.env.NEXT_PUBLIC_TEKTOS_WS_PROTOCOL ?? "ws";

export const wsUrl = (path = "/") =>
  `${TEKTOS_WS_PROTOCOL}://${TEKTOS_HOST}:${TEKTOS_PORT}${path}`;

export const httpUrl = (path = "/") =>
  `http${TEKTOS_WS_PROTOCOL === "wss" ? "s" : ""}://${TEKTOS_HOST}:${TEKTOS_PORT}${path}`;
