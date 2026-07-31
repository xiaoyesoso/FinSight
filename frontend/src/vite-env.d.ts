/// <reference types="vite/client" />

// Custom env variables for the IIRAS frontend.
interface ImportMetaEnv {
  /** Backend base URL for API calls (dev only; empty in production for same-origin). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
