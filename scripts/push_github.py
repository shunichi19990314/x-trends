#!/usr/bin/env python3
"""
GitHub に push するための補助スクリプト。

    export GITHUB_TOKEN=ghp_xxxx
    python scripts/push_github.py <owner> [repo] [public|private]

    # 例
    python scripts/push_github.py myname x-trends public

動作:
  1. リポジトリが無ければ GitHub API で作成（public/private は引数で指定）
  2. origin にクリーンなURL（トークンを含まない）を設定
  3. トークン付きURLで一度だけ push（.git/config にトークンを残さない）

必要なトークン権限:
  - fine-grained PAT: Contents = Read and write
                      Administration = Read and write（リポジトリを新規作成する場合のみ）
  - classic PAT: repo スコープ
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com"
DESCRIPTION = (
    "X (Twitter) trends dashboard — 地域別トレンドの表示・履歴・推移グラフ・"
    "地域比較・カテゴリ分類・キーワード通知（FastAPI + SQLite）"
)


def gh(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict]:
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"message": raw[:300]}


def scrub_token(token: str) -> None:
    """.git/config 等にトークンが残っていたら除去する（保険）。"""
    cfg = ROOT / ".git" / "config"
    if not cfg.exists():
        return
    text = cfg.read_text(encoding="utf-8")
    if token in text or "x-access-token" in text:
        clean = text.replace(f"x-access-token:{token}@", "").replace(token, "")
        cfg.write_text(clean, encoding="utf-8")
        print("[ok] .git/config からトークンを除去しました")


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print("  $", " ".join(cmd[:2]), "…")
    return subprocess.run(cmd, cwd=ROOT, check=check,
                          capture_output=True, text=True)


def main() -> int:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not token:
        print("❌ GITHUB_TOKEN が未設定です。\n"
              "   export GITHUB_TOKEN=ghp_xxx  してから再実行してください。", file=sys.stderr)
        return 2
    if not args:
        print(__doc__)
        return 2

    owner = args[0]
    repo = args[1] if len(args) > 1 else "x-trends"
    private = (args[2].lower() in {"private", "true", "1"}) if len(args) > 2 else False

    # --- 認証確認 -------------------------------------------------------
    code, me = gh("GET", "/user", token)
    if code != 200:
        print(f"❌ トークン認証に失敗しました (HTTP {code}): {me.get('message', '')}", file=sys.stderr)
        print("   権限: fine-grained なら Contents=Read and write、classic なら repo が必要です。",
              file=sys.stderr)
        return 1
    login = me.get("login", owner)
    print(f"[ok] 認証済み: {login}")

    # --- リポジトリ確認 / 作成 -------------------------------------------
    code, info = gh("GET", f"/repos/{owner}/{repo}", token)
    if code == 200:
        print(f"[ok] リポジトリ既存: {info.get('html_url')} (private={info.get('private')})")
    elif code == 404:
        payload = {"name": repo, "private": private, "description": DESCRIPTION,
                   "has_issues": False, "auto_init": False}
        target = "/user/repos" if owner == login else f"/orgs/{owner}/repos"
        code2, created = gh("POST", target, token, payload)
        if code2 not in (200, 201):
            print(f"❌ リポジトリ作成に失敗 (HTTP {code2}): {created.get('message', '')}", file=sys.stderr)
            if "Resource not accessible" in str(created.get("message", "")):
                print("   → fine-grained PAT なら Administration=Read and write が必要です。\n"
                      "     または GitHub 側で空リポジトリを作ってから再実行してください。", file=sys.stderr)
            return 1
        print(f"[ok] 作成しました: {created.get('html_url')} (private={created.get('private')})")
    else:
        print(f"❌ リポジトリ確認に失敗 (HTTP {code}): {info.get('message', '')}", file=sys.stderr)
        return 1

    # --- remote 設定（トークンを含まないURL） ------------------------------
    clean_url = f"https://github.com/{owner}/{repo}.git"
    run(["git", "remote", "remove", "origin"], check=False)
    run(["git", "remote", "add", "origin", clean_url])

    # --- push（トークンはこのURL内にのみ使い、保存しない） ------------------
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip() or "main"
    push_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
    print(f"[push] {branch} → origin/{branch}")
    # 注意: `-u` を付けるとトークン付きURLが branch.<name>.remote に保存されてしまうため、
    #       push 自体は -u なしで行い、upstream はあとから origin に設定し直す。
    res = subprocess.run(["git", "push", push_url, f"{branch}:{branch}"],
                         cwd=ROOT, capture_output=True, text=True)
    out = (res.stdout + res.stderr).replace(token, "***")
    print(out.strip())
    if res.returncode != 0:
        print("❌ push に失敗しました", file=sys.stderr)
        return 1

    # --- 後片付け: tracking を origin（トークンなし）に向ける ---------------
    run(["git", "fetch", "origin"], check=False)
    run(["git", "branch", "--set-upstream-to", f"origin/{branch}", branch], check=False)
    scrub_token(token)

    print(f"\n🎉 完了: https://github.com/{owner}/{repo}")
    print("   次のステップ: Render → New + → Blueprint → このリポジトリを選択")
    print("   （render.yaml が自動検出されます。X_BEARER_TOKEN は空ならデモモードで起動）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
