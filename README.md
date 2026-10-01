# X Trends Dashboard

X（旧Twitter）のトレンドを**地域別にまとめて表示**するセルフホスト型ダッシュボード。

- 175地域（全世界 / 日本 / 都道府県・主要都市 / 世界）をワンクリック切替
- 各トレンドの **投稿数・ランク変動・24時間スパークライン・急上昇（勢い）・初出時刻**
- **カテゴリ自動分類**（エンタメ / アニメ・ゲーム / スポーツ / ニュース / テック / 経済 / 暮らし / #タグ）
- **推移タイムライン**、**地域比較**（複数都市の共通話題を抽出）、**分析**（ドーナツ・粘着度・ヒートマップ）
- **キーワード通知**（ブラウザ通知＋音＋検知ログ）
- 履歴をSQLiteに蓄積（X APIは「今」しか返さないので、時系列は自前で貯める設計）
- CSV書き出し / 全文検索 / ダーク・ライトテーマ / PWA / レスポンシブ
- **APIキーが無くても全機能が動くデモモード内蔵**

技術スタック: **FastAPI + SQLite + 素のES Modules（ビルド不要・依存ゼロのフロント）**

---

## 1. とりあえず動かす（30秒）

```bash
cd x-trends
./run.sh
# → http://127.0.0.1:8000
```

`.env` が無ければ自動で作成され、**デモモード（合成データ）**で起動します。
APIキーがなくてもUIの全機能を確認できます。

手動でやる場合:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

> `static/index.html` をブラウザで直接開いても動きます（バックエンド未接続を検知して
> ブラウザ内でデモデータを生成するフォールバックが入っています）。

---

## 2. 実データに繋ぐ（X API）

### 2-1. 公式 X API v2 を使う

エンドポイントはこれ一本です。

```
GET https://api.x.com/2/trends/by/woeid/{woeid}
Authorization: Bearer <Bearer Token>
→ {"data": [{"trend_name": "...", "tweet_count": 12345}, ...]}
```

`.env` に書くだけ:

```dotenv
TRENDS_PROVIDER=official      # 未設定でも X_BEARER_TOKEN があれば自動で official
X_BEARER_TOKEN=AAAAAAAA...    # console.x.com / developer portal で発行
```

**2026年時点の注意点（重要）**

| 項目 | 内容 |
|---|---|
| 課金モデル | 2026年2月から **pay-per-use（クレジット前払い）**。Free / Basic / Pro の月額プランは新規受付終了、既存 Basic は 2026-06-01、Pro は 2026-09-01 に移行済み |
| Trends の単価 | 公式レートカードで **$0.010 / リクエスト** 前後（1回の呼び出しで約20〜50トレンドが返る） |
| 権限 | 「Trends は旧Pro相当の権限が必要」という報告と「pay-per-useで叩ける」という報告が混在します。**必ず console.x.com で自分のアカウントの権限と単価を確認**してください。403が返る場合は権限不足です |
| レート制限 | **75リクエスト / 15分**（アプリ全体で共有。App-only 認証） |
| 履歴 | 返ってこない。本ダッシュボードはSQLiteに自前で蓄積します |
| `tweet_count` | 仕様上 **欠損することが多い**（UIでは「投稿数 非公開」と表示） |
| 未対応WOEID | エラーではなく **空配列** が返る（約470地点のみ対応） |

**コスト試算**（`POLL_INTERVAL=5`、4地域を監視）

```
12回/時 × 24時間 × 4地域 = 1,152 リクエスト/日 ≒ $11.5/日 ≒ $345/月
```

→ 監視地域数 × 取得頻度がそのまま料金になります。
`POLL_INTERVAL=15`、`WATCH_WOEIDS=1,23424856` 程度に絞るのが現実的です。
（リソースは24時間UTC以内で重複課金されない「デデュープ」規定がありますが、
トレンドは毎回中身が変わるため当てにしないでください）

### 2-2. 公式が高すぎる場合の代替

`TWITTERAPI_KEY` を設定すると、同じWOEID体系のサードパーティAPIに切り替わります
（WOEIDは完全に共通なので地域データはそのままでOK）。

```dotenv
TRENDS_PROVIDER=twitterapiio
TWITTERAPI_KEY=...
```

TwitterAPI.io などのリセラーは1リクエスト単位課金で、
「4地域を5分ごと」なら月数十ドル程度に収まるケースが多いです。
ただし **X公式ではない** ため、規約・継続性・データ品質は自己判断で。

### 2-3. スクレイピングについて

非公式エンドポイントやHTMLスクレイピングは **Xの利用規約違反** であり、
IP/アカウントのBAN対象です。本プロジェクトには実装していません。

