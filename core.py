"""YouTube logic only: list channel videos, fetch captions, parse, filter. No web or database code."""
import json
import re

import yt_dlp

LANGS = ("ko", "en")
CHUNK_SECONDS = 45  # transcript is split into chunks of this length
CONTEXT = 1         # keep this many chunks before/after each matching chunk

KEYWORDS = [
    # Korean: markets / macro
    "주식", "증시", "코스피", "코스닥", "나스닥", "다우", "S&P", "지수", "종목", "섹터", "업종",
    "시장", "전망", "예상", "예측", "목표가", "주가", "시총", "시가총액", "밸류", "PER", "PBR",
    "금리", "기준금리", "연준", "Fed", "FOMC", "한은", "인플레", "물가", "CPI", "GDP", "고용",
    "환율", "달러", "엔화", "원화", "유가", "금값", "채권", "국채", "수익률", "부동산", "아파트",
    "실적", "매출", "영업이익", "순이익", "어닝", "가이던스", "배당", "공시", "IPO", "상장",
    "매수", "매도", "공매도", "물타기", "손절", "익절", "비중", "포트폴리오", "레버리지", "ETF",
    "상승", "하락", "급등", "급락", "폭락", "반등", "조정", "랠리", "버블", "고점", "저점", "바닥",
    "리스크", "위험", "침체", "경기", "불황", "호황", "관세", "규제", "정책", "선거", "전쟁",
    "반도체", "AI", "2차전지", "배터리", "바이오", "자동차", "조선", "방산", "은행", "코인", "비트코인",
    "외국인", "기관", "수급", "거래량", "외인",
    # English
    "stock", "market", "index", "forecast", "outlook", "earnings", "revenue", "guidance",
    "rate", "inflation", "recession", "yield", "bond", "dollar", "tariff", "buy", "sell",
    "bull", "bear", "rally", "crash", "valuation", "dividend", "sector", "risk",
]
KEYWORD_RE = re.compile("|".join(re.escape(k) for k in KEYWORDS), re.IGNORECASE)
# numbers with units (3%, 5조, 100달러), tickers (NVDA), 6-digit Korean stock codes
NUMBER_RE = re.compile(r"\d+(\.\d+)?\s*(%|퍼센트|프로|bp|원|달러|조|억|만|배|포인트)|\b[A-Z]{2,5}\b|\b\d{6}\b")

VIDEO_ID_RE = re.compile(r"(?:[?&]v=|youtu\.be/|/shorts/|/live/)([\w-]{11})")

RATE_LIMIT_SIGNS =("429", "Too Many Requests", "not a bot")
GONE_SIGNS = ("Private video", "Video unavailable", "has been removed", "members-only")

YDL_OPTS = {"quiet": True, "no_warnings": True, "skip_download": True, "ignore_no_formats_error": True}


class RateLimited(Exception):
    pass


def new_ydl():
    return yt_dlp.YoutubeDL(YDL_OPTS)


def parse_urls(text):
    """Text (one URL per line, first column) -> list of URLs."""
    urls = []
    for line in text.splitlines():
        first = re.split(r"[,\t ]+", line.strip())[0].strip('"')
        if first.startswith("http"):
            urls.append(first)
    return urls


def _raise_if_rate_limited(e):
    if any(s in str(e) for s in RATE_LIMIT_SIGNS):
        raise RateLimited(str(e)) from e


def list_video_ids(ydl, url):
    """Channel/playlist/video URL -> video IDs. Only reads the listing, not each video."""
    m = VIDEO_ID_RE.search(url)
    if m and "list=" not in url:  # a single video: ID is in the URL, no request needed
        return [m.group(1)]
    try:
        info = ydl.extract_info(url, download=False, process=False)
    except Exception as e:
        _raise_if_rate_limited(e)
        raise
    if "entries" not in info:  # a single video
        return [info["id"]]
    ids = []
    for e in info["entries"]:
        if e.get("ie_key") == "Youtube":
            ids.append(e["id"])
        elif e.get("url"):  # channel tab (Videos / Shorts / Live) -> list it too
            ids += list_video_ids(ydl, e["url"])
    return list(dict.fromkeys(ids))  # remove duplicates, keep order


