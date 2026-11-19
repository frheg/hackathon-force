// Subsurface Evidence UI. One file, no build. Every number comes from /api; every page starts with what you are looking at.
const $ = (s, r = document) => r.querySelector(s), api = (p, q = {}) => fetch("api/" + p + "?" + new URLSearchParams(q)).then((r) => r.json());
const pct = (x, d = 1) => (x == null ? "–" : (100 * x).toFixed(d) + "%"), f2 = (x, d = 2) => (x == null ? "–" : (+x).toFixed(d));
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
let META, LAYERS, use = [], map = null;
const pill = (cls, t) => `<span class="pill ${cls}">${esc(t || cls.replace("_", " "))}</span>`;
const what = (title, ...lines) => `<div class="card what"><h3>${title || "What you are looking at"}</h3>${lines.map((l) => `<p>${l}</p>`).join("")}</div>`;
const STATUS_WORDS = { helps: "helped when tested", no_evidence: "no measurable help", hurts: "made it worse", not_built: "not built yet" };
const I = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const PAGES = [
  ["Overview", [["start", "Start here", I('<path d="M3 11 12 4l9 7v9H3z"/>')], ["scene", "3D explorer", I('<path d="M12 2 3 7v10l9 5 9-5V7z"/><path d="M3 7l9 5 9-5M12 12v10"/>')], ["map", "Map", I('<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>')], ["data", "Data explorer", I('<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>')], ["units", "Units", I('<path d="M4 6h16M4 12h16M4 18h16"/>')]]],
  ["Why we believe it", [["layers", "Evidence layers", I('<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>')], ["knowledge", "Knowledge", I('<path d="M4 4h12a4 4 0 0 1 4 4v12H8a4 4 0 0 1-4-4z"/><path d="M8 8h8"/>')], ["validation", "Validation", I('<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>')], ["contradictions", "Contradictions", I('<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17h.01"/>')], ["log", "Decision log", I('<path d="M6 3h12v18H6z"/><path d="M9 8h6M9 12h6M9 16h4"/>')]]],
];

function plot(el, data, layout = {}, cfg = {}) {
  const ink = css("--ink"), mut = css("--mut"), line = css("--line");
  const base = { paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { family: "Inter, system-ui", color: ink, size: 12 }, margin: { l: 56, r: 16, t: 24, b: 44 },
    xaxis: { gridcolor: line, zerolinecolor: line, linecolor: line, color: mut }, yaxis: { gridcolor: line, zerolinecolor: line, linecolor: line, color: mut }, legend: { orientation: "h", y: -0.2 } };
  const L = { ...base, ...layout, xaxis: { ...base.xaxis, ...(layout.xaxis || {}) }, yaxis: { ...base.yaxis, ...(layout.yaxis || {}) } };
  return Plotly.react(el, data, L, { displaylogo: false, responsive: true, ...cfg });
}