---

## 3. 設定（`.env`）

| 変数 | 既定 | 説明 |
|---|---|---|
| `TRENDS_PROVIDER` | 自動 | `official` / `twitterapiio` / `demo` |
| `X_BEARER_TOKEN` | – | 公式APIのBearer Token |
| `TWITTERAPI_KEY` | – | 代替APIのキー |
| `POLL_INTERVAL` | `5` | 自動収集の間隔（**分**）。フロントの表示更新間隔はUI側で別途設定 |
| `WATCH_WOEIDS` | `1,23424856,1118370,15015372` | 自動収集する地域。空なら既定セット |
| `POLLER_ENABLED` | `true` | `false` で手動更新のみに |
| `SEED_HISTORY` | `true` | 初回起動時にデモ履歴2日分を作る（demo時のみ動作） |
| `DB_PATH` | `./data/trends.db` | SQLite の場所 |
| `HISTORY_DAYS` | `7` | 履歴の保持日数（超過分は自動削除） |
| `MAX_SNAPSHOTS` | `4000` | 1地域あたりのスナップショット上限 |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | 待ち受け |
| `ACCESS_TOKEN` | – | 設定すると `X-Access-Token` ヘッダ必須（`/api/health` とUI配信は除く） |
| `DEBUG` | `false` | `true` で uvicorn reload |

UIからも変更できるもの: 自動更新ON/OFF・更新間隔・表示件数・監視地域・通知キーワード・テーマ。

---

## 4. 使い方

### 基本操作

| 操作 | 方法 |
|---|---|
| 地域切替 | 左サイドバー、または上部の地域検索（`東京` / `Berlin` / `23424856`） |
| 絞り込み | カテゴリチップ、一覧内の検索ボックス、「新着のみ」「#タグのみ」「重複をまとめる」 |
| 並べ替え | ランク順 / 投稿数順 / 急上昇 / 名前順 |
| 詳細 | カードをクリック → 投稿数とランクの24時間推移、最大/最小/平均、X検索リンク |
| 通知 | 🔔 → 地域とキーワードを追加（例: `大谷` `地震` `ChatGPT`）。一致すると通知＋音 |
| 書き出し | `CSV` ボタン（BOM付きなのでExcelでそのまま開けます） |
| 共有 | 共有ボタンで上位20件をテキスト化（`navigator.share` 対応端末は共有シート） |

### キーボードショートカット

| キー | 動作 |
|---|---|
| `/` | 全体検索にフォーカス |
| `R` | 今すぐ更新（**APIを1回消費します**） |
| `T` | テーマ切替 |
| `1` `2` `3` `4` | トレンド / 推移 / 比較 / 分析 |
| `Esc` | ドロワー・モーダルを閉じる |

### タブの中身

- **トレンド** … 現在のスナップショット。カードにランク・変動・投稿数・スパークライン
- **推移** … スナップショットごとの上位10件を時系列で。6h / 24h / 72h
- **比較** … 複数地域の横並び＋「複数地域で同時にトレンド」の共通話題を抽出
- **分析** … KPI、カテゴリ内訳ドーナツ、粘着度（何割の時間ランクインしていたか）、時間×トレンドのヒートマップ

---

## 5. API リファレンス

Swagger UI: **http://127.0.0.1:8000/docs**

| Method | Path | 説明 |
|---|---|---|
| GET | `/api/health` | 生存確認 |
| GET | `/api/config` | プロバイダ・カテゴリ定義・監視地域 |
| GET | `/api/locations` | 地域一覧（`?q=東京` で検索） |
| GET | `/api/trends/{woeid}` | 現在のトレンド（`?refresh=true&hours=24`） |
| GET | `/api/trends/{woeid}/history` | 特定トレンドの履歴（`?name=鬼滅の刃&hours=48`） |
| GET | `/api/trends/{woeid}/timeline` | スナップショット列 |
| GET | `/api/trends/{woeid}/top` | 期間内の粘着度ランキング |
| GET | `/api/trends/{woeid}/categories` | カテゴリ集計 |
| GET | `/api/compare` | 地域比較（`?woeids=1,23424856,1118370`） |
| GET | `/api/search` | 全地域・全履歴の横断検索 |
| GET | `/api/stats/{woeid}` | 保存統計 |
| GET | `/api/status` | ポーラー状態・エラー・API呼び出し回数 |
| POST | `/api/refresh` | 今すぐ収集（`?woeid=` で1地域だけ） |
| POST | `/api/watch` | 監視地域の変更 `{"woeids":[1,23424856]}` |
| POST | `/api/notifications/keywords` | サーバ側通知キーワード |
| GET | `/api/notifications/events` | 通知の発火履歴 |
| GET | `/api/export/{woeid}.csv` | CSV |

