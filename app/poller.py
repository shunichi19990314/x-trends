"""
バックグラウンドのトレンド収集ループ。

  - 監視対象の地点を順番にポーリングして SQLite に保存
  - 1リクエストごとに少し待つ（レート制限 & 課金対策）
  - 公式 API のレート制限は 75リクエスト / 15分（アプリ全体で共有）
  - 通知キーワードに一致したら notif_events に記録
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import httpx

from . import db
from .config import DEFAULT_WOEIDS, settings
from .locations import BY_WOEID, get_location
from .providers import ProviderError, fetch_demo, fetch_trends

# 通知キーワード（DB ではなくメモリ + localStorage 側の管理が基本だが、
# サーバ側通知も欲しい場合はここに足す）
SERVER_KEYWORDS: dict[int, list[str]] = {}


class Poller:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.running = False
        self.watch: list[int] = settings.resolved_watch_woeids(DEFAULT_WOEIDS)
        self.last_run: int | None = None
        self.last_error: str | None = None
        self.cycle_count = 0
        self.api_calls = 0
        self.stopped = asyncio.Event()

    # ------------------------------------------------------------------ #
    def set_watch(self, woeids: list[int]) -> None:
        self.watch = [w for w in woeids if isinstance(w, int)]

    async def start(self) -> None:
        if not settings.poller_enabled or self.task:
            return
        self.running = True
        self.stopped.clear()
        self.task = asyncio.create_task(self._loop(), name="trend-poller")

    async def stop(self) -> None:
        self.running = False
        self.stopped.set()
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):
                pass
        self.task = None

    # ------------------------------------------------------------------ #
    async def _loop(self) -> None:
        # 起動直後に1回だけ実行し、以降は interval ごとに回す
        while self.running:
            try:
                await self.run_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - ループは絶対に殺さない
                self.last_error = f"{type(exc).__name__}: {exc}"
            try:
                await asyncio.wait_for(
                    self.stopped.wait(), timeout=max(15, settings.poll_interval * 60)
                )
                break  # stopped がセットされた
            except asyncio.TimeoutError:
                continue

    async def run_cycle(self, force: bool = False) -> dict:
        """1サイクル実行。結果サマリを返す。"""
        provider = settings.resolved_provider()
        ok, failed = [], []
        async with httpx.AsyncClient(timeout=25) as client:
            for woeid in self.watch:
                try:
                    if provider == "demo":
                        trends = fetch_demo(woeid)
                        used = "demo"
                    else:
                        trends, used = await fetch_trends(woeid, provider, client)
                        self.api_calls += 1
                    if not trends:
                        failed.append({"woeid": woeid, "error": "トレンドが空でした"})
                        continue
                    ts = int(time.time())
                    db.save_snapshot(woeid, trends, provider=used, source="api", ts=ts)
                    self._check_notifications(woeid, trends, ts)
                    ok.append(woeid)
                except ProviderError as exc:
                    self.last_error = str(exc)
                    failed.append({"woeid": woeid, "error": str(exc)})
                except Exception as exc:  # noqa: BLE001
                    self.last_error = f"{type(exc).__name__}: {exc}"
                    failed.append({"woeid": woeid, "error": str(exc)})
                # バーストを避ける
                await asyncio.sleep(0.6 if provider == "demo" else 1.2)
        self.last_run = int(time.time())
        self.cycle_count += 1
        return {"ok": ok, "failed": failed, "provider": provider}

    # ------------------------------------------------------------------ #
    def _check_notifications(self, woeid: int, trends: list[dict], ts: int) -> None:
        keywords = SERVER_KEYWORDS.get(woeid, [])
        if not keywords:
            return
        for kw in keywords:
            kw_lower = kw.lower()
            for t in trends:
                name = t.get("name", "")
                if kw_lower in name.lower():
                    db.log_notif_event(
                        woeid, kw, name, t.get("rank"), t.get("tweet_count"), ts
                    )
                    break

    # ------------------------------------------------------------------ #
    def status(self) -> dict:
        loc_names = []
        for w in self.watch:
            loc = get_location(w)
            loc_names.append(loc.name_ja if loc else str(w))
        return {
            "enabled": settings.poller_enabled,
            "running": self.running and self.task is not None,
            "interval_minutes": settings.poll_interval,
            "watch_woeids": self.watch,
            "watch_names": loc_names,
            "last_run": self.last_run,
            "last_run_iso": (
                datetime.fromtimestamp(self.last_run, tz=timezone.utc).isoformat()
                if self.last_run else None
            ),
            "last_error": self.last_error,
            "cycles": self.cycle_count,
            "api_calls": self.api_calls,
            "provider": settings.resolved_provider(),
        }


poller = Poller()


def seed_history(days: int = 2, interval_minutes: int = 30) -> int:
    """
    デモ履歴を埋める（初回起動時 / SEED_HISTORY=true のとき）。
    実 API では過去データを取得できないので、これは demo プロバイダ限定。
    """
    if settings.resolved_provider() != "demo":
        return 0
    now = int(time.time())
    start = now - days * 24 * 3600
    step = interval_minutes * 60
    total = 0
    for woeid in poller.watch:
        ts = start - (start % step)
        while ts <= now:
            trends = fetch_demo(woeid, ts=ts)
            if db.save_snapshot(woeid, trends, provider="demo", source="seed", ts=ts):
                total += 1
            ts += step
    return total
