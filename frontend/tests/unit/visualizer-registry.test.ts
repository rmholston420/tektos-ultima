import {
  getVisualizer,
  listVisualizers,
  registerVisualizer,
} from "@/components/assistant-ui/tool-visualizers/registry";
import { registerBuiltinVisualizers } from "@/components/assistant-ui/tool-visualizers";

describe("visualizer registry", () => {
  test("registers built-ins", () => {
    registerBuiltinVisualizers();
    const names = listVisualizers();
    for (const t of ["bash", "file_read", "file_write", "directory_list", "search"]) {
      expect(names).toContain(t);
    }
  });

  test("returns undefined for unknown tools", () => {
    expect(getVisualizer("does-not-exist-tool")).toBeUndefined();
  });

  test("register adds a new tool", () => {
    const Fake = () => null;
    registerVisualizer("custom_x", Fake);
    expect(getVisualizer("custom_x")).toBe(Fake);
  });
});
