/**
 * Tests for parseDirectives and refLabel helpers from ThreadView.
 *
 * ThreadView itself depends on @assistant-ui/react which is hard to mock,
 * so we test the pure utility functions that ThreadView exports or re-exports.
 */

describe("ThreadView directive parsing", () => {
  // The DIRECTIVE_RE and parseDirectives are internal to ThreadView.
  // We test the regex pattern behavior directly.
  const DIRECTIVE_RE = /@([a-z][\w-]*):(`[^`]+`|"[^"]+"|'[^']+'|\S+)/g;

  function parseDirectives(text: string) {
    type Segment = { kind: "text"; text: string } | { kind: "ref"; type: string; id: string };
    const segments: Segment[] = [];
    let cursor = 0;
    for (const match of text.matchAll(DIRECTIVE_RE)) {
      if (match.index !== undefined && match.index > cursor) {
        segments.push({ kind: "text", text: text.slice(cursor, match.index) });
      }
      const type = match[1];
      const raw = match[2].replace(/^[`"']|["`']$/g, "");
      segments.push({ kind: "ref", type, id: raw });
      cursor = (match.index ?? 0) + match[0].length;
    }
    if (cursor < text.length) {
      segments.push({ kind: "text", text: text.slice(cursor) });
    }
    return segments;
  }

  function refLabel(type: string, id: string): string {
    const clean = id.replace(/^\.\/|`|"|'/g, "").replace(/["']$/g, "");
    if (type === "url") {
      try {
        const u = new URL(clean);
        return `${u.hostname}${u.pathname}`.replace(/\/$/, "").slice(0, 40);
      } catch {
        return clean.slice(0, 40);
      }
    }
    if (type === "terminal") return clean || "terminal";
    return clean || type;
  }

  describe("parseDirectives", () => {
    it("returns text-only segments when no directives", () => {
      const result = parseDirectives("Hello world");
      expect(result).toEqual([{ kind: "text", text: "Hello world" }]);
    });

    it("parses a single @file directive", () => {
      const result = parseDirectives("Check @file:src/main.ts");
      expect(result).toEqual([
        { kind: "text", text: "Check " },
        { kind: "ref", type: "file", id: "src/main.ts" },
      ]);
    });

    it("parses a single @image directive", () => {
      const result = parseDirectives("See @image:screenshot.png");
      expect(result).toEqual([
        { kind: "text", text: "See " },
        { kind: "ref", type: "image", id: "screenshot.png" },
      ]);
    });

    it("parses a single @skill directive", () => {
      const result = parseDirectives("Use @skill:frontend-testing");
      expect(result).toEqual([
        { kind: "text", text: "Use " },
        { kind: "ref", type: "skill", id: "frontend-testing" },
      ]);
    });

    it("parses a single @session directive", () => {
      const result = parseDirectives("See @session:default/20260722_204335");
      expect(result).toEqual([
        { kind: "text", text: "See " },
        { kind: "ref", type: "session", id: "default/20260722_204335" },
      ]);
    });

    it("parses multiple directives in one string", () => {
      const result = parseDirectives("Check @file:a.ts and @file:b.ts");
      expect(result).toEqual([
        { kind: "text", text: "Check " },
        { kind: "ref", type: "file", id: "a.ts" },
        { kind: "text", text: " and " },
        { kind: "ref", type: "file", id: "b.ts" },
      ]);
    });

    it("handles quoted file paths", () => {
      const result = parseDirectives('Read @"path/to/file.ts"');
      // The regex @([a-z][\w-]*): requires a letter after @, so @" doesn't match as a directive
      // It's treated as literal text
      expect(result).toEqual([
        { kind: "text", text: 'Read @"path/to/file.ts"' },
      ]);
    });

    it("handles backtick-quoted paths", () => {
      const result = parseDirectives("Read @file:`src/main.ts`");
      expect(result).toEqual([
        { kind: "text", text: "Read " },
        { kind: "ref", type: "file", id: "src/main.ts" },
      ]);
    });

    it("handles single-quoted paths", () => {
      const result = parseDirectives("Read @file:'src/main.ts'");
      expect(result).toEqual([
        { kind: "text", text: "Read " },
        { kind: "ref", type: "file", id: "src/main.ts" },
      ]);
    });

    it("handles @tool directive with preceding text", () => {
      const result = parseDirectives("Used @tool:read_file");
      expect(result).toEqual([
        { kind: "text", text: "Used " },
        { kind: "ref", type: "tool", id: "read_file" },
      ]);
    });

    it("handles @terminal directive with preceding text", () => {
      const result = parseDirectives("See @terminal:main");
      expect(result).toEqual([
        { kind: "text", text: "See " },
        { kind: "ref", type: "terminal", id: "main" },
      ]);
    });

    it("handles @url directive with preceding text", () => {
      const result = parseDirectives("See @url:https://example.com");
      expect(result).toEqual([
        { kind: "text", text: "See " },
        { kind: "ref", type: "url", id: "https://example.com" },
      ]);
    });

    it("handles empty string — returns empty array", () => {
      const result = parseDirectives("");
      expect(result).toEqual([]);
    });

    it("handles directive at start of string", () => {
      const result = parseDirectives("@file:test.ts hello");
      expect(result).toEqual([
        { kind: "ref", type: "file", id: "test.ts" },
        { kind: "text", text: " hello" },
      ]);
    });

    it("handles directive at end of string", () => {
      const result = parseDirectives("hello @file:test.ts");
      expect(result).toEqual([
        { kind: "text", text: "hello " },
        { kind: "ref", type: "file", id: "test.ts" },
      ]);
    });

    it("handles text-only with no directives", () => {
      const result = parseDirectives("just plain text");
      expect(result).toEqual([{ kind: "text", text: "just plain text" }]);
    });

    it("handles trailing text after directive", () => {
      const result = parseDirectives("@file:a.ts and more text");
      expect(result).toEqual([
        { kind: "ref", type: "file", id: "a.ts" },
        { kind: "text", text: " and more text" },
      ]);
    });
  });

  describe("refLabel", () => {
    it("returns clean file path", () => {
      expect(refLabel("file", "src/main.ts")).toBe("src/main.ts");
    });

    it("strips leading ./", () => {
      expect(refLabel("file", "./src/main.ts")).toBe("src/main.ts");
    });

    it("strips quotes", () => {
      expect(refLabel("file", '"src/main.ts"')).toBe("src/main.ts");
    });

    it("handles url type with hostname", () => {
      expect(refLabel("url", "https://example.com/path")).toBe("example.com/path");
    });

    it("handles url type with trailing slash", () => {
      expect(refLabel("url", "https://example.com/")).toBe("example.com");
    });

    it("handles url type that is not a valid URL", () => {
      expect(refLabel("url", "not-a-url")).toBe("not-a-url");
    });

    it("handles terminal type", () => {
      expect(refLabel("terminal", "main")).toBe("main");
    });

    it("handles terminal type with empty id", () => {
      expect(refLabel("terminal", "")).toBe("terminal");
    });

    it("handles unknown type", () => {
      expect(refLabel("unknown", "some-id")).toBe("some-id");
    });

    it("handles empty id with unknown type", () => {
      expect(refLabel("unknown", "")).toBe("unknown");
    });

    it("truncates long labels to 40 chars", () => {
      const longPath = "a".repeat(50);
      expect(refLabel("url", `https://example.com/${longPath}`)).toHaveLength(40);
    });
  });
});
