// Subsurface Evidence UI. One file, no build. Every number comes from /api; every page says what it shows.
const $ = (s, r = document) => r.querySelector(s), NOTARGET = /^(catalog|table\/|targets|last_job|log|docs-list)/;
let META, LAYERS, TARGET = localStorage.getItem("target") || "green_clay", map = null, COAST = null, TARGETS = null;
const api = (p, q = {}) => fetch("api/" + p + "?" + new URLSearchParams(NOTARGET.test(p) ? q : { target: TARGET, ...q })).then((r) => r.json());
const pct = (x, d = 1) => (x == null ? "–" : (100 * x).toFixed(d) + "%"), f2 = (x, d = 2) => (x == null ? "–" : (+x).toFixed(d)), sg = (x, d = 3) => (x == null ? "–" : (x > 0 ? "+" : "") + (+x).toFixed(d));
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim(), W = () => META.words;
const tag = (cls, t, tip) => `<span class="tag ${cls}"${tip ? ` title="${esc(tip)}"` : ""}>${esc(t || cls.replace("_", " "))}</span>`;
const note = (title, ...l) => `<div class="note"><b>${title}</b>${l.map((x) => `<p>${x}</p>`).join("")}</div>`;
const STATUS_WORDS = { helps: "helps", no_evidence: "no measurable help", hurts: "makes it worse", not_built: "not built / no data" };
const evTip = (l) => { const e = l.evidence; if (!e) return l.status === "not_built" ? "Nothing to test: no code or no data for this evidence." : ""; const verb = l.status === "helps" ? "improved" : l.status === "hurts" ? "worsened" : "did not measurably change";
  return `On wells held out of fitting, adding this ${verb} prediction accuracy by ${sg(e.delta_gain)} (90% range ${sg(e.p05)} to ${sg(e.p95)}), compared with ${e.compared_with}${e.units ? `, on ${e.units} units` : ""}. Range entirely above 0 = helps; spanning 0 = no evidence; entirely below 0 = worse.`; };
const NAV = [["start", "Overview"], ["scene", "3D"], ["map", "Map"], ["units", "Units"], ["data", "Data"], ["targets", "Targets"], ["layers", "Layers"], ["knowledge", "Knowledge"], ["validation", "Validation"], ["contradictions", "Contradictions"], ["log", "Log"]];
const SEQ = ["#c6dbef", "#6baed6", "#2171b5", "#08306b"]; // one hue, light to dark: share of successes

function plot(el, data, layout = {}, cfg = {}) {
  const ink = css("--ink"), mut = css("--mut"), rule = css("--rule"), ax = { gridcolor: rule, zerolinecolor: rule, linecolor: ink, color: mut, ticks: "outside", tickcolor: rule };
  const L = { paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { family: "Inter, system-ui", color: ink, size: 12 }, margin: { l: 56, r: 16, t: 14, b: 44 }, legend: { orientation: "h", y: -0.22 }, ...layout, xaxis: { ...ax, ...(layout.xaxis || {}) }, yaxis: { ...ax, ...(layout.yaxis || {}) } };
  return Plotly.react(el, data, L, { displaylogo: false, responsive: true, ...cfg });
}
const fig = (id, h, cap) => `<figure><div id="${id}" style="height:${h}px"></div><figcaption>${cap}</figcaption></figure>`;

// ---- floating panes over a full-screen stage ----
function stage(inner) { $("#view").innerHTML = `<div class="stage">${inner}<div id="panes"><button class="btn" id="hideall">hide all panels</button></div></div>`;
  let hid = false; $("#hideall").onclick = (e) => { hid = !hid; document.querySelectorAll(".pane").forEach((p) => (p.style.display = hid ? "none" : "")); e.target.textContent = hid ? "show panels" : "hide all panels"; }; }
function pane(id, title, body, pos, shut = false) {
  const st = $(".stage"), key = "pane:" + id, saved = localStorage.getItem(key), el = document.createElement("div"); el.className = "pane" + ((saved ?? (shut ? "1" : "0")) === "1" ? " shut" : ""); el.style.cssText = pos; el.id = "pane-" + id;
  el.innerHTML = `<div class="ph"><span>${title}</span><button title="hide or show">–</button></div><div class="pb">${body}</div>`; st.appendChild(el);
  $("button", el).onclick = () => { el.classList.toggle("shut"); localStorage.setItem(key, el.classList.contains("shut") ? "1" : "0"); };
  $(".ph", el).onpointerdown = (e) => { if (e.target.tagName === "BUTTON") return; const r = el.getBoundingClientRect(), s = st.getBoundingClientRect(), dx = e.clientX - r.left, dy = e.clientY - r.top; el.style.right = el.style.bottom = "auto"; el.setPointerCapture(e.pointerId);
    el.onpointermove = (m) => { el.style.left = Math.max(0, Math.min(s.width - 60, m.clientX - s.left - dx)) + "px"; el.style.top = Math.max(0, Math.min(s.height - 30, m.clientY - s.top - dy)) + "px"; }; el.onpointerup = () => (el.onpointermove = null); };
  return el; }

