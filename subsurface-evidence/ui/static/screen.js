// The decision view has no chart CDN, target-model or GPU dependency.
function strictRuleStyle(result) {
  switch (result?.state) {
    case "candidate interval": return {key:"candidate", ink:"var(--good)", mark:"+", text:"Qualifying interval"};
    case "not seen on supported metres": return {key:"below", ink:"var(--bad)", mark:"−", text:"Not seen on supported metres"};
    case "insufficient evidence": return {key:"unknown", ink:"var(--mut)", mark:"?", text:"Insufficient evidence"};
    default: return {key:"unrated", ink:"var(--mut)", mark:"·", text: result ? "Unrecognised rule state" : "Rule not evaluated here"};
  }
}

async function mountSmeaheia(routeArg, live) {
  const [id, pin, ...extra] = routeArg.split("/");
  if ((id && !/^\d+$/.test(id)) || (pin !== undefined && !/^[0-9a-f]{64}$/.test(pin)) || extra.length) {
    doc('<h1>Invalid well or receipt</h1><a href="#screen">Open the Smeaheia screen</a>'); return;
  }
  const endpoint = "api/screen/smeaheia";
  let d;
  try {
    const r = await fetch(endpoint + (pin ? "?version=" + pin : ""));
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    d = await r.json();
    if (![1, 2].includes(d.schema) || !d.wells?.length || !/^[a-f0-9]{64}$/.test(d.version) || (pin && pin !== d.version)
        || (d.schema === 2 && (!d.interval_rule?.parameters || !d.wells.every(w => w.interval_screen?.strict))))
      throw new Error("unsupported receipt");
  } catch (e) {
    if (live()) doc(`<h1>Smeaheia screen unavailable</h1><p>The pinned evidence could not be loaded (${esc(e.message)}). No other build was substituted.</p>
      <a href="#earth">Open the 3D subsurface model</a>`);
    return;
  }
  if (!live()) return;
  const local = w => w.surveys.some(s => s.in_hull);
  const candidates = d.wells.filter(local), references = d.wells.filter(w => !local(w));
  const both = w => w.markers.every(m => m.picks.length);
  let well = id ? d.wells.find(w => String(w.npdid) === id) : candidates.find(w => w.report_claim) || candidates[0];
  if (!well) { doc('<h1>Well not in this screen</h1><p>Not a negative finding.</p><a href="#screen">Open the review queue</a>'); return; }
  const source = `${endpoint}?version=${d.version}`, validation = d.validation;
  const url = s => /^https:\/\/factpages\.sodir\.no\//.test(s) ? esc(s) : null;
  const opts = ws => ws.map(w => `<option value="${w.npdid}">${esc(w.wellbore)} · ${both(w) ? "both markers reported" : "marker evidence incomplete"}</option>`).join("");
  const loc = ref => `${esc(ref.member.split("/").pop())}, PDF p.${ref.pdf_page}`;
  const round = n => Number(n).toFixed(0);
  const states = candidates.map(w => strictRuleStyle(w.interval_screen?.strict).key);
  const colourControls = d.schema === 2 ? `<label><input id="sc-colour" type="checkbox" aria-controls="sc-scene sc-legend"> Colour wellheads by rock + pressure rule</label>
    <p id="sc-legend" class="tip" hidden>Inside footprints only: <b style="color:var(--good)">+ Green: qualifying interval (${states.filter(k=>k==="candidate").length})</b>;
    <b style="color:var(--bad)">− Red: not seen on supported metres (${states.filter(k=>k==="below").length})</b>;
    <b style="color:var(--mut)">? Grey: insufficient evidence (${states.filter(k=>k==="unknown").length})</b>.
    Outside reference labelled separately. Colours do not show cement, pressure-test outcomes or barrier integrity.</p>` : "";
  doc(`<div class="screen"><h1>Smeaheia legacy-well review</h1>
    <p class="lead">Which wells report the reservoir or seal, and what needs checking?</p>
    <div class="screen-layout"><section aria-label="Survey view">
    <p><b>${candidates.length} wellheads</b> in two indexed survey footprints. ${candidates.filter(both).length} report both markers. ${references.length} outside reference, not counted.</p>
    <label for="sc-well">Review borehole</label> <select id="sc-well"><optgroup label="Inside indexed footprint">${opts(candidates)}</optgroup><optgroup label="Outside reference only">${opts(references)}</optgroup></select>
    <svg id="sc-scene" viewBox="0 0 640 370" aria-label="Rotatable 3D survey footprints, wellheads, sampled paths and supported formation picks"></svg>
    <div class="row"><label>Rotate <input type="range" min="-180" max="180" value="-20" id="sc-rotate"></label>
    <label><input type="checkbox" id="sc-plan"> Plan view</label></div>
    ${colourControls}
    <p class="tip">Outlines at sea level, heads at registry water depth. Lines: sampled FORCE positions only. Gold: reservoir top. Purple: seal top. No inferred vertical well sticks. EPSG:3035 km; depth m TVDSS (+ down), exaggerated 6× in 3D.</p>
    <p class="tip">Smeaheia: <a href="https://doi.org/10.11582/2021.00012">Equinor and Gassnova</a>. Well records: Sodir.</p>
    <details><summary>Historical depth estimate</summary><label><input type="checkbox" id="sc-surface"> Show frozen Sognefjord grid nodes</label>
    <p class="tip">${esc(d.historical_surface.note)} Point at a node for depth and model SD.</p></details>
    </section><section id="sc-detail" aria-live="polite"></section></div>
    <details id="sc-validation"><summary>Why there is no new depth prediction</summary>
    <p>${esc(validation.target)} ${esc(validation.design)}</p>
    <p>${validation.scored} of ${validation.registry_wells_with_top} Horda boreholes scored across ${validation.blocks} blocks.
    Mean absolute error: <b>${round(validation.median_mae_m)} m</b> training median; <b>${round(validation.nearest_mae_m)} m</b> nearest well.
    Gain ${round(validation.gain_m)} m (positive is better). Paired 90% resampling range: wells ${validation.well_gain90_m.map(round).join(" to ")} m; blocks ${validation.block_gain90_m.map(round).join(" to ")} m.</p>
    <p>Excluded: ${Object.entries(validation.excluded).map(([k,v]) => `${v} ${esc(k)}`).join("; ")}. ${esc(validation.limit)}</p></details>
    <details><summary>Scope, sources and receipt</summary>
    <p>Membership uses the convex hulls of decimated GN1101 and TNE01 traces, not a licence, plume or containment boundary. Laterals can enter from outside, and hulls can include gaps. ${d.registry_screen.excluded_unresolved_coordinates} registry positions were unresolved in the original shelf-wide scan. No completeness or risk ranking is implied.</p>
    <p>Marker roles: ${loc(d.rule.sources.site)}. ${esc(d.rule.sources.site.finding)}</p>
    <p>${esc(d.credit)} <a href="https://doi.org/10.11582/2021.00012">Released source and terms</a>. No reselling.</p>
    <p><a id="sc-receipt" href="${source}">Exact rows, folds, source paths and hashes (JSON)</a> ·
    <a href="api/earth/snapshot?region=pilot&amp;build=${esc(d.earth_build)}">Earth build ${esc(d.earth_build)}</a></p></details>
    </div>`);
  const screen = $(".screen");
  const get = s => $(s, screen);
  const draw = () => {
    const colour = !!get("#sc-colour")?.checked;
    if (get("#sc-legend")) get("#sc-legend").hidden = !colour;
    drawSmeaheia(get("#sc-scene"), d, well, +get("#sc-rotate").value, get("#sc-plan").checked, get("#sc-surface").checked, colour);
  };
  function selectWell(w, updateLink) {
    well = w;
    if (updateLink) history.replaceState(null, "", `#screen/${w.npdid}/${d.version}`);
    get("#sc-well").value = w.npdid;
    const allPlaced = w.markers.every(m => m.picks.length && m.picks.every(p => p.top_position));
    const sourceLink = u => u ? `<a href="${u}">FactPages record</a>` : "FactPages URL unavailable";
    get("#sc-detail").innerHTML = `<h2>${esc(w.wellbore)}</h2><p>${local(w) ? "Footprint candidate" : "Outside reference only"} ·
      ${w.surveys.map(s => esc(s.id.toUpperCase())).join(", ")} · NPDID ${w.npdid}</p>
      <table><thead><tr><th>Marker</th><th>Reported interval<br>m MD from rig</th><th>Top on sampled path<br>m TVDSS</th></tr></thead><tbody>
      ${w.markers.map(m => `<tr><td>${esc(m.name)}<br><small>${esc(m.role)}</small></td>
        <td>${m.picks.map(p => `${p.top_md_m}–${p.base_md_m}`).join("<br>") || "Unknown"}</td>
        <td>${m.picks.map(p => p.top_position ? p.top_position.tvdss.toFixed(1) : "Unknown").join("<br>") || "Unknown"}</td></tr>`).join("")}</tbody></table>
      <p class="tip">Sodir interpreted formation intervals; vertical positions interpolate adjacent FORCE samples only. No MD-to-TVD substitution. Rig reference ${w.rkb_m == null ? "unknown" : `${w.rkb_m} m above sea level`}.</p>
      <p><b>Barrier integrity: unknown.</b> Storage-boundary crossing: unknown. Registry status ${esc(w.registry_status)}${w.completion_year ? `; completed ${w.completion_year}` : ""}. Status is not a barrier test.</p>
      ${w.report_claim ? `<p><b>Reported operations:</b> ${esc(w.report_claim.finding)}<br><small>${loc(w.report_claim)} · ${esc(w.report_claim.section)}</small></p>` : "<p>No page-verified abandonment claim in this receipt.</p>"}
      ${TRACK_FOR_SCREEN[d.version] ? `<details id="sc-track"><summary>Compare formation, cement and test depths</summary><div></div></details>` : ""}
      ${d.schema === 2 ? intervalPanel(w.interval_screen, d.interval_rule) :
        '<p id="sc-interval">Historical receipt: no rock and pressure assessment in this version.</p>'}
      <p><b>Next check:</b> ${!both(w) ? "Obtain the exact-borehole formation picks and directional survey." :
        !allPlaced ? "Obtain directional stations at the missing top depths." : "Check the abandonment record and barrier-test evidence at the reported intervals."}</p>
      <p class="tip">${w.surveys.map(s => esc(s.datum_issue || s.tie_status)).join(" ")} ${d.independent_ties} independent local time-depth ties verified; no seismic conversion.</p>
      <details><summary>Source rows and documents</summary><p>${sourceLink(url(w.url))} · ${esc(w.registry_table)} / ${w.npdid}. Formation rows: wellbore_formation_top, NPDID ${w.npdid}, ${w.markers.map(m => m.unit_id).join(" / ")} (FORMATION) and MD bounds above.</p>
      <p>Sampled positions: ${w.path_segments.length ? w.path_segments.map(seg => `${seg[0][3].toFixed(1)}–${seg.at(-1)[3].toFixed(1)} m MD`).join("; ") : "none in this source"}. Frozen force_paths.parquet, ${esc(w.wellbore)}. The receipt includes brackets and separates gaps.</p>
      <p>Registry-listed documents (${w.documents.length}); links are not verified findings:</p><ul>${w.documents.map(r =>
        `<li>${url(r.url) ? `<a href="${url(r.url)}">${esc(r.name)}</a>` : esc(r.name)} · ${esc(r.kind)}</li>`).join("")}</ul></details>`;
    const track = get("#sc-track");
    if (track) track.ontoggle = () => {
      if (track.open && !track.dataset.loaded) { track.dataset.loaded = "1"; loadWellTrack(track.querySelector("div"), w.npdid, TRACK_FOR_SCREEN[d.version], d.version); }
    };
    draw();
  }
  get("#sc-well").onchange = e => selectWell(d.wells.find(w => w.npdid === +e.target.value), true);
  get("#sc-scene").onclick = e => { const point = e.target.closest("[data-well]");
    if (point) selectWell(d.wells.find(w => w.npdid === +point.dataset.well), true); };
  get("#sc-rotate").oninput = get("#sc-plan").onchange = get("#sc-surface").onchange = draw;
  if (get("#sc-colour")) get("#sc-colour").onchange = draw;
  selectWell(well, false);
}

