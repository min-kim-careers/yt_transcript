# YouTube Transcripts App

Fetches Korean/English transcripts from YouTube channels/playlists/videos via yt-dlp, stores them in SQLite, filters market-relevant parts for pasting into an LLM for market forecasting.

## Structure
- `core.py`: YouTube logic only (list videos, pick captions, parse json3/vtt, chunk, keyword filter). No web/DB code.
- `db.py`: SQLite (`transcripts.db`, one `videos` table).
- `app.py`: FastAPI server. One background job at a time. Serves `web/dist` at `/`.
- `web/`: Svelte 5 (runes) + Vite + Tailwind v4. Flat: `App.svelte`, `main.js`, `app.css`, `index.html`.

## Run
pip install fastapi uvicorn yt-dlp
cd web && pnpm install && pnpm build && cd ..
uvicorn app:app            # http://localhost:8000
Dev UI: `pnpm dev` in web/ (proxies /api to :8000), localhost:5173

## API
POST /api/fetch {text, max_new} · GET /api/status · GET /api/videos?q= · GET /api/videos/{id} · GET /api/export?q=&full=&download=

## Key behaviour (don't break)
- Rate limit protection is the top priority: known video IDs (any status) are never re-fetched; 2s delay between videos; backoff 60/180/600s on 429/"not a bot", then stop; only one job runs at a time.
- Statuses: ok, no_captions, unavailable are stored. Other errors are not stored, so they retry next run.
- Caption priority: manual ko/en, then auto `*-orig`, then auto translated.
- Filter: 45s chunks, keep keyword/number/ticker hits ±1 chunk, gaps marked `[...]`.

## Conventions
- Keep code minimal and readable; the owner wants to understand every line.
- Root stays flat; only `web/` is a subfolder.
- pnpm, not npm. Plain Svelte, not SvelteKit (move to SvelteKit + adapter-static only when multiple pages are needed).
- When showing changes, show only changed files/diffs, never unchanged files.
- Be concise.

## Status
Not yet run against real YouTube or built: test the first fetch with a small max_new.

## Later (not now)
AI analysis pipeline (`analysis.py`, Claude API), scheduler (APScheduler), dashboards.