"use client";

import type { ComponentType } from "react";
import type { ToolCallRecord } from "@/lib/stores/session";

export interface VisualizerProps {
  tool: ToolCallRecord;
}

export type Visualizer = ComponentType<VisualizerProps>;

const registry = new Map<string, Visualizer>();

/** Register a visualizer for a tool name (exact match). */
export function registerVisualizer(toolName: string, component: Visualizer): void {
  registry.set(toolName, component);
}

/** Get the registered visualizer for a tool name, or undefined. */
export function getVisualizer(toolName: string): Visualizer | undefined {
  return registry.get(toolName);
}

/** Enumerate registered tools (used by Settings/Panels). */
export function listVisualizers(): string[] {
  return Array.from(registry.keys());
}
