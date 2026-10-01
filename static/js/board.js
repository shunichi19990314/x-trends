/* トレンド一覧（ボード）と詳細ドロワー */

import { $, el, esc, compact, fullNum, hhmm, mdhm, ago, highlight, copyText, toast } from "./util.js";
import { sparkline, lineChart } from "./charts.js";
import { api } from "./api.js";
import { state, catMeta, savePrefs } from "./state.js";

let maxCount = 1;

/* ------------------------------------------------------------------ */
/* カテゴリチップ                                                       */
/* ------------------------------------------------------------------ */

export function renderChips() {
  const wrap = $("#catChips");
  if (!wrap) return;
  wrap.innerHTML = "";
  const counts = new Map();
  for (const t of state.snapshot?.trends || []) {
    counts.set(t.category, (counts.get(t.category) || 0) + 1);
  }
  const all = el("button", {
    class: "chip" + (state.catFilter.size === 0 ? " is-active" : ""),
    html: `すべて <span class="n">${state.snapshot?.trends?.length || 0}</span>`,
    onclick: () => { state.catFilter.clear(); savePrefs(); renderChips(); renderList(); },
  });
  wrap.append(all);

  for (const c of state.categories) {
    const n = counts.get(c.id) || 0;
    if (!n) continue;
    const active = state.catFilter.has(c.id);
    wrap.append(el("button", {
      class: "chip" + (active ? " is-active" : ""),
      style: active ? `background:${c.color};border-color:${c.color}` : `color:${c.color}`,
      html: `${c.icon} ${c.ja} <span class="n">${n}</span>`,
      onclick: () => {
        if (active) state.catFilter.delete(c.id); else state.catFilter.add(c.id);
        savePrefs(); renderChips(); renderList();
      },
    }));
  }
}

/* ------------------------------------------------------------------ */
/* フィルタ + ソート                                                    */
/* ------------------------------------------------------------------ */

function normalizeName(name) {
  return name.toLowerCase()
    .replace(/^[#\s]+/, "")
    .replace(/[・･\s]/g, "")
    .replace(/[！!？?。，,\.]/g, "");
}

export function filteredTrends() {
  let items = [...(state.snapshot?.trends || [])];
  const q = state.textFilter.trim().toLowerCase();

  if (state.catFilter.size) items = items.filter(t => state.catFilter.has(t.category));
  if (state.onlyNew) items = items.filter(t => t.change === "new");
  if (state.onlyHashtag) items = items.filter(t => t.name.startsWith("#"));
  if (q) items = items.filter(t => t.name.toLowerCase().includes(q));

  if (state.hideDup) {
    const seen = new Map();
    items = items.filter((t) => {
      const k = normalizeName(t.name);
      if (seen.has(k)) return false;
      seen.set(k, true);
      return true;
    });
  }

  switch (state.sort) {
    case "volume":
      items.sort((a, b) => (b.tweet_count || 0) - (a.tweet_count || 0));
      break;
    case "rising":
      items.sort((a, b) => {
        const sa = a.change === "new" ? 1e9 : (a.rank_delta || 0) * 1000 + (a.momentum_pct || 0);
        const sb = b.change === "new" ? 1e9 : (b.rank_delta || 0) * 1000 + (b.momentum_pct || 0);
        return sb - sa;
      });
      break;
    case "name":
      items.sort((a, b) => a.name.localeCompare(b.name, "ja"));
      break;
    default:
      items.sort((a, b) => a.rank - b.rank);
  }
  return items.slice(0, state.limit);
}

/* ------------------------------------------------------------------ */
/* カード                                                              */
/* ------------------------------------------------------------------ */

function deltaMark(t) {
  if (t.change === "new") return el("span", { class: "delta new", text: "NEW" });
  if (t.change === "up") return el("span", { class: "delta up", html: `▲${t.rank_delta}` });
  if (t.change === "down") return el("span", { class: "delta down", html: `▼${Math.abs(t.rank_delta)}` });
  return el("span", { class: "delta same", text: "–" });
}

export function card(t, idx) {
  const c = catMeta(t.category);
  const pct = t.tweet_count ? Math.max(2, Math.round((t.tweet_count / maxCount) * 100)) : 0;
  const rankCls = t.rank === 1 ? "top1" : t.rank === 2 ? "top2" : t.rank === 3 ? "top3" : "";

  const sub = el("div", { class: "card-sub" }, [
    el("span", { class: "cat", style: `color:${c.color}`, html: `${c.icon} ${c.ja}` }),
    el("span", { class: "vol", text: t.tweet_count ? `${compact(t.tweet_count)} 投稿` : "投稿数 非公開" }),
    t.momentum_pct != null && Math.abs(t.momentum_pct) >= 5
      ? el("span", { class: `mom ${t.momentum_pct > 0 ? "up" : "down"}`, text: `${t.momentum_pct > 0 ? "+" : ""}${t.momentum_pct}%` })
      : null,
    t.change === "new" ? el("span", { class: "delta new", text: "初登場" }) : null,
    t.also_trending_in?.length
      ? el("span", { class: "also", title: "他地域でもトレンド", text: `+${t.also_trending_in.length}地域` })
      : null,
  ]);

  const card = el("div", {
    class: "card", style: { "--cat-color": c.color }, role: "button", tabindex: "0",
    title: `${t.name}\nランク ${t.rank}位 / ${t.tweet_count ? fullNum(t.tweet_count) + " 投稿" : "投稿数不明"}`,
    onclick: () => openDrawer(t),
    onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDrawer(t); } },
  }, [
    el("div", { class: `rank ${rankCls}` }, [el("span", { text: String(t.rank) }), deltaMark(t)]),
    el("div", { class: "card-main" }, [
      el("div", { class: "card-title", html: highlight(t.name, state.textFilter) }),
      sub,
      (t.sparkline?.length > 1) ? sparkline(t.sparkline, { color: c.color, value: "rank" }) : null,
      t.tweet_count ? el("div", { class: "bar-track" }, el("div", { class: "bar-fill", style: { width: pct + "%" } })) : null,
    ]),
  ]);
  return card;
}

