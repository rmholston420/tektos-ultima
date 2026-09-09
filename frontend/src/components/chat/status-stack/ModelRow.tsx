"use client";

import { useStore } from "@nanostores/react";
import { Cpu } from "lucide-react";
import { $sessionModel } from "@/lib/stores/session";
import { $connectionState } from "@/lib/stores/connection";
import { StatusRow } from "./StatusRow";

export function ModelRow() {
  const model = useStore($sessionModel);
  const state = useStore($connectionState);
  if (state !== "connected") return null;
  return (
    <StatusRow icon={<Cpu className="h-3 w-3" />} tone="info" data-testid="status-model">
      <span className="text-text-muted">model</span>{" "}
      <span className="font-mono text-text-base">
        {model ?? "— (no session yet)"}
      </span>
    </StatusRow>
  );
}
