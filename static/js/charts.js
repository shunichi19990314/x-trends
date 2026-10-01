/* SVG チャート群（ライブラリ不使用・インライン生成） */

import { compact, hhmm, mdhm } from "./util.js";

const NS = "http://www.w3.org/2000/svg";
function S(tag, attrs = {}, kids = []) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined) continue;
    n.setAttribute(k, v);
  }
  for (const c of [].concat(kids)) if (c) n.append(c);
  return n;
}
function T(x, y, text, attrs = {}) {
  const n = S("text", { x, y, "font-size": "10", fill: "currentColor", opacity: ".65", ...attrs });
  n.textContent = text;
  return n;
}

let uid = 0;
const gid = () => `g${++uid}`;

/* ------------------------------------------------------------------ */
/* スパークライン                                                       */
/* ------------------------------------------------------------------ */

export function sparkline(points, { w = 220, h = 26, color = "#4f9dff", value = "rank" } = {}) {
  const data = (points || []).map(p => ({ ts: p.ts, v: p[value] })).filter(p => p.v != null);
  const svg = S("svg", { class: "spark", viewBox: `0 0 ${w} ${h}`, preserveAspectRatio: "none" });
  if (data.length < 2) {
    svg.append(S("line", { x1: 0, y1: h / 2, x2: w, y2: h / 2, stroke: color, "stroke-width": 1, "stroke-dasharray": "3 3", opacity: ".35" }));
    return svg;
  }
  const invert = value === "rank";           // ランクは小さいほど上
  const vs = data.map(d => d.v);
  let min = Math.min(...vs), max = Math.max(...vs);
  if (min === max) { min -= 1; max += 1; }
  const pad = 2;
  const x = i => (i / (data.length - 1)) * (w - 2) + 1;
  const y = v => {
    const t = (v - min) / (max - min);
    const ty = invert ? t : 1 - t;
    return pad + ty * (h - pad * 2);
  };
  const d = data.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
  const id = gid();
  svg.append(
    S("defs", {}, S("linearGradient", { id, x1: 0, y1: 0, x2: 0, y2: 1 },
      S("stop", { offset: "0%", "stop-color": color, "stop-opacity": ".38" }),
      S("stop", { offset: "100%", "stop-color": color, "stop-opacity": "0" }))),
    S("path", { d: `${d}L${x(data.length - 1).toFixed(1)},${h}L1,${h}Z`, fill: `url(#${id})`, stroke: "none" }),
    S("path", { d, fill: "none", stroke: color, "stroke-width": "1.6", "stroke-linejoin": "round", "stroke-linecap": "round", "vector-effect": "non-scaling-stroke" }),
    S("circle", { cx: x(data.length - 1), cy: y(data[data.length - 1].v), r: 2.1, fill: color }),
  );
  return svg;
}

/* ------------------------------------------------------------------ */
/* 折れ線 / 面グラフ（詳細ドロワー用）                                     */
/* ------------------------------------------------------------------ */