export function renderList() {
  const list = $("#trendList");
  const empty = $("#boardEmpty");
  if (!list) return;
  const items = filteredTrends();
  maxCount = Math.max(1, ...items.map(t => t.tweet_count || 0));
  list.innerHTML = "";
  if (!items.length) {
    empty.hidden = false;
    $("#trendCount").textContent = "0 件";
    return;
  }
  empty.hidden = true;
  const frag = document.createDocumentFragment();
  items.forEach((t, i) => frag.append(card(t, i)));
  list.append(frag);
  $("#trendCount").textContent = `${items.length} 件表示`;
}

export function renderBoardHeader(snap) {
  const loc = snap.location || {};
  $("#locTitle").textContent = loc.name_ja ? `${loc.name_ja} のトレンド` : "トレンド";
  const bits = [];
  if (loc.name && loc.name !== loc.name_ja) bits.push(loc.name);
  if (loc.place_type_ja) bits.push(loc.place_type_ja);
  bits.push(`WOEID ${snap.location?.woeid ?? loc.woeid ?? "-"}`);
  bits.push(`取得 ${ago(snap.age_seconds)} (${hhmm(snap.ts)} JST)`);
  bits.push(`${snap.count} 件`);
  bits.push(`source: ${snap.source || "-"} / ${snap.provider || "-"}`);
  $("#locMeta").textContent = bits.join(" · ");
  const csv = $("#btnCsv");
  if (csv) csv.href = api.online ? api.csvUrl(loc.woeid) : "#";
}

export function renderSkeleton(n = 12) {
  const list = $("#trendList");
  if (!list) return;
  list.innerHTML = "";
  for (let i = 0; i < n; i++) list.append(el("div", { class: "sk sk-card" }));
}

/* ------------------------------------------------------------------ */
/* 詳細ドロワー                                                         */
/* ------------------------------------------------------------------ */

let drawerTrend = null;

