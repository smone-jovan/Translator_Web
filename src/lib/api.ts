// Centralized API configuration for cross-device access (Desktop & Mobile) via same-origin proxy
export const API_BASE = "";

export const getApiUrl = (path: string) =>
  path.startsWith("/") ? path : `/${path}`;

export function getActiveWorkspace(): string {
  try {
    const ws = localStorage.getItem("readomni_workspace");
    if (ws && ["main", "ghost"].includes(ws.toLowerCase())) {
      return ws.toLowerCase();
    }
  } catch {
    // ignore
  }
  return "main";
}

/**
 * Helper kanonik ADR-118 untuk membuat key localStorage / sessionStorage
 * yang terisolasi berdasarkan workspace aktif ('main' atau 'ghost').
 */
export function getWorkspaceStorageKey(
  baseKey: string,
  suffix?: string | number
): string {
  const ws = getActiveWorkspace();
  if (suffix !== undefined && suffix !== null && suffix !== "") {
    return `${baseKey}_${ws}_${suffix}`;
  }
  return `${baseKey}_${ws}`;
}

/**
 * Bersihkan seluruh cache sessionStorage saat pengguna berpindah workspace (main <-> ghost)
 * agar tidak terjadi kebocoran tampilan data antar workspace saat reload.
 */
export function clearWorkspaceSessionCache(): void {
  try {
    sessionStorage.clear();
  } catch {
    // ignore storage errors
  }
}

export function getWorkspaceHeaders(): Record<string, string> {
  return {
    "X-Workspace": getActiveWorkspace(),
  };
}

// Transparent fetch wrapper ensuring X-Workspace is included on all /api requests
if (typeof window !== "undefined" && window.fetch) {
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    try {
      const urlStr =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : (input as Request).url;
      if (urlStr && urlStr.includes("/api/")) {
        const workspace = getActiveWorkspace();
        const customInit = init ? { ...init } : {};
        const headers = new Headers(
          customInit.headers ||
            (typeof input !== "string" && !(input instanceof URL)
              ? (input as Request).headers
              : {})
        );
        if (!headers.has("X-Workspace") && !headers.has("x-workspace")) {
          headers.set("X-Workspace", workspace);
        }
        customInit.headers = headers;
        return originalFetch(input, customInit);
      }
    } catch {
      // Fallback to original fetch if anything fails
    }
    return originalFetch(input, init);
  };
}
