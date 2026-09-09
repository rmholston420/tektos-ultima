"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useStore } from "@nanostores/react";
import { MessageSquare, Files, Play, LayoutDashboard, Settings } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { $connectionState, $connectionError } from "@/lib/stores/connection";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  match: (pathname: string) => boolean;
}

const NAV: NavItem[] = [
  { href: "/", label: "Chat", icon: MessageSquare, match: (p) => p === "/" || p.startsWith("/s/") },
  { href: "/artifacts", label: "Artifacts", icon: Files, match: (p) => p.startsWith("/artifacts") },
  { href: "/runs", label: "Runs", icon: Play, match: (p) => p.startsWith("/runs") },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, match: (p) => p.startsWith("/dashboard") },
  { href: "/settings", label: "Settings", icon: Settings, match: (p) => p.startsWith("/settings") },
];

export function LeftRail() {
  const pathname = usePathname();
  const state = useStore($connectionState);
  const error = useStore($connectionError);
  const dotClass =
    state === "connected"
      ? "bg-success"
      : state === "connecting" || state === "reconnecting"
        ? "bg-agent animate-tektos-pulse"
        : "bg-error";
  return (
    <aside aria-label="Navigation" className="hairline flex min-h-0 flex-col bg-surface-2">
      <div className="flex flex-col gap-4 p-3">
        <div className="text-11 uppercase tracking-wide text-text-muted">Tektos</div>
        <div className="flex items-center gap-2 text-11" data-testid="connection-indicator">
          <span className={cn("h-2 w-2 rounded-full", dotClass)} />
          <span className="text-text-muted">{state}</span>
        </div>
        {error && (
          <div className="text-11 text-error" role="status">
            {error}
          </div>
        )}
      </div>
      <nav className="mt-2 flex flex-col gap-0.5 px-2">
        {NAV.map(({ href, label, icon: Icon, match }) => {
          const active = match(pathname ?? "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2 rounded px-2 py-1.5 text-11",
                "transition-colors duration-fast ease",
                active
                  ? "bg-surface-4 text-text-base"
                  : "text-text-muted hover:bg-surface-3 hover:text-text-base",
              )}
              data-testid={`nav-${label.toLowerCase()}`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