function intervalPanel(s, rule) {
  const p = rule.parameters, v = s.strict, g = s.group_screen, ex = s.example_in_longest;
  const n = (v, digits = 0) => v == null ? "unknown" : Number(v).toFixed(digits);
  const run = v => v.longest_joint_m == null ? "unknown" : `${v.longest_joint_m} m`;
  const bounds = v.longest_bounds_md_m;
  return `<section id="sc-interval"><p><b>Rock + pressure scenario: ${esc(v.state)}.</b>
    ${bounds ? `Longest joint run: ${bounds[0]}–${bounds[1]} m MD (${run(v)}).` : ""}
    ${s.missing.map(esc).join(" ")}</p>
    <details><summary>Inputs, pressure assumptions and sensitivity</summary>
    <p>Tests the overburden above the reported Sognefjord top, not the reservoir itself. No neighbour transfer, CO₂ injection forecast or barrier verdict.</p>
    <p>1. <b>Rock:</b> on the same log sample, gamma &gt;${p.gamma_min_api} API, deep resistivity &lt;${p.resistivity_max_ohm_m} Ω·m and sonic &gt;${p.sonic_min_us_ft} µs/ft.
    ${s.rock_signature_bins} of ${s.rock_log_bins} bins with all three measured curves above the target meet this signature.</p>
    <p>2. <b>Load:</b> top ${n(s.target_md_m)} m MD / ${n(s.target_tvd_rkb_m, 1)} m TVD from rig.
    Mud weight at top ${n(s.mud_at_target_g_cm3, 3)}; assumed reservoir equivalent density ${n(s.assumed_pp_g_cm3, 3)} g/cm³.
    Gas gradient ${p.gas_g_cm3} g/cm³. Compare required load with capacity interpolated between leak-off tests, not a local pressure measurement.
    ${s.pressure_window_log_bins} of ${s.pressure_supported_log_bins} positioned log bins with a pressure comparison meet the load.</p>
    <p>3. <b>Overlap:</b> need ${p.continuous_m} adjacent 1 m bins meeting both conditions. ${v.assessable_bins} bins assessable with all three curves and pressure;
    ${v.joint_bins} meet both. Longest: ${run(v)}. Missing bins break runs.
    Sensitivity, longest run: allowing missing sonic ${run(s.optional_sonic)}; keeping sonic but subtracting no overbalance from mud ${run(s.zero_overbalance)}.</p>
    ${ex ? `<p>One sample in the longest run: ${n(ex.md, 2)} m MD; GR ${n(ex.gr_api, 1)} API, RDEP ${n(ex.rdep_ohm_m, 2)} Ω·m, DTC ${n(ex.dtc_us_ft, 1)} µs/ft.
      Available ${n(ex.available_emw, 3)} vs required ${n(ex.required_emw, 3)} g/cm³ (both modelled).</p>` : ""}
    <p><b>Separate formation check:</b> ${g.in_window_m == null ? "unknown; no pressure-supported group overlap." :
      `${g.in_window_m} of ${g.supported_m} supported Hordaland/Rogaland metres meet the pressure rule (${g.meets_total ? "meets" : "below"} ${p.group_total_m} m total).`}
    Group metres need not be continuous and do not establish clay or integrity.</p>
    <p class="tip">Sources in receipt: FORCE 2020 train.csv (exact well and MD); Sodir wellbore_mud, wellbore_casing_and_lot and wellbore_formation_top.
    <a href="${esc(rule.source)}">Nature's Plug rule</a>, adapted. These scenarios have not been validated against local barrier outcomes.</p></details></section>`;
}

