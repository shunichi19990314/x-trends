"""
X トレンドダッシュボード — FastAPI バックエンド。

起動:
    uvicorn app.main:app --reload
    または python -m app.main
"""

from __future__ import annotations

import csv
import io
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import db
from .classify import CATEGORIES, all_categories, category_meta, classify
from .config import DEFAULT_WOEIDS, STATIC_DIR, settings
from .locations import (BY_WOEID, grouped_locations, location_to_dict,
                        search_locations)
from .poller import SERVER_KEYWORDS, poller, seed_history
from .providers import ProviderError, fetch_demo, fetch_trends

APP_VERSION = "1.0.0"


# --------------------------------------------------------------------------- #
# lifespan
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if settings.seed_history and not db.all_locations_stats():
        try:
            n = seed_history(days=2, interval_minutes=30)
            print(f"[seed] デモ履歴 {n} スナップショットを作成しました")
        except Exception as exc:  # noqa: BLE001
            print(f"[seed] 失敗: {exc}")
    await poller.start()
    print(f"[x-trends] provider={settings.resolved_provider()} "
          f"watch={poller.watch} interval={settings.poll_interval}min")
    yield
    await poller.stop()


app = FastAPI(
    title="X Trends Dashboard API",
    version=APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# 認証（ACCESS_TOKEN を設定したときだけ有効）
# --------------------------------------------------------------------------- #

def require_token(x_access_token: str | None = Header(default=None)) -> None:
    if not settings.access_token:
        return
    if x_access_token != settings.access_token:
        raise HTTPException(status_code=401, detail="X-Access-Token が不正です")


# --------------------------------------------------------------------------- #
# ヘルパ
# --------------------------------------------------------------------------- #

def _loc_or_404(woeid: int):
    loc = BY_WOEID.get(woeid)
    if not loc:
        raise HTTPException(status_code=404, detail=f"未知の WOEID: {woeid}")
    return loc


def _sparkline(woeid: int, name: str, hours: int = 24) -> list[dict]:
    hist = db.trend_history(woeid, name, hours=hours)
    return [{"ts": h["ts"], "rank": h["rank"], "count": h["tweet_count"]} for h in hist]


def _fmt_location(woeid: int) -> dict:
    loc = BY_WOEID.get(woeid)
    return location_to_dict(loc) if loc else {"woeid": woeid, "name": str(woeid),
                                              "name_ja": str(woeid), "place_type": "town",
                                              "place_type_ja": "都市", "country": "?",
                                              "country_ja": "?", "region": "other"}


def _enrich(woeid: int, snap: dict, prev: dict | None, spark_hours: int = 24) -> list[dict]:
    """ランク変動・初出・勢い・他地点での流行を付与する。"""
    prev_ranks: dict[str, int] = (prev or {}).get("ranks", {})
    # 他地点でも同時に流行しているか
    cross: dict[str, list[int]] = defaultdict(list)
    for other in poller.watch:
        if other == woeid:
            continue
        osnap = db.latest_snapshot(other)
        if not osnap:
            continue
        for t in osnap["trends"][:20]:
            cross[t["name"].lower()].append(other)

    out: list[dict] = []
    for t in snap["trends"]:
        name = t["name"]
        key = name.lower()
        rank = t["rank"]
        prev_rank = prev_ranks.get(key)
        if prev_rank is None:
            change = "new"
            delta = None
        else:
            delta = prev_rank - rank          # 正 = 上昇
            change = "up" if delta > 0 else ("down" if delta < 0 else "same")

        spark = _sparkline(woeid, name, hours=spark_hours)
        counts = [p["count"] for p in spark if p["count"]]
        avg = sum(counts) / len(counts) if counts else None
        cur = t["tweet_count"]
        momentum = None
        if avg and cur:
            momentum = round((cur - avg) / avg * 100, 1)

        fs = db.first_seen(woeid, name)
        out.append({
            "name": name,
            "rank": rank,
            "tweet_count": cur,
            "category": t.get("category") or classify(name),
            "category_meta": category_meta(t.get("category") or classify(name)),
            "change": change,
            "rank_delta": delta,
            "prev_rank": prev_rank,
            "first_seen_ts": fs,
            "age_minutes": (int((snap["ts"] - fs) / 60) if fs else None),
            "momentum_pct": momentum,
            "avg_count_24h": int(avg) if avg else None,
            "sparkline": spark,
            "also_trending_in": cross.get(key, []),
            "url": f"https://x.com/search?q={_quote(name)}&src=trend_click",
        })
    return out


def _quote(text: str) -> str:
    from urllib.parse import quote
    return quote(text, safe="")


# --------------------------------------------------------------------------- #
# 基本
# --------------------------------------------------------------------------- #

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": APP_VERSION,
        "time": datetime.now(timezone.utc).isoformat(),
        "provider": settings.resolved_provider(),
    }


