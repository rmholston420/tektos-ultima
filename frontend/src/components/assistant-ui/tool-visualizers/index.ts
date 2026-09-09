"use client";

import { registerVisualizer } from "./registry";
import { BashVisualizer } from "./BashVisualizer";
import { FileReadVisualizer } from "./FileReadVisualizer";
import { FileWriteVisualizer } from "./FileWriteVisualizer";
import { DirectoryListVisualizer } from "./DirectoryListVisualizer";
import { SearchVisualizer } from "./SearchVisualizer";

/**
 * Register built-in visualizers. Imported once by the shell so the
 * registry is populated before any transcript render. Additional
 * plugins can register more visualizers from their own entry points.
 */
export function registerBuiltinVisualizers(): void {
  registerVisualizer("bash", BashVisualizer);
  registerVisualizer("shell", BashVisualizer);
  registerVisualizer("file_read", FileReadVisualizer);
  registerVisualizer("read_file", FileReadVisualizer);
  registerVisualizer("file_write", FileWriteVisualizer);
  registerVisualizer("write_file", FileWriteVisualizer);
  registerVisualizer("file_delete", FileWriteVisualizer);
  registerVisualizer("directory_list", DirectoryListVisualizer);
  registerVisualizer("directory_create", DirectoryListVisualizer);
  registerVisualizer("ls", DirectoryListVisualizer);
  registerVisualizer("search", SearchVisualizer);
  registerVisualizer("grep", SearchVisualizer);
  registerVisualizer("ripgrep", SearchVisualizer);
}
