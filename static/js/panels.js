/* 通知パネル・設定モーダル・監視地域エディタ */

import { $, $$, el, esc, hhmm, mdhm, ago, toast, chime } from "./util.js";
import { api } from "./api.js";
import { state, savePrefs } from "./state.js";

/* ================================================================== */
/* 通知                                                                */
/* ================================================================== */

export function renderNotifPanel() {
  const locSel = $("#notifLoc");
  if (locSel) {
    locSel.innerHTML = "";
    for (const g of state.locations.groups) {
      const og = el("optgroup", { label: g.label });
      for (const l of g.locations) og.append(el("option", { value: String(l.woeid), text: l.name_ja, selected: l.woeid === state.woeid }));
      locSel.append(og);
    }
  }
  $("#notifEnableBrowser").checked = !!state.browserNotif;
  $("#notifSound").checked = !!state.sound;
  renderKeywords();
  renderNotifLog();
  updateBellDot();
}

function renderKeywords() {
  const box = $("#notifList");
  if (!box) return;
  box.innerHTML = "";
  if (!state.keywords.length) {
    box.append(el("p", { class: "muted small", text: "キーワード未登録。例: 「大谷」「地震」「ChatGPT」" }));
    return;
  }
  box.append(el("div", { class: "muted small", style: { marginBottom: "4px" }, text: "登録中のキーワード" }));
  for (const k of state.keywords) {
    const locName = state.locations.byWoeid.get(k.woeid)?.name_ja || k.woeid;
    box.append(el("div", { class: "notif-item" }, [
      el("span", { class: "kw", text: k.kw }),
      el("span", { class: "muted small", text: locName }),
      el("button", {
        title: "削除", html: "✕",
        onclick: () => {
          state.keywords = state.keywords.filter(x => x !== k);
          savePrefs(); renderKeywords(); syncServerKeywords();
        },
      }),
    ]));
  }
}

function renderNotifLog() {
  const box = $("#notifList");
  if (!box) return;
  if (!state.notifLog.length) return;
  box.append(el("div", { class: "muted small", style: { margin: "12px 0 4px" }, text: "検知ログ" }));
  for (const e of state.notifLog.slice(0, 30)) {
    box.append(el("div", { class: "notif-item" }, [
      el("span", { class: "kw", text: e.name }),
      el("span", { class: "muted small", text: `${e.loc} ${e.rank ? e.rank + "位" : ""} ${e.count ? "· " + e.count.toLocaleString("ja-JP") : ""}` }),
      el("span", { class: "when", text: mdhm(e.ts) }),
    ]));
  }
  box.append(el("button", {
    class: "btn btn-tiny", style: { marginTop: "8px" }, text: "ログをクリア",
    onclick: () => { state.notifLog = []; savePrefs(); renderNotifLog(); },
  }));
}

export function updateBellDot() {
  const dot = $("#bellDot");
  if (dot) dot.hidden = state.notifLog.length === 0;
}

export function addKeyword(woeid, kw) {
  kw = (kw || "").trim();
  if (!kw) return false;
  if (state.keywords.some(k => k.woeid === woeid && k.kw === kw)) {
    toast("同じキーワードは登録済みです", "info");
    return false;
  }
  state.keywords.push({ woeid, kw, added: Date.now() });
  savePrefs(); renderKeywords(); syncServerKeywords();
  toast(`「${kw}」を通知に追加しました`, "ok");
  return true;
}

export async function syncServerKeywords() {
  if (!api.online) return;
  const map = {};
  for (const k of state.keywords) {
    (map[k.woeid] = map[k.woeid] || []).push(k.kw);
  }
  try { await api.setServerKeywords(map); } catch { /* 無視 */ }
}

/** スナップショットからキーワード一致を判定して通知する */
export function checkNotifications(snap) {
  if (!snap?.trends) return;
  const woeid = snap.location?.woeid ?? state.woeid;
  const mine = state.keywords.filter(k => k.woeid === woeid);
  if (!mine.length) return;

  const seen = state.seenNames.get(woeid) || new Set();
  let fired = 0;

  for (const t of snap.trends) {
    for (const k of mine) {
      if (!t.name.toLowerCase().includes(k.kw.toLowerCase())) continue;
      const key = `${k.kw}|${t.name}|${Math.floor(snap.ts / 1800)}`;   // 30分単位で重複抑止
      if (seen.has(key)) continue;
      seen.add(key);
      fired++;
      const entry = {
        ts: snap.ts, woeid, loc: snap.location?.name_ja || String(woeid),
        kw: k.kw, name: t.name, rank: t.rank, count: t.tweet_count,
      };
      state.notifLog.unshift(entry);
      if (state.browserNotif && "Notification" in window && Notification.permission === "granted") {
        try {
          new Notification(`Xトレンド: ${t.name}`, {
            body: `${entry.loc} ${t.rank}位${t.tweet_count ? " · " + t.tweet_count.toLocaleString("ja-JP") + "投稿" : ""}`,
            tag: key, icon: "/favicon.svg",
          });
        } catch { /* iOS等では無視 */ }
      }
      if (state.sound) chime();
      toast(`🔔 ${entry.loc}で「${t.name}」が ${t.rank}位`, "info", 5200);
    }
  }
  state.notifLog = state.notifLog.slice(0, 200);
  state.seenNames.set(woeid, seen);
  if (fired) { savePrefs(); renderNotifLog(); updateBellDot(); }
}

