// Centralized API configuration for cross-device access (Desktop & Mobile) via same-origin proxy
export const API_BASE = '';

export const getApiUrl = (path: string) => path.startsWith('/') ? path : `/${path}`;

