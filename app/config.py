"""実行時設定。すべて環境変数 / .env から読む（12-factor）。"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """python-dotenv 無しの最小 .env ローダ。既にセット済みの環境変数は上書きしない。"""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on", "y"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


@dataclass
class Settings:
    # --- プロバイダ -------------------------------------------------------
    # official | twitterapiio | demo   （未指定なら自動判定）
    provider: str = os.getenv("TRENDS_PROVIDER", "").strip().lower()

    # 公式 X API v2 (pay-per-use / レガシー Pro)
    x_bearer_token: str = os.getenv("X_BEARER_TOKEN", "").strip()
    x_api_base: str = os.getenv("X_API_BASE", "https://api.x.com").rstrip("/")

    # 代替プロバイダ TwitterAPI.io
    twitterapi_key: str = os.getenv("TWITTERAPI_KEY", "").strip()
    twitterapi_base: str = os.getenv(
        "TWITTERAPI_BASE", "https://api.twitterapi.io"
    ).rstrip("/")

    # --- 収集（ポーラー） -------------------------------------------------
    # 何分間隔でトレンドを取りに行くか。X 側は概ね5分ごとに再計算される。
    poll_interval: int = _int("POLL_INTERVAL", 5)
    # 監視対象の WOEID（カンマ区切り）。空なら DEFAULT_WOEIDS を使用。
    watch_woeids: str = os.getenv("WATCH_WOEIDS", "").strip()
    # ポーラーを起動するか（false にすると API 経由のオンデマンド取得のみ）
    poller_enabled: bool = _bool("POLLER_ENABLED", True)
    # 起動時に過去のデモ履歴を埋めるか
    seed_history: bool = _bool("SEED_HISTORY", True)

    # --- ストレージ / サーバ ----------------------------------------------
    db_path: str = os.getenv("DB_PATH", str(ROOT / "data" / "trends.db"))
    history_days: int = _int("HISTORY_DAYS", 7)
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = _int("PORT", 8000)
    # 閲覧を制限したい場合に設定（空なら認証なし）
    access_token: str = os.getenv("ACCESS_TOKEN", "").strip()
    debug: bool = _bool("DEBUG", False)

    # 履歴に残す1地点あたりのスナップショット上限（自動トリム）
    max_snapshots_per_location: int = _int("MAX_SNAPSHOTS", 4000)

    def resolved_watch_woeids(self, defaults: list[int]) -> list[int]:
        if not self.watch_woeids:
            return list(defaults)
        out: list[int] = []
        for part in self.watch_woeids.replace(";", ",").split(","):
            part = part.strip()
            if part.isdigit() and int(part) not in out:
                out.append(int(part))
        return out or list(defaults)

    def resolved_provider(self) -> str:
        if self.provider:
            return self.provider
        if self.x_bearer_token:
            return "official"
        if self.twitterapi_key:
            return "twitterapiio"
        return "demo"

    def public_dict(self) -> dict:
        """フロントに返して良い情報だけ。シークレットは絶対に含めない。"""
        return {
            "provider": self.resolved_provider(),
            "poll_interval": self.poll_interval,
            "poller_enabled": self.poller_enabled,
            "history_days": self.history_days,
            "has_x_token": bool(self.x_bearer_token),
            "has_twitterapi_key": bool(self.twitterapi_key),
            "auth_required": bool(self.access_token),
        }


def _resolve_db_path(path: str) -> str:
    """
    DB パスを実際に使える形に解決する。

    Render などのPaaSは読み取り専用/一時ファイルシステムの場合があり、
    書き込めないとアプリ全体が起動不能になる。その場合は一時ディレクトリに
    フォールバックする（履歴は消えるが、サービスは生きたまま）。
    """
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = ROOT / p
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        probe = p.parent / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return str(p)
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "x-trends" / p.name
        try:
            fallback.parent.mkdir(parents=True, exist_ok=True)
            return str(fallback)
        except OSError:
            return str(p)


settings = Settings()
settings.db_path = _resolve_db_path(settings.db_path)

# デフォルト監視対象: 全世界 + 日本 + 主要都市（コストを抑えた控えめなセット）
DEFAULT_WOEIDS: list[int] = [
    1,          # Worldwide
    23424856,   # Japan
    1118370,    # Tokyo
    15015372,   # Osaka
    23424977,   # United States
    44418,      # London
]

STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
