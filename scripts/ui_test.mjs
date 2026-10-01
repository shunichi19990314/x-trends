/**
 * フロントエンドのスモークテスト（jsdom + Node）。
 * サーバを起動した状態で index.html をロードし、
 *   - JS が例外なく初期化されるか
 *   - トレンドカードが描画されるか
 *   - 各ビューの切替・操作が動くか
 * を確認する。
 *
 * 使い方:
 *   cd x-trends && python -m uvicorn app.main:app --port 8123 &
 *   BASE=http://127.0.0.1:8123 ROOT=/path/to/x-trends node ui_test.mjs
 */
import { JSDOM, VirtualConsole } from "jsdom";
import fs from "node:fs";
const nfetch = globalThis.fetch;   // Node 18+ のネイティブ fetch

const BASE = process.env.BASE || "http://127.0.0.1:8123";
const ROOT = process.env.ROOT || "/home/user/x-trends";
const STATIC = `${ROOT}/static`;

const errors = [];
const logs = [];
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => errors.push("jsdomError: " + (e.stack || e.message)));
vc.on("error", (...a) => errors.push("console.error: " + a.join(" ")));
vc.on("warn", (...a) => logs.push("warn: " + a.join(" ")));
vc.on("log", (...a) => logs.push("log: " + a.join(" ")));

const html = fs.readFileSync(`${STATIC}/index.html`, "utf8");
const dom = new JSDOM(html, {
  url: BASE + "/",
  runScripts: "outside-only",
  pretendToBeVisual: true,
  virtualConsole: vc,
});

const { window } = dom;

// --- ブラウザ API のスタブ -------------------------------------------------
let store = new Map();
try {
  // jsdom が localStorage を実装していればそれを使い、無ければ自前スタブ
  window.localStorage.setItem("__probe", "1");
  window.localStorage.removeItem("__probe");
  store = null;
} catch {
  const stub = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  };
  Object.defineProperty(window, "localStorage", { value: stub, configurable: true });
}
const kvGet = (k) => (store ? store.get(k) : window.localStorage.getItem(k));
window.matchMedia = window.matchMedia || (() => ({
  matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {},
}));
window.AudioContext = undefined;
window.Notification = class {
  static permission = "default";
  static requestPermission = async () => "granted";
};
window.URL.createObjectURL = () => "blob:stub";
window.URL.revokeObjectURL = () => {};
window.navigator.share = undefined;
window.scrollTo = () => {};
window.Element.prototype.scrollIntoView = () => {};
window.SVGElement.prototype.getBoundingClientRect = function () {
  return { x: 0, y: 0, top: 0, left: 0, right: 460, bottom: 170, width: 460, height: 170 };
};

// --- グローバル化 ----------------------------------------------------------
for (const key of ["window", "document", "navigator", "location", "Element", "SVGElement",
                   "Node", "Event", "CustomEvent", "MouseEvent", "KeyboardEvent", "Blob",
                   "URL", "Notification", "getComputedStyle", "HTMLElement"]) {
  try { if (window[key] !== undefined) globalThis[key] = window[key]; } catch {}
}
globalThis.window = window;
globalThis.document = window.document;
globalThis.navigator = window.navigator;
globalThis.location = window.location;
globalThis.localStorage = window.localStorage;
// jsdom の fetch は相対URLを解決できないため、Node の fetch で絶対URL化して叩く
globalThis.fetch = (u, o) => nfetch(new URL(u, BASE).toString(), o);
try { Object.defineProperty(window, "fetch", { value: globalThis.fetch, configurable: true, writable: true }); } catch {}
globalThis.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0);
globalThis.cancelAnimationFrame = (id) => clearTimeout(id);

const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const $ = (s) => window.document.querySelector(s);
const $$ = (s) => [...window.document.querySelectorAll(s)];

const results = [];
function check(name, cond, extra = "") {
  results.push({ name, ok: !!cond });
  console.log(`${cond ? "✅" : "❌"} ${name}${extra ? "  " + extra : ""}`);
}

try {
  await import(`${STATIC}/js/app.js`);
} catch (e) {
  console.log("❌ app.js の import に失敗:", e);
  process.exit(1);
}

for (let i = 0; i < 60; i++) {
  await sleep(250);
  if ($$("#trendList .card").length > 0) break;
}

check("初期化でJSエラーなし", errors.length === 0, errors.slice(0, 2).join(" | "));
check("プロバイダバッジ表示", !!$("#providerBadge")?.textContent?.trim(), $("#providerBadge")?.textContent);

const cards = $$("#trendList .card");
check("トレンドカードが描画された", cards.length >= 20, `${cards.length} 枚`);
check("地域タイトルが入った", /トレンド/.test($("#locTitle")?.textContent || ""), $("#locTitle")?.textContent);
check("サイドバーに地域が並んだ", $$("#locList .loc-item").length > 50, `${$$("#locList .loc-item").length} 地域`);
check("カテゴリチップが出た", $$("#catChips .chip").length >= 2, `${$$("#catChips .chip").length} 個`);
check("スパークラインSVG", $$("#trendList svg.spark").length > 0, `${$$("#trendList svg.spark").length} 本`);
check("最終更新ラベル", !!$("#lastUpdated")?.textContent?.trim(), $("#lastUpdated")?.textContent);

