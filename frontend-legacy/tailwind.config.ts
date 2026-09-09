// @ts-check
import { resolve } from "path";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          1: "#0a0e17",
          2: "#0d1520",
          3: "#111827",
          4: "#1a2234",
        },
        surface: {
          DEFAULT: "#151d2e",
          hover: "#1c2740",
          active: "#232f4a",
        },
        border: {
          DEFAULT: "#1e2a3f",
          light: "#2a3855",
          focus: "#3b82f6",
        },
        text: {
          primary: "#e2e8f0",
          secondary: "#94a3b8",
          muted: "#64748b",
          accent: "#60a5fa",
        },
        accent: {
          DEFAULT: "#3b82f6",
          hover: "#2563eb",
          active: "#1d4ed8",
          glow: "rgba(59, 130, 246, 0.15)",
        },
        status: {
          success: "#10b981",
          warning: "#f59e0b",
          error: "#ef4444",
          info: "#6366f1",
        },
        tibet: {
          bg: "#1a0f2e",
          gold: "#d4a843",
          crimson: "#8b2252",
          saffron: "#f4c430",
          incense: "#7c3aed",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
        collapse: ["Collapse", "Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 20px rgba(59, 130, 246, 0.15)",
        "glow-lg": "0 0 40px rgba(59, 130, 246, 0.25)",
      },
    },
  },
  plugins: [],
};
