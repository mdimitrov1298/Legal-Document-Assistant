/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Full API base including the version prefix, e.g. `http://127.0.0.1:8000/api/v1`. */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
