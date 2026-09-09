"use client";

import { atom } from "nanostores";
import type { ConnectionState } from "@/types/protocol";

/** Global connection state, mirrored from ProtocolClient. */
export const $connectionState = atom<ConnectionState>("disconnected");
export const $connectionError = atom<string | null>(null);
