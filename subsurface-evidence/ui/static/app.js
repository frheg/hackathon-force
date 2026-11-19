// Subsurface Evidence UI. One file, no build. Everything shown comes from /api with its numbers (hide nothing).
const $ = (s) => document.querySelector(s), api = (p, q = {}) => fetch("api/" + p + "?" + new URLSearchParams(q)).then((r) => r.json());
const pct = (x) => (x == null ? "–" : (100 * x).toFixed(1) + "%"), f2 = (x) => (x == null ? "–" : (+x).toFixed(2));
const esc = (s) => String(s ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
let META, LAYERS, use = null, map = null;
const tag = (s, t) => `<span class="tag ${s}">${t || s.replace("_", " ")}</span>`;
const PAGES = { start: "Start here", map: "Map", units: "Units", layers: "Evidence layers", knowledge: "Knowledge", validation: "Validation", contradictions: "Contradictions", log: "Decision log" };

async function init() {
  META = await api("meta"); LAYERS = await api("layers"); use = LAYERS.filter((l) => l.on_by_default).map((l) => l.name);
  $("#links").innerHTML = Object.entries(PAGES).map(([k, v]) => `<a data-p="${k}">${v}</a>`).join("");
  $("#links").onclick = (e) => e.target.dataset.p && (location.hash = e.target.dataset.p);
  $("#burger").onclick = () => $("#nav").classList.toggle("hide");
  $("#theme").onclick = () => { const d = document.documentElement; d.dataset.theme = d.dataset.theme === "dark" ? "light" : "dark"; };
  $("#top").innerHTML = `device ${META.device} · worker ${META.worker ? "on" : "off"} · layers on: ${use.join(", ")}`;
  addEventListener("hashchange", route); route();
}
function route() {
  const p = (location.hash.slice(1) || "start").split("/")[0];
  document.querySelectorAll("nav a").forEach((a) => a.classList.toggle("on", a.dataset.p === p));
  (PAGES_FN[p] || PAGES_FN.start)(location.hash.split("/").slice(1).join("/"));
}
const layerBox = () => `<span class="mut">layers:</span> ` + LAYERS.filter((l) => l.built).map((l) => `<label><input type="checkbox" data-l="${l.name}" ${use.includes(l.name) ? "checked" : ""}> ${l.title} ${tag(l.status)}</label>`).join(" ");
function bindLayers(re) { document.querySelectorAll("[data-l]").forEach((c) => (c.onchange = () => { use = [...document.querySelectorAll("[data-l]")].filter((x) => x.checked).map((x) => x.dataset.l); $("#top").innerHTML = `layers on: ${use.join(", ")}`; re(); })); }

const PAGES_FN = {
  async start() {
    const d = META.data;
    $("#view").innerHTML = `<h2>Start here</h2><p class="sub">${esc(META.target_text)}</p>
    <div class="card"><b>What this is</b><br>An evidence engine: each data type is a layer that adds a log-odds term; the sum is calibrated into a rate. Every number is traceable to a layer, a rule or a log entry.</div>
    <div class="card"><b>The honest state</b><br>Formation prior: ${tag(META.status.strat)} · neighbours: ${tag(META.status.spatial)} · logs: ${tag(META.status.logs)} · seismic: ${tag(META.status.seismic)}.<br>
    Skill is small (see Validation). Reported rate depends on how much was described, not only on geology. Treat estimates as leads, not facts.</div>
    <div class="card"><b>Data</b><pre>${esc(JSON.stringify(d, null, 1))}</pre></div>
    <div class="card"><b>Validation</b> blocked ${META.block_km} km spatial folds, ${META.folds} folds, whole-well bootstraps. Full numbers: Validation.</div>`;
  },
  async map() {
    const fs = (await api("formations")).filter((f) => f.units >= 20);
    $("#view").innerHTML = `<h2>Map</h2><p class="sub">Estimated green share of clay rows. Grey = beyond the neighbour reach (no local evidence). Dots = training units.</p>
    <div class="row"><select id="f">${fs.map((f) => `<option>${esc(f.name)}</option>`).join("")}</select>${layerBox()}<button id="fine">fine map (worker/GPU)</button><span id="mi" class="mut"></span></div><div id="map"></div>`;
    const draw = async (fine) => {
      const f = $("#f").value; $("#mi").textContent = "computing…";
      const m = fine ? await fetch("api/jobs/map?" + new URLSearchParams({ formation: f, res: 0.02 }), { method: "POST" }).then((r) => r.json()) : await api("map", { formation: f, res: 0.1, layers: use.join(",") });
      if (m.detail) { $("#mi").textContent = m.detail; return; }
      $("#mi").textContent = `${m.cells.toLocaleString()} cells · ${m.units} units · ${m.device} · ${m.seconds}s · reach ${m.reach_km} km`;
      if (map) map.remove(); map = L.map("map"); L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OSM" }).addTo(map);
      const dl = m.lat[1] - m.lat[0], dn = m.lon[1] - m.lon[0], mx = Math.max(...m.rate.flat());
      const cv = document.createElement("canvas"); cv.width = m.lon.length; cv.height = m.lat.length; const g = cv.getContext("2d");
      m.rate.forEach((row, i) => row.forEach((v, j) => { const far = m.nearest_km[i][j] > m.reach_km; g.fillStyle = far ? "rgba(120,120,120,.12)" : `rgba(31,111,92,${0.15 + 0.8 * v / mx})`; g.fillRect(j, m.lat.length - 1 - i, 1, 1); }));
      const b = [[m.lat[0] - dl / 2, m.lon[0] - dn / 2], [m.lat.at(-1) + dl / 2, m.lon.at(-1) + dn / 2]];
      map.invalidateSize(); map.fitBounds(b, { padding: [10, 10] }); L.imageOverlay(cv.toDataURL(), b, { opacity: 0.8, className: "px" }).addTo(map);
      (m.points || []).forEach((p) => L.circleMarker([p.lat, p.lon], { radius: 3, weight: 1 }).bindTooltip(`${p.unit}: ${p.green}/${p.rows} rows`).addTo(map));
      L.control.scale().addTo(map);
    };
    $("#f").onchange = () => draw(false); $("#fine").onclick = () => draw(true); bindLayers(() => draw(false)); draw(false);
  },
  async units() {
    $("#view").innerHTML = `<h2>Units</h2><p class="sub">One wellbore × formation interval. Click a row for the full evidence breakdown.</p><div class="row"><input id="q" placeholder="search well"><select id="f"><option value="">all formations</option></select><select id="s"><option>rate</option><option>observed</option><option>rows</option></select>${layerBox()}</div><div class="card"><table id="t"></table></div>`;
    (await api("formations")).forEach((f) => $("#f").insertAdjacentHTML("beforeend", `<option>${esc(f.name)}</option>`));
    const go = async () => { const u = await api("units", { q: $("#q").value, formation: $("#f").value, sort: $("#s").value, layers: use.join(",") });
      $("#t").innerHTML = "<tr><th>unit<th>rows<th>green<th>observed<th>estimate<th>depth m</tr>" + u.map((x) => `<tr class="click" data-u="${esc(x.unit)}"><td>${esc(x.unit)}<td>${x.coverage}<td>${x.n_green}<td>${pct(x.observed)}<td>${pct(x.rate)}<td>${x.top}–${x.bot}</tr>`).join(""); };
    $("#t").onclick = (e) => { const r = e.target.closest("tr[data-u]"); if (r) location.hash = "unit/" + encodeURIComponent(r.dataset.u); };
    $("#q").oninput = go; $("#f").onchange = go; $("#s").onchange = go; bindLayers(go); go();
  },
  async unit(id) {
    const u = await api("unit", { id: decodeURIComponent(id), layers: use.join(",") });
    $("#view").innerHTML = `<h2>${esc(u.unit)}</h2><p class="sub">${u.level} · ${u.top}–${u.bot} m · ${u.lat.toFixed(3)}, ${u.lon.toFixed(3)}</p><div class="row"><a href="#units">← units</a>${layerBox()}</div>
    <div class="card"><b>Observed</b> ${u.green_rows} of ${u.described_clay_rows} described clay rows name a green mineral (${pct(u.observed_rate)}). ${u.labelled ? "" : "<span class='mut'>Too few rows: not used for training.</span>"}<br>
    <b>Estimate</b> ${pct(u.estimate.rate)} (uncalibrated ${pct(u.estimate.raw_rate)}) · out-of-fold estimate ${pct(u.validation_estimate)}</div>
    <div class="card"><b>Evidence (log-odds; right = raises)</b><table>${u.estimate.parts.map((p) => `<tr><td>${p.layer}${p.status ? " " + tag(p.status) : ""}<td style="width:260px">${p.llr == null ? "<span class='mut'>silent</span>" : `<div class="bar ${p.llr < 0 ? "neg" : ""}" style="width:${Math.min(100, Math.abs(p.llr) * 25)}%"></div>`}<td>${p.llr == null ? "" : f2(p.llr)}<td>${esc(p.why)}</tr>`).join("")}</table></div>
    <div class="card"><b>Log medians in this interval</b><pre>${esc(JSON.stringify(u.logs))}</pre></div>`;
    bindLayers(() => PAGES_FN.unit(id));
  },
  async layers() {
    $("#view").innerHTML = `<h2>Evidence layers</h2><p class="sub">One layer = one data type = one log-odds term. Add a data type by adding a layer.</p>` + LAYERS.map((l) => `<div class="card"><b>${l.title}</b> ${tag(l.status)} ${l.on_by_default ? tag("on", "on by default") : tag("not_built", "off by default")}<br>${esc(l.doc)}<pre>${esc(JSON.stringify(l.params, null, 1))}</pre></div>`).join("");
  },
  async knowledge() {
    const k = await api("kb");
    $("#view").innerHTML = `<h2>Knowledge</h2><p class="sub">Sourced rules, each tested against the data. Never trusted, never hidden. About one false hit in seven is expected by chance.</p><div class="card"><table><tr><th>rule<th>source status<th>data says<th>numbers</tr>` +
      k.map((r) => `<tr><td><b>${r.id}</b> ${esc(r.statement)}<br><span class="mut">${esc(r.caveat)}</span>${r.sources.map((s) => `<br><a href="${s.url}" target="_blank" rel="noopener">${esc(s.says)}</a>`).join("")}<td>${tag(r.status === "sourced" ? "helps" : "no_evidence", r.status)}<td>${tag(r.verdict)}<td>${esc(r.numbers)}</tr>`).join("") + "</table></div>";
  },
  async validation() {
    const r = await api("validation"), d = r.delta;
    const tb = (rows, h) => `<table><tr>${h.map((x) => `<th>${x}`).join("")}</tr>${rows.map((x) => `<tr>${x.map((c) => `<td>${typeof c === "number" ? c.toFixed(4) : esc(c)}`).join("")}</tr>`).join("")}</table>`;
    $("#view").innerHTML = `<h2>Validation</h2><p class="sub">Held-out wells in blocked ${r.block_km} km folds. Gain = binomial deviance reduction vs a constant rate. Intervals resample whole wells.</p>
    <div class="card"><b>Ablation</b>${tb(Object.entries(r.ablation).map(([k, v]) => [k, v.units, v.deviance_gain, v.auc_in_coverage_bins]), ["layers", "units", "deviance gain", "AUC in coverage bins"])}</div>
    <div class="card"><b>Does a layer help? (gain difference, 90% interval)</b>${tb(Object.entries(d).map(([k, v]) => [k, v.delta_gain, `[${v.p05.toFixed(4)}, ${v.p95.toFixed(4)}]`, v.significant ? "significant" : "not significant"]), ["comparison", "delta", "interval", ""])}</div>
    ${["ell", "a", "k", "C"].map((k) => `<div class="card"><b>Sweep ${k} (value, gain, AUC)</b><pre>${esc(JSON.stringify(r["sweep_" + k]))}</pre></div>`).join("")}
    <div class="card"><b>Everything else (raw)</b><pre>${esc(JSON.stringify(r, null, 1).slice(0, 20000))}</pre></div>`;
  },
  async contradictions() {
    const c = await api("contradictions");
    $("#view").innerHTML = `<h2>Contradictions</h2><p class="sub">Where the model and the reports disagree most (binomial tail). Candidates for review, not errors.</p>` + Object.entries(c).map(([k, v]) => `<div class="card"><b>${k.replaceAll("_", " ")}</b><pre>${esc(JSON.stringify(v.slice(0, 25), null, 1))}</pre></div>`).join("");
  },
  async log() {
    const l = await api("log"); $("#view").innerHTML = `<h2>Decision log</h2><p class="sub">Append-only. Every choice, number and mistake.</p><div class="card md">${marked.parse(l.markdown)}</div>`;
  },
};
init();
