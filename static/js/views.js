/* サイドバー / 推移 / 比較 / 分析 / 検索 の描画 */

import { $, el, esc, compact, fullNum, hhmm, mdhm, ago, agoShort, highlight, debounce } from "./util.js";
import { sparkline, lineChart, donut, hbars, heatmap } from "./charts.js";
import { api } from "./api.js";
import { state, catMeta, savePrefs } from "./state.js";

/* ================================================================== */
/* サイドバー（地域）                                                    */
/* ================================================================== */

export function renderSidebar() {
  const list = $("#locList");
  if (!list) return;
  list.innerHTML = "";
  const watchSet = new Set(state.watch || []);

  for (const group of state.locations.groups) {
    const det = el("details", { class: "loc-group", open: group.region === "japan" || group.locations.some(l => l.woeid === state.woeid) });
    const sum = el("summary", {}, [
      el("span", { text: group.label }),
      el("span", { class: "count", text: String(group.locations.length) }),
    ]);
    det.append(sum);

    const sorted = [...group.locations].sort((a, b) => {
      const p = { worldwide: 0, country: 1, town: 2 };
      return (p[a.place_type] ?? 3) - (p[b.place_type] ?? 3) || a.name_ja.localeCompare(b.name_ja, "ja");
    });

    for (const loc of sorted) {
      state.locations.byWoeid.set(loc.woeid, loc);
      const btn = el("button", {
        class: "loc-item" + (loc.woeid === state.woeid ? " is-active" : "") + (watchSet.has(loc.woeid) ? " is-watched" : ""),
        title: `${loc.name} (WOEID ${loc.woeid})${loc.has_data === false && api.online ? " — 履歴なし" : ""}`,
        onclick: () => {
          state.woeid = loc.woeid;
          savePrefs();
          renderSidebar();
          document.dispatchEvent(new CustomEvent("xt:location-changed", { detail: { woeid: loc.woeid } }));
        },
      }, [
        el("span", { class: "pt", text: loc.place_type_ja }),
        el("span", { class: "nm", text: loc.name_ja }),
        el("span", { class: "wo", text: String(loc.woeid) }),
      ]);
      det.append(btn);
    }
    list.append(det);
  }
}

export const searchLocations = debounce(async (q) => {
  const box = $("#locSearchResults");
  if (!box) return;
  if (!q.trim()) { box.hidden = true; box.innerHTML = ""; return; }
  const res = await api.locations(q.trim());
  box.innerHTML = "";
  const items = res.results || [];
  if (!items.length) {
    box.append(el("div", { class: "muted small", style: { padding: "8px" }, text: "該当する地域がありません" }));
  }
  for (const loc of items) {
    box.append(el("button", {
      onclick: () => {
        box.hidden = true; $("#locSearch").value = "";
        state.woeid = loc.woeid; savePrefs(); renderSidebar();
        document.dispatchEvent(new CustomEvent("xt:location-changed", { detail: { woeid: loc.woeid } }));
      },
    }, [
      el("span", {}, [el("b", { text: loc.name_ja }), el("span", { class: "muted small", text: ` ${loc.name}` })]),
      el("span", { class: "muted small", text: `${loc.place_type_ja} · ${loc.woeid}` }),
    ]));
  }
  box.hidden = false;
}, 200);

/* ================================================================== */
/* 推移（タイムライン）                                                  */
/* ================================================================== */

