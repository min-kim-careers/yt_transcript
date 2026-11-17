"""
Web server. Run from this folder:
    uvicorn app:app            -> open http://localhost:8000
"""
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import core
import db

DELAY = 2                 # seconds between videos
BACKOFF = [60, 180, 600]  # waits after each consecutive rate limit; then the job stops

app = FastAPI()
db.init()
job = {"running": False, "stop": False, "log": []}  # one job at a time, so we never hit YouTube in parallel


def log(msg):
    job["log"].append(time.strftime("%H:%M:%S  ") + msg)


def wait(seconds):
    """Sleep, but wake early if Stop was pressed. Returns True if stopped."""
    for _ in range(seconds):
        if job["stop"]:
            break
        time.sleep(1)
    return job["stop"]


def fetch_one(ydl, vid, prefix):
    """Fetch and save one video, waiting on rate limits. Returns False if the job should stop."""
    for pause in BACKOFF + [None]:
        try:
            v = core.fetch_video(ydl, vid)
        except core.RateLimited:
            if pause is None:
                log("Rate limited repeatedly. Stopped. Try again later.")
                return False
            log(f"{prefix} rate limited, waiting {pause}s")
            if wait(pause):
                return False
            continue  # retry the same video
        except Exception as e:
            log(f"{prefix} {vid} error (will retry next run): {e}")
        else:
            db.save(v)  # saved right away, so an interrupted job keeps what it got
            log(f"{prefix} {v['title']} -> {v['status']}")
        return not wait(DELAY)


def run_job(urls, max_new):
    try:
        known = db.known_ids()
        done = 0
        with core.new_ydl() as ydl:
            # One URL at a time: list it, fetch its new videos, then the next URL
            for url in urls:
                if job["stop"]:
                    return
                log(f"Listing {url}")
                try:
                    found = core.list_video_ids(ydl, url)
                except Exception as e:
                    log(f"  failed: {e}")
                    continue
                new = [i for i in found if i not in known]
                log(f"  {len(found)} videos, {len(new)} new")
                for n, vid in enumerate(new, 1):
                    if max_new and done >= max_new:
                        log(f"Reached max {max_new} new videos")
                        return
                    if not fetch_one(ydl, vid, f"[{n}/{len(new)}]"):
                        return
                    known.add(vid)
                    done += 1
    finally:
        log("Done")
        job["running"] = False


class FetchRequest(BaseModel):
    text: str         # URLs, one per line
    max_new: int = 0  # 0 = no limit


@app.post("/api/fetch")
def start_fetch(req: FetchRequest):
    if job["running"]:
        raise HTTPException(409, "A job is already running")
    urls = core.parse_urls(req.text)
    if not urls:
        raise HTTPException(400, "No URLs found")
    job.update(running=True, stop=False, log=[])
    threading.Thread(target=run_job, args=(urls, req.max_new), daemon=True).start()
    return {"ok": True}


@app.post("/api/stop")
def stop():
    """Stop the running job after the current video (saved videos are kept)."""
    if job["running"] and not job["stop"]:
        job["stop"] = True
        log("Stopping after the current video...")
    return {"ok": True}


@app.get("/api/status")
def status():
    return job


@app.get("/api/videos")
def videos(q: str = ""):
    return db.search(q)


@app.delete("/api/videos")
def delete_videos(ids: str):
    """ids=a,b,c"""
    db.delete(ids.split(","))
    return {"ok": True}


@app.get("/api/videos/{vid}")
def video(vid: str):
    v = db.get(vid)
    if not v:
        raise HTTPException(404, "Not found")
    return v


@app.get("/api/export", response_class=PlainTextResponse)
def export(q: str = "", ids: str = "", full: bool = False, download: bool = False):
    """Matching (or chosen, ids=a,b,c) transcripts as one copy-paste friendly text."""
    wanted = set(ids.split(",")) if ids else None
    parts = []
    for v in db.with_text("" if wanted else q):
        if wanted and v["id"] not in wanted:
            continue
        text = v["full_text"] if full else v["filtered_text"]
        if text:
            parts.append(f"===== {v['title']} ({v['upload_date']} | {v['channel']}) =====\n{v['url']}\n{text}")
    headers = {"Content-Disposition": "attachment; filename=transcripts.txt"} if download else {}
    return PlainTextResponse("\n\n".join(parts), headers=headers)


# Serve the built Svelte app (web/dist) at "/". Must come after the API routes.
DIST = Path(__file__).with_name("web") / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")