export async function requestBrowserNotif(checkbox) {
  if (!("Notification" in window)) {
    toast("このブラウザは通知に対応していません", "err");
    checkbox.checked = false; state.browserNotif = false; savePrefs();
    return;
  }
  if (Notification.permission === "granted") {
    state.browserNotif = true; savePrefs(); return;
  }
  const p = await Notification.requestPermission();
  state.browserNotif = p === "granted";
  checkbox.checked = state.browserNotif;
  savePrefs();
  toast(state.browserNotif ? "ブラウザ通知を許可しました" : "通知が許可されませんでした", state.browserNotif ? "ok" : "err");
}

/* ================================================================== */
/* 設定モーダル                                                         */
/* ================================================================== */

export async function openSettings() {
  $("#settingsModal").hidden = false;
  await Promise.all([renderProviderInfo(), renderWatchEditor(), renderStatusBox()]);
  $("#cfgInterval").value = String(state.intervalSec);
  $("#cfgLimit").value = String(state.limit);
  $("#cfgSpark").value = String(state.sparkHours);
  $("#cfgToken").value = state.token;
}

export function closeSettings() { $("#settingsModal").hidden = true; }

async function renderProviderInfo() {
  const box = $("#providerInfo");
  if (!box) return;
  let st;
  try { st = await api.status(); } catch { st = null; }
  const cfg = st?.config || {};
  const rows = [
    ["バックエンド接続", api.online ? "オンライン" : "オフライン（ブラウザ内デモ）"],
    ["データソース", label(cfg.provider)],
    ["X Bearer Token", cfg.has_x_token ? "設定済み ✅" : "未設定"],
    ["TwitterAPI.io Key", cfg.has_twitterapi_key ? "設定済み ✅" : "未設定"],
    ["サーバ側ポーラー", cfg.poller_enabled ? `ON（${cfg.poll_interval}分ごと）` : "OFF"],
    ["履歴保持", `${cfg.history_days ?? "-"}日`],
  ];
  box.innerHTML = "";
  for (const [k, v] of rows) box.append(el("div", {}, [el("span", { text: k }), el("b", { text: v })]));
}

function label(p) {
  return { official: "公式 X API v2", twitterapiio: "TwitterAPI.io（代替）", demo: "デモ（合成データ）" }[p] || p || "不明";
}

async function renderStatusBox() {
  const box = $("#statusBox");
  if (!box) return;
  try {
    const st = await api.status();
    const p = st.poller || {};
    box.innerHTML = "";
    const rows = [
      ["最終収集", p.last_run ? mdhm(p.last_run) + " JST" : "–"],
      ["収集サイクル数", String(p.cycles ?? 0)],
      ["API呼び出し回数", String(p.api_calls ?? 0)],
      ["直近エラー", p.last_error || "なし"],
      ["DBの地域数", String(st.db_locations ?? 0)],
    ];
    for (const [k, v] of rows) box.append(el("div", {}, [el("span", { text: k }), el("b", { text: v })]));
  } catch (err) {
    box.innerHTML = "";
    box.append(el("div", {}, [el("span", { text: "ステータス" }), el("b", { text: err.message })]));
  }
}

async function renderWatchEditor() {
  const box = $("#watchEditor");
  if (!box) return;
  box.innerHTML = "";
  const current = new Set(state.watch || []);

  // よく使う地域だけ並べる（全件は検索で追加）
  const quick = [1, 23424856, 1118370, 15015372, 1117642, 1117561, 1116957,
                 23424977, 2459115, 2442047, 23424975, 44418, 23424829, 638242,
                 23424819, 615702, 23424768, 455825, 23424848, 2295411,
                 1132599, 23424781, 1257801, 1062617, 23424755, 1100661];

  for (const w of quick) {
    const loc = state.locations.byWoeid.get(w);
    if (!loc) continue;
    const row = el("label", { class: "watch-row" }, [
      el("input", {
        type: "checkbox", checked: current.has(w),
        onchange: async (e) => {
          if (e.target.checked) current.add(w); else current.delete(w);
          await applyWatch([...current]);
        },
      }),
      el("span", { text: `${loc.name_ja} (${loc.name})` }),
      el("span", { class: "muted small", style: { marginLeft: "auto" }, text: loc.place_type_ja }),
    ]);
    box.append(row);
  }

  const addRow = el("div", { class: "watch-add" });
  const input = el("input", { type: "text", placeholder: "地域名で検索して追加（例: 仙台 / Berlin）" });
  const results = el("div", { class: "loc-results", style: { position: "static", marginTop: "6px" } });
  const btn = el("button", { class: "btn btn-tiny", text: "検索", onclick: doSearch });
  addRow.append(input, btn);
  box.append(addRow, results);

  async function doSearch() {
    const q = input.value.trim();
    if (!q) return;
    const res = await api.locations(q);
    results.innerHTML = "";
    for (const loc of (res.results || []).slice(0, 8)) {
      results.append(el("button", {
        onclick: async () => {
          current.add(loc.woeid);
          await applyWatch([...current]);
          results.innerHTML = ""; input.value = "";
          toast(`${loc.name_ja} を監視に追加しました`, "ok");
        },
      }, [el("span", { text: `${loc.name_ja} (${loc.name})` }), el("span", { class: "muted small", text: String(loc.woeid) })]));
    }
    if (!(res.results || []).length) results.append(el("div", { class: "muted small", style: { padding: "6px" }, text: "見つかりません" }));
    results.hidden = false;
  }
  input.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); doSearch(); } });
}

async function applyWatch(woeids) {
  state.watch = woeids;
  savePrefs();
  try {
    await api.setWatch(woeids);
    if (api.online) { await api.refresh().catch(() => {}); }
  } catch (err) {
    toast(`監視地域の更新に失敗: ${err.message}`, "err");
  }
  document.dispatchEvent(new CustomEvent("xt:watch-changed"));
  renderStatusBox();
}

export { renderStatusBox, label as providerLabel };