export async function renderTimeline() {
  const wrap = $("#tlWrap");
  wrap.innerHTML = "";
  wrap.append(el("div", { class: "sk", style: { height: "180px" } }));
  try {
    const data = await api.timeline(state.woeid, state.timelineHours);
    wrap.innerHTML = "";
    const snaps = data.snapshots || [];
    if (!snaps.length) {
      wrap.append(el("p", { class: "muted", text: "この時間帯のスナップショットがありません。自動収集を続けると溜まっていきます。" }));
      return;
    }
    wrap.append(el("p", { class: "muted small", style: { marginBottom: "10px" },
      text: `${data.location?.name_ja || ""} — ${snaps.length} スナップショット（新しい順）` }));

    const tl = el("div", { class: "tl" });
    for (const snap of [...snaps].reverse()) {
      const d = new Date(snap.ts * 1000);
      const row = el("div", { class: "tl-row" }, [
        el("div", { class: "tl-time" }, [el("b", { text: hhmm(snap.ts) }), el("span", { text: `${d.getMonth() + 1}/${d.getDate()}` })]),
        el("div", { class: "tl-items" }, snap.top.map(t => {
          const c = catMeta(t.category);
          return el("button", {
            class: "pill",
            title: `${t.name} — ${t.rank}位${t.tweet_count ? " / " + fullNum(t.tweet_count) + "投稿" : ""}`,
            onclick: () => document.dispatchEvent(new CustomEvent("xt:open-trend", { detail: { name: t.name, woeid: state.woeid } })),
          }, [
            el("span", { class: "dotc", style: { background: c.color } }),
            el("span", { class: "r", text: String(t.rank) }),
            el("span", { class: "t", text: t.name }),
          ]);
        })),
      ]);
      tl.append(row);
    }
    wrap.append(tl);
  } catch (err) {
    wrap.innerHTML = "";
    wrap.append(el("p", { class: "muted", text: `取得失敗: ${err.message}` }));
  }
}

/* ================================================================== */
/* 比較                                                                */
/* ================================================================== */

const CMP_PRESETS = {
  jp: [1118370, 15015372, 1117642, 1117561, 1116957, 1118184],
  world: [1, 23424977, 23424975, 23424768, 23424848, 23424755],
  mix: [23424856, 1118370, 1, 23424977, 1132599, 44418],
};

export async function renderCompare() {
  const grid = $("#cmpGrid");
  const shared = $("#cmpShared");
  grid.innerHTML = "";
  shared.innerHTML = "";
  for (let i = 0; i < state.compareIds.length; i++) grid.append(el("div", { class: "sk", style: { height: "260px" } }));

  try {
    const data = await api.compare(state.compareIds, 12);
    grid.innerHTML = "";
    shared.innerHTML = "";

    // 共通話題
    const sharedKeys = new Set((data.shared || []).map(s => s.name_key));
    shared.append(el("h3", { text: `${data.shared?.length || 0} 件の話題が複数の地域で同時にトレンド` }));
    if (data.shared?.length) {
      const tags = el("div", { class: "tags" });
      for (const s of data.shared.slice(0, 20)) {
        const first = data.columns.find(c => c.trends.some(t => t.name.toLowerCase() === s.name_key));
        const name = first?.trends.find(t => t.name.toLowerCase() === s.name_key)?.name || s.name_key;
        tags.append(el("span", {
          class: "pill", title: `${s.woeids.map(w => state.locations.byWoeid.get(w)?.name_ja || w).join(", ")}`,
          onclick: () => document.dispatchEvent(new CustomEvent("xt:open-trend", { detail: { name, woeid: s.woeids[0] } })),
        }, [el("span", { class: "t", text: name }), el("span", { class: "r", text: `${s.count}地域` })]));
      }
      shared.append(tags);
    } else {
      shared.append(el("p", { class: "muted small", text: "現時点で複数地域に共通するトレンドはありません。" }));
    }

    for (const col of data.columns) {
      const head = el("header", {}, [
        el("div", {}, [
          el("b", { text: col.location?.name_ja || col.location?.woeid }),
          el("div", { class: "muted small", text: col.ts ? `${ago(col.age_seconds)}更新 · ${col.trends.length}件` : "データなし" }),
        ]),
        el("button", { class: "btn btn-tiny", text: "表示", onclick: () => {
          state.woeid = col.location.woeid; savePrefs(); renderSidebar();
          document.dispatchEvent(new CustomEvent("xt:location-changed", { detail: { woeid: col.location.woeid } }));
          document.dispatchEvent(new CustomEvent("xt:switch-view", { detail: { view: "board" } }));
        }}),
      ]);
      const ol = el("ol");
      for (const t of col.trends) {
        const c = catMeta(t.category);
        ol.append(el("li", {
          class: sharedKeys.has(t.name.toLowerCase()) ? "shared" : "",
          onclick: () => document.dispatchEvent(new CustomEvent("xt:open-trend", { detail: { name: t.name, woeid: col.location.woeid } })),
        }, [
          el("span", { class: "dotc", style: { width: "6px", height: "6px", borderRadius: "50%", background: c.color, flex: "none" } }),
          el("span", { class: "nm", text: t.name }),
          el("span", { class: "v", text: t.tweet_count ? compact(t.tweet_count) : "–" }),
        ]));
      }
      grid.append(el("div", { class: "cmp-col" }, [head, ol]));
    }
  } catch (err) {
    grid.innerHTML = "";
    grid.append(el("p", { class: "muted", text: `取得失敗: ${err.message}` }));
  }
}

