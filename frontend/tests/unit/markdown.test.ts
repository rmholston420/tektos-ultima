import { renderMarkdown } from "@/lib/markdown";

describe("renderMarkdown", () => {
  test("renders headings and paragraphs", () => {
    const html = renderMarkdown("# Title\n\nHello.");
    expect(html).toContain("<h1>Title</h1>");
    expect(html).toContain("<p>Hello.</p>");
  });

  test("highlights code fences", () => {
    const html = renderMarkdown("```ts\nconst x = 1;\n```");
    expect(html).toContain("language-ts");
    expect(html).toContain("hljs");
  });

  test("sanitizes script tags", () => {
    const html = renderMarkdown('<script>alert("xss")</script>ok');
    expect(html).not.toContain("<script");
    expect(html).toContain("ok");
  });

  test("keeps safe links", () => {
    const html = renderMarkdown("[docs](https://example.com)");
    expect(html).toContain('href="https://example.com"');
  });

  test("gfm tables", () => {
    const html = renderMarkdown("| a | b |\n|---|---|\n| 1 | 2 |");
    expect(html).toContain("<table>");
    expect(html).toContain("<td>1</td>");
  });
});
