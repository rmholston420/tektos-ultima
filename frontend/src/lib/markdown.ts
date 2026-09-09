"use client";

import DOMPurify from "dompurify";
import { marked } from "marked";
import hljs from "highlight.js/lib/common";
import "highlight.js/styles/github-dark.css";

/**
 * Configure marked with syntax highlighting and safe defaults.
 *
 * All output passes through DOMPurify before being written to the DOM,
 * so untrusted assistant/tool content cannot inject scripts.
 */
marked.setOptions({
  gfm: true,
  breaks: false,
});

marked.use({
  renderer: {
    code(this: unknown, { text, lang }: { text: string; lang?: string }) {
      const language = lang && hljs.getLanguage(lang) ? lang : "plaintext";
      let highlighted: string;
      try {
        highlighted = hljs.highlight(text, { language, ignoreIllegals: true }).value;
      } catch {
        highlighted = escapeHtml(text);
      }
      return `<pre class="tektos-code"><code class="language-${escapeHtml(language)} hljs">${highlighted}</code></pre>`;
    },
  },
});

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function renderMarkdown(md: string): string {
  const html = marked.parse(md, { async: false }) as string;
  return DOMPurify.sanitize(html, {
    ADD_ATTR: ["target", "rel"],
    FORBID_TAGS: ["script", "style", "iframe", "object", "embed"],
  });
}
