/* エントリポイント：初期化・イベント配線・自動更新 */

import { $, $$, el, toast, copyText, debounce, ago, agoShort, hhmm, compact } from "./util.js";
import { api, setToken, downloadCsv, ONLINE } from "./api.js";
import { state, savePrefs, catMeta } from "./state.js";
import * as board from "./board.js";
import * as views from "./views.js";
import * as panels from "./panels.js";

let refreshTimer = null;
let tickTimer = null;
let currentSnap = null;

/* ================================================================== */
/* 初期化                                                              */
/* ================================================================== */

async function init() {
  applyTheme();
  bindStaticEvents();

  await api.probe();
  state.online = api.online;

  try {
    if (state.token) setToken(state.token);
    state.config = await api.config();
    if (state.config?.categories?.length) state.categories = state.config.categories;
    if (!state.watch && state.config?.watch?.length) state.watch = state.config.watch;
  } catch (err) {
    console.warn("config取得失敗", err);
  }

  try {
    const locs = await api.locations();
    state.locations.groups = locs.groups || [];
    state.locations.byWoeid = new Map();
    for (const g of state.locations.groups) for (const l of g.locations) state.locations.byWoeid.set(l.woeid, l);
    if (!state.locations.byWoeid.has(state.woeid) && state.locations.byWoeid.size) {
      state.woeid = state.locations.byWoeid.has(23424856) ? 23424856 : [...state.locations.byWoeid.keys()][0];
    }
  } catch (err) {
    toast("地域一覧の取得に失敗しました: " + err.message, "err");
  }

  paintProviderBadge();
  views.renderSidebar();
  switchView(state.view, { skipRender: true });
  await loadBoard();
  startTimers();
  panels.syncServerKeywords();

  if (!api.online) {
    toast("バックエンド未接続のためブラウザ内デモデータで表示しています。uvicorn を起動すると実データになります。", "info", 7000);
  }
}

function applyTheme() {
  document.documentElement.dataset.theme = state.theme;
}

function paintProviderBadge() {
  const b = $("#providerBadge");
  const p = state.config?.provider || "demo";
  b.textContent = api.online ? p : "offline-demo";
  b.className = "badge badge-" + p;
  b.title = {
    official: "公式 X API v2 (GET /2/trends/by/woeid/{woeid}) から取得",
    twitterapiio: "TwitterAPI.io から取得",
    demo: "合成データ（APIキー未設定）",
  }[p] || p;
}

/* ================================================================== */
/* データ読み込み                                                       */
/* ================================================================== */

async function loadBoard(opts = {}) {
  const list = $("#trendList");
  if (!currentSnap || opts.hard) board.renderSkeleton();
  setConn("busy");
  state.loading = true;
  try {
    const snap = await api.trends(state.woeid, {
      hours: state.sparkHours,
      refresh: !!opts.refresh,
    });
    currentSnap = snap;
    state.snapshot = snap;
    board.renderBoardHeader(snap);
    board.renderChips();
    board.renderList();
    panels.checkNotifications(snap);
    setConn("ok");
    paintLastUpdated(snap);
    paintSidebarStats();
    document.title = `${snap.location?.name_ja || ""}トレンド — X Trends`;
  } catch (err) {
    setConn("err");
    $("#locMeta").textContent = "取得に失敗しました";
    $("#trendList").innerHTML = "";
    $("#boardEmpty").hidden = false;
    $("#boardEmpty").innerHTML = "";
    $("#boardEmpty").append(el("p", { text: `エラー: ${err.message}` }),
      el("p", { class: "muted small", style: { marginTop: "8px" },
        html: "APIキー・プラン・レート制限を確認してください。設定は右上の ⚙ から。" }));
    toast("トレンド取得に失敗: " + err.message, "err", 5000);
  } finally {
    state.loading = false;
  }
}

function paintLastUpdated(snap) {
  const node = $("#lastUpdated");
  if (!node) return;
  node.textContent = snap ? `更新 ${hhmm(snap.ts)} JST · ${ago(snap.age_seconds)}` : "";
  node.title = snap ? `取得元: ${snap.provider} / ${snap.source}` : "";
}

