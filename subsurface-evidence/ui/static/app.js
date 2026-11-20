// Subsurface Evidence UI. One file, no build. Every number comes from /api; every page says what it shows.
const $$ = (s, r = document) => [...r.querySelectorAll(s)], $ = (s, r = document) => r.querySelector(s), NOTARGET = /^(catalog|table\/|targets|last_job|log|docs-list|seismic\/|provenance\/|earth\/)/;
const FEATN = { lp: "unit rate", lnb: "neighbours' rate", sand: "sand share", shale: "shale share", zb_km: "depth below seabed", phi_athy: "compaction porosity", deltaic: "deltaic unit",
  lkit: "distance to mature source", lkit_max: "distance to source mature at maximum burial", lkit_gas: "distance to gas-mature source", mature: "source below in the oil window", lfault: "distance to a mapped fault",
  on_high: "on a structural high", lclos: "structural closure", salt: "salt thickness", lcharge: "migrated charge", lcharge_max: "migrated charge at maximum burial",
  p_charge: "reached by migrating oil", p_charge_max: "reached by migrating oil at maximum burial" };
let META, LAYERS, TARGET = localStorage.getItem("target") || "green_clay", map = null, COAST = null, TARGETS = null;
// Every request is tracked: the header shows what is running and for how long, a bar runs under the header, and stages show a centred notice.
const BUSY = new Map(); let busyId = 0;
const LABELS = { scene: "3D scene: wells, estimate sheets, unusual areas", map: "map grid", units: "units table", unit: "unit evidence", validation: "validation results", hotspots: "unusual areas", "jobs/map": "fine map (GPU worker; first start can take minutes)", "targets/build": "building and validating the target (about 35 s)", log: "decision log", catalog: "data catalog" };
function track(label, p) { const id = ++busyId; BUSY.set(id, { label, t: Date.now() }); paintBusy(); return p.finally(() => { BUSY.delete(id); paintBusy(); }); }
function paintBusy() { document.body.classList.toggle("busy", BUSY.size > 0); const v = [...BUSY.values()], txt = v.map((b) => `${b.label} (${Math.round((Date.now() - b.t) / 1000)} s)`).join(" · ");
  const el = $("#busy"); if (el) el.textContent = v.length ? "Working: " + txt : ""; const w = $("#wait"); if (w) { w.style.display = v.length ? "" : "none"; w.querySelector("span").textContent = "Working: " + txt; } }
setInterval(paintBusy, 500);
const api = (p, q = {}) => track(LABELS[p] || p, fetch("api/" + p + "?" + new URLSearchParams(NOTARGET.test(p) ? q : { target: TARGET, ...q })).then((r) => r.json()));
const pct = (x, d = 1) => (x == null ? "–" : (100 * x).toFixed(d) + "%"), f2 = (x, d = 2) => (x == null ? "–" : (+x).toFixed(d)), sg = (x, d = 3) => (x == null ? "–" : (x > 0 ? "+" : "") + (+x).toFixed(d));
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim(), W = () => META.words;
const tag = (cls, t, tip) => `<span class="tag ${cls}"${tip ? ` title="${esc(tip)}"` : ""}>${esc(t || cls.replace("_", " "))}</span>`;
const note = (title, ...l) => `<div class="note"><b>${title}</b>${l.map((x) => `<p>${x}</p>`).join("")}</div>`;
const STATUS_WORDS = { helps: "helps", no_evidence: "no measurable help", hurts: "makes it worse", not_built: "not built / no data" };
const evTip = (l) => { const e = l.evidence; if (!e) return l.status === "not_built" ? "Nothing to test: no code or no data for this evidence." : ""; const verb = l.status === "helps" ? "improved" : l.status === "hurts" ? "worsened" : "did not measurably change";
  return `On wells held out of fitting, adding this ${verb} prediction accuracy by ${sg(e.delta_gain)} (90% range ${sg(e.p05)} to ${sg(e.p95)}), compared with ${e.compared_with}${e.units ? `, on ${e.units} units` : ""}. Range entirely above 0 = helps; spanning 0 = no evidence; entirely below 0 = worse.`; };
const NAV = [["screen", "Smeaheia"], ["tracks", "Well tracks"], ["research", "Research"], ["log", "Decision log"]];
// secondary pages live under one tab each, reached by the sub-navigation at the top of that tab (old links keep working)
const SUB = { earth: [["earth", "Model"], ["rpt", "Rock physics"], ["scene", "Saved targets (depth along the hole)"]], units: [["units", "All units"], ["contradictions", "Most surprising"]], validation: [["validation", "Scorecard"], ["layers", "Layers"], ["knowledge", "Geology rules"], ["sensitivity", "Sensitivity"]],
  data: [["data", "Catalog"], ["lineage", "Lineage"], ["workflows", "Other tools"]], architecture: [["architecture", "Charts"], ["start", "Overview and terms"]] };
const PARENT = Object.fromEntries(Object.entries(SUB).flatMap(([k, v]) => v.map(([p]) => [p, k]))); PARENT.unit = "units";
// Colour palettes for shares (low to high). `stops` colour sheets, map shading and legends; `bins` colour the four stick classes (the last is the strongest: above the colour range).
const PALS = {
  blue: { name: "Blue (soft)", stops: [[0, "#c6dbef"], [0.4, "#6baed6"], [0.7, "#2171b5"], [1, "#08306b"]], bins: ["#9ecae1", "#4292c6", "#08519c", "#d95f02"] },
  viridis: { name: "High contrast (viridis, colour-blind safe)", stops: [[0, "#440154"], [0.25, "#3b528b"], [0.5, "#21918c"], [0.75, "#5ec962"], [1, "#fde725"]], bins: ["#440154", "#31688e", "#35b779", "#fde725"] },
  warm: { name: "Warm (yellow to dark red)", stops: [[0, "#ffeda0"], [0.35, "#fd8d3c"], [0.7, "#e31a1c"], [1, "#67000d"]], bins: ["#fed976", "#fd8d3c", "#e31a1c", "#67000d"] },
  gray: { name: "Grey to black (print)", stops: [[0, "#e6e6e6"], [1, "#111111"]], bins: ["#cccccc", "#888888", "#444444", "#d95f02"] },
};
let STICKS = [], PAL = localStorage.getItem("pal") || "blue", CMAX = +localStorage.getItem("cmax") || 0.2, CMIN = +localStorage.getItem("cmin") || 0;
const pal = () => PALS[PAL] || PALS.blue;
const rampCss = () => `linear-gradient(90deg, ${pal().stops.map(([p, c]) => `${c} ${p * 100}%`).join(",")})`;
const palUI = () => `<div class="row"><label>Colours <select id="pal">${Object.entries(PALS).map(([k, v]) => `<option value="${k}" ${k === PAL ? "selected" : ""}>${v.name}</option>`).join("")}</select></label></div>
  <div class="row" title="Shares at or below the low end get the lightest colour, shares at or above the high end the strongest. Narrow the range to separate small differences, move the low end up to ignore the very low values."><span class="tip">colour range</span> <label class="chk">from <input type="range" id="cmin" min="0" max="0.58" step="0.005" value="${CMIN}" style="width:90px"> <span id="cminv">${pct(CMIN, CMIN < 0.1 ? 1 : 0)}</span></label> <label class="chk">to <input type="range" id="cmax" min="0.02" max="0.6" step="0.005" value="${CMAX}" style="width:90px"> <span id="cmaxv">${pct(CMAX, CMAX < 0.1 ? 1 : 0)}</span></label></div>`;
function bindPal(redraw) { const fmt = (x) => pct(x, x < 0.1 ? 1 : 0), save = () => { localStorage.setItem("cmin", CMIN); localStorage.setItem("cmax", CMAX); $("#cminv").textContent = fmt(CMIN); $("#cmaxv").textContent = fmt(CMAX); $("#cmin").value = CMIN; $("#cmax").value = CMAX; };
  $("#pal").onchange = (e) => { PAL = e.target.value; localStorage.setItem("pal", PAL); redraw(); };
  $("#cmin").oninput = (e) => { CMIN = Math.min(+e.target.value, CMAX - 0.01); save(); redraw(); };  // the low end always stays below the high end
  $("#cmax").oninput = (e) => { CMAX = Math.max(+e.target.value, CMIN + 0.01); save(); redraw(); }; }

function plot(el, data, layout = {}, cfg = {}) {
  const ink = css("--ink"), mut = css("--mut"), rule = css("--rule"), ax = { gridcolor: rule, zerolinecolor: rule, linecolor: ink, color: mut, ticks: "outside", tickcolor: rule };
  const L = { paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { family: "Inter, system-ui", color: ink, size: 12 }, margin: { l: 56, r: 16, t: 14, b: 44 }, legend: { orientation: "h", y: -0.22 }, ...layout, xaxis: { ...ax, ...(layout.xaxis || {}) }, yaxis: { ...ax, ...(layout.yaxis || {}) } };
  return Plotly.react(el, data, L, { displaylogo: false, responsive: true, ...cfg });
}
// WebGL scenes can fail once while the container is still being sized: purge and try again before giving up
async function plot3(el, data, layout) { const L = { ...layout, autosize: false, width: el.clientWidth || undefined, height: el.clientHeight || undefined };  // explicit size: the scene follows its container exactly, and only when we redraw
  // doubleClick off: a quick second click (e.g. on a well stick) must not reset the view
  try { return await plot(el, data, L, { responsive: false, doubleClick: false }); } catch (e) { console.warn("3D plot failed once, retrying:", e); Plotly.purge(el); await new Promise((r) => setTimeout(r, 500)); return plot(el, data, L, { responsive: false, doubleClick: false }); } }
const PERF = (() => { try { return localStorage.getItem("perf") === "1"; } catch { return false; } })(), tick = () => performance.now();  // localStorage.perf = "1" logs where a 3D refresh spends its time
const fig = (id, h, cap) => `<figure><div id="${id}" style="height:${h}px"></div><figcaption>${cap}</figcaption></figure>`;

// ---- floating panes over a full-screen stage ----
// ---- layout of the 3D page: settings on the left, information on the right. Both collapse to a strip, fold into sections, and remember their width and state.
// 3D scenes are redrawn, not resized: Plotly's resize of a WebGL scene can throw "axis scaling" and leave a stale canvas. A redraw is cheap (the data is cached).
const REDRAW = {}, fitPlots = (() => { let t; return () => { clearTimeout(t); t = setTimeout(() => { const pw = $(".plotwrap"); if (pw && REDRAW.k !== pw.clientWidth + "x" + pw.clientHeight) REDRAW.scene?.(); REDRAW.insp?.(); }, 120); }; })();
let stageObserver;
const setCol = (sd) => { const el = $("#side" + sd), b = $("#col" + sd); if (el && b) { const shut = el.classList.contains("shut"); b.textContent = (sd === "L") === shut ? "›" : "‹"; b.setAttribute("aria-expanded", String(!shut)); } };
function stage2(inner, readView) {
  $("#view").innerHTML = `<div class="stage2"><aside class="side" id="sideL"><div class="sh"><b>Settings</b><span><button class="lnk" id="resetside" title="Forget widths and folded sections">reset</button><button id="colL" title="Collapse or expand the settings">‹</button></span></div><div class="sb" id="sbL"></div><div class="grip" id="gripL"></div></aside>
    <div class="plotwrap">${inner}<div class="wait" id="wait" style="display:none"><i></i><span></span></div></div>
    <aside class="side right" id="sideR"><div class="grip" id="gripR"></div><div class="sh">
      <b class="sh-rail">Evidence</b>
      <div class="pane-tabs" role="tablist" aria-label="Evidence pane">
        <button class="pane-tab" id="infoTab" role="tab" data-pane="info" aria-controls="sbR">Information</button>
        <button class="pane-tab" id="deskTab" role="tab" data-pane="desk" aria-controls="deskPane">${DESK_NAME}</button>
      </div><span><button id="colR" title="Collapse or expand the evidence pane">›</button></span>
    </div><div class="sb" id="sbR" role="tabpanel" aria-labelledby="infoTab"></div>
    <div class="sb desk-pane" id="deskPane" role="tabpanel" aria-labelledby="deskTab" hidden>
      <header class="desk-head"><div class="desk-heading"><h2>${DESK_NAME}</h2><button class="lnk" id="desk-clear" type="button">New thread</button></div><p id="desk-scope" class="tip"></p></header>
      <div id="desk-transcript" class="desk-transcript" role="log" aria-label="Conversation">
        <div id="desk-samples" class="desk-samples"><p>An assistant for reading the model and its sources: Diskos reports, FactPages, and on the Earth model page the model's own numbers, tests and rules. Select a cell or a well interval to focus it.</p>
        <button class="lnk" type="button" data-question="What is observed and what is estimated in this view?">Explain this view</button>
        <button class="lnk" type="button" data-question="Why does the selected cell have this probability, and what should I check before trusting it?">Why this number?</button>
        <button class="lnk" type="button" data-question="Which assumptions does this rest on, and do their rules hold in this region?">Check the assumptions</button>
        <button class="lnk" type="button" data-question="What would change this conclusion, and which data would settle it?">What would change it?</button>
        <button class="lnk" type="button" data-question="What does turning on neighbour evidence change, and what is still uncertain?">Explain neighbour evidence</button></div>
      </div>
      <form class="desk-form"><label for="desk-question">Question</label><textarea id="desk-question" rows="3" placeholder="Ask about this view or name a wellbore…" required minlength="3" maxlength="2000"></textarea>
        <div class="desk-controls"><span id="desk-status" class="tip" role="status"></span><button class="btn on" type="submit">Ask</button></div></form>
    </div></aside></div>`;
  const tabs = $$("[data-pane]", $("#sideR"));
  const showPane = (name) => {
    $("#sbR").hidden = name !== "info"; $("#deskPane").hidden = name !== "desk";
    tabs.forEach((b) => { const selected = b.dataset.pane === name; b.setAttribute("aria-selected", String(selected)); b.tabIndex = selected ? 0 : -1; });
    localStorage.setItem("sideR:pane", name);
  };
  for (const b of tabs) {
    b.onclick = () => showPane(b.dataset.pane);
    b.onkeydown = (e) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
      e.preventDefault();
      const next = e.key === "Home" ? tabs[0] : e.key === "End" ? tabs[1] : tabs.find((t) => t !== b);
      showPane(next.dataset.pane); next.focus();
    };
  }
  const saved = localStorage.getItem("sideR:pane");
  showPane(saved === "agent" || saved === "desk" ? "desk" : "info");
  for (const sd of ["L", "R"]) { const el = $("#side" + sd), grip = $("#grip" + sd); el.style.setProperty("--w", (+localStorage.getItem(`side:${sd}:w`) || (sd === "L" ? 330 : 430)) + "px"); el.classList.toggle("shut", localStorage.getItem(`side:${sd}:shut`) === "1"); setCol(sd);
    $("#col" + sd).onclick = () => { el.classList.toggle("shut"); localStorage.setItem(`side:${sd}:shut`, el.classList.contains("shut") ? "1" : "0"); setCol(sd); fitPlots(); };
    grip.onpointerdown = (e) => { grip.setPointerCapture(e.pointerId); const x0 = e.clientX, w0 = el.getBoundingClientRect().width; grip.onpointermove = (m) => el.style.setProperty("--w", Math.max(240, Math.min(900, w0 + (m.clientX - x0) * (sd === "L" ? 1 : -1))) + "px");
      grip.onpointerup = () => { grip.onpointermove = null; localStorage.setItem(`side:${sd}:w`, parseInt(el.style.getPropertyValue("--w"))); fitPlots(); }; }; }
  $("#resetside").onclick = () => { Object.keys(localStorage).filter((k) => /^(side|sec):/.test(k)).forEach((k) => localStorage.removeItem(k)); route(); };
  let firstRO = true;
  stageObserver = new ResizeObserver(() => { if (firstRO) { firstRO = false; return; } fitPlots(); });
  stageObserver.observe($(".plotwrap"));
  const desk = mountDesk($("#deskPane"), readView);
  return { ...desk, open(q) { $("#sideR").classList.remove("shut"); setCol("R"); showPane("desk"); desk.draft(q); fitPlots(); } };
}
function sec(side, id, title, body, open = true) {  // one foldable section in a sidebar; its state is remembered
  const key = "sec:" + id, saved = localStorage.getItem(key), isOpen = saved == null ? open : saved === "1", el = document.createElement("section"); el.className = "sec" + (isOpen ? "" : " fold"); el.id = "sec-" + id;
  el.innerHTML = `<div class="sech"><span class="car"></span>${title}</div><div class="secb">${body}</div>`; $("#sb" + side).appendChild(el);
  $(".sech", el).onclick = () => { el.classList.toggle("fold"); localStorage.setItem(key, el.classList.contains("fold") ? "0" : "1"); fitPlots(); }; return el; }
function widenRight(on) { const el = $("#sideR"); if (!el) return;  // the inspector needs room: widen the information pane while it is open, restore after
  if (on) { el._w0 = el.style.getPropertyValue("--w"); el.style.setProperty("--w", Math.max(parseInt(el._w0) || 430, 620) + "px"); el.classList.remove("shut"); setCol("R"); } else if (el._w0) el.style.setProperty("--w", el._w0); fitPlots(); }

