/* API クライアント。
   バックエンド(FastAPI)に繋がれば実データ、繋がらなければブラウザ内で
   デモデータを生成して同じ形を返す → index.html 単体でも UI が動く。 */

import { CATS, demoTrends } from "./demo.js";

const BASE = "";
let _token = "";
export let ONLINE = false;

export function setToken(t) { _token = t || ""; }
export function getToken() { return _token; }

async function req(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (_token) headers["X-Access-Token"] = _token;
  const res = await fetch(BASE + path, { ...opts, headers });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { const j = await res.json(); detail = j.detail || JSON.stringify(j).slice(0, 200); } catch {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

/* ======================================================================== */
/* オフライン用フォールバックデータ                                          */
/* ======================================================================== */

const OFFLINE_LOCS = [
  [1,"Worldwide","全世界","XX","全世界","worldwide","worldwide"],
  [23424856,"Japan","日本","JP","日本","country","japan"],
  [1118370,"Tokyo","東京","JP","日本","town","japan"],
  [15015372,"Osaka","大阪","JP","日本","town","japan"],
  [1117642,"Nagoya","名古屋","JP","日本","town","japan"],
  [1117089,"Yokohama","横浜","JP","日本","town","japan"],
  [1116957,"Sapporo","札幌","JP","日本","town","japan"],
  [1117561,"Fukuoka","福岡","JP","日本","town","japan"],
  [1117623,"Kobe","神戸","JP","日本","town","japan"],
  [1118184,"Kyoto","京都","JP","日本","town","japan"],
  [1118212,"Saitama","さいたま","JP","日本","town","japan"],
  [1118105,"Hiroshima","広島","JP","日本","town","japan"],
  [1118226,"Sendai","仙台","JP","日本","town","japan"],
  [23424977,"United States","アメリカ","US","アメリカ","country","americas"],
  [2459115,"New York","ニューヨーク","US","アメリカ","town","americas"],
  [2442047,"Los Angeles","ロサンゼルス","US","アメリカ","town","americas"],
  [2487956,"San Francisco","サンフランシスコ","US","アメリカ","town","americas"],
  [2476195,"San Diego","サンディエゴ","US","アメリカ","town","americas"],
  [2379574,"Chicago","シカゴ","US","アメリカ","town","americas"],
  [23424775,"Canada","カナダ","CA","カナダ","country","americas"],
  [4118,"Toronto","トロント","CA","カナダ","town","americas"],
  [23424900,"Mexico","メキシコ","MX","メキシコ","country","americas"],
  [23424768,"Brazil","ブラジル","BR","ブラジル","country","americas"],
  [455825,"Sao Paulo","サンパウロ","BR","ブラジル","town","americas"],
  [23424975,"United Kingdom","イギリス","GB","イギリス","country","europe"],
  [44418,"London","ロンドン","GB","イギリス","town","europe"],
  [28218,"Manchester","マンチェスター","GB","イギリス","town","europe"],
  [23424819,"France","フランス","FR","フランス","country","europe"],
  [615702,"Paris","パリ","FR","フランス","town","europe"],
  [23424829,"Germany","ドイツ","DE","ドイツ","country","europe"],
  [638242,"Berlin","ベルリン","DE","ドイツ","town","europe"],
  [23424936,"Spain","スペイン","ES","スペイン","country","europe"],
  [766273,"Madrid","マドリード","ES","スペイン","town","europe"],
  [23424989,"Italy","イタリア","IT","イタリア","country","europe"],
  [721943,"Rome","ローマ","IT","イタリア","town","europe"],
  [23424781,"China","中国","CN","中国","country","asia"],
  [1257802,"Beijing","北京","CN","中国","town","asia"],
  [1257801,"Shanghai","上海","CN","中国","town","asia"],
  [23424788,"Korea","韓国","KR","韓国","country","asia"],
  [1132599,"Seoul","ソウル","KR","韓国","town","asia"],
  [23424948,"Taiwan","台湾","TW","台湾","country","asia"],
  [2306190,"Taipei","台北","TW","台湾","town","asia"],
  [23424942,"Malaysia","マレーシア","MY","マレーシア","country","asia"],
  [1257799,"Kuala Lumpur","クアラルンプール","MY","マレーシア","town","asia"],
  [1062617,"Singapore","シンガポール","SG","シンガポール","town","asia"],
  [23424848,"India","インド","IN","インド","country","asia"],
  [2295411,"Mumbai","ムンバイ","IN","インド","town","asia"],
  [23424933,"Thailand","タイ","TH","タイ","country","asia"],
  [1225448,"Bangkok","バンコク","TH","タイ","town","asia"],
  [23424922,"Indonesia","インドネシア","ID","インドネシア","country","asia"],
  [1047378,"Jakarta","ジャカルタ","ID","インドネシア","town","asia"],
  [23424845,"Philippines","フィリピン","PH","フィリピン","country","asia"],
  [1167715,"Manila","マニラ","PH","フィリピン","town","asia"],
  [23424755,"Australia","オーストラリア","AU","オーストラリア","country","asia"],
  [1100661,"Sydney","シドニー","AU","オーストラリア","town","asia"],
  [23424930,"United Arab Emirates","UAE","AE","UAE","country","mea"],
  [1940330,"Dubai","ドバイ","AE","UAE","town","mea"],
  [23424931,"Saudi Arabia","サウジアラビア","SA","サウジアラビア","country","mea"],
  [1939873,"Riyadh","リヤド","SA","サウジアラビア","town","mea"],
  [23424809,"Egypt","エジプト","EG","エジプト","country","mea"],
  [23424903,"Nigeria","ナイジェリア","NG","ナイジェリア","country","mea"],
  [1398823,"Lagos","ラゴス","NG","ナイジェリア","town","mea"],
  [23424942,"South Africa","南アフリカ","ZA","南アフリカ","country","mea"],
  [1580913,"Johannesburg","ヨハネスブルク","ZA","南アフリカ","town","mea"],
];

const REGION_LABEL = {
  worldwide: "🌍 全世界", japan: "🇯🇵 日本", asia: "🌏 アジア・オセアニア",
  americas: "🌎 南北アメリカ", europe: "🌍 ヨーロッパ", mea: "🌍 中東・アフリカ",
};
const REGION_ORDER = ["worldwide", "japan", "asia", "americas", "europe", "mea"];
const PT_JA = { worldwide: "全世界", country: "国", town: "都市" };

const OFFLINE_MAP = new Map(OFFLINE_LOCS.map(r => [r[0], {
  woeid: r[0], name: r[1], name_ja: r[2], country: r[3], country_ja: r[4],
  place_type: r[5], place_type_ja: PT_JA[r[5]] || r[5], region: r[6],
}]));

const now = () => Math.floor(Date.now() / 1000);
const xurl = (n) => `https://x.com/search?q=${encodeURIComponent(n)}&src=trend_click`;
const catMeta = (c) => ({ id: c, ...(CATS[c] || CATS.other) });

function offlineEnrich(woeid, trends, hours = 24) {
  const t0 = now();
  const step = 1800;
  const stamps = [];
  for (let ts = t0 - hours * 3600; ts <= t0; ts += step) stamps.push(ts);
  const histByName = new Map();
  for (const ts of stamps) {
    for (const t of demoTrends(woeid, ts, 50)) {
      if (!histByName.has(t.name)) histByName.set(t.name, []);
      histByName.get(t.name).push({ ts, rank: t.rank, count: t.tweet_count });
    }
  }
  const prevTs = t0 - 1800;
  const prevMap = new Map(demoTrends(woeid, prevTs, 50).map(t => [t.name, t.rank]));

  return trends.map((t) => {
    const spark = histByName.get(t.name) || [];
    const counts = spark.map(p => p.count).filter(c => c != null);
    const avg = counts.length ? counts.reduce((a, b) => a + b, 0) / counts.length : null;
    const prevRank = prevMap.get(t.name);
    const firstTs = spark.length ? spark[0].ts : t0;
    const delta = prevRank == null ? null : prevRank - t.rank;
    return {
      ...t,
      category_meta: t.category_meta || catMeta(t.category),
      change: prevRank == null ? "new" : (delta > 0 ? "up" : delta < 0 ? "down" : "same"),
      rank_delta: delta,
      prev_rank: prevRank ?? null,
      first_seen_ts: firstTs,
      age_minutes: Math.round((t0 - firstTs) / 60),
      momentum_pct: avg && t.tweet_count ? Math.round((t.tweet_count - avg) / avg * 1000) / 10 : null,
      avg_count_24h: avg ? Math.round(avg) : null,
      sparkline: spark,
      also_trending_in: [],
      url: xurl(t.name),
    };
  });
}

function offlineSnapshot(woeid, hours = 24) {
  const t0 = now();
  const trends = demoTrends(woeid, t0, 50);
  return {
    location: OFFLINE_MAP.get(woeid) || { woeid, name: String(woeid), name_ja: String(woeid), place_type: "town", place_type_ja: "都市" },
    fetched_at: new Date(t0 * 1000).toISOString(),
    ts: t0,
    age_seconds: 0,
    provider: "demo",
    source: "offline",
    previous_ts: t0 - 1800,
    count: trends.length,
    trends: offlineEnrich(woeid, trends, hours),
  };
}

/* ======================================================================== */
/* 公開 API                                                                  */
/* ======================================================================== */

async function probe() {
  try {
    const r = await fetch(BASE + "/api/health", { cache: "no-store" });
    ONLINE = r.ok;
  } catch { ONLINE = false; }
  return ONLINE;
}

export const api = {
  probe,
  get online() { return ONLINE; },

  async health() {
    if (ONLINE) return req("/api/health");
    return { status: "ok", version: "offline", provider: "demo", time: new Date().toISOString() };
  },

  async config() {
    if (ONLINE) return req("/api/config");
    return {
      provider: "demo", poll_interval: 5, poller_enabled: false, history_days: 7,
      has_x_token: false, has_twitterapi_key: false, auth_required: false,
      default_woeids: [1, 23424856, 1118370, 15015372, 23424977, 44418],
      categories: Object.entries(CATS).map(([id, c]) => ({ id, ...c })),
      watch: [1, 23424856, 1118370],
    };
  },

  async locations(q) {
    if (ONLINE) return req("/api/locations" + (q ? `?q=${encodeURIComponent(q)}` : ""));
    if (q) {
      const ql = q.toLowerCase();
      const results = [...OFFLINE_MAP.values()]
        .filter(l => `${l.name} ${l.name_ja} ${l.country_ja}`.toLowerCase().includes(ql))
        .slice(0, 20);
      return { results };
    }
    const groups = [];
    for (const region of REGION_ORDER) {
      const locs = [...OFFLINE_MAP.values()].filter(l => l.region === region);
      if (locs.length) groups.push({ region, label: REGION_LABEL[region] || region, locations: locs });
    }
    return { groups, total: OFFLINE_MAP.size };
  },

  async trends(woeid, { refresh = false, hours = 24, provider = null } = {}) {
    if (ONLINE) {
      const p = new URLSearchParams({ hours: String(hours) });
      if (refresh) p.set("refresh", "true");
      if (provider) p.set("provider", provider);
      return req(`/api/trends/${woeid}?${p}`);
    }
    return offlineSnapshot(woeid, hours);
  },

  async history(woeid, name, hours = 24) {
    if (ONLINE) {
      const p = new URLSearchParams({ name, hours: String(hours) });
      return req(`/api/trends/${woeid}/history?${p}`);
    }
    const t0 = now();
    const points = [];
    for (let ts = t0 - hours * 3600; ts <= t0; ts += 1800) {
      const hit = demoTrends(woeid, ts, 50).find(t => t.name === name);
      if (hit) points.push({ ts, rank: hit.rank, count: hit.tweet_count, fetched_at: new Date(ts * 1000).toISOString() });
    }
    const counts = points.map(p => p.count).filter(c => c != null);
    const ranks = points.map(p => p.rank);
    return {
      name, woeid, hours, points,
      summary: {
        appearances: points.length,
        best_rank: ranks.length ? Math.min(...ranks) : null,
        worst_rank: ranks.length ? Math.max(...ranks) : null,
        max_count: counts.length ? Math.max(...counts) : null,
        min_count: counts.length ? Math.min(...counts) : null,
        avg_count: counts.length ? Math.round(counts.reduce((a, b) => a + b, 0) / counts.length) : null,
        first_seen: points.length ? points[0].ts : null,
      },
      category: catMeta((points[0]?.category) || "other"),
    };
  },

  async timeline(woeid, hours = 24) {
    if (ONLINE) return req(`/api/trends/${woeid}/timeline?hours=${hours}`);
    const t0 = now();
    const snapshots = [];
    for (let ts = t0 - hours * 3600; ts <= t0; ts += 1800) {
      snapshots.push({
        ts, fetched_at: new Date(ts * 1000).toISOString(),
        top: demoTrends(woeid, ts, 10).map(t => ({
          name: t.name, rank: t.rank, tweet_count: t.tweet_count, category: t.category,
        })),
      });
    }
    return { location: OFFLINE_MAP.get(woeid), hours, snapshots };
  },

  async top(woeid, hours = 24, limit = 20) {
    if (ONLINE) return req(`/api/trends/${woeid}/top?hours=${hours}&limit=${limit}`);
    const t0 = now();
    const agg = new Map();
    let snaps = 0;
    for (let ts = t0 - hours * 3600; ts <= t0; ts += 1800) {
      snaps++;
      for (const t of demoTrends(woeid, ts, 50)) {
        const a = agg.get(t.name) || { name: t.name, category: t.category, appearances: 0, best_rank: 99, sum_rank: 0, max_count: 0, sum_count: 0, n_count: 0 };
        a.appearances++; a.best_rank = Math.min(a.best_rank, t.rank); a.sum_rank += t.rank;
        if (t.tweet_count != null) { a.max_count = Math.max(a.max_count, t.tweet_count); a.sum_count += t.tweet_count; a.n_count++; }
        agg.set(t.name, a);
      }
    }
    const items = [...agg.values()].map(a => ({
      name: a.name, category: a.category, category_meta: catMeta(a.category),
      appearances: a.appearances, best_rank: a.best_rank,
      avg_rank: Math.round(a.sum_rank / a.appearances * 10) / 10,
      max_count: a.max_count || null,
      avg_count: a.n_count ? Math.round(a.sum_count / a.n_count) : null,
      persistence: Math.round(a.appearances / snaps * 1000) / 10,
      url: xurl(a.name),
    })).sort((x, y) => y.appearances - x.appearances || x.avg_rank - y.avg_rank).slice(0, limit);
    return { location: OFFLINE_MAP.get(woeid), hours, snapshots: snaps, items };
  },

  async categories(woeid) {
    if (ONLINE) return req(`/api/trends/${woeid}/categories`);
    const snap = offlineSnapshot(woeid, 1);
    const agg = new Map();
    for (const t of snap.trends) {
      const a = agg.get(t.category) || { category: t.category, meta: catMeta(t.category), count: 0, total_count: 0, best_rank: 999, top: null };
      a.count++; a.total_count += t.tweet_count || 0;
      if (t.rank < a.best_rank) { a.best_rank = t.rank; a.top = t.name; }
      agg.set(t.category, a);
    }
    return { location: snap.location, items: [...agg.values()].sort((a, b) => b.total_count - a.total_count) };
  },

  async compare(woeids, limit = 10) {
    if (ONLINE) return req(`/api/compare?woeids=${woeids.join(",")}&limit=${limit}`);
    const columns = [];
    const sets = new Map();
    for (const w of woeids) {
      const snap = offlineSnapshot(w, 1);
      const trends = snap.trends.slice(0, limit);
      for (const t of trends) {
        const k = t.name.toLowerCase();
        if (!sets.has(k)) sets.set(k, new Set());
        sets.get(k).add(w);
      }
      columns.push({ location: snap.location, ts: snap.ts, age_seconds: 0,
        trends: trends.map(t => ({ name: t.name, rank: t.rank, tweet_count: t.tweet_count, category: t.category, category_meta: t.category_meta })) });
    }
    const shared = [...sets.entries()].filter(([, v]) => v.size > 1)
      .map(([k, v]) => ({ name_key: k, count: v.size, woeids: [...v].sort((a, b) => a - b) }))
      .sort((a, b) => b.count - a.count).slice(0, 25);
    return { columns, shared };
  },

  async search(q, { woeid = null, hours = 72, limit = 60 } = {}) {
    if (ONLINE) {
      const p = new URLSearchParams({ q, hours: String(hours), limit: String(limit) });
      if (woeid != null) p.set("woeid", String(woeid));
      return req(`/api/search?${p}`);
    }
    const ql = q.toLowerCase();
    const t0 = now();
    const found = new Map();
    for (let ts = t0 - hours * 3600; ts <= t0; ts += 1800) {
      for (const w of [...OFFLINE_MAP.keys()].slice(0, 8)) {
        for (const t of demoTrends(w, ts, 50)) {
          if (!t.name.toLowerCase().includes(ql)) continue;
          const k = `${w}|${t.name}`;
          const a = found.get(k) || { name: t.name, woeid: w, category: t.category, best_rank: 999, max_count: 0, first_ts: ts, last_ts: ts, appearances: 0 };
          a.appearances++; a.best_rank = Math.min(a.best_rank, t.rank);
          a.max_count = Math.max(a.max_count, t.tweet_count || 0);
          a.first_ts = Math.min(a.first_ts, ts); a.last_ts = Math.max(a.last_ts, ts);
          found.set(k, a);
        }
      }
    }
    const results = [...found.values()]
      .filter(r => !woeid || r.woeid === woeid)
      .map(r => ({ ...r, location: OFFLINE_MAP.get(r.woeid), category_meta: catMeta(r.category), url: xurl(r.name) }))
      .sort((a, b) => b.max_count - a.max_count).slice(0, limit);
    return { query: q, hours, count: results.length, results };
  },

  async status() {
    if (ONLINE) return req("/api/status");
    return {
      poller: { enabled: false, running: false, interval_minutes: 5, watch_woeids: [1, 23424856, 1118370],
        watch_names: ["全世界", "日本", "東京"], last_run: now(), cycles: 0, api_calls: 0, provider: "demo" },
      config: { provider: "demo", poll_interval: 5, poller_enabled: false, history_days: 7,
        has_x_token: false, has_twitterapi_key: false, auth_required: false },
      locations: [1, 23424856, 1118370].map(w => ({ ...OFFLINE_MAP.get(w), snapshots: 48, last_ts: now() })),
      db_locations: 3,
      server_time: new Date().toISOString(),
      offline: true,
    };
  },

  async refresh(woeid = null) {
    if (ONLINE) return req(`/api/refresh${woeid ? `?woeid=${woeid}` : ""}`, { method: "POST" });
    return { ok: true, result: { ok: [woeid ?? 1], failed: [], provider: "demo" }, offline: true };
  },

  async setWatch(woeids) {
    if (ONLINE) return req("/api/watch", { method: "POST", body: JSON.stringify({ woeids }) });
    return { ok: true, watch: woeids, offline: true };
  },

  async setServerKeywords(map) {
    if (ONLINE) return req("/api/notifications/keywords", { method: "POST", body: JSON.stringify({ keywords: map }) });
    return { ok: true, offline: true };
  },

  async notifEvents(limit = 50) {
    if (ONLINE) return req(`/api/notifications/events?limit=${limit}`);
    return { events: [], offline: true };
  },

  csvUrl(woeid) { return `${BASE}/api/export/${woeid}.csv`; },
};

/** CSV を作る（オフライン時はクライアント側で生成） */
export async function downloadCsv(woeid, snap, token) {
  if (ONLINE) {
    try {
      const res = await fetch(api.csvUrl(woeid), { headers: token ? { "X-Access-Token": token } : {} });
      if (res.ok) {
        const blob = await res.blob();
        triggerDownload(blob, `x-trends-${woeid}-${Date.now()}.csv`);
        return true;
      }
    } catch { /* fallthrough */ }
  }
  const rows = [["rank", "trend", "tweet_count", "category", "url"]];
  for (const t of snap.trends) rows.push([t.rank, t.name, t.tweet_count ?? "", t.category, t.url || xurl(t.name)]);
  const csv = "\ufeff" + rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\n");
  triggerDownload(new Blob([csv], { type: "text/csv;charset=utf-8" }), `x-trends-${woeid}-${Date.now()}.csv`);
  return true;
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
