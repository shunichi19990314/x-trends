#!/usr/bin/env python3
"""
スモークテスト: サーバを起動して主要エンドポイントを叩く。

    python scripts/smoke_test.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8123"))
BASE = f"http://{HOST}:{PORT}"

FAILED: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    mark = "✅" if cond else "❌"
    print(f"{mark} {name}" + (f"  {extra}" if extra else ""))
    if not cond:
        FAILED.append(name)


def main() -> int:
    env = {**os.environ, "PORT": str(PORT), "HOST": HOST, "TRENDS_PROVIDER": "demo",
           "SEED_HISTORY": "true", "POLL_INTERVAL": "5"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", HOST, "--port", str(PORT)],
        cwd=str(ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    logs: list[str] = []
    try:
        # 起動待ち
        ready = False
        for _ in range(120):
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                print("サーバが起動しませんでした:\n", out[-3000:])
                return 1
            try:
                r = httpx.get(f"{BASE}/api/health", timeout=2)
                if r.status_code == 200:
                    ready = True
                    break
            except Exception:
                pass
            time.sleep(0.5)
        check("サーバ起動", ready)
        if not ready:
            return 1

        with httpx.Client(base_url=BASE, timeout=30) as c:
            r = c.get("/api/health")
            check("GET /api/health", r.status_code == 200, r.text[:80])

            r = c.get("/api/config")
            cfg = r.json()
            check("GET /api/config", r.status_code == 200 and "categories" in cfg,
                  f"provider={cfg.get('provider')} cats={len(cfg.get('categories', []))}")

            r = c.get("/api/locations")
            data = r.json()
            total = data.get("total", 0)
            check("GET /api/locations", r.status_code == 200 and total > 50, f"{total} 地域")

            r = c.get("/api/locations", params={"q": "東京"})
            res = r.json().get("results", [])
            check("GET /api/locations?q=東京", bool(res) and res[0]["woeid"] == 1118370,
                  json.dumps(res[0], ensure_ascii=False) if res else "empty")

            r = c.get("/api/trends/23424856", params={"hours": 24})
            t = r.json()
            check("GET /api/trends/23424856 (日本)",
                  r.status_code == 200 and len(t.get("trends", [])) >= 20,
                  f"{len(t.get('trends', []))}件 / source={t.get('source')}")
            if t.get("trends"):
                first = t["trends"][0]
                keys = {"name", "rank", "tweet_count", "category", "change", "sparkline", "url"}
                check("トレンド項目の形", keys.issubset(first.keys()),
                      ",".join(sorted(first.keys())))
                check("スパークラインが埋まっている", len(first["sparkline"]) >= 2,
                      f"{len(first['sparkline'])}点")

            r = c.get("/api/trends/1", params={"hours": 24})
            check("GET /api/trends/1 (全世界)", r.status_code == 200)

            name = t["trends"][0]["name"]
            r = c.get("/api/trends/23424856/history", params={"name": name, "hours": 48})
            h = r.json()
            check("GET .../history", r.status_code == 200 and len(h.get("points", [])) >= 2,
                  f"{len(h.get('points', []))}点 best_rank={h.get('summary', {}).get('best_rank')}")

            r = c.get("/api/trends/23424856/timeline", params={"hours": 24})
            check("GET .../timeline", r.status_code == 200 and len(r.json().get("snapshots", [])) >= 2,
                  f"{len(r.json().get('snapshots', []))}snap")

            r = c.get("/api/trends/23424856/top", params={"hours": 24, "limit": 10})
            top = r.json()
            check("GET .../top", r.status_code == 200 and len(top.get("items", [])) > 0,
                  f"{len(top.get('items', []))}件 / {top['items'][0]['name'] if top.get('items') else ''}")

            r = c.get("/api/trends/23424856/categories")
            check("GET .../categories", r.status_code == 200 and len(r.json().get("items", [])) > 0)

            r = c.get("/api/compare", params={"woeids": "1,23424856,1118370,23424977"})
            cmp_ = r.json()
            check("GET /api/compare", r.status_code == 200 and len(cmp_.get("columns", [])) == 4,
                  f"shared={len(cmp_.get('shared', []))}")

            q = t["trends"][3]["name"]
            r = c.get("/api/search", params={"q": q[:6], "hours": 48})
            check("GET /api/search", r.status_code == 200, f"{len(r.json().get('results', []))}件")

            r = c.get("/api/status")
            st = r.json()
            check("GET /api/status", r.status_code == 200 and "poller" in st,
                  f"watch={st['poller']['watch_names']}")

            r = c.post("/api/watch", json={"woeids": [1, 23424856, 1118370]})
            check("POST /api/watch", r.status_code == 200, r.text[:80])

            r = c.post("/api/refresh")
            check("POST /api/refresh", r.status_code == 200, json.dumps(r.json(), ensure_ascii=False)[:120])

            r = c.post("/api/notifications/keywords", json={"keywords": {"23424856": ["地震"]}})
            check("POST /api/notifications/keywords", r.status_code == 200)

            r = c.get("/api/export/23424856.csv")
            check("GET /api/export/23424856.csv",
                  r.status_code == 200 and "trend" in r.text.splitlines()[0],
                  f"{len(r.content)} bytes")

            r = c.get("/")
            check("GET / (index.html)", r.status_code == 200 and "X Trends" in r.text)
            for path in ["/static/style.css", "/static/js/app.js", "/static/js/api.js",
                         "/static/js/views.js", "/static/js/board.js", "/static/js/charts.js",
                         "/static/js/panels.js", "/static/js/state.js", "/static/js/util.js",
                         "/static/js/demo.js", "/favicon.svg", "/static/manifest.webmanifest"]:
                r = c.get(path)
                check(f"GET {path}", r.status_code == 200 and len(r.content) > 100,
                      f"{len(r.content)} bytes")

            r = c.get("/docs")
            check("GET /docs", r.status_code == 200)

            r = c.get("/api/trends/99999999")
            check("未知WOEIDは404", r.status_code == 404, r.text[:60])

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()

    print()
    if FAILED:
        print(f"❌ {len(FAILED)} 件失敗: {FAILED}")
        return 1
    print("🎉 全テスト合格")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
