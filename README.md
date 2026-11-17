# YouTube Transcripts

A small personal tool that fetches Korean/English transcripts from YouTube channels, playlists or videos, stores them in SQLite, and keeps the market-related parts so they can be pasted into an LLM.

- Paste channel / playlist / video URLs, fetch new videos one at a time (with rate-limit backoff and a Stop button)
- Browse by fetch day and channel, tick videos, copy or download them as one text block
- Keyword filter keeps market-relevant 45-second chunks (prices, rates, tickers, sectors…)

Built with FastAPI, [yt-dlp](https://github.com/yt-dlp/yt-dlp), SQLite, Svelte 5, Vite and Tailwind.

## Run

With Docker:

```bash
docker compose -f compose.dev.yml up -d    # http://localhost:5173
```

Without Docker:

```bash
pip install -r requirements.txt
uvicorn app:app --reload                   # API on :8000
cd web && pnpm install && pnpm dev         # UI on http://localhost:5173
```

Try a small "Max new videos" first.

## Disclaimer

- For personal use. You are responsible for following [YouTube's Terms of Service](https://www.youtube.com/t/terms) and for respecting the copyright of the creators whose transcripts you fetch. Don't redistribute fetched transcripts.
- Not affiliated with YouTube or Google.
- Nothing here is financial advice.
