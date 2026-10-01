/* アプリ状態とユーザー設定の管理 */

import { store } from "./util.js";
import { CATS } from "./demo.js";

export const state = {
  online: false,
  config: null,
  categories: Object.entries(CATS).map(([id, c]) => ({ id, ...c })),
  locations: { groups: [], byWoeid: new Map() },
  woeid: store.get("woeid", 23424856),     // 既定は「日本」
  view: store.get("view", "board"),
  snapshot: null,
  loading: false,
  error: null,

  // 表示オプション
  sort: store.get("sort", "rank"),
  catFilter: new Set(store.get("catFilter", [])),
  textFilter: store.get("textFilter", ""),
  onlyNew: store.get("onlyNew", false),
  onlyHashtag: store.get("onlyHashtag", false),
  hideDup: store.get("hideDup", false),
  limit: store.get("limit", 50),
  sparkHours: store.get("sparkHours", 24),

  autoRefresh: store.get("autoRefresh", true),
  intervalSec: store.get("intervalSec", 300),
  nextTickAt: 0,

  timelineHours: store.get("timelineHours", 24),
  analyticsHours: store.get("analyticsHours", 24),
  compareIds: store.get("compareIds", [1118370, 15015372, 1117642, 1117561, 1116957]),

  watch: store.get("watch", null),         // null = サーバに従う
  theme: store.get("theme", "dark"),
  token: store.get("token", ""),

  // 通知
  keywords: store.get("keywords", []),     // [{woeid, kw, added}]
  browserNotif: store.get("browserNotif", false),
  sound: store.get("sound", true),
  seenNames: new Map(),                    // woeid -> Set(name) 既読
  notifLog: store.get("notifLog", []),     // [{ts, woeid, loc, kw, name, rank, count}]
};

export function savePrefs() {
  store.set("woeid", state.woeid);
  store.set("view", state.view);
  store.set("sort", state.sort);
  store.set("catFilter", [...state.catFilter]);
  store.set("textFilter", state.textFilter);
  store.set("onlyNew", state.onlyNew);
  store.set("onlyHashtag", state.onlyHashtag);
  store.set("hideDup", state.hideDup);
  store.set("limit", state.limit);
  store.set("sparkHours", state.sparkHours);
  store.set("autoRefresh", state.autoRefresh);
  store.set("intervalSec", state.intervalSec);
  store.set("timelineHours", state.timelineHours);
  store.set("analyticsHours", state.analyticsHours);
  store.set("compareIds", state.compareIds);
  store.set("watch", state.watch);
  store.set("theme", state.theme);
  store.set("token", state.token);
  store.set("keywords", state.keywords);
  store.set("browserNotif", state.browserNotif);
  store.set("sound", state.sound);
  store.set("notifLog", state.notifLog.slice(0, 200));
}

export function catMeta(id) {
  const found = state.categories.find(c => c.id === id);
  return found || { id: id || "other", ja: "その他", icon: "✨", color: "#64748b" };
}

export function locationLabel(woeid) {
  const l = state.locations.byWoeid.get(Number(woeid));
  return l ? l.name_ja : String(woeid);
}

export function locationOf(woeid) {
  return state.locations.byWoeid.get(Number(woeid)) || null;
}

export function addNotif(entry) {
  state.notifLog.unshift(entry);
  state.notifLog = state.notifLog.slice(0, 200);
  savePrefs();
}