async function init() {
  META = await api("meta"); LAYERS = await api("layers"); use = LAYERS.filter((l) => l.on_by_default).map((l) => l.name);
  $("#links").innerHTML = PAGES.map(([g, items]) => `<div class="grp">${g}</div>` + items.map(([k, t, ic]) => `<a data-p="${k}" title="${t}">${ic}<span class="lbl">${t}</span></a>`).join("")).join("");
  $("#links").onclick = (e) => { const a = e.target.closest("a"); if (a) location.hash = a.dataset.p; $("#nav").classList.remove("open"); };
  $("#collapse").onclick = () => { const n = $("#nav"); innerWidth < 800 ? n.classList.toggle("open") : n.classList.toggle("mini"); setTimeout(() => window.dispatchEvent(new Event("resize")), 250); };
  $("#theme").onclick = () => { const d = document.documentElement; d.dataset.theme = (d.dataset.theme || (matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light")) === "dark" ? "light" : "dark"; route(); };
  chips(); addEventListener("hashchange", route); route();
}
const chips = () => ($("#chips").innerHTML = `${pill("plain", "compute: " + META.device)}${pill("plain", "GPU worker: " + (META.worker ? "on demand" : "off"))}${pill("plain", "layers on: " + use.join(", "))}`);
function route() {
  const [p, ...rest] = (location.hash.slice(1) || "start").split("/");
  document.querySelectorAll("#links a").forEach((a) => a.classList.toggle("on", a.dataset.p === (p === "unit" ? "units" : p)));
  const t = PAGES.flatMap((g) => g[1]).find((x) => x[0] === p); $("#crumb").textContent = t ? t[1] : "Unit";
  const v = $("#view"); v.innerHTML = '<div class="skeleton">loading…</div>'; if (map) { map.remove(); map = null; }
  (PAGES_FN[p] || PAGES_FN.start)(decodeURIComponent(rest.join("/"))).catch((e) => (v.innerHTML = `<div class="card warn"><b>Could not load this page.</b><pre>${esc(e)}</pre></div>`));
}
const layerBox = () => `<span class="tip">evidence used:</span> ` + LAYERS.filter((l) => l.built).map((l) => `<label class="chk"><input type="checkbox" data-l="${l.name}" ${use.includes(l.name) ? "checked" : ""}> ${l.title} ${pill(l.status)}</label>`).join(" ");
function bindLayers(re) { document.querySelectorAll("[data-l]").forEach((c) => (c.onchange = () => { use = [...document.querySelectorAll("[data-l]")].filter((x) => x.checked).map((x) => x.dataset.l); chips(); re(); })); }
const ramp = (m) => `<div class="legend"><span>low</span><div class="ramp"></div><span>high (${pct(m)})</span><span style="margin-left:12px">grey = no wells within reach: no estimate</span></div>`;

const PAGES_FN = {
  async start() {
    const d = META.data, fs = (await api("formations")).filter((f) => f.units >= 20).slice(0, 14);
    $("#view").innerHTML = `<h1>Where might green clay be, and why do we think so?</h1><p class="lead">Old well reports describe rock in words. We counted how often geologists wrote a green mineral (glauconite, green clay, chlorite) when describing clay, for every well and rock formation. This tool turns those counts into an estimate, shows the evidence behind each number, and tests itself on wells it never saw.</p>
    <div class="grid g4"><div class="card stat"><b>${d.units.toLocaleString()}</b><span>units (one well × one formation)</span></div><div class="card stat"><b>${d.wellbores_labelled}</b><span>wells with enough description</span></div>
    <div class="card stat"><b>${d.rows.toLocaleString()}</b><span>described clay rows read</span></div><div class="card stat"><b>${pct(d.base_rate)}</b><span>of them name a green mineral</span></div></div>
    <div class="grid g2"><div class="card what"><h3>How to read it</h3><p><b>Rate</b> = share of described clay rows that name a green mineral. It is <b>what geologists wrote</b>, not a measured amount.</p><p><b>Evidence layers</b> each add or subtract from the estimate: the formation, nearby wells, well logs, later seismic. Each is tested and labelled.</p><p>Start with the <a href="#scene">3D explorer</a> (where and how deep) or the <a href="#map">map</a> (one formation from above).</p></div>
    <div class="card warn"><h3>The honest state</h3><p>${LAYERS.map((l) => `${pill(l.status, l.title + ": " + STATUS_WORDS[l.status])}`).join(" ")}</p><p>The skill is <b>small</b>: the formation tells a little, neighbours and logs tell nothing measurable yet. Wells described in more detail look greener, so use estimates as leads to check, not facts. <a href="#validation">See the scorecard</a>.</p></div></div>
    <div class="card"><h2>Reported green share by formation</h2><p class="tip">Bars: share of described clay rows naming a green mineral. Dashed line: overall ${pct(d.base_rate)}.</p><div id="fp" class="plot" style="height:340px"></div></div>`;
    plot($("#fp"), [{ type: "bar", x: fs.map((f) => f.name), y: fs.map((f) => f.rate * 100), marker: { color: css("--acc") }, hovertemplate: "%{x}<br>%{y:.1f}%<extra></extra>", customdata: fs.map((f) => f.rows) }],
      { yaxis: { title: "% green", ticksuffix: "%" }, xaxis: { tickangle: -35 }, shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: d.base_rate * 100, y1: d.base_rate * 100, line: { color: css("--mut"), dash: "dash" } }], margin: { l: 56, r: 16, t: 10, b: 120 } });
  },

  async scene() {
    const fl = await api("formations3d"), want = ["NORDLAND GP", "ROGALAND GP", "SELE FM"].filter((x) => fl.some((f) => f.name === x)), st = { reg: "58,62", sel: new Set(want), ex: 12, op: 0.55, wells: true, surf: true, box: true, hs: null };
    $("#view").innerHTML = `<h1>3D explorer</h1>${what("", "Each <b>vertical stick</b> is one well, drawn where it is and from the top to the bottom of the rock formation. Its colour is the share of described clay rows that name a green mineral (grey: too few rows to say).",
      "Each <b>translucent sheet</b> is one formation across the area: its height is the typical depth, its colour the model's estimate. Cells with no well within 60 km are left out.",
      "Each <b>orange or blue box</b> marks an area (20 km wide) where the reports are unusually green (orange) or unusually not green (blue). Click one in the list to fly to it and read why. <b>Depth is measured depth along the well, not true vertical depth.</b>")}
    <div class="card"><div class="row"><b>Region</b><select id="reg"><option value="58,62">North Sea (58–62°N)</option><option value="62,69">Norwegian Sea (62–69°N)</option><option value="69,90">Barents Sea (>69°N)</option><option value="0,90">Whole shelf (small!)</option></select></div>
    <div class="row"><b>Formations</b>${fl.slice(0, 14).map((f) => `<label class="chk"><input type="checkbox" data-f="${esc(f.name)}" ${st.sel.has(f.name) ? "checked" : ""}> ${esc(f.name)} <span class="tip">${f.wells}</span></label>`).join("")}</div>
    <div class="row"><label class="chk"><input type="checkbox" id="cw" checked> wells</label><label class="chk"><input type="checkbox" id="cs" checked> estimate sheets</label><label class="chk"><input type="checkbox" id="cb" checked> hotspot boxes</label>
    <label class="chk">depth stretch <input type="range" id="ex" min="1" max="40" value="12"><span id="exv">12×</span></label><label class="chk">sheet opacity <input type="range" id="op" min="10" max="100" value="55"></label>
    <label class="chk" title="Seismic cubes are not built yet: the layer exists as a registered stub"><input type="checkbox" disabled> seismic cube (not built)</label></div></div>
    <div class="split"><div class="card" style="padding:8px"><div id="p3" class="plot" style="height:720px"></div><div class="legend" style="padding:6px 10px"><span>stick colour:</span><span>observed green share</span><div class="ramp"></div><span>sheet colour: estimate</span></div></div>
    <div><div class="card"><h2>Interesting areas</h2><p class="tip">Ranked by how unlikely they are by chance, after correcting for how many windows were tested. Click to fly there.</p><div id="hs"></div></div></div></div>`;
    let S = null; const stretch = () => st.ex;
    const draw = async () => {
      const q = [...st.sel].join(","); if (!q) { plot($("#p3"), [], {}); $("#hs").innerHTML = '<p class="tip">pick a formation</p>'; return; }
      const [la, lb] = st.reg.split(","); S = await api("scene", { formations: q, lat_min: la, lat_max: lb }); const tr = [], W = S.wells, ex = stretch();
      const xs = W.map((w) => w.x).concat(...S.surfaces.map((s) => s.x.flat())), ys = W.map((w) => w.y).concat(...S.surfaces.map((s) => s.y.flat()));
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), zmax = Math.max(...W.map((w) => w.bot), 1000);
      if (st.surf) S.surfaces.forEach((s, i) => tr.push({ type: "surface", x: s.x, y: s.y, z: s.depth.map((r) => r.map((v) => (v == null ? null : -v))), surfacecolor: s.rate, cmin: 0, cmax: 0.2, opacity: st.op, showscale: i === 0, name: s.formation,
        colorscale: [[0, "rgba(14,159,126,0.15)"], [0.5, "#0e9f7e"], [1, "#064e3b"]], colorbar: { title: "estimate", len: 0.4, thickness: 10, x: 0.02, tickformat: ".0%" }, hovertemplate: s.formation + "<br>depth %{z:.0f} m<br>estimate %{surfacecolor:.1%}<extra></extra>", lighting: { ambient: 0.9, diffuse: 0.3 } }));
      if (st.wells) { const bins = [[-1, "too few rows", css("--mut")], [0.02, "<2%", "#7dd3c0"], [0.08, "2–8%", "#2dd4a7"], [0.2, "8–20%", "#f5b84a"], [9, ">20%", "#ff6b6b"]];
        const bi = (w) => (w.rows < 3 || w.obs == null ? 0 : w.obs < 0.02 ? 1 : w.obs < 0.08 ? 2 : w.obs < 0.2 ? 3 : 4);
        bins.forEach(([_, nm, col], b) => { const g = W.filter((w) => bi(w) === b); if (!g.length) return; const x = [], y = [], z = [], t = [];
          g.forEach((w) => { const lab = `${w.unit}<br>${w.green} of ${w.rows} rows green${w.obs == null ? "" : " (" + pct(w.obs) + ")"}<br>${w.top.toFixed(0)}–${w.bot.toFixed(0)} m MD`; x.push(w.x, w.x, null); y.push(w.y, w.y, null); z.push(-w.top, -w.bot, null); t.push(lab, lab, ""); });
          tr.push({ type: "scatter3d", mode: "lines", x, y, z, text: t, hoverinfo: "text", line: { color: col, width: b === 0 ? 3 : 6 }, name: nm + " (" + g.length + ")" }); }); }
      const hs = S.hotspots;
      if (st.box) hs.forEach((h) => { const r = h.radius_km, c = h.kind === "hot" ? css("--hot") : css("--cold"), sel = st.hs === h.id, [a, b] = [-h.top, -h.bot];
        const X = [h.x - r, h.x + r, h.x + r, h.x - r, h.x - r, h.x + r, h.x + r, h.x - r], Y = [h.y - r, h.y - r, h.y + r, h.y + r, h.y - r, h.y - r, h.y + r, h.y + r], Z = [a, a, a, a, b, b, b, b];
        tr.push({ type: "mesh3d", x: X, y: Y, z: Z, i: [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3], j: [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 0, 4], k: [2, 3, 6, 7, 5, 4, 6, 5, 7, 6, 4, 7], color: c, opacity: sel ? 0.45 : 0.2, flatshading: true, name: h.id, hoverinfo: "text", text: h.text, showlegend: false }); });
      const ar = { x: 1, y: Math.max((y1 - y0) / (x1 - x0), 0.15), z: Math.max((zmax / 1000 / ((x1 - x0) || 1)) * ex, 0.12) };
      S._g = { x0, x1, y0, y1, zmax, ar };
      const zt = [0, 1000, 2000, 3000, 4000].filter((v) => v <= zmax + 500);
      await plot($("#p3"), tr, { margin: { l: 0, r: 0, t: 0, b: 0 }, legend: { orientation: "h", y: 0, font: { size: 11 } }, scene: { aspectmode: "manual", aspectratio: ar, camera: { eye: { x: 1.5, y: -1.6, z: 0.9 } },
        xaxis: { title: "East (km)", gridcolor: css("--line"), color: css("--mut"), backgroundcolor: "rgba(0,0,0,0)" }, yaxis: { title: "North (km)", gridcolor: css("--line"), color: css("--mut"), backgroundcolor: "rgba(0,0,0,0)" },
        zaxis: { title: "Depth MD (m)", tickvals: zt.map((v) => -v), ticktext: zt.map(String), gridcolor: css("--line"), color: css("--mut"), backgroundcolor: "rgba(0,0,0,0)" } } });
      $("#hs").innerHTML = hs.length ? hs.map((h) => `<div class="hs ${st.hs === h.id ? "sel" : ""}" data-h="${esc(h.id)}"><div class="row" style="margin:0">${pill(h.kind === "hot" ? "hot" : "cold", h.kind === "hot" ? "greener than usual" : "less green than usual")}${h.p_adj < 0.05 ? pill("ok", "survives correction") : pill("warnc", "exploratory")}<b>${esc(h.formation)}</b></div>
        <p><b>${h.lift}×</b> the formation rate · ${h.wells} wells · ${h.rows} rows</p><p>${esc(h.text)}</p></div>`).join("") : '<p class="tip">No window in these formations has enough wells and rows to test.</p>';
    };
    const fly = (id) => { const h = S?.hotspots.find((x) => x.id === id); if (!h) return; st.hs = id; const g = S._g, ar = g.ar; const c = { x: ((h.x - (g.x0 + g.x1) / 2) / (g.x1 - g.x0)) * ar.x, y: ((h.y - (g.y0 + g.y1) / 2) / (g.y1 - g.y0)) * ar.y, z: (-((h.top + h.bot) / 2) + g.zmax / 2) / g.zmax * ar.z * 0.5 };
      Plotly.relayout($("#p3"), { "scene.camera": { center: c, eye: { x: c.x + 0.5, y: c.y - 0.6, z: c.z + 0.35 } } }); document.querySelectorAll(".hs").forEach((e) => e.classList.toggle("sel", e.dataset.h === id)); };
    $("#hs").onclick = (e) => { const el = e.target.closest(".hs"); if (el) fly(el.dataset.h); };
    document.querySelectorAll("[data-f]").forEach((c) => (c.onchange = () => { c.checked ? st.sel.add(c.dataset.f) : st.sel.delete(c.dataset.f); draw(); }));
    $("#reg").onchange = (e) => { st.reg = e.target.value; st.hs = null; draw(); }; $("#cw").onchange = (e) => { st.wells = e.target.checked; draw(); }; $("#cs").onchange = (e) => { st.surf = e.target.checked; draw(); }; $("#cb").onchange = (e) => { st.box = e.target.checked; draw(); };
    $("#ex").oninput = (e) => { st.ex = +e.target.value; $("#exv").textContent = st.ex + "×"; if (S) { const g = S._g; g.ar.z = Math.max((g.zmax / 1000 / ((g.x1 - g.x0) || 1)) * st.ex, 0.12); Plotly.relayout($("#p3"), { "scene.aspectratio": g.ar }); } };
    $("#op").oninput = (e) => { st.op = +e.target.value / 100; draw(); }; await draw();
  },

  async map() {
    const fs = (await api("formations")).filter((f) => f.units >= 20), hs = await api("hotspots");
    $("#view").innerHTML = `<h1>Map</h1>${what("", "One rock formation seen from above. <b>Green shading</b> is the estimated share of described clay rows that name a green mineral: darker = higher. <b>Faint grey</b> = no well of this formation within 60 km, so the model says nothing there. <b>Blue dots</b> are the wells it learned from; hover a dot for its counts.",
      "<b>Orange / blue circles</b> are the same 20 km areas as in the 3D explorer (greener / less green than usual). Pick another formation, or switch evidence on and off, to see the estimate change.")}
    <div class="card"><div class="row"><select id="f">${fs.map((f) => `<option>${esc(f.name)}</option>`).join("")}</select>${layerBox()}<button class="btn" id="fine" title="Runs on the GPU worker if it is free, else on the CPU">Fine map (GPU)</button><span id="mi" class="tip"></span></div><div id="map"></div><div style="margin-top:8px" id="lg"></div></div>`;
    const draw = async (fine) => {
      const f = $("#f").value; $("#mi").textContent = fine ? "starting the GPU worker, first start can take minutes…" : "computing…";
      const m = fine ? await fetch("api/jobs/map?" + new URLSearchParams({ formation: f, res: 0.02 }), { method: "POST" }).then((r) => r.json()) : await api("map", { formation: f, res: 0.1, layers: use.join(",") });
      if (m.detail) { $("#mi").textContent = m.detail; return; }
      $("#mi").textContent = `${m.cells.toLocaleString()} cells · ${m.units} wells · ${m.device} · ${m.seconds}s${m.via ? " · via " + m.via : ""}`;
      if (map) map.remove(); map = L.map("map"); L.tileLayer("https://{s}.basemaps.cartocdn.com/" + (css("--bg") < "#80" ? "dark_all" : "light_all") + "/{z}/{x}/{y}.png", { attribution: "© OSM © CARTO" }).addTo(map);
      const dl = m.lat[1] - m.lat[0], dn = m.lon[1] - m.lon[0], mx = Math.max(...m.rate.flat()); $("#lg").innerHTML = ramp(mx);
      const cv = document.createElement("canvas"); cv.width = m.lon.length; cv.height = m.lat.length; const g = cv.getContext("2d");
      m.rate.forEach((row, i) => row.forEach((v, j) => { const far = m.nearest_km[i][j] > m.reach_km; g.fillStyle = far ? "rgba(120,120,120,.10)" : `rgba(14,159,126,${0.12 + 0.8 * v / mx})`; g.fillRect(j, m.lat.length - 1 - i, 1, 1); }));
      const b = [[m.lat[0] - dl / 2, m.lon[0] - dn / 2], [m.lat.at(-1) + dl / 2, m.lon.at(-1) + dn / 2]]; map.invalidateSize(); map.fitBounds(b, { padding: [10, 10] }); L.imageOverlay(cv.toDataURL(), b, { opacity: 0.85, className: "px" }).addTo(map);
      hs.filter((h) => h.formation === f).forEach((h) => L.circle([h.lat, h.lon], { radius: h.radius_km * 1000, color: h.kind === "hot" ? "#ff922b" : "#4dabf7", weight: 2, fillOpacity: 0.12 }).bindTooltip(`${h.kind === "hot" ? "greener" : "less green"}: ${h.lift}× formation rate, ${h.wells} wells`).addTo(map));
      (m.points || []).forEach((p) => L.circleMarker([p.lat, p.lon], { radius: 3, weight: 1, color: "#4dabf7", fillOpacity: 0.7 }).bindTooltip(`${p.unit}: ${p.green} of ${p.rows} rows green`).addTo(map)); L.control.scale().addTo(map);
    };
    $("#f").onchange = () => draw(false); $("#fine").onclick = () => draw(true); bindLayers(() => draw(false)); await draw(false);
  },


  async data() {
    const cat = await api("catalog"), st = { t: null, f: [], x: null, y: "", agg: "count", tab: "chart", off: 0 };
    $("#view").innerHTML = `<h1>Data explorer</h1>${what("", "Everything we hold, where it came from, and a way to look inside it. Pick a table, then <b>chart</b> any column, browse <b>rows</b>, or see wells on a <b>map</b>. <b>Click a bar to filter</b> to it; every view (chart, rows, map) then updates. Remove a filter with its x.", "Only the Sodir FactPages tables are browsable here. Reports, logs and seismic are listed with their origin and what they contain.")}
    <div class="grid g3">${cat.datasets.map((d) => `<div class="card"><div class="row" style="margin:0 0 6px"><h2 style="margin:0">${esc(d.name)}</h2>${pill(d.used === "no" ? "muted" : "ok", "used: " + d.used)}</div><p>${esc(d.what)}</p><p class="tip"><b>Origin:</b> ${esc(d.source)}<br><b>Size:</b> ${esc(d.size)} · <span class="mono">${esc(d.path)}</span></p></div>`).join("")}</div>
    <div class="card"><div class="row"><b>FactPages table</b><select id="tb"><option value="">choose…</option>${cat.tables.map((t) => `<option value="${t.name}">${t.name} (${t.rows.toLocaleString()} rows, ${t.cols} cols)</option>`).join("")}</select></div><div id="ex"></div></div>`;
    const fq = () => st.f.map((x) => x.join("|")), qs = (o) => { const p = new URLSearchParams(o); fq().forEach((f) => p.append("f", f)); return p; };
    const get = (p, o) => fetch("api/" + p + "?" + qs(o)).then((r) => r.json());
    const chips2 = () => (st.f.length ? `<div class="row"><span class="tip">filters:</span>${st.f.map((f, i) => `<span class="pill plain">${esc(f[0])} ${esc(f[1])} ${esc(f[2] ?? "")} <a data-rm="${i}" style="cursor:pointer;margin-left:6px">✕</a></span>`).join("")}</div>` : "");
    const show = async () => {
      const cols = st.cols, tabs = [["chart", "Chart"], ["rows", "Rows"], ["map", "Map"], ["cols", "Columns"]];
      $("#ex").innerHTML = `<div class="row">${tabs.map(([k, t]) => `<button class="btn ${st.tab === k ? "primary" : ""}" data-tab="${k}">${t}</button>`).join("")}</div>${chips2()}<div id="pane"></div>`;
      $("#ex").onclick = (e) => { const rm = e.target.closest("[data-rm]"), tb = e.target.closest("[data-tab]"); if (rm) { st.f.splice(+rm.dataset.rm, 1); show(); } if (tb) { st.tab = tb.dataset.tab; show(); } };
      const P = $("#pane");
      if (st.tab === "cols") P.innerHTML = `<p class="tip">${st.n.toLocaleString()} rows. Null = share missing. Distinct = number of different values.</p><div style="max-height:60vh;overflow:auto"><table><tr><th>column<th>type<th>missing<th>distinct<th>min<th>max</tr>${cols.map((c) => `<tr><td><b>${esc(c.name)}</b><td class="mono">${esc(c.type)}<td>${pct(c.null_share, 0)}<td>${c.distinct.toLocaleString()}<td class="mono">${esc((c.min ?? "").slice(0, 30))}<td class="mono">${esc((c.max ?? "").slice(0, 30))}</tr>`).join("")}</table></div>`;
      if (st.tab === "rows") { const r = await get("table/rows", { name: st.t, limit: 100, offset: st.off }); P.innerHTML = `<div class="row"><button class="btn" id="pv">←</button><button class="btn" id="nx">→</button><span class="tip">${r.total.toLocaleString()} rows match · showing ${st.off + 1}–${st.off + r.rows.length}</span></div><div style="max-height:60vh;overflow:auto"><table><tr>${r.columns.map((c) => `<th>${esc(c)}`).join("")}</tr>${r.rows.map((row) => `<tr>${row.map((v) => `<td>${esc(String(v ?? "").slice(0, 60))}`).join("")}</tr>`).join("")}</table></div>`;
        $("#pv").onclick = () => { st.off = Math.max(0, st.off - 100); show(); }; $("#nx").onclick = () => { st.off += 100; show(); }; }
      if (st.tab === "chart") { P.innerHTML = `<div class="row"><label class="chk">x <select id="cx">${cols.map((c) => `<option ${c.name === st.x ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></label><label class="chk">y <select id="cy"><option value="">(count of rows)</option>${cols.filter((c) => c.numeric).map((c) => `<option ${c.name === st.y ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></label><label class="chk">as <select id="ca">${["mean", "sum", "median"].map((a) => `<option ${a === st.agg ? "selected" : ""}>${a}</option>`).join("")}</select></label><span class="tip">click a bar to filter</span></div><div id="ch" class="plot" style="height:420px"></div>`;
        const run = async () => { st.x = $("#cx").value; st.y = $("#cy").value; st.agg = $("#ca").value; const d = await get("table/chart", { name: st.t, x: st.x, ...(st.y ? { y: st.y, agg: st.agg } : {}) });
          await plot($("#ch"), [{ type: "bar", x: d.x.map((v) => (d.kind === "hist" ? +v.toPrecision(5) : v)), y: d.y, marker: { color: css("--acc") }, hovertemplate: "%{x}: %{y:,.2f}<extra></extra>" }], { xaxis: { title: st.x, type: d.kind === "cat" ? "category" : "linear", tickangle: d.kind === "cat" ? -35 : 0 }, yaxis: { title: st.y ? `${st.agg} of ${st.y}` : "rows" }, margin: { l: 60, r: 10, t: 10, b: 110 } });
          $("#ch").on("plotly_click", (e) => { const v = e.points[0].x; if (d.kind === "cat") st.f.push([st.x, "eq", v]); else { st.f.push([st.x, "ge", String(v - d.step / 2)]); st.f.push([st.x, "lt", String(v + d.step / 2)]); } st.off = 0; show(); }); };
        ["#cx", "#cy", "#ca"].forEach((s) => ($(s).onchange = run)); await run(); }
      if (st.tab === "map") { const d = await get("table/points", { name: st.t }); P.innerHTML = d.points.length ? `<p class="tip">${d.points.length.toLocaleString()} points from ${d.lat}/${d.lon} (max 6000). Filters apply.</p><div id="map" style="height:520px"></div>` : `<p class="tip">${esc(d.note)}</p>`;
        if (d.points.length) { if (map) map.remove(); map = L.map("map"); L.tileLayer("https://{s}.basemaps.cartocdn.com/" + (css("--bg") < "#80" ? "dark_all" : "light_all") + "/{z}/{x}/{y}.png", { attribution: "© OSM © CARTO" }).addTo(map); const g = L.featureGroup(d.points.map((p) => L.circleMarker([p.lat, p.lon], { radius: 3, weight: 1, color: "#2dd4a7", fillOpacity: 0.6 }))).addTo(map); map.fitBounds(g.getBounds(), { padding: [10, 10] }); } }
    };
    $("#tb").onchange = async (e) => { st.t = e.target.value; st.f = []; st.off = 0; if (!st.t) { $("#ex").innerHTML = ""; return; } const c = await api("table/columns", { name: st.t }); st.cols = c.columns; st.n = c.rows; st.x = c.columns[0].name; st.y = ""; st.tab = "chart"; await show(); };
  },

  async units() {
    $("#view").innerHTML = `<h1>Units</h1>${what("", "One row = one <b>unit</b>: one well drawn through one rock formation. <b>Rows</b> = how many described clay rows it has; <b>green</b> = how many of those name a green mineral; <b>observed</b> = green/rows; <b>estimate</b> = what the model expects for it.",
      "Click a row to see exactly why it got its estimate. Sort by estimate to find likely places, or by observed to find what geologists actually wrote.")}
    <div class="card"><div class="row"><input type="search" id="q" placeholder="search well, e.g. 30/6"><select id="f"><option value="">all formations</option></select><select id="s"><option value="rate">sort: estimate</option><option value="observed">sort: observed</option><option value="rows">sort: rows</option></select>${layerBox()}</div><div style="max-height:70vh;overflow:auto"><table id="t"></table></div></div>`;
    (await api("formations")).forEach((f) => $("#f").insertAdjacentHTML("beforeend", `<option>${esc(f.name)}</option>`));
    const go = async () => { const u = await api("units", { q: $("#q").value, formation: $("#f").value, sort: $("#s").value, layers: use.join(",") }); const mx = Math.max(...u.map((x) => x.rate || 0), 0.01);
      $("#t").innerHTML = "<tr><th>unit<th>depth (m MD)<th>rows<th>green<th>observed<th>estimate</tr>" + u.map((x) => `<tr class="click" data-u="${esc(x.unit)}"><td><b>${esc(x.wellbore)}</b> <span class="tip">${esc(x.name)}</span><td class="mono">${x.top}–${x.bot}<td>${x.coverage}<td>${x.n_green}<td>${pct(x.observed)}<td><div class="row" style="margin:0;gap:8px"><div class="track"><div class="bar" style="width:${100 * x.rate / mx}%"></div></div>${pct(x.rate)}</div></tr>`).join(""); };
    $("#t").onclick = (e) => { const r = e.target.closest("tr[data-u]"); if (r) location.hash = "unit/" + encodeURIComponent(r.dataset.u); }; $("#q").oninput = go; $("#f").onchange = go; $("#s").onchange = go; bindLayers(go); await go();
  },

  async unit(id) {
    const draw = async () => { const u = await api("unit", { id, layers: use.join(",") }), P = u.estimate.parts, names = { base: "Starting point (overall rate)", strat: "Formation", spatial: "Nearby wells", logs: "Well logs", seismic: "Seismic" };
      $("#view").innerHTML = `<p><a href="#units">← all units</a></p><h1>${esc(u.wellbore)} <span class="muted">× ${esc(u.formation)}</span></h1><p class="lead">${esc(u.level.toLowerCase())} interval ${u.top}–${u.bot} m MD · ${u.lat.toFixed(3)}° N, ${u.lon.toFixed(3)}° E</p>
      ${what("", "The model starts from the overall green share and then adds or subtracts <b>evidence</b>. Each bar below is one kind of evidence: right (green) pushes the estimate up, left (red) pushes it down. The unit of the bars is log-odds (a sum of these gives the final number). Under each bar is the reason in words.")}
      <div class="grid g3"><div class="card stat"><b>${u.green_rows} of ${u.described_clay_rows}</b><span>described clay rows name a green mineral (observed ${pct(u.observed_rate)})</span></div><div class="card stat"><b>${pct(u.estimate.rate)}</b><span>model estimate (${pct(u.validation_estimate)} when this well was held out of training)</span></div><div class="card"><div class="row" style="margin:0">${layerBox()}</div></div></div>
      ${u.labelled ? "" : '<div class="card warn">Too few described rows (under 3): this unit was not used for training, the estimate is shown for context.</div>'}
      <div class="card"><h2>Evidence, step by step</h2><div id="wf" class="plot" style="height:300px"></div><table>${P.map((p) => `<tr><td><b>${names[p.layer] || p.layer}</b> ${p.status ? pill(p.status) : ""}<td class="mono">${p.llr == null ? "silent" : (p.llr > 0 ? "+" : "") + f2(p.llr)}<td>${esc(p.why)}</tr>`).join("")}</table></div>
      <div class="card"><h2>Log medians in this interval</h2><p class="tip">GR gamma, RHOB density, NPHI neutron, PEF photoelectric, DTC sonic, RDEP resistivity (log10), DNSEP neutron–density separation. Shown for reference; the log layer is ${pill(META.status.logs)}.</p><table><tr>${Object.keys(u.logs).map((k) => `<th>${k}`).join("")}</tr><tr>${Object.values(u.logs).map((v) => `<td class="mono">${v ?? "–"}`).join("")}</tr></table></div>`;
      const used = P.filter((p) => p.llr != null), pos = css("--acc"), neg = css("--bad");
      plot($("#wf"), [{ type: "waterfall", orientation: "h", y: used.map((p) => names[p.layer] || p.layer), x: used.map((p) => p.llr), measure: used.map((_, i) => (i === 0 ? "absolute" : "relative")), connector: { line: { color: css("--line") } }, increasing: { marker: { color: pos } }, decreasing: { marker: { color: neg } }, totals: { marker: { color: css("--mut") } }, text: used.map((p) => (p.llr > 0 ? "+" : "") + f2(p.llr)), textposition: "outside" }],
        { xaxis: { title: "log-odds (right = more likely)" }, yaxis: { autorange: "reversed" }, margin: { l: 190, r: 40, t: 10, b: 44 } });
      bindLayers(draw); };
    await draw();
  },

  async layers() {
    $("#view").innerHTML = `<h1>Evidence layers</h1>${what("", "A <b>layer</b> is one kind of data turned into a nudge up or down. We only keep a layer switched on if testing on unseen wells shows it does not hurt. <b>Helped</b> = tested better than not using it. <b>No measurable help</b> = indistinguishable from nothing. <b>Made it worse</b> = off by default. <b>Not built</b> = a place reserved for it.",
      "New data types (seismic cubes, more logs) are added as new layers without changing the rest.")}<div class="grid g2" id="lc"></div>`;
    const stat = { strat: "Counts how often geologists wrote a green mineral in this rock formation across all wells, smoothed so small samples do not mislead.", spatial: "Looks at wells of the same formation nearby (within 60 km) and weights them by closeness: green rocks tend to cluster.", logs: "Instrument readings along the well (gamma, density, neutron, etc.) compared with the formation's normal.", seismic: "Reflections of sound waves in 3D. Would add information between wells. Not built: no seismic cube is linked to these wells yet." };
    $("#lc").innerHTML = LAYERS.map((l) => `<div class="card"><div class="row" style="margin:0 0 6px"><h2 style="margin:0">${esc(l.title)}</h2>${pill(l.status, STATUS_WORDS[l.status])}${l.on_by_default ? pill("ok", "on by default") : pill("muted", "off by default")}</div><p>${stat[l.name] || ""}</p><p class="tip">${esc(l.doc)}</p>${l.name === "logs" && l.params.weights ? '<div id="lw" class="plot" style="height:260px"></div>' : ""}</div>`).join("");
    const lg = LAYERS.find((l) => l.name === "logs");
    if (lg?.params.weights) { const w = Object.entries(lg.params.weights); plot($("#lw"), [{ type: "bar", orientation: "h", y: w.map((x) => x[0]), x: w.map((x) => x[1].w), marker: { color: w.map((x) => (x[1].stable_sign >= 0.9 ? css("--acc") : css("--mut"))) }, error_x: { type: "data", symmetric: false, array: w.map((x) => x[1].p95 - x[1].w), arrayminus: w.map((x) => x[1].w - x[1].p05), color: css("--mut") }, hovertemplate: "%{y}: %{x:.2f}<extra></extra>" }],
      { title: { text: "log weights (bars: fitted, lines: 90% over resampled wells; green = same sign in ≥90% of resamples)", font: { size: 11 } }, yaxis: { autorange: "reversed" }, margin: { l: 60, r: 10, t: 40, b: 30 } }); }
  },

  async knowledge() {
    const k = await api("kb");
    $("#view").innerHTML = `<h1>Knowledge</h1>${what("", "Textbook geology rules written down with a link to where they come from. Each one is <b>tested against the data</b>: <b>agrees</b> = data point the way the rule says, <b>disagrees</b> = the other way, <b>inconclusive</b> = the data cannot tell. A rule is never trusted blindly and never hidden when the data disagree.",
      "<b>AUC</b> is the chance that a green row has a higher value than a not-green row: 0.5 = no difference. Seven checks per rock type: about one false hit by chance is expected.")}
    <div class="grid g2">${k.map((r) => `<div class="card"><div class="row" style="margin:0 0 6px"><h2 style="margin:0">${esc(r.id)}</h2>${pill(r.verdict, "data " + r.verdict.replace("_", " "))}${pill(r.status === "sourced" ? "helps" : r.status === "inferred" ? "no_evidence" : "plain", r.status.replace("_", " "))}</div>
    <p>${esc(r.statement)}</p>${r.caveat ? `<p class="tip">${esc(r.caveat)}</p>` : ""}<p class="mono" style="color:var(--mut)">${esc(r.numbers)}</p><p>${r.sources.map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.says)}</a>`).join("<br>")}</p></div>`).join("")}</div>`;
  },

  async validation() {
    const r = await api("validation"), d = r.delta, ab = r.ablation;
    $("#view").innerHTML = `<h1>Validation</h1>${what("", "The scorecard. We hide whole areas (40 km blocks) of wells, fit the model on the rest, and see how well it predicts the hidden ones. <b>Gain</b> = how much better than guessing the overall rate (bigger = better; 0 = no better). Lines on charts are 90% ranges from resampling whole wells.",
      "Message: formation gives a small real gain; nearby wells and well logs do not show a measurable gain on this target. This is shown here on purpose.")}
    <div class="grid g2"><div class="card"><h2>Does each layer help?</h2><p class="tip">Gain difference with 90% range. Range entirely right of 0 = helps; spanning 0 = no evidence; entirely left = hurts.</p><div id="v1" class="plot" style="height:280px"></div></div>
    <div class="card"><h2>Combinations</h2><p class="tip">Gain for each set of layers on all ${ab.strat.units.toLocaleString()} test units.</p><div id="v2" class="plot" style="height:280px"></div></div>
    <div class="card"><h2>Are the numbers honest?</h2><p class="tip">Predicted vs observed rate in 10 groups. On the dashed line = calibrated.</p><div id="v3" class="plot" style="height:300px"></div></div>
    <div class="card"><h2>Distance to the nearest training well</h2><p class="tip">Gain with and without neighbours, by distance (km).</p><div id="v4" class="plot" style="height:300px"></div></div>
    <div class="card"><h2>Smoothing choices barely matter</h2><p class="tip">Gain for different neighbourhood sizes (km). Flat = no tuning needed.</p><div id="v5" class="plot" style="height:280px"></div></div>
    <div class="card"><h2>Skill by amount of description</h2><p class="tip">AUC by rows per unit. 0.5 = nothing, 1 = perfect.</p><div id="v6" class="plot" style="height:280px"></div></div></div>`;
    const ent = Object.entries(d), acc = css("--acc"), bad = css("--bad"), mut = css("--mut");
    plot($("#v1"), [{ type: "scatter", mode: "markers", y: ent.map((e) => e[0].replaceAll("_", " ")), x: ent.map((e) => e[1].delta_gain), marker: { size: 11, color: ent.map((e) => (e[1].p05 > 0 ? acc : e[1].p95 < 0 ? bad : mut)) }, error_x: { type: "data", symmetric: false, array: ent.map((e) => e[1].p95 - e[1].delta_gain), arrayminus: ent.map((e) => e[1].delta_gain - e[1].p05), color: mut } }],
      { xaxis: { title: "gain difference", zeroline: true, zerolinewidth: 2, zerolinecolor: mut }, yaxis: { autorange: "reversed" }, margin: { l: 250, r: 20, t: 10, b: 44 } });
    plot($("#v2"), [{ type: "bar", x: Object.keys(ab), y: Object.values(ab).map((v) => v.deviance_gain), marker: { color: acc }, hovertemplate: "%{x}: %{y:.4f}<extra></extra>" }], { yaxis: { title: "deviance gain", rangemode: "tozero" } });
    const rc = r.reliability_calibrated; plot($("#v3"), [{ type: "scatter", mode: "markers+lines", x: rc.map((x) => x.predicted * 100), y: rc.map((x) => x.observed * 100), marker: { color: acc, size: rc.map((x) => 5 + x.rows / 1500) }, line: { color: acc, width: 1 }, name: "calibrated" },
      { type: "scatter", mode: "markers", x: r.reliability_raw.map((x) => x.predicted * 100), y: r.reliability_raw.map((x) => x.observed * 100), marker: { color: mut, symbol: "x" }, name: "raw" }, { type: "scatter", mode: "lines", x: [0, 12], y: [0, 12], line: { dash: "dash", color: css("--line") }, name: "ideal", showlegend: false }],
      { xaxis: { title: "predicted %" }, yaxis: { title: "observed %" } });
    plot($("#v4"), [{ type: "bar", name: "formation only", x: r.by_distance.map((x) => `${x.from_km}–${x.to_km}`), y: r.by_distance.map((x) => x.gain_strat_only), marker: { color: mut } }, { type: "bar", name: "+ neighbours", x: r.by_distance.map((x) => `${x.from_km}–${x.to_km}`), y: r.by_distance.map((x) => x.deviance_gain), marker: { color: acc } }], { barmode: "group", yaxis: { title: "deviance gain" }, xaxis: { title: "km to nearest training well" } });
    plot($("#v5"), [{ type: "scatter", mode: "lines+markers", x: r.sweep_ell.map((x) => x.ell_km), y: r.sweep_ell.map((x) => x.deviance_gain), line: { color: acc } }], { xaxis: { type: "log", title: "neighbourhood size (km)" }, yaxis: { title: "deviance gain", rangemode: "tozero" } });
    plot($("#v6"), [{ type: "bar", x: r.by_coverage.map((x) => x.coverage + " (n=" + x.n + ")"), y: r.by_coverage.map((x) => x.auc), marker: { color: acc } }], { yaxis: { title: "AUC", range: [0.4, 0.8] }, shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0.5, y1: 0.5, line: { dash: "dash", color: mut } }] });
  },

  async contradictions() {
    const c = await api("contradictions"), t = (rows, kind) => `<table><tr><th>unit<th>rows<th>green<th>model said<th>${kind}</tr>${rows.slice(0, 25).map((x) => `<tr class="click" data-u="${esc(x.unit)}"><td>${esc(x.unit)}<td>${x.coverage}<td>${x.n_green}<td>${pct(x.p_full)}<td class="mono">${(x.tail_many ?? x.tail_none)?.toExponential(1)}</tr>`).join("")}</table>`;
    $("#view").innerHTML = `<h1>Contradictions</h1>${what("", "Places where what geologists <b>wrote</b> disagrees most with what the model <b>expected</b>. Either the model is missing something, the report is unusual, or it is a place worth a second look. These are candidates for review, not errors.")}
    <div class="grid g2"><div class="card"><h2>Much greener than expected</h2>${t(c.reported_but_unexpected, "chance")}</div><div class="card"><h2>Expected green, none written</h2>${t(c.expected_but_not_reported, "chance")}</div></div>`;
    $("#view").onclick = (e) => { const r = e.target.closest("tr[data-u]"); if (r) location.hash = "unit/" + encodeURIComponent(r.dataset.u); };
  },

  async log() { const l = await api("log"); $("#view").innerHTML = `<h1>Decision log</h1>${what("", "Every choice, number, mistake and correction, in order, with the reasoning. Nothing is edited after the fact: wrong turns stay marked so the work can be backtracked.")}<div class="card md">${marked.parse(l.markdown)}</div>`; },
};
init();
