# AI-RAG Engine — Frontend

React + TypeScript SPA for the Template AI Engine: dashboards, uploads, chat, and auth against the FastAPI backend.

## Stack

| Layer | Choice |
|--------|--------|
| Runtime | **Node 20+** (matches the Docker `node:20-alpine` build image) |
| UI | **React 19**, **React Router 6** |
| Build | **Vite 7** with **@vitejs/plugin-react** 5.x |
| Styling | **Tailwind CSS 4** via **@tailwindcss/vite** |
| State / data | **Zustand**, **TanStack React Query**, **React Hook Form** + **Zod** |
| HTTP | **Axios** (`src/lib/api.ts`) |

**Note:** `@tailwindcss/vite` expects Vite 5–7, and `@vitejs/plugin-react` 6.x targets Vite 8 only. This repo pins **Vite `^7.3.1`** and **`@vitejs/plugin-react` `^5.1.0`** so `npm ci` and Docker builds stay compatible.

## Prerequisites

- **Node.js 20+** and **npm** (or **pnpm** / **yarn** if you adjust lockfiles)
- Backend API running for full functionality (default proxied target: `http://localhost:8000`)

## Install

From this directory:

```bash
npm install
```

Use `npm ci` in CI or Docker — it requires `package-lock.json` to match `package.json`.

## Environment variables

Create `.env` / `.env.local` as needed (Vite only exposes vars prefixed with `VITE_`):

| Variable | Purpose |
|----------|---------|
| `VITE_API_BASE_URL` | Base URL for Axios (default in code: `/api`). In dev, Vite proxies `/api` → backend (see `vite.config.ts`). |

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Dev server with HMR (default port **3000**) |
| `npm run build` | `tsc -b` then production Vite build → `dist/` |
| `npm run preview` | Serve `dist/` locally (useful after `build`) |
| `npm run lint` | ESLint |

## Local development

1. Start the API (from repo root), e.g. backend on port **8000**.
2. In `frontend/`:

   ```bash
   npm run dev
   ```

3. Open **http://localhost:3000** (see `vite.config.ts`).

The dev server proxies **`/api`** → **`http://localhost:8000`**, stripping the `/api` prefix so browser calls like `GET /api/health` hit the backend `GET /health`.

## Docker

From the **repository root** (not `frontend/`):

```bash
cp .env.example .env   # configure DB, Redis, JWT, etc.
docker compose up --build -d
```

- The **frontend** image is built from [`Dockerfile`](./Dockerfile`) (`npm ci` → `npm run build` → static files served by nginx).
- Published port is **`3002` → container `3000`** in [`docker-compose.yml`](../docker-compose.yml) (host **3002** avoids clashing with other apps on **3000**).
- **Nginx** on the host may expose **80** / **443** and route to the API and UI — see [`../nginx/`](../nginx/).

After compose is up:

- UI: **http://localhost:3002**
- API docs: **http://localhost:8000/docs**
- Health: **http://localhost:8000/health**

## Project layout (high level)

```
frontend/
├── src/
│   ├── components/     # Layout, UI primitives
│   ├── lib/            # api client, utils (cn, formatters)
│   ├── pages/          # Route-level screens
│   ├── services/       # API wrappers
│   ├── stores/         # Zustand state
│   └── vite-env.d.ts   # Vite env typings
├── vite.config.ts      # proxy, Tailwind, @ alias
├── Dockerfile          # production build + nginx serve
└── package.json
```

## Troubleshooting

| Issue | What to try |
|--------|-------------|
| `npm ci` fails with peer dependency errors | Ensure `package.json` / `package-lock.json` are in sync (run `npm install` locally and commit the lockfile). |
| API calls fail in dev | Confirm backend is on port 8000 or adjust `vite.config.ts` `server.proxy`. |
| `Cannot find module '../lib/...'` | Ensure `src/lib/api.ts` and `src/lib/utils.ts` exist (they are committed in this repo). |

## More documentation

- Repo-wide architecture and API: **[../README.md](../README.md)**