export function lineChart(points, opts = {}) {
  const {
    w = 460, h = 170, color = "#4f9dff", value = "count",
    yLabel = "投稿数", xTicks = 6, areaFill = true,
  } = opts;
  const padL = 44, padR = 12, padT = 12, padB = 22;
  const iw = w - padL - padR, ih = h - padT - padB;
  const data = (points || []).filter(p => p[value] != null).map(p => ({ ts: p.ts, v: p[value] }));
  const svg = S("svg", { viewBox: `0 0 ${w} ${h}`, style: "width:100%;height:auto;display:block;color:var(--text)" });

  if (data.length < 2) {
    svg.append(T(w / 2, h / 2, "履歴が2点以上ありません（収集を続けると増えていきます）",
      { "text-anchor": "middle", "font-size": "11", opacity: ".6" }));
    return svg;
  }

  const invert = value === "rank";
  const vs = data.map(d => d.v);
  let min = Math.min(...vs), max = Math.max(...vs);
  if (min === max) { min = Math.max(0, min - 1); max += 1; }
  if (!invert) min = Math.max(0, min - (max - min) * 0.12);
  const t0 = data[0].ts, t1 = data[data.length - 1].ts;
  const span = Math.max(1, t1 - t0);

  const X = ts => padL + ((ts - t0) / span) * iw;
  const Y = v => {
    const t = (v - min) / (max - min);
    return padT + (invert ? t : 1 - t) * ih;
  };

  // グリッド + Y軸ラベル
  const steps = 4;
  for (let i = 0; i <= steps; i++) {
    const v = min + ((max - min) * i) / steps;
    const y = Y(v);
    svg.append(S("line", { x1: padL, y1: y, x2: w - padR, y2: y, stroke: "currentColor", opacity: ".1", "stroke-width": 1 }));
    svg.append(T(padL - 6, y + 3, invert ? String(Math.round(v)) : compact(v), { "text-anchor": "end", "font-family": "var(--mono)" }));
  }
  // X軸ラベル
  for (let i = 0; i <= xTicks; i++) {
    const ts = t0 + (span * i) / xTicks;
    svg.append(T(X(ts), h - 6, hhmm(ts), { "text-anchor": "middle", "font-family": "var(--mono)" }));
  }

  const d = data.map((p, i) => `${i ? "L" : "M"}${X(p.ts).toFixed(1)},${Y(p.v).toFixed(1)}`).join("");
  if (areaFill) {
    const id = gid();
    svg.append(
      S("defs", {}, S("linearGradient", { id, x1: 0, y1: 0, x2: 0, y2: 1 },
        S("stop", { offset: "0%", "stop-color": color, "stop-opacity": ".35" }),
        S("stop", { offset: "100%", "stop-color": color, "stop-opacity": "0" }))),
      S("path", { d: `${d}L${X(t1).toFixed(1)},${padT + ih}L${X(t0).toFixed(1)},${padT + ih}Z`, fill: `url(#${id})` }),
    );
  }
  svg.append(S("path", { d, fill: "none", stroke: color, "stroke-width": "2", "stroke-linejoin": "round", "stroke-linecap": "round" }));

  // データ点
  const dotR = data.length > 60 ? 0 : 2.4;
  if (dotR) data.forEach(p => svg.append(S("circle", { cx: X(p.ts), cy: Y(p.v), r: dotR, fill: color })));

  // ホバー
  const cross = S("line", { y1: padT, y2: padT + ih, stroke: color, "stroke-width": 1, opacity: 0 });
  const dot = S("circle", { r: 4, fill: color, stroke: "var(--bg-2)", "stroke-width": 2, opacity: 0 });
  const tip = S("g", { opacity: 0 });
  const tipBg = S("rect", { rx: 6, height: 30, fill: "var(--panel-2)", stroke: "var(--line-2)" });
  const tipT1 = T(0, 0, "", { "font-size": "10.5", opacity: "1", fill: "var(--text)", "font-weight": "600" });
  const tipT2 = T(0, 0, "", { "font-size": "10", opacity: "1", fill: "var(--text-dim)", "font-family": "var(--mono)" });
  tip.append(tipBg, tipT1, tipT2);
  const hit = S("rect", { x: padL, y: padT, width: iw, height: ih, fill: "transparent", style: "cursor:crosshair" });
  svg.append(cross, dot, tip, hit);

  hit.addEventListener("mousemove", (ev) => {
    const rect = svg.getBoundingClientRect();
    const scale = w / rect.width;
    const mx = (ev.clientX - rect.left) * scale;
    let best = data[0], bd = Infinity;
    for (const p of data) {
      const dist = Math.abs(X(p.ts) - mx);
      if (dist < bd) { bd = dist; best = p; }
    }
    const cx = X(best.ts), cy = Y(best.v);
    cross.setAttribute("x1", cx); cross.setAttribute("x2", cx); cross.setAttribute("opacity", ".45");
    dot.setAttribute("cx", cx); dot.setAttribute("cy", cy); dot.setAttribute("opacity", "1");
    const l1 = mdhm(best.ts) + " JST";
    const l2 = `${yLabel}: ${invert ? best.v + "位" : compact(best.v)}`;
    tipT1.textContent = l1; tipT2.textContent = l2;
    const bw = Math.max(l1.length, l2.length) * 6.4 + 16;
    tipBg.setAttribute("width", bw);
    let tx = cx + 10;
    if (tx + bw > w - padR) tx = cx - bw - 10;
    let ty = Math.max(padT, Math.min(cy - 34, h - padB - 34));
    tip.setAttribute("transform", `translate(${tx},${ty})`);
    tipT1.setAttribute("x", 8); tipT1.setAttribute("y", 13);
    tipT2.setAttribute("x", 8); tipT2.setAttribute("y", 25);
    tip.setAttribute("opacity", "1");
  });
  hit.addEventListener("mouseleave", () => {
    cross.setAttribute("opacity", 0); dot.setAttribute("opacity", 0); tip.setAttribute("opacity", 0);
  });
  return svg;
}

/* ------------------------------------------------------------------ */
/* ドーナツ                                                             */
/* ------------------------------------------------------------------ */

