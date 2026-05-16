// Centralized API configuration for cross-device access (Desktop & Mobile)
export const API_BASE = window.location.hostname === 'localhost' 
  ? 'http://localhost:8000' 
  : `http://${window.location.hostname}:8000`;

export const getApiUrl = (path: string) => `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