function drawSmeaheia(svg, d, selected, angle, plan, showSurface, colour) {
  const view = plan ? Math.PI/2 : .48, a = plan ? 0 : angle * Math.PI / 180;
  const project = ([x,y,z]) => [x*Math.cos(a) - y*Math.sin(a),
    -(x*Math.sin(a) + y*Math.cos(a))*Math.sin(view) + z*.006*Math.cos(view)];
  const heads = d.wells.filter(w => w.water_m != null);
  const rings = d.footprints.map(f => f.xy.map(p => [...p,0]));
  const points = [...rings.flat(), ...heads.map(w => [...w.head_xy,w.water_m]), ...d.wells.flatMap(w => w.path_segments.flat())];
  const extent = points.map(project), xs = extent.map(p => p[0]), ys = extent.map(p => p[1]);
  const xmin = Math.min(...xs), xmax = Math.max(...xs), ymin = Math.min(...ys), ymax = Math.max(...ys);
  const scale = Math.min(524 / (xmax-xmin || 1), 288 / (ymax-ymin || 1));
  const pt = p => { const [x,y] = project(p); return [320 + (x-(xmin+xmax)/2)*scale, 185 + (y-(ymin+ymax)/2)*scale]; };
  const coords = p => pt(p).map(n => n.toFixed(2)).join(",");
  const circle = (p,r,c,title,attr="") => { const [x,y] = pt(p); return `<circle cx="${x}" cy="${y}" r="${r}" fill="${c}" ${attr}><title>${esc(title)}</title></circle>`; };
  let scene = rings.map((r,i) => `<polygon points="${r.map(coords).join(" ")}" fill="none" stroke="var(--mut)" stroke-dasharray="4 3"><title>${esc(d.footprints[i].id.toUpperCase())} indexed hull, sea-level projection</title></polygon>`).join("");
  if (showSurface) {
    const s = d.historical_surface;
    for (let j=0; j<s.y.length; j++) for (let i=0; i<s.x.length; i++) if (s.z[j][i] !== null)
      scene += circle([s.x[i],s.y[j],s.z[j][i]],2,"var(--mut)",`Historical Sognefjord top ${s.z[j][i]} m TVDSS; model SD ${s.sd[j][i]} m`, 'class="sc-grid"');
  }
  for (const w of d.wells) {
    for (const seg of w.path_segments) scene += `<polyline points="${seg.map(coords).join(" ")}" fill="none" stroke="var(--data)" stroke-width="${w === selected ? 3 : 1.5}"><title>${esc(w.wellbore)} sampled positions, ${seg[0][3]} to ${seg.at(-1)[3]} m MD</title></polyline>`;
    for (const m of w.markers) for (const pick of m.picks) if (pick.top_position) {
      const {x,y,tvdss} = pick.top_position;
      scene += circle([x,y,tvdss],w === selected ? 5 : 3,m.unit_id === 151 ? "#b77700" : "#9656b0",`${w.wellbore}: ${m.name}, ${tvdss.toFixed(1)} m TVDSS`, `data-well="${w.npdid}"`);
    }
  }
  for (const w of heads) {
    const p = [...w.head_xy,w.water_m], [x,y] = pt(p);
    const state = colour ? strictRuleStyle(w.interval_screen?.strict) : null;
    const ref = state && !w.surveys.some(s=>s.in_hull) ? " (ref)" : "";
    const title = `${w.wellbore}${ref}, registry water depth ${w.water_m} m${state ? ". Rock + pressure: " + state.text : ""}`;
    scene += circle(p,w === selected ? 6 : 4,state?.ink || "var(--paper)",title, `data-well="${w.npdid}" ${state ? `data-rule="${state.key}"` : ""} stroke="var(--ink)" stroke-width="2"`);
    scene += `<text x="${x+7}" y="${y-5}" fill="var(--ink)" font-size="12" data-well="${w.npdid}">${state ? state.mark + " " : ""}${esc(w.wellbore)}${ref}</text>`;
  }
  svg.innerHTML = `${scene}<text x="12" y="350" fill="var(--mut)" font-size="12">${plan ? "Plan: north up, east right" : `3D: azimuth rotation ${angle}°, vertical stretch 6×`}</text>`;
}
