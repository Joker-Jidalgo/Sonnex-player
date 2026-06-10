# main.py — Sonnex Backend v1.5
# Python 3.8 | ytmusicapi для поиска + yt-dlp с cookies для стриминга

import asyncio
import re
import time
from typing import List, Optional, Tuple

import yt_dlp
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

app = FastAPI(title="Sonnex API", version="1.5.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ──────────────────────────────────
class Track(BaseModel):
    id: str
    title: str
    artist: str
    duration: Optional[float] = None
    cover_url: Optional[str] = None
    stream_url: Optional[str] = None
    is_premium: bool = False

class SearchResponse(BaseModel):
    query: str
    took_ms: float
    results: List[Track]

# ── Search через ytmusicapi ──────────────────
def search_tracks(query: str, limit: int = 10) -> List[Track]:
    try:
        from ytmusicapi import YTMusic
        ytm = YTMusic()
        raw = ytm.search(query, filter="songs", limit=limit)
    except Exception as e:
        print(f"[search] ytmusicapi failed: {e}, falling back to yt-dlp")
        return _search_ytdlp(query, limit)

    results = []
    for item in raw[:limit]:
        try:
            vid_id = item.get("videoId", "")
            if not vid_id:
                continue

            title  = item.get("title", "Untitled")
            artists = item.get("artists") or []
            artist = artists[0]["name"] if artists else "Unknown"
            duration_s = None
            dur_str = item.get("duration")        # "3:45"
            if dur_str and ":" in str(dur_str):
                parts = str(dur_str).split(":")
                duration_s = int(parts[0]) * 60 + int(parts[1])

            # Обложка
            thumbnails = item.get("thumbnails") or []
            cover_url = thumbnails[-1]["url"] if thumbnails else None

            results.append(Track(
                id=vid_id,
                title=title,
                artist=artist,
                duration=duration_s,
                cover_url=cover_url,
                stream_url=f"http://127.0.0.1:8000/api/stream/{vid_id}",
            ))
        except Exception as e:
            print(f"[search] skip item: {e}")
            continue

    return results


def _search_ytdlp(query: str, limit: int) -> List[Track]:
    """Fallback поиск через yt-dlp если ytmusicapi недоступен."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "noplaylist": True,
    }
    results = []
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        except Exception as e:
            print(f"[search-ytdlp] error: {e}")
            return []

    for entry in (info.get("entries") or []):
        vid_id = entry.get("id", "")
        if not vid_id:
            continue
        duration = float(entry.get("duration") or 0)
        if duration > 0 and (duration < 30 or duration > 720):
            continue
        raw_title = entry.get("title", "Untitled")
        uploader  = entry.get("uploader") or ""
        if " - " in raw_title:
            parts  = raw_title.split(" - ", 1)
            artist, title = parts[0].strip(), parts[1].strip()
        else:
            artist = re.sub(r'(\s*-\s*Topic|VEVO)$', '', uploader, flags=re.IGNORECASE).strip() or "Unknown"
            title  = raw_title
        thumbnails = entry.get("thumbnails") or []
        cover_url  = thumbnails[-1].get("url") if thumbnails else None
        results.append(Track(
            id=vid_id, title=title, artist=artist,
            duration=duration or None, cover_url=cover_url,
            stream_url=f"http://127.0.0.1:8000/api/stream/{vid_id}",
        ))
    return results


# ── Stream ───────────────────────────────────
def _pick_url(formats: list) -> Optional[str]:
    def ok(f):
        u = f.get("url", "")
        return bool(u) and not any(x in u for x in [".m3u8", ".mpd", "initplayback"])

    audio = [f for f in formats
             if f.get("acodec") not in (None, "none", "")
             and f.get("vcodec") in (None, "none", "")
             and ok(f)]
    if audio:
        best = max(audio, key=lambda f: float(f.get("abr") or 0))
        print(f"  → audio: {best.get('ext')} {best.get('abr')}kbps")
        return best["url"]

    mixed = [f for f in formats
             if f.get("acodec") not in (None, "none", "") and ok(f)]
    if mixed:
        best = min(mixed, key=lambda f: int(f.get("height") or 9999))
        print(f"  → mixed: {best.get('ext')} {best.get('height')}p")
        return best["url"]
    return None


# Клиенты в порядке приоритета
_STREAM_CLIENTS = [
    "tv_embedded",
    "web_creator",   # YouTube Studio клиент — меньше ограничений
    "web",
    "android_vr",    # VR клиент — не блокируется
]

def get_stream_url(video_id: str) -> str:
    url = f"https://www.youtube.com/watch?v={video_id}"

    for client in _STREAM_CLIENTS:
        print(f"[stream] {video_id} → client={client}")
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "extractor_args": {
                "youtube": {
                    "player_client": [client],
                    "skip": ["hls", "dash"],
                }
            },
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            fmts = info.get("formats") or []
            print(f"  {len(fmts)} formats")
            u = _pick_url(fmts)
            if u:
                return u
        except Exception as e:
            print(f"  {client} error: {e}")

    # Финальный fallback — без skip dash/hls, берём что дадут
    print(f"[stream] {video_id} → final fallback (no skip)")
    opts_f = {
        "quiet": False,
        "skip_download": True,
        "noplaylist": True,
        "extractor_args": {
            "youtube": {"player_client": ["tv_embedded"]}
        },
    }
    try:
        with yt_dlp.YoutubeDL(opts_f) as ydl:
            info = ydl.extract_info(url, download=False)
        fmts = info.get("formats") or []
        for f in reversed(fmts):
            u = f.get("url", "")
            if u:
                print(f"  fallback url: ext={f.get('ext')}")
                return u
    except Exception as e:
        print(f"  final fallback error: {e}")

    raise ValueError(
        f"Video {video_id} is restricted (age-gate/geo-block). "
        "Try a different track."
    )


# ── Routes ───────────────────────────────────
@app.get("/")
async def root():
    return FileResponse("index.html")

@app.get("/api/search", response_model=SearchResponse)
async def api_search(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(10, ge=1, le=20),
):
    t0 = time.monotonic()
    loop = asyncio.get_event_loop()
    tracks = await loop.run_in_executor(None, search_tracks, q, limit)
    took = (time.monotonic() - t0) * 1000
    print(f"[search] '{q}' → {len(tracks)} tracks in {took:.0f}ms")
    return SearchResponse(query=q, took_ms=round(took, 1), results=tracks)

@app.get("/api/stream-url/{video_id}")
async def api_stream_url(video_id: str):
    if not re.match(r'^[A-Za-z0-9_\-]{5,20}$', video_id):
        raise HTTPException(400, "Invalid video ID")
    loop = asyncio.get_event_loop()
    try:
        url = await loop.run_in_executor(None, get_stream_url, video_id)
    except Exception as e:
        raise HTTPException(502, detail=str(e))
    return {"video_id": video_id, "url": url}

@app.get("/api/stream/{video_id}")
async def api_stream(video_id: str):
    if not re.match(r'^[A-Za-z0-9_\-]{5,20}$', video_id):
        raise HTTPException(400, "Invalid video ID")
    loop = asyncio.get_event_loop()
    try:
        url = await loop.run_in_executor(None, get_stream_url, video_id)
    except Exception as e:
        raise HTTPException(502, detail=str(e))
    return RedirectResponse(url=url, status_code=302)

if __name__ == "__main__":
    import uvicorn
    print("🛸  Sonnex API v1.5 → http://127.0.0.1:8000")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)