export function setComparePreset(key) {
  if (CMP_PRESETS[key]) { state.compareIds = [...CMP_PRESETS[key]]; savePrefs(); renderCompare(); }
}

/* ================================================================== */
/* 分析                                                                */
/* ================================================================== */

export async function renderAnalytics() {
  const kpi = $("#kpiRow");
  const catBox = $("#catChart");
  const persistBox = $("#persistChart");
  const hmBox = $("#heatmap");
  [kpi, catBox, persistBox, hmBox].forEach(n => { if (n) n.innerHTML = ""; });
  kpi.append(...Array.from({ length: 4 }, () => el("div", { class: "sk", style: { height: "76px" } })));

  try {
    const [snap, top, cats, tl] = await Promise.all([
      api.trends(state.woeid, { hours: state.sparkHours }).catch(() => null),
      api.top(state.woeid, state.analyticsHours, 15),
      api.categories(state.woeid),
      api.timeline(state.woeid, Math.min(state.analyticsHours, 72)),
    ]);

    const trends = snap?.trends || [];
    const newCount = trends.filter(t => t.change === "new").length;
    const tagCount = trends.filter(t => t.name.startsWith("#")).length;
    const totalVol = trends.reduce((s, t) => s + (t.tweet_count || 0), 0);
    const rising = trends.filter(t => t.change === "up").length;

    kpi.innerHTML = "";
    const kpis = [
      { k: "現在のトレンド", v: trends.length, s: `${snap?.location?.name_ja || ""} · ${snap ? ago(snap.age_seconds) + "更新" : ""}` },
      { k: "新着（前回比）", v: newCount, s: `上昇 ${rising} / 下降 ${trends.filter(t => t.change === "down").length}` },
      { k: "ハッシュタグ", v: tagCount, s: `通常ワード ${trends.length - tagCount}` },
      { k: "合計投稿数", v: compact(totalVol), s: `平均 ${trends.length ? compact(Math.round(totalVol / trends.length)) : "–"}` },
    ];
    for (const x of kpis) {
      kpi.append(el("div", { class: "kpi" }, [
        el("div", { class: "k", text: x.k }),
        el("div", { class: "v", text: String(x.v) }),
        el("div", { class: "s", text: x.s }),
      ]));
    }

    // カテゴリ
    catBox.innerHTML = "";
    const catItems = (cats.items || []).map(i => ({
      label: i.meta?.ja || catMeta(i.category).ja,
      value: i.count, color: i.meta?.color || catMeta(i.category).color,
      icon: i.meta?.icon || catMeta(i.category).icon,
    }));
    if (catItems.length) {
      const flex = el("div", { style: { display: "flex", gap: "16px", alignItems: "center", flexWrap: "wrap" } });
      flex.append(donut(catItems));
      const legend = el("div", { style: { flex: "1", minWidth: "180px" } });
      const total = catItems.reduce((s, i) => s + i.value, 0) || 1;
      for (const i of catItems) {
        legend.append(el("div", {
          style: { display: "flex", alignItems: "center", gap: "7px", fontSize: "12.5px", padding: "2px 0" },
          html: `<span style="width:9px;height:9px;border-radius:2px;background:${i.color};display:inline-block"></span>
                 <span>${i.icon || ""} ${esc(i.label)}</span>
                 <b style="margin-left:auto;font-family:var(--mono)">${i.value} <span class="muted small">(${Math.round(i.value / total * 100)}%)</span></b>`,
        }));
      }
      flex.append(legend);
      catBox.append(flex);
    } else {
      catBox.append(el("p", { class: "muted small", text: "データがありません" }));
    }

    // 粘り強い話題
    persistBox.innerHTML = "";
    const items = (top.items || []).slice(0, 12).map(i => ({
      label: i.name, value: i.persistence, color: catMeta(i.category).color,
      icon: catMeta(i.category).icon, raw: i,
    }));
    if (items.length) {
      persistBox.append(hbars(items, {
        max: 100, fmt: v => `${v}%`,
        onClick: (it) => document.dispatchEvent(new CustomEvent("xt:open-trend", { detail: { name: it.raw.name, woeid: state.woeid } })),
      }));
      persistBox.append(el("p", { class: "muted small", style: { marginTop: "8px" },
        text: `直近 ${top.hours}時間 / ${top.snapshots}スナップショット中、何割の時間ランクインしていたか` }));
    } else {
      persistBox.append(el("p", { class: "muted small", text: "履歴がまだありません" }));
    }

    // ヒートマップ
    hmBox.innerHTML = "";
    const snaps = tl.snapshots || [];
    if (snaps.length >= 3) {
      const freq = new Map();
      for (const s of snaps) for (const t of s.top) freq.set(t.name, (freq.get(t.name) || 0) + 1);
      const names = [...freq.entries()].sort((a, b) => b[1] - a[1]).slice(0, 14).map(e => e[0]);
      const cols = snaps.map(s => s.ts);
      const rows = names.map(name => {
        const values = new Map();
        for (const s of snaps) {
          const hit = s.top.find(t => t.name === name);
          if (hit) values.set(s.ts, hit.rank);
        }
        return { name, values };
      });
      hmBox.append(heatmap(rows, cols, {
        onClick: (name) => document.dispatchEvent(new CustomEvent("xt:open-trend", { detail: { name, woeid: state.woeid } })),
      }));
    } else {
      hmBox.append(el("p", { class: "muted small", text: "スナップショットが3件以上たまると表示されます。" }));
    }
  } catch (err) {
    kpi.innerHTML = "";
    kpi.append(el("p", { class: "muted", text: `取得失敗: ${err.message}` }));
  }
}

