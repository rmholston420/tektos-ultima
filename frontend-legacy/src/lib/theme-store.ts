/**
 * Tektos-Ultima v1 — Theme Store
 *
 * Centralized theme management with localStorage persistence.
 * Three themes: abyss (dark), temple (Tibetan), clarity (minimalist).
 *
 * Exemplar pattern: Singleton store with reactive subscriptions.
 */

export type ThemeName = "abyss" | "temple" | "clarity";

export interface ThemeInfo {
  name: ThemeName;
  label: string;
  description: string;
  icon: string;
}

export const THEMES: Record<ThemeName, ThemeInfo> = {
  abyss: {
    name: "abyss",
    label: "Abyss",
    description: "Deep space dark — living darkness with blue accents",
    icon: "🌑",
  },
  temple: {
    name: "temple",
    label: "Temple",
    description: "Tibetan gold — warm spirituality with crimson depth",
    icon: "🏛️",
  },
  clarity: {
    name: "clarity",
    label: "Clarity",
    description: "Perplexity minimalist — clean light interface",
    icon: "☀️",
  },
};

class ThemeStore {
  private currentTheme: ThemeName = "abyss";
  private listeners = new Set<(theme: ThemeName) => void>();
  private initialized = false;

  private ensureInit(): void {
    if (this.initialized || typeof window === "undefined") return;
    this.initialized = true;
    const saved = localStorage.getItem("tektos-theme") as ThemeName | null;
    if (saved && THEMES[saved]) { this.currentTheme = saved; this.apply(saved); }
    else this.apply("abyss");
  }

  private apply(theme: ThemeName): void {
    /* istanbul ignore if — window is always defined in jsdom */ if (typeof window === "undefined") return;
    if (theme === "abyss") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", theme);
  }

  set(theme: ThemeName): void {
    this.ensureInit(); this.currentTheme = theme; this.apply(theme);
    /* istanbul ignore if — window is always defined in jsdom */
    if (typeof window !== "undefined") localStorage.setItem("tektos-theme", theme);
    Array.from(this.listeners).forEach((l) => l(theme));
  }

  get(): ThemeName { this.ensureInit(); return this.currentTheme; }
  onChange(listener: (theme: ThemeName) => void): () => void { this.ensureInit(); this.listeners.add(listener); return () => { this.listeners.delete(listener); }; }
  getAll(): ThemeInfo[] { return Object.values(THEMES); }
}

export const themeStore = new ThemeStore();