例:

```bash
curl 'http://127.0.0.1:8000/api/trends/1118370?refresh=true'
curl 'http://127.0.0.1:8000/api/search?q=大谷&hours=72'
curl -X POST 'http://127.0.0.1:8000/api/watch' -H 'Content-Type: application/json' \
     -d '{"woeids":[1,23424856,1118370,15015372]}'
```

---

## 6. ディレクトリ構成

```
x-trends/
├── app/
│   ├── main.py         # FastAPI ルート定義
│   ├── providers.py    # official / twitterapiio / demo の取得層
│   ├── demo_data.py    # デモ用の話題語彙（日本語820 / 英語590 / 全世界共通234）
│   ├── classify.py     # カテゴリ分類の辞書＋ルール（ここを拡張すると精度が上がる）
│   ├── db.py           # SQLite（snapshots / trend_entries / notif_events / meta）
│   ├── poller.py       # バックグラウンド収集ループ＋デモ履歴のシード
│   ├── locations.py    # WOEID マスタ（175地域）
│   └── config.py       # .env 読み込み
├── static/
│   ├── index.html
│   ├── style.css
│   └── js/             # app / api / state / board / views / panels / charts / demo / util
├── data/trends.db      # 履歴（gitignore 済み）
├── scripts/smoke_test.py
├── render.yaml         # Render Blueprint（デプロイ構成）
├── .python-version     # Render / pyenv 用の Python 版指定
├── requirements.txt / .env.example / run.sh / Dockerfile / docker-compose.yml
```

### 拡張ポイント

- **地域を追加**: `app/locations.py` の `_RAW` に1行足すだけ
- **カテゴリ精度を上げる**: `app/classify.py` の `KEYWORDS` に語を追加
- **別のデータソース**: `app/providers.py` に `fetch_xxx()` を足して `fetch_trends()` に分岐を追加
- **通知をSlack/Discordに**: `app/poller.py` の `_check_notifications()`

---

## 7. デプロイ（Render）

リポジトリ直下の **`render.yaml`**（Blueprint）に構成を書いてあります。
GitHub に push して Render で読み込むだけでデプロイできます。

### 7-1. Blueprint でデプロイ（推奨）

1. GitHub にリポジトリを作成して push
   ```bash
   # A) 手動
   git init -b main
   git add -A && git commit -m "X Trends Dashboard"
   git remote add origin https://github.com/<user>/<repo>.git
   git push -u origin main

   # B) 補助スクリプト（リポジトリ作成 + push を一括。トークンは .git/config に残しません）
   export GITHUB_TOKEN=ghp_xxxxxxxx        # fine-grained: Contents=RW (+Administration=RW)
   python scripts/push_github.py <owner> x-trends public
   ```
2. Render Dashboard → **New +** → **Blueprint** → 対象リポジトリを選択
   （GitHub App のインストール許可が必要）
3. `render.yaml` が自動検出され、環境変数入力画面が出ます。
   - **X_BEARER_TOKEN** … 公式APIを使う場合のみ入力。空なら **demo モード**で起動します
   - **ACCESS_TOKEN** … 公開URLを守るパスフレーズ。空なら認証なし
4. **Apply** → ビルド完了後 `https://<service>.onrender.com` で閲覧

Blueprint の中身（`render.yaml`）:

| 項目 | 値 |
|---|---|
| runtime | `python`（`PYTHON_VERSION=3.13.5` / `.python-version` でも指定） |
| plan | `free` |
| region | `singapore` |
| buildCommand | `pip install --no-cache-dir -r requirements.txt` |
| startCommand | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1` |
| healthCheckPath | `/api/health` |
| numInstances | `1`（**必ず1**。pollerがプロセス内常駐＋SQLite単一ファイルのため） |

### 7-2. 手動でサービスを作る場合

New + → **Web Service** で以下を入力すれば同じ構成になります。

- Runtime: **Python 3**
- Build Command: `pip install --no-cache-dir -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
- Health Check Path: `/api/health`
- Environment Variables: `TRENDS_PROVIDER` / `X_BEARER_TOKEN` / `POLL_INTERVAL` /
  `WATCH_WOEIDS` / `DB_PATH=/opt/render/project/src/data/trends.db` / `ACCESS_TOKEN`

> `PORT` は Render が自動で注入します。コード側は `--port $PORT` で受けるだけなので
> 固定ポートを書く必要はありません。

### 7-3. Free プランの注意点（重要）

