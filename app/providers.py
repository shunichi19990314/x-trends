"""
トレンド取得プロバイダ。

  official     X API v2   GET /2/trends/by/woeid/{woeid}   (Bearer Token)
  twitterapiio TwitterAPI.io GET /twitter/trends?woeid=...  (X-API-Key)  ※代替
  demo         APIなしで動く合成データ（開発・デモ・オフライン用）

公式エンドポイントのレスポンス形:
    {"data": [{"trend_name": "...", "tweet_count": 12345}, ...]}
  * tweet_count は欠損することが多い（仕様）。
  * 2026年時点で X API は pay-per-use。Trends は 1リクエスト $0.010 前後。
    （console.x.com の料金表が最終的な正）
"""

from __future__ import annotations

import hashlib
import math
import random
import time
from datetime import datetime, timezone

import httpx

from . import demo_data
from .demo_data import GLOBAL_DEDUPED
from .config import settings

USER_AGENT = "x-trends-dashboard/1.0 (+local)"


class ProviderError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# 共通整形
# --------------------------------------------------------------------------- #

def _normalize(raw: list[dict]) -> list[dict]:
    """各プロバイダのレスポンスを {"name", "tweet_count"} 形式に揃える。"""
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = (
            item.get("trend_name")
            or item.get("name")
            or item.get("topic")
            or item.get("query")
        )
        if not name:
            continue
        count = item.get("tweet_count", item.get("tweet_volume"))
        try:
            count = int(count) if count is not None else None
        except (TypeError, ValueError):
            count = None
        out.append({"name": str(name).strip(), "tweet_count": count})
    return out


# --------------------------------------------------------------------------- #
# 公式 X API v2
# --------------------------------------------------------------------------- #

async def fetch_official(woeid: int, client: httpx.AsyncClient | None = None) -> list[dict]:
    url = f"{settings.x_api_base}/2/trends/by/woeid/{woeid}"
    headers = {
        "Authorization": f"Bearer {settings.x_bearer_token}",
        "User-Agent": USER_AGENT,
    }
    # trend.fields を付けると tweet_count を明示要求できる（未対応環境でも無害）
    params = {"trend.fields": "tweet_count"}
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=20)
    try:
        resp = await client.get(url, headers=headers, params=params)
    finally:
        if own_client:
            await client.aclose()

    if resp.status_code == 401:
        raise ProviderError(
            "401 Unauthorized: X_BEARER_TOKEN が無効または期限切れです。"
            "console.x.com で Bearer Token を再発行してください"
        )
    if resp.status_code == 403:
        raise ProviderError(
            "403 Forbidden: このアカウントでは Trends エンドポイントを呼び出せません。"
            "クレジット残高 / プランの権限を確認してください（2026年現在 X API は pay-per-use、"
            "Trends は 1リクエスト単位で課金されます）。代替として TWITTERAPI_KEY を設定すると"
            "プロバイダを切り替えられます"
        )
    if resp.status_code == 429:
        retry = resp.headers.get("x-rate-limit-reset")
        raise ProviderError(
            f"429 レート制限に達しました（Trends は 75リクエスト/15分）。リセット: {retry or '不明'}"
        )
    if resp.status_code >= 400:
        raise ProviderError(f"X API エラー {resp.status_code}: {resp.text[:300]}")

    payload = resp.json()
    if isinstance(payload, dict):
        data = payload.get("data")
        if data is None:
            data = payload.get("trends", [])
    elif isinstance(payload, list):
        # v1.1 互換形 [{"trends": [...], "as_of": ...}] で返る実装もある
        if payload and isinstance(payload[0], dict) and isinstance(payload[0].get("trends"), list):
            data = payload[0]["trends"]
        else:
            data = payload
    else:
        data = []
    return _normalize(data)


# --------------------------------------------------------------------------- #
# 代替プロバイダ: TwitterAPI.io
# --------------------------------------------------------------------------- #

async def fetch_twitterapiio(woeid: int, client: httpx.AsyncClient | None = None) -> list[dict]:
    url = f"{settings.twitterapi_base}/twitter/trends"
    headers = {"X-API-Key": settings.twitterapi_key, "User-Agent": USER_AGENT}
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=20)
    try:
        resp = await client.get(url, headers=headers, params={"woeid": woeid})
    finally:
        if own_client:
            await client.aclose()
    if resp.status_code >= 400:
        raise ProviderError(f"TwitterAPI.io エラー {resp.status_code}: {resp.text[:300]}")
    payload = resp.json()
    if isinstance(payload, dict):
        data = payload.get("trends") or payload.get("data") or []
    else:
        data = payload
    return _normalize(data)