// --- ドロワー ---
cards[0].dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
await sleep(1800);
check("ドロワーが開く", $("#drawer")?.classList.contains("is-open"));
check("ドロワーに詳細が出た", ($("#drawerBody")?.textContent || "").length > 40, ($("#drawerBody h2")?.textContent || "").slice(0, 30));
check("詳細チャート(SVG)が描画", $$("#drawerBody svg").length >= 1, `${$$("#drawerBody svg").length} 本`);
$("#drawerClose").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
await sleep(250);
check("ドロワーが閉じる", !$("#drawer")?.classList.contains("is-open"));

// --- カテゴリ絞り込み ---
const chip = $$("#catChips .chip")[1];
if (chip) {
  const before = $$("#trendList .card").length;
  chip.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await sleep(400);
  check("カテゴリ絞り込みで件数が変わる", $$("#trendList .card").length !== before,
    `${before} → ${$$("#trendList .card").length}`);
  chip.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await sleep(300);
}

// --- ソート ---
const volBtn = $$("#sortSeg button").find(b => b.dataset.sort === "volume");
volBtn.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
await sleep(400);
check("投稿数順ソート", volBtn.classList.contains("is-active"));

// --- 検索 ---
$("#globalSearch").value = "AI";
$("#globalSearch").dispatchEvent(new window.Event("input", { bubbles: true }));
await sleep(2600);
check("グローバル検索ビューに切替", $("#view-search")?.classList.contains("is-active"));
check("検索結果が出た", $$("#searchResults .card").length > 0, `${$$("#searchResults .card").length} 件`);
check("検索メタ文言", /AI/.test($("#searchMeta")?.textContent || ""), $("#searchMeta")?.textContent);

// --- タブ ---
for (const [tab, view, probeSel] of [
  ["timeline", "#view-timeline", ".tl-row"],
  ["compare", "#view-compare", ".cmp-col"],
  ["analytics", "#view-analytics", ".kpi"],
]) {
  const btn = $$(".tab").find(t => t.dataset.view === tab);
  btn.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
  await sleep(2400);
  check(`${tab} ビュー描画`, $(view)?.classList.contains("is-active") && $$(probeSel).length > 0,
    `${$$(probeSel).length} 要素`);
}

check("KPI 4つ", $$("#kpiRow .kpi").length === 4, String($$("#kpiRow .kpi").length));
check("ドーナツチャート", $$("#catChart svg").length >= 1);
check("ヒートマップ", $$("#heatmap table.hm").length === 1 || /スナップショット/.test($("#heatmap")?.textContent || ""));
check("粘り話題バー", $$("#persistChart .bar-row").length > 0, `${$$("#persistChart .bar-row").length} 本`);

// --- 地域切替 ---
$$(".tab").find(t => t.dataset.view === "board").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
await sleep(500);
const tokyo = $$("#locList .loc-item").find(b => b.textContent.includes("東京"));
tokyo.dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
await sleep(2400);
check("地域切替（東京）", /東京/.test($("#locTitle")?.textContent || ""), $("#locTitle")?.textContent);

// --- 通知 ---
$("#btnBell").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
await sleep(400);
check("通知パネルが開く", !$("#bellPopover").hidden);
const kw = $$("#trendList .card .card-title")[0]?.textContent || "AI";
$("#notifKeyword").value = kw;
$("#notifAdd").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
await sleep(400);
const kwStored = kvGet("xtrends:keywords") || "";
check("キーワード追加", kwStored.length > 2, kwStored.slice(0, 90));
$("#bellClose").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));

// --- 設定 ---
$("#btnSettings").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
await sleep(1500);
check("設定モーダルが開く", !$("#settingsModal").hidden);
check("プロバイダ情報", /データソース/.test($("#providerInfo")?.textContent || ""));
check("監視地域エディタ", $$("#watchEditor .watch-row").length > 5, `${$$("#watchEditor .watch-row").length} 行`);
$("#settingsClose").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
await sleep(300);

// --- テーマ ---
$("#btnTheme").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
await sleep(200);
check("テーマ切替(light)", window.document.documentElement.dataset.theme === "light", window.document.documentElement.dataset.theme);
$("#btnTheme").dispatchEvent(new window.MouseEvent("click", { bubbles: true }));
await sleep(200);

await sleep(600);
check("操作を通じてJSエラーなし", errors.length === 0, errors.slice(0, 3).join(" | "));

const failed = results.filter(r => !r.ok);
console.log("\n" + (failed.length ? `❌ ${failed.length} 件失敗` : "🎉 全UIテスト合格"));
if (logs.length) console.log("--- console ---\n" + logs.slice(0, 10).join("\n"));
process.exit(failed.length ? 1 : 0);
