# Frontend

React 19 + Vite + TypeScript UI for the Legal Document Assistant. It talks to the
backend API v1 (`/api/v1`) and keeps all UI copy in Bulgarian.

## Scripts

| Command             | Purpose                                           |
| ------------------- | ------------------------------------------------- |
| `npm install`       | Install dependencies (Node `^20.19` or `>=22.12`) |
| `npm run dev`       | Dev server on http://127.0.0.1:5173               |
| `npm run build`     | Type-check and build to `dist/`                   |
| `npm run preview`   | Serve the production build locally                |
| `npm run lint`      | ESLint (flat config, type-aware rules)            |
| `npm run typecheck` | `tsc --noEmit` for app and tooling configs        |
| `npm run format`    | Prettier write (`format:check` to verify only)    |

## Configuration

| Variable            | Default   | Notes                                                        |
| ------------------- | --------- | ------------------------------------------------------------ |
| `VITE_API_BASE_URL` | `/api/v1` | Full API base including the version prefix. Build-time only. |

See `.env.example`. Put local overrides in `.env.local` (git-ignored).

## API proxy

- **Dev:** `vite.config.ts` proxies `/api` to `http://127.0.0.1:8000`, so start the
  backend first and leave `VITE_API_BASE_URL` unset.
- **Container:** `nginx.conf` serves `dist/` and proxies `/api/` to
  `http://backend:8000` (the backend service name on the compose network).

```sh
docker build -t legal-frontend .
docker run --rm -p 8080:80 legal-frontend
```

## Layout

```
src/
  api/         fetch client (ApiError from the error envelope) and typed endpoint modules
  hooks/       useHealth (polls every 15 s), useCases, useCaseDetail
  components/  one small component per UI concern
  styles/      plain CSS (base, layout, components)
  utils/       formatting helpers
```

Imports use the `@/` alias for `src/`.
