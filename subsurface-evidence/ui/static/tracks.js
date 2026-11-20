// Source evidence stays at its original depth and on its original borehole.
const TRACK_FOR_SCREEN = Object.freeze({
  "50fe1fd2c6ab16d51bc3e1bb7bf4c573d2bcaf65fa5864fa9ad95f442f89eb7c": "d92d14a3bce5e33d44fddec575a7e544ed392cbdb99d2dc39e64746b813bb5ca"
});
async function trackJSON(path, pin) {
  const r = await fetch("api/tracks" + path + (pin ? "?version=" + encodeURIComponent(pin) : ""));
  if (!r.ok) throw new Error(`Track data unavailable (HTTP ${r.status}); no other release substituted.`);
  const d = await r.json();
  if (!/^[a-f0-9]{64}$/.test(d.version) || (pin && pin !== d.version)) throw new Error("Track version mismatch.");
  return d;
}

async function loadWellTrack(el, id, pin, focusVersion = null) {
  el.textContent = "Loading depth evidence…";
  try {
    const d = await trackJSON(`/wells/${id}`, pin);
    if (String(d.well?.npdid) !== String(id) || (focusVersion && focusVersion !== d.focus_version))
      throw new Error("Borehole or focused receipt mismatch.");
    if (el.isConnected) showWellTrack(el, d);
  } catch (e) { if (el.isConnected) el.textContent = e.message; }
}

function showWellTrack(el, d) {
  const w = d.well, v = d.version, reports = d.reports;
  const safe = u => typeof u === "string" && /^https:\/\/factpages\.sodir\.no\//.test(u);
  const kinds = ["formation","placement","formation test","reservoir test","equipment test","scenario"];
  const events = [...w.events];
  if (w.scenario?.longest_bounds_md_m) {
    const [top, base] = w.scenario.longest_bounds_md_m;
    events.push({kind:"scenario", top, base, label:`Longest joint run: ${w.scenario.longest_joint_m} m; ${w.scenario.state}`,
      source:"interval scenario"});
  }
  const links = (e) => {
    const ref = reports[e.source];
    if (ref) {
      const link = e.source === "sleipner" ? `api/tracks/sources/sleipner?version=${v}#page=${e.page}` : ref.url;
      return `<a href="${esc(link)}" target="_blank" rel="noopener">${e.source === "sleipner" ? "Open public PDF" : "Publisher access, original archive"} · PDF p.${e.page}</a>
        <br>${esc(ref.member || ref.path)} · ${esc(ref.credit)}<br>SHA-256 <code>${esc(ref.sha256)}</code>`;
    }
    if (e.kind === "scenario") return `<a href="#screen/${w.npdid}/${d.focus_version}">Pinned Smeaheia scenario and assumptions</a>`;
    return `${esc(e.source)}${e.also_source ? " + " + esc(e.also_source) : ""} · NPDID ${w.npdid} + ${esc(w.name)}. ${safe(w.url) ? `<a href="${esc(w.url)}" target="_blank" rel="noopener">Sodir well record</a>` : ""}`;
  };
  const placed = events.map((e,i) => [e,i]).filter(([e]) => Number.isFinite(e.top) && Number.isFinite(e.base));
  const zmax = Math.max(1, ...placed.map(([e]) => e.base));
  const y = z => 45 + 345*z/zmax;
  const lines = kinds.map((k,i) => `<text x="${92+i*109}" y="22" text-anchor="middle">${esc(k)}</text>`).join("");
  const bars = placed.map(([e,i]) => {
    const x = 68 + kinds.indexOf(e.kind)*109, h = Math.max(3, y(e.base)-y(e.top));
    return `<rect data-track-row="${i}" x="${x}" y="${y(e.top)}" width="47" height="${h}" fill="${e.kind === "scenario" ? "var(--hot)" : e.kind === "placement" ? "var(--cold)" : "var(--data)"}" stroke="var(--paper)" stroke-width=".7">
      <title>${esc(e.label)} · ${e.top}–${e.base} m. Open source row.</title></rect>`;
  }).join("");
  const depth = e => e.top == null ? "Not positioned" : e.top === e.base ? `${e.top} m` : `${e.top}–${e.base} m`;
  el.innerHTML = `<article class="well-track" data-track-id="${w.npdid}"><h2>${esc(w.name)} · depth evidence</h2>
    <p>NPDID ${w.npdid} · ${esc(w.kind)} · status ${esc(w.status || "unknown")}. <b>Present barrier integrity: unknown.</b></p>
    ${w.overlaps.length ? `<h3>Reported MD overlap, not tested isolation</h3><ul>${w.overlaps.map(o =>
      `<li>${esc(o.placement)} × ${esc(o.formation)}: <b>${o.m} of ${o.formation_m} m</b>.</li>`).join("")}</ul><p class="tip">${esc(w.overlaps[0].datum)}</p>` : ""}
    ${placed.length ? `<svg class="depth-lanes" viewBox="0 0 705 410" role="img" aria-label="Depth increasing downwards. Source rows follow the chart.">
      ${lines}${[0, .25, .5, .75, 1].map(f => `<line x1="52" x2="682" y1="${y(zmax*f)}" y2="${y(zmax*f)}" stroke="var(--rule)"/><text x="48" y="${y(zmax*f)+4}" text-anchor="end">${Math.round(zmax*f)}</text>`).join("")}${bars}</svg>` : "<p>No positioned intervals in the checked sources. Do not infer absence.</p>"}
    <p class="tip">Metres down the well, not vertical depth. Registry MD and reported operational metres are shown side by side, not assumed registered. Tests with unknown interval stay off the axis. LOT/FIT and DST are formation or reservoir tests, not plug tests.</p>
    <p><b>Missing evidence:</b> ${!events.some(e=>e.kind==="formation") ? "No valid reported formation interval. " : ""}
    ${!events.some(e=>e.kind==="placement") ? "No reviewed placement interval. " : ""}
    No interval-specific test of a placed cement plug is established by the records curated here. A missing record is not a failed test.</p>
    ${w.scenario ? `<p>Separate rock + pressure scenario: ${esc(w.scenario.state)}. <a href="#screen/${w.npdid}/${d.focus_version}">View wellhead overlay and assumptions</a>.</p>` : "<p>Rock + pressure rule: not evaluated for this well. No result transferred from nearby wells.</p>"}
    <h3>Source rows</h3>${events.map((e,i) => `<details data-row-id="${i}"><summary>${esc(e.kind)} · ${esc(depth(e))} · ${esc(e.label)}</summary>
      <p>${e.unit_id ? `Unit ID ${e.unit_id}. ` : ""}${e.emw_g_cm3 ? `Reported equivalent density ${e.emw_g_cm3} g/cm³. ` : ""}${esc(e.evidence || "")} ${esc(e.note || "")} ${esc(e.datum || "")}</p><p>${links(e)}</p></details>`).join("")}
    <details><summary>Document leads (${w.leads.length}); not findings</summary><ul>${w.leads.map(r =>
      `<li>${safe(r.url) ? `<a href="${esc(r.url)}">${esc(r.title)}</a>` : esc(r.title)} · ${esc(r.source)} · ${esc(r.type)} ${esc(r.item || "")}</li>`).join("")}</ul></details>
    <p class="tip">${w.excluded} depth rows excluded by depth checks. <a href="api/tracks/wells/${w.npdid}?version=${v}">Exact well receipt</a> ·
    <a href="#tracks/${w.npdid}/${v}">Link to this track</a>. Registry: Sodir. Smeaheia and Sleipner: Equinor and Gassnova.</p></article>`;
  el.querySelector(".depth-lanes")?.addEventListener("click", e => {
    const i = e.target.closest("[data-track-row]")?.dataset.trackRow;
    if (i !== undefined) {
      const row = el.querySelector(`[data-row-id="${i}"]`); row.open = true; row.scrollIntoView({block:"center"});
    }
  });
}

