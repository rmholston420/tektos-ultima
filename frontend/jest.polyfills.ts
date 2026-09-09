// Minimal polyfills / globals for jsdom tests.
if (typeof (globalThis as { TextEncoder?: unknown }).TextEncoder === "undefined") {
  const { TextEncoder, TextDecoder } = require("util");
  (globalThis as unknown as { TextEncoder: unknown }).TextEncoder = TextEncoder;
  (globalThis as unknown as { TextDecoder: unknown }).TextDecoder = TextDecoder;
}