@app.get("/api/config", dependencies=[Depends(require_token)])
async def config():
    return {
        **settings.public_dict(),
        "default_woeids": DEFAULT_WOEIDS,
        "categories": all_categories(),
        "watch": poller.watch,
    }


@app.get("/api/locations", dependencies=[Depends(require_token)])
async def locations(
    q: str | None = Query(default=None, description="あいまい検索"),
    region: str | None = None,
):
    if q:
        return {"results": search_locations(q, limit=20)}
    groups = grouped_locations()
    if region:
        groups = [g for g in groups if g["region"] == region]
    stats = {s["woeid"]: s for s in db.all_locations_stats()}
    for g in groups:
        for loc in g["locations"]:
            st = stats.get(loc["woeid"])
            loc["has_data"] = bool(st and st["snapshots"])
            loc["last_ts"] = st["last_ts"] if st else None
    return {"groups": groups, "total": sum(len(g["locations"]) for g in groups)}


# --------------------------------------------------------------------------- #
# トレンド本体
# --------------------------------------------------------------------------- #

@app.get("/api/trends/{woeid}", dependencies=[Depends(require_token)])
async def trends(
    woeid: int,
    refresh: bool = Query(default=False, description="true でオンデマンド再取得"),
    provider: str | None = Query(default=None, description="official|twitterapiio|demo"),
    hours: int = Query(default=24, ge=1, le=168, description="スパークラインの時間幅"),
):
    _loc_or_404(woeid)

    if refresh:
        try:
            if (provider or settings.resolved_provider()) == "demo":
                data = fetch_demo(woeid)
                used = "demo"
            else:
                data, used = await fetch_trends(woeid, provider)
            db.save_snapshot(woeid, data, provider=used, source="api")
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"取得失敗: {exc}") from exc

    snap = db.latest_snapshot(woeid)
    if not snap:
        # 履歴が空なら、デモデータで即座に埋めて返す（初回体験を良くする）
        data = fetch_demo(woeid)
        db.save_snapshot(woeid, data, provider="demo", source="api")
        snap = db.latest_snapshot(woeid)
    if not snap:
        raise HTTPException(status_code=504, detail="データがありません")

    prev = db.previous_snapshot(woeid, snap["ts"])
    items = _enrich(woeid, snap, prev, spark_hours=hours)

    return {
        "location": _fmt_location(woeid),
        "fetched_at": snap["fetched_at"],
        "ts": snap["ts"],
        "age_seconds": int(time.time() - snap["ts"]),
        "provider": snap["provider"] or settings.resolved_provider(),
        "source": snap["source"],
        "previous_ts": prev["ts"] if prev else None,
        "count": len(items),
        "trends": items,
    }


@app.get("/api/trends/{woeid}/history", dependencies=[Depends(require_token)])
async def trend_history(woeid: int, name: str = Query(..., min_length=1),
                        hours: int = Query(default=24, ge=1, le=336)):
    _loc_or_404(woeid)
    hist = db.trend_history(woeid, name, hours=hours)
    counts = [h["tweet_count"] for h in hist if h["tweet_count"] is not None]
    ranks = [h["rank"] for h in hist]
    return {
        "name": name,
        "woeid": woeid,
        "hours": hours,
        "points": [{"ts": h["ts"], "rank": h["rank"], "count": h["tweet_count"],
                    "fetched_at": h["fetched_at"]} for h in hist],
        "summary": {
            "appearances": len(hist),
            "best_rank": min(ranks) if ranks else None,
            "worst_rank": max(ranks) if ranks else None,
            "max_count": max(counts) if counts else None,
            "min_count": min(counts) if counts else None,
            "avg_count": int(sum(counts) / len(counts)) if counts else None,
            "first_seen": db.first_seen(woeid, name),
        },
        "category": category_meta(classify(name)),
    }


@app.get("/api/trends/{woeid}/timeline", dependencies=[Depends(require_token)])
async def timeline(woeid: int, hours: int = Query(default=24, ge=1, le=168), top: int = Query(default=10, ge=1, le=50)):
    _loc_or_404(woeid)
    rows = db.timeline(woeid, hours=hours, bucket_minutes=60)
    return {
        "location": _fmt_location(woeid),
        "hours": hours,
        "snapshots": [
            {"ts": r["ts"], "fetched_at": r["fetched_at"],
             "top": [{"name": t["name"], "rank": t["rank"],
                      "tweet_count": t["tweet_count"],
                      "category": t["category"]} for t in r["top"][:top]]}
            for r in rows
        ],
    }