async function mountTracks(arg, live) {
  const [id, pin, ...extra] = arg.split("/");
  if ((id && !/^\d+$/.test(id)) || (pin !== undefined && !/^[a-f0-9]{64}$/.test(pin)) || extra.length)
    throw new Error("Invalid track address.");
  const d = await trackJSON("", pin);
  if (!live()) return;
  if (id && !d.index.some(r => String(r[0]) === id)) throw new Error("Borehole not in this track release.");
  doc(`<h1>Well depth tracks</h1><p>All registered boreholes are searchable, including records without usable coordinates. Choose an area or search by well name or Sodir ID.</p>
    <p><label>Area <select id="wt-area">${Object.entries(d.scopes).map(([k,v])=>`<option value="${esc(k)}">${esc(v)}</option>`).join("")}</select></label>
    <label>Well <input id="wt-search" type="search" placeholder="Name or NPDID"></label> <label><input id="wt-pa" type="checkbox"> P&amp;A status only</label></p>
    <p class="tip">Regions and Sleipner use registry wellhead boxes. Northern Lights: 12 km around 31/5-7. Smeaheia: six audited survey-footprint candidates. These are selection areas, not storage boundaries.</p>
    <p id="wt-coverage"></p><p id="wt-count" aria-live="polite"></p><select id="wt-well" aria-label="Matching boreholes"></select> <button class="btn" id="wt-prev">Previous 100</button> <button class="btn" id="wt-next">Next 100</button>
    <div id="wt-result"></div>`);
  const area = $("#wt-area"), search = $("#wt-search"), pa = $("#wt-pa"), select = $("#wt-well");
  area.value = "all";
  let page = 0;
  function choose(i) {
    const root = $("#wt-result"), node = document.createElement("div");
    root.replaceChildren(node);
    if (!i) { history.replaceState(null, "", "#tracks"); root.textContent = "No matching boreholes."; return; }
    history.replaceState(null, "", `#tracks/${i}/${d.version}`);
    loadWellTrack(node, i, d.version);
  }
  function results(preferred) {
    const q = search.value.trim().toLowerCase();
    const c = d.coverage?.[area.value];
    $("#wt-coverage").textContent = c ? `Area coverage before filters: ${c.positioned} of ${c.wells} wells have positioned records; ${c.placements} have reviewed cement placements. ${c.leads_only} have document leads only.` : "";
    const rows = d.index.filter(([i,n,s,areas]) => (area.value==="all" || areas.includes(area.value))
      && (!pa.checked || s==="P&A") && (!q || n.toLowerCase().includes(q) || String(i)===q));
    if (preferred) page = Math.max(0, Math.floor(rows.findIndex(r=>String(r[0])===preferred)/100));
    const batch = rows.slice(page*100, page*100+100);
    select.innerHTML = batch.map(r=>`<option value="${r[0]}">${esc(r[1])} · ${r[0]}</option>`).join("");
    if (preferred) select.value = preferred;
    $("#wt-count").textContent = `${rows.length} matching boreholes${batch.length ? ` · showing ${page*100+1}–${page*100+batch.length}` : ""}`;
    $("#wt-prev").disabled = page===0; $("#wt-next").disabled = (page+1)*100>=rows.length;
    choose(select.value);
  }
  area.onchange = pa.onchange = search.oninput = () => { page=0; results(); };
  $("#wt-prev").onclick = () => { page--; results(); };
  $("#wt-next").onclick = () => { page++; results(); };
  select.onchange = () => choose(select.value);
  results(id || "5839");
}