/* ================================================================== */
/* 検索                                                                */
/* ================================================================== */

export async function renderSearch(q, opts = {}) {
  document.dispatchEvent(new CustomEvent("xt:switch-view", { detail: { view: "search" } }));
  const box = $("#searchResults");
  box.innerHTML = "";
  box.append(el("div", { class: "sk", style: { height: "120px" } }));
  $("#searchMeta").textContent = `「${q}」を検索中…`;
  try {
    const res = await api.search(q, { woeid: opts.woeid ?? null, hours: opts.hours ?? 72, limit: opts.limit ?? 60 });
    box.innerHTML = "";
    $("#searchMeta").textContent =
      `「${q}」 ${res.count} 件 · 直近 ${res.hours}時間 · ${opts.woeid ? (state.locations.byWoeid.get(opts.woeid)?.name_ja || opts.woeid) : "全地域"}`;
    if (!res.count) {
      box.append(el("p", { class: "muted", text: "履歴から見つかりませんでした。収集している地域・期間を広げると見つかることがあります。" }));
      return;
    }
    const grid = el("div", { class: "trend-grid" });
    for (const r of res.results) {
      const c = catMeta(r.category);
      const loc = r.location || state.locations.byWoeid.get(r.woeid) || {};
      grid.append(el("div", {
        class: "card", style: { "--cat-color": c.color },
        onclick: () => document.dispatchEvent(new CustomEvent("xt:open-trend", { detail: { name: r.name, woeid: r.woeid } })),
      }, [
        el("div", { class: "rank" }, [el("span", { text: String(r.best_rank) }), el("span", { class: "delta", text: "best" })]),
        el("div", { class: "card-main" }, [
          el("div", { class: "card-title", html: highlight(r.name, q) }),
          el("div", { class: "card-sub" }, [
            el("span", { class: "cat", style: `color:${c.color}`, html: `${c.icon} ${c.ja}` }),
            el("span", { class: "vol", text: `${loc.name_ja || r.woeid}` }),
            el("span", { class: "vol", text: `最大 ${compact(r.max_count)}` }),
            el("span", { class: "vol", text: `${r.appearances}回観測` }),
          ]),
          el("div", { class: "card-sub", style: { marginTop: "4px" } }, [
            el("span", { text: `${mdhm(r.first_ts)} 〜 ${hhmm(r.last_ts)} JST` }),
            el("a", { href: r.url, target: "_blank", rel: "noopener", onclick: e => e.stopPropagation(), text: "Xで検索 ↗" }),
          ]),
        ]),
      ]));
    }
    box.append(grid);
  } catch (err) {
    box.innerHTML = "";
    box.append(el("p", { class: "muted", text: `検索失敗: ${err.message}` }));
  }
}