@app.get("/api/trends/{woeid}/top", dependencies=[Depends(require_token)])
async def top_trends(woeid: int, hours: int = Query(default=24, ge=1, le=336), limit: int = Query(default=20, ge=1, le=100)):
    """期間内に「長く・高く」出ていたトレンドのランキング。"""
    _loc_or_404(woeid)
    since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
    conn = db._connect()
    rows = conn.execute(
        """
        SELECT e.name AS name, e.category AS category,
               COUNT(*) AS appearances,
               MIN(e.rank) AS best_rank,
               ROUND(AVG(e.rank),1) AS avg_rank,
               MAX(e.tweet_count) AS max_count,
               ROUND(AVG(e.tweet_count),0) AS avg_count,
               MIN(s.ts) AS first_ts, MAX(s.ts) AS last_ts
        FROM trend_entries e JOIN snapshots s ON s.id=e.snapshot_id
        WHERE e.woeid=? AND s.ts>=?
        GROUP BY e.name_lower
        ORDER BY appearances DESC, avg_rank ASC
        LIMIT ?
        """,
        (woeid, since, limit),
    ).fetchall()
    total_snaps = conn.execute(
        "SELECT COUNT(*) AS n FROM snapshots WHERE woeid=? AND ts>=?", (woeid, since)
    ).fetchone()["n"] or 1

    items = []
    for r in rows:
        d = dict(r)
        d["category_meta"] = category_meta(d.get("category") or "other")
        d["persistence"] = round(d["appearances"] / total_snaps * 100, 1)
        d["url"] = f"https://x.com/search?q={_quote(d['name'])}&src=trend_click"
        items.append(d)
    return {"location": _fmt_location(woeid), "hours": hours,
            "snapshots": total_snaps, "items": items}


@app.get("/api/trends/{woeid}/categories", dependencies=[Depends(require_token)])
async def categories(woeid: int):
    _loc_or_404(woeid)
    snap = db.latest_snapshot(woeid)
    if not snap:
        return {"location": _fmt_location(woeid), "items": []}
    agg: dict[str, dict] = {}
    for t in snap["trends"]:
        cid = t["category"]
        a = agg.setdefault(cid, {"category": cid, "meta": category_meta(cid),
                                 "count": 0, "total_count": 0, "best_rank": 999,
                                 "top": None})
        a["count"] += 1
        a["total_count"] += t["tweet_count"] or 0
        if t["rank"] < a["best_rank"]:
            a["best_rank"] = t["rank"]
            a["top"] = t["name"]
    items = sorted(agg.values(), key=lambda x: -x["total_count"])
    return {"location": _fmt_location(woeid), "items": items}


# --------------------------------------------------------------------------- #
# 比較 / 検索
# --------------------------------------------------------------------------- #

@app.get("/api/compare", dependencies=[Depends(require_token)])
async def compare(
    woeids: str = Query(default="1,23424856,23424977,44418", description="カンマ区切り"),
    limit: int = Query(default=10, ge=1, le=30),
):
    ids: list[int] = []
    for part in woeids.split(","):
        part = part.strip()
        if part.isdigit() and int(part) not in ids:
            ids.append(int(part))
    if not ids:
        raise HTTPException(status_code=400, detail="woeids が空です")

    columns = []
    name_sets: dict[str, set[int]] = defaultdict(set)
    for w in ids:
        snap = db.latest_snapshot(w)
        items = snap["trends"][:limit] if snap else []
        for t in items:
            name_sets[t["name"].lower()].add(w)
        columns.append({
            "location": _fmt_location(w),
            "ts": snap["ts"] if snap else None,
            "age_seconds": int(time.time() - snap["ts"]) if snap else None,
            "trends": [
                {"name": t["name"], "rank": t["rank"], "tweet_count": t["tweet_count"],
                 "category": t["category"],
                 "category_meta": category_meta(t["category"])}
                for t in items
            ],
        })
    shared = sorted(
        ({"name_key": k, "count": len(v), "woeids": sorted(v)}
         for k, v in name_sets.items() if len(v) > 1),
        key=lambda x: -x["count"],
    )
    return {"columns": columns, "shared": shared[:25]}