function paintSidebarStats() {
  $("#statWatch").textContent = String(state.watch?.length ?? "-");
  const snaps = state.snapshot ? (state.snapshot.count ?? "-") : "-";
  $("#statSnaps").textContent = String(snaps);
  scheduleNextTick();
}

function scheduleNextTick() {
  state.nextTickAt = Date.now() + state.intervalSec * 1000;
}

function setConn(kind) {
  const c = $("#connState");
  c.className = "conn " + kind;
  c.title = { ok: "接続OK", err: "エラー", busy: "取得中" }[kind] || "";
}

/* ================================================================== */
/* タイマー                                                            */
/* ================================================================== */

function startTimers() {
  clearInterval(refreshTimer);
  clearInterval(tickTimer);
  scheduleNextTick();
  refreshTimer = setInterval(() => {
    if (!state.autoRefresh) return;
    if (document.hidden) return;                    // 裏タブでは叩かない（課金対策）
    if (Date.now() < state.nextTickAt) return;
    loadBoard();
    scheduleNextTick();
    if (state.view === "timeline") views.renderTimeline();
  }, 5000);
  tickTimer = setInterval(() => {
    if (!state.autoRefresh) { $("#statNext").textContent = "OFF"; return; }
    const left = Math.max(0, Math.round((state.nextTickAt - Date.now()) / 1000));
    $("#statNext").textContent = agoShort(left);
    if (currentSnap) paintLastUpdated({ ...currentSnap, age_seconds: Math.floor(Date.now() / 1000) - currentSnap.ts });
  }, 1000);
}

/* ================================================================== */
/* ビュー切替                                                          */
/* ================================================================== */

function switchView(name, { skipRender = false } = {}) {
  state.view = name;
  savePrefs();
  $$(".tab").forEach(t => t.classList.toggle("is-active", t.dataset.view === name));
  $$(".view").forEach(v => v.classList.toggle("is-active", v.id === `view-${name}`));
  if (skipRender) return;
  if (name === "timeline") views.renderTimeline();
  else if (name === "compare") views.renderCompare();
  else if (name === "analytics") views.renderAnalytics();
}

/* ================================================================== */
/* イベント配線                                                        */
/* ================================================================== */

