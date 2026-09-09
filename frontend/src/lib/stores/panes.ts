"use client";

import { atom } from "nanostores";
import type { PaneId } from "@/components/panes/registry";

export const $activePane = atom<PaneId>("files");
export const $rightRailOpen = atom<boolean>(true);