export function donut(items, { size = 170, thickness = 22 } = {}) {
  const total = items.reduce((s, i) => s + (i.value || 0), 0) || 1;
  const r = (size - thickness) / 2;
  const cx = size / 2, cy = size / 2;
  const svg = S("svg", { viewBox: `0 0 ${size} ${size}`, style: `width:${size}px;height:${size}px;max-width:100%` });
  let angle = -Math.PI / 2;
  for (const it of items) {
    const frac = (it.value || 0) / total;
    if (frac <= 0) continue;
    const a2 = angle + frac * Math.PI * 2;
    const large = frac > 0.5 ? 1 : 0;
    const x1 = cx + r * Math.cos(angle), y1 = cy + r * Math.sin(angle);
    const x2 = cx + r * Math.cos(a2), y2 = cy + r * Math.sin(a2);
    const path = S("path", {
      d: `M${x1.toFixed(2)},${y1.toFixed(2)}A${r},${r} 0 ${large} 1 ${x2.toFixed(2)},${y2.toFixed(2)}`,
      fill: "none", stroke: it.color || "#4f9dff", "stroke-width": thickness, "stroke-linecap": "butt",
      opacity: ".92", style: "cursor:pointer",
    });
    const ttl = S("title");
    ttl.textContent = `${it.label}: ${it.value} (${(frac * 100).toFixed(1)}%)`;
    path.append(ttl);
    svg.append(path);
    angle = a2;
  }
  svg.append(
    (() => { const t = T(cx, cy - 1, String(items.reduce((s, i) => s + (i.value || 0), 0)),
      { "text-anchor": "middle", "font-size": "19", "font-weight": "700", opacity: "1", fill: "var(--text)", "font-family": "var(--mono)" }); return t; })(),
    T(cx, cy + 15, "トレンド数", { "text-anchor": "middle", "font-size": "9.5", fill: "var(--muted)" }),
  );
  return svg;
}

/* ------------------------------------------------------------------ */
/* 横棒グラフ                                                           */
/* ------------------------------------------------------------------ */

export function hbars(items, { max = null, fmt = compact, onClick = null, showValue = true } = {}) {
  const wrap = document.createElement("div");
  wrap.className = "bars";
  const m = max || Math.max(1, ...items.map(i => i.value || 0));
  for (const it of items) {
    const row = document.createElement("div");
    row.className = "bar-row" + (onClick ? " clickable" : "");
    const pct = Math.max(1.5, ((it.value || 0) / m) * 100);
    row.innerHTML =
      `<span class="lbl" title="${String(it.label).replace(/"/g, "&quot;")}">${it.icon ? `<span>${it.icon}</span>` : ""}<span style="overflow:hidden;text-overflow:ellipsis">${it.label}</span></span>` +
      `<span class="track"><span class="fill" style="width:${pct.toFixed(1)}%;background:${it.color || "linear-gradient(90deg,var(--accent),var(--accent-2))"}"></span></span>` +
      (showValue ? `<span class="val">${fmt(it.value)}</span>` : "");
    if (onClick) row.addEventListener("click", () => onClick(it));
    wrap.append(row);
  }
  return wrap;
}

/* ------------------------------------------------------------------ */
/* ヒートマップ（HTMLテーブル）                                          */
/* ------------------------------------------------------------------ */

export function heatmap(rows, cols, { onClick = null } = {}) {
  // rows: [{name, values: {(ts|null)} }]  cols: [ts,...]
  const tbl = document.createElement("table");
  tbl.className = "hm";
  const thead = document.createElement("thead");
  const htr = document.createElement("tr");
  htr.append(document.createElement("th"));
  for (const c of cols) {
    const th = document.createElement("th");
    th.textContent = hhmm(c);
    htr.append(th);
  }
  thead.append(htr);
  tbl.append(thead);

  const tbody = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.className = "row";
    th.textContent = row.name;
    th.title = row.name;
    tr.append(th);
    for (const c of cols) {
      const td = document.createElement("td");
      const v = row.values.get(c);
      if (v == null) {
        td.className = "na";
        td.textContent = "";
      } else {
        // ランク1が最も濃い
        const t = Math.min(1, (v - 1) / 24);
        const alpha = 0.95 - t * 0.78;
        td.style.background = `rgba(79,157,255,${alpha.toFixed(2)})`;
        td.style.color = alpha > 0.55 ? "rgba(255,255,255,.9)" : "var(--text-dim)";
        td.textContent = v;
        td.title = `${row.name} — ${hhmm(c)} JST: ${v}位`;
        if (onClick) { td.style.cursor = "pointer"; td.addEventListener("click", () => onClick(row.name, c)); }
      }
      tr.append(td);
    }
    tbody.append(tr);
  }
  tbl.append(tbody);
  return tbl;
}