def pick_track(info):
    """Prefer manual subs, then original-language auto captions, then translated auto captions."""
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    candidates = []
    for lang in LANGS:
        candidates += [(manual, k) for k in manual if k == lang or k.startswith(lang + "-")]
    for lang in LANGS:
        candidates += [(auto, k) for k in auto if k == f"{lang}-orig"]
    for lang in LANGS:
        candidates += [(auto, lang)] if lang in auto else []
    for source, key in candidates:
        formats = {f.get("ext"): f["url"] for f in source[key]}
        for ext in ("json3", "vtt"):
            if ext in formats:
                return key, ext, formats[ext]
    return None


def parse_json3(raw):
    """YouTube json3 captions -> [(start_seconds, text)]"""
    lines = []
    for ev in json.loads(raw).get("events", []):
        text = "".join(s.get("utf8", "") for s in ev.get("segs") or []).strip()
        if text:
            lines.append((ev.get("tStartMs", 0) / 1000, text))
    return lines


def parse_vtt(raw):
    """VTT captions -> [(start_seconds, text)]"""
    lines, t = [], 0.0
    for line in raw.splitlines():
        line = line.strip()
        if "-->" in line:
            parts = [float(p) for p in line.split("-->")[0].strip().replace(",", ".").split(":")]
            t = sum(p * 60 ** i for i, p in enumerate(reversed(parts)))
        elif line and not line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) and not line.isdigit():
            line = re.sub(r"<[^>]+>", "", line).strip()  # remove inline tags
            if line and (not lines or lines[-1][1] != line):
                lines.append((t, line))
    return lines


def to_chunks(lines):
    """[(seconds, text)] -> [(chunk_start_seconds, chunk_text)] of CHUNK_SECONDS each."""
    chunks, current, start, last = [], [], None, None
    for t, text in lines:
        text = re.sub(r"\s+", " ", text).strip()
        if not text or text == last:  # skip blanks and repeated caption lines
            continue
        last = text
        if start is None:
            start = t
        if t - start >= CHUNK_SECONDS and current:
            chunks.append((start, " ".join(current)))
            current, start = [], t
        current.append(text)
    if current:
        chunks.append((start, " ".join(current)))
    return chunks


def filter_chunks(chunks):
    """Keep chunks with keywords/numbers/tickers plus CONTEXT neighbours. Cut parts marked [...]"""
    hits = {i for i, (_, c) in enumerate(chunks) if KEYWORD_RE.search(c) or NUMBER_RE.search(c)}
    keep = sorted({j for i in hits for j in range(i - CONTEXT, i + CONTEXT + 1) if 0 <= j < len(chunks)})
    parts, prev = [], None
    for i in keep:
        if prev is not None and i != prev + 1:
            parts.append("[...]")
        m, s = divmod(int(chunks[i][0]), 60)
        parts.append(f"[{m}:{s:02d}] {chunks[i][1]}")
        prev = i
    return "\n".join(parts)


def fetch_video(ydl, vid):
    """Video ID -> dict ready to store. Raises RateLimited if YouTube blocks us."""
    url = f"https://www.youtube.com/watch?v={vid}"
    v = {"id": vid, "url": url, "title": vid, "channel": "", "upload_date": "",
         "lang": "", "status": "", "full_text": "", "filtered_text": ""}
    try:
        info = ydl.extract_info(url, download=False)
        d = info.get("upload_date") or ""  # "20261115" -> "2026-11-15"
        v.update(title=info.get("title", vid), channel=info.get("channel", ""),
                 upload_date=f"{d[:4]}-{d[4:6]}-{d[6:]}" if d else "")
        track = pick_track(info)
        if not track:
            v["status"] = "no_captions"
            return v
        lang, ext, sub_url = track
        raw = ydl.urlopen(sub_url).read().decode("utf-8", errors="replace")
    except Exception as e:
        _raise_if_rate_limited(e)
        if any(s in str(e) for s in GONE_SIGNS):
            v["status"] = "unavailable"
            return v
        raise  # other errors (e.g. upcoming live): not stored, so retried next run
    chunks = to_chunks(parse_json3(raw) if ext == "json3" else parse_vtt(raw))
    v.update(lang=lang, status="ok",
             full_text=" ".join(c for _, c in chunks), filtered_text=filter_chunks(chunks))
    return v