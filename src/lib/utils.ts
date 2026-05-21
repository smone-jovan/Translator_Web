import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import React from "react";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Basic markdown parser for rendering bold (**text**) and italic (*text*)
 * strings safely inside React elements.
 */
export function renderMarkdown(text: string | null | undefined): (string | React.ReactElement)[] {
  if (!text) return [];

  // Match **bold** or *italic* sequences (non-greedy)
  // Group 1 captures the entire match so it is preserved in the output of .split()
  const parts = text.split(/(\*\*.*?\*\*|\*.*?\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      const inner = part.slice(2, -2);
      return React.createElement("strong", { key: index, className: "font-bold" }, inner);
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      const inner = part.slice(1, -1);
      return React.createElement("em", { key: index, className: "italic" }, inner);
    }
    return part;
  });
}