function bindStaticEvents() {
  // タブ
  $$(".tab").forEach(t => t.addEventListener("click", () => switchView(t.dataset.view)));

  // 更新
  $("#btnRefresh").addEventListener("click", async () => {
    const btn = $("#btnRefresh");
    btn.classList.add("spinning");
    btn.disabled = true;
    await loadBoard({ refresh: api.online });
    btn.classList.remove("spinning");
    btn.disabled = false;
    if (state.view !== "board") switchView(state.view);
    toast("更新しました", "ok", 1600);
  });

  // 自動更新
  $("#autoRefresh").checked = state.autoRefresh;
  $("#autoRefresh").addEventListener("change", e => {
    state.autoRefresh = e.target.checked; savePrefs(); scheduleNextTick();
    toast(state.autoRefresh ? `自動更新 ON（${state.intervalSec}秒ごと）` : "自動更新 OFF", "info", 1800);
  });

  // テーマ
  $("#btnTheme").addEventListener("click", () => {
    state.theme = state.theme === "dark" ? "light" : "dark";
    savePrefs(); applyTheme();
  });

  // 設定
  $("#btnSettings").addEventListener("click", () => panels.openSettings());
  $("#settingsClose").addEventListener("click", () => panels.closeSettings());
  $("#settingsModal").addEventListener("click", e => { if (e.target.id === "settingsModal") panels.closeSettings(); });
  $("#btnForceRefresh").addEventListener("click", async () => {
    $("#btnForceRefresh").disabled = true;
    try { await api.refresh(); toast("全地域の収集を実行しました", "ok"); await panels.renderStatusBox(); }
    catch (err) { toast("失敗: " + err.message, "err"); }
    $("#btnForceRefresh").disabled = false;
  });
  $("#btnOpenDocs").addEventListener("click", () => window.open("/docs", "_blank"));

  $("#cfgInterval").addEventListener("change", e => {
    state.intervalSec = Number(e.target.value); savePrefs(); scheduleNextTick();
  });
  $("#cfgLimit").addEventListener("change", e => {
    state.limit = Number(e.target.value); savePrefs(); board.renderList();
  });
  $("#cfgSpark").addEventListener("change", async e => {
    state.sparkHours = Number(e.target.value); savePrefs(); await loadBoard({ hard: true });
  });
  $("#cfgToken").addEventListener("change", e => {
    state.token = e.target.value.trim(); savePrefs(); setToken(state.token);
    toast("トークンを保存しました", "ok");
  });

  // 通知
  $("#btnBell").addEventListener("click", e => {
    e.stopPropagation();
    const p = $("#bellPopover");
    p.hidden = !p.hidden;
    if (!p.hidden) panels.renderNotifPanel();
  });
  $("#bellClose").addEventListener("click", () => { $("#bellPopover").hidden = true; });
  document.addEventListener("click", e => {
    const p = $("#bellPopover");
    if (!p.hidden && !p.contains(e.target) && !$("#btnBell").contains(e.target)) p.hidden = true;
  });
  $("#notifAdd").addEventListener("click", () => {
    const w = Number($("#notifLoc").value) || state.woeid;
    const kw = $("#notifKeyword").value;
    if (panels.addKeyword(w, kw)) $("#notifKeyword").value = "";
  });
  $("#notifKeyword").addEventListener("keydown", e => { if (e.key === "Enter") $("#notifAdd").click(); });
  $("#notifEnableBrowser").addEventListener("change", e => panels.requestBrowserNotif(e.target));
  $("#notifSound").addEventListener("change", e => { state.sound = e.target.checked; savePrefs(); });

  // 地域検索
  $("#locSearch").addEventListener("input", e => views.searchLocations(e.target.value));
  $("#locSearch").addEventListener("blur", () => setTimeout(() => { $("#locSearchResults").hidden = true; }, 180));
  $("#locSearch").addEventListener("focus", e => { if (e.target.value) views.searchLocations(e.target.value); });
  $("#btnWatchEdit").addEventListener("click", () => panels.openSettings());

  // グローバル検索
  const gs = $("#globalSearch");
  const doGlobal = debounce(() => {
    const q = gs.value.trim();
    if (!q) return;
    views.renderSearch(q);
  }, 350);
  gs.addEventListener("input", doGlobal);
  gs.addEventListener("keydown", e => {
    if (e.key === "Enter") {
      const q = gs.value.trim();
      if (q) views.renderSearch(q);
    }
    if (e.key === "Escape") { gs.blur(); }
  });

  // ボードの絞り込み
  $("#trendFilter").value = state.textFilter;
  $("#trendFilter").addEventListener("input", debounce(e => {
    state.textFilter = e.target.value; savePrefs(); board.renderList();
  }, 160));
  $("#onlyNew").checked = state.onlyNew;
  $("#onlyNew").addEventListener("change", e => { state.onlyNew = e.target.checked; savePrefs(); board.renderList(); });
  $("#onlyHashtag").checked = state.onlyHashtag;
  $("#onlyHashtag").addEventListener("change", e => { state.onlyHashtag = e.target.checked; savePrefs(); board.renderList(); });
  $("#hideDup").checked = state.hideDup;
  $("#hideDup").addEventListener("change", e => { state.hideDup = e.target.checked; savePrefs(); board.renderList(); });

  // ソート
  $$("#sortSeg button").forEach(b => {
    b.classList.toggle("is-active", b.dataset.sort === state.sort);
    b.addEventListener("click", () => {
      state.sort = b.dataset.sort; savePrefs();
      $$("#sortSeg button").forEach(x => x.classList.toggle("is-active", x === b));
      board.renderList();
    });
  });

  // CSV / 共有
  $("#btnCsv").addEventListener("click", async e => {
    if (!currentSnap) return;
    e.preventDefault();
    await downloadCsv(state.woeid, currentSnap, state.token);
    toast("CSVを書き出しました", "ok");
  });
  $("#btnShare").addEventListener("click", async () => {
    if (!currentSnap) return;
    const loc = currentSnap.location;
    const lines = [`【Xトレンド】${loc?.name_ja || ""} ${hhmm(currentSnap.ts)} JST`, ""];
    board.filteredTrends().slice(0, 20).forEach((t, i) => {
      lines.push(`${i + 1}. ${t.name}${t.tweet_count ? ` (${compact(t.tweet_count)})` : ""}`);
    });
    lines.push("", "#XTrends");
    const text = lines.join("\n");
    if (navigator.share) {
      try { await navigator.share({ title: "X Trends", text }); return; } catch { /* キャンセル等 */ }
    }
    toast(await copyText(text) ? "一覧をコピーしました" : "コピーに失敗しました", "ok");
  });

  // 推移のレンジ
  $$("#tlRange button").forEach(b => {
    b.classList.toggle("is-active", Number(b.dataset.hours) === state.timelineHours);
    b.addEventListener("click", () => {
      state.timelineHours = Number(b.dataset.hours); savePrefs();
      $$("#tlRange button").forEach(x => x.classList.toggle("is-active", x === b));
      views.renderTimeline();
    });
  });

  // 分析のレンジ
  $$("#anRange button").forEach(b => {
    b.classList.toggle("is-active", Number(b.dataset.hours) === state.analyticsHours);
    b.addEventListener("click", () => {
      state.analyticsHours = Number(b.dataset.hours); savePrefs();
      $$("#anRange button").forEach(x => x.classList.toggle("is-active", x === b));
      views.renderAnalytics();
    });
  });

  // 比較プリセット
  $$("#cmpPreset button").forEach(b => b.addEventListener("click", () => {
    $$("#cmpPreset button").forEach(x => x.classList.toggle("is-active", x === b));
    views.setComparePreset(b.dataset.preset);
  }));

  // ドロワー
  $("#drawerClose").addEventListener("click", () => board.closeDrawer());
  $("#drawerBackdrop").addEventListener("click", () => board.closeDrawer());

  // キーボードショートカット
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") { board.closeDrawer(); panels.closeSettings(); $("#bellPopover").hidden = true; }
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "");
    if (typing) return;
    if (e.key === "/") { e.preventDefault(); $("#globalSearch").focus(); }
    else if (e.key === "r" || e.key === "R") { e.preventDefault(); $("#btnRefresh").click(); }
    else if (e.key === "t" || e.key === "T") { e.preventDefault(); $("#btnTheme").click(); }
    else if (e.key === "1") switchView("board");
    else if (e.key === "2") switchView("timeline");
    else if (e.key === "3") switchView("compare");
    else if (e.key === "4") switchView("analytics");
  });

  // タブが復帰したら更新
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && state.autoRefresh) { state.nextTickAt = 0; }
  });

  // 内部イベント
  document.addEventListener("xt:location-changed", async () => {
    currentSnap = null;
    await loadBoard({ hard: true });
    if (state.view !== "board") switchView(state.view);
  });
  document.addEventListener("xt:switch-view", e => switchView(e.detail.view));
  document.addEventListener("xt:watch-changed", () => { views.renderSidebar(); paintSidebarStats(); });
  document.addEventListener("xt:keywords-changed", () => panels.renderNotifPanel());
  document.addEventListener("xt:open-trend", async (e) => openTrendByName(e.detail.name, e.detail.woeid));
}

/* タイムライン/比較からクリックされた名前だけで詳細を開く */
async function openTrendByName(name, woeid) {
  try {
    const snap = await api.trends(woeid ?? state.woeid, { hours: state.sparkHours });
    const t = snap.trends.find(x => x.name === name);
    if (t) {
      state.snapshot = snap;
      board.openDrawer(t);
    } else {
      const c = catMeta("other");
      board.openDrawer({
        name, rank: null, tweet_count: null, category: c.id, change: "same",
        rank_delta: null, momentum_pct: null, avg_count_24h: null, sparkline: [],
        also_trending_in: [], age_minutes: null, first_seen_ts: null,
        url: `https://x.com/search?q=${encodeURIComponent(name)}&src=trend_click`,
      });
      // snapshot の location を合わせないと履歴取得先がずれる
      state.snapshot = { ...state.snapshot, location: snap.location };
    }
  } catch (err) {
    toast("詳細を開けませんでした: " + err.message, "err");
  }
}

init().catch(err => {
  console.error(err);
  document.body.append(el("div", {
    class: "toast err", style: { position: "fixed", top: "12px", left: "12px", zIndex: 999 },
    text: "初期化に失敗しました: " + err.message,
  }));
});
