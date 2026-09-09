import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Surface ramp (13 steps, OpenHands-style)
        "surface-0": "var(--surface-0)",
        "surface-1": "var(--surface-1)",
        "surface-2": "var(--surface-2)",
        "surface-3": "var(--surface-3)",
        "surface-4": "var(--surface-4)",
        "surface-5": "var(--surface-5)",
        "surface-6": "var(--surface-6)",
        "surface-7": "var(--surface-7)",
        "surface-8": "var(--surface-8)",
        "surface-9": "var(--surface-9)",
        "surface-10": "var(--surface-10)",
        "surface-11": "var(--surface-11)",
        "surface-12": "var(--surface-12)",
        // Text
        "text-base": "var(--text-base)",
        "text-muted": "var(--text-muted)",
        "text-faint": "var(--text-faint)",
        // Accent
        primary: "var(--primary)",
        "primary-hover": "var(--primary-hover)",
        agent: "var(--agent)",
        "agent-hover": "var(--agent-hover)",
        // Semantic
        error: "var(--error)",
        warning: "var(--warning)",
        success: "var(--success)",
        // Stroke
        stroke: "var(--stroke)",
      },
      fontFamily: {
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        // Hermes density baseline
        "10": ["10px", "14px"],
        "11": ["11px", "16px"],
        "12": ["12px", "16px"],
        "13": ["13px", "18px"],
        "14": ["14px", "20px"],
        "16": ["16px", "24px"],
        "20": ["20px", "28px"],
        "28": ["28px", "36px"],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        DEFAULT: "var(--radius)",
        full: "9999px",
      },
      boxShadow: {
        card: "var(--shadow)",
      },
      transitionDuration: {
        fast: "100ms",
        narrative: "240ms",
      },
      transitionTimingFunction: {
        ease: "cubic-bezier(0.4, 0.0, 0.2, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