async function init() {
  $("#links").innerHTML = NAV.map(([k, t]) => `<a data-p="${k}">${t}</a>`).join(""); $("#links").onclick = (e) => { const a = e.target.closest("a"); if (a) location.hash = a.dataset.p; };
  $("#theme").onclick = () => { const d = document.documentElement; d.dataset.theme = (d.dataset.theme || (matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light")) === "dark" ? "light" : "dark"; route(); };
  await loadTarget(); $("#target").onchange = async (e) => { TARGET = e.target.value; localStorage.setItem("target", TARGET); await loadTarget(); route(); };
  addEventListener("hashchange", route); route(); setInterval(job, 15000); job();
}
async function loadTarget() { TARGETS = await api("targets"); const all = [TARGETS.builtin, ...TARGETS.saved]; if (!all.some((t) => t.id === TARGET)) TARGET = "green_clay";
  $("#target").innerHTML = all.map((t) => `<option value="${t.id}" ${t.id === TARGET ? "selected" : ""}>${esc(t.title)}</option>`).join(""); META = await api("meta"); LAYERS = await api("layers"); }
const job = async () => { const j = await api("last_job"); $("#job").textContent = j.job ? `last heavy job: ${j.job}, ${j.via}, ${j.seconds}s` : ""; };
function route() {
  const [p, ...rest] = (location.hash.slice(1) || "start").split("/");
  document.querySelectorAll("#links a").forEach((a) => a.classList.toggle("on", a.dataset.p === (p === "unit" ? "units" : p)));
  if (map) { map.remove(); map = null; } $("#view").innerHTML = '<div class="doc"><p class="tip">loading…</p></div>';
  (PAGES[p] || PAGES.start)(decodeURIComponent(rest.join("/"))).catch((e) => ($("#view").innerHTML = `<div class="doc"><div class="note warn"><b>Could not load this page</b><pre>${esc(e)}</pre></div></div>`));
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
const rampBar = (mx) => `<div class="legend"><span>0%</span><div class="ramp"></div><span>${pct(mx)}</span><span>· grey: no well within reach, no estimate</span></div>`;
const osm = () => L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap contributors", maxZoom: 18 });

const PAGES = {
  async start() {
    const d = META.data, fs = (await api("formations")).filter((f) => f.units >= 20).slice(0, 14), w = W();
    doc(`<h1>${esc(META.title)}</h1><p class="lead">${esc(META.target_text)}. Each ${esc(w.unit)} gets an estimate, the evidence behind it, and a test on wells the model never saw.</p>
    <div class="grid g4"><div><div class="num">${d.labelled.toLocaleString()}</div><div class="cap">units used (${w.unit})</div></div><div><div class="num">${d.wellbores_labelled.toLocaleString()}</div><div class="cap">wells</div></div><div><div class="num">${d.rows.toLocaleString()}</div><div class="cap">${esc(w.rows)}</div></div><div><div class="num">${pct(d.base_rate)}</div><div class="cap">${esc(w.hit)}</div></div></div>
    <h2>How to read the numbers</h2><p>The <b>rate</b> is the share of ${esc(w.rows)} that ${esc(w.hit)}. It is what the records say, not a direct measurement of the ground. Evidence <b>layers</b> each add or subtract from the starting rate: the formation or group, nearby wells, well logs, later seismic. Hover a layer's status for the test behind it.</p>
    ${note("Status of the evidence", `<p>${LAYERS.map((l) => `${esc(l.title)}: ${tag(l.status, STATUS_WORDS[l.status], evTip(l))}`).join(" · ")}</p>`, "Skill is small. Use estimates as leads to check, not as facts. See <a href='#validation'>Validation</a> for the full test.")}
    <h2>Where to go</h2><table><tr><td><a href="#scene">3D</a><td>wells, estimate sheets and unusual areas in depth<tr><td><a href="#map">Map</a><td>one formation from above<tr><td><a href="#units">Units</a><td>every row, with the evidence behind each estimate<tr><td><a href="#data">Data</a><td>what we hold, where it comes from, and every database table<tr><td><a href="#targets">Targets</a><td>build a new question from any table (e.g. discovery, DST flow, mud weight)<tr><td><a href="#layers">Layers</a>, <a href="#knowledge">Knowledge</a>, <a href="#validation">Validation</a><td>why the estimates can be trusted, or not</table>
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

  async scene() {
    const fl = await api("formations3d"), want = ["NORDLAND GP", "ROGALAND GP", "SELE FM", "HORDALAND GP"].filter((x) => fl.some((f) => f.name === x)).slice(0, 3), w = W();
    const st = { reg: "58,62", sel: new Set(want.length ? want : fl.slice(0, 2).map((f) => f.name)), ex: 12, op: 0.5, wells: true, surf: true, box: true, map: true, ref: "rig", hs: null }; let S = null;
    stage('<div class="fill" id="p3"></div>');
    pane("sc-ctl", "Controls", `<div class="row"><label>Region <select id="reg"><option value="58,62">North Sea (58–62°N)</option><option value="0,90">whole shelf (small)</option><option value="62,69">Norwegian Sea (62–69°N)</option><option value="69,90">Barents Sea (>69°N)</option></select></label></div>
      <div class="row"><label>Depth measured from <select id="ref"><option value="rig">rig floor (as recorded)</option><option value="sea">sea level</option><option value="bed">seabed</option></select></label></div>
      <p class="tip" style="margin:2px 0">Formations (wells)</p><div id="fl" style="max-height:170px;overflow:auto">${fl.slice(0, 16).map((f) => `<label class="chk" style="display:flex"><input type="checkbox" data-f="${esc(f.name)}" ${st.sel.has(f.name) ? "checked" : ""}> ${esc(f.name)} <span class="tip">${f.wells}</span></label>`).join("")}</div>
      <div class="row"><label class="chk"><input type="checkbox" id="cw" checked> wells</label><label class="chk"><input type="checkbox" id="cs" checked> estimate sheets</label><label class="chk"><input type="checkbox" id="cb" checked> unusual areas</label><label class="chk"><input type="checkbox" id="cm" checked> coast and grid</label></div>
      <div class="row"><label class="chk">depth stretch <input type="range" id="ex" min="1" max="40" value="12"> <span id="exv">12×</span></label></div><div class="row"><label class="chk">sheet opacity <input type="range" id="op" min="10" max="100" value="50"></label></div>
      <p class="tip" style="margin:2px 0">Seismic cube: not built (no cube lies over these wells).</p>`, "top:12px;left:12px;width:300px");
    pane("sc-hs", "Unusual areas", '<p class="tip">20 km windows whose rate differs from the formation. Ranked by chance after correcting for the number of windows tested. Click to fly there.</p><div id="hs"></div>', "top:12px;right:12px;width:380px;bottom:12px");
    pane("sc-guide", "What you are looking at", `<p><b>Sticks</b>: one per <i>well × formation</i>, not per whole well. Each is drawn at the well's surface position, straight down, over the depth range where that well passes through the formation (a well crossing three chosen formations gives three stacked sticks). It is the same unit as one dot on the Map; the dot has no depth. Real wells may deviate, so deeper parts can lie off to the side. Colour = share of ${esc(w.rows)} that ${esc(w.hit)} (grey: too few to say).</p><p><b>Sheets</b> are the formation across the area: height = typical depth, colour = model estimate; left out where no well is within 60 km.</p>
      <p><b>Boxes</b> mark 20 km areas that are unusually high (orange) or low (purple) vs the formation.</p><p><b>Depth</b> is measured <i>along the well</i> (not vertical) from the reference you choose: the rig floor (about 25 m above sea level; how Sodir records it), sea level, or the seabed (rig floor height + water depth). The water column is empty space above the seabed. Grid and coast are drawn at depth 0.</p>`, "bottom:12px;left:12px;width:310px", true);
    const refLab = { rig: "Depth below rig floor (m, along well)", sea: "Depth below sea level (m, along well)", bed: "Depth below seabed (m, along well)" };
    const dz = (v, o) => (st.ref === "rig" ? v : st.ref === "sea" ? v - (o.kb ?? 25) : v - (o.kb ?? 25) - (o.wd ?? 0));
    const draw = async () => {
      const q = [...st.sel].join(","); if (!q) { plot($("#p3"), [], {}); $("#hs").innerHTML = '<p class="tip">pick a formation</p>'; return; }
      const [la, lb] = st.reg.split(","); S = await api("scene", { formations: q, lat_min: la, lat_max: lb }); const tr = [], Wl = S.wells, ex = st.ex;
      const sdepth = (s) => (st.ref === "bed" ? s.depth_sb : s.depth.map((r) => r.map((v) => (v == null ? null : st.ref === "sea" ? v - s.kb : v))));
      const xs = Wl.map((w) => w.x).concat(...S.surfaces.map((s) => s.x.flat())), ys = Wl.map((w) => w.y).concat(...S.surfaces.map((s) => s.y.flat()));
      const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), zmax = Math.max(...Wl.map((w) => dz(w.bot, w)), 500);
      if (st.surf) S.surfaces.forEach((s, i) => tr.push({ type: "surface", x: s.x, y: s.y, z: sdepth(s).map((r) => r.map((v) => (v == null ? null : -v))), surfacecolor: s.rate, cmin: 0, cmax: 0.2, opacity: st.op, showscale: i === 0, name: s.formation,
        colorscale: [[0, "rgba(198,219,239,.4)"], [0.4, "#6baed6"], [0.7, "#2171b5"], [1, "#08306b"]], colorbar: { title: "estimate", orientation: "h", len: 0.28, thickness: 9, x: 0.5, y: 0.1, tickformat: ".0%" }, hovertemplate: s.formation + "<br>depth %{z:.0f} m<br>estimate %{surfacecolor:.1%}<extra></extra>" }));
      if (st.wells) { const bins = [["too few trials", css("--mut")], ["<2%", SEQ[0]], ["2–8%", SEQ[1]], ["8–20%", SEQ[2]], [">20%", css("--hot")]], bi = (w) => (w.rows < 1 || w.obs == null ? 0 : w.obs < 0.02 ? 1 : w.obs < 0.08 ? 2 : w.obs < 0.2 ? 3 : 4);
        bins.forEach(([nm, col], b) => { const g = Wl.filter((w) => bi(w) === b); if (!g.length) return; const x = [], y = [], z = [], t = [];
          g.forEach((w) => { const lab = `${w.unit}<br>${w.green} of ${w.rows} ${w.obs == null ? "" : "(" + pct(w.obs) + ")"}<br>${dz(w.top, w).toFixed(0)}–${dz(w.bot, w).toFixed(0)} m ${st.ref === "rig" ? "below rig floor" : st.ref === "sea" ? "below sea level" : "below seabed"}`; x.push(w.x, w.x, null); y.push(w.y, w.y, null); z.push(-dz(w.top, w), -dz(w.bot, w), null); t.push(lab, lab, ""); });
          tr.push({ type: "scatter3d", mode: "lines", x, y, z, text: t, hoverinfo: "text", line: { color: col, width: b === 0 ? 2 : 5 }, name: nm + " (" + g.length + ")" }); }); }
      const hs = S.hotspots;
      if (st.box) hs.forEach((h) => { const r = h.radius_km, c = h.kind === "hot" ? css("--hot") : css("--cold"), sel = st.hs === h.id, a = -dz(h.top, h), b = -dz(h.bot, h);
        tr.push({ type: "mesh3d", x: [h.x - r, h.x + r, h.x + r, h.x - r, h.x - r, h.x + r, h.x + r, h.x - r], y: [h.y - r, h.y - r, h.y + r, h.y + r, h.y - r, h.y - r, h.y + r, h.y + r], z: [a, a, a, a, b, b, b, b], i: [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3], j: [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 0, 4], k: [2, 3, 6, 7, 5, 4, 6, 5, 7, 6, 4, 7], color: c, opacity: sel ? 0.45 : 0.2, flatshading: true, name: h.id, hoverinfo: "text", text: h.text, showlegend: false }); });
      if (st.map) tr.unshift(...(await mapLines({ x0, x1, y0, y1 })));
      const ar = { x: 1, y: Math.max((y1 - y0) / (x1 - x0), 0.15), z: Math.max((zmax / 1000 / ((x1 - x0) || 1)) * ex, 0.1) }; S._g = { x0, x1, y0, y1, zmax, ar }; const zt = [0, 500, 1000, 2000, 3000, 4000, 5000].filter((v) => v <= zmax + 400);
      const axs = (t) => ({ title: t, gridcolor: css("--rule"), color: css("--mut"), backgroundcolor: "rgba(0,0,0,0)", showbackground: false });
      await plot($("#p3"), tr, { margin: { l: 0, r: 0, t: 0, b: 0 }, legend: { orientation: "h", x: 0.3, y: 0.02, bgcolor: "rgba(0,0,0,0)", font: { size: 11 } }, scene: { aspectmode: "manual", aspectratio: ar, camera: { eye: { x: 1.4, y: -1.5, z: 0.8 } }, xaxis: axs("East (km)"), yaxis: axs("North (km)"), zaxis: { ...axs(refLab[st.ref]), tickvals: zt.map((v) => -v), ticktext: zt.map(String) } } });
      $("#hs").innerHTML = hs.length ? hs.map((h) => `<div class="hs ${st.hs === h.id ? "sel" : ""}" data-h="${esc(h.id)}"><b>${esc(h.formation)}</b> · ${tag(h.kind, h.kind === "hot" ? "higher than usual" : "lower than usual")} · ${h.p_adj < 0.05 ? tag("ok", "survives correction") : tag("warnc", "exploratory")}<p><b>${h.lift}×</b> the formation rate · ${h.wells} wells · ${h.rows} trials</p><p>${esc(h.text)}</p></div>`).join("") : '<p class="tip">No window here has enough wells and trials to test.</p>';
    };
    const fly = (id) => { const h = S?.hotspots.find((x) => x.id === id); if (!h) return; st.hs = id; const g = S._g, ar = g.ar, zc = -dz((h.top + h.bot) / 2, h); const c = { x: ((h.x - (g.x0 + g.x1) / 2) / (g.x1 - g.x0)) * ar.x, y: ((h.y - (g.y0 + g.y1) / 2) / (g.y1 - g.y0)) * ar.y, z: ((zc + g.zmax / 2) / g.zmax) * ar.z * 0.5 };
      Plotly.relayout($("#p3"), { "scene.camera": { center: c, eye: { x: c.x + 0.5, y: c.y - 0.6, z: c.z + 0.35 } } }); document.querySelectorAll(".hs").forEach((e) => e.classList.toggle("sel", e.dataset.h === id)); };
    $("#hs").onclick = (e) => { const el = e.target.closest(".hs"); if (el) fly(el.dataset.h); };
    document.querySelectorAll("[data-f]").forEach((c) => (c.onchange = () => { c.checked ? st.sel.add(c.dataset.f) : st.sel.delete(c.dataset.f); draw(); }));
    $("#reg").onchange = (e) => { st.reg = e.target.value; st.hs = null; draw(); }; $("#ref").onchange = (e) => { st.ref = e.target.value; draw(); };
    for (const [id, k] of [["cw", "wells"], ["cs", "surf"], ["cb", "box"], ["cm", "map"]]) $("#" + id).onchange = (e) => { st[k] = e.target.checked; draw(); };
    $("#ex").oninput = (e) => { st.ex = +e.target.value; $("#exv").textContent = st.ex + "×"; if (S) { const g = S._g; g.ar.z = Math.max((g.zmax / 1000 / ((g.x1 - g.x0) || 1)) * st.ex, 0.1); Plotly.relayout($("#p3"), { "scene.aspectratio": g.ar }); } };
    $("#op").oninput = (e) => { st.op = +e.target.value / 100; draw(); }; await draw(); job();
  },

  async map() {
    const fs = (await api("formations")).filter((f) => f.units >= 20), hs = await api("hotspots"), w = W(); let f = fs[0]?.name;
    stage('<div class="fill" id="map"></div>');
    pane("mp-ctl", "Controls", `<div class="row"><label>Group <select id="f">${fs.map((x) => `<option>${esc(x.name)}</option>`).join("")}</select></label></div><div class="row" style="display:block">${layerBox().replaceAll("<label", "<label style='display:flex'")}</div>
      <div class="row"><button class="btn" id="fine" title="Runs on the GPU worker when it is free, else on the CPU">Fine map (GPU)</button></div><p id="mi" class="tip"></p>`, "top:12px;left:12px;width:300px");
    pane("mp-leg", "Legend", `<div id="lg"></div><p><b>Shading</b> = model estimate of the share of ${esc(w.rows)} that ${esc(w.hit)}; darker = higher. <b>Grey</b> = no well of this group within 60 km: no estimate.</p><p><b>Black dots</b> = one per well that crossed this group, at its surface position (the same units as the sticks in 3D; hover for counts). <b>Orange / purple circles</b> = 20 km areas unusually high / low.</p>`, "bottom:24px;left:12px;width:300px");
    const draw = async (fine) => { f = $("#f").value; $("#mi").textContent = fine ? "starting the GPU worker, the first start can take minutes…" : "computing…";
      const m = fine ? await fetch("api/jobs/map?" + new URLSearchParams({ formation: f, res: 0.02, target: TARGET }), { method: "POST" }).then((r) => r.json()) : await api("map", { formation: f, res: 0.1, layers: useNow().join(",") });
      if (m.detail) { $("#mi").textContent = m.detail; return; } $("#mi").textContent = `${m.cells.toLocaleString()} cells · ${m.units} units · ${m.device} · ${m.seconds}s${m.via ? " · via " + m.via : ""}`; job();
      if (map) map.remove(); map = L.map("map", { zoomControl: false }); L.control.zoom({ position: "bottomright" }).addTo(map); osm().addTo(map);
      const dl = m.lat[1] - m.lat[0], dn = m.lon[1] - m.lon[0], mx = Math.max(...m.rate.flat()); $("#lg").innerHTML = rampBar(mx);
      // Leaflet stretches the image linearly in Web Mercator: sample rows evenly in Mercator y, not latitude (else the shading drifts up to ~170 km from the dots)
      const my = (la) => Math.log(Math.tan(Math.PI / 4 + (la * Math.PI) / 360)), la0 = m.lat[0] - dl / 2, la1 = m.lat.at(-1) + dl / 2, H = m.lat.length * 3, cv = document.createElement("canvas"); cv.width = m.lon.length; cv.height = H; const g = cv.getContext("2d");
      for (let r = 0; r < H; r++) { const y = my(la1) - ((r + 0.5) / H) * (my(la1) - my(la0)), la = (360 / Math.PI) * Math.atan(Math.exp(y)) - 90, i = Math.min(m.lat.length - 1, Math.max(0, Math.round((la - m.lat[0]) / dl)));
        for (let j = 0; j < m.lon.length; j++) { const v = m.rate[i][j], far = m.nearest_km[i][j] > m.reach_km; g.fillStyle = far ? "rgba(120,120,120,.10)" : `rgba(31,95,153,${0.1 + 0.85 * v / mx})`; g.fillRect(j, r, 1, 1); } }
      const b = [[la0, m.lon[0] - dn / 2], [la1, m.lon.at(-1) + dn / 2]]; map.fitBounds(b, { padding: [10, 10] }); L.imageOverlay(cv.toDataURL(), b, { opacity: 0.85, className: "px" }).addTo(map);
      hs.filter((h) => h.formation === f).forEach((h) => L.circle([h.lat, h.lon], { radius: h.radius_km * 1000, color: h.kind === "hot" ? "#d95f02" : "#7570b3", weight: 2, fillOpacity: 0.1 }).bindTooltip(`${h.kind === "hot" ? "higher" : "lower"}: ${h.lift}× the group rate, ${h.wells} wells`).addTo(map));
      (m.points || []).forEach((p) => L.circleMarker([p.lat, p.lon], { radius: 2.5, weight: 1, color: "#111", fillColor: "#fff", fillOpacity: 0.9 }).bindTooltip(`${p.unit}: ${p.green} of ${p.rows}`).addTo(map)); L.control.scale().addTo(map); };
    $("#f").onchange = () => draw(false); $("#fine").onclick = () => draw(true); bindLayers(() => draw(false)); await draw(false);
  },

  async units() {
    doc(`<h1>Units</h1><p class="lead">One row is one ${esc(W().unit)}. <b>Trials</b>: ${esc(W().rows)} in it. <b>Successes</b>: how many ${esc(W().hit)}. <b>Observed</b> = successes / trials. <b>Estimate</b> = what the model expects. Click a row for the evidence behind its estimate.</p>
    <div class="row"><input type="search" id="q" placeholder="search well, e.g. 30/6"><select id="f"><option value="">all groups</option></select><select id="s"><option value="rate">sort by estimate</option><option value="observed">sort by observed</option><option value="rows">sort by trials</option></select></div><div class="row">${layerBox()}</div><table id="t"></table>`);
    (await api("formations")).forEach((f) => $("#f").insertAdjacentHTML("beforeend", `<option>${esc(f.name)}</option>`));
    const go = async () => { const u = await api("units", { q: $("#q").value, formation: $("#f").value, sort: $("#s").value, layers: useNow().join(",") }), mx = Math.max(...u.map((x) => x.rate || 0), 0.01);
      $("#t").innerHTML = "<tr><th>well<th>group<th class=r>depth m (MD)<th class=r>trials<th class=r>successes<th class=r>observed<th>estimate</tr>" + u.map((x) => `<tr class="click" data-u="${esc(x.unit)}"><td><b>${esc(x.wellbore)}</b><td>${esc(x.name)}<td class="r mono">${x.top}–${x.bot}<td class=r>${x.coverage}<td class=r>${x.n_green}<td class=r>${pct(x.observed)}<td><span class="track" style="display:inline-block;vertical-align:middle"><div class="bar" style="width:${100 * x.rate / mx}%"></div></span> ${pct(x.rate)}</tr>`).join(""); };
    $("#t").onclick = (e) => { const r = e.target.closest("tr[data-u]"); if (r) location.hash = "unit/" + encodeURIComponent(r.dataset.u); }; $("#q").oninput = go; $("#f").onchange = go; $("#s").onchange = go; bindLayers(go); await go();
  },

  async unit(id) {
    const draw = async () => { const u = await api("unit", { id, layers: useNow().join(",") }), P = u.estimate.parts, w = W(), names = { base: "Starting rate", strat: "Formation or group", spatial: "Nearby wells", logs: "Well logs", seismic: "Seismic" };
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

  async data() {
    const cat = await api("catalog"), st = { t: null, f: [], x: null, y: "", agg: "mean", tab: "chart", off: 0 };
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
        $("#pv").onclick = () => { st.off = Math.max(0, st.off - 100); show(); }; $("#nx").onclick = () => { st.off += 100; show(); }; }
      if (st.tab === "chart") { P.innerHTML = `<div class="row"><label>x <select id="cx">${cols.map((c) => `<option ${c.name === st.x ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></label><label>y <select id="cy"><option value="">(count of rows)</option>${cols.filter((c) => c.numeric).map((c) => `<option ${c.name === st.y ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></label><label>as <select id="ca">${["mean", "sum", "median"].map((a) => `<option ${a === st.agg ? "selected" : ""}>${a}</option>`).join("")}</select></label><span class="tip">click a bar to filter</span></div><div id="ch" style="height:420px"></div>`;
        const run = async () => { st.x = $("#cx").value; st.y = $("#cy").value; st.agg = $("#ca").value; const d = await get("table/chart", { name: st.t, x: st.x, ...(st.y ? { y: st.y, agg: st.agg } : {}) });
          await plot($("#ch"), [{ type: "bar", x: d.x.map((v) => (d.kind === "hist" ? +v.toPrecision(5) : v)), y: d.y, marker: { color: css("--data") }, hovertemplate: "%{x}: %{y:,.2f}<extra></extra>" }], { xaxis: { title: st.x, type: d.kind === "cat" ? "category" : "linear", tickangle: d.kind === "cat" ? -35 : 0 }, yaxis: { title: st.y ? `${st.agg} of ${st.y}` : "rows" }, margin: { l: 60, r: 10, t: 10, b: 110 } });
          $("#ch").on("plotly_click", (e) => { const v = e.points[0].x; if (d.kind === "cat") st.f.push([st.x, "eq", v]); else { st.f.push([st.x, "ge", String(v - d.step / 2)]); st.f.push([st.x, "lt", String(v + d.step / 2)]); } st.off = 0; show(); }); };
        ["#cx", "#cy", "#ca"].forEach((s) => ($(s).onchange = run)); await run(); }
      if (st.tab === "map") { const d = await get("table/points", { name: st.t }); P.innerHTML = d.points.length ? `<p class="tip">${d.points.length.toLocaleString()} points (max 6000) from ${d.lat} / ${d.lon}. Filters apply.</p><div id="map" style="height:560px"></div>` : `<p class="tip">${esc(d.note)}</p>`;
        if (d.points.length) { if (map) map.remove(); map = L.map("map"); osm().addTo(map); const g = L.featureGroup(d.points.map((p) => L.circleMarker([p.lat, p.lon], { radius: 2.5, weight: 1, color: "#111", fillColor: "#fff", fillOpacity: 0.9 }))).addTo(map); map.fitBounds(g.getBounds(), { padding: [10, 10] }); } } };
    $("#tb").onchange = async (e) => { st.t = e.target.value; st.f = []; st.off = 0; if (!st.t) { $("#ex").innerHTML = ""; return; } const c = await api("table/columns", { name: st.t }); st.cols = c.columns; st.n = c.rows; st.x = c.columns[0].name; st.y = ""; st.tab = "chart"; await show(); };
  },

  async targets() {
    const opt = await api("targets/options"), T = await api("targets"), form = { title: "", mode: "well", table: "wellbore_exploration", population: [], success: [], group: "wlbMainArea" };
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
        <div class="row"><label><input type="radio" name="md" value="well" ${form.mode === "well" ? "checked" : ""}> Well</label><label><input type="radio" name="md" value="interval" ${form.mode === "interval" ? "checked" : ""}> Interval (well × formation)</label>
        <label>Table <select id="bt2">${opt[form.mode].map((t) => `<option value="${t.table}" ${t.table === form.table ? "selected" : ""}>${t.table} (${t.rows.toLocaleString()} rows)</option>`).join("")}</select></label>
        ${form.mode === "well" ? `<label>Group by <select id="bg">${g.map((c) => `<option ${c.name === form.group ? "selected" : ""}>${c.name}</option>`).join("")}</select></label>` : '<span class="tip">grouped by formation / group tops</span>'}</div>${filt("population", "Count only rows where (optional)")}${filt("success", "Success when (required)")}`; };
    const tt = () => { const all = [T.builtin, ...T.saved]; $("#tt").innerHTML = "<tr><th>target<th>mode<th class=r>units<th class=r>successes / trials<th>group gain<th>neighbour gain<th></tr>" + all.map((t) => { const s = t.summary;
      return `<tr><td><b>${esc(t.title)}</b>${t.id === TARGET ? ' <span class="tag ok">active</span>' : ""}<td>${t.mode}<td class=r>${s ? s.units.toLocaleString() : "3,762"}<td class=r>${s ? `${s.successes.toLocaleString()} / ${s.trials.toLocaleString()}` : "3,032 / 49,961"}<td>${s ? fmtG(s.gain_formation) : '<span class="tip">see Validation</span>'}<td>${s ? fmtG(s.gain_spatial) : ""}<td><a data-use="${t.id}" style="cursor:pointer">use</a>${t.builtin ? "" : ` · <a data-rmt="${t.id}" style="cursor:pointer">delete</a>`}</tr>`; }).join(""); };
    tt(); draw();
    $("#view").onclick = async (e) => { const a = e.target.closest("[data-use],[data-rmt],[data-pr],[data-add],[data-del]"); if (!a) return;
      if (a.dataset.use) { TARGET = a.dataset.use; localStorage.setItem("target", TARGET); await loadTarget(); T.saved = (await api("targets")).saved; tt(); }
      if (a.dataset.rmt && confirm("Delete this saved target?")) { await fetch("api/targets/" + a.dataset.rmt, { method: "DELETE" }); if (TARGET === a.dataset.rmt) { TARGET = "green_clay"; localStorage.setItem("target", TARGET); } await loadTarget(); Object.assign(T, await api("targets")); tt(); }
      if (a.dataset.pr) { const p = T.presets[+a.dataset.pr]; Object.assign(form, { title: p.title, mode: p.mode, table: p.table, population: [...(p.population || [])], success: [...p.success], group: p.group || "wlbMainArea", words: p.words }); draw(); }
      if (a.dataset.add) { form[a.dataset.add].push(`${tabOf().columns[0].name}|eq|`); draw(); }
      if (a.dataset.del) { const [k, i] = a.dataset.del.split("|"); form[k].splice(+i, 1); draw(); } };
    $("#view").onchange = (e) => { const t = e.target; if (t.name === "md") { form.mode = t.value; form.table = opt[form.mode][0].table; form.population = []; form.success = []; draw(); } if (t.id === "bt2") { form.table = t.value; form.population = []; form.success = []; draw(); } if (t.id === "bg") form.group = t.value;
      if (t.dataset.k) { const f = form[t.dataset.k], i = +t.dataset.i, [c, o = "eq", v = ""] = f[i].split("|"), n = { c, o, v }; n[t.dataset.p] = t.value; f[i] = `${n.c}|${n.o}|${n.v}`; if (t.dataset.p === "c") draw(); } };
    $("#view").oninput = (e) => { if (e.target.id === "bt") form.title = e.target.value; if (e.target.dataset?.p === "v") { const f = form[e.target.dataset.k], i = +e.target.dataset.i, [c, o = "eq"] = f[i].split("|"); f[i] = `${c}|${o}|${e.target.value}`; } };
    $("#go").onclick = async () => { if (!form.success.length) { $("#gs").textContent = "add at least one success condition"; return; } const s = Date.now(), timer = setInterval(() => ($("#gs").textContent = `building and validating (5-fold, 40 km blocks)… ${Math.round((Date.now() - s) / 1000)} s`), 1000);
      const body = { ...form, words: form.words && form.words.rows ? form.words : { rows: form.mode === "well" ? "wells" : "rows", hit: "meet the success condition", short: "success", unit: form.mode === "well" ? "wellbore" : "well x formation interval" } };
      const r = await fetch("api/targets/build", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }); clearInterval(timer); const j = await r.json();
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

  async knowledge() {
    const k = await api("kb"); doc(`<h1>Knowledge</h1><p class="lead">Textbook geology rules, each with its source and a test against our data. <b>Agrees</b>: the data lean the way the rule says. <b>Disagrees</b>: the other way. <b>Inconclusive</b>: the data cannot tell. A rule is never trusted blindly and never hidden when the data disagree. AUC = chance that a positive row has a higher value than a negative one (0.5 = no difference); about one false hit in seven checks is expected by chance.</p>
    ${k.length ? `<table><tr><th>rule<th>source status<th>data says<th>numbers and sources</tr>${k.map((r) => `<tr><td><b>${esc(r.id)}</b> ${esc(r.statement)}${r.caveat ? `<br><span class="tip">${esc(r.caveat)}</span>` : ""}<td>${tag(r.status === "sourced" ? "helps" : r.status === "inferred" ? "no_evidence" : "muted", r.status.replace("_", " "))}<td>${tag(r.verdict)}<td><span class="mono">${esc(r.numbers)}</span><br>${r.sources.map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.says)}</a>`).join("<br>")}</tr>`).join("")}</table>` : '<div class="note"><b>None yet</b>No sourced rules have been written for this target. Rules live in backend/se/knowledge/rules/*.yaml and need a source and a status.</div>'}`);
  },

  async validation() {
    const r = await api("validation"), d = r.delta, ab = r.ablation;
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

  async contradictions() {
    const c = await api("contradictions"), t = (rows, kind) => `<table><tr><th>unit<th class=r>trials<th class=r>successes<th class=r>model said<th class=r>${kind}</tr>${rows.slice(0, 25).map((x) => `<tr class="click" data-u="${esc(x.unit)}"><td>${esc(x.unit)}<td class=r>${x.coverage}<td class=r>${x.n_green}<td class=r>${pct(x.p_full)}<td class="r mono">${(x.tail_many ?? x.tail_none)?.toExponential(1)}</tr>`).join("")}</table>`;
    doc(`<h1>Contradictions</h1><p class="lead">Where the records and the model disagree most. Either the model misses something, the record is unusual, or it is worth a second look. Candidates for review, not errors. “Chance” is the probability of a result this extreme if the model were right.</p><h2>Much higher than expected</h2>${t(c.reported_but_unexpected, "chance")}<h2>Expected, but none recorded</h2>${t(c.expected_but_not_reported, "chance")}`);
    $(".doc").onclick = (e) => { const r = e.target.closest("tr[data-u]"); if (r) location.hash = "unit/" + encodeURIComponent(r.dataset.u); };
  },

  async log() { const l = await api("log"); doc(`<h1>Decision log</h1><p class="lead">Every choice, number, mistake and correction, in order, with the reasoning. Wrong turns stay marked so the work can be backtracked.</p><div class="md">${marked.parse(l.markdown)}</div>`); },
};
init();