export async function openDrawer(trend) {
  drawerTrend = trend;
  const body = $("#drawerBody");
  const drawer = $("#drawer");
  const backdrop = $("#drawerBackdrop");
  body.innerHTML = "";
  drawer.classList.add("is-open");
  drawer.setAttribute("aria-hidden", "false");
  backdrop.hidden = false;

  const c = catMeta(trend.category);
  const loc = state.snapshot?.location || {};

  body.append(el("h2", { text: trend.name }));
  body.append(el("div", { class: "dmeta" }, [
    el("span", { class: "chip is-active", style: `background:${c.color};border-color:${c.color}`, html: `${c.icon} ${c.ja}` }),
    el("span", { class: "chip", text: `${loc.name_ja || ""} ${trend.rank}位` }),
    trend.change === "new" ? el("span", { class: "chip", style: "color:var(--new);border-color:var(--new)", text: "NEW 初登場" }) : null,
    trend.age_minutes != null ? el("span", { class: "chip", text: `観測 ${Math.round(trend.age_minutes / 60)}時間` }) : null,
  ]));

  const stats = el("div", { class: "dstat" }, [
    el("div", {}, [el("div", { class: "k", text: "現在の投稿数" }), el("div", { class: "v", text: trend.tweet_count ? compact(trend.tweet_count) : "–" })]),
    el("div", {}, [el("div", { class: "k", text: "24h平均" }), el("div", { class: "v", text: trend.avg_count_24h ? compact(trend.avg_count_24h) : "–" })]),
    el("div", {}, [el("div", { class: "k", text: "最高ランク" }), el("div", { class: "v", text: "…" })]),
    el("div", {}, [el("div", { class: "k", text: "出現回数" }), el("div", { class: "v", text: "…" })]),
  ]);
  body.append(stats);

  body.append(el("div", { class: "actions" }, [
    el("a", { class: "btn btn-primary", href: trend.url || `https://x.com/search?q=${encodeURIComponent(trend.name)}`, target: "_blank", rel: "noopener", text: "X で見る" }),
    el("button", { class: "btn", text: "名前をコピー", onclick: async () => toast(await copyText(trend.name) ? "コピーしました" : "コピー失敗", "ok") }),
    el("button", { class: "btn", text: "検索URLをコピー", onclick: async () => toast(await copyText(trend.url || "") ? "コピーしました" : "コピー失敗", "ok") }),
    el("button", { class: "btn", text: "🔔 通知する", onclick: () => notifyFromDrawer(trend) }),
  ]));

  const chartBox = el("div", { class: "bigchart" }, [el("h4", { text: "投稿数の推移（24時間）" })]);
  const rankBox = el("div", { class: "bigchart" }, [el("h4", { text: "ランクの推移（24時間）" })]);
  const alsoBox = el("div", { class: "bigchart" }, [el("h4", { text: "関連情報" })]);
  body.append(chartBox, rankBox, alsoBox);

  alsoBox.append(el("div", { class: "kv" }, [
    el("div", {}, [el("span", { text: "カテゴリ" }), el("b", { text: `${c.icon} ${c.ja}` })]),
    el("div", {}, [el("span", { text: "初出" }), el("b", { text: trend.first_seen_ts ? mdhm(trend.first_seen_ts) + " JST" : "–" })]),
    el("div", {}, [el("span", { text: "勢い（24h平均比）" }), el("b", { text: trend.momentum_pct == null ? "–" : `${trend.momentum_pct > 0 ? "+" : ""}${trend.momentum_pct}%` })]),
    el("div", {}, [el("span", { text: "他地域でもトレンド" }), el("b", { text: (trend.also_trending_in || []).length ? trend.also_trending_in.map(w => state.locations.byWoeid.get(w)?.name_ja || w).join(", ") : "なし" })]),
  ]));

  // 履歴取得
  try {
    const hist = await api.history(loc.woeid ?? state.woeid, trend.name, state.sparkHours);
    const vals = stats.querySelectorAll(".v");
    vals[2].textContent = hist.summary.best_rank ? `${hist.summary.best_rank}位` : "–";
    vals[3].textContent = String(hist.summary.appearances);

    chartBox.append(lineChart(hist.points, { value: "count", color: "#4f9dff", yLabel: "投稿数" }));
    rankBox.append(lineChart(hist.points, { value: "rank", color: "#f472b6", yLabel: "ランク", areaFill: false }));

    if (hist.summary.max_count) {
      alsoBox.append(el("div", { class: "kv", style: { marginTop: "10px" } }, [
        el("div", {}, [el("span", { text: "最大投稿数" }), el("b", { text: fullNum(hist.summary.max_count) })]),
        el("div", {}, [el("span", { text: "最小投稿数" }), el("b", { text: fullNum(hist.summary.min_count) })]),
        el("div", {}, [el("span", { text: "平均投稿数" }), el("b", { text: fullNum(hist.summary.avg_count) })]),
      ]));
    }
  } catch (err) {
    chartBox.append(el("p", { class: "muted small", text: `履歴を取得できませんでした: ${err.message}` }));
  }
}

function notifyFromDrawer(trend) {
  const loc = state.snapshot?.location || {};
  const woeid = loc.woeid ?? state.woeid;
  const exists = state.keywords.some(k => k.woeid === woeid && k.kw === trend.name);
  if (exists) { toast("このキーワードは既に登録済みです", "info"); return; }
  state.keywords.push({ woeid, kw: trend.name, added: Date.now() });
  savePrefs();
  toast(`「${trend.name}」を通知キーワードに追加しました`, "ok");
  document.dispatchEvent(new CustomEvent("xt:keywords-changed"));
}

export function closeDrawer() {
  drawerTrend = null;
  $("#drawer").classList.remove("is-open");
  $("#drawer").setAttribute("aria-hidden", "true");
  $("#drawerBackdrop").hidden = true;
}

export function currentDrawerTrend() { return drawerTrend; }
