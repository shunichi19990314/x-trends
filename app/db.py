"""
SQLite によるトレンド履歴の永続化。

X API は「今のスナップショット」しか返さないので、
時系列グラフ・急上昇検知・比較機能は自前で履歴を貯める必要がある。

テーブル:
  snapshots      1行 = ある地点のある時刻の取得結果
  trend_entries  1行 = そのスナップショット内の1トレンド
  notif_events   通知を発火した記録（重複通知防止）
  meta           キーバリュー（最終取得時刻など）
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .classify import classify
from .config import settings

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    woeid       INTEGER NOT NULL,
    fetched_at  TEXT    NOT NULL,
    ts          INTEGER NOT NULL,
    provider    TEXT    NOT NULL DEFAULT '',
    source      TEXT    NOT NULL DEFAULT 'api',   -- api | cache | demo | seed
    UNIQUE (woeid, ts)
);
CREATE INDEX IF NOT EXISTS idx_snap_woeid_ts ON snapshots (woeid, ts DESC);

CREATE TABLE IF NOT EXISTS trend_entries (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    woeid       INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    name_lower  TEXT    NOT NULL,
    rank        INTEGER NOT NULL,
    tweet_count INTEGER,
    category    TEXT    NOT NULL DEFAULT 'other',
    PRIMARY KEY (snapshot_id, rank)
);
CREATE INDEX IF NOT EXISTS idx_entry_lookup ON trend_entries (woeid, name_lower);

CREATE TABLE IF NOT EXISTS notif_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    woeid       INTEGER NOT NULL,
    keyword     TEXT    NOT NULL,
    matched     TEXT    NOT NULL,
    rank        INTEGER,
    tweet_count INTEGER,
    ts          INTEGER NOT NULL,
    created_at  TEXT    NOT NULL,
    UNIQUE (woeid, keyword, matched, ts)
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _connect() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(settings.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        _local.conn = conn
    return conn


@contextmanager
def tx():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    with tx() as conn:
        conn.executescript(SCHEMA)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_entry_ts ON trend_entries (snapshot_id)"
        )


# --------------------------------------------------------------------------- #
# 書き込み
# --------------------------------------------------------------------------- #

def save_snapshot(
    woeid: int,
    trends: list[dict],
    provider: str = "",
    source: str = "api",
    ts: int | None = None,
) -> int | None:
    """トレンド一覧を保存し、snapshot_id を返す。既存があればスキップ。"""
    ts = ts if ts is not None else int(time.time())
    # X のトレンドは数分ごとにしか変わらないため、短時間の重複取得は無視する
    with tx() as conn:
        row = conn.execute(
            "SELECT id FROM snapshots WHERE woeid=? AND ts=?", (woeid, ts)
        ).fetchone()
        if row:
            return None
        fetched_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        cur = conn.execute(
            "INSERT INTO snapshots (woeid, fetched_at, ts, provider, source) "
            "VALUES (?,?,?,?,?)",
            (woeid, fetched_at, ts, provider, source),
        )
        snap_id = int(cur.lastrowid)
        payload = []
        for i, t in enumerate(trends, start=1):
            name = (t.get("name") or t.get("trend_name") or "").strip()
            if not name:
                continue
            count = t.get("tweet_count")
            try:
                count = int(count) if count is not None else None
            except (TypeError, ValueError):
                count = None
            payload.append((
                snap_id, woeid, name, name.lower(), i, count,
                t.get("category") or classify(name),
            ))
        conn.executemany(
            "INSERT OR IGNORE INTO trend_entries "
            "(snapshot_id, woeid, name, name_lower, rank, tweet_count, category) "
            "VALUES (?,?,?,?,?,?,?)",
            payload,
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (f"last_fetch:{woeid}", str(ts)),
        )
    trim(woeid)
    return snap_id


def trim(woeid: int) -> None:
    """古い履歴を削ってDB肥大化を防ぐ（日数超過 or 件数超過）。"""
    limit = max(50, settings.max_snapshots_per_location)
    cutoff_ts = int(
        (datetime.now(timezone.utc) - timedelta(days=settings.history_days)).timestamp()
    )
    with tx() as conn:
        rows = conn.execute(
            "SELECT id, ts FROM snapshots WHERE woeid=? ORDER BY ts DESC", (woeid,)
        ).fetchall()
        doomed: list[int] = []
        for i, r in enumerate(rows):
            if i >= limit or r["ts"] < cutoff_ts:
                doomed.append(r["id"])
        if not doomed:
            return
        conn.executemany(
            "DELETE FROM trend_entries WHERE snapshot_id=?", [(i,) for i in doomed]
        )
        conn.executemany("DELETE FROM snapshots WHERE id=?", [(i,) for i in doomed])


# --------------------------------------------------------------------------- #
# 読み取り
# --------------------------------------------------------------------------- #

def latest_snapshot(woeid: int) -> dict | None:
    with tx() as conn:
        snap = conn.execute(
            "SELECT * FROM snapshots WHERE woeid=? ORDER BY ts DESC LIMIT 1", (woeid,)
        ).fetchone()
        if not snap:
            return None
        entries = conn.execute(
            "SELECT name, rank, tweet_count, category FROM trend_entries "
            "WHERE snapshot_id=? ORDER BY rank", (snap["id"],)
        ).fetchall()
        return {
            "id": snap["id"],
            "woeid": woeid,
            "fetched_at": snap["fetched_at"],
            "ts": snap["ts"],
            "provider": snap["provider"],
            "source": snap["source"],
            "trends": [dict(e) for e in entries],
        }


def previous_snapshot(woeid: int, before_ts: int) -> dict | None:
    with tx() as conn:
        snap = conn.execute(
            "SELECT id FROM snapshots WHERE woeid=? AND ts<? ORDER BY ts DESC LIMIT 1",
            (woeid, before_ts),
        ).fetchone()
        if not snap:
            return None
        entries = conn.execute(
            "SELECT name, rank, tweet_count FROM trend_entries WHERE snapshot_id=?",
            (snap["id"],),
        ).fetchall()
        return {"ts": snap["id"], "ranks": {e["name"].lower(): e["rank"] for e in entries}}


def trend_history(woeid: int, name: str, hours: int = 24) -> list[dict]:
    """特定トレンドの出現履歴（時系列）。"""
    since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
    name_lower = name.strip().lower()
    with tx() as conn:
        rows = conn.execute(
            """
            SELECT s.ts AS ts, s.fetched_at AS fetched_at, e.rank AS rank,
                   e.tweet_count AS tweet_count, e.category AS category
            FROM trend_entries e
            JOIN snapshots s ON s.id = e.snapshot_id
            WHERE e.woeid = ? AND e.name_lower = ? AND s.ts >= ?
            ORDER BY s.ts ASC
            """,
            (woeid, name_lower, since),
        ).fetchall()
    return [dict(r) for r in rows]


def first_seen(woeid: int, name: str) -> int | None:
    name_lower = name.strip().lower()
    with tx() as conn:
        row = conn.execute(
            "SELECT MIN(s.ts) AS first_ts FROM trend_entries e "
            "JOIN snapshots s ON s.id=e.snapshot_id "
            "WHERE e.woeid=? AND e.name_lower=?",
            (woeid, name_lower),
        ).fetchone()
    return row["first_ts"] if row and row["first_ts"] else None


def timeline(woeid: int, hours: int = 24, bucket_minutes: int = 60) -> list[dict]:
    """スナップショットごとの上位トレンドを並べたタイムライン。"""
    since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
    with tx() as conn:
        snaps = conn.execute(
            "SELECT id, ts, fetched_at FROM snapshots WHERE woeid=? AND ts>=? "
            "ORDER BY ts ASC",
            (woeid, since),
        ).fetchall()
        if not snaps:
            return []
        ids = [s["id"] for s in snaps]
        marks = ",".join("?" * len(ids))
        entries = conn.execute(
            f"SELECT snapshot_id, name, rank, tweet_count, category FROM trend_entries "
            f"WHERE snapshot_id IN ({marks}) AND rank<=? ORDER BY rank",
            (*ids, 10),
        ).fetchall()
    by_snap: dict[int, list[dict]] = {}
    for e in entries:
        by_snap.setdefault(e["snapshot_id"], []).append(dict(e))
    return [
        {"ts": s["ts"], "fetched_at": s["fetched_at"], "top": by_snap.get(s["id"], [])}
        for s in snaps
    ]


def search(
    query: str,
    woeid: int | None = None,
    hours: int = 72,
    limit: int = 100,
) -> list[dict]:
    """全地点・全履歴からキーワード検索。"""
    q = f"%{query.strip().lower()}%"
    since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
    sql = """
        SELECT e.name AS name, e.woeid AS woeid, e.category AS category,
               MIN(e.rank) AS best_rank,
               MAX(e.tweet_count) AS max_count,
               MIN(s.ts) AS first_ts,
               MAX(s.ts) AS last_ts,
               COUNT(*) AS appearances
        FROM trend_entries e
        JOIN snapshots s ON s.id = e.snapshot_id
        WHERE s.ts >= ? AND e.name_lower LIKE ?
    """
    params: list = [since, q]
    if woeid is not None:
        sql += " AND e.woeid = ?"
        params.append(woeid)
    sql += " GROUP BY e.woeid, e.name_lower ORDER BY max_count DESC, appearances DESC LIMIT ?"
    params.append(limit)
    with tx() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def location_stats(woeid: int) -> dict:
    with tx() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n, MIN(ts) AS first_ts, MAX(ts) AS last_ts "
            "FROM snapshots WHERE woeid=?", (woeid,)
        ).fetchone()
        uniq = conn.execute(
            "SELECT COUNT(DISTINCT name_lower) AS n FROM trend_entries e "
            "JOIN snapshots s ON s.id=e.snapshot_id WHERE e.woeid=?", (woeid,)
        ).fetchone()
    return {
        "snapshots": row["n"] or 0,
        "unique_trends": uniq["n"] or 0,
        "first_ts": row["first_ts"],
        "last_ts": row["last_ts"],
    }


def all_locations_stats() -> list[dict]:
    with tx() as conn:
        rows = conn.execute(
            "SELECT woeid, COUNT(*) AS snapshots, MAX(ts) AS last_ts FROM snapshots "
            "GROUP BY woeid ORDER BY last_ts DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def set_meta(key: str, value: str) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)", (key, value)
        )


def get_meta(key: str) -> str | None:
    with tx() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def log_notif_event(woeid: int, keyword: str, matched: str, rank: int | None,
                    count: int | None, ts: int) -> bool:
    """重複なら False、新規登録できたら True。"""
    with tx() as conn:
        try:
            conn.execute(
                "INSERT INTO notif_events (woeid, keyword, matched, rank, tweet_count, ts, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (woeid, keyword, matched, rank, count, ts,
                 datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def recent_notif_events(limit: int = 50) -> list[dict]:
    with tx() as conn:
        rows = conn.execute(
            "SELECT * FROM notif_events ORDER BY ts DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def dump_snapshot_json(woeid: int) -> dict | None:
    snap = latest_snapshot(woeid)
    if not snap:
        return None
    return {"location": woeid, **snap}