@app.get("/api/search", dependencies=[Depends(require_token)])
async def search(
    q: str = Query(min_length=1),
    woeid: int | None = None,
    hours: int = Query(default=72, ge=1, le=720),
    limit: int = Query(default=60, ge=1, le=300),
):
    rows = db.search(q, woeid=woeid, hours=hours, limit=limit)
    for r in rows:
        r["location"] = _fmt_location(r["woeid"])
        r["category_meta"] = category_meta(r.get("category") or classify(r["name"]))
        r["url"] = f"https://x.com/search?q={_quote(r['name'])}&src=trend_click"
    return {"query": q, "hours": hours, "count": len(rows), "results": rows}


@app.get("/api/stats/{woeid}", dependencies=[Depends(require_token)])
async def stats(woeid: int):
    _loc_or_404(woeid)
    return {"location": _fmt_location(woeid), **db.location_stats(woeid)}


@app.get("/api/status", dependencies=[Depends(require_token)])
async def status():
    loc_stats = {s["woeid"]: s for s in db.all_locations_stats()}
    return {
        "poller": poller.status(),
        "config": settings.public_dict(),
        "locations": [
            {**_fmt_location(w), "snapshots": loc_stats.get(w, {}).get("snapshots", 0),
             "last_ts": loc_stats.get(w, {}).get("last_ts")}
            for w in poller.watch
        ],
        "db_locations": len(loc_stats),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


# --------------------------------------------------------------------------- #
# 操作系
# --------------------------------------------------------------------------- #

@app.post("/api/refresh", dependencies=[Depends(require_token)])
async def refresh(woeid: int | None = Query(default=None)):
    """手動で今すぐ収集する。"""
    if woeid is not None:
        _loc_or_404(woeid)
        poller.set_watch([woeid])
        result = await poller.run_cycle(force=True)
        poller.set_watch(settings.resolved_watch_woeids(DEFAULT_WOEIDS))
        return {"ok": True, "result": result}
    result = await poller.run_cycle(force=True)
    return {"ok": True, "result": result}


@app.post("/api/watch", dependencies=[Depends(require_token)])
async def set_watch(payload: dict):
    woeids = payload.get("woeids") or []
    if not isinstance(woeids, list):
        raise HTTPException(status_code=400, detail="woeids は配列で指定してください")
    clean: list[int] = []
    for w in woeids:
        try:
            wi = int(w)
        except (TypeError, ValueError):
            continue
        if wi in BY_WOEID and wi not in clean:
            clean.append(wi)
    if not clean:
        raise HTTPException(status_code=400, detail="有効な WOEID がありません")
    poller.set_watch(clean)
    return {"ok": True, "watch": clean,
            "names": [BY_WOEID[w].name_ja for w in clean]}


@app.post("/api/notifications/keywords", dependencies=[Depends(require_token)])
async def set_keywords(payload: dict):
    """サーバ側通知キーワード（グローバル）。"""
    data = payload.get("keywords") or {}
    SERVER_KEYWORDS.clear()
    if isinstance(data, dict):
        for k, v in data.items():
            try:
                wi = int(k)
            except (TypeError, ValueError):
                continue
            if isinstance(v, list):
                SERVER_KEYWORDS[wi] = [str(x) for x in v if str(x).strip()]
    return {"ok": True, "keywords": SERVER_KEYWORDS}


@app.get("/api/notifications/events", dependencies=[Depends(require_token)])
async def notif_events(limit: int = Query(default=50, ge=1, le=200)):
    rows = db.recent_notif_events(limit)
    for r in rows:
        r["location"] = _fmt_location(r["woeid"])
    return {"events": rows}


@app.get("/api/export/{woeid}.csv", dependencies=[Depends(require_token)])
async def export_csv(woeid: int):
    _loc_or_404(woeid)
    snap = db.latest_snapshot(woeid)
    if not snap:
        raise HTTPException(status_code=404, detail="データがありません")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["rank", "trend", "tweet_count", "category", "url"])
    for t in snap["trends"]:
        w.writerow([t["rank"], t["name"], t["tweet_count"] or "",
                    t["category"], f"https://x.com/search?q={_quote(t['name'])}"])
    loc = BY_WOEID[woeid]
    filename = f"x-trends_{loc.name}_{datetime.now(timezone.utc):%Y%m%d%H%M}.csv"
    return Response(
        content="\ufeff" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------------- #
# 静的ファイル
# --------------------------------------------------------------------------- #

app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=False), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/favicon.svg", include_in_schema=False)
async def favicon():
    p = STATIC_DIR / "favicon.svg"
    if p.exists():
        return FileResponse(str(p))
    return Response(status_code=404)


def main() -> None:
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port,
                reload=settings.debug)


if __name__ == "__main__":
    main()
