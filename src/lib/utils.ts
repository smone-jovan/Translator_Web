import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import React from "react";
import { API_BASE, getActiveWorkspace, getWorkspaceHeaders } from "./api";
import SafeReaderImage from "@/components/reader/SafeReaderImage";

export { getActiveWorkspace, getWorkspaceHeaders };

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Resolve a stored cover URL into something an <img> can load reliably.
 * Remote http(s) covers go through the backend proxy (handles hotlink protection and
 * Cloudflare-protected hosts, and caches on disk); data:/blob:/local paths pass through.
 */
export function coverImageSrc(
  url: string | null | undefined
): string | undefined {
  if (!url) return undefined;
  if (url.startsWith("http://") || url.startsWith("https://")) {
    return `${API_BASE}/api/images/proxy?url=${encodeURIComponent(url)}`;
  }
  return url;
}

/**
 * Text colour for destructive actions. rose-500 measured ~3.1-3.7:1 on sepia/white and on the
 * dark-blue omni theme. rose-700 on the light themes (sepia, white), rose-300 on omni and
 * rose-400 on the near-black themes keep it >= 4.5:1 (WCAG 1.4.3).
 */
export const DESTRUCTIVE_TEXT =
  "text-rose-400 [:root[data-theme=white]_&]:text-rose-700 [:root[data-theme=sepia]_&]:text-rose-700 [:root[data-theme=omni]_&]:text-rose-300";

/**
 * Basic markdown parser for rendering bold (**text**) and italic (*text*)
 * strings safely inside React elements.
 */
export function renderMarkdown(
  text: string | null | undefined
): (string | React.ReactElement)[] {
  if (!text) return [];

  // Match <img src="..."> or ![alt](url) or **bold** or *italic* sequences (non-greedy)
  // Group 1 captures the entire match so it is preserved in the output of .split()
  const parts = text.split(
    /(<img\s+[^>]*src\s*=\s*['"][^'"]+['"][^>]*>|!\[.*?\]\(.*?\)|\*\*.*?\*\*|\*.*?\*)/gi
  );

  return parts.map((part, index) => {
    if (
      part.toLowerCase().startsWith("<img ") &&
      part.toLowerCase().includes("src=")
    ) {
      const srcMatch = part.match(/src\s*=\s*['"]([^'"]+)['"]/i);
      const altMatch = part.match(/alt\s*=\s*['"]([^'"]*)['"]/i);
      if (srcMatch) {
        let imgSrc = srcMatch[1];
        if (imgSrc.startsWith("/images/")) {
          imgSrc = `${API_BASE}${imgSrc}`;
        } else if (
          imgSrc.startsWith("http://") ||
          imgSrc.startsWith("https://")
        ) {
          imgSrc = `${API_BASE}/api/images/proxy?url=${encodeURIComponent(imgSrc)}`;
        }
        return React.createElement(SafeReaderImage, {
          key: index,
          src: imgSrc,
          alt: altMatch ? altMatch[1] : "Image",
          className:
            "max-w-full h-auto my-4 rounded-xl border border-[var(--border)] shadow-sm mx-auto block",
        });
      }
    }
    if (part.startsWith("![") && part.includes("](") && part.endsWith(")")) {
      const altMatch = part.match(/!\[(.*?)\]/);
      const urlMatch = part.match(/\((.*?)\)/);
      if (altMatch && urlMatch) {
        let imgSrc = urlMatch[1];
        // Fix for local images extracted from EPUB
        if (imgSrc.startsWith("/images/")) {
          imgSrc = `${API_BASE}${imgSrc}`;
        } else if (
          imgSrc.startsWith("http://") ||
          imgSrc.startsWith("https://")
        ) {
          imgSrc = `${API_BASE}/api/images/proxy?url=${encodeURIComponent(imgSrc)}`;
        }
        return React.createElement(SafeReaderImage, {
          key: index,
          src: imgSrc,
          alt: altMatch[1],
          className:
            "max-w-full h-auto my-4 rounded-xl border border-[var(--border)] shadow-sm mx-auto block",
        });
      }
    }
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      const inner = part.slice(2, -2);
      return React.createElement(
        "strong",
        { key: index, className: "font-bold" },
        inner
      );
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      const inner = part.slice(1, -1);
      return React.createElement(
        "em",
        { key: index, className: "italic" },
        inner
      );
    }
    return part;
  });
}
