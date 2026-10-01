/* ユーティリティ：整形・DOM・トースト・保存 */

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") Object.assign(node.style, v);
    else node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return node;
}

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------- 数値・時刻 ---------- */

const JFT = new Intl.DateTimeFormat("ja-JP", {
  timeZone: "Asia/Tokyo", hour: "2-digit", minute: "2-digit", hour12: false,
});
const JFDM = new Intl.DateTimeFormat("ja-JP", {
  timeZone: "Asia/Tokyo", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false,
});
const JFD = new Intl.DateTimeFormat("ja-JP", {
  timeZone: "Asia/Tokyo", year: "numeric", month: "short", day: "numeric", weekday: "short",
});

export const hhmm = (ts) => JFT.format(new Date(ts * 1000));
export const mdhm = (ts) => JFDM.format(new Date(ts * 1000));
export const ymd = (ts) => JFD.format(new Date(ts * 1000));

export function compact(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return "–";
  n = Number(n);
  if (n >= 1e8) return (n / 1e8).toFixed(1).replace(/\.0$/, "") + "億";
  if (n >= 1e4) return (n / 1e4).toFixed(1).replace(/\.0$/, "") + "万";
  if (n >= 1000) return n.toLocaleString("ja-JP");
  return String(n);
}

export function fullNum(n) {
  if (n === null || n === undefined) return "不明";
  return Number(n).toLocaleString("ja-JP");
}

export function ago(seconds) {
  if (seconds === null || seconds === undefined) return "–";
  seconds = Math.max(0, Math.floor(seconds));
  if (seconds < 45) return "たった今";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分前`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}時間前`;
  return `${Math.floor(seconds / 86400)}日前`;
}

export function agoShort(seconds) {
  if (seconds == null) return "–";
  seconds = Math.max(0, Math.floor(seconds));
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

/* ---------- 永続化 ---------- */

const PREFIX = "xtrends:";
export const store = {
  get(key, fallback = null) {
    try {
      const raw = localStorage.getItem(PREFIX + key);
      if (raw === null) return fallback;
      return JSON.parse(raw);
    } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(PREFIX + key, JSON.stringify(value)); } catch { /* 容量超過など */ }
  },
  del(key) { try { localStorage.removeItem(PREFIX + key); } catch {} },
};

/* ---------- トースト ---------- */

export function toast(message, kind = "info", ms = 3200) {
  const wrap = document.getElementById("toastWrap");
  if (!wrap) return;
  const node = el("div", { class: `toast ${kind}`, text: message });
  wrap.append(node);
  setTimeout(() => {
    node.style.transition = "opacity .3s, transform .3s";
    node.style.opacity = "0";
    node.style.transform = "translateY(8px)";
    setTimeout(() => node.remove(), 320);
  }, ms);
}

/* ---------- その他 ---------- */

export function debounce(fn, wait = 220) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); };
}

export function highlight(text, query) {
  const safe = esc(text);
  if (!query) return safe;
  const q = query.trim();
  if (!q) return safe;
  const idx = safe.toLowerCase().indexOf(q.toLowerCase());
  if (idx < 0) return safe;
  return safe.slice(0, idx) + "<mark>" + safe.slice(idx, idx + q.length) + "</mark>" + safe.slice(idx + q.length);
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = el("textarea", { style: { position: "fixed", opacity: "0" } });
    ta.value = text;
    document.body.append(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { ok = false; }
    ta.remove();
    return ok;
  }
}

/** 通知音（WebAudioで生成。外部ファイル不要） */
export function chime() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const notes = [880, 1174.7];
    notes.forEach((f, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = f;
      gain.gain.setValueAtTime(0, ctx.currentTime + i * 0.11);
      gain.gain.linearRampToValueAtTime(0.16, ctx.currentTime + i * 0.11 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + i * 0.11 + 0.32);
      osc.connect(gain).connect(ctx.destination);
      osc.start(ctx.currentTime + i * 0.11);
      osc.stop(ctx.currentTime + i * 0.11 + 0.34);
    });
    setTimeout(() => ctx.close(), 900);
  } catch { /* 鳴らせなくても致命傷ではない */ }
}
