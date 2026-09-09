import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Tailwind-aware class merger. Use everywhere instead of raw template strings. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