async function init() {
  $("#links").innerHTML = NAV.map(([k, t]) => `<a href="#${k}" data-p="${k}">${t}</a>`).join("");
  $("#theme").onclick = () => { const d = document.documentElement; d.dataset.theme = (d.dataset.theme || (matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light")) === "dark" ? "light" : "dark"; route(); };
  $("#target").onchange = async (e) => { TARGET = e.target.value; localStorage.setItem("target", TARGET); await loadTarget(); route(); };
  addEventListener("hashchange", route); addEventListener("resize", fitPlots); route();
  setInterval(() => { if (!$("#job").hidden) job(); }, 15000);
}
const assetPromises = new Map(), researchScripts = {
  plot: "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js",
  leaf: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js",
  topo: "https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js",
  marked: "https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js",
  mermaid: "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js",
};
function researchAssets(p) {
  const keys = [];
  if (["earth","rpt","scene","data","unit","validation","layers","start"].includes(p)) keys.push("plot");
  if (["earth","data"].includes(p)) {
    keys.push("leaf");
    if (!$("#leaf-css")) { const l = document.createElement("link"); l.id = "leaf-css"; l.rel = "stylesheet"; l.href = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css"; document.head.append(l); }
  }
  if (["earth","scene"].includes(p)) keys.push("topo", "marked");
  if (p === "rpt") keys.push("marked");
  if (p === "architecture") keys.push("marked", "mermaid");
  return Promise.all(keys.map((k) => {
    if (!assetPromises.has(k)) assetPromises.set(k, new Promise((ok, fail) => {
      const s = document.createElement("script"); s.src = researchScripts[k]; s.onload = ok;
      s.onerror = () => { assetPromises.delete(k); s.remove(); fail(new Error("Could not load research chart library: " + k)); }; document.head.append(s);
    }));
    return assetPromises.get(k);
  }));
}
async function loadTarget() { TARGETS = await api("targets"); const all = [TARGETS.builtin, ...TARGETS.saved]; if (!all.some((t) => t.id === TARGET)) TARGET = "green_clay";
  $("#target").innerHTML = all.map((t) => `<option value="${t.id}" ${t.id === TARGET ? "selected" : ""}>${esc(t.title)}</option>`).join(""); META = await api("meta"); LAYERS = await api("layers"); }
const job = async () => { const j = await api("last_job"); $("#job").textContent = j.job ? `last heavy job: ${j.job}, ${j.via}, ${j.seconds}s` : ""; };
let routeSeq = 0;
const pageError = (e) => doc(`<div class="note warn"><b>Could not load this page</b><pre>${esc(String(e.stack || e).slice(0, 900))}</pre></div>`);
async function route() {
  const [p, ...rest] = (location.hash.slice(1) || "screen").split("/");
  const seq = ++routeSeq, live = () => seq === routeSeq;
  stageObserver?.disconnect(); closeDesk(); REDRAW.scene = REDRAW.insp = null;
  document.querySelectorAll("#links a").forEach((a) => {
    const selected = a.dataset.p === (["screen","log","tracks"].includes(p) ? p : "research");
    a.classList.toggle("on", selected);
    if (selected) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  if (map) { map.remove(); map = null; } $("#view").innerHTML = '<div class="doc"><p class="tip">loading…</p></div>';
  if (p === "map") { location.hash = "earth"; return; }  // old addresses land on the subsurface model
  const needsTarget = ["start","scene","units","unit","contradictions","targets","validation","layers","knowledge"].includes(p);
  $("#target").closest("label").hidden = !needsTarget; $("#job").hidden = !needsTarget;
  try {
    await Promise.all([researchAssets(p), needsTarget && (!META || !LAYERS) ? loadTarget() : null]);
    if (!live()) return;
    await (PAGES[p] || PAGES.research)(decodeURIComponent(rest.join("/")), live);
    const sub = SUB[PARENT[p]], d = $("#view .doc");
    const nav = sub && `<nav class="subnav">${sub.map(([k, t]) => `<a href="#${k}" class="${k === p ? "on" : ""}">${t}</a>`).join("")}</nav>`;
    if (live() && sub && d) d.insertAdjacentHTML("afterbegin", nav);
    else if (live() && sub && $("#sbL")) $("#sbL").insertAdjacentHTML("afterbegin", nav.replace('class="subnav"', 'class="subnav side"'));  // 3D pages: the views switch in the sidebar
  } catch (e) { if (live()) pageError(e); }
}
const doc = (h) => ($("#view").innerHTML = `<div class="doc">${h}</div>`);
let use = null;
const useNow = () => (use && use.target === TARGET ? use.v : (use = { target: TARGET, v: LAYERS.filter((l) => l.on_by_default).map((l) => l.name) }).v);
const layerBox = () => `<span class="tip">evidence used:</span> ` + LAYERS.filter((l) => l.built).map((l) => `<label class="chk" title="${esc(evTip(l))}"><input type="checkbox" data-l="${l.name}" ${useNow().includes(l.name) ? "checked" : ""}> ${esc(l.title)} ${tag(l.status, STATUS_WORDS[l.status])}</label>`).join(" ");
function bindLayers(re) { document.querySelectorAll("[data-l]").forEach((c) => (c.onchange = () => { use = { target: TARGET, v: [...document.querySelectorAll("[data-l]")].filter((x) => x.checked).map((x) => x.dataset.l) }; re(); })); }
async function coast() { if (COAST) return COAST; try { const t = await fetch("https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json").then((r) => r.json()); COAST = topojson.mesh(t, t.objects.countries).coordinates; } catch { COAST = []; } return COAST; }
const KMX = (lon) => (lon - 3) * 111.32 * Math.cos((61 * Math.PI) / 180), KMY = (lat) => (lat - 61) * 110.57; // same frame as the scene API
async function mapLines(b) { const out = [], m = 80, ok = (x, y) => x >= b.x0 - m && x <= b.x1 + m && y >= b.y0 - m && y <= b.y1 + m, cx = [], cy = [], cz = [];
  (await coast()).forEach((ln) => { let open = false; ln.forEach(([lo, la]) => { const x = KMX(lo), y = KMY(la); if (ok(x, y)) { cx.push(x); cy.push(y); cz.push(0); open = true; } else if (open) { cx.push(null); cy.push(null); cz.push(null); open = false; } }); cx.push(null); cy.push(null); cz.push(null); });
  out.push({ type: "scatter3d", mode: "lines", x: cx, y: cy, z: cz, line: { color: css("--mut"), width: 3 }, hoverinfo: "skip", showlegend: false });
  const gx = [], gy = [], gz = [], tx = [], ty = [], tt = []; for (let la = 50; la <= 80; la += 2) { const y = KMY(la); if (y < b.y0 - m || y > b.y1 + m) continue; gx.push(b.x0 - m, b.x1 + m, null); gy.push(y, y, null); gz.push(0, 0, null); tx.push(b.x0 - m); ty.push(y); tt.push(la + "°N"); }
  for (let lo = -10; lo <= 40; lo += 5) { const x = KMX(lo); if (x < b.x0 - m || x > b.x1 + m) continue; gx.push(x, x, null); gy.push(b.y0 - m, b.y1 + m, null); gz.push(0, 0, null); tx.push(x); ty.push(b.y0 - m); tt.push(lo + "°E"); }
  out.push({ type: "scatter3d", mode: "lines", x: gx, y: gy, z: gz, line: { color: css("--rule"), width: 1 }, hoverinfo: "skip", showlegend: false }, { type: "scatter3d", mode: "text", x: tx, y: ty, z: tx.map(() => 0), text: tt, textfont: { size: 10, color: css("--mut") }, hoverinfo: "skip", showlegend: false });
  return out; }
const osm = () => L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap contributors", maxZoom: 18 });

function panZoom(box) {
  const inner = box.querySelector(".pzin"), svg = inner.querySelector("svg"); let k = 1, x = 0, y = 0, drag = null;
  const set = () => (inner.style.transform = `translate(${x}px,${y}px) scale(${k})`);
  const fit = () => { const w = svg.getBBox ? svg.viewBox.baseVal.width || svg.getBoundingClientRect().width / k : 800, h = svg.viewBox.baseVal.height || 400;
    svg.setAttribute("width", w); svg.setAttribute("height", h); k = Math.min(box.clientWidth / w, (box.clientHeight - 30) / h, 1.5); x = (box.clientWidth - w * k) / 2; y = 30; set(); };
  const zoom = (f, cx = box.clientWidth / 2, cy = box.clientHeight / 2) => { const nk = Math.min(Math.max(k * f, 0.1), 8); x = cx - ((cx - x) * nk) / k; y = cy - ((cy - y) * nk) / k; k = nk; set(); };
  box.onwheel = (e) => { e.preventDefault(); const r = box.getBoundingClientRect(); zoom(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - r.left, e.clientY - r.top); };
  box.onpointerdown = (e) => { if (e.target.closest("button")) return; drag = [e.clientX - x, e.clientY - y]; box.setPointerCapture(e.pointerId); box.classList.add("grab"); };
  box.onpointermove = (e) => { if (drag) { x = e.clientX - drag[0]; y = e.clientY - drag[1]; set(); } };
  box.onpointerup = () => { drag = null; box.classList.remove("grab"); };
  box.ondblclick = fit;
  box.querySelector(".pzbar").onclick = (e) => { const z = e.target.dataset.z; if (!z) return; if (z === "fit") fit(); else if (z === "full") { box.classList.toggle("pzfull"); requestAnimationFrame(fit); } else zoom(+z); };
  requestAnimationFrame(fit);
}

const MAXF = 30;  // formations shown at once in the 3D view: a guard on draw time, not a data limit
let TIED = null;  // tied seismic horizons, fetched once
// a small map of the Norwegian shelf in a corner of the stage, with the area in view as a box (equirectangular, cos-latitude scaled)
async function minimap(host, box, label) {
  const L0 = -4, L1 = 32, B0 = 55.5, B1 = 72.5, W = 180, k = Math.cos((64 * Math.PI) / 180), H = Math.round((W * (B1 - B0)) / ((L1 - L0) * k));
  const px = (lo) => ((lo - L0) / (L1 - L0)) * W, py = (la) => H - ((la - B0) / (B1 - B0)) * H;
  const lines = (await coast()).map((ln) => ln.filter(([lo, la]) => lo > L0 - 2 && lo < L1 + 2 && la > B0 - 2 && la < B1 + 2).map(([lo, la]) => `${px(lo).toFixed(1)},${py(la).toFixed(1)}`).join(" ")).filter((s) => s.length);
  const [la0, la1] = box.lat, [lo0, lo1] = box.lon;
  let el = host.querySelector(".minimap"); if (!el) { el = document.createElement("div"); el.className = "minimap"; host.appendChild(el); }
  el.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Map of the Norwegian shelf with the area in view"><title>${esc(label)}</title>
    ${lines.map((p) => `<polyline points="${p}" fill="none" stroke="var(--mut)" stroke-width="0.7"/>`).join("")}
    ${[62, 69].map((la) => `<line x1="0" x2="${W}" y1="${py(la)}" y2="${py(la)}" stroke="var(--rule)" stroke-dasharray="2,2"/>`).join("")}
    <rect x="${px(lo0)}" y="${py(la1)}" width="${px(lo1) - px(lo0)}" height="${py(la0) - py(la1)}" fill="rgba(224,33,138,0.25)" stroke="#e0218a" stroke-width="1.5"/>
    <text x="4" y="${H - 4}" font-size="9" fill="var(--mut)">North Sea · Norwegian Sea (62°N) · Barents Sea (69°N)</text></svg><div class="tip">${esc(label)}</div>`;
}
// layer colours: distinct, muted enough to sit under the viridis cells; one per group or formation, the same in the list and the scene
const LAYC = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#76b7b2", "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#86bcb6", "#d4a6c8", "#8cd17d", "#f1ce63", "#a0cbe8", "#ffbe7d", "#bab0ac"];
const swatch = (c, kind = "fill") => `<span class="sw ${kind}" style="${kind === "text" ? `color:${c}` : `background:${c}`}" aria-hidden="true">${kind === "text" ? "Aa" : ""}</span>`;
// EPSG:3035 (ETRS89 / LAEA Europe, GRS80) from lon/lat in degrees, in km: Snyder's ellipsoidal Lambert azimuthal equal-area (matches pyproj to the mm)
const L3035 = (() => { const a = 6378137, e2 = 0.0066943800229, e = Math.sqrt(e2), r = Math.PI / 180, l0 = 10 * r, p0 = 52 * r;
  const q = (p) => { const s = Math.sin(p); return (1 - e2) * (s / (1 - e2 * s * s) - (1 / (2 * e)) * Math.log((1 - e * s) / (1 + e * s))); };
  const qp = q(Math.PI / 2), b1 = Math.asin(q(p0) / qp), Rq = a * Math.sqrt(qp / 2), D = (a * (Math.cos(p0) / Math.sqrt(1 - e2 * Math.sin(p0) ** 2))) / (Rq * Math.cos(b1));
  return (lon, lat) => { const l = lon * r - l0, b = Math.asin(q(lat * r) / qp), B = Rq * Math.sqrt(2 / (1 + Math.sin(b1) * Math.sin(b) + Math.cos(b1) * Math.cos(b) * Math.cos(l)));
    return [(4321000 + B * D * Math.cos(b) * Math.sin(l)) / 1000, (3210000 + (B / D) * (Math.cos(b1) * Math.sin(b) - Math.sin(b1) * Math.cos(b) * Math.cos(l))) / 1000]; }; })();
// point at a layer in a list (an element with data-hl) to pick out its traces in a 3D plot (traces with meta.hl): it comes forward, a surface takes
// the layer's colour, lines get wider, everything else that has a layer fades. Leaving the list restores the drawing.
function hoverLayers(list, plotEl, colourOf) {
  let on = null;
  const set = (name) => { const gd = plotEl(); if (!gd?.data?.length) return; const d = gd.data;
    if (name == null) { const o = gd._hl0; gd._hl0 = null; if (!o) return; const sf = o.filter((x) => d[x.i]?.type === "surface"), ln = o.filter((x) => d[x.i] && d[x.i].type !== "surface");
      if (o.length) Plotly.restyle(gd, { opacity: o.map((x) => x.op) }, o.map((x) => x.i)); if (sf.length) Plotly.restyle(gd, { colorscale: sf.map((x) => x.cs) }, sf.map((x) => x.i)); if (ln.length) Plotly.restyle(gd, { "line.width": ln.map((x) => x.lw) }, ln.map((x) => x.i)); return; }
    if (!gd._hl0) gd._hl0 = d.map((t, i) => (t.meta?.hl != null ? { i, op: t.opacity ?? 1, cs: t.colorscale, lw: t.line?.width ?? 2 } : null)).filter(Boolean);
    const o = gd._hl0, hit = (x) => d[x.i].meta.hl === name, c = colourOf?.(name), sf = o.filter((x) => d[x.i].type === "surface"), ln = o.filter((x) => d[x.i].type !== "surface" && d[x.i].mode !== "text");
    if (!o.some(hit)) return;
    Plotly.restyle(gd, { opacity: o.map((x) => (hit(x) ? Math.max(0.9, x.op) : Math.min(x.op, 0.12))) }, o.map((x) => x.i));
    if (sf.length && c) Plotly.restyle(gd, { colorscale: sf.map((x) => (hit(x) ? [[0, c], [1, c]] : x.cs)) }, sf.map((x) => x.i));
    if (ln.length) Plotly.restyle(gd, { "line.width": ln.map((x) => (hit(x) ? x.lw * 2.5 : x.lw)) }, ln.map((x) => x.i)); };
  list.addEventListener("mouseover", (e) => { const n = e.target.closest("[data-hl]")?.dataset.hl ?? null; if (n !== on) { on = n; set(n); } });
  list.addEventListener("mouseleave", () => { on = null; set(null); });
}
// CO2 capacity of a region (P10.4): per unit P10 / P50 / P90, and the Sodir atlas aquifers beside our numbers for the same units
const capTable = (K) => `<p><b>CO2 storage capacity</b>, ${K.realisations} correlated realisations, efficiency ${K.efficiency.p10 * 100}–${K.efficiency.p90 * 100} % (P10–P90, ${esc(K.efficiency.source)}): region total ${K.total_mt.p10.toLocaleString()} / <b>${K.total_mt.p50.toLocaleString()}</b> / ${K.total_mt.p90.toLocaleString()} Mt (P10 / P50 / P90).</p>
  <table style="font-size:12px"><tr><th>unit<th class=r>P10<th class=r>P50<th class=r>P90 Mt<th class=r>pore/bulk</tr>${K.units.slice(0, 8).map((u) => `<tr><td>${esc(u.unit)}<td class=r>${Math.round(u.p10_mt)}<td class=r><b>${Math.round(u.p50_mt)}</b><td class=r>${Math.round(u.p90_mt)}<td class=r>${u.pore_over_bulk.toFixed(2)}</tr>`).join("")}</table>
  ${K.atlas?.length ? `<p class="tip">Against the Sodir CO2 Storage Atlas (2011): ${K.atlas.map((a) => `${esc(a.aquifer)}: atlas ${a.atlas_capacity_gt} Gt, ours ${a.our_capacity_at_atlas_E_gt} Gt at the atlas efficiency (P50 ${a.our_capacity_p50_gt} Gt with ours); pore/bulk ${a.atlas_pore_over_bulk ?? "–"} vs ${a.our_pore_over_bulk}; density ${a.atlas_density_t_rm3} vs ${a.our_density_t_rm3} t/m³`).join("; ")}. ${esc(K.caveat)}.</p>` : ""}`;
// ---- the seismic inspector, one module since the 3D views were merged (P10): a side pane with a 2D section or time slice and a 3D cube or
// full block. ctx: SV (surveys), LN (line cache), sv (the selected survey: id, axis, pos, v, gain, base), later (redraw the main view).
function seismicKit(ctx) {
  const { SV, LN, later } = ctx, st = { get sv() { return ctx.sv; } };
  // ---- seismic inspector: a side pane with a 2D view (section or time slice) and a 3D cube view. It shares the survey, the line and the baseline with the big scene.
  const IN = { el: null, mode: "inline", il: null, xl: null, t: 1000, gain: 1, cmap: "seis", depth: false, clear: false, enrich: false, lay: "only2d", detail: 350000, sid: "", cache: new Map(), wells: [], seq: 0 };
  const WELLC = "#00b84a";  // wells: a saturated green, away from the blue-white-red and grey seismic colours
  const CM = { seis: [[0, "#2c5aa0"], [0.5, "#f7f7f7"], [1, "#b2182b"]], gray: [[0, "#000000"], [1, "#ffffff"]] };
  // see-through: near-zero amplitudes (the white or mid-grey of the colour scale) become transparent, so only reflections remain
  const CLEAR = { seis: [[0, "rgba(44,90,160,1)"], [0.4, "rgba(120,150,200,0.6)"], [0.5, "rgba(247,247,247,0)"], [0.6, "rgba(210,120,120,0.6)"], [1, "rgba(178,24,43,1)"]],
    gray: [[0, "rgba(0,0,0,1)"], [0.4, "rgba(90,90,90,0.6)"], [0.5, "rgba(128,128,128,0)"], [0.6, "rgba(170,170,170,0.6)"], [1, "rgba(255,255,255,1)"]] };
  const OPQ = [[0, 1], [0.38, 0.55], [0.5, 0], [0.62, 0.55], [1, 1]];
  const cmap = () => (IN.clear ? CLEAR : CM)[IN.cmap];
  const icache = (k, f) => (IN.cache.has(k) ? Promise.resolve(IN.cache.get(k)) : f().then((v) => (IN.cache.set(k, v), v)));
  const Yv = (t) => (IN.depth ? (t / 2) * st.sv.v : t), Ylab = () => (IN.depth ? "Depth preview (m, uncalibrated)" : "Survey two-way time (ms)");
  const inspectLater = (() => { let t; return () => { clearTimeout(t); t = setTimeout(inspectDraw, 90); }; })();
  const nearIdx = (arr, v) => arr.reduce((b, x, i) => (Math.abs(x - v) < Math.abs(arr[b] - v) ? i : b), 0);
  function inspectSetup(m) { const L = LN[m.id], set = (id, max, val) => { const e = $(id); e.min = 0; e.max = max; e.value = val; };
    set("#si-il", L.inline.length - 1, nearIdx(L.inline, IN.il)); set("#si-xl", L.crossline.length - 1, nearIdx(L.crossline, IN.xl)); const t = $("#si-t"); t.min = m.t0_ms; t.max = m.t_end_ms; t.step = m.dt_ms; t.value = IN.t; }
  async function inspectDraw() {
    const sv = st.sv, my = ++IN.seq, m = SV.find((x) => x.id === sv.id); if (!m || !IN.el) return;
    if (IN.sid !== sv.id) { IN.sid = sv.id; IN.cam = IN.blockCam = null; if (!LN[sv.id]) LN[sv.id] = await api("seismic/lines", { survey: sv.id }); const L = LN[sv.id]; IN.il = L.inline[L.inline.length >> 1]; IN.xl = L.crossline[L.crossline.length >> 1]; IN.t = Math.round((m.t0_ms + m.t_end_ms) / 2); IN.wells = await api("seismic/wells", { survey: sv.id }); inspectSetup(m); }
    if (!IN.el) return;
    const L = LN[sv.id], b = sv.base || "", k = (...a) => [sv.id, b, ...a].join("|"), q = (o) => ({ survey: sv.id, ...(b ? { baseline: b } : {}), ...o });
    const en = IN.enrich ? await Promise.all([icache(k("ei", IN.il, sv.v), () => api("seismic/enrich", { survey: sv.id, axis: "inline", index: IN.il, v: sv.v })), icache(k("ex", IN.xl, sv.v), () => api("seismic/enrich", { survey: sv.id, axis: "crossline", index: IN.xl, v: sv.v }))]) : null;
    const [inl, xln, tsl] = await Promise.all([icache(k("i", IN.il), () => api("seismic/curtain", q({ axis: "inline", index: IN.il, tstep: 1 }))), icache(k("x", IN.xl), () => api("seismic/curtain", q({ axis: "crossline", index: IN.xl, tstep: 1 }))), icache(k("t", IN.t), () => api("seismic/slice", q({ t_ms: IN.t })))]);
    if (my !== IN.seq || !IN.el) return;
    const p99 = m.amp_p99, real = (v) => (v == null ? null : (v / 127) * p99), zm = p99 / IN.gain, cs = cmap(), cs3 = CM[IN.cmap], see = IN.clear ? { opacityscale: OPQ } : {}, stepI = Math.abs(L.inline[1] - L.inline[0]) || 1, stepX = Math.abs(L.crossline[1] - L.crossline[0]) || 1;
    $("#si-ilv").textContent = IN.il; $("#si-xlv").textContent = IN.xl; $("#si-tv").textContent = Math.round(tsl.t_ms) + " ms"; $("#si-gv").textContent = IN.gain.toFixed(1) + "×";
    $("#si-title").textContent = `${m.name}: ` + ({ inline: `inline ${IN.il}`, crossline: `crossline ${IN.xl}`, time: `time slice at ${Math.round(tsl.t_ms)} ms` }[IN.mode]); $("#si-mode-lab").textContent = { inline: `Inline section ${IN.il}`, crossline: `Crossline section ${IN.xl}`, time: `Time slice at ${Math.round(tsl.t_ms)} ms` }[IN.mode];
    // ---- 2D view
    let t2, lay2; const wl = [];
    if (IN.mode === "time") {
      t2 = [{ type: "heatmap", x: tsl.xl, y: tsl.il, z: tsl.amp.map((r) => r.map(real)), colorscale: cs, zmin: -zm, zmax: zm, colorbar: { thickness: 8, len: 0.8 }, hovertemplate: "Inline %{y}<br>Crossline %{x}<br>Amplitude %{z:.0f}<extra></extra>" }];
      IN.wells.forEach((w) => wl.push({ type: "scatter", mode: "markers+text", x: [w.xl], y: [w.il], text: [w.name], textposition: "top center", marker: { symbol: "x", size: 12, color: WELLC, line: { width: 2 } }, textfont: { color: WELLC }, hovertemplate: `Well ${esc(w.name)}<br>${w.dist_m} m from the nearest trace<extra></extra>`, showlegend: false }));
      lay2 = { xaxis: { title: "Crossline number" }, yaxis: { title: "Inline number" } };
    } else {
      const cu = IN.mode === "inline" ? inl : xln, xs = IN.mode === "inline" ? cu.xl : cu.il, ys = cu.t_ms.map(Yv), lab = IN.mode === "inline" ? [`Inline ${cu.index}`, "Crossline"] : [`Crossline ${cu.index}`, "Inline"];
      t2 = [{ type: "heatmap", x: xs, y: ys, z: cu.amp.map((r) => r.map(real)), colorscale: cs, zmin: -zm, zmax: zm, colorbar: { thickness: 8, len: 0.8 }, hovertemplate: `${lab[0]}<br>${lab[1]} %{x}<br>${IN.depth ? "Depth %{y:.0f} m" : "Time %{y:.0f} ms"}<br>Amplitude %{z:.0f}<extra></extra>` }];
      IN.wells.filter((w) => (IN.mode === "inline" ? Math.abs(w.il - IN.il) <= stepI * 1.5 : Math.abs(w.xl - IN.xl) <= stepX * 1.5)).forEach((w) => { const x = IN.mode === "inline" ? w.xl : w.il; wl.push({ type: "scatter", mode: "lines+text", x: [x, x], y: [ys[0], ys.at(-1)], text: [w.name, ""], textposition: "bottom right", line: { color: WELLC, width: 3 }, textfont: { color: WELLC, size: 12 }, hovertemplate: `Well ${esc(w.name)}<br>${w.dist_m} m from the nearest trace<extra></extra>`, showlegend: false }); });
      lay2 = { xaxis: { title: IN.mode === "inline" ? "Crossline number (west to east)" : "Inline number" }, yaxis: { title: Ylab(), autorange: "reversed" } };
    }
    const HC = ["#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#a6761d", "#666666"];
    if (en && IN.mode !== "time") {
      const E = IN.mode === "inline" ? en[0] : en[1], step = IN.mode === "inline" ? stepX : stepI, wide = step * 6;
      E.horizons.forEach((h, i) => wl.push({ type: "scatter", mode: "lines", x: h.along, y: h.twt.map((t) => (t == null ? null : Yv(t))), line: { color: HC[i % HC.length], width: 2 }, connectgaps: false, name: h.name.replace(" GP", " Gp").replace(" FM", " Fm"), hovertemplate: `${esc(h.name)} (interpreted horizon)<br>${IN.depth ? "%{y:.0f} m" : "%{y:.0f} ms"}<extra></extra>`, showlegend: true }));
      E.wells.filter((w) => (IN.mode === "inline" ? Math.abs(w.il - IN.il) <= stepI * 1.5 : Math.abs(w.xl - IN.xl) <= stepX * 1.5)).forEach((w) => { const x0 = IN.mode === "inline" ? w.xl : w.il;
        if (w.gr) wl.push({ type: "scatter", mode: "lines", x: w.gr.v.map((g) => x0 + (Math.min(Math.max(g, 0), 150) / 150) * wide), y: w.gr.twt.map(Yv), line: { color: "#7a3ff2", width: 1.4 }, customdata: w.gr.v.map((g, i) => [g, w.gr.tvdss[i]]), hovertemplate: `${esc(w.name)} gamma ray %{customdata[0]:.0f} gAPI<br>%{customdata[1]:.0f} m below sea level<br>${esc(w.log_source)}<extra></extra>`, showlegend: false });
        const tp = (w.tops || []).filter((t) => t.level === "GROUP" || t.level === "FORMATION");
        if (tp.length) wl.push({ type: "scatter", mode: "markers+text", x: tp.map(() => x0), y: tp.map((t) => Yv(t.twt)), text: tp.map((t) => (t.level === "GROUP" ? t.name.replace(" GP", "") : "")), textposition: "middle left", textfont: { size: 9, color: css("--ink") }, marker: { symbol: "line-ew-open", size: 14, color: css("--ink"), line: { width: 2 } }, customdata: tp.map((t) => [t.name, t.md, t.tvdss]), hovertemplate: `${esc(w.name)}: top %{customdata[0]}<br>MD %{customdata[1]:.0f} m, %{customdata[2]:.0f} m below sea level<extra>Sodir formation top</extra>`, showlegend: false }); });
    }
    const g2 = $("#si2d"); if (!g2 || !IN.el) return; if (g2.offsetWidth) await plot(g2, [...t2, ...wl], { ...lay2, margin: { l: 54, r: 10, t: 6, b: 40 }, uirevision: IN.mode + sv.id, showlegend: !!en, legend: { orientation: "h", y: -0.12, font: { size: 10 } } });
    g2.removeAllListeners?.("plotly_hover"); g2.on && g2.on("plotly_hover", (e) => { const pt = e.points?.[0]; if (!pt || pt.data.type !== "heatmap") return; let la = "", pos = "";
      if (IN.mode === "time") { const i = tsl.il.indexOf(pt.y), j = tsl.xl.indexOf(pt.x); pos = `inline ${pt.y}, crossline ${pt.x}, ${Math.round(tsl.t_ms)} ms`; } else { const cu = IN.mode === "inline" ? inl : xln, i = nearIdx(IN.mode === "inline" ? cu.xl : cu.il, pt.x); la = ` · ${cu.lat[i]}° N, ${cu.lon[i]}° E · ${cu.dist_km[i]} km along the line`; pos = `${IN.mode === "inline" ? "inline " + cu.index + ", crossline " + pt.x : "crossline " + cu.index + ", inline " + pt.x}, ${IN.depth ? Math.round(pt.y) + " m" : Math.round(pt.y) + " ms"}`; }
      $("#sihov").innerHTML = `<b>${pos}</b> · amplitude <b>${Math.round(pt.z)}</b> (${(pt.z / p99).toFixed(2)} of the 99th percentile, ${p99.toFixed(0)})${la}`; });
    // ---- 3D cube view: the two sections and the time slice through a transparent box, with our wells
    const tmin = m.t0_ms, tmax = m.t_end_ms, zt = -Yv(tmin), zb = -Yv(tmax), pl = [];
    [["inline", inl], ["crossline", xln]].forEach(([nm, cu]) => pl.push({ type: "surface", x: cu.t_ms.map(() => cu.x), y: cu.t_ms.map(() => cu.y), z: cu.t_ms.map((t) => cu.x.map(() => -Yv(t))), surfacecolor: cu.amp.map((r) => r.map(real)), cmin: -zm, cmax: zm, colorscale: cs3, ...see, showscale: false, opacity: IN.clear || IN.mode === nm ? 1 : 0.72, name: nm, lighting: { ambient: 1, diffuse: 0 }, hovertemplate: `${nm} ${cu.index}<br>${IN.depth ? "depth" : "time"} %{z:.0f}<br>amplitude %{surfacecolor:.0f}<extra></extra>` }));
    const tz = -Yv(tsl.t_ms); pl.push({ type: "surface", x: tsl.x, y: tsl.y, z: tsl.x.map((r) => r.map((v) => (v == null ? null : tz))), surfacecolor: tsl.amp.map((r) => r.map(real)), cmin: -zm, cmax: zm, colorscale: cs3, ...see, showscale: false, opacity: IN.clear || IN.mode === "time" ? 1 : 0.72, name: "time slice", lighting: { ambient: 1, diffuse: 0 }, hovertemplate: `time slice ${Math.round(tsl.t_ms)} ms<br>amplitude %{surfacecolor:.0f}<extra></extra>` });
    const ring = [...m.footprint, m.footprint[0]].map((p) => [KMX(p[1]), KMY(p[0])]), ox = [], oy = [], oz = [];
    [zt, zb].forEach((z) => ring.forEach(([x, y]) => { ox.push(x); oy.push(y); oz.push(z); })); ox.push(null); oy.push(null); oz.push(null); ring.slice(0, -1).forEach(([x, y]) => { ox.push(x, x, null); oy.push(y, y, null); oz.push(zt, zb, null); });
    pl.push({ type: "scatter3d", mode: "lines", x: ox, y: oy, z: oz, line: { color: css("--ink"), width: 2 }, hoverinfo: "skip", name: "survey box", showlegend: false });
    if (en) {
      [[en[0], inl, "xl"], [en[1], xln, "il"]].forEach(([E, cu, key]) => E.horizons.forEach((h, i) => { const pos = new Map(cu[key].map((v, j) => [v, j]));
        const hx = [], hy = [], hz = []; h.along.forEach((a, j) => { const q = pos.get(a); if (q == null || h.twt[j] == null) { hx.push(null); hy.push(null); hz.push(null); } else { hx.push(cu.x[q]); hy.push(cu.y[q]); hz.push(-Yv(h.twt[j])); } });
        pl.push({ type: "scatter3d", mode: "lines", x: hx, y: hy, z: hz, line: { color: HC[i % HC.length], width: 5 }, name: h.name, hovertemplate: `${esc(h.name)}<extra>interpreted horizon</extra>`, showlegend: false }); }));
      en[0].wells.filter((w) => w.gr).forEach((w) => pl.push({ type: "scatter3d", mode: "lines", x: w.gr.twt.map(() => w.x), y: w.gr.twt.map(() => w.y), z: w.gr.twt.map((t) => -Yv(t)), line: { width: 10, color: w.gr.v, cmin: 0, cmax: 150, colorscale: [[0, "#f2d74e"], [0.5, "#8c9a4b"], [1, "#5b3a1a"]] }, customdata: w.gr.v, hovertemplate: `${esc(w.name)} gamma ray %{customdata:.0f} gAPI<extra>${esc(w.log_source)}</extra>`, showlegend: false }));
    }
    IN.wells.forEach((w) => pl.push({ type: "scatter3d", mode: "lines+text", x: [w.x, w.x], y: [w.y, w.y], z: [zt, zb], text: [w.name, ""], textposition: "top center", line: { color: WELLC, width: 9 }, textfont: { color: WELLC, size: 13 }, hovertemplate: `Well ${esc(w.name)}<extra></extra>`, showlegend: false }));
    const xs3 = ring.map((r) => r[0]), ys3 = ring.map((r) => r[1]), dx = Math.max(...xs3) - Math.min(...xs3) || 1, dy = Math.max(...ys3) - Math.min(...ys3) || 1, step = (IN.depth ? 1000 : 1000), ticks = Array.from({ length: Math.floor(Yv(tmax) / step) + 1 }, (_, i) => i * step);
    const ax = (t) => ({ title: t, gridcolor: css("--rule"), color: css("--mut"), showbackground: false });
    if (IN.lay === "block") { await blockDraw(m, en); return; }
    // keep the cube's camera across redraws (slider moves, gain, enrich): read it back from the live scene, as in the big scene
    let cam3 = null; if ($("#si3d")?.data?.[0]?.type === "surface") try { cam3 = $("#si3d")._fullLayout.scene._scene.getCamera(); } catch {}
    if (cam3) IN.cam = cam3;
    const g3 = $("#si3d"); if (!g3 || !IN.el) return; if (g3.offsetWidth) await plot3(g3, pl, { margin: { l: 0, r: 0, t: 0, b: 0 }, uirevision: sv.id + IN.depth, showlegend: false, scene: { aspectmode: "manual", aspectratio: { x: 1, y: Math.max(dy / dx, 0.2), z: 0.55 }, camera: IN.cam || { eye: { x: 1.5, y: -1.6, z: 0.9 } }, xaxis: ax("East (km)"), yaxis: ax("North (km)"), zaxis: { ...ax(Ylab()), tickvals: ticks.map((v) => -v), ticktext: ticks.map(String) } } });
    const enInfo = en ? `<tr><td>Enriched<td>${en[0].horizon_source ? esc(en[0].horizon_source) + " (coloured lines); " : "no interpreted horizons for this survey; "}gamma ray: ${en[0].wells.filter((w) => w.gr).map((w) => esc(w.name) + " (" + esc(w.log_source) + ")").join(", ") || "none"}; formation tops: Sodir. Depth to time: ${esc((en[0].time_model || []).join("; "))}. Purple wiggle: gamma ray (left = low, sand-like; right = high, shale-like).` : "";
    $("#siinfo").innerHTML = `<table style="font-size:12px">${enInfo}<tr><td>Survey<td><b>${esc(m.name)}</b>${m.survey_year ? ` (surveyed ${m.survey_year}, processed ${"20" + m.processing})` : ""}<tr><td>Traces<td>${m.traces_total.toLocaleString()} in the survey, every ${m.decimation}th inline and crossline shown (${m.traces_kept.toLocaleString()})<tr><td>Sampling<td>${m.dt_ms} ms, ${Math.round(m.t0_ms)} to ${Math.round(m.t_end_ms)} ms two-way time<tr><td>Lines<td>inline ${m.inline[0]}–${m.inline[1]}, crossline ${m.crossline[0]}–${m.crossline[1]}${m.bin_m ? `, trace spacing about ${Math.round(m.bin_m)} m` : ""}<tr><td>Amplitude<td>99th percentile ${p99.toFixed(0)}; colours span ±${zm.toFixed(0)}${sv.base ? "; <b>difference</b> against " + esc(sv.base) : ""}<tr><td>Our wells<td>${IN.wells.length ? IN.wells.map((w) => esc(w.name) + " (" + w.dist_m + " m from a trace)").join(", ") : "none inside this survey"}<tr><td>Credit<td>${esc(m.credit)}</table>`;
  }
  // ---- the whole survey as one transparent volume (inline x crossline x time grid): strong reflections opaque, quiet zones see-through,
  // so interpreted horizons, wells and gamma ray inside stay visible. Thinned on the server to about 350,000 values.
  async function blockDraw(m, en) {
    const sv = st.sv, c = await icache(["cube", sv.id, IN.detail].join("|"), () => api("seismic/cube", { survey: sv.id, max_points: IN.detail })); const g = $("#si3d"); if (!g || !IN.el || !g.offsetWidth) return;
    const ni = c.il.length, nj = c.xl.length, nk = c.t_ms.length, X = [], Y = [], Z = [], V = [];
    for (let i = 0; i < ni; i++) for (let j = 0; j < nj; j++) for (let k = 0; k < nk; k++) { X.push(c.xl[j]); Y.push(c.il[i]); Z.push(-Yv(c.t_ms[k])); V.push(c.amp[(i * nj + j) * nk + k]); }
    const lim = 127 / IN.gain, cs3 = CM[IN.cmap], HC = ["#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02", "#a6761d", "#666666"];
    const pl = [{ type: "volume", x: X, y: Y, z: Z, value: V, isomin: -lim, isomax: lim, cmin: -lim, cmax: lim, colorscale: cs3, opacity: 0.25, surface: { count: 14 }, caps: { x: { show: false }, y: { show: false }, z: { show: false } },
      opacityscale: [[0, 1], [0.3, 0.5], [0.45, 0], [0.55, 0], [0.7, 0.5], [1, 1]], showscale: false, hovertemplate: "inline %{y}, crossline %{x}<br>%{z:.0f}<extra>amplitude</extra>" }];
    c.horizons.forEach((h, i) => pl.push({ type: "surface", x: c.xl, y: c.il, z: h.twt.map((r) => r.map((t) => (t == null ? null : -Yv(t)))), surfacecolor: h.twt.map((r) => r.map(() => 1)), colorscale: [[0, HC[i % HC.length]], [1, HC[i % HC.length]]], showscale: false, opacity: 0.55, name: h.name, hovertemplate: `${esc(h.name)}<br>inline %{y}, crossline %{x}<extra>interpreted horizon</extra>`, lighting: { ambient: 0.8, diffuse: 0.3 } }));
    const t0 = -Yv(c.t_ms[0]), t1 = -Yv(c.t_ms.at(-1));
    IN.wells.forEach((w) => pl.push({ type: "scatter3d", mode: "lines+text", x: [w.xl, w.xl], y: [w.il, w.il], z: [t0, t1], text: [w.name, ""], textposition: "top center", line: { color: WELLC, width: 9 }, textfont: { color: WELLC, size: 13 }, hovertemplate: `Well ${esc(w.name)}<extra></extra>`, showlegend: false }));
    if (en) en[0].wells.filter((w) => w.gr).forEach((w) => pl.push({ type: "scatter3d", mode: "lines", x: w.gr.twt.map(() => w.xl), y: w.gr.twt.map(() => w.il), z: w.gr.twt.map((t) => -Yv(t)), line: { width: 14, color: w.gr.v, cmin: 0, cmax: 150, colorscale: [[0, "#f2d74e"], [0.5, "#8c9a4b"], [1, "#5b3a1a"]] }, customdata: w.gr.v, hovertemplate: `${esc(w.name)} gamma ray %{customdata:.0f} gAPI<extra></extra>`, showlegend: false }));
    if (g.data?.[0]?.type === "volume") try { IN.blockCam = g._fullLayout.scene._scene.getCamera(); } catch {}  // only a block scene's camera is a block camera
    const ax = (t) => ({ title: t, gridcolor: css("--rule"), color: css("--mut"), showbackground: false }), ticks = Array.from({ length: Math.floor(Yv(c.t_ms.at(-1)) / 1000) + 1 }, (_, i) => i * 1000);
    await plot3(g, pl, { margin: { l: 0, r: 0, t: 0, b: 0 }, uirevision: "block" + sv.id, showlegend: false, scene: { aspectmode: "manual", aspectratio: { x: 1, y: Math.max(c.along_inline_axis_km / Math.max(c.along_crossline_axis_km, 0.1), 0.15), z: 0.6 }, camera: IN.blockCam || { eye: { x: 1.6, y: -1.6, z: 0.9 } },
      xaxis: ax("Crossline"), yaxis: ax("Inline"), zaxis: { ...ax(Ylab()), tickvals: ticks.map((v) => -v), ticktext: ticks.map(String) } } });
    $("#si-title").textContent = `${m.name}: full block (every ${c.stride.inline}th kept line, ${c.stride.time * m.dt_ms} ms)`;
    $("#siinfo").innerHTML = `<table style="font-size:12px"><tr><td>Block<td>${ni} inlines × ${nj} crosslines × ${nk} samples (${V.length.toLocaleString()} values), thinned from the decimated copy. Quiet amplitudes are transparent; the gain sets which reflections stay opaque.${c.horizons.length ? "<tr><td>Horizons<td>" + c.horizons.map((h) => esc(h.name)).join(", ") + " (Smeaheia key horizons 2010)" : ""}<tr><td>Credit<td>${esc(c.credit)}</table>`;
  }
  function inspectClose() { if (IN.el) { IN.el.remove(); IN.ctl && IN.ctl.remove(); IN.stage && IN.stage.remove(); IN.el = IN.stage = null; } const b = $("#sv-inspect"); if (b) { b.textContent = "Inspect seismic ▸"; b.classList.add("on"); } REDRAW.scene?.(); }
  function inspectOpen() { if (!SV.length) return; if (!st.sv.id) { const sel = $("#sv-id"); sel.value = SV[0].id; sel.dispatchEvent(new Event("change", { bubbles: true })); }
    IN.sid = ""; IN.ctl = sec("L", "inspc", "Seismic inspector: view", `<div class="row"><b id="si-mode-lab"></b></div>
      <div class="row"><label class="chk"><input type="radio" name="si-mode" value="inline" checked> inline section</label><label class="chk"><input type="radio" name="si-mode" value="crossline"> crossline section</label><label class="chk"><input type="radio" name="si-mode" value="time"> time slice</label></div>
      <div class="row"><label class="chk" style="width:100%">inline <input type="range" id="si-il" style="flex:1"> <span id="si-ilv" class="mono"></span></label></div>
      <div class="row"><label class="chk" style="width:100%">crossline <input type="range" id="si-xl" style="flex:1"> <span id="si-xlv" class="mono"></span></label></div>
      <div class="row"><label class="chk" style="width:100%">time <input type="range" id="si-t" style="flex:1"> <span id="si-tv" class="mono"></span></label></div>
      <div class="row"><label class="chk" style="width:100%" title="Colours saturate at the 99th-percentile amplitude divided by the gain: higher gain shows weaker reflections">gain <input type="range" id="si-g" min="0.5" max="8" step="0.1" value="1" style="flex:1"> <span id="si-gv"></span></label></div>
      <div class="row"><label>Colours <select id="si-cm"><option value="seis">blue–white–red</option><option value="gray">grey</option></select></label><label class="chk" title="Make near-zero amplitudes transparent, in the inspector and in the big scene"><input type="checkbox" id="si-clear"> see-through quiet zones</label></div>
      <div class="row"><label class="chk"><input type="checkbox" id="si-d"> depth (illustrative)</label></div>
      <div class="row"><label title="Full block only: values sent to the browser; more is smoother and needs a stronger graphics card">Block detail <select id="si-det"><option value="350000">normal (350 k)</option><option value="900000">high (900 k)</option><option value="1800000">very high (1.8 M)</option></select></label></div>
      <div class="row"><label class="chk" title="Overlay what else we know: interpreted horizons (Smeaheia), gamma-ray logs and formation tops of the wells in this survey"><input type="checkbox" id="si-en"> enrich: horizons, gamma ray, formation tops</label></div>`, true);
    IN.el = sec("R", "insp", "Seismic inspector: survey", `<div id="siinfo"></div>`, true);
    IN.stage = document.createElement("div"); IN.stage.className = "istage"; IN.stage.innerHTML = `<div class="ibar"><b id="si-title"></b>
      <span class="tip">view</span>${[["only2d", "2D section"], ["only3d", "3D cube"], ["block", "full block"]].map(([k, t]) => `<button class="lnk lay ${IN.lay === k ? "on" : ""}" data-lay="${k}">${t}</button>`).join("")}<span style="flex:1"></span><button class="btn" id="si-close" title="Close the inspector and return to the 3D scene">✕ 3D scene</button></div>
      <div id="sihov" class="tip ihov">hover the section for values</div>
      <div class="igrid ${IN.lay}"><div id="si2d"></div><div id="si3d"></div></div>`;
    $(".plotwrap").appendChild(IN.stage);
    $("#si-close").onclick = () => inspectClose();
    IN.stage.querySelector(".ibar").addEventListener("click", (e) => { const k = e.target.dataset.lay; if (!k) return; IN.lay = k; $(".igrid", IN.stage).className = "igrid " + k; IN.stage.querySelectorAll(".lay").forEach((b) => b.classList.toggle("on", b.dataset.lay === k)); try { const g = $("#si3d"); if (g.data?.[0]?.type === "surface") IN.cam = g._fullLayout.scene._scene.getCamera(); if (g.data?.[0]?.type === "volume") IN.blockCam = g._fullLayout.scene._scene.getCamera(); Plotly.purge(g); } catch {} inspectLater(); });
    const b = $("#sv-inspect"); b.textContent = "Close inspector ◂"; b.classList.remove("on");
    const body = $(".secb", IN.ctl), sync = () => { const sv = st.sv, L = LN[sv.id]; if (!L) return; sv.axis = IN.mode === "crossline" ? "crossline" : "inline"; const arr = L[sv.axis], v = sv.axis === "inline" ? IN.il : IN.xl; sv.pos = arr.length > 1 ? nearIdx(arr, v) / (arr.length - 1) : 0.5; sv.ck = ""; $$("[name='sv-ax']").forEach((r) => (r.checked = r.value === sv.axis)); later(); };
    body.oninput = (e) => { const t = e.target, L = LN[st.sv.id]; if (!L) return; if (t.id === "si-il") IN.il = L.inline[+t.value]; else if (t.id === "si-xl") IN.xl = L.crossline[+t.value]; else if (t.id === "si-t") IN.t = +t.value; else if (t.id === "si-g") IN.gain = +t.value; else return; if (t.id === "si-il" || t.id === "si-xl") sync(); inspectLater(); };
    body.onchange = (e) => { const t = e.target; if (t.name === "si-mode") { IN.mode = t.value; if (t.value !== "time") sync(); inspectLater(); } else if (t.id === "si-cm") { IN.cmap = t.value; inspectLater(); } else if (t.id === "si-d") { IN.depth = t.checked; inspectLater(); } else if (t.id === "si-clear") { IN.clear = t.checked; inspectLater(); later(); } else if (t.id === "si-en") { IN.enrich = t.checked; inspectLater(); } else if (t.id === "si-det") { IN.detail = +t.value; inspectLater(); } };
    new ResizeObserver(() => { try { Plotly.Plots.resize($("#si2d")); } catch {} inspectLater(); }).observe(IN.stage);
    inspectLater(); }
  if ($("#sv-inspect")) { $("#sv-inspect").onclick = () => (IN.el ? inspectClose() : inspectOpen()); ["#sv-id", "#sv-base"].forEach((id) => $(id).addEventListener("change", () => IN.el && inspectLater())); $("#sv-v").addEventListener("input", () => IN.el && IN.depth && inspectLater()); }
  return { IN, OPQ, inspectOpen, inspectClose, inspectLater };
}
const RPTC = { brine: "#1f77b4", oil: "#2ca02c", gas: "#d62728" };  // rock physics template fluid lines
const PAGES = {
  screen: mountSmeaheia,
  tracks: mountTracks,
  // ---- Nature's Plug (Jeham) inside the model (PLAN P13, LOG L090): his Green Clay relation on our surfaces, tested at his report sites;
  // his formation-level and nearest-well verdicts by region; his barrier cases. A comparison and a screen, not a barrier verification.
  async jeham() {
    const J = await api("earth/jeham"), g = J.green_clay_test, RN = { pilot: "Northern North Sea (Horda)", north_sea_south: "Southern North Sea", norwegian_sea: "Norwegian Sea", barents: "Barents Sea" };
    doc(`<h1>Nature's Plug in the model</h1><p class="lead">Jeham's open screen for where overburden clay could seal a well (<a href="https://github.com/jeham3408/natures-plug/tree/3df7c523f9469756aeb8910c2be01456ddda7df8" target="_blank" rel="noopener">natures-plug</a>, MIT, commit 3df7c52), run unchanged and joined to our earth model. It ranks where to look; it does not verify a barrier.</p>
      <h2>A. Green Clay as a surface of our model</h2>
      <p>His relation, ${esc(J.relation)}, applied to our kriged Hordaland and Rogaland tops in every shelf column. At his ${g.sites} report sites (wells whose reports give a TVD for the Green Clay top): our surface misses by <b>${g.mean_abs_miss_ours_m} m</b> on average, his own prediction by <b>${g.mean_abs_miss_his_m} m</b> (his held-out figure, leaving a field out: ${g.his_field_held_out_m} m). Ours is ${Math.abs(g.median_signed_miss_ours_m)} m shallower in the median; about 25–30 m of that is datum (report depths below the rig floor, ours below sea level).</p>
      <p class="tip">Not a held-out test: his coefficients were fitted on these sites, and our surfaces include the sites' own group tops.</p>
      <table style="font-size:13px"><tr><th>field<th class=r>report top (m TVD)<th class=r>his prediction (m)<th class=r>ours (m TVDSS)<th class=r>our miss (m)<th>source</tr>
      ${J.green_clay_sites.map((s) => `<tr><td>${esc(s.field)}<td class=r>${s.report_tvd_m}<td class=r>${s.his_pred_m ?? "–"}<td class=r>${s.our_top_tvdss_m ?? "–"}<td class=r>${s.our_err_m ?? "–"}<td class="tip">${esc(s.file || "")}${s.page ? `, p. ${s.page}` : ""}</tr>`).join("")}</table>
      <h2>B and D. His verdicts by region</h2>
      <p class="tip">Formation level: an exploration well has at least 50 m of Hordaland or Rogaland inside the leak-off pressure window (present), less (thin), none (absent), or cannot be tested. Nearest-well: a wellbore left to plug takes the log verdict of the nearest assessed log well within 10 km. Our Smeaheia screen does not do this; it is shown as his result.</p>
      <table style="font-size:13px"><tr><th>region<th class=r>Green Clay columns<th class=r>median top (m TVDSS)<th class=r>median thickness (m)<th class=r>exploration wells: present / thin / absent / untested<th class=r>left to plug: pass / fail / no well within 10 km</tr>
      ${Object.entries(J.regions).map(([r, R]) => `<tr><td>${esc(RN[r] || r)}<td class=r>${R.green_clay?.columns?.toLocaleString() ?? "–"}<td class=r>${R.green_clay?.top_median_m ?? "–"}<td class=r>${R.green_clay?.thickness_median_m ?? "–"}<td class=r>${R.formation_level.present} / ${R.formation_level.thin} / ${R.formation_level.absent} / ${R.formation_level.none}<td class=r>${R.inheritance.log_pass} / ${R.inheritance.log_fail} / ${R.inheritance.log_none}</tr>`).join("")}</table>
      <p class="tip">Shelf totals from his engine: ${J.engine_totals.left.toLocaleString()} wellbores left to plug; ${J.engine_totals.log[2]} pass, ${J.engine_totals.log[1]} fail, ${J.engine_totals.log[0]} with no assessed log well within 10 km. ${J.engine_totals.controls.assessed} of ${J.engine_totals.controls.all} log wells assessable, ${J.engine_totals.controls.pass} pass. Log level against formation level: ${J.agree.passPresent} of ${J.agree.passPresent + J.agree.passOther} passes are also "present".</p>
      <h2>C. Reported clay barriers (his 15 hand-read cases)</h2>
      <table style="font-size:13px"><tr><th>well<th>area<th>unit<th>outcome<th>what the report says<th class=r>our Green Clay top (m TVDSS)<th>source</tr>
      ${J.barrier_cases.map((c) => `<tr><td>${esc(c.well)}<td>${esc(c.area || "")}<td>${esc(c.unit || "")}<td>${esc(c.outcome || "")}<td>${esc(c.summary || c.how || "")}<td class=r>${c.our_green_clay_top_tvdss_m ?? "–"}<td class="tip">${esc(c.src?.file || "")}${c.src?.page ? `, p. ${c.src.page}` : ""}</tr>`).join("")}</table>
      <p class="tip">Credit: Nature's Plug by Jeham (MIT). Our use: LOG L090.</p>`);
  },

  async research() {
    doc(`<h1>Research workspace</h1><p class="lead">Preserved models and experiments. These are not inputs to the Smeaheia well review.</p>
      <h2>Regional models</h2><p><a href="#earth">3D Earth model &amp; seismic inspector</a> · <a href="#rpt">Rock physics</a> · <a href="#sensitivity">Sensitivity</a> · <a href="#jeham">Nature's Plug in the model</a></p>
      <h2>Reported targets</h2><p><a href="#targets">Target builder</a> · <a href="#scene">Saved 3D targets</a> · <a href="#units">Well intervals</a> · <a href="#validation">Validation</a></p>
      <h2>Sources &amp; methods</h2><p><a href="#data">Data catalog</a> · <a href="#lineage">Lineage</a> · <a href="#architecture">Architecture</a> · <a href="#workflows">Other Studio tools</a></p>
      <p class="tip">The historical CO₂ storage and chance-of-success scores are uncalibrated. Regional model selection reused the retrospective time split. Neither validates a barrier or leak prediction.</p>`);
  },
  async start(_, live) {
    const d = META.data, fs = (await api("formations")).filter((f) => f.units >= 20).slice(0, 14), w = W();
    if (!live()) return;
    doc(`<h1>${esc(META.title)}</h1><p class="lead">${esc(META.target_text)}. Each ${esc(w.unit)} gets an estimate, the evidence behind it, and a test on wells the model never saw.</p>
    <div class="grid g4"><div><div class="num">${d.labelled.toLocaleString()}</div><div class="cap">units used (${w.unit})</div></div><div><div class="num">${d.wellbores_labelled.toLocaleString()}</div><div class="cap">wells</div></div><div><div class="num">${d.rows.toLocaleString()}</div><div class="cap">${esc(w.rows)}</div></div><div><div class="num">${pct(d.base_rate)}</div><div class="cap">${esc(w.hit)}</div></div></div>
    <h2>How to read the numbers</h2><p>The <b>rate</b> is the share of ${esc(w.rows)} that ${esc(w.hit)}. It is what the records say, not a direct measurement of the ground. Evidence <b>layers</b> each add or subtract from the starting rate: the formation or group, nearby wells, well logs, later seismic. Hover a layer's status for the test behind it.</p>
    ${note("Status of the evidence", `<p>${LAYERS.map((l) => `${esc(l.title)}: ${tag(l.status, STATUS_WORDS[l.status], evTip(l))}`).join(" · ")}</p>`, "Skill is small. Use estimates as leads to check, not as facts. See <a href='#validation'>Validation</a> for the full test.")}
    <h2>Where to go</h2><table><tr><td><a href="#earth">Subsurface model</a><td>the 3D model of the shelf: strata, target probabilities with their evidence, wells at vertical depth, what each well found, seismic, map layers; <b>Saved targets</b> shows the Target builder's sheets and sticks<tr><td><a href="#units">Units</a><td>every row, with the evidence behind each estimate<tr><td><a href="#data">Data</a><td>what we hold, where it comes from, and every database table<tr><td><a href="#targets">Targets</a><td>build a new question from any table (e.g. discovery, DST flow, mud weight)<tr><td><a href="#layers">Layers</a>, <a href="#knowledge">Knowledge</a>, <a href="#validation">Validation</a><td>why the estimates can be trusted, or not</table>
    <h2>Terms</h2><table><tr><td><b>Formation</b><td>A named layer of rock that geologists can recognise across a region, defined by its rock type and its place in the stack. Example: the Sele Formation is a dark, layered shale found over much of the North Sea. The same formation is met at different depths in different wells (deeper in basins, shallower on highs).
    <tr><td><b>Group</b><td>A set of related formations. The Hordaland Group contains many formations. Where a report only names the group, the group is used.
    <tr><td><b>Formation top</b><td>The depth where a well first enters a formation; the bottom is where it leaves it. Names and depths come from the Sodir register.
    <tr><td><b>Well / wellbore</b><td>One drilled hole (e.g. 30/6-21; 30/6-21 A is a sidetrack of it).
    <tr><td><b>Unit</b><td>One well passing through one formation (or, for well-level targets, one well). The row everything is scored on.
    <tr><td><b>Measured depth (MD)</b><td>Distance along the well from the rig floor, not straight down. The rig floor is about 25 m above sea level. Seabed = rig floor height + water depth.
    <tr><td><b>Trial, success, rate</b><td>A trial is one described row or test; a success is one that meets the target's condition; the rate is successes ÷ trials.
    <tr><td><b>Log-odds</b><td>The scale evidence is added on: each layer adds or subtracts a number; the sum is turned into a rate.</table>
    <h2>Rate by group</h2>${fig("fp", 340, `Share of ${esc(w.rows)} that ${esc(w.hit)}, by formation or group. Dashed line: overall ${pct(d.base_rate)}.`)}`);
    plot($("#fp"), [{ type: "bar", x: fs.map((f) => f.name), y: fs.map((f) => f.rate * 100), marker: { color: css("--data") }, hovertemplate: "%{x}<br>%{y:.1f}%<extra></extra>" }], { yaxis: { title: "%", ticksuffix: "%" }, xaxis: { tickangle: -35 }, shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: d.base_rate * 100, y1: d.base_rate * 100, line: { color: css("--mut"), dash: "dash" } }], margin: { l: 56, r: 16, t: 10, b: 120 } });
  },

  // ---- the NCS earth model of the pilot (PLAN P7.2): group tops as surfaces (a unit's thickness is the gap to the next top), target cells
  // coloured by probability and faded by support, wells on their paths. Click a cell for the evidence chain behind its number.
  async earth(region, live) {
    const RG = await api("earth/regions"); region = region || "pilot";
    const RNAME = (id) => RG.find((r) => r.id === id)?.short || id.replace(/_/g, " ");
    const built = RG.filter((r) => r.built), ALL = region === "all" && built.length > 1, REG = ALL ? built.map((r) => r.id) : [region === "all" ? "pilot" : region];
    const listedBuild = (r) => RG.find((v) => v.id === r)?.build || "legacy";
    const [MS, SV] = await Promise.all([Promise.all(REG.map((r) => api("earth/meta", { region: r, build: listedBuild(r) }))), api("seismic/surveys").catch(() => [])]); if (!live()) return;
    if (MS.some((m) => !m.horizons)) throw new Error("Earth build unavailable. Reload the view.");
    const build = (r) => MS[REG.indexOf(r)]?.build || "legacy";
    const query = (r) => ({ region: r, build: build(r) });
    const href = (path, r) => `api/earth/${path}?${new URLSearchParams(query(r))}`;
    const ea = async (path, r, args = {}) => {
      const d = await api("earth/" + path, { ...args, ...query(r) });
      if (d.detail) throw new Error(typeof d.detail === "string" ? d.detail : "Invalid Earth request.");
      if (Object.hasOwn(d, "build") && (d.build || "legacy") !== build(r)) throw new Error("Scene build mismatch. Reload the view.");
      return d;
    };
    const buildText = (r) => build(r) === "legacy" ? "legacy, not frozen" : `build ${build(r)}`;
    const hasPilot = REG.includes("pilot");
    const smeaheia = hasPilot && SV.find((s) => s.id === "gn1101");
    const LN = {};  // seismic line lists per survey (shared with the inspector)
    const M = MS[0];  // targets and rules; every region has the same targets, its own numbers (the skill table and the info list them per region)
    const groups = [...new Set(MS.flatMap((m) => m.horizons.filter((h) => h.level === "GROUP" || h.level === "SEABED").map((h) => h.name)))];
    const fms = [...new Set(MS.flatMap((m) => m.horizons.filter((h) => h.level !== "GROUP" && h.level !== "SEABED").map((h) => h.name)))];
    const LAYN = [...groups, ...fms], gcol = (g) => (g === "SEABED" ? "#8fb8d8" : LAYC[Math.max(0, LAYN.indexOf(g)) % LAYC.length]);  // one colour per top, the same in the list and the scene
    const ML = [["coast", "coast", css("--mut"), "line"], ["grid", "latitude and longitude", css("--rule"), "line"], ["faults", "mapped faults (Sodir)", "#b5442c", "line"],
      ["elements", "structural elements (Sodir)", "#5b7fa6", "line"], ["names", "structural element names", "#5b7fa6", "text"], ["surveys", "seismic survey outlines", "#c99a06", "line"],
      ["plug", "Nature's Plug verdicts (Jeham): green pass, red fail; filled = own logs, open = taken from the nearest log well within 10 km", "linear-gradient(90deg,#1a9850 50%,#d73027 50%)", "fill"]];
    // settings survive a change of region or target (owner: changing the region reset everything); remembered per browser
    const SAVE = "earth:settings", sv = (() => { try { return JSON.parse(localStorage.getItem(SAVE) || "{}"); } catch { return {}; } })(), PRE = M.presets || {};
    const sugg = (t) => ["SEABED", ...(PRE[t]?.top_groups || [])].filter((g) => groups.includes(g));  // the groups where the target is most likely
    const autoP = (t) => Math.max(0.05, Math.min(0.95, Math.round((PRE[t]?.q90 ?? 0.5) * 20) / 20));  // top 10 percent of cells, not a fixed 0.5
    const st = { colour: "p", t: "hydrocarbons", pmin: 0.5, pauto: true, smin: 0.0, fade: true, weak: false, wells: true, obs: true, tied: false, ex: ALL ? 30 : 8, seq: 0, cam: null, ...sv, map: new Set(sv.map || ["coast", "grid", "faults", "elements"]),
      sv: { id: "", axis: "inline", pos: 0.5, v: 2.0, gain: 1, base: "", ck: "" } };
    if (!M.targets.some((t) => t.id === st.t)) st.t = "hydrocarbons";
    st.show = new Set((sv.show || sugg(st.t)).filter((g) => LAYN.includes(g))); if (!st.show.size) st.show = new Set(sugg(st.t));
    if (st.pauto) st.pmin = autoP(st.t);
    const keep = () => { try { localStorage.setItem(SAVE, JSON.stringify({ colour: st.colour, t: st.t, pmin: st.pmin, pauto: st.pauto, smin: st.smin, fade: st.fade, weak: st.weak, wells: st.wells, obs: st.obs, tied: st.tied, ex: st.ex, map: [...st.map], show: [...st.show] })); } catch {} };
    const tgt = (id, m = M) => m.targets.find((t) => t.id === id);
    const desk = stage2('<div class="fill" id="pe"></div>', () => {
      const r = st.selection?.region || REG[0];
      return { view: "earth", target: st.t, definition: tgt(st.t)?.title || "", region: r, earth_region: r, region_name: RNAME(r), earth_build: build(r),
        earth_wellbore: st.selection?.well || "", earth_target: st.t, cell: st.selection?.cell ?? null, probability_at_least: st.pmin, formations: [...st.show].slice(0, 30), depth_reference: "sea" };
    });
    const isComposite = (t) => ["co2_storage", "chance_of_success"].includes(t);
    const PRESET = [["oil", "Oil and gas prospects", "hydrocarbons"], ["res", "Reservoir quality", "reservoir"], ["co2", "CO2 storage", "co2_storage"], ["op", "Drilling hazard", "overpressure"]];
    const COLS = [["Target", [["p", "probability of the target"]]], ["Properties between wells", [["po", "porosity (%)"], ["gr", "gamma ray (gAPI)"]]], ["CO2 storage", [["cc", "capacity (kt per cell)"], ["lw", "nearby legacy wells (screening)"]]]];
    const CDESC = { p: "Colour = the target's probability (published form: model, unit rate or base rate); faint dots have little data behind them.", po: "Colour = estimated porosity, the compaction trend plus the unit's offset and nearby wells.",
      gr: "Colour = estimated gamma ray per unit: low is sand-like, high is shale-like. Only regions with FORCE log wells.", cc: "Colour = expected CO2 capacity of the cell at the median storage efficiency.", lw: "Nearby wellheads that reach below the cell top; not proven intersections or leaks." };
    sec("L", "e-r", "Region and presets", `<div class="row"><label>Region <select id="e-r">${RG.map((r) => `<option value="${r.id}" ${!ALL && r.id === REG[0] ? "selected" : ""} ${r.built ? "" : "disabled"}>${esc(r.title)}${r.built ? "" : " (not built)"}</option>`).join("")}
      ${built.length > 1 ? `<option value="all" ${ALL ? "selected" : ""}>All regions side by side (${built.length})</option>` : ""}</select></label></div>
      ${smeaheia ? `<div class="row"><button id="smeaheia" type="button" class="btn on">Explore Smeaheia</button></div><p class="tip">Go to GN1101 and show the feasibility workbook picks. These are research controls, not a calibrated volume.</p>` : ""}
      <p class="tip" style="margin:2px 0">Presets: a target, its likely strata and a threshold that shows its top 10 percent of cells.</p>
      <div class="row presets">${PRESET.map(([k, t]) => `<button class="btn" type="button" data-pre="${k}">${esc(t)}</button>`).join("")}</div>
      <p class="tip">Settings stay when you change region. Each region is fitted and tested on its own wells; "side by side" does not pool them.</p>`, true);
    sec("L", "e-t", "What is shown", `<div class="row"><label>Target <select id="e-t">${M.targets.map((t) => `<option value="${t.id}" ${t.id === st.t ? "selected" : ""}>${esc(t.title)}</option>`).join("")}</select></label></div>
      <p class="tip" id="e-td" style="margin:2px 0"></p>
      <div class="row"><label>Colour cells by <select id="e-c">${COLS.map(([g, os]) => `<optgroup label="${esc(g)}">${os.map(([v, t]) => `<option value="${v}" ${v === st.colour ? "selected" : ""}>${esc(t)}</option>`).join("")}</optgroup>`).join("")}</select></label></div>
      <p class="tip" id="e-cd" style="margin:2px 0"></p>`, true);
    sec("L", "e-fl", "Which cells", `<div class="row"><label class="chk" style="width:100%"><span id="e-pl">probability at least</span> <input type="range" id="e-p" min="0.05" max="0.95" step="0.05" value="${st.pmin}" style="flex:1"> <span id="e-pv" class="mono">${st.pmin.toFixed(2)}</span></label></div>
      <div class="row"><label class="chk"><input type="checkbox" id="e-pa" ${st.pauto ? "checked" : ""}> automatic: the target's top 10 percent of cells</label></div>
      <div class="row"><label class="chk" style="width:100%">support at least <input type="range" id="e-s" min="0" max="0.9" step="0.05" value="${st.smin}" style="flex:1"> <span id="e-sv" class="mono">${st.smin.toFixed(2)}</span></label></div>
      <div class="row"><label class="chk"><input type="checkbox" id="e-weak" ${st.weak ? "checked" : ""}> include cells with near-zero support</label></div>
      <div class="row"><label class="chk"><input type="checkbox" id="e-f" ${st.fade ? "checked" : ""}> fade cells with little support</label></div><p id="e-n" class="tip"></p>`, true);
    sec("L", "e-s", "Strata (group tops)", `<p class="tip" style="margin:2px 0">A group fills the space down to the next top. Point at a name to pick out its sheet · <button class="lnk" id="e-sug" type="button">suggested</button> · <button class="lnk" id="e-none" type="button">none</button> · <button class="lnk" id="e-all" type="button">all</button></p>
      <div id="e-g">${groups.map((g) => `<label class="chk lay" data-hl="${esc(g)}"><input type="checkbox" data-g="${esc(g)}" ${st.show.has(g) ? "checked" : ""}>${swatch(gcol(g))} ${esc(g)}</label>`).join("")}
      ${fms.length ? `<details style="margin-top:4px"><summary class="tip">Formation tops (${fms.length})</summary>${fms.map((g) => `<label class="chk lay" data-hl="${esc(g)}"><input type="checkbox" data-g="${esc(g)}" ${st.show.has(g) ? "checked" : ""}>${swatch(gcol(g))} ${esc(g)}</label>`).join("")}</details>` : ""}</div>`, true);
    sec("L", "e-m", "Wells and map", `<div class="row"><label class="chk lay" data-hl="wells"><input type="checkbox" id="e-w" ${st.wells ? "checked" : ""}>${swatch("#e0218a", "line")} wells (vertical depth; sidetracks without one estimated)</label></div>
      <div class="row"><label class="chk lay" data-hl="observed"><input type="checkbox" id="e-o" ${st.obs ? "checked" : ""}>${swatch("linear-gradient(90deg,#440154,#21918c,#fde725)", "line")} observed in wells: what each well found, unit by unit</label></div>
      <p class="tip" style="margin:2px 0">Map layers, drawn at sea level. Point at a name to pick it out.</p><div id="e-ml">${ML.map(([k, t, c, kind]) => `<label class="chk lay" data-hl="map:${k}"><input type="checkbox" data-m="${k}" ${st.map.has(k) ? "checked" : ""}>${swatch(c, kind)} ${esc(t)}</label>`).join("")}</div>`, false);
    sec("L", "seis", "Seismic", SV.length ? `<p class="tip" style="margin:0 0 6px">Preview depth = TWT × velocity / 2, assuming time zero at sea level. The first trace sample is not the seabed. Preview depths are not calibrated.</p>
      <div class="row"><label>Survey <select id="sv-id"><option value="">none</option>${SV.map((x) => `<option value="${x.id}">${esc(x.name)}</option>`).join("")}</select></label></div>
      <div class="row"><label class="chk"><input type="radio" name="sv-ax" value="inline" checked> inline</label><label class="chk"><input type="radio" name="sv-ax" value="crossline"> crossline</label>
        <label class="chk"><input type="radio" name="sv-ax" value="time"> time slice</label><label class="chk"><input type="radio" name="sv-ax" value="cube"> whole cube</label></div>
      <div class="row"><label class="chk" style="width:100%"><span id="sv-poslab">position</span> <input type="range" id="sv-pos" min="0" max="1" step="0.005" value="0.5" style="flex:1"></label></div><p class="tip" id="sv-lab" style="margin:0"></p>
      <div class="row"><label class="chk">velocity <input type="range" id="sv-v" min="1.6" max="2.8" step="0.05" value="2.0"> <span id="sv-vv">2.0 km/s</span></label></div>
      <div class="row"><label class="chk">gain <input type="range" id="sv-g" min="0.5" max="6" step="0.1" value="1"> <span id="sv-gv">1.0×</span></label></div>
      <div class="row"><label class="chk"><input type="checkbox" id="sv-clear" checked> see-through: weak amplitudes transparent</label></div>
      <div class="row"><label>Difference against <select id="sv-base"><option value="">none (amplitude)</option></select></label><span class="tip">same processing only</span></div>
      <div class="row">${hasPilot ? `<label class="chk"><input type="checkbox" id="sv-tied" ${st.tied ? "checked" : ""}> 2010 tied horizons (research)</label>` : ""} <button class="btn" id="sv-fly" type="button">Fly to survey</button></div>
      ${smeaheia ? `<div class="row"><label class="chk"><input type="checkbox" id="sv-picks"> GN1101 feasibility picks (interpretation)</label></div><p id="sv-pick-note" class="tip"></p>` : ""}
      <div class="row"><button class="btn on" id="sv-inspect" title="Open a side pane with a 2D section or time slice and a 3D cube of this survey">Inspect seismic ▸</button></div>
      <p class="tip" style="margin:4px 0">${[...new Set(SV.map((x) => x.credit))].map(esc).join("<br>")}</p>` : '<p class="tip">No seismic indexed.</p>', false);
    sec("L", "e-v", "Display", `<div class="row"><label class="chk">depth stretch <input type="range" id="e-x" min="1" max="60" value="${st.ex}"> <span id="e-xv">${st.ex}×</span></label></div>
      <div class="row"><button class="btn" id="e-top" type="button" title="look straight down, like a map">Top view</button> <button class="btn" id="e-reset" type="button">Reset view</button></div>
      <p class="tip">Export for Petrel / RMS: ${REG.map((r, i) => MS[i].export_available === false ? `${esc(RNAME(r))}: no verified export` : `<a href="${esc(href("export", r))}" download>${esc(RNAME(r))}</a>`).join(" · ")}</p>`, false);
    sec("R", "e-info", "What you are looking at", '<div id="e-ib"></div>', true);
    { const T7 = ["hydrocarbons", "oil", "gas", "reservoir", "overpressure", "green_clay", "calcareous_clay", "sandy_delta"];
      sec("R", "e-skill", "Skill by region (held-out wells)", `<p class="tip">Deviance gain (the share of the base rate's prediction error removed: 0 = none, 1 = perfect) over each region's base rate on held-out 40 km blocks of its own wells (0 = no better than the base rate). After the slash: the same model trained on wells completed before 2005 and scored on later wells (forward in time). In brackets: what is published (model, unit prior or base rate).</p>
        <table style="font-size:12px"><tr><th>target${built.map((r) => `<th class=r>${esc(r.short || r.title)}`).join("")}</tr>${T7.map((t) => `<tr><td>${t.replace(/_/g, " ")}${built.map((r) => { const k = r.skill[t]; return `<td class=r>${k ? `${k.gain_model_vs_base} / ${k.forward_in_time ?? "–"} <span class="tip">(${esc(k.published || "")})</span>` : "–"}`; }).join("")}</tr>`).join("")}</table>
        <p class="tip">Not built yet: ${RG.filter((r) => !r.built).map((r) => esc(r.title)).join(", ") || "none"}.</p>`, false); }
    const pickHint = "Click a cell, well marker or horizon to inspect its evidence.";
    sec("R", "e-cell", "Selected evidence", `<div id="e-cb"><p class="tip">${pickHint}</p></div>`, true);
    if (smeaheia) {
      sec("R", "e-support", "Smeaheia depth coverage", '<div id="e-depth-support"><p class="tip">Loading source coverage…</p></div>', false);
      const renderSupport = (audit) => {
        const el = $("#e-depth-support");
        if (!live() || !el) return;
        if (!audit?.surveys?.length) { el.textContent = "Local depth coverage receipt unavailable."; return; }
        const spans = (rows) => rows.length ? rows.slice(0, 3).map((r) => `${f2(r.from_md_m, 1)}–${f2(r.to_md_m, 1)} m MD`).join("; ") + (rows.length > 3 ? `; +${rows.length - 3} spans in receipt` : "") : "none in this source";
        const records = (w) => Object.entries(w.force).filter(([, rows]) => rows.length).map(([curve, rows]) => `${esc(curve)} ${spans(rows)}`).join("<br>");
        el.innerHTML = `<p><b>${audit.independent_ties_verified} verified independent ties.</b> MD spans below describe source coverage, not registration to seismic. Depths are along the hole.</p>
          ${audit.surveys.map((s) => `<h3>${esc(s.id.toUpperCase())}</h3><p class="tip">Indexed TWT ${s.indexed_time_ms.t0_ms} to ${s.indexed_time_ms.t_end_ms} ms. First sample is not the seabed.</p>
            ${s.wells.map((w) => `<details><summary>${esc(w.wellbore)} · ${esc(w.tie_status)}</summary>
            <p class="tip">Sodir NPDID ${w.npdid} · ${w.in_hull ? `${w.nearest_indexed_trace_m} m from nearest retained trace at wellhead` : "published reference, not in this indexed footprint screen"}</p>
            <p><b>Measured wireline (FORCE):</b><br>${records(w) || "none in FORCE training for this well."}</p>
            ${w.local_sonic.map((l) => `<p><b>Released sonic:</b> ${esc(l.curve)} (${esc(l.units)}), ${spans(l.spans)}.</p>`).join("")}
            <p><b>RealPore samples:</b> ${w.realpore.rows} rows, ${w.realpore.porosity_rows} porosity values${w.realpore.rows ? `; ${spans(w.realpore.spans)} (discrete plugs)` : ""}.</p>
            <p><b>Core–log pairs:</b> ${w.porosity_log_pairs.rows}${w.porosity_log_pairs.rows ? ` within 0.5 m MD; ${spans(w.porosity_log_pairs.spans)}` : " in this screen"}.</p>
            <p><b>Report-derived intervals:</b> ${w.report_intervals.length ? w.report_intervals.map((r) => `${esc(r.name)} ${f2(r.from_md_m, 0)}–${f2(r.to_md_m, 0)} m MD`).join("; ") : "none scored for this target"}.</p>
            ${w.published_picks.length ? `<p><b>Workbook interpretations:</b> ${esc(w.published_picks[0].source_well)}, ${w.published_picks.map((p) => `${f2(p.md_m, 1)} m MD → ${f2(p.twt_ms, 1)} ms TWT`).join("; ")}.</p>` : ""}
            ${w.datum_issue ? `<p class="tip">${esc(w.datum_issue)}</p>` : ""}
            ${w.report_reference ? `<p class="tip">§${esc(w.report_reference.section)}, PDF page ${w.report_reference.pdf_page}. ${esc(w.report_reference.note)}</p>` : ""}
            ${w.petrography_reference ? `<p class="tip">Petrography, Table ${esc(w.petrography_reference.table)}, PDF page ${w.petrography_reference.pdf_page}. ${esc(w.petrography_reference.note)}</p>` : ""}
            </details>`).join("")}`).join("")}
          <p class="tip">${esc(audit.credit)} · <a href="api/provenance/smeaheia-support" target="_blank" rel="noopener">Source rows, gaps and acquisition list</a></p>`;
      };
      api("provenance/smeaheia-support").then(renderSupport, () => renderSupport(null));
    }
    const C = new Map(), get = (k, f) => (C.has(k) ? Promise.resolve(C.get(k)) : f().then((v) => (C.set(k, v), v)));
    const info = () => { const t = tgt(st.t); const g = t.gain_model_vs_base; $("#e-ib").innerHTML = `<p><b>${esc(t.title)}</b>. Each prediction dot is one unit (formation, else group) in one ${REG.map((r, i) => MS[i].pilot.step_km).join("/")} km column. Colour = ${isComposite(t.id) ? "screening score (not a probability)" : "estimated probability"}; support is a separate score based on nearby evidence and held-out skill. Depth is metres below sea level.</p>
      <p class="tip">${REG.map((r) => `${esc(RNAME(r))}: ${build(r) === "legacy" ? buildText(r) : `<a href="${esc(href("snapshot", r))}" target="_blank" rel="noopener">${buildText(r)}</a>`}`).join(" · ")}</p>
      ${ALL ? `<p>${REG.map((r, i) => { const x = tgt(st.t, MS[i]); return x ? `${esc(MS[i].pilot.title)}: ${x.id === "co2_storage" ? "composite, not calibrated" : `gain <b>${x.gain_model_vs_base}</b> (${esc(x.published || "")})`}` : ""; }).join("<br>")}</p>`
      : t.id === "co2_storage" ? `<p>${esc(t.composite?.terms || "")}. Not calibrated: ${esc(t.why || "")}. Checks at known sites: ${Object.entries(t.checks || {}).map(([k, v]) => `${esc(k)}: ${Object.entries(v).filter(([kk]) => kk.endsWith("FM")).map(([kk, vv]) => `${esc(kk)} ${vv}`).join(", ")}`).join("; ")} (region median ${Object.values(t.checks || {})[0]?.pilot_median}).</p>`
        : `<p>Held-out wells (blocked 40 km): gain over the base rate <b>${g}</b> (unit prior alone ${t.gain_unit_prior_vs_base}); published: <b>${esc(t.published || "")}</b>; ${t.rows} observations in ${t.wells} wells; base rate ${pct(t.base_rate)}.</p>
          ${t.time_test?.gain_selected_features != null ? `<p class="tip">Forward in time (trained on wells completed before ${t.time_test.year}, scored on ${t.time_test.test_wells} later wells): gain ${t.time_test.gain_selected_features} (unit prior ${t.time_test.gain_unit_prior}).</p>` : ""}
          ${t.features ? `<p class="tip">Model inputs: ${esc(t.features.map((f) => FEATN[f] || f).join(", "))}. Model family: ${esc(t.family || "logistic")}${t.families ? ` (held-out / forward: ${Object.entries(t.families).map(([k, v]) => `${k} ${v.held_out} / ${v.forward_in_time ?? "–"}`).join("; ")})` : ""}.</p>` : ""}
          ${t.gain_nested != null ? `<p class="tip">With the inputs chosen inside each training fold (nested): gain ${t.gain_nested}, against ${t.gain_selected_on_same_folds} when chosen on the scored folds.${t.model_rejected ? ` Model not published: ${esc(t.model_rejected)}.` : ""}</p>` : ""}`}
      ${!ALL && t.id === "co2_storage" && M.co2_capacity ? capTable(M.co2_capacity) : ""}
      ${!ALL && t.id === "chance_of_success" && t.test ? `<p class="tip">Held-out check against wells with hydrocarbons (${t.test.rows} unit observations, calibrated on other blocks): chance of success ${t.test.gain_cos}; elements alone: ${(t.composite?.elements || []).map((e) => `${e} ${t.test["gain_" + e]}`).join(", ")}. Limiting element across cells: ${Object.entries(t.limiting_share || {}).map(([k, v]) => `${k} ${pct(v)}`).join(", ")}. Charge at ${esc(t.composite?.charge_at || "")}.</p>` : ""}
      ${M.conditional_on ? `<p class="tip"><b>Read as:</b> ${esc(M.conditional_on)}.</p>` : ""}
      <p class="tip">Model surfaces are estimates, not measured tops. Rock physics template results are diagnostic only and do not feed these probabilities. <a href="#log">Decision log</a>.</p>`; };
    const mapTraces = async (box) => {  // map layers in the scene's frame (EPSG:3035 km) at depth 0, clipped to the box
      const out = [], [x0, x1, y0, y1] = box, inb = (x, y) => x >= x0 && x <= x1 && y >= y0 && y <= y1;
      const line = (xs, ys, k, c, w, dash) => out.push({ type: "scatter3d", mode: "lines", x: xs, y: ys, z: xs.map((v) => (v == null ? null : 0)), line: { color: c, width: w, ...(dash ? { dash } : {}) }, name: ML.find((m) => m[0] === k)[1], meta: { hl: "map:" + k }, hoverinfo: "skip", showlegend: false });
      const proj = (pts) => { const xs = [], ys = []; let open = false; pts.forEach(([lo, la]) => { const [x, y] = L3035(lo, la); if (inb(x, y)) { xs.push(x); ys.push(y); open = true; } else if (open) { xs.push(null); ys.push(null); open = false; } }); xs.push(null); ys.push(null); return [xs, ys]; };
      if (st.map.has("coast")) { const xs = [], ys = []; (await coast()).forEach((ln) => { const [a, b] = proj(ln); xs.push(...a); ys.push(...b); }); line(xs, ys, "coast", css("--mut"), 3); }
      if (st.map.has("grid")) { const xs = [], ys = [];
        for (let la = 54; la <= 76; la += ALL ? 2 : 1) { const [a, b] = proj(Array.from({ length: 81 }, (_, i) => [-10 + i * 0.6, la])); xs.push(...a); ys.push(...b); }
        for (let lo = -10; lo <= 40; lo += ALL ? 5 : 2) { const [a, b] = proj(Array.from({ length: 61 }, (_, i) => [lo, 54 + i * 0.4])); xs.push(...a); ys.push(...b); }
        line(xs, ys, "grid", css("--rule"), 1); }
      const MP = await Promise.all(REG.map((r) => get("map|" + r, () => ea("map", r).catch(() => null))));
      MP.filter(Boolean).forEach((m) => {
        if (st.map.has("faults")) line(m.faults.x, m.faults.y, "faults", "#b5442c", 2.5);
        if (st.map.has("elements")) line(m.elements.x, m.elements.y, "elements", "#5b7fa6", 1.5, "dash");
        if (st.map.has("names")) { const n = m.element_names.filter((e) => inb(e.x, e.y)); out.push({ type: "scatter3d", mode: "text", x: n.map((e) => e.x), y: n.map((e) => e.y), z: n.map(() => 0), text: n.map((e) => e.name), textfont: { size: 10, color: "#5b7fa6" }, meta: { hl: "map:names" }, name: "structural element names", hovertext: n.map((e) => `${e.name}: ${e.kind}`), hoverinfo: "text", showlegend: false }); } });
      if (st.map.has("plug")) {  // Jeham's log-level screen (his engine, unchanged): solid = judged on the well's own logs, open = inherited
        const J = await get("plug", () => api("earth/jeham/wells").catch(() => null));
        if (J) { const COL = { pass: "#1a9850", fail: "#d73027" };
          const pts = (S, keep) => { const x = [], y = [], c = [], t = []; S.lat.forEach((la, i) => { if (!keep(i)) return; const [px, py] = L3035(S.lon[i], la); if (!inb(px, py)) return; x.push(px); y.push(py); c.push(COL[S.verdict[i]] || "#9a9a9a"); t.push(i); }); return { x, y, c, t }; };
          const I = pts(J.inherited, (i) => J.inherited.verdict[i] !== "none");
          out.push({ type: "scatter3d", mode: "markers", x: I.x, y: I.y, z: I.x.map(() => 0), marker: { size: 3.5, color: I.c, symbol: "circle-open", line: { width: 1.5, color: I.c } }, name: "Nature's Plug: inherited verdict", meta: { hl: "map:plug" },
            text: I.t.map((i) => `${J.inherited.name[i]}<br>Nature's Plug: ${J.inherited.verdict[i]}, taken from ${J.inherited.from[i]} at ${J.inherited.km[i]} km (his nearest-well rule)`), hoverinfo: "text", showlegend: false });
          const A = pts(J.assessed, () => true);
          out.push({ type: "scatter3d", mode: "markers", x: A.x, y: A.y, z: A.x.map(() => 0), marker: { size: 6, color: A.c, symbol: "circle", line: { width: 1, color: "#ffffff" } }, name: "Nature's Plug: own logs", meta: { hl: "map:plug" },
            text: A.t.map((i) => `${J.assessed.name[i]}<br>Nature's Plug: ${J.assessed.verdict[i]} on its own logs; longest clay run in the pressure window ${J.assessed.longest_m[i] ?? 0} m${J.assessed.group[i] ? ` (${J.assessed.group[i]})` : ""}<br>rule: 30 m of GR > 40 API, RDEP < 1.3 ohm.m, DTC > 135 us/ft inside the leak-off window`), hoverinfo: "text", showlegend: false }); } }
      if (st.map.has("surveys")) { const SV = await get("surveys", () => api("seismic/surveys").catch(() => [])); const xs = [], ys = []; SV.forEach((s) => { if (!s.footprint?.length) return; const [a, b] = proj([...s.footprint, s.footprint[0]].map(([la, lo]) => [lo, la])); xs.push(...a); ys.push(...b); }); line(xs, ys, "surveys", "#c99a06", 3); }
      return out; };
    const minSupport = () => Math.max(st.smin, st.weak ? 0 : 0.05);
    const drawScene = async () => {
      const my = ++st.seq, g = $("#pe"); $("#e-pv").textContent = st.pmin.toFixed(2); $("#e-sv").textContent = st.smin.toFixed(2); $("#e-xv").textContent = st.ex + "×"; info(); keep();
      $("#e-pl").textContent = isComposite(st.t) ? "score at least" : "probability at least";
      { const t = tgt(st.t); $("#e-td").textContent = t ? (t.base_rate != null ? `Base rate ${pct(t.base_rate)} of unit observations; published as ${t.published}.` : "A composite of other targets, not calibrated.") + (st.pauto ? ` Threshold: the top 10 percent of cells (${st.pmin.toFixed(2)}).` : "") : ""; $("#e-cd").textContent = CDESC[st.colour] || ""; }
      const lim = ALL ? Math.round(30000 / REG.length) : 30000;
      const drawnTarget = st.t, smin = minSupport();
      const D = await Promise.all(REG.map((r) => Promise.all([get("s|" + r, () => ea("surfaces", r, { step: ALL ? 3 : 2 })), get(["t", r, drawnTarget, st.pmin, smin].join("|"), () => ea("target", r, { t: drawnTarget, pmin: st.pmin, smin, limit: lim })), get("w|" + r, () => ea("wells", r))])));
      if (my !== st.seq || !g || !live()) return;
      const nT = D.reduce((n, d) => n + d[1].n, 0), nS = D.reduce((n, d) => n + d[1].shown, 0);
      $("#e-n").textContent = `${nT.toLocaleString()} cells at or above ${st.pmin.toFixed(2)}, support ≥ ${smin.toFixed(2)}${nS < nT ? `; ${nS.toLocaleString()} shown` : ""}.`;
      const tr = [];
      D.forEach(([S], ri) => S.surfaces.filter((h) => st.show.has(h.name)).forEach((h) => { const c = gcol(h.name); tr.push({ type: "surface", x: S.x, y: S.y, z: h.z.map((r) => r.map((v) => (v == null ? null : -v))), customdata: h.sd.map((r, a) => r.map((v, b) => [v, h.near_km[a][b]])), surfacecolor: h.z.map((r) => r.map(() => 0)), cmin: 0, cmax: 1,
        colorscale: [[0, c], [1, c]], showscale: false, opacity: 0.45, name: h.name, meta: { hl: h.name, pick: "surface", region: REG[ri] }, showlegend: false, hovertemplate: `estimated ${esc(h.name)}${ALL ? ` (${esc(REG[ri])})` : ""}: %{z:.0f} m (signed TVDSS)<br>± %{customdata[0]:.0f} m (1 sd); nearest well pick %{customdata[1]:.1f} km<extra></extra>`, lighting: { ambient: 0.85, diffuse: 0.3 } }); }));
      const bins = st.fade ? [[0.6, 1.01, 0.95, "well supported"], [0.3, 0.6, 0.5, "some support"], [-1, 0.3, 0.15, "little support"]] : [[-1, 1.01, 0.85, "cells"]];
      const prop = async (name, k) => { const P = (await Promise.all(REG.map((r) => get(k + "|" + r, () => ea("property", r, { name, limit: lim }).catch(() => null))))); return P.map((p, ri) => p && { ...p, ri }).filter(Boolean); };
      const join = (P, f) => P.flatMap((p) => (f === "customdata" ? p.cell.map((c, i) => [c, p.unit[i], p.sd?.[i], p.ri]) : p[f]));  // one list over the regions; customdata = cell, unit, sd, region
      const PC = { po: ["porosity", "porosity (estimated)", 0, 35, [[0, "#3b2c1a"], [0.5, "#c9a54a"], [1, "#fff3b0"]], "%", (G) => `Porosity between wells, sigma ${G.test?.sigma_pct} points (held-out error of the P3.2 model).`],
        cc: ["co2_capacity", "CO2 capacity", 0, null, [[0, "#e8f1f7"], [0.4, "#5aa4c8"], [1, "#0b3a5d"]], "kt", (G) => `Expected CO2 storage capacity per cell (kt) at the median efficiency (2 %), weighted by P(reservoir, dense CO2, seal, no overpressure).`] };
      if (PC[st.colour]) { const [nm, title, cmin, cmax, cs, un, why] = PC[st.colour]; const P = await prop(nm, st.colour); if (!P.length) { $("#e-n").textContent = "Not built in this region."; } else { if (my !== st.seq) return;
        const val = join(P, "value"), hi = cmax ?? Math.max(1, [...val].sort((a, b) => a - b)[Math.floor(val.length * 0.98)] || 1);
        $("#e-n").textContent = `${why(P[0])} ${P.reduce((n, p) => n + p.shown, 0).toLocaleString()} of ${P.reduce((n, p) => n + p.n, 0).toLocaleString()} cells (evenly thinned).`;
        tr.push({ type: "scatter3d", mode: "markers", name: title, meta: { pick: "cell" }, x: join(P, "x"), y: join(P, "y"), z: P.flatMap((p) => p.top.map((v, i) => -(v + p.base[i]) / 2)), customdata: join(P, "customdata"),
          marker: { size: 3.2, opacity: 0.85, color: val, cmin, cmax: hi, colorscale: cs, showscale: true, colorbar: { title: { text: un }, thickness: 10, len: 0.5 } },
          hovertemplate: `%{customdata[1]}<br>${title} %{marker.color:.1f} ${un}<extra></extra>` }); } }
      else if (st.colour === "lw") { const P = await prop("legacy_wells", "lw"); if (!P.length) { $("#e-n").textContent = "Not built in this region."; } else { if (my !== st.seq) return;
        $("#e-n").textContent = `${P.reduce((n, p) => n + p.shown, 0).toLocaleString()} of ${P.reduce((n, p) => n + p.n, 0).toLocaleString()} cells. ${P[0].test?.what || ""}`;
        tr.push({ type: "scatter3d", mode: "markers", name: "nearby legacy wells", meta: { pick: "cell" }, x: join(P, "x"), y: join(P, "y"), z: P.flatMap((p) => p.top.map((v, i) => -(v + p.base[i]) / 2)), customdata: join(P, "customdata"),
          marker: { size: 3.2, opacity: 0.8, color: join(P, "value"), cmin: 0, cmax: 20, colorscale: [[0, "#d9e7f2"], [0.25, "#f2b84e"], [1, "#a3271c"]], showscale: true, colorbar: { title: { text: "wellbores" }, thickness: 10, len: 0.5 } },
          hovertemplate: "%{customdata[1]}<br>%{marker.color:.0f} nearby wellheads reaching below the top<extra>screening only</extra>" }); } }
      else if (st.colour === "gr") { const P = await prop("gamma_ray", "gr"); if (!P.length) { $("#e-n").textContent = "No gamma-ray model here: no FORCE log wells."; } else { if (my !== st.seq) return; const t = P[0].test;
        $("#e-n").textContent = `Gamma ray in ${P.reduce((n, p) => n + p.shown, 0).toLocaleString()} of ${P.reduce((n, p) => n + p.n, 0).toLocaleString()} cells (evenly thinned${P.length < REG.length ? "; only regions with FORCE log wells" : ""}). Held-out wells: error ${t.rmse_model_gAPI} gAPI vs unit mean ${t.rmse_unit_mean_gAPI} and region mean ${t.rmse_pilot_mean_gAPI} (${t.wells} FORCE wells). One value per unit and column; within a unit the log varies by about ${t.within_unit_sd_median_gAPI} gAPI.`;
        tr.push({ type: "scatter3d", mode: "markers", name: "gamma ray (estimated)", meta: { pick: "cell" }, x: join(P, "x"), y: join(P, "y"), z: P.flatMap((p) => p.top.map((v, i) => -(v + p.base[i]) / 2)), customdata: join(P, "customdata"),
          marker: { size: 3.2, opacity: 0.8, color: join(P, "value"), cmin: 20, cmax: 150, colorscale: [[0, "#f2d74e"], [0.5, "#8c9a4b"], [1, "#5b3a1a"]], showscale: true, colorbar: { title: { text: "GR (gAPI)" }, thickness: 10, len: 0.5 } },
          hovertemplate: "%{customdata[1]}<br>gamma ray %{marker.color:.0f} ± %{customdata[2]:.0f} gAPI (estimated between wells)<extra>low = sand-like, high = shale-like</extra>" }); } }
      else bins.forEach(([lo, hi, op, nm]) => { const x = [], y = [], z = [], cd = [], col = [];
        D.forEach(([, T], ri) => T.support.forEach((s, i) => { if (s >= lo && s < hi) { x.push(T.x[i]); y.push(T.y[i]); z.push(-(T.top[i] + T.base[i]) / 2); cd.push([T.cell[i], T.unit[i], T.p05[i], T.p95[i], T.support[i], T.top[i], T.base[i], ri]); col.push(T.p[i]); } }));
        if (!x.length) return;
        tr.push({ type: "scatter3d", mode: "markers", name: nm, meta: { pick: "cell" }, x, y, z, customdata: cd,
          marker: { size: ALL ? 2.6 : 3.5, opacity: op, color: col, cmin: 0, cmax: 1, colorscale: "Viridis", showscale: !tr.some((o) => o.marker?.colorbar?.title?.text === "probability" || o.marker?.colorbar?.title?.text === "score"), colorbar: { title: { text: isComposite(drawnTarget) ? "score" : "probability" }, thickness: 10, len: 0.5 } },
          hovertemplate: `%{customdata[1]}<br>${isComposite(drawnTarget) ? "screening score %{marker.color:.2f}" : "probability %{marker.color:.0%} (90% range %{customdata[2]:.0%}–%{customdata[3]:.0%})"}<br>support %{customdata[4]:.2f}<br>%{customdata[5]:.0f}–%{customdata[6]:.0f} m TVDSS<extra>click for evidence</extra>` }); });
      const wellMarkers = [];
      if (st.wells) { const wx = [], wy = [], wz = []; D.forEach(([, , Wl], ri) => Wl.forEach((w) => {
        w.x.forEach((v, i) => { wx.push(v); wy.push(w.y[i]); wz.push(w.z[i] == null ? null : -w.z[i]); }); wx.push(null); wy.push(null); wz.push(null);
        const head = w.head || [w.x[0], w.y[0], w.z[0]]; if (head.every(Number.isFinite)) wellMarkers.push({ w, head, r: REG[ri] });
      }));
        tr.push({ type: "scatter3d", mode: "lines", x: wx, y: wy, z: wz, line: { color: "#e0218a", width: 3 }, name: "well paths", meta: { hl: "wells" }, hoverinfo: "skip" });
        tr.push({ type: "scatter3d", mode: "markers", x: wellMarkers.map((m) => m.head[0]), y: wellMarkers.map((m) => m.head[1]), z: wellMarkers.map((m) => -m.head[2]),
          text: wellMarkers.map((m) => esc(m.w.name)), marker: { size: 4, color: "#e0218a", symbol: "diamond" }, name: "well evidence", meta: { pick: "well", hl: "wells" }, hovertemplate: "%{text}<extra>well evidence</extra>" }); }
      if (st.obs && st.t !== "co2_storage" && st.t !== "chance_of_success") {  // backtracking: what the wells found, at vertical depth, coloured like the cells
        const O = (await Promise.all(REG.map((r) => get(["o", r, drawnTarget].join("|"), () => ea("observed", r, { t: drawnTarget }).catch(() => null))))).filter(Boolean); if (my !== st.seq) return;
        const ox = [], oy = [], oz = [], oc = [], ot = [];
        O.forEach((o) => o.x.forEach((x, i) => { ox.push(x, x, null); oy.push(o.y[i], o.y[i], null); oz.push(-o.top[i], -o.base[i], null); oc.push(o.ev[i], o.ev[i], o.ev[i]);
          const h = `${o.wellbore[i]} · ${o.unit[i]}<br>observed: ${o.ev[i] === 1 ? "yes" : o.ev[i] === 0 ? "no" : (o.ev[i] * 100).toFixed(0) + " % of records"} (evidence weight ${o.w[i]})<br>${o.top[i]}–${o.base[i]} m TVDSS`; ot.push(h, h, h); }));
        if (ox.length) tr.push({ type: "scatter3d", mode: "lines", x: ox, y: oy, z: oz, line: { color: oc, cmin: 0, cmax: 1, colorscale: "Viridis", width: 7 }, text: ot, hoverinfo: "text", name: "observed in wells", meta: { hl: "observed" } }); }
      const kmLL = (x, y) => L3035(x / (111.32 * Math.cos((61 * Math.PI) / 180)) + 3, y / 110.57 + 61);  // the seismic API's local km frame to EPSG:3035
      if (st.sv.id) { const sv = st.sv, sid = sv.id, gn = sv.gain, me = SV.find((x) => x.id === sid), zt = (t) => -((t / 2) * sv.v), see = sv.clear ? { opacityscale: KIT.OPQ } : {};
        const SC = [[0, "#2c5aa0"], [0.5, "#f7f7f7"], [1, "#b2182b"]], bar = { title: { text: "amplitude<br>(1 = survey p99)", side: "right" }, thickness: 10, len: 0.35, x: 1.0, y: 0.75, tickformat: ".1f" };
        const lab = (x, y, z, text) => tr.push({ type: "scatter3d", mode: "text", x, y, z, text, textfont: { size: 10, color: css("--ink") }, hoverinfo: "skip", showlegend: false, name: "seismic labels", meta: { hl: "seismic" } });
        const tticks = (t0, t1) => { const out = []; for (let t = Math.ceil(t0 / 500) * 500; t <= t1; t += 500) out.push(t); return out; };
        if (sv.axis === "inline" || sv.axis === "crossline") {
          if (!LN[sid]) LN[sid] = await api("seismic/lines", { survey: sid }); const arr = LN[sid][sv.axis], idx = arr[Math.round(sv.pos * (arr.length - 1))], ck = [sid, sv.axis, idx, sv.base].join("|");
          $("#sv-poslab").textContent = sv.axis; $("#sv-lab").textContent = `${sv.axis} ${idx} (of ${arr[0]}–${arr[arr.length - 1]}); depth = two-way time / 2 × ${sv.v.toFixed(2)} km/s from sea level`;
          if (sv.ck !== ck) { sv.cu = await api("seismic/curtain", { survey: sid, axis: sv.axis, index: idx, ...(sv.base ? { baseline: sv.base } : {}) }); sv.ck = ck; } if (my !== st.seq) return;
          const cu = sv.cu, P = cu.x.map((x, i) => kmLL(x, cu.y[i])), px = P.map((p) => p[0]), py = P.map((p) => p[1]), zz = cu.t_ms.map(zt), other = sv.axis === "inline" ? cu.xl : cu.il, oname = sv.axis === "inline" ? "XL" : "IL";
          tr.push({ type: "surface", x: cu.t_ms.map(() => px), y: cu.t_ms.map(() => py), z: zz.map((z) => px.map(() => z)), customdata: cu.t_ms.map((t) => px.map((_, i) => [t, other[i]])), surfacecolor: cu.amp.map((r) => r.map((v) => v / 127)), cmin: -1 / gn, cmax: 1 / gn,
            showscale: true, colorbar: bar, opacity: 1, name: `${sid} ${sv.axis} ${idx}`, meta: { hl: "seismic" }, ...see, colorscale: SC, lighting: { ambient: 1, diffuse: 0 },
            hovertemplate: `${esc(cu.survey)} · ${sv.axis} ${cu.index} · ${oname} %{customdata[1]}<br>two-way time %{customdata[0]:.0f} ms<br>depth preview %{z:.0f} m TVDSS<br>amplitude %{surfacecolor:.2f} (survey p99 = 1)<extra></extra>` });
          const n = px.length, ks = [0, Math.floor(n / 4), Math.floor(n / 2), Math.floor((3 * n) / 4), n - 1], top = zt(cu.t_ms[0]);  // line numbers along the top edge, time and depth down the start edge
          lab(ks.map((k) => px[k]), ks.map((k) => py[k]), ks.map(() => top + 150), ks.map((k) => `${oname} ${other[k]}`));
          const tk = tticks(cu.t_ms[0], cu.t_ms[cu.t_ms.length - 1]); lab(tk.map(() => px[0]), tk.map(() => py[0]), tk.map(zt), tk.map((t) => `${t} ms · ${Math.round(-zt(t))} m`)); }
        else if (sv.axis === "time") {
          const t0 = me?.t0_ms ?? 0, t1 = me?.t_end_ms ?? 4000, t = Math.round((t0 + sv.pos * (t1 - t0)) / 4) * 4, ck = [sid, "t", t, sv.base].join("|");
          $("#sv-poslab").textContent = "two-way time"; $("#sv-lab").textContent = `time slice at ${t} ms two-way time ≈ ${Math.round((t / 2) * sv.v)} m below sea level (at ${sv.v.toFixed(2)} km/s)`;
          if (sv.ck !== ck) { sv.sl = await api("seismic/slice", { survey: sid, t_ms: t, ...(sv.base ? { baseline: sv.base } : {}) }); sv.ck = ck; } if (my !== st.seq) return;
          const S = sv.sl, XY = S.x.map((r, a) => r.map((x, b) => (x == null || S.y[a][b] == null ? null : kmLL(x, S.y[a][b]))));
          tr.push({ type: "surface", x: XY.map((r) => r.map((p) => p && p[0])), y: XY.map((r) => r.map((p) => p && p[1])), z: XY.map((r) => r.map((p) => (p ? zt(S.t_ms) : null))), surfacecolor: S.amp.map((r) => r.map((v) => (v == null ? null : v / 127))),
            customdata: S.amp.map((r, a) => r.map((_, b) => [S.il[a], S.xl[b]])), cmin: -1 / gn, cmax: 1 / gn, showscale: true, colorbar: bar, colorscale: SC, ...see, name: `${sid} t ${S.t_ms} ms`, meta: { hl: "seismic" }, lighting: { ambient: 1, diffuse: 0 },
            hovertemplate: `${esc(sid)} · IL %{customdata[0]} · XL %{customdata[1]}<br>two-way time ${S.t_ms} ms, depth preview %{z:.0f} m TVDSS<br>amplitude %{surfacecolor:.2f} (survey p99 = 1)<extra></extra>` });
          const c = (a, b) => XY[a]?.[b]; const corners = [[0, 0], [0, S.xl.length - 1], [S.il.length - 1, 0], [S.il.length - 1, S.xl.length - 1]].map(([a, b]) => { for (let d = 0; d < 30; d++) { const p = c(Math.abs(a - d), Math.abs(b - d)) || c(a, Math.abs(b - d)) || c(Math.abs(a - d), b); if (p) return [p, a, b]; } return null; }).filter(Boolean);
          lab(corners.map((q) => q[0][0]), corners.map((q) => q[0][1]), corners.map(() => zt(S.t_ms) + 120), corners.map((q) => `IL ${S.il[q[1]]} · XL ${S.xl[q[2]]}`)); }
        else {  // the whole cube: evenly spaced time slices through the block, weak amplitudes see-through (a rotated survey is not a regular volume in this frame)
          const ck = [sid, "cube"].join("|"); $("#sv-poslab").textContent = "slices"; if (sv.ck !== ck) { sv.cb = await api("seismic/cube", { survey: sid, max_points: 160000, horizons: false }); sv.ck = ck; } if (my !== st.seq) return;
          const B = sv.cb, ni = B.il.length, nj = B.xl.length, nt = B.t_ms.length, f = B.xy_from_il_xl, nS = Math.round(4 + sv.pos * 16);
          $("#sv-lab").textContent = `whole cube: ${nS} time slices from ${B.t_ms[0]} to ${B.t_ms[nt - 1]} ms (${ni} × ${nj} traces after thinning by ${B.stride.inline}); depth = time / 2 × ${sv.v.toFixed(2)} km/s`;
          const XY = B.il.map((il) => B.xl.map((xl) => kmLL(f.x[0] + f.x[1] * il + f.x[2] * xl, f.y[0] + f.y[1] * il + f.y[2] * xl)));
          for (let s = 0; s < nS; s++) { const k = Math.round((s + 0.5) * (nt / nS) - 0.5), T = B.t_ms[k];
            tr.push({ type: "surface", x: XY.map((r) => r.map((p) => p[0])), y: XY.map((r) => r.map((p) => p[1])), z: XY.map((r) => r.map(() => zt(T))), surfacecolor: B.il.map((_, a) => B.xl.map((_, b) => { const v = B.amp[(a * nj + b) * nt + k]; return v === 0 ? null : v / 127; })),
              cmin: -1 / gn, cmax: 1 / gn, colorscale: SC, opacity: 0.55, opacityscale: KIT.OPQ, showscale: s === 0, colorbar: bar, name: `${sid} t ${T} ms`, meta: { hl: "seismic" }, lighting: { ambient: 1, diffuse: 0 },
              hovertemplate: `${esc(sid)}<br>two-way time ${T} ms, depth preview %{z:.0f} m TVDSS<br>amplitude %{surfacecolor:.2f} (survey p99 = 1)<extra></extra>` }); }
          const C4 = [[0, 0], [0, nj - 1], [ni - 1, 0], [ni - 1, nj - 1]], ztop = zt(B.t_ms[0]), zbot = zt(B.t_ms[nt - 1]), ex = [], ey = [], ez = [];  // the block's vertical edges, labelled
          C4.forEach(([a, b]) => { ex.push(XY[a][b][0], XY[a][b][0], null); ey.push(XY[a][b][1], XY[a][b][1], null); ez.push(ztop, zbot, null); });
          tr.push({ type: "scatter3d", mode: "lines", x: ex, y: ey, z: ez, line: { color: css("--mut"), width: 2 }, hoverinfo: "skip", showlegend: false, name: "cube edges", meta: { hl: "seismic" } });
          lab(C4.map(([a, b]) => XY[a][b][0]), C4.map(([a, b]) => XY[a][b][1]), C4.map(() => ztop + 150), C4.map(([a, b]) => `IL ${B.il[a]} · XL ${B.xl[b]}`));
          const tk = tticks(B.t_ms[0], B.t_ms[nt - 1]); lab(tk.map(() => XY[0][0][0]), tk.map(() => XY[0][0][1]), tk.map(zt), tk.map((t) => `${t} ms · ${Math.round(-zt(t))} m`)); } }
      let picks = null;
      if (st.picks) {
        picks = await get("gn1101-picks", () => api("provenance/velocity/picks"));
        if (my !== st.seq || !live()) return;
        $("#sv-pick-note").textContent = picks.picks?.length ? `${picks.picks.length} picks at two sites. Click an amber marker for the source row.` : "Feasibility pick receipt unavailable. Amplitudes are still only a preview.";
        if (picks.picks?.length) tr.push({ type: "scatter3d", mode: "markers", name: "GN1101 feasibility picks", meta: { pick: "gn1101", region: "pilot" },
          x: picks.picks.map((p) => p.x_km), y: picks.picks.map((p) => p.y_km), z: picks.picks.map((p) => p.tvdss_m_signed),
          text: picks.picks.map((p) => `${esc(p.source_well)} · ${esc(p.horizon)}`), marker: { size: 5, color: "#e5a817", symbol: "diamond" },
          hovertemplate: "%{text}<br>%{z:.0f} m signed TVDSS<extra>workbook interpretation</extra>" });
      } else if ($("#sv-pick-note")) $("#sv-pick-note").textContent = "";
      if (st.tied && hasPilot) { const T = await get("tied|pilot", () => ea("tied", "pilot", { step: 2 }).catch(() => null)); if (my !== st.seq || !live()) return; const HC = ["#1b9e77", "#d95f02", "#7570b3"];
        if (T?.surfaces.length) {
        const XY = T.lon.map((r, a) => r.map((lo, b) => (lo == null || T.lat[a][b] == null ? null : L3035(lo, T.lat[a][b]))));
        T.surfaces.forEach((h, i) => tr.push({ type: "surface", x: XY.map((r) => r.map((p) => p && p[0])), y: XY.map((r) => r.map((p) => p && p[1])), z: h.z.map((r) => r.map((v) => (v == null ? null : -v))), surfacecolor: h.z.map((r) => r.map(() => 1)), colorscale: [[0, HC[i % 3]], [1, HC[i % 3]]], showscale: false, opacity: 0.6,
          name: h.name + " (2010 research tie)", meta: { pick: "tied", region: "pilot", horizon: h.name, source: T.source }, customdata: h.sd, hovertemplate: `${esc(h.name)}: research depth estimate<br>%{z:.0f} m (± %{customdata:.0f} m)<extra>Smeaheia 2010 horizons</extra>`, lighting: { ambient: 0.85, diffuse: 0.3 } }));
      } }
      const xr = [Math.min(...D.map(([S]) => Math.min(...S.x))), Math.max(...D.map(([S]) => Math.max(...S.x)))], yr = [Math.min(...D.map(([S]) => Math.min(...S.y))), Math.max(...D.map(([S]) => Math.max(...S.y)))], zr = [-5500, 0];
      st._g = { xr, yr, zr, ar: { x: 1, y: (yr[1] - yr[0]) / (xr[1] - xr[0]), z: ((zr[1] - zr[0]) / 1000 / (xr[1] - xr[0])) * st.ex } };
      tr.unshift(...(await mapTraces([xr[0], xr[1], yr[0], yr[1]]))); if (my !== st.seq) return;
      let cam = null; if (!st.camForce) { try { if (g.data?.length) cam = g._fullLayout.scene._scene.getCamera(); } catch {} if (cam) st.cam = cam; } st.camForce = false;
      const ax = (t, r) => ({ title: t, range: r, autorange: false, gridcolor: css("--rule"), color: css("--mut"), showbackground: false });
      g._hl0 = null;  // a new drawing: forget any highlight saved from the previous one
      await plot3(g, tr, { margin: { l: 0, r: 0, t: 0, b: 0 }, uirevision: st.cam ? "earth" : "earth-" + st.seq, legend: { orientation: "h", x: 0.02, y: 0.02, font: { size: 11 } }, scene: { aspectmode: "manual", aspectratio: { x: 1, y: (yr[1] - yr[0]) / (xr[1] - xr[0]), z: ((zr[1] - zr[0]) / 1000 / (xr[1] - xr[0])) * st.ex },
        camera: st.cam || { eye: { x: 1.3, y: -1.5, z: 0.9 } }, xaxis: ax("East (km, EPSG:3035)", xr), yaxis: ax("North (km)", yr), zaxis: { ...ax("Depth below sea level (m)", zr), tickvals: [0, -1000, -2000, -3000, -4000, -5000], ticktext: ["0", "1000", "2000", "3000", "4000", "5000"] } } });
      if (my !== st.seq || !live()) return;
      const showEvidence = (selection, html) => {
        st.selection = selection; desk?.sync?.();
        $("#e-cb").innerHTML = html; $("#sec-e-cell").classList.remove("fold");
      };
      g.removeAllListeners?.("plotly_click"); g.on("plotly_click", async (e) => {
        const point = e.points?.[0], m = point?.data?.meta, cd = point?.customdata;
        if (!m?.pick || !live() || my !== st.seq) return;
        const click = st.click = (st.click || 0) + 1;
        if (m.pick === "well") {
          const hit = wellMarkers[point.pointNumber]; if (!hit) return;
          const { w, r } = hit;
          showEvidence({ region: r, well: w.name }, `<p><b>${esc(w.name)}</b> · ${esc(w.source)}</p>
            <p>FactPages: rig floor ${f2(w.rkb_m, 1)} m above sea level; water depth ${f2(w.water_depth_m, 0)} m; TD ${f2(w.td_md_m, 0)} m MD (along hole).
            End-of-hole TVD ${f2(w.end_tvd_m, 0)} m below rig floor${w.depth_source === "estimated" ? ` (estimated, σ ${f2(w.end_tvd_sd_m, 0)} m)` : ""}.</p>
            <p class="tip">${w.source === "FORCE path" ? "Logged positions only where available." : "Path shown at the wellhead: lateral trajectory not resolved."} Source rows: <code>wells.parquet</code> and <code>${w.source === "FORCE path" ? "force_paths.parquet" : "tops.parquet"}</code>, keyed by wellbore · ${buildText(r)}.</p>`);
          return;
        }
        if (m.pick === "gn1101") {
          const p = picks?.picks[point.pointNumber]; if (!p) return;
          showEvidence({ region: "pilot" }, `<p><b>${esc(p.horizon)}</b> · ${esc(p.source_well)}</p>
            <p>Workbook interpretation: ${f2(p.twt_ms)} ms TWT → ${f2(-p.tvdss_m_signed)} m below sea level. ${f2(p.md_m)} m MD along the hole. Seabed: ${f2(p.seabed_twt_ms, 1)} ms interpreted TWT; ${f2(p.water_depth_m, 0)} m registered water depth.</p>
            <p class="tip">${esc(picks.source.member)} · ${esc(p.sheet)}, row ${p.row}. Sodir NPDID ${p.factpages_npdid}: ${esc(p.site_link)}. These are not independent checkshots. <a href="api/provenance/velocity" target="_blank" rel="noopener">Source receipt and held-out results</a>.</p>`);
          return;
        }
        if (m.pick === "surface" || m.pick === "tied") {
          if (!Number.isFinite(point.z)) return;
          const tied = m.pick === "tied";
          showEvidence({ region: m.region }, `<p><b>${esc(tied ? m.horizon : point.data.name)}</b> · ${tied ? "research interpretation converted to depth" : "modelled surface"}</p>
            <p>${f2(-point.z, 0)} m below sea level at ${f2(point.x, 1)}, ${f2(point.y, 1)} km (EPSG:3035) · σ ${f2(tied ? cd : cd?.[0], 0)} m${tied ? "" : ` · nearest well pick ${f2(cd?.[1], 1)} km`}.</p>
            <p class="tip">${tied ? `${esc(m.source)}. Not GN1101 workbook picks; no independent checkshot validation.` : "Derived estimate, not a measured well top. See surfaces.npz in the snapshot receipt."} · ${buildText(m.region)}.</p>`);
          return;
        }
        if (m.pick !== "cell" || !Array.isArray(cd) || !Number.isInteger(cd[0])) return;
        const rg = REG[cd[cd.length - 1]] || REG[0];
        showEvidence({ region: rg }, '<p class="tip">Loading cell evidence…</p>');
        let c;
        try { c = await ea("cell", rg, { t: drawnTarget, cell: cd[0] }); }
        catch (err) {
          if (live() && my === st.seq && st.click === click) showEvidence({ region: rg }, `<p class="tip">${esc(err.message)} Reload the 3D view.</p>`);
          return;
        }
        if (!live() || my !== st.seq || st.click !== click) return;
        showEvidence({ region: rg, cell: cd[0] }, `<p><b>${esc(c.unit)}</b> (${esc(c.group)}) · ${buildText(rg)} · cell ${cd[0]}.</p>
          <p>${c.x_km}, ${c.y_km} km: ${c.top_m}–${c.base_m} m below sea level, ${c.thickness_m} m thick, ${c.depth_below_seabed_m} m below the seabed${c.group_top_sd_m != null ? `; group top ± ${c.group_top_sd_m} m, nearest pick ${c.group_top_nearest_pick_km} km` : ""}.</p>
          <p>${esc(c.title)}: ${isComposite(c.target) ? `<b>${f2(c.p)}</b> screening score (not a probability)` : `<b>${pct(c.p)}</b> probability (90% range ${pct(c.p05)}–${pct(c.p95)})`}; support <b>${c.support}</b> (0–1). Published as: ${esc(c.published || "composite")}.</p>
          ${c.nearest_observations ? `<table style="font-size:12px"><tr><th>nearest ${esc(c.unit)} observation<th class=r>distance (km)<th class=r>observed (0–1)<th class=r>evidence weight</tr>${c.nearest_observations.map((o) => `<tr><td>${esc(o.wellbore)}<td class=r>${o.distance_km}<td class=r>${o.event}<td class=r>${o.weight}</tr>`).join("")}</table><p class="tip">Unit rate across the region: ${pct(c.unit_rate)}. Model weights (per standard deviation of each input, on the log-odds scale): ${esc(JSON.stringify(c.coefficients))}.</p>` : `<p>Terms here: reservoir ${c.terms?.reservoir}, overpressure ${c.terms?.overpressure}. ${esc(c.composite?.terms || "")}</p>`}
          ${c.factors ? `<p class="tip">Petroleum system here: nearest mature source ${c.factors.kitchen_km} km (${c.factors.kitchen_at_max_burial_km} km at maximum burial, gas window ${c.factors.gas_kitchen_km} km); source below in the oil window with probability ${pct(c.factors.source_mature_below_p)}; nearest mapped fault ${c.factors.fault_km} km; ${c.factors.on_structural_high ? "on a mapped structural high" : "not on a mapped high"}; closure on the unit top ${c.factors.closure_m} m${c.factors.salt_km ? `; salt ${c.factors.salt_km} km` : ""}${c.factors.charge_p != null ? `; oil migrating along this unit reaches it with probability ${pct(c.factors.charge_p)} (${c.factors.charge_km2} km² of mature kitchen upstream)` : ""}. Used by this model: ${esc(c.factors.used_by_model.map((f) => FEATN[f] || f).join(", ") || "none (none beat the model without them on held-out wells)")}.</p>` : ""}
          ${c.elements ? `<p>Elements: ${Object.entries(c.elements).map(([k, v]) => `${k} <b>${v}</b>`).join(" × ")}; limiting element: <b>${esc(c.limiting_element || "")}</b>.</p>` : ""}
          ${c.co2_capacity_kt != null ? `<p class="tip">Expected CO2 capacity of this cell: <b>${c.co2_capacity_kt}</b> kt (median efficiency).</p>` : ""}
          ${c.legacy_wells != null ? `<p class="tip">Nearby legacy wells: <b>${c.legacy_wells}</b>. Screening only: proximity and end depth, not a confirmed intersection.</p>` : ""}
          ${c.rules?.length ? `<p class="tip">Rules: ${c.rules.map((r) => `${esc(r.id)} (${esc(r.verdict)})`).join(", ")}.</p>` : ""}`); });
    };
    const draw = () => {
      const seq = st.seq + 1;
      return drawScene().catch((err) => {
        if (!live() || seq !== st.seq) return;
        $("#e-n").textContent = `Scene not updated: ${err.message}`;
      });
    };
    const setG = (a) => { st.show = new Set(a.filter((g) => groups.includes(g))); $$("[data-g]").forEach((c) => (c.checked = st.show.has(c.dataset.g))); draw(); };
    const setT = (t) => { st.t = t; st.selection = null; $("#e-cb").textContent = pickHint; desk?.sync?.(); $("#e-t").value = t; if (st.pauto) { st.pmin = autoP(t); $("#e-p").value = st.pmin; } };
    $("#e-t").onchange = (e) => { setT(e.target.value); draw(); };
    $("#e-p").oninput = (e) => { st.pmin = +e.target.value; st.pauto = false; $("#e-pa").checked = false; draw(); };
    $("#e-pa").onchange = (e) => { st.pauto = e.target.checked; if (st.pauto) { st.pmin = autoP(st.t); $("#e-p").value = st.pmin; } draw(); };
    $("#e-s").oninput = (e) => { st.smin = +e.target.value; draw(); };
    $("#e-weak").onchange = (e) => { st.weak = e.target.checked; draw(); };
    $("#e-f").onchange = (e) => { st.fade = e.target.checked; draw(); }; $("#e-c").onchange = (e) => { st.colour = e.target.value; draw(); }; $("#e-w").onchange = (e) => { st.wells = e.target.checked; draw(); }; $("#e-x").oninput = (e) => { st.ex = +e.target.value; draw(); };
    $("#e-g").onchange = (e) => { const n = e.target.dataset.g; if (!n) return; e.target.checked ? st.show.add(n) : st.show.delete(n); draw(); };
    $("#e-ml").onchange = (e) => { const n = e.target.dataset.m; if (!n) return; e.target.checked ? st.map.add(n) : st.map.delete(n); draw(); };
    $("#e-none").onclick = () => setG([]); $("#e-all").onclick = () => setG(groups); $("#e-sug").onclick = () => setG(sugg(st.t));
    $$("[data-pre]").forEach((b) => (b.onclick = () => { const [, , t] = PRESET.find((p) => p[0] === b.dataset.pre); st.colour = "p"; $("#e-c").value = "p"; st.pauto = true; $("#e-pa").checked = true; st.smin = 0; $("#e-s").value = 0; st.fade = true; $("#e-f").checked = true;
      setT(t); setG(sugg(t)); }));
    $("#e-top").onclick = () => { st.cam = { eye: { x: 0, y: 0, z: 2.4 }, up: { x: 0, y: 1, z: 0 } }; st.camForce = true; draw(); };
    $("#e-reset").onclick = () => { st.cam = null; st.camForce = true; draw(); };
    [$("#e-g"), $("#sec-e-m")].forEach((el) => el && hoverLayers(el, () => $("#pe"), (n) => (n.startsWith("map:") || n === "wells" || n === "observed" ? null : gcol(n))));
    $("#e-o").onchange = (e) => { st.obs = e.target.checked; draw(); };
    const KIT = seismicKit({ SV, LN, get sv() { return st.sv; }, later: draw });  // the inspector (side pane, 2D and 3D), shared module
    if ($("#sv-id")) { const sv = st.sv; $("#sv-id").onchange = (e) => { sv.id = e.target.value; sv.base = ""; sv.ck = ""; const me = SV.find((x) => x.id === sv.id); $("#sv-base").innerHTML = '<option value="">none (amplitude)</option>' + SV.filter((x) => me && me.processing && x.id !== sv.id && x.processing === me.processing).map((x) => `<option value="${x.id}">${esc(x.name)}</option>`).join(""); draw(); };
      sv.clear = true; $$('[name="sv-ax"]').forEach((r) => (r.onchange = (e) => { sv.axis = e.target.value; sv.ck = ""; draw(); })); $("#sv-pos").oninput = (e) => { sv.pos = +e.target.value; draw(); };
      $("#sv-clear").onchange = (e) => { sv.clear = e.target.checked; draw(); };
      $("#sv-v").oninput = (e) => { sv.v = +e.target.value; $("#sv-vv").textContent = sv.v.toFixed(2) + " km/s"; draw(); }; $("#sv-g").oninput = (e) => { sv.gain = +e.target.value; $("#sv-gv").textContent = sv.gain.toFixed(1) + "×"; draw(); }; $("#sv-base").onchange = (e) => { sv.base = e.target.value; sv.ck = ""; draw(); };
      if ($("#sv-tied")) $("#sv-tied").onchange = (e) => { st.tied = e.target.checked; draw(); };
      if ($("#sv-picks")) $("#sv-picks").onchange = (e) => { st.picks = e.target.checked; draw(); };
      const fly = (x) => { const g = st._g; if (!g || !x) return;
        // frame the survey: centre on its footprint at about 1.5 km depth, eye at a distance in proportion to its size (scene units: x spans ar.x)
        const fp = (x.footprint || []).map(([la, lo]) => L3035(lo, la)), xs = fp.map((p) => p[0]), ys = fp.map((p) => p[1]), [cx, cy] = fp.length ? [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2] : L3035(x.centre[1], x.centre[0]);
        const size = fp.length ? Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 5) : 30, f = (size / (g.xr[1] - g.xr[0])) * g.ar.x;
        const c = { x: ((cx - (g.xr[0] + g.xr[1]) / 2) / (g.xr[1] - g.xr[0])) * g.ar.x, y: ((cy - (g.yr[0] + g.yr[1]) / 2) / (g.yr[1] - g.yr[0])) * g.ar.y, z: ((-1500 - (g.zr[0] + g.zr[1]) / 2) / (g.zr[1] - g.zr[0])) * g.ar.z };
        st.cam = { center: c, eye: { x: c.x + 0.9 * f, y: c.y - 1.1 * f, z: c.z + 0.8 * f }, up: { x: 0, y: 0, z: 1 } }; st.camForce = true; draw(); };
      $("#sv-fly").onclick = () => fly(SV.find((q) => q.id === sv.id) || SV[0]);
      if ($("#smeaheia")) $("#smeaheia").onclick = () => {
        $("#sv-picks").checked = st.picks = true;
        // Jump to the footprint without switching on an uncalibrated amplitude curtain.
        fly(smeaheia);
      };
    }
    REDRAW.scene = draw; await draw();
    { const la = [Math.min(...MS.map((m) => m.pilot.lat[0])), Math.max(...MS.map((m) => m.pilot.lat[1]))], lo = [Math.min(...MS.map((m) => m.pilot.lon[0])), Math.max(...MS.map((m) => m.pilot.lon[1]))];
      minimap($(".plotwrap"), { lat: la, lon: lo }, ALL ? `All ${REG.length} regions: ${la[0]}–${la[1]}°N, ${lo[0]}–${lo[1]}°E` : `${M.pilot.title}: ${la[0]}–${la[1]}°N, ${lo[0]}–${lo[1]}°E`); }
    $("#e-r").onchange = (e) => { location.hash = "earth/" + e.target.value; };
  },

  // ---- rock physics template on the FORCE wells with shear logs (PLAN P11.1): acoustic impedance against Vp/Vs, model lines for friable and
  // cemented sand with brine, oil and gas, the samples coloured by what they say; the tests of cementation and fluid beside it.
  async rpt(region, live) {
    const RG = (await api("earth/regions")).filter((r) => r.built); region = region || "pilot";
    const [D, ablation] = await Promise.all([api("earth/rpt", { region }).catch(() => null), api("provenance/rock-porosity").catch(() => null)]); if (!live()) return;
    const st = { col: "cement", only: false, lines: new Set(["friable sand|brine", "contact cement|brine", "friable sand|gas", "contact cement|gas"]), clay: 0 };
    stage2('<div class="fill" id="pr"></div>', () => ({ view: "rock physics", target: "rock physics template", region }));
    sec("L", "r-r", "Region", `<div class="row"><label>Region <select id="r-r">${RG.map((r) => `<option value="${r.id}" ${r.id === region ? "selected" : ""}>${esc(r.title)}</option>`).join("")}</select></label></div>
      <p class="tip">Only FORCE wells with a shear-sonic log (32 of 98) can be placed on the template; the Norwegian and Barents Seas have none.</p>`, true);
    if (!D) { $("#pr").innerHTML = '<div class="doc"><p class="tip">No FORCE wells with shear logs in this region.</p></div>'; return; }
    const COLS = { cement: ["cement index (0 friable, 1 cemented)", -0.5, 1.5], T: ["temperature (C)", 20, 140], phi: ["density porosity", 0, 0.4], dai: ["softening against brine (dAI)", -0.1, 0.1] };
    sec("L", "r-c", "What is shown", `<div class="row"><label>Colour samples by <select id="r-c">${Object.entries(COLS).map(([k, [t]]) => `<option value="${k}" ${k === st.col ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label></div>
      <div class="row"><label class="chk"><input type="checkbox" id="r-o"> only samples where the models apply (clean sand, porosity 15-37 %)</label></div>
      <p class="tip" style="margin:2px 0">Model lines (porosity 5-39 %, clean sand, effective pressure ${D.report.template_pressure_MPa} MPa):</p>
      <div id="r-l">${["friable sand", "contact cement"].flatMap((m) => ["brine", "oil", "gas"].map((f) => `<label class="chk lay"><input type="checkbox" data-ln="${m}|${f}" ${st.lines.has(m + "|" + f) ? "checked" : ""}>${swatch(RPTC[f], "line")} ${m}, ${f}</label>`)).join("")}</div>`, true);
    const verdict = (t) => (t ? `${tag(t.verdict === "agrees" ? "ok" : t.verdict === "disagrees" ? "bad" : "warnc", t.verdict)}` : "");
    const P = D.pooled || {}, ct = P.cement_test || {}, ft = P.fluid_test || {};
    sec("R", "r-i", "What it shows", `<p>A <b>rock physics template</b> (Ødegaard and Avseth 2004): acoustic impedance against Vp/Vs. Lines are physics models: <b>friable sand</b> (grain contacts only, Hertz-Mindlin and the soft-sand bound) and <b>contact cement</b> (Dvorkin and Nur 1996, quartz at the contacts), each with brine, oil or gas by Gassmann. Gas pulls a sand down and left; cement pushes it right.</p>
      <p><b>Cementation</b> (all FORCE wells pooled, ${P.valid_samples ?? "–"} clean high-porosity sand samples in ${P.valid_wells ?? "–"} wells): cement index ${ct.median_cool ?? "–"} at ≤ ${ct.cool_C ?? 70} °C vs <b>${ct.median_hot ?? "–"}</b> at ≥ ${ct.hot_C ?? 90} °C, difference ${ct.hot_minus_cool ?? "–"} (90 % ${ct.p05 ?? "–"} to ${ct.p95 ?? "–"}, whole wells resampled) ${verdict(ct)}. Rule R-RPT-CEMENT: quartz cement from about 70-80 °C.</p>
      <p><b>Fluid</b>: ${ft.verdict === "not_testable" ? `not testable: ${esc(ft.why || "")}.` : `HC well-units ${ft.median_dai_hc} vs dry ${ft.median_dai_dry}, AUC ${ft.auc_softer_means_hc} ${verdict(ft)}.`} Sonic logs read the invaded zone near the hole, so oil is muted; gas shows most.</p>
      <p class="tip">Bands of 70 and 90 °C were set from the theory before the test. Mineral and fluid moduli are textbook values; density porosity assumes brine. ${D.report.valid_samples} valid samples in this region (${D.report.validity ? `porosity ${D.report.validity.phi.join("-")}, clay < ${D.report.validity.clay_max}` : ""}); tight and shaly sands fall below the friable line, outside the models.</p>`, true);
    sec("R", "r-t", "Cement index by temperature (pooled)", `<table style="font-size:12px"><tr><th>T °C<th class=r>samples<th class=r>wells<th class=r>cement<th class=r>porosity</tr>${(P.cement_vs_temperature || []).map((b) => `<tr><td>${esc(b.T)}<td class=r>${b.n}<td class=r>${b.wells}<td class=r>${b.cement}<td class=r>${b.phi}</tr>`).join("")}</table>`, true);
    if (ablation?.main) {
      const fmt = (c) => `${f2(c.rmse_pp.fixed_density)} / ${f2(c.rmse_pp.raw_logs)} / ${f2(c.rmse_pp.raw_plus_physics)}`;
      const { main, template_sand: sand } = ablation;
      sec("R", "r-core", "Do physics features improve core porosity?", `<p><b>Research only. Does not feed production probabilities.</b></p>
        <p>Held-out RMSE (porosity points): fixed quartz/brine density / raw logs / same logs + physics.</p>
        <p><b>Measured sonic:</b> ${fmt(main)} · ${main.rows.toLocaleString()} plugs across ${main.wells} wells. Paired 90% gain interval: ${main.gain_block_bootstrap_90_pp.map((v) => f2(v)).join(" to ")} pp.</p>
        <p><b>Template sand:</b> ${sand.rmse_pp ? `${fmt(sand)} · ${sand.rows} plugs in ${sand.wells} wells.` : "not enough wells to score."}</p>
        <p class="tip">Same rows within each comparison; 40 km blocked whole wells. RealPore © GeoProvider (CC BY 4.0). <a href="api/provenance/rock-porosity" target="_blank" rel="noopener">Comparison receipt</a></p>`, true);
    } else {
      sec("R", "r-core", "Do physics features improve core porosity?", '<p class="tip">Local core-porosity comparison receipt unavailable.</p>', true);
    }
    const draw = async () => { const p = D.points, k = p.ai.map((_, i) => i).filter((i) => !st.only || p.valid[i]), [ct_, lo, hi] = COLS[st.col];
      const tr = D.template.filter((l) => l.clay === 0 && st.lines.has(l.model + "|" + l.fluid)).map((l) => ({ type: "scatter", mode: "lines", x: l.ai, y: l.vpvs, name: `${l.model}, ${l.fluid}`, text: l.phi.map((f) => `porosity ${(f * 100).toFixed(0)} %`),
        line: { color: RPTC[l.fluid], width: 2.5, dash: l.model === "friable sand" ? "dot" : "solid" }, hovertemplate: "%{text}<br>AI %{x:.2f}, Vp/Vs %{y:.2f}<extra>%{fullData.name}</extra>" }));
      tr.push({ type: "scattergl", mode: "markers", name: "FORCE samples", x: k.map((i) => p.ai[i]), y: k.map((i) => p.vpvs[i]), customdata: k.map((i) => [p.wellbore[i], p.unit[i], p.tvdss[i], p.phi[i], p.T[i], p.cement[i]]),
        marker: { size: 4, opacity: 0.6, color: k.map((i) => p[st.col][i]), cmin: lo, cmax: hi, colorscale: "Viridis", showscale: true, colorbar: { title: { text: ct_ }, thickness: 10, len: 0.6 } },
        hovertemplate: "%{customdata[0]} · %{customdata[1]}<br>%{customdata[2]:.0f} m TVDSS, porosity %{customdata[3]:.2f}, %{customdata[4]:.0f} °C<br>cement index %{customdata[5]:.2f}<extra></extra>" });
      await plot($("#pr"), tr, { margin: { l: 60, r: 20, t: 10, b: 50 }, xaxis: { title: "Acoustic impedance (km/s · g/cm³)", gridcolor: css("--rule") }, yaxis: { title: "Vp/Vs (ratio of P- to S-wave velocity)", range: [1.4, 3.2], gridcolor: css("--rule") }, legend: { orientation: "h", y: -0.18 } }); };
    $("#r-r").onchange = (e) => { location.hash = "rpt/" + e.target.value; }; $("#r-c").onchange = (e) => { st.col = e.target.value; draw(); }; $("#r-o").onchange = (e) => { st.only = e.target.checked; draw(); };
    $("#r-l").onchange = (e) => { const n = e.target.dataset.ln; if (!n) return; e.target.checked ? st.lines.add(n) : st.lines.delete(n); draw(); };
    REDRAW.scene = draw; await draw();
  },

  // ---- P12: what the model's untested constants change (sensitivity), the inputs refitted per fold, and the coefficient uncertainty
  async sensitivity(_, live) {
    const R = await api("earth/sensitivity"); const v = (x) => (Array.isArray(x) ? x.join(" / ") : x == null ? "–" : typeof x === "number" ? (Math.abs(x) >= 100 ? Math.round(x).toLocaleString() : x) : esc(String(x)));
    if (!live()) return;
    doc(`<h1>Sensitivity and checks</h1><p class="lead">Every constant the model uses without a data test of its own, set low and high with everything else fixed. <b>Matters</b> marks a constant that moves a held-out gain by more than 0.02, flips a rule verdict, changes a capacity by more than a quarter, or reorders the support. Units are in each row.</p>
      ${R.map((g) => `<h2>${esc(g.title)}</h2>
        <table style="font-size:13px"><tr><th>constant<th>values (low / used / high)<th>what it changes<th class=r>low<th class=r>used<th class=r>high<th></tr>
        ${g.rows.map((r) => r.error ? `<tr><td>${esc(r.constant)}<td colspan=6 class="tip">failed: ${esc(r.error)}</tr>` : `<tr><td>${esc(r.constant)}<td>${v(r.values)}<td>${esc(r.result)}<td class=r>${v(r.low)}<td class=r><b>${v(r.base)}</b><td class=r>${v(r.high)}<td>${r.matters ? tag("warnc", "matters") : tag("ok", "robust")}</tr>`).join("")}</table>
        <h3>Inputs refitted inside each fold, and the coefficient uncertainty</h3>
        <table style="font-size:13px"><tr><th>target<th>inputs refitted<th class=r>held-out gain, shared fit<th class=r>refitted per fold<th class=r>difference<th class=r>90% range, inputs only<th class=r>inputs + coefficients</tr>
        ${Object.entries(g.checks).map(([t, c]) => `<tr><td>${esc(t.replace(/_/g, " "))}<td>${esc((c.refit?.refit_inputs || []).join(", ") || "none")}<td class=r>${v(c.refit?.gain_shared_fit)}<td class=r>${v(c.refit?.gain_refit_per_fold)}<td class=r>${v(c.refit?.difference)}<td class=r>${c.range90 ? pct(c.range90.inputs_only) : "–"}<td class=r>${c.range90 ? pct(c.range90.inputs_and_coefficients) : "–"}</tr>`).join("")}</table>`).join("") || '<p class="tip">Not computed yet: EARTH_REGION=&lt;region&gt; python -m se.earth.sensitivity</p>'}
      <p class="tip">Gains are deviance gains over the base rate on held-out 40 km blocks (0 = no better than the base rate). Capacities in Mt CO2 (P50 of the region). 90% range = median over cells of p95 - p05, in probability points. PLAN P12, LOG L078.</p>`);
  },

  async scene(_, live) {
    const [fl, SV] = await Promise.all([api("formations3d"), api("seismic/surveys")]);
    if (!live()) return;
    const want = ["NORDLAND GP", "ROGALAND GP", "SELE FM", "HORDALAND GP"].filter((x) => fl.some((f) => f.name === x)).slice(0, 3), w = W();
    const spatial = LAYERS.find((l) => l.name === "spatial"), LN = {};
    const depthPreviewNote = "The inspector shows survey two-way time. The 3D overlay assumes a sea-level zero and one average velocity; it does not apply a seabed pick or a calibrated well tie.";
    const regions = { "58,62": "North Sea", "0,90": "Whole shelf", "62,69": "Norwegian Sea", "69,90": "Barents Sea" };
    const st = { reg: "58,62", sel: new Set(want.length ? want : fl.slice(0, 2).map((f) => f.name)), ex: 12, op: 0.5, wells: true, surf: true, box: true, map: true, ref: "rig", hs: null, cls: [true, true, true, true, true], kinds: { hot: true, cold: true }, seq: 0, spatial: spatial?.status === "helps" && spatial.on_by_default, res: 0.15, hov: null, focus: null, sv: { id: "", axis: "inline", pos: 0.5, v: 2.0, gain: 1, base: "", foot: true, cu: null, ck: "" } };
    let S = null;
    const wellName = (unit) => unit.split(" | ")[0];
    const desk = stage2('<div class="fill" id="p3"></div>', () => ({
      target: META.title.slice(0, 120), definition: META.target_text.slice(0, 500), region: regions[st.reg],
      formations: [...st.sel], neighbours: st.spatial, depth_reference: st.ref, seismic_survey: st.sv.id,
      interval: st.focus ? { wellbore: wellName(st.focus.unit), unit: st.focus.unit, top_md: st.focus.top, base_md: st.focus.bot, hits: st.focus.green, trials: st.focus.rows } : null,
    }));
    sec("L", "data", "Data", `<div class="row"><label>Region <select id="reg"><option value="58,62">North Sea (58–62°N)</option><option value="0,90">whole shelf (small)</option><option value="62,69">Norwegian Sea (62–69°N)</option><option value="69,90">Barents Sea (>69°N)</option></select></label></div>
      <div class="row"><label>Depth measured from <select id="ref"><option value="rig">rig floor (as recorded)</option><option value="sea">sea level</option><option value="bed">seabed</option></select></label></div>
<p class="tip" style="margin:2px 0">Formations (up to ${MAXF}; each one adds a sheet and its sticks) · <button class="lnk" id="f-none" type="button">none</button> · <button class="lnk" id="f-top" type="button">largest 8</button></p><div id="fl" style="max-height:220px;overflow:auto">${fl.map((f, i) => `<label class="chk lay" data-hl="${esc(f.name)}"><input type="checkbox" data-f="${esc(f.name)}" ${st.sel.has(f.name) ? "checked" : ""}>${swatch(LAYC[i % LAYC.length])} ${esc(f.name)} <span class="tip">${f.wells}</span></label>`).join("")}</div><p class="tip" style="margin:2px 0">Point at a formation to pick out its sheet in its colour.</p>`, true);
    sec("L", "display", "Display", `${palUI()}
      <div class="row"><label class="chk"><input type="checkbox" id="cw" checked> wells</label><label class="chk"><input type="checkbox" id="cs" checked> estimate sheets</label><label class="chk"><input type="checkbox" id="cb" checked> unusual areas</label><label class="chk"><input type="checkbox" id="cm" checked> coast and grid</label></div>
      <div class="row"><label class="chk" title="${esc(spatial ? evTip(spatial) : "")}"><input type="checkbox" id="c-sp" ${st.spatial ? "checked" : ""} ${spatial?.built ? "" : "disabled"}> neighbour evidence ${tag(spatial?.status || "not_built", STATUS_WORDS[spatial?.status || "not_built"])}</label></div>
      <div class="row"><label>Estimate detail <select id="c-res"><option value="0.15">normal (0.15°)</option><option value="0.05">fine (0.05°, GPU worker)</option></select></label></div>
      <div class="row"><button class="btn" id="v-top" title="look straight down, like a map">Top view</button> <button class="btn" id="v-reset">Reset view</button></div>
      <div class="row"><label class="chk">depth stretch <input type="range" id="ex" min="1" max="40" value="12"> <span id="exv">12×</span></label></div><div class="row"><label class="chk">sheet opacity <input type="range" id="op" min="10" max="100" value="50"></label></div>`, true);
    const focusPanel = sec("R", "focus", "Evidence in this view", `<p><b>${esc(META.title)}</b>. ${esc(META.target_text)}</p><p class="tip">Observed results and model estimates are separate. Seismic is displayed for inspection, not used in the estimate.</p><div id="focusbody"></div><p><a href="#validation">How well does the model predict?</a></p>`, true);
    const pick = (w) => {
      st.focus = w || null;
      $("#focusbody").innerHTML = w ? `<p><b>${esc(w.unit)}</b><br>${w.top.toFixed(0)}–${w.bot.toFixed(0)} m MD · ${w.rows ? `${w.green} of ${w.rows} recorded trials` : "no eligible records"}</p><p><a href="#unit/${encodeURIComponent(w.unit)}">Interval evidence</a> · <button type="button" class="lnk" id="focus-ask">Ask Strata Desk</button> · <button type="button" class="lnk" id="focus-clear">Clear</button></p>`
        : '<p class="tip">Click a well stick to inspect its interval, or use <a href="#units">the units table</a>.</p>';
      if (w) {
        $("#focus-ask").onclick = () => desk.open("What is known about this well interval, and what is missing?");
        $("#focus-clear").onclick = () => pick(null);
      }
      desk.sync();
    };
    pick(null);
    sec("R", "key", "Colour key: what the colours mean", '<div id="keybody"><p class="tip">loading…</p></div>', true);
    sec("R", "areas", "Unusual areas", '<p class="tip">20 km windows whose rate differs from the formation. Ranked by chance after correcting for the number of windows tested. Click to fly there.</p><div id="hs"></div>', true);
    sec("R", "guide", "What you are looking at", `<p><b>What the percentages mean.</b> A stick shows an <i>observed</i> share: successes ÷ trials in that interval (${esc(w.hit)} ÷ ${esc(w.rows)}). A sheet shows the <i>model estimate</i> of the same share. With neighbour evidence off, the sheet colour is based on the formation or group alone. A box compares the share in a 20 km window with the formation average.</p><p><b>Sticks</b>: one per <i>well × formation interval</i>, not per whole well. Each is drawn at the well's surface position, straight down, over the depth range where that well passes through the formation. Real wells may deviate, so deeper parts can lie off to the side. Colour = share of ${esc(w.rows)} that ${esc(w.hit)} (grey: too few to say).</p><p><b>Sheets</b> use smoothed interval mid-depths for their shape; these are not mapped geological horizons. They are masked beyond the well-data reach.</p>
      <p><b>Boxes</b> mark 20 km areas that are unusually high (orange) or low (purple) vs the formation.</p><p><b>Depth</b> is measured <i>along the well</i> (not vertical) from the reference you choose: the rig floor (about 25 m above sea level; how Sodir records it), sea level, or the seabed (rig floor height + water depth). The water column is empty space above the seabed. Grid and coast are drawn at depth 0. <b>Top view</b> gives the map-like picture.</p>`, false);
    sec("L", "seis", "Seismic", SV.length ? `<p class="tip" style="margin:0 0 6px">Open seismic over the North Sea. Vertical section (curtain) along one line, drawn where it really is.</p>
      <div class="row"><label>Survey <select id="sv-id"><option value="">none</option>${SV.map((x) => `<option value="${x.id}">${esc(x.name)}</option>`).join("")}</select></label></div>
      <div class="row"><label class="chk"><input type="radio" name="sv-ax" value="inline" checked> inline</label><label class="chk"><input type="radio" name="sv-ax" value="crossline"> crossline</label><span id="sv-lab" class="tip"></span></div>
      <div class="row"><input type="range" id="sv-pos" min="0" max="1" step="0.005" value="0.5" style="width:100%"></div>
      <div class="row"><label class="chk">velocity <input type="range" id="sv-v" min="1.6" max="2.8" step="0.05" value="2.0"> <span id="sv-vv">2.0 km/s</span></label></div>
      <div class="row"><label class="chk">gain <input type="range" id="sv-g" min="0.5" max="6" step="0.1" value="1"></label></div>
      <div class="row"><label>Difference against <select id="sv-base"><option value="">none (amplitude)</option></select></label><span class="tip">same processing only</span></div>
      <div class="row"><label class="chk"><input type="checkbox" id="sv-foot" checked> survey outlines</label> <button class="btn" id="sv-fly">Fly to survey</button></div>
      <div class="row"><label class="chk" title="Smeaheia Key Horizons 2010 research tie (L058). Not independently validated."><input type="checkbox" id="sv-tied"> 2010 tied horizons (research)</label></div>
      <div class="row"><button class="btn on" id="sv-inspect" title="Open a side pane with a 2D section or time slice and a 3D cube of this survey">Inspect seismic ▸</button></div>
      <p class="tip" id="svnote" style="margin:4px 0">${depthPreviewNote}</p>
      <p class="tip" style="margin:4px 0">${[...new Set(SV.map((x) => x.credit))].map(esc).join("<br>")}</p>` : '<p class="tip">No seismic indexed yet (backend: python -m se.seismic.index).</p>', false);
    const refLab = { rig: "Depth below rig floor (m, along well)", sea: "Depth below sea level (m, along well)", bed: "Depth below seabed (m, along well)" };
    const dz = (v, o) => (st.ref === "rig" ? v : st.ref === "sea" ? v - (o.kb ?? 25) : v - (o.kb ?? 25) - (o.wd ?? 0));
    const draw = async () => {
      if (!live()) return;
      desk.sync();
      const my = ++st.seq, T0 = tick(), q = [...st.sel].join(","), active = () => live() && my === st.seq;
      if (!q) { pick(null); plot($("#p3"), [], {}); $("#hs").innerHTML = '<p class="tip">Pick a formation.</p>'; return; }
      const [la, lb] = st.reg.split(","); const T1 = tick(), key = [TARGET, q, la, lb, st.spatial, st.res].join("|");
      if (!S || S._key !== key) { const got = await api("scene", { formations: q, lat_min: la, lat_max: lb, spatial: st.spatial, res: st.res }); if (!active()) return; got._key = key; S = got; }
      if (st.focus && !S.wells.some((w) => w.unit === st.focus.unit)) pick(null);
      const T2 = tick(); const tr = [], Wl = S.wells, ex = st.ex;
      const sdepth = (s) => (st.ref === "bed" ? s.depth_sb : s.depth.map((r) => r.map((v) => (v == null ? null : st.ref === "sea" ? v - s.kb : v))));
      const xs = Wl.map((w) => w.x).concat(...S.surfaces.map((s) => s.x.flat())), ys = Wl.map((w) => w.y).concat(...S.surfaces.map((s) => s.y.flat()));
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), zmax = Math.max(...Wl.map((w) => dz(w.bot, w)), 500);
      if (st.surf) S.surfaces.forEach((s, i) => tr.push({ type: "surface", x: s.x, y: s.y, z: sdepth(s).map((r) => r.map((v) => (v == null ? null : -v))), surfacecolor: s.rate, cmin: CMIN, cmax: CMAX, opacity: st.op, showscale: i === 0, name: s.formation, meta: { hl: s.formation },
        colorscale: pal().stops, colorbar: { title: "model estimate", orientation: "h", len: 0.28, thickness: 9, x: 0.5, y: 0.1, tickformat: ".0%" }, hovertemplate: `<b>${esc(s.formation)}</b> (estimate sheet)<br>Smoothed interval mid-depth: %{z:.0f} m<br>Model estimate: <b>%{surfacecolor:.1%}</b> of ${esc(w.rows)} ${esc(w.hit)}<br>${st.spatial ? "Formation + neighbouring wells" : "Formation/group only"} · not an observation<extra></extra>` }));
      if (st.wells) { const rg = CMAX - CMIN, c1 = CMIN + 0.1 * rg, c2 = CMIN + 0.4 * rg, P = (x) => pct(x, x < 0.1 ? 1 : 0), pb = pal().bins, bins = [["observed: too few to judge", css("--mut")], [`observed under ${P(c1)}`, pb[0]], [`observed ${P(c1)} to ${P(c2)}`, pb[1]], [`observed ${P(c2)} to ${P(CMAX)}`, pb[2]], [`observed over ${P(CMAX)}`, pb[3]]], MINN = TARGET === "green_clay" ? 3 : 1, bi = (w) => (w.rows < MINN || w.obs == null ? 0 : w.obs < c1 ? 1 : w.obs < c2 ? 2 : w.obs < CMAX ? 3 : 4);
        STICKS = bins.map(([nm, col], b) => [nm, col, Wl.filter((w) => bi(w) === b).length]);
        bins.forEach(([nm, col], b) => { const g = Wl.filter((w) => bi(w) === b); if (!g.length) return; const x = [], y = [], z = [], t = [], units = [];
          g.forEach((w) => { const lab = `<b>${esc(w.unit)}</b><br>Interval ${dz(w.top, w).toFixed(0)}–${dz(w.bot, w).toFixed(0)} m ${st.ref === "rig" ? "below the rig floor" : st.ref === "sea" ? "below sea level" : "below the seabed"} (along the well)<br>Observed: <b>${w.green} of ${w.rows}</b> ${esc(W().rows)} ${esc(W().hit)}${w.obs == null || w.rows < 1 ? "" : " = <b>" + pct(w.obs) + "</b>"}${w.rows < 3 && w.rows > 0 ? "<br>(too few to judge)" : w.rows === 0 ? "<br>(none recorded here)" : ""}`; x.push(w.x, w.x, null); y.push(w.y, w.y, null); z.push(-dz(w.top, w), -dz(w.bot, w), null); t.push(lab, lab, ""); units.push(w.unit, w.unit, null); });
          tr.push({ type: "scatter3d", mode: "lines", x, y, z, text: t, customdata: units, hoverinfo: "text", line: { color: col, width: b === 0 ? 2 : 5 }, meta: { cls: b }, visible: st.cls[b] !== false, name: nm + " (" + g.length + ")" }); }); }
      const hs = S.hotspots.filter((h) => st.kinds[h.kind]);
      if (st.box) hs.forEach((h) => { const r = h.radius_km, c = h.kind === "hot" ? css("--hot") : css("--cold"), sel = st.hs === h.id, a = -dz(h.top, h), b = -dz(h.bot, h);
        tr.push({ type: "mesh3d", meta: h.id, x: [h.x - r, h.x + r, h.x + r, h.x - r, h.x - r, h.x + r, h.x + r, h.x - r], y: [h.y - r, h.y - r, h.y + r, h.y + r, h.y - r, h.y - r, h.y + r, h.y + r], z: [a, a, a, a, b, b, b, b], i: [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3], j: [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 0, 4], k: [2, 3, 6, 7, 5, 4, 6, 5, 7, 6, 4, 7], color: c, opacity: sel ? 0.45 : 0.2, flatshading: true, name: h.id, hoverinfo: "text", text: `<b>Area #${hs.indexOf(h) + 1}: ${h.kind === "hot" ? "higher" : "lower"} than the ${esc(h.formation)} average</b><br>${esc(h.text).replace(/(.{70}\s)/g, "$1<br>")}`, showlegend: false }); });
      if (st.box && hs.length) tr.push({ type: "scatter3d", mode: "text", x: hs.map((h) => h.x), y: hs.map((h) => h.y), z: hs.map((h) => -dz(h.top, h)), text: hs.map((_, i) => "#" + (i + 1)), textfont: { size: 15, color: css("--ink") }, hoverinfo: "skip", showlegend: false });
      const [lat0, lat1] = [Number(la), Number(lb)];
      if (SV.length && st.sv.foot) { const sites = {}; SV.filter((x) => x.footprint.some((p) => p[0] >= lat0 && p[0] <= lat1)).forEach((x) => (sites[x.dataset + x.centre.map((c) => c.toFixed(1)).join()] ||= []).push(x));  // one outline per site, not one per vintage
        Object.values(sites).forEach((g) => { const x = g[0], ring = [...x.footprint, x.footprint[0]], nm = g.length > 1 ? `${x.dataset === "sleipner" ? "Sleipner 4D" : x.dataset} (${g.length} vintages)` : x.name;
          tr.push({ type: "scatter3d", mode: "lines", x: ring.map((p) => KMX(p[1])), y: ring.map((p) => KMY(p[0])), z: ring.map(() => 0), line: { color: css("--ink"), width: 4 }, hoverinfo: "text", text: ring.map(() => `${nm}<br>${x.wells_inside.length} of our wells inside<br>${x.credit}`), showlegend: false });
          tr.push({ type: "scatter3d", mode: "text", x: [KMX(x.centre[1])], y: [KMY(x.centre[0])], z: [0], text: [nm], textfont: { size: 11, color: css("--ink") }, hoverinfo: "skip", showlegend: false }); }); }
      const sv = st.sv, note = $("#svnote");
      if (note) { note.textContent = depthPreviewNote; note.style.color = ""; }
      if (sv.id && st.ref !== "bed") { const sid = sv.id; if (!LN[sid]) LN[sid] = await api("seismic/lines", { survey: sid }); if (!active()) return; const arr = LN[sid][sv.axis], idx = arr[Math.round(sv.pos * (arr.length - 1))], ck = [sid, sv.axis, idx, sv.base].join("|");
        $("#sv-lab").textContent = `${sv.axis} ${idx}`; if (sv.ck !== ck) { const cu = await api("seismic/curtain", { survey: sid, axis: sv.axis, index: idx, ...(sv.base ? { baseline: sv.base } : {}) }); if (!active()) return; sv.cu = cu; sv.ck = ck; }
        const cu = sv.cu, off = st.ref === "rig" ? 25 : 0, zz = cu.t_ms.map((t) => -((t / 2) * sv.v + off)), g = sv.gain;
        tr.push({ type: "surface", x: cu.t_ms.map(() => cu.x), y: cu.t_ms.map(() => cu.y), z: zz.map((z) => cu.x.map(() => z)), customdata: cu.t_ms.map((t) => cu.x.map(() => t)), surfacecolor: cu.amp.map((r) => r.map((v) => v / 127)), cmin: -1 / g, cmax: 1 / g, showscale: false, opacity: 1, name: sv.id, ...(IN.clear ? { opacityscale: OPQ } : {}),
          colorscale: [[0, "#2c5aa0"], [0.5, "#f7f7f7"], [1, "#b2182b"]], hovertemplate: `${esc(cu.survey)} ${cu.axis} ${cu.index}<br>Survey two-way time: %{customdata:.0f} ms<br>Scene z: %{z:.0f} m (uncalibrated)<extra></extra>`, lighting: { ambient: 1, diffuse: 0 } }); }
      else if (sv.id && note) { note.textContent = "Switch the depth reference to rig floor or sea level for the uncalibrated preview. The inspector still shows survey time. Seabed placement needs a calibrated tie."; note.style.color = css("--warn"); }
      if (st.tied) { const T = TIED || (TIED = await api("earth/tied", { step: 2 })); if (!active()) return; const off = st.ref === "rig" ? 25 : 0;
        const X = T.lon.map((r, a) => r.map((lo, b) => (lo == null ? null : KMX(lo)))), Y = T.lat.map((r) => r.map((la) => (la == null ? null : KMY(la)))), HC = ["#1b9e77", "#d95f02", "#7570b3"];
        if (st.ref !== "bed") T.surfaces.forEach((h, i) => tr.push({ type: "surface", x: X, y: Y, z: h.z.map((r) => r.map((v) => (v == null ? null : -(v + off)))), surfacecolor: h.z.map((r) => r.map(() => 1)), colorscale: [[0, HC[i % 3]], [1, HC[i % 3]]], showscale: false, opacity: 0.6,
          name: h.name + " (tied seismic)", customdata: h.sd, hovertemplate: `${esc(h.name)}: tied seismic horizon<br>%{z:.0f} m (± %{customdata:.0f} m)<extra>Smeaheia, Equinor and Gassnova</extra>`, lighting: { ambient: 0.85, diffuse: 0.3 } })); }
      if (st.map) tr.unshift(...(await mapLines({ x0, x1, y0, y1 })));
      // Axis ranges are fixed from the data of the chosen formations (not from whatever is switched on), so toggling the coast, seismic or sheets never rescales or moves the scene.
      const mg = 80, rx = [x0 - mg, x1 + mg], ry = [y0 - mg, y1 + mg], seisDeep = sv.id && st.ref !== "bed" && sv.cu ? (Math.max(...sv.cu.t_ms) / 2) * sv.v + (st.ref === "rig" ? 25 : 0) : 0, zlow = Math.max(zmax, seisDeep) * 1.03, zr = [-zlow, zlow * 0.02];
      const ar = { x: 1, y: (ry[1] - ry[0]) / (rx[1] - rx[0]), z: ((zr[1] - zr[0]) / 1000 / (rx[1] - rx[0])) * ex }; S._g = { x0: rx[0], x1: rx[1], y0: ry[0], y1: ry[1], zr, ar }; st._d = { x0, x1, y0, y1 }; const zt = [0, 500, 1000, 2000, 3000, 4000, 5000, 6000].filter((v) => v <= zlow);
      const axs = (t, range) => ({ title: t, range, autorange: false, gridcolor: css("--rule"), color: css("--mut"), backgroundcolor: "rgba(0,0,0,0)", showbackground: false });
      // the camera: the view you have right now is read back from the live scene and passed again, so a redraw never moves it; only a new region starts from the default view
      let liveCamera = null; try { liveCamera = $("#p3")?._fullLayout?.scene?._scene?.getCamera?.() || null; } catch {}
      const cam = st.camFor !== st.reg ? st.cam || { eye: { x: 1.4, y: -1.5, z: 0.8 } } : liveCamera || st.cam || { eye: { x: 1.4, y: -1.5, z: 0.8 } };
      if (!active()) return; const T3 = tick(); if ($("#p3")) $("#p3")._hl0 = null; await plot3($("#p3"), tr, { uirevision: st.reg, margin: { l: 0, r: 0, t: 0, b: 0 }, legend: { orientation: "h", x: 0.3, y: 0.02, bgcolor: "rgba(0,0,0,0)", font: { size: 11 } }, scene: { uirevision: st.reg, aspectmode: "manual", aspectratio: ar, camera: cam, xaxis: axs("East (km)", rx), yaxis: axs("North (km)", ry), zaxis: { ...axs(refLab[st.ref], zr), tickvals: zt.map((v) => -v), ticktext: zt.map(String) } } });
      if (!active()) return;
      st.camFor = st.reg; st.mini?.(); const pw = $(".plotwrap"); if (pw) REDRAW.k = pw.clientWidth + "x" + pw.clientHeight;
      if (PERF) console.log("PERF3D " + JSON.stringify({ api_ms: Math.round(T2 - T1), build_traces_ms: Math.round(T3 - T2), plotly_ms: Math.round(tick() - T3), points: tr.reduce((n, d) => n + (d.x ? d.x.flat().length : 0), 0), traces: tr.length, wells: Wl.length }));
      $("#hs").innerHTML = hs.length ? hs.map((h) => `<div class="hs ${st.hs === h.id ? "sel" : ""}" data-h="${esc(h.id)}"><b>#${hs.indexOf(h) + 1} ${esc(h.formation)}</b> · ${tag(h.kind, h.kind === "hot" ? "higher than usual" : "lower than usual")} · ${h.p_adj < 0.05 ? tag("ok", "survives correction") : tag("warnc", "exploratory")}<p><b>${pct(h.rate)}</b> of ${h.rows} ${W().rows} ${W().hit}, vs <b>${pct(h.formation_rate)}</b> across ${esc(h.formation)} (${h.lift}× ${h.kind === "hot" ? "higher" : "lower"}); ${h.wells} wells in a 20 km window</p><p>${esc(h.text)}</p></div>`).join("") : '<p class="tip">No window here has enough wells and trials to test.</p>';
      const kb = $("#keybody"); if (kb) kb.innerHTML = `<p><b>A stick</b> (the vertical bars) is <b>one well's interval inside one formation</b>: it starts where the well enters the formation and ends where it leaves it. Its colour is the <b>observed share</b>: how many of the ${esc(W().rows)} recorded there ${esc(W().hit)}, divided by all of them.</p>
        <div class="row" style="margin:2px 0"><span class="tip">show on the map:</span> <a data-all="1" style="cursor:pointer">all</a> · <a data-all="0" style="cursor:pointer">none</a> <span class="tip">· click a row to show or hide it, “only” isolates it, hover to find it</span></div>
        <table style="font-size:12px">${STICKS.map(([nm, col, n], b) => `<tr class="kr" data-c="${b}" style="cursor:pointer"><td style="width:22px"><input type="checkbox" ${st.cls[b] !== false ? "checked" : ""}><td style="width:34px"><span style="display:inline-block;width:26px;height:6px;background:${col}"></span><td>${esc(nm)}<td class="r">${n}<td><a data-only="${b}" style="cursor:pointer">only</a>`).join("")}</table>
        <p class="tip" style="margin:4px 0">Grey: fewer than ${TARGET === "green_clay" ? 3 : 1} record${TARGET === "green_clay" ? "s" : ""}, too few to say. Neighbouring sticks differ because they are different wells: the rock changes, and wells describe rock with different detail.</p>
        <p><b>A sheet</b> shows the estimated share (${st.spatial ? "formation/group plus neighbouring wells" : "formation/group only"}). Where it is drawn depends on well coverage; its shape is not a geological horizon.</p><div class="legend"><span>${pct(CMIN, CMIN < 0.1 ? 1 : 0)}</span><div class="ramp" style="background:${rampCss()}"></div><span>${pct(CMAX, CMAX < 0.1 ? 1 : 0)}+</span></div>
        <p><b>A box</b> marks a 20 km area whose share is higher or lower than the formation average. #n matches the list on the right.</p>
        <div class="row" style="margin:2px 0"><label class="chk"><input type="checkbox" data-k="hot" ${st.kinds.hot ? "checked" : ""}> <span class="hot"><b>higher</b></span> (orange)</label><label class="chk"><input type="checkbox" data-k="cold" ${st.kinds.cold ? "checked" : ""}> <span class="cold"><b>lower</b></span> (purple)</label></div>`;
      const gd = $("#p3"); gd.removeAllListeners?.("plotly_hover"); gd.removeAllListeners?.("plotly_unhover"); gd.removeAllListeners?.("plotly_relayout"); gd.removeAllListeners?.("plotly_relayouting"); gd.removeAllListeners?.("plotly_click");
      gd.on("plotly_click", (e) => {
        const p = e.points?.[0], unit = p?.customdata ?? p?.data?.customdata?.[p.pointNumber];
        const w = typeof unit === "string" && S.wells.find((x) => x.unit === unit);
        if (w) { pick(w); focusPanel.classList.remove("fold"); }
      });
      gd.on("plotly_hover", (e) => { const m = e.points?.[0]?.data?.meta; if (m) hl(m, true); }); gd.on("plotly_unhover", () => hl(null));
      const keepCam = (e) => { if (e["scene.camera"]) st.cam = e["scene.camera"]; else if (e["scene.camera.eye"]) st.cam = { ...(st.cam || {}), eye: e["scene.camera.eye"] }; };
      gd.on("plotly_relayout", keepCam); gd.on("plotly_relayouting", keepCam);  // also while dragging, so a redraw mid-drag keeps the view
    };
    // hover either the list entry or the box in 3D: both light up, the others fade
    const hl = (id, fromPlot) => { if (st.hov === (id || null)) return; st.hov = id || null; document.querySelectorAll(".hs").forEach((e) => e.classList.toggle("hov", !!id && e.dataset.h === id)); if (id && fromPlot) document.querySelector(`.hs[data-h="${CSS.escape(id)}"]`)?.scrollIntoView({ block: "nearest" });
      const gd = $("#p3"), idx = [], op = []; (gd.data || []).forEach((d, i) => { if (d.type === "mesh3d" && d.meta) { idx.push(i); op.push(id ? (d.meta === id ? 0.65 : 0.05) : d.meta === st.hs ? 0.45 : 0.2); } }); if (idx.length) Plotly.restyle(gd, { opacity: op }, idx); };
    const fly = (id) => { const h = S?.hotspots.find((x) => x.id === id); if (!h) return; st.hs = id; const g = S._g, ar = g.ar, zc = -dz((h.top + h.bot) / 2, h); const c = { x: ((h.x - (g.x0 + g.x1) / 2) / (g.x1 - g.x0)) * ar.x, y: ((h.y - (g.y0 + g.y1) / 2) / (g.y1 - g.y0)) * ar.y, z: ((zc - (g.zr[0] + g.zr[1]) / 2) / (g.zr[1] - g.zr[0])) * ar.z };
      Plotly.relayout($("#p3"), { "scene.camera": { center: c, eye: { x: c.x + 0.5, y: c.y - 0.6, z: c.z + 0.35 } } }); document.querySelectorAll(".hs").forEach((e) => e.classList.toggle("sel", e.dataset.h === id)); };
    $("#hs").onclick = (e) => { const el = e.target.closest(".hs"); if (el) fly(el.dataset.h); };
    $("#hs").onmouseover = (e) => { const el = e.target.closest(".hs"); if (el) hl(el.dataset.h); }; $("#hs").onmouseleave = () => hl(null);
    document.querySelectorAll("[data-f]").forEach((c) => (c.onchange = () => {
      c.checked ? st.sel.add(c.dataset.f) : st.sel.delete(c.dataset.f);
      $$("[data-f]").forEach((e) => { e.disabled = !e.checked && st.sel.size >= MAXF; });
      draw();
    }));
    { const fi = new Map(fl.map((f, i) => [f.name, LAYC[i % LAYC.length]])); hoverLayers($("#fl"), () => $("#p3"), (n) => fi.get(n)); }
    const setF = (names) => { st.sel = new Set(names); $$("[data-f]").forEach((e) => { e.checked = st.sel.has(e.dataset.f); e.disabled = !e.checked && st.sel.size >= MAXF; }); draw(); };
    $("#f-none").onclick = () => setF([]); $("#f-top").onclick = () => setF($$("[data-f]").slice(0, 8).map((e) => e.dataset.f));  // the list is sorted by well count
    bindPal(() => later()); $("#reg").onchange = (e) => { st.reg = e.target.value; st.hs = null; st.cam = null; draw(); }; $("#ref").onchange = (e) => { st.ref = e.target.value; draw(); };
    for (const [id, k] of [["cw", "wells"], ["cs", "surf"], ["cb", "box"], ["cm", "map"]]) $("#" + id).onchange = (e) => { st[k] = e.target.checked; draw(); };
    $("#ex").oninput = (e) => { st.ex = +e.target.value; $("#exv").textContent = st.ex + "×"; if (S) { const g = S._g; g.ar.z = ((g.zr[1] - g.zr[0]) / 1000 / ((g.x1 - g.x0) || 1)) * st.ex; Plotly.relayout($("#p3"), { "scene.aspectratio": g.ar }); } };
    const later = (() => { let t; return () => { clearTimeout(t); t = setTimeout(draw, 90); }; })();  // coalesce a slider drag into one redraw
    // colour key as a filter: show or hide a stick class, isolate one, find one by hovering (restyle only: no redraw, no scene change)
    const stickIdx = () => { const idx = [], cls = []; ($("#p3").data || []).forEach((d, i) => { if (d.meta && typeof d.meta === "object" && "cls" in d.meta) { idx.push(i); cls.push(d.meta.cls); } }); return [idx, cls]; };
    const applyCls = () => { const [idx, cls] = stickIdx(); if (idx.length) Plotly.restyle($("#p3"), { visible: cls.map((c) => st.cls[c] !== false) }, idx); $$("#keybody [data-c]").forEach((r) => (r.querySelector("input").checked = st.cls[+r.dataset.c] !== false)); };
    const fadeCls = (b) => { const [idx, cls] = stickIdx(); if (idx.length) Plotly.restyle($("#p3"), { opacity: cls.map((c) => (b == null || c === b ? 1 : 0.1)) }, idx); };
    const KB = $("#keybody");
    KB.onclick = (e) => { const t = e.target, all = t.closest("[data-all]"), only = t.closest("[data-only]"), row = t.closest("[data-c]"), kind = t.closest("[data-k]");
      if (kind) { st.kinds[kind.dataset.k] = kind.checked; draw(); return; }
      if (all) { st.cls = st.cls.map(() => all.dataset.all === "1"); applyCls(); return; }
      if (only) { const c = +only.dataset.only, isolated = st.cls.every((v, i) => (i === c) === (v !== false)); st.cls = st.cls.map((_, i) => (isolated ? true : i === c)); applyCls(); return; }
      if (row) { const c = +row.dataset.c; st.cls[c] = st.cls[c] === false; applyCls(); } };
    KB.onmouseover = (e) => { const r = e.target.closest("[data-c]"); fadeCls(r ? +r.dataset.c : null); }; KB.onmouseleave = () => fadeCls(null);
    REDRAW.scene = later; REDRAW.insp = () => IN.el && $("#si3d") && $("#si3d").offsetWidth > 0 && inspectLater();
    $("#op").oninput = (e) => { st.op = +e.target.value / 100; later(); };
    $("#c-sp").onchange = (e) => { st.spatial = e.target.checked; draw(); }; $("#c-res").onchange = (e) => { st.res = +e.target.value; draw(); };
    $("#v-top").onclick = () => { st.cam = { eye: { x: 0, y: -0.0001, z: 2.4 }, up: { x: 0, y: 1, z: 0 }, center: { x: 0, y: 0, z: 0 } }; Plotly.relayout($("#p3"), { "scene.camera": st.cam }); };
    $("#v-reset").onclick = () => { st.cam = { eye: { x: 1.4, y: -1.5, z: 0.8 }, up: { x: 0, y: 0, z: 1 }, center: { x: 0, y: 0, z: 0 } }; Plotly.relayout($("#p3"), { "scene.camera": st.cam }); };
    if ($("#sv-id")) { const sv = st.sv; $("#sv-id").onchange = (e) => { sv.id = e.target.value; sv.base = ""; sv.ck = ""; const me = SV.find((x) => x.id === sv.id); $("#sv-base").innerHTML = '<option value="">none (amplitude)</option>' + SV.filter((x) => me && me.processing && x.id !== sv.id && x.processing === me.processing).map((x) => `<option value="${x.id}">${esc(x.name)}</option>`).join(""); draw(); };
      document.querySelectorAll('[name="sv-ax"]').forEach((r) => (r.onchange = (e) => { sv.axis = e.target.value; sv.ck = ""; draw(); })); $("#sv-pos").oninput = (e) => { sv.pos = +e.target.value; later(); };
      $("#sv-v").oninput = (e) => { sv.v = +e.target.value; $("#sv-vv").textContent = sv.v.toFixed(1) + " km/s"; later(); }; $("#sv-g").oninput = (e) => { sv.gain = +e.target.value; later(); }; $("#sv-base").onchange = (e) => { sv.base = e.target.value; sv.ck = ""; draw(); }; $("#sv-foot").onchange = (e) => { sv.foot = e.target.checked; draw(); }; $("#sv-tied").onchange = (e) => { st.tied = e.target.checked; draw(); };
      $("#sv-fly").onclick = () => { const x = SV.find((q) => q.id === sv.id) || SV[0]; if (!S?._g || !x) return; const g = S._g, ar = g.ar, cx = KMX(x.centre[1]), cy = KMY(x.centre[0]); const c = { x: ((cx - (g.x0 + g.x1) / 2) / (g.x1 - g.x0)) * ar.x, y: ((cy - (g.y0 + g.y1) / 2) / (g.y1 - g.y0)) * ar.y, z: ((-1000 - (g.zr[0] + g.zr[1]) / 2) / (g.zr[1] - g.zr[0])) * ar.z };
        Plotly.relayout($("#p3"), { "scene.camera": { center: c, eye: { x: c.x + 0.3, y: c.y - 0.35, z: c.z + 0.2 } } }); }; }

    const { IN, OPQ, inspectOpen, inspectClose, inspectLater } = seismicKit({ SV, LN, get sv() { return st.sv; }, later });
    // the box is the scene's real extent (its x and y axes, in the KMX/KMY frame), not the whole latitude band of the region
    const mini = () => { const d = st._d; if (!d) return; const lon = (x) => x / (111.32 * Math.cos((61 * Math.PI) / 180)) + 3, lat = (y) => y / 110.57 + 61, f = (v) => v.toFixed(1);
      minimap($(".plotwrap"), { lat: [lat(d.y0), lat(d.y1)], lon: [lon(d.x0), lon(d.x1)] }, `In view: ${regions[st.reg]}, ${f(lat(d.y0))}–${f(lat(d.y1))}°N, ${f(lon(d.x0))}–${f(lon(d.x1))}°E`); };
    st.mini = mini; await draw(); job();
  },

  async units() {
    doc(`<h1>Units</h1><p class="lead">One row is one ${esc(W().unit)}. <b>Trials</b>: ${esc(W().rows)} in it. <b>Successes</b>: how many ${esc(W().hit)}. <b>Observed</b> = successes / trials. <b>Estimate</b> = what the model expects. Click a row for the evidence behind its estimate.</p>
    <div class="row"><input type="search" id="q" placeholder="search well, e.g. 30/6"><select id="f"><option value="">all groups</option></select><select id="s"><option value="rate">sort by estimate</option><option value="observed">sort by observed</option><option value="rows">sort by trials</option></select></div><div class="row">${layerBox()}</div><table id="t"></table>`);
    (await api("formations")).forEach((f) => $("#f").insertAdjacentHTML("beforeend", `<option>${esc(f.name)}</option>`));
    const go = async () => { const u = await api("units", { q: $("#q").value, formation: $("#f").value, sort: $("#s").value, layers: useNow().join(",") }), mx = Math.max(...u.map((x) => x.rate || 0), 0.01);
      $("#t").innerHTML = "<tr><th>well<th>group<th class=r>depth m (MD)<th class=r>trials<th class=r>successes<th class=r>observed<th>estimate</tr>" + u.map((x) => `<tr class="click" data-u="${esc(x.unit)}"><td><b>${esc(x.wellbore)}</b><td>${esc(x.name)}<td class="r mono">${x.top}–${x.bot}<td class=r>${x.coverage}<td class=r>${x.n_green}<td class=r>${pct(x.observed)}<td><span class="track" style="display:inline-block;vertical-align:middle"><div class="bar" style="width:${100 * x.rate / mx}%"></div></span> ${pct(x.rate)}</tr>`).join(""); };
    $("#t").onclick = (e) => { const r = e.target.closest("tr[data-u]"); if (r) location.hash = "unit/" + encodeURIComponent(r.dataset.u); }; $("#q").oninput = go; $("#f").onchange = go; $("#s").onchange = go; bindLayers(go); await go();
  },

  async unit(id, live) {
    const draw = async () => { const u = await api("unit", { id, layers: useNow().join(",") }), P = u.estimate.parts, w = W(), names = { base: "Starting rate", strat: "Formation or group", spatial: "Nearby wells", logs: "Well logs", seismic: "Seismic" };
      if (!live()) return;
      doc(`<p><a href="#units">← all units</a></p><h1>${esc(u.wellbore)} <span class="muted">× ${esc(u.formation)}</span></h1><p class="lead">${esc(u.level.toLowerCase())}, ${u.top}–${u.bot} m measured depth below the rig floor · ${u.lat.toFixed(3)}° N, ${u.lon.toFixed(3)}° E</p>
      <div class="grid g3"><div><div class="num">${u.green_rows} of ${u.described_clay_rows}</div><div class="cap">${esc(w.rows)} ${esc(w.hit)} (observed ${pct(u.observed_rate)})</div></div><div><div class="num">${pct(u.estimate.rate)}</div><div class="cap">model estimate (${pct(u.validation_estimate)} with this well held out)</div></div></div>
      <div class="row">${layerBox()}</div>${u.labelled ? "" : '<div class="note warn"><b>Too little data</b>Not used for training; the estimate is shown for context.</div>'}
      <h2>Evidence, step by step</h2><p>Start from the overall rate, then add or subtract one term per kind of evidence (units: log-odds; right raises the estimate, left lowers it). The reason for each is in words.</p>${fig("wf", 260, "Contribution of each evidence layer to this unit's estimate.")}
      <table>${P.map((p) => `<tr><td><b>${names[p.layer] || p.layer}</b> ${p.status ? tag(p.status, STATUS_WORDS[p.status]) : ""}<td class="mono r">${p.llr == null ? "silent" : sg(p.llr, 2)}<td>${esc(p.why)}</tr>`).join("")}</table>
      <h2>Well-log medians in this interval</h2><p class="tip">GR gamma, RHOB density, NPHI neutron, PEF photoelectric, DTC sonic, RDEP resistivity (log10), DNSEP neutron–density separation. Only the green-clay target uses them.</p><table><tr>${Object.keys(u.logs).map((k) => `<th>${k}`).join("")}</tr><tr>${Object.values(u.logs).map((v) => `<td class="mono">${v ?? "–"}`).join("")}</tr></table>`);
      const used = P.filter((p) => p.llr != null); plot($("#wf"), [{ type: "waterfall", orientation: "h", y: used.map((p) => names[p.layer] || p.layer), x: used.map((p) => p.llr), measure: used.map((_, i) => (i === 0 ? "absolute" : "relative")), connector: { line: { color: css("--rule") } }, increasing: { marker: { color: css("--data") } }, decreasing: { marker: { color: css("--bad") } }, totals: { marker: { color: css("--mut") } }, text: used.map((p) => sg(p.llr, 2)), textposition: "outside" }],
        { xaxis: { title: "log-odds" }, yaxis: { autorange: "reversed" }, margin: { l: 150, r: 40, t: 10, b: 44 } }); bindLayers(draw); };
    await draw();
  },

  async data(_, live) {
    const cat = await api("catalog"), st = { t: null, f: [], x: null, y: "", agg: "mean", tab: "chart", off: 0 };
    if (!live()) return;
    doc(`<h1>Data</h1><p class="lead">What we hold, where it comes from, and every table of the Sodir FactPages register. Pick a table to chart a column, read rows or map wells. Clicking a bar adds a filter that every view then respects.</p>
    <table><tr><th>dataset<th>what it contains<th>origin<th>size<th>used here</tr>${cat.datasets.map((d) => `<tr><td><b>${esc(d.name)}</b><br><span class="mono tip">${esc(d.path)}</span><td>${esc(d.what)}<td>${esc(d.source)}<td>${esc(d.size)}<td>${esc(d.used)}</tr>`).join("")}</table>
    <h2>FactPages tables</h2><div class="row"><select id="tb"><option value="">choose a table…</option>${cat.tables.map((t) => `<option value="${t.name}">${t.name} (${t.rows.toLocaleString()} rows, ${t.cols} columns)</option>`).join("")}</select></div><div id="ex"></div>`);
    const qs = (o) => { const p = new URLSearchParams(o); st.f.map((x) => x.join("|")).forEach((f) => p.append("f", f)); return p; }, get = (p, o) => fetch("api/" + p + "?" + qs(o)).then((r) => r.json());
    const chips = () => (st.f.length ? `<div class="row"><span class="tip">filters:</span>${st.f.map((f, i) => `<span class="mono">${esc(f[0])} ${esc(f[1])} ${esc(f[2] ?? "")} <a data-rm="${i}" style="cursor:pointer">[x]</a></span>`).join(" ")}</div>` : "");
    const show = async () => { const cols = st.cols, tabs = [["chart", "Chart"], ["rows", "Rows"], ["map", "Map"], ["cols", "Columns"]];
      $("#ex").innerHTML = `<div class="row">${tabs.map(([k, t]) => `<button class="btn ${st.tab === k ? "on" : ""}" data-tab="${k}">${t}</button>`).join("")}</div>${chips()}<div id="pane"></div>`;
      $("#ex").onclick = (e) => { const rm = e.target.closest("[data-rm]"), tb = e.target.closest("[data-tab]"); if (rm) { st.f.splice(+rm.dataset.rm, 1); show(); } if (tb) { st.tab = tb.dataset.tab; show(); } };
      const P = $("#pane");
      if (st.tab === "cols") P.innerHTML = `<p class="tip">${st.n.toLocaleString()} rows. Missing = share empty; distinct = number of different values.</p><table><tr><th>column<th>type<th class=r>missing<th class=r>distinct<th>min<th>max</tr>${cols.map((c) => `<tr><td><b>${esc(c.name)}</b><td class="mono">${esc(c.type)}<td class=r>${pct(c.null_share, 0)}<td class=r>${c.distinct.toLocaleString()}<td class="mono">${esc((c.min ?? "").slice(0, 30))}<td class="mono">${esc((c.max ?? "").slice(0, 30))}</tr>`).join("")}</table>`;
      if (st.tab === "rows") { const r = await get("table/rows", { name: st.t, limit: 100, offset: st.off }); P.innerHTML = `<div class="row"><button class="btn" id="pv">←</button><button class="btn" id="nx">→</button><span class="tip">${r.total.toLocaleString()} rows match · showing ${st.off + 1}–${st.off + r.rows.length}</span></div><div style="overflow:auto"><table><tr>${r.columns.map((c) => `<th>${esc(c)}`).join("")}</tr>${r.rows.map((row) => `<tr>${row.map((v) => `<td>${esc(String(v ?? "").slice(0, 60))}`).join("")}</tr>`).join("")}</table></div>`;
        if ($("#pv")) { $("#pv").onclick = () => { st.off = Math.max(0, st.off - 100); show(); }; $("#nx").onclick = () => { st.off += 100; show(); }; } }  // the tab may have changed while the rows loaded
      if (st.tab === "chart") { P.innerHTML = `<div class="row"><label>x <select id="cx">${cols.map((c) => `<option ${c.name === st.x ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></label><label>y <select id="cy"><option value="">(count of rows)</option>${cols.filter((c) => c.numeric).map((c) => `<option ${c.name === st.y ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></label><label>as <select id="ca">${["mean", "sum", "median"].map((a) => `<option ${a === st.agg ? "selected" : ""}>${a}</option>`).join("")}</select></label><span class="tip">click a bar to filter</span></div><div id="ch" style="height:420px"></div>`;
        const run = async () => { st.x = $("#cx").value; st.y = $("#cy").value; st.agg = $("#ca").value; const d = await get("table/chart", { name: st.t, x: st.x, ...(st.y ? { y: st.y, agg: st.agg } : {}) });
          await plot($("#ch"), [{ type: "bar", x: d.x.map((v) => (d.kind === "hist" ? +v.toPrecision(5) : v)), y: d.y, marker: { color: css("--data") }, hovertemplate: "%{x}: %{y:,.2f}<extra></extra>" }], { xaxis: { title: st.x, type: d.kind === "cat" ? "category" : "linear", tickangle: d.kind === "cat" ? -35 : 0 }, yaxis: { title: st.y ? `${st.agg} of ${st.y}` : "rows" }, margin: { l: 60, r: 10, t: 10, b: 110 } });
          $("#ch").on("plotly_click", (e) => { const v = e.points[0].x; if (d.kind === "cat") st.f.push([st.x, "eq", v]); else { st.f.push([st.x, "ge", String(v - d.step / 2)]); st.f.push([st.x, "lt", String(v + d.step / 2)]); } st.off = 0; show(); }); };
        ["#cx", "#cy", "#ca"].forEach((s) => ($(s).onchange = run)); await run(); }
      if (st.tab === "map") { const d = await get("table/points", { name: st.t }); P.innerHTML = d.points.length ? `<p class="tip">${d.points.length.toLocaleString()} points (max 6000) from ${d.lat} / ${d.lon}. Filters apply.</p><div id="map" style="height:560px"></div>` : `<p class="tip">${esc(d.note)}</p>`;
        if (d.points.length) { if (map) map.remove(); map = L.map("map"); osm().addTo(map); const g = L.featureGroup(d.points.map((p) => L.circleMarker([p.lat, p.lon], { radius: 2.5, weight: 1, color: "#111", fillColor: "#fff", fillOpacity: 0.9 }))).addTo(map); map.fitBounds(g.getBounds(), { padding: [10, 10] }); } } };
    $("#tb").onchange = async (e) => { st.t = e.target.value; st.f = []; st.off = 0; if (!st.t) { $("#ex").innerHTML = ""; return; } const c = await api("table/columns", { name: st.t }); st.cols = c.columns; st.n = c.rows; st.x = c.columns[0].name; st.y = ""; st.tab = "chart"; await show(); };
  },

  async workflows() {
    const workflows = [
      ["Diskos Detective", "/hackathon/detective/", "Cited report + FactPages evidence and a measured DISKOS-QA scorecard."],
      ["Barrier Ledger", "/hackathon/barrier/", "CO2 legacy-well / P&A screening with missing evidence shown."],
      ["Spud Brief", "/hackathon/spud/", "Offset mud, LOT and drilling-hazard evidence before a well."],
      ["Tie-back Matchmaker", "/hackathon/tieback/", "Discovery, host, reserve and timing relations."],
      ["Data Doctor", "/hackathon/doctor/", "Conflicts in position, depth, tops and report claims."],
      ["Log Lens", "/hackathon/logs/", "FORCE log benchmark with observed-vs-predicted disagreements."],
      ["Seismic Lookalike", "/hackathon/seismic/", "Held-out seismic analogue search; not NCS ground truth."],
      ["Field Pulse", "/hackathon/decline/", "Production, decline and Sodir reserves."],
    ];
    doc(`<h1>Workflows</h1><p class="lead">One evidence workflow across structured data, reports, models and specialist tools. Choose an area, inspect provenance, test a claim, then compare decisions. No page below turns a model output into geological truth.</p>
      <div class="note"><b>Configured areas</b><p><b>Smeaheia:</b> CCS seismic, wells and barrier evidence. <b>Sleipner:</b> 4D CO₂-storage context and processing-aware differences. <b>Northern Lights:</b> legacy-well screening around Aurora/Eos. <b>NCS-wide:</b> formations, wells, FactPages, logs, cores and reports.</p></div>
      <h2>Evidence tools</h2><table><tr><th>tool<th>role</tr>${workflows.map(([n, u, d]) => `<tr><td><a href="${u}"><b>${esc(n)}</b></a><td>${esc(d)}</tr>`).join("")}</table>
      <h2>Operating rule</h2><p>Measured data → extracted claim → model estimate → held-out test → calibration → uncertainty → source receipt. Missing or conflicting evidence stays visible. Current green-clay, log and seismic limits are listed on <a href="#validation">Validation</a> and <a href="#layers">Layers</a>.</p>`);
  },

  async lineage(_, live) {
    const [cat, lineage, proof, velocity, plan, coverage] = await Promise.all(["datasets", "model", "proof", "velocity", "relations", "seismic-coverage"].map((p) => api("provenance/" + p)));
    if (!live()) return;
    if (!cat.datasets) {
      doc(`<h1>Lineage and model proof</h1>${note("Dataset inventory unavailable", "The backend did not supply the dataset inventory.")}`);
      return;
    }
    const bytes = (n) => n >= 1e12 ? (n / 1e12).toFixed(1) + " TB" : n >= 1e9 ? (n / 1e9).toFixed(1) + " GB" : (n / 1e6).toFixed(1) + " MB";
    const rows = cat.datasets.map((d) => `<tr><td><b>${esc(d.name)}</b><br><span class="mono tip">${esc(d.path)}</span><td>${esc((d.modality || []).join(", "))}<td>${esc(d.kind)}<td class="r">${bytes(d.bytes)}<br>${d.files.toLocaleString()} files<td>${esc(d.license)}<br><span class="tip">${esc(d.truth)}</span><td>${d.limitations.map((x) => esc(x)).join(" · ")}</tr>`).join("");
    const por = proof.metrics?.porosity, perm = proof.metrics?.log10_perm;
    const v = velocity.evaluation;
    const methods = { ui_constant: "Constant 2 km/s (3D preview)", seabed_fixed_rock: "Seabed + fixed rock speed", seabed_fitted_rock: "Seabed + fitted rock speed", layer_cake: "Seabed + fitted layer speeds" };
    const pilot = v ? `<h2>GN1101 depth pilot</h2><p>${esc(v.split)} · ${v.sites} sites. Reference: ${esc(velocity.test_reference)}. The calibrated overlay is not enabled.</p>
      <table><tr><th>method<th>RMSE (m)<th>max absolute error (m)</tr>${Object.entries(v.pooled_scores).map(([m, s]) => `<tr><td>${esc(methods[m] || m)}<td>${f2(s.rmse_m, 1)}<td>${f2(s.max_abs_m, 1)}</tr>`).join("")}</table><p class="tip">${velocity.limitations.map(esc).join(" ")}</p><p><a href="api/provenance/velocity">Raw ties, held-out residuals and source receipt</a></p>` : "";
    const footprint = coverage.surveys ? `<h2>Seismic wellhead screen</h2><p>${coverage.distinct_wells_in_footprints} distinct wellheads across ${coverage.surveys.length} indexed surveys or processing variants. ${esc(coverage.scope)}</p>
      <table><tr><th>survey<th>wellheads in hull<th>FORCE train<th>RealPore rows present<th>labelled report intervals present</tr>${coverage.surveys.map((s) => `<tr><td>${esc(s.name)}<td>${s.well_count}<td>${s.wells.filter((w) => w.force_train_logs).length}<td>${s.wells.filter((w) => w.core_rows_with_matching_id_and_name > 0).length}<td>${s.wells.filter((w) => w.labelled_report_intervals > 0).length}</tr>`).join("")}</table>
      <p class="tip">The last three columns count wellheads, not rows. Overlapping surveys and vintages can include the same well.</p><p><a href="api/provenance/seismic-coverage">Well IDs, distances and source receipt</a></p>` : "";
    const relations = plan.relations ? `<h2>How sources connect</h2><p>${esc(plan.scope)}</p><table><tr><th>relation<th>entity and join keys<th>role and limit</tr>${plan.relations.map((r) => `<tr><td>${esc(r.id)}<br><span class="tip">${r.inputs.map(esc).join(" · ")}</span><td>${esc(r.grain)}<br><span class="tip">${r.keys.map(esc).join(" · ")}</span><td><b>${esc(r.state.replaceAll("_", " "))}</b> · ${esc(r.use)}<br><span class="tip">${esc(r.guard)}</span></tr>`).join("")}</table>` : "";
    const historical = por && perm ? `<h2>First GPU proof · historical</h2><p>${esc(proof.purpose)} Split: ${esc(proof.split.name)}. Device: <b>${esc(proof.device)}</b>. Hidden-test labels used: <b>${proof.split.hidden_test_used ? "yes" : "no"}</b>.</p>
      <table><tr><th>target<th>median RMSE<th>tree RMSE / R²<th>masked MLP RMSE / R²</tr><tr><td>Core porosity (%)<td>${f2(por.median.rmse)}<td>${f2(por.histgb.rmse)} / ${f2(por.histgb.r2, 3)}<td>${f2(por.mlp.rmse)} / ${f2(por.mlp.r2, 3)}<tr><td>log10 permeability<td>${f2(perm.median.rmse)}<td>${f2(perm.histgb.rmse)} / ${f2(perm.histgb.r2, 3)}<td>${f2(perm.mlp.rmse)} / ${f2(perm.mlp.r2, 3)}</table>
      <div class="note warn"><b>Historical baseline, not a released model</b><p>The shallow tree beat the proof neural net on its blocked split. These scores predate the well-ID and depth-join audit.</p><p>${proof.limitations.map(esc).join(" · ")}</p></div>` : note("GPU proof unavailable", esc(proof.detail || "No proof artifact reported."));
    const current = lineage.validation ? `<h2>Current model lineage</h2><p>Unit policy: <span class="mono">${esc(lineage.unit_policy)}</span>. Split: ${esc(lineage.validation.split)}. Calibration: ${esc(lineage.validation.calibration)}. Bootstrap: ${esc(lineage.validation.bootstrap)}.</p>
      <table><tr><th>artifact / code<th>bytes<th>sha256 prefix</tr>${lineage.artifacts.concat(lineage.code).map((x) => `<tr><td class="mono">${esc(x.path)}<td class="r">${(x.bytes || 0).toLocaleString()}<td class="mono">${esc((x.sha256 || "directory/large-file").slice(0, 16))}</tr>`).join("")}</table>` : note("Model lineage unavailable", esc(lineage.detail || "No model lineage reported."));
    doc(`<h1>Lineage and model proof</h1><p class="lead">Source, licence, grain, truth status, limits, code/model hashes and validation policy. Derived tables are not primary evidence.</p>
      <div class="grid g4"><div><div class="num">${cat.datasets.length}</div><div class="cap">dataset records</div></div><div><div class="num">${bytes(cat.bytes_total)}</div><div class="cap">catalogued bytes, source paths deduplicated</div></div><div><div class="num">${proof.data?.overlap_wells ?? "–"}</div><div class="cap">whole wells in first cross-modal proof</div></div><div><div class="num">${proof.training_seconds == null ? "–" : proof.training_seconds + "s"}</div><div class="cap">GPU cross-validation training</div></div></div>
      ${pilot}${footprint}${historical}${current}${relations}<h2>Dataset inventory</h2><div style="overflow:auto"><table><tr><th>dataset<th>modalities<th>kind<th class="r">size / files<th>licence + truth status<th>known limits</tr>${rows}</table></div>`);
  },

  async targets(_, live) {
    const opt = await api("targets/options"), T = await api("targets"), form = { title: "", mode: "well", table: "wellbore_exploration", population: [], success: [], group: "wlbMainArea", keywords: [], lith: ["clay"] };
    if (!live()) return;
    const fmtG = (g) => `${sg(g.delta_gain, 4)} <span class="tip">[${sg(g.p05, 4)}, ${sg(g.p95, 4)}]</span> ${tag(g.p05 > 0 ? "helps" : g.p95 < 0 ? "hurts" : "no_evidence", g.p05 > 0 ? "helps" : g.p95 < 0 ? "worse" : "no evidence")}`;
    doc(`<h1>Targets</h1><p class="lead">A target is a question we can score: <i>for this well or interval, how likely is X?</i> Choose a table, say what counts as X, and the same engine (formation prior, neighbours, validation, explanations) runs on it. Everything built here is saved and can be opened on the map, 3D view, units and validation pages through the Target switch at the top.</p>
    <h2>Saved targets</h2><table id="tt"></table>
    <h2>Build a target</h2><div class="note"><b>How it works</b><p><b>Well</b>: one unit per wellbore (e.g. did a wildcat find oil or gas). <b>Interval</b>: one unit per well × formation, counting rows of a test or log table that fall inside it (e.g. DST tests that flowed oil, mud weights above a limit). Success = rows meeting your conditions; trials = rows meeting the population conditions.</p></div>
    <div class="row">Presets: ${T.presets.map((p, i) => `<button class="btn" data-pr="${i}">${esc(p.title)}</button>`).join(" ")}</div>
    <div id="bf"></div><div class="row"><button class="btn on" id="go">Build and validate</button><span id="gs" class="tip"></span></div><div id="res"></div>`);
    const tabOf = () => opt[form.mode].find((t) => t.table === form.table) || opt[form.mode][0], colOf = (n) => tabOf().columns.find((c) => c.name === n);
    const filt = (key, label) => `<h3>${label}</h3>${form[key].map((f, i) => { const [c, o = "eq", v = ""] = f.split("|"), cd = colOf(c);
      return `<div class="row"><select data-k="${key}" data-i="${i}" data-p="c">${tabOf().columns.map((x) => `<option ${x.name === c ? "selected" : ""}>${x.name}</option>`).join("")}</select><select data-k="${key}" data-i="${i}" data-p="o">${Object.entries(opt.ops).map(([k, t]) => `<option value="${k}" ${k === o ? "selected" : ""}>${t}</option>`).join("")}</select><input type="text" data-k="${key}" data-i="${i}" data-p="v" value="${esc(v)}" list="dl-${key}-${i}" placeholder="${cd?.numeric ? `${cd.min} … ${cd.max}` : "value"}"><datalist id="dl-${key}-${i}">${(cd?.values || []).map((x) => `<option>${esc(x)}</option>`).join("")}</datalist><a data-del="${key}|${i}" style="cursor:pointer">[remove]</a></div>`; }).join("")}<div class="row"><button class="btn" data-add="${key}">add condition</button></div>`;
    const draw = () => { const g = opt[form.mode].length ? tabOf().columns.filter((c) => !c.numeric && c.distinct > 1 && c.distinct <= 60) : [];
      $("#bf").innerHTML = `<div class="row"><label>Title <input type="text" id="bt" value="${esc(form.title)}" size="40" placeholder="e.g. Oil found by wildcat wells"></label></div>
        <div class="row"><label><input type="radio" name="md" value="well" ${form.mode === "well" ? "checked" : ""}> Well</label><label><input type="radio" name="md" value="interval" ${form.mode === "interval" ? "checked" : ""}> Interval (well × formation)</label><label><input type="radio" name="md" value="text" ${form.mode === "text" ? "checked" : ""}> Report text</label>
        ${form.mode === "text" ? "" : `<label>Table <select id="bt2">${opt[form.mode].map((t) => `<option value="${t.table}" ${t.table === form.table ? "selected" : ""}>${t.table} (${t.rows.toLocaleString()} rows)</option>`).join("")}</select></label>
        ${form.mode === "well" ? `<label>Group by <select id="bg">${g.map((c) => `<option ${c.name === form.group ? "selected" : ""}>${c.name}</option>`).join("")}</select></label>` : '<span class="tip">grouped by formation / group tops</span>'}`}</div>
        ${form.mode === "text" ? `<div class="note"><b>Report text</b><p>The rock-description lines of ${opt.text.lines.toLocaleString()} well-report lines in ${opt.text.wells.toLocaleString()} wells. A line is a success when it contains one of the keywords (matched case-insensitively at the start of a word: “calc” finds calcareous and calcite). Trials are the lines of the rock types you tick. More detailed reports contribute more lines, so the reporting-effort caveat applies.</p></div>
        <div class="row"><label>Keywords (comma separated) <input type="text" id="kw" size="44" value="${esc((form.keywords || []).join(", "))}" placeholder="e.g. calcareous, calcite"></label></div>
        <div class="row">Rock types: ${["clay", "sand", "carbonate", "other"].map((l) => `<label class="chk"><input type="checkbox" data-lith="${l}" ${(form.lith || []).includes(l) ? "checked" : ""}> ${l} <span class="tip">${(opt.text.liths[l] || 0).toLocaleString()}</span></label>`).join(" ")} <span class="tip">“other” is mostly operations text, not rock</span></div>
        <div class="row"><button class="btn" id="pvw">Preview matching lines</button></div><div id="pvr"></div>` : `${filt("population", "Count only rows where (optional)")}${filt("success", "Success when (required)")}`}`; };
    const tt = () => { const all = [T.builtin, ...T.saved]; $("#tt").innerHTML = "<tr><th>target<th>mode<th class=r>units<th class=r>successes / trials<th>group gain<th>neighbour gain<th></tr>" + all.map((t) => { const s = t.summary;
      return `<tr><td><b>${esc(t.title)}</b>${t.id === TARGET ? ' <span class="tag ok">active</span>' : ""}<td>${t.mode}<td class=r>${s ? s.units.toLocaleString() : "3,762"}<td class=r>${s ? `${s.successes.toLocaleString()} / ${s.trials.toLocaleString()}` : "3,032 / 49,961"}<td>${s ? fmtG(s.gain_formation) : '<span class="tip">see Validation</span>'}<td>${s ? fmtG(s.gain_spatial) : ""}<td><a data-use="${t.id}" style="cursor:pointer">use</a>${t.builtin ? "" : ` · <a data-rmt="${t.id}" style="cursor:pointer">delete</a>`}</tr>`; }).join(""); };
    tt(); draw();
    $("#view").onclick = async (e) => { const a = e.target.closest("[data-use],[data-rmt],[data-pr],[data-add],[data-del],#pvw"); if (!a) return;
      if (a.dataset.use) { TARGET = a.dataset.use; localStorage.setItem("target", TARGET); await loadTarget(); T.saved = (await api("targets")).saved; tt(); }
      if (a.dataset.rmt && confirm("Delete this saved target?")) { await fetch("api/targets/" + a.dataset.rmt, { method: "DELETE" }); if (TARGET === a.dataset.rmt) { TARGET = "green_clay"; localStorage.setItem("target", TARGET); } await loadTarget(); Object.assign(T, await api("targets")); tt(); }
      if (a.dataset.pr) { const p = T.presets[+a.dataset.pr]; Object.assign(form, { title: p.title, mode: p.mode, table: p.table || form.table, population: [...(p.population || [])], success: [...(p.success || [])], group: p.group || "wlbMainArea", words: p.words, keywords: [...(p.keywords || [])], lith: [...(p.lith || ["clay"])] }); draw(); }
      if (a.id === "pvw") { const q = await api("text/preview", { keywords: form.keywords.join(","), lith: form.lith.join(",") }); $("#pvr").innerHTML = q.detail ? `<p class="bad">${esc(q.detail)}</p>` : `<p><b>${q.matches.toLocaleString()}</b> of ${q.lines.toLocaleString()} lines match (${pct(q.share)}), in ${q.wells.toLocaleString()} wells. Examples (well, page, depth):</p><table>${q.examples.map((x) => `<tr><td class="mono">${esc(x.wellbore)} p.${x.page}<td class="mono r">${x.depth} m<td>${esc(x.lith)}<td>${esc(x.text.slice(0, 200))}</tr>`).join("")}</table>`; }
      if (a.dataset.add) { form[a.dataset.add].push(`${tabOf().columns[0].name}|eq|`); draw(); }
      if (a.dataset.del) { const [k, i] = a.dataset.del.split("|"); form[k].splice(+i, 1); draw(); } };
    $("#view").onchange = (e) => { const t = e.target; if (t.name === "md") { form.mode = t.value; if (form.mode !== "text") form.table = opt[form.mode][0].table; form.population = []; form.success = []; draw(); } if (t.dataset?.lith) form.lith = [...document.querySelectorAll("[data-lith]")].filter((x) => x.checked).map((x) => x.dataset.lith); if (t.id === "bt2") { form.table = t.value; form.population = []; form.success = []; draw(); } if (t.id === "bg") form.group = t.value;
      if (t.dataset.k) { const f = form[t.dataset.k], i = +t.dataset.i, [c, o = "eq", v = ""] = f[i].split("|"), n = { c, o, v }; n[t.dataset.p] = t.value; f[i] = `${n.c}|${n.o}|${n.v}`; if (t.dataset.p === "c") draw(); } };
    $("#view").oninput = (e) => { if (e.target.id === "bt") form.title = e.target.value; if (e.target.id === "kw") form.keywords = e.target.value.split(",").map((x) => x.trim()).filter(Boolean); if (e.target.dataset?.p === "v") { const f = form[e.target.dataset.k], i = +e.target.dataset.i, [c, o = "eq"] = f[i].split("|"); f[i] = `${c}|${o}|${e.target.value}`; } };
    $("#go").onclick = async () => { if (form.mode === "text" ? !form.keywords.length : !form.success.length) { $("#gs").textContent = form.mode === "text" ? "add at least one keyword" : "add at least one success condition"; return; } const s = Date.now(), timer = setInterval(() => ($("#gs").textContent = `building and validating (5-fold, 40 km blocks)… ${Math.round((Date.now() - s) / 1000)} s`), 1000);
      const body = { ...form, words: form.words && form.words.rows ? form.words : { rows: form.mode === "well" ? "wells" : form.mode === "text" ? "described rows" : "rows", hit: form.mode === "text" ? "mention " + form.keywords.join(" or ") : "meet the success condition", short: form.mode === "text" ? (form.keywords[0] || "keyword") : "success", unit: form.mode === "well" ? "wellbore" : "well x formation interval" } };
      const r = await track(LABELS["targets/build"], fetch("api/targets/build", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })); clearInterval(timer); const j = await r.json(); if (!$("#gs")) return;  // the page may have changed while it built
      if (!r.ok) { $("#gs").innerHTML = `<span class="bad">${esc(typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail))}</span>`; return; } $("#gs").textContent = `done in ${j.summary.seconds} s`; Object.assign(T, await api("targets")); tt();
      const m = j.summary; $("#res").innerHTML = `<h2>Result: ${esc(j.title)}</h2><div class="grid g4"><div><div class="num">${m.units.toLocaleString()}</div><div class="cap">units, ${m.wells.toLocaleString()} wells</div></div><div><div class="num">${pct(m.base_rate)}</div><div class="cap">overall success rate</div></div></div>
        <table><tr><th>evidence<th>gain over the previous step (held-out wells, 90% range)</tr><tr><td>Formation / group<td>${fmtG(m.gain_formation)}<tr><td>Neighbouring wells<td>${fmtG(m.gain_spatial)}</table><p><button class="btn on" id="useit">Open this target</button> then use Map, 3D, Units and Validation.</p>`; $("#useit").onclick = async () => { TARGET = j.id; localStorage.setItem("target", TARGET); await loadTarget(); location.hash = "validation"; }; };
  },

  async layers() {
    doc(`<h1>Layers</h1><p class="lead">A layer is one kind of data turned into a push up or down on the estimate. A layer stays switched on unless testing on unseen wells shows it makes predictions worse. Hover or read the test under each.</p>`);
    const why = { strat: "How often this outcome occurs in the formation or group across all wells, smoothed so small samples do not mislead.", spatial: "Looks at wells of the same group nearby (within 60 km), weighted by closeness: outcomes tend to cluster.", logs: "Instrument readings along the well (gamma, density, neutron...) compared with the formation's normal. Green clay target only.", seismic: "Reflected sound waves in 3D, would add information between wells. Not built: no seismic cube lies over these wells." };
    $("#view").firstChild.insertAdjacentHTML("beforeend", LAYERS.map((l) => { const e = l.evidence; return `<h2>${esc(l.title)} ${tag(l.status, STATUS_WORDS[l.status])}</h2><p>${why[l.name] || ""}</p><p class="tip">${esc(l.doc)}</p>${e ? `<p><b>Test:</b> on wells held out of fitting, adding this layer changed accuracy by <b>${sg(e.delta_gain)}</b> (90% range ${sg(e.p05)} to ${sg(e.p95)}) compared with ${esc(e.compared_with)}${e.units ? `, using the ${e.units} units that have logs` : ""}. ${l.status === "hurts" ? "The whole range is below zero: the layer made predictions <b>worse</b> on unseen wells (it fits the training wells but does not carry over), so it is off by default." : l.status === "helps" ? "The whole range is above zero." : "The range spans zero: no measurable difference."}</p>` : '<p class="tip">Nothing to test.</p>'}${l.name === "logs" && l.params.weights ? fig("lw", 240, "Fitted log weights; lines are 90% ranges over resampled wells. Dark bars kept the same sign in at least 90% of resamples.") : ""}`; }).join(""));
    const lg = LAYERS.find((l) => l.name === "logs"); if (lg?.params.weights && $("#lw")) { const w = Object.entries(lg.params.weights);
      plot($("#lw"), [{ type: "bar", orientation: "h", y: w.map((x) => x[0]), x: w.map((x) => x[1].w), marker: { color: w.map((x) => (x[1].stable_sign >= 0.9 ? css("--data") : css("--mut"))) }, error_x: { type: "data", symmetric: false, array: w.map((x) => x[1].p95 - x[1].w), arrayminus: w.map((x) => x[1].w - x[1].p05), color: css("--mut") } }], { yaxis: { autorange: "reversed" }, margin: { l: 60, r: 10, t: 10, b: 30 } }); }
  },

  async knowledge(_, live) {
    const k = await api("kb"); if (!live()) return;
    doc(`<h1>Knowledge</h1><p class="lead">Textbook geology rules, each with its source and a test against our data. <b>Agrees</b>: the data lean the way the rule says. <b>Disagrees</b>: the other way. <b>Inconclusive</b>: the data cannot tell. A rule is never trusted blindly and never hidden when the data disagree. AUC = chance that a positive row has a higher value than a negative one (0.5 = no difference); about one false hit in seven checks is expected by chance.</p>
    ${k.length ? `<table><tr><th>rule<th>source status<th>data says<th>numbers and sources</tr>${k.map((r) => `<tr><td><b>${esc(r.id)}</b> ${esc(r.statement)}${r.caveat ? `<br><span class="tip">${esc(r.caveat)}</span>` : ""}<td>${tag(r.status === "sourced" ? "helps" : r.status === "inferred" ? "no_evidence" : "muted", r.status.replace("_", " "))}<td>${tag(r.verdict)}<td><span class="mono">${esc(r.numbers)}</span><br>${r.sources.map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.says)}</a>`).join("<br>")}</tr>`).join("")}</table>` : '<div class="note"><b>None yet</b>No sourced rules have been written for this target. Rules live in backend/se/knowledge/rules/*.yaml and need a source and a status.</div>'}`);
  },

  async validation(_, live) {
    const r = await api("validation"), d = r.delta, ab = r.ablation;
    if (!live()) return;
    doc(`<h1>Validation</h1><p class="lead">The scorecard for “${esc(META.title)}”. We hide whole ${r.block_km} km blocks of wells, fit on the rest and predict the hidden ones. <b>Gain</b> is how much better than guessing the overall rate (0 = no better). Ranges are 90% intervals from resampling whole wells.</p>
    <h2>Does each layer help?</h2>${fig("v1", 260, "Gain difference when a layer is added, with 90% range. Right of zero = helps; spanning zero = no evidence; left = worse.")}
    <h2>Layer combinations</h2>${fig("v2", 260, `Gain for each set of layers on all ${ab.strat.units.toLocaleString()} held-out units.`)}
    <h2>Are the numbers honest?</h2>${fig("v3", 320, "Predicted vs observed rate in ten groups. On the dashed line = calibrated. Crosses: before calibration.")}
    ${r.by_distance?.length ? `<h2>Distance to the nearest training well</h2>${fig("v4", 300, "Gain with and without neighbours, by distance (km) to the nearest training well.")}` : ""}
    ${r.sweep_ell?.length ? `<h2>Settings barely matter</h2>${fig("v5", 280, "Gain for different neighbourhood sizes (km). Flat means no tuning is needed.")}` : ""}
    ${r.by_coverage?.length ? `<h2>Skill by amount of data per unit</h2>${fig("v6", 280, "AUC by trials per unit. 0.5 = nothing, 1 = perfect.")}` : ""}`);
    const ent = Object.entries(d).filter(([, v]) => v), data = css("--data"), bad = css("--bad"), mut = css("--mut");
    plot($("#v1"), [{ type: "scatter", mode: "markers", y: ent.map((e) => e[0].replaceAll("_", " ")), x: ent.map((e) => e[1].delta_gain), marker: { size: 9, color: ent.map((e) => (e[1].p05 > 0 ? data : e[1].p95 < 0 ? bad : mut)) }, error_x: { type: "data", symmetric: false, array: ent.map((e) => e[1].p95 - e[1].delta_gain), arrayminus: ent.map((e) => e[1].delta_gain - e[1].p05), color: mut } }], { xaxis: { title: "gain difference", zerolinewidth: 2, zerolinecolor: mut }, yaxis: { autorange: "reversed" }, margin: { l: 250, r: 20, t: 10, b: 44 } });
    plot($("#v2"), [{ type: "bar", x: Object.keys(ab), y: Object.values(ab).map((v) => v.deviance_gain), marker: { color: data }, hovertemplate: "%{x}: %{y:.4f}<extra></extra>" }], { yaxis: { title: "gain", rangemode: "tozero" } });
    const rc = r.reliability_calibrated, mxr = Math.max(...rc.map((x) => Math.max(x.predicted, x.observed))) * 100 * 1.1;
    plot($("#v3"), [{ type: "scatter", mode: "markers+lines", x: rc.map((x) => x.predicted * 100), y: rc.map((x) => x.observed * 100), marker: { color: data, size: 8 }, line: { color: data, width: 1 }, name: "calibrated" }, { type: "scatter", mode: "markers", x: r.reliability_raw.map((x) => x.predicted * 100), y: r.reliability_raw.map((x) => x.observed * 100), marker: { color: mut, symbol: "x" }, name: "raw" }, { type: "scatter", mode: "lines", x: [0, mxr], y: [0, mxr], line: { dash: "dash", color: css("--rule") }, showlegend: false }], { xaxis: { title: "predicted %" }, yaxis: { title: "observed %" } });
    if ($("#v4")) plot($("#v4"), [{ type: "bar", name: "group only", x: r.by_distance.map((x) => `${x.from_km}–${x.to_km}`), y: r.by_distance.map((x) => x.gain_strat_only), marker: { color: mut } }, { type: "bar", name: "+ neighbours", x: r.by_distance.map((x) => `${x.from_km}–${x.to_km}`), y: r.by_distance.map((x) => x.deviance_gain), marker: { color: data } }], { barmode: "group", yaxis: { title: "gain" }, xaxis: { title: "km to nearest training well" } });
    if ($("#v5")) plot($("#v5"), [{ type: "scatter", mode: "lines+markers", x: r.sweep_ell.map((x) => x.ell_km), y: r.sweep_ell.map((x) => x.deviance_gain), line: { color: data } }], { xaxis: { type: "log", title: "neighbourhood size (km)" }, yaxis: { title: "gain", rangemode: "tozero" } });
    if ($("#v6")) plot($("#v6"), [{ type: "bar", x: r.by_coverage.map((x) => x.coverage + " (n=" + x.n + ")"), y: r.by_coverage.map((x) => x.auc), marker: { color: data } }], { yaxis: { title: "AUC", range: [0.4, 0.9] }, shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0.5, y1: 0.5, line: { dash: "dash", color: mut } }] });
  },

  async contradictions(_, live) {
    const c = await api("contradictions"), t = (rows, kind) => `<table><tr><th>unit<th class=r>trials<th class=r>successes<th class=r>model said<th class=r>${kind}</tr>${rows.slice(0, 25).map((x) => `<tr class="click" data-u="${esc(x.unit)}"><td>${esc(x.unit)}<td class=r>${x.coverage}<td class=r>${x.n_green}<td class=r>${pct(x.p_full)}<td class="r mono">${(x.tail_many ?? x.tail_none)?.toExponential(1)}</tr>`).join("")}</table>`;
    if (!live()) return;
    doc(`<h1>Contradictions</h1><p class="lead">Where the records and the model disagree most. Either the model misses something, the record is unusual, or it is worth a second look. Candidates for review, not errors. “Chance” is the probability of a result this extreme if the model were right.</p><h2>Much higher than expected</h2>${t(c.reported_but_unexpected, "chance")}<h2>Expected, but none recorded</h2>${t(c.expected_but_not_reported, "chance")}`);
    $(".doc").onclick = (e) => { const r = e.target.closest("tr[data-u]"); if (r) location.hash = "unit/" + encodeURIComponent(r.dataset.u); };
  },

  async architecture(_, live) {
    // docs/architecture.md: mermaid charts rendered in place, each in a pan/zoom frame (wheel = zoom at the cursor, drag = move)
    const d = (await api("docs-list")).find((x) => x.name === "architecture");
    if (!live()) return;
    if (!d) return doc(`<div class="note warn">docs/architecture.md is missing.</div>`);
    doc(`<h1>Architecture</h1><p class="lead">Every data source, how sources are joined, the methods applied, and what came out, with the reason behind each result. Scroll to zoom a chart, drag to move it, double-click to fit.</p><div class="md">${marked.parse(d.markdown.replace(/^# .*\n/, ""))}</div>`);
    const dark = document.documentElement.dataset.theme === "dark" || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme:dark)").matches);
    mermaid.initialize({ startOnLoad: false, theme: dark ? "dark" : "neutral", securityLevel: "strict", flowchart: { htmlLabels: true, useMaxWidth: false }, fontFamily: "Inter, sans-serif" });
    let i = 0;
    for (const code of document.querySelectorAll(".md pre code.language-mermaid")) {
      const { svg } = await mermaid.render("arch" + i++, code.textContent);
      const box = document.createElement("div"); box.className = "pz"; box.innerHTML = `<div class="pzbar"><button class="lnk" data-z="1.25">+</button><button class="lnk" data-z="0.8">−</button><button class="lnk" data-z="fit">fit</button><button class="lnk" data-z="full">full screen</button></div><div class="pzin">${svg}</div>`;
      code.parentElement.replaceWith(box); panZoom(box);
    }
  },

  async log(_, live) { const l = await api("log"); if (!live()) return; if (typeof l.markdown !== "string") throw new Error("Decision log unavailable");
    const [intro, ...entries] = l.markdown.split(/^## (?=L\d+)/m);
    doc(`<h1>Decision log</h1><p class="lead">Append-only source, newest entry shown first.</p>${entries.reverse().map((entry,i) => {
      const [title,...body] = entry.split("\n");
      return `<details${i ? "" : " open"}><summary>${esc(title)}</summary><pre class="screen-log">${esc(body.join("\n").trim())}</pre></details>`;
    }).join("")}<details><summary>Log introduction</summary><pre class="screen-log">${esc(intro)}</pre></details>`); },
};
init();