# --------------------------------------------------------------------------- #
# デモ（合成データ）
# --------------------------------------------------------------------------- #

def _hash_int(*parts) -> int:
    key = "|".join(str(p) for p in parts)
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)


def fetch_demo(woeid: int, ts: int | None = None, count: int = 50) -> list[dict]:
    """
    時刻から決定論的にトレンドを生成する。
    同じ ts なら同じ結果 → 履歴をあとから埋めても整合する。

    スコアは3層の合計で作る（地域比較で「共通して流行っている話題」が生まれるように）:
      global  … 全世界で同時に流れる話題（どの地点でも共通）
      local   … そのロケール特有の話題（日本なら日本語トレンド）
      town    … その地点だけのローカルな揺らぎ
    """
    ts = ts if ts is not None else int(time.time())
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    # 5分単位で値を変える（X のトレンド更新周期と同じ）
    bucket = ts - (ts % 300)
    day = dt.strftime("%Y-%m-%d")

    def rng_of(*parts) -> random.Random:
        return random.Random(_hash_int(*parts))

    global_rng = rng_of("global", bucket)          # 全地点共通 → 同じ話題が各地で流行る
    global_day = rng_of("global", "day", day)
    local_rng = rng_of("locale", woeid, bucket)
    local_day = rng_of("locale", woeid, day)
    town_rng = rng_of("town", woeid, bucket)
    town_day = rng_of("town", woeid, day)

    locale = demo_data.locale_for(woeid)
    is_world = woeid == 1

    # 時間帯ごとの「旬」バイアス（JST 基準）
    jst_hour = (dt.hour + 9) % 24
    slot = demo_data.time_slot(jst_hour)
    weekend = dt.weekday() >= 5

    def score(item: dict, rng: random.Random, day_rng: random.Random, weight: float) -> float:
        base = item["base"] * weight * rng.uniform(0.55, 1.9)
        if item.get("slot") == slot:
            base *= rng.uniform(2.4, 6.0)
        if item.get("daily") and day_rng.random() < 0.14:
            base *= rng.uniform(3.0, 9.0)          # その日のバズ
        if item.get("weekly") and weekend:
            base *= 1.8
        return base

    scored: list[tuple[float, dict]] = []
    seen: set[str] = set()

    # 全世界トレンドはグローバル層が支配的
    g_weight, l_weight, t_weight = (1.0, 0.0, 0.15) if is_world else (0.42, 0.62, 0.28)

    for item in GLOBAL_DEDUPED:
        name = item["name"]
        if name in seen:
            continue
        seen.add(name)
        scored.append((score(item, global_rng, global_day, g_weight), item))

    for item in demo_data.build_pool(locale):
        name = item["name"]
        if name in seen:
            continue
        seen.add(name)
        s = score(item, local_rng, local_day, l_weight)
        s += score(item, town_rng, town_day, t_weight)
        scored.append((s, item))

    scored.sort(key=lambda x: -x[0])
    top = scored[:count]

    trend_max = top[0][0] if top else 1.0
    trends = []
    for i, (sc, item) in enumerate(top, start=1):
        ratio = sc / trend_max
        tweet_count = max(
            300,
            int(math.pow(ratio, 1.6) * town_rng.uniform(180_000, 520_000)),
        )
        if item.get("count") == "none":
            tweet_count = None
        trends.append({
            "name": item["name"],
            "tweet_count": tweet_count,
            "rank": i,
        })
    return trends


# --------------------------------------------------------------------------- #
# ディスパッチ
# --------------------------------------------------------------------------- #

async def fetch_trends(woeid: int, provider: str | None = None,
                       client: httpx.AsyncClient | None = None) -> tuple[list[dict], str]:
    """(trends, provider_used) を返す。失敗時は ProviderError。"""
    provider = provider or settings.resolved_provider()
    if provider == "official":
        if not settings.x_bearer_token:
            raise ProviderError("X_BEARER_TOKEN が未設定です")
        return await fetch_official(woeid, client), "official"
    if provider == "twitterapiio":
        if not settings.twitterapi_key:
            raise ProviderError("TWITTERAPI_KEY が未設定です")
        return await fetch_twitterapiio(woeid, client), "twitterapiio"
    if provider == "demo":
        return fetch_demo(woeid), "demo"
    raise ProviderError(f"不明なプロバイダ: {provider}")