| 制約 | 影響 | 対処 |
|---|---|---|
| **15分アイドルでスリープ** | 収集(poller)が止まり、アクセス時にコールドスタート（数十秒） | 有料プランにする／外部の Uptime ロボットで定期ping |
| **ディスクが永続化されない** | デプロイ・再起動ごとに `data/trends.db` が消え、履歴がゼロから | ①`SEED_HISTORY=true` でデモ履歴を自動生成（demo時のみ）<br>②有料プランで **Disk** を付ける（下記） |
| 750時間/月の無料枠 | 常時稼働1サービスならギリギリ収まる | 複数サービスを立てるなら有料 |

**履歴を残したい場合（有料プラン）**: `plan: starter` 以上に変更し、
`render.yaml` 末尾の `disk:` コメントを外します。

```yaml
    plan: starter
    disk:
      name: trends-data
      mountPath: /opt/render/project/src/data
      sizeGB: 1
```

`DB_PATH` は既にその mountPath 配下を指しているので追加設定は不要です。
Disk は24時間ごとに自動スナップショットが取られます。

### 7-4. APIコスト暴発の防止

公開デプロイは「常時ポーリング＝常時課金」です。`render.yaml` の既定は
控えめにしてあります（**15分間隔 × 3地域 ≒ 864リクエスト/日**）。

- 公式APIのTrends単価で概算すると **$8〜9/日** 程度。無料枠では賄えないので、
  まずは `TRENDS_PROVIDER=demo` で挙動確認 → 必要になったら課金、が安全です
- 監視地域を増やす・間隔を縮める前に、必ず `/api/status` の `api_calls` と
  console.x.com のクレジット残高を確認してください
- 一時的に止めたいだけなら Dashboard で `POLLER_ENABLED=false`（手動更新のみになる）

### 7-5. セキュリティ

- `ACCESS_TOKEN` を設定すると、`/api/*` は `X-Access-Token` ヘッダ必須になります
  （`/api/health` と UI の配信は除外）。UIの「設定 → アクセストークン」に入力すると
  localStorage に保存され、以降のリクエストに自動付与されます
- **X の Bearer Token はブラウザに一切渡していません**。API呼び出しはすべて
  サーバ側（Render コンテナ内）で行い、`/api/config` が返すのは
  `has_x_token: true/false` の有無だけです
- 公開する場合は必ず `ACCESS_TOKEN` を設定してください。放置すると
  第三者が `/api/refresh` を叩いて**あなたのクレジットを消費**できます

### Docker / 自前サーバ

```bash
docker build -t x-trends .
docker run -d -p 8000:8000 --env-file .env -v $PWD/data:/app/data --name x-trends x-trends
```

```ini
# /etc/systemd/system/x-trends.service
[Unit]
Description=X Trends Dashboard
After=network.target

[Service]
WorkingDirectory=/opt/x-trends
ExecStart=/opt/x-trends/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
EnvironmentFile=/opt/x-trends/.env

[Install]
WantedBy=multi-user.target
```

自前で公開するときは前段にリバースプロキシ（nginx / Caddy）を置いて
HTTPS を終端してください。

---

## 8. テスト

```bash
# バックエンド + 静的ファイル（サーバを自動起動して全エンドポイントを検査）
python scripts/smoke_test.py

# フロントエンド（jsdom で index.html をロードし、UI操作を一通り自動化）
npm i jsdom                                  # 初回のみ
uvicorn app.main:app --port 8123 &           # 別ターミナルで起動しておく
BASE=http://127.0.0.1:8123 ROOT=$PWD node scripts/ui_test.mjs
```

どちらも最後の行に `🎉 全テスト合格` / `🎉 全UIテスト合格` が出ればOKです。

---

## 9. 既知の制限

- **Xの「あなた向けのトレンド」は取得不可**。APIが返すのは地域ベースの公開トレンドのみ
- **履歴はXから遡れない**。本アプリを起動してからの蓄積分だけが見られます
  （demoモードは初回起動時に2日分を自動生成）
- `tweet_count` は欠損が多く、投稿数順ソートが効かないことがあります
- WOEIDはYahoo由来のレガシーIDで、Xが対応するのは約470地点のみ。
  未対応地点は空配列が返ります（本アプリの175地域は対応済みIDから選定）
- 分類は辞書ベースの推定です。誤分類は `classify.py` の語を追加して調整してください

---

## 参考

- X API v2 Trends: `GET /2/trends/by/woeid/:woeid`（App-only認証 / 75req/15min）
- X API 料金: https://docs.x.com/x-api/getting-started/pricing
- WOEID の由来: Yahoo GeoPlanet（2010年からXが流用）
