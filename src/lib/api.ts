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

/**
 * Bersihkan cache sessionStorage untuk daftar Library, metadata Thread,
 * dan konten Chapter setelah terjadi mutasi (import, hapus, edit, sinkronisasi glosarium,
 * atau perbaikan fidelity) agar pengguna tidak pernah melihat teks/status basi.
 */
export function invalidateThreadCache(
  threadId?: number | string | null,
  chapterId?: number | string | null
): void {
  try {
    const ws = getActiveWorkspace();
    sessionStorage.removeItem(`readomni_library_cache_v1_${ws}`);
    sessionStorage.removeItem("readomni_library_cache_v1");

    if (threadId !== undefined && threadId !== null && threadId !== "") {
      const tid = String(threadId);
      sessionStorage.removeItem(`readomni_thread_cache_${ws}_${tid}`);
      sessionStorage.removeItem(`readomni_thread_cache_${tid}`);

      if (chapterId !== undefined && chapterId !== null && chapterId !== "") {
        const cid = String(chapterId);
        sessionStorage.removeItem(`readomni_chapter_cache_${ws}_${tid}_${cid}`);
        sessionStorage.removeItem(`readomni_chapter_cache_${tid}_${cid}`);
        sessionStorage.removeItem(`readomni_ch_cache_${ws}_${tid}_${cid}`);
        sessionStorage.removeItem(`readomni_ch_cache_${tid}_${cid}`);
      } else {
        const prefixes = [
          `readomni_chapter_cache_${ws}_${tid}_`,
          `readomni_chapter_cache_${tid}_`,
          `readomni_ch_cache_${ws}_${tid}_`,
          `readomni_ch_cache_${tid}_`,
        ];
        const keysToRemove: string[] = [];
        for (let i = 0; i < sessionStorage.length; i++) {
          const k = sessionStorage.key(i);
          if (k && prefixes.some((p) => k.startsWith(p))) {
            keysToRemove.push(k);
          }
        }
        keysToRemove.forEach((k) => sessionStorage.removeItem(k));
      }
    }
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
