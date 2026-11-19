// Data Atlas: one view per dataset (what it is, the key numbers, charts with how to read them, the words it uses),
// an overview of how the datasets connect, a well lookup across all of them, and a glossary.
;(() => {
  const $ = (id) => document.getElementById(id)
  const view = $('view')
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim()
  const num = (v, d = 0) => (v === null || v === undefined || Number.isNaN(+v) ? '–' : (+v).toLocaleString('en-US', { maximumFractionDigits: d }))
  const gb = (b) => (b >= 1e9 ? `${num(b / 1e9, 1)} GB` : b >= 1e6 ? `${num(b / 1e6, 0)} MB` : b ? `${num(b / 1e3, 0)} kB` : '–')
  const get = (u) => fetch(u).then(async (r) => { const d = await r.json().catch(() => ({})); if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`); return d })
  const S = (i) => css(`--s${i}`)

  // ---------- glossary: every term the pages use, in plain words ----------
  const G = {
    wellbore: ['Wellbore', 'One hole drilled from the surface. A well can have several wellbores (sidetracks). Names look like 15/9-19 A: quadrant 15, block 9, well 19, sidetrack A.', 'All datasets join on this name'],
    well: ['Well', 'The drilling location; may contain several wellbores. People often say well when they mean wellbore.'],
    sidetrack: ['Sidetrack', 'A new wellbore drilled out of an existing one, usually to reach a different target. Marked by a letter after the name (15/9-19 A).'],
    exploration: ['Exploration well', 'Drilled to find out whether oil or gas is there (wildcat) or how much (appraisal).'],
    wildcat: ['Wildcat', 'An exploration well into an untested trap. Most find nothing.'],
    appraisal: ['Appraisal well', 'Drilled after a discovery, to measure its size and quality.'],
    development: ['Development well', 'Drilled on a field that is being produced: producers, injectors and observation wells.'],
    field: ['Field', 'A discovery that has been approved for production, with its own development plan (PDO).'],
    discovery: ['Discovery', 'Oil or gas proven by a well. It becomes a field when a development is approved; many wait for years.'],
    licence: ['Production licence (PL)', 'The permit from the state to explore and produce in an area, held by a group of companies. Named PL 001, PL 1064.'],
    relinquishment: ['Relinquishment report', 'Written when companies give a licence back. It explains what they studied, what they drilled and why they stopped: a record of failed ideas.'],
    operator: ['Operator', 'The company that runs the work on behalf of the licence partners.'],
    sodir: ['Sodir', 'The Norwegian Offshore Directorate (formerly NPD), the state agency that collects and publishes data from the shelf.'],
    npd: ['NPD', 'Norwegian Petroleum Directorate, renamed Sodir in 2024. NPDID is its numeric id for a wellbore, field or licence.'],
    npdid: ['NPDID', 'Sodir\'s numeric id for an object (wellbore, field, licence). More reliable to join on than names.'],
    factpages: ['FactPages', 'Sodir\'s public register of the shelf, published as tables.'],
    diskos: ['Diskos', 'The national data bank for the shelf, run by Sodir and the companies: well reports, logs, seismic. Public data is released after a confidentiality period.'],
    ncs: ['NCS', 'Norwegian Continental Shelf: the seabed areas under Norway: North Sea, Norwegian Sea and Barents Sea.'],
    spud: ['Spud', 'The moment drilling of a wellbore starts. "Spud date" or entry date.'],
    td: ['TD', 'Total depth: the deepest point the wellbore reached, usually as measured depth.'],
    md: ['MD', 'Measured depth: length along the wellbore from the reference point. In a deviated well it is longer than the vertical depth.'],
    tvd: ['TVD', 'True vertical depth: straight down from the reference point. What matters for pressure.'],
    kb: ['KB / RKB', 'Kelly bushing: the depth reference on the rig floor, some tens of metres above sea level. Depths are usually below RKB.'],
    content: ['Content', 'What the well found: OIL, GAS, OIL/GAS, GAS/CONDENSATE, SHOWS (traces only) or DRY (nothing).'],
    dry: ['Dry well', 'A well that found no movable oil or gas.'],
    shows: ['Shows', 'Traces of oil or gas seen in cuttings, cores or gas readings, but not enough to produce.'],
    condensate: ['Condensate', 'Light liquid that drops out of gas as pressure falls. Counted with gas or as its own product.'],
    ngl: ['NGL', 'Natural gas liquids: ethane, propane, butane taken out of the gas stream.'],
    oe: ['o.e. (oil equivalents)', 'One number for all products: 1 Sm3 of oil, or 1,000 Sm3 of gas, is 1 Sm3 o.e. MSm3 o.e. is a million of those (6.3 million barrels).'],
    sm3: ['Sm3', 'Standard cubic metre: a volume at surface conditions (15 °C, 1 atm). One Sm3 of oil is 6.29 barrels.'],
    reserves: ['Reserves', 'Oil and gas the companies have decided to produce. Remaining reserves are what is left to produce.'],
    recoverable: ['Recoverable', 'The part of the oil and gas in place that can be produced. Usually 20 to 60 percent of what is there.'],
    production: ['Production', 'Monthly volumes per field reported to Sodir: oil, gas, NGL, condensate, and water produced along with them.'],
    water: ['Produced water', 'Formation water that comes up with oil. Rises as a field ages; a sign of decline.'],
    facility: ['Facility', 'A platform, subsea template, FPSO or other installation.'],
    tieback: ['Tie-back', 'Producing a small discovery through an existing platform instead of building a new one.'],
    pa: ['P&A', 'Plug and abandonment: sealing a well for good with cement plugs when it is no longer used. Norway has about 2,900 wells to plug.'],
    formation: ['Formation', 'A named rock layer with one character, e.g. the Draupne Formation (source rock) or Sleipner Formation. Groups are larger units, members smaller.'],
    group: ['Group (stratigraphy)', 'A set of formations, e.g. the Viking Group or the Nordland Group.'],
    top: ['Formation top', 'The depth where a formation starts in a wellbore, picked by a geologist from logs and cuttings.'],
    lithostratigraphy: ['Lithostratigraphy', 'Dividing the rock column into named units (groups, formations) by rock type.'],
    lithology: ['Lithology', 'The rock type: sandstone, shale, limestone and so on.'],
    sandstone: ['Sandstone', 'Rock of sand grains. Often the reservoir: the pore space between grains holds the oil and gas.'],
    shale: ['Shale / claystone', 'Fine-grained mud rock. Low permeability: often the seal above a reservoir, or the source rock.'],
    limestone: ['Limestone / chalk', 'Rock of calcium carbonate. The chalk fields (Ekofisk) produce from it.'],
    marl: ['Marl', 'A mix of clay and carbonate.'],
    halite: ['Halite / anhydrite', 'Salt and gypsum-like evaporites, laid down when seas dried out. Salt flows and shapes traps.'],
    reservoir: ['Reservoir', 'Porous, permeable rock that holds oil or gas under a seal.'],
    seal: ['Seal (cap rock)', 'Tight rock above a reservoir that stops oil and gas escaping.'],
    source: ['Source rock', 'Organic-rich rock (on the NCS mostly the Draupne / Kimmeridge shale) that made the oil and gas when buried and heated.'],
    trap: ['Trap', 'A shape in the rocks (a dome, a fault block) where oil and gas collect under a seal.'],
    porosity: ['Porosity', 'The share of the rock that is pore space, in percent. Good sandstone reservoirs: 20 to 30 %. Says how much fluid the rock can hold.'],
    permeability: ['Permeability', 'How easily fluid flows through the rock, in millidarcy (mD). Below 1 mD is tight; above 100 mD is good. Spans many orders of magnitude, so it is plotted on a log scale.'],
    md_unit: ['mD (millidarcy)', 'The unit of permeability. 1 darcy = 1,000 mD.'],
    saturation: ['Saturation (Sw, So)', 'The share of the pore space filled with water (Sw) or oil (So). Sw = 30 % means 70 % hydrocarbons.'],
    klinkenberg: ['Klinkenberg correction', 'Gas flows more easily than liquid through tiny pores, so air permeability reads high. The correction converts it to an equivalent liquid permeability.'],
    helium: ['Helium porosity', 'Porosity measured by pushing helium into a dried plug. The lab standard.'],
    grain_density: ['Grain density', 'Density of the rock grains alone, g/cm3. Quartz sand is 2.65; higher means heavier minerals.'],
    core: ['Core', 'A cylinder of rock cut from the wellbore and brought up. The ground truth for what the rock is.'],
    plug: ['Core plug', 'A small cylinder (about 2.5 to 3.8 cm) drilled out of a core and measured in the lab, every 25 cm or so.'],
    cuttings: ['Cuttings', 'Rock chips the drill bit makes, carried up by the mud and examined on the rig.'],
    log: ['Well log', 'A measurement recorded continuously down the wellbore by a tool on a cable (wireline) or in the drill string (LWD). One value every 15 cm.'],
    las: ['LAS', 'Log ASCII Standard: the plain-text file format for well logs.'],
    gr: ['GR (gamma ray)', 'Natural radioactivity of the rock, in API units. Shale is high (above 80 to 100), clean sand and carbonate low. The first log people look at.'],
    rhob: ['RHOB (bulk density)', 'Density of rock plus fluids, g/cm3. Lower in porous rock and in gas.'],
    nphi: ['NPHI (neutron porosity)', 'Hydrogen content read as porosity. High in shale (bound water) and low in gas.'],
    'density-neutron': ['Density-neutron crossplot', 'RHOB against NPHI. Sand, shale, limestone and dolomite fall in different places; gas pulls points up-left. Lithology from two logs.'],
    rdep: ['RDEP (deep resistivity)', 'How well the rock resists electric current, ohm·m, deep into the rock. Salt water conducts, oil and gas do not: high resistivity in a porous rock suggests hydrocarbons. Log scale.'],
    dtc: ['DTC (sonic)', 'Time for a sound wave to cross a foot of rock, µs/ft. Slower (higher) in porous and soft rock. Links logs to seismic.'],
    pef: ['PEF (photoelectric factor)', 'Tells minerals apart: quartz about 1.8, calcite 5, dolomite 3.'],
    cali: ['CALI (caliper)', 'Hole diameter. Wider than the bit means the wall has caved, and the other logs may read wrong there.'],
    sp: ['SP (spontaneous potential)', 'Natural voltage in the hole; shifts in permeable beds.'],
    facies: ['Facies', 'A body of rock with one character and origin, e.g. channel sand or marine shale. On seismic: a region with one texture.'],
    'force2020': ['FORCE 2020 competition', 'A machine-learning contest in 2020: predict lithology from logs on wells the models never saw. The winner scored -0.47 on its penalty metric.'],
    seismic: ['Seismic', 'An image of the subsurface made from sound: a ship fires air guns, sound echoes back from rock layers, and the echoes are stacked into a 3D cube.'],
    inline: ['Inline / crossline', 'The two horizontal directions of a 3D seismic grid. An inline is a vertical slice along the shooting direction; a crossline is at right angles.'],
    trace: ['Trace', 'One vertical column of a seismic cube: the echo recorded at one surface position, sample by sample.'],
    twt: ['TWT', 'Two-way time: how long sound took to go down and back, in milliseconds. Seismic depth axes are usually time, not metres.'],
    amplitude: ['Amplitude', 'How strong the echo is. Bright spots (very strong) can mean gas.'],
    segy: ['SEG-Y', 'The standard file format for seismic: a text header, a binary header, then trace after trace with its own header.'],
    fault: ['Fault', 'A crack where rock blocks have moved past each other. Faults make traps and also leak.'],
    ddr: ['DDR (daily drilling report)', 'The rig\'s report of each 24 hours: every activity with start and end time, depth reached and a comment.'],
    npt: ['NPT (non-productive time)', 'Rig time spent not making progress: waiting, repairs, stuck pipe, losses. A rig costs USD 300k to 500k a day, so NPT is expensive.'],
    rop: ['ROP', 'Rate of penetration: how fast the bit drills, metres per hour.'],
    trip: ['Trip', 'Pulling the drill string out of the hole and running it back, e.g. to change the bit. Hours with no new hole.'],
    casing: ['Casing', 'Steel pipe cemented into the hole in steps (30", 20", 13 3/8", 9 5/8"...) to hold the wall and isolate pressures.'],
    shoe: ['Casing shoe', 'The bottom of a casing string. A leak-off test is done just below it.'],
    lot: ['LOT (leak-off test)', 'Pressure test below a casing shoe: pump until the rock starts taking fluid. Gives the strongest mud the hole can hold, the top of the drilling window.'],
    mud: ['Drilling mud', 'Heavy fluid pumped down the drill pipe: cools the bit, carries cuttings up, and its weight holds back formation pressure. Mud weight in g/cm3 (sg).'],
    window: ['Drilling window', 'The mud weights between pore pressure (too light: influx, kick) and fracture pressure (too heavy: losses). The narrower, the harder the well.'],
    kick: ['Kick', 'Formation fluid entering the wellbore because the mud is too light. Left alone it becomes a blowout.'],
    dst: ['DST (drill-stem test)', 'Flowing a zone through the drill string to measure rate, pressure and fluid. The proof that a reservoir produces.'],
    vsp: ['VSP', 'Vertical seismic profile: seismic recorded with receivers in the wellbore, to tie well depths to seismic time.'],
    biostratigraphy: ['Biostratigraphy', 'Dating rock by the microfossils in it (palynology, foraminifera).'],
    completion_report: ['Completion report (final well report)', 'The document written after a well is finished: what was drilled, the rocks met, logs, cores, tests, problems and the result. The richest single source per well.'],
    ocr: ['OCR', 'Optical character recognition: reading text out of scanned page images. Old reports were typed and scanned, so OCR text has errors and garbled pages.'],
    gibberish: ['Gibberish page', 'A page where OCR produced no real text: scanned logs, charts, maps, tables. Flagged in the text corpus so you can drop or treat them differently.'],
    rag: ['RAG', 'Retrieval-augmented generation: find the passages that answer a question, then let a language model answer from them with citations.'],
    passage: ['Passage (chunk)', 'A piece of a document, a few paragraphs long, that a search returns.'],
    entailed: ['Supported (entailed)', 'In DISKOS-QA: the reference answer really follows from the passage. 938 of 1,027 questions are supported.'],
    recall: ['Recall@5', 'How often the right passage is among the top 5 search results.'],
    sar: ['SAR', 'Synthetic aperture radar: a satellite sends radar pulses and images the sea surface, day or night through cloud. Oil smooths the waves, so slicks show as dark patches.'],
    seep: ['Seep', 'Oil or gas leaking naturally from the seabed. Slicks far from installations can point to an active petroleum system below.'],
    ccs: ['CCS', 'Carbon capture and storage: injecting CO2 into deep rock (Northern Lights, Smeaheia). Old wells nearby must not leak.'],
    pdo: ['PDO', 'Plan for development and operation: the plan the state approves before a field is built.'],
    hpht: ['HPHT', 'High pressure, high temperature wells: above about 690 bar or 150 °C. Narrow windows and costly.'],
    quadrant: ['Quadrant and block', 'The NCS is divided in quadrants (1° by 1°), each in 12 blocks. Wellbore 15/9-19 sits in quadrant 15, block 9.'],
  }
  const T = (key, text) => `<span class="term" data-t="${key}">${esc(text ?? G[key]?.[0] ?? key)}</span>`
  const tip = $('tip')
  document.addEventListener('mouseover', (e) => {
    const t = e.target.closest('.term')
    if (!t || !G[t.dataset.t]) return
    const [name, def, note] = G[t.dataset.t]
    tip.innerHTML = `<b>${esc(name)}</b>${esc(def)}${note ? `<div class="muted" style="margin-top:.3rem">${esc(note)}</div>` : ''}`
    tip.hidden = false
    const r = t.getBoundingClientRect()
    tip.style.left = `${Math.min(innerWidth - 356, Math.max(8, r.left))}px`
    tip.style.top = `${r.bottom + 8 + tip.offsetHeight > innerHeight ? r.top - tip.offsetHeight - 8 : r.bottom + 8}px`
  })
  document.addEventListener('mouseout', (e) => { if (e.target.closest('.term')) tip.hidden = true })
  const terms = (keys) => `<div class="panel"><div class="panel-head"><h2>Words this data uses</h2><span class="hint">Hover any dotted word for its meaning</span></div><div class="terms">${keys.map((k) => `<span class="chip">${T(k)}</span>`).join('')}</div></div>`

  // ---------- chart helpers ----------
  function layout(extra = {}) {
    const ink = css('--ink-2'), grid = css('--line'), muted = css('--muted')
    const axis = (a = {}) => ({ gridcolor: grid, zerolinecolor: grid, linecolor: grid, tickfont: { color: muted, size: 11 }, title: { font: { color: muted, size: 12 } }, automargin: true, ...a })
    const base = { paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { family: 'Geist, Inter, system-ui, sans-serif', color: ink, size: 12 },
      margin: { l: 56, r: 16, t: 10, b: 44 }, bargap: 0.18, hoverlabel: { bgcolor: css('--panel-2'), bordercolor: css('--line-2'), font: { color: css('--ink') } },
      legend: { orientation: 'h', y: 1.12, font: { color: ink } }, xaxis: axis(), yaxis: axis() }
    for (const [k, v] of Object.entries(extra)) base[k] = /^[xy]axis\d*$/.test(k) ? axis(v) : v
    return base
  }
  const cfg = { responsive: true, displaylogo: false, displayModeBar: false, modeBarButtonsToRemove: ['lasso2d', 'select2d', 'toggleSpikelines'] }
  const plot = (id, data, lay = {}) => Plotly.newPlot(id, data, layout(lay), cfg)
  const bar = (list, { color = S(1), h = false, name = '', x = 'k', y = 'n', fmt = '' } = {}) => ({
    type: 'bar', orientation: h ? 'h' : 'v', name, marker: { color, line: { width: 0 } },
    x: h ? list.map((d) => d[y]) : list.map((d) => d[x]), y: h ? list.map((d) => d[x]) : list.map((d) => d[y]),
    hovertemplate: h ? `%{y}: %{x:,}${fmt}<extra></extra>` : `%{x}: %{y:,}${fmt}<extra></extra>`,
  })
  const histo = (hd, color = S(1), share = false) => {
    const tot = hd.counts.reduce((a, b) => a + b, 0) || 1
    const ys = share ? hd.counts.map((c) => (c / tot) * 100) : hd.counts
    const mids = hd.edges.slice(0, -1).map((e, i) => (e + hd.edges[i + 1]) / 2)
    const xs = hd.log ? mids.map((m) => 10 ** m) : mids
    // on a log axis each bar is as wide as its bin in real units, so the bars look even
    const width = hd.log ? hd.edges.slice(0, -1).map((e, i) => (10 ** hd.edges[i + 1] - 10 ** e) * 0.85) : (hd.edges[1] - hd.edges[0]) * 0.9
    return { type: 'bar', x: xs, y: ys, marker: { color }, width, hovertemplate: share ? '%{x:.3~g}: %{y:.1f} %<extra></extra>' : '%{x:.3~g}: %{y:,}<extra></extra>' }
  }
// how is one sentence, or [what it is, how to read it]
  const panel = (title, body, how = '', hint = '') => `<div class="panel"><div class="panel-head"><h2>${title}</h2>${hint ? `<span class="hint">${hint}</span>` : ''}</div>${body}${Array.isArray(how) ? `<p class="how"><b>What it is:</b> ${how[0]}</p><p class="how"><b>How to read it:</b> ${how[1]}</p>` : how ? `<p class="how"><b>How to read it:</b> ${how}</p>` : ''}</div>`
  const K = () => Math.max(1, Math.min(1.7, innerHeight / 800)) // charts grow with the window height
  const chart = (id, h = 320) => `<div id="${id}" class="chart" style="height:${Math.round(h * K())}px"></div>`
  const kpis = (list) => `<div class="kpis" style="margin:1rem 0">${list.map(([v, k, cls = '']) => `<div class="kpi ${cls}"><div class="v">${v}</div><div class="k">${k}</div></div>`).join('')}</div>`
  const table = (cols, rows_, max = 400) => `<div class="table-wrap" style="max-height:${max}px"><table><thead><tr>${cols.map(([h, , c]) => `<th class="${c || ''}">${h}</th>`).join('')}</tr></thead><tbody>${rows_.map((r) => `<tr>${cols.map(([, f, c]) => `<td class="${c || ''}">${f(r)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`
  const plain = (what, why, use) => `<div class="plain"><div><h3>What it is</h3><p>${what}</p></div><div><h3>Why it matters</h3><p>${why}</p></div><div><h3>What you could build</h3><p>${use}</p></div></div>`
  function map(el, points, colorOf, popup, view = [63, 6], zoom = 4.5) {
    const dark = window.theme.isDark()
    const esri = 'https://server.arcgisonline.com/ArcGIS/rest/services'
    const [base, ref, native] = dark ? ['Canvas/World_Dark_Gray_Base', 'Canvas/World_Dark_Gray_Reference', 15] : ['Ocean/World_Ocean_Base', 'Ocean/World_Ocean_Reference', 9]
    const m = L.map(el, { scrollWheelZoom: false, zoomSnap: 0.5, preferCanvas: true }).setView(view, zoom)
    L.tileLayer(`${esri}/${base}/MapServer/tile/{z}/{y}/{x}`, { maxZoom: 13, maxNativeZoom: native, attribution: 'Esri, GEBCO, NOAA' }).addTo(m)
    L.tileLayer(`${esri}/${ref}/MapServer/tile/{z}/{y}/{x}`, { maxZoom: 13, maxNativeZoom: native }).addTo(m)
    const ring = css('--bg')
    for (const p of points) if (p.lat != null && p.lon != null) L.circleMarker([p.lat, p.lon], { radius: 3.5, weight: 0.6, color: ring, fillColor: colorOf(p), fillOpacity: 0.9 }).bindPopup(popup(p)).addTo(m)
    return m
  }
  const legend = (items) => `<div class="legend" style="margin-top:.6rem">${items.map(([c, l]) => `<span><i style="background:${c}"></i>${esc(l)}</span>`).join('')}</div>`
  const wellLink = (w) => `<a href="#well/${encodeURIComponent(w)}">${esc(w)}</a>`

  // ---------- frame ----------
  let catalog = null, focus = false
  const VIEWS = {}
  async function frame() {
    catalog = await get('api/catalog')
    focus = catalog.focus?.length > 0
    const item = (d) => `<a href="#${d.id}" data-v="${d.id}">${esc(d.name)}<span class="count ${d.downloading ? 'busy' : ''}">${d.downloading ? 'loading' : d.present ? gb(d.bytes) : 'not yet'}</span></a>`
    $('side').innerHTML = `
      <a class="brand" href="#overview"><span class="brand-mark"></span><span><b>${focus ? 'Seismic Atlas' : 'Data Atlas'}</b></span></a>
      <nav class="nav"><a href="#overview" data-v="overview">Overview</a>${focus ? '<a href="#learn" data-v="learn">Start here</a><a href="#resolution" data-v="resolution">Resolution &amp; granularity</a>' : '<a href="#connect" data-v="connect">How the data connects</a><a href="#well" data-v="well">Well lookup</a>'}<a href="#glossary" data-v="glossary">Glossary</a></nav>
      <div class="nav-group"><div>${focus ? 'Official (from the mail)' : 'From the organisers'}</div><nav class="nav">${catalog.datasets.filter((d) => d.origin === 'mail').map(item).join('')}</nav></div>
      <div class="nav-group"><div>${focus ? 'Stand-in (found earlier)' : 'Found before the event'}</div><nav class="nav">${catalog.datasets.filter((d) => d.origin === 'earlier').map(item).join('')}</nav></div>
      <div class="side-foot"><span id="theme-slot"></span><a href="../">Subsurface Studio</a><p style="margin:.5rem 0 0">${focus ? 'Seismic only for the hackathon task; the other datasets are hidden (FOCUS in sketches/atlas.py).' : 'The data behind the tools, explained.'}</p></div>`
    $('theme-slot').replaceWith(window.theme.button())
    route()
  }
  async function route() {
    const [name, ...rest] = decodeURIComponent(location.hash.slice(1) || 'overview').split('/')
    for (const a of document.querySelectorAll('.side a[data-v]')) a.classList.toggle('on', a.dataset.v === name)
    $('side').classList.remove('open')
    tip.hidden = true
    view.innerHTML = '<span class="thinking"><span class="spin"></span>Loading</span>'
    scrollTo(0, 0)
    const ds = catalog.datasets.find((d) => d.id === name)
    try {
      if (VIEWS[name]) await VIEWS[name](ds, rest.join('/'))
      else view.innerHTML = '<div class="empty">No such page.</div>'
    } catch (e) {
      view.innerHTML = `${ds ? head(ds) : ''}<div class="callout err">${esc(e.message)}</div>`
    }
  }
  addEventListener('hashchange', route)
  addEventListener('themechange', route) // charts and the map read their colours when drawn, so draw the page again
  const head = (d, extra = '') => `<div class="page-head"><div><div class="eyebrow">${d.origin === 'mail' ? 'From the organisers' : 'Found before the event'}</div><h1>${esc(d.name)}</h1>
      <p class="lede">${esc(d.what)}</p>
      <div class="meta"><span>Licence <b>${esc(d.licence)}</b></span><span>On disk <b>${gb(d.bytes)}</b>${d.downloading ? ' <span class="tag amber">downloading</span>' : ''}</span>
        <span>Folder <b class="mono">data/${esc(d.path)}</b></span>${d.source ? `<span><a href="${esc(d.source)}" target="_blank" rel="noopener">Source</a></span>` : ''}${d.built ? `<span>Profiled <b>${esc(d.built)}</b></span>` : ''}</div></div>${extra}</div>`
  const profile = (n) => get(`api/profile/${n}`)

  // ---------- overview ----------
  VIEWS.overview = async () => {
    if (focus) return seismicOverview()
    const ds = catalog.datasets
    const total = ds.reduce((a, d) => a + d.bytes, 0)
    const card = (d) => `<a class="card" href="#${d.id}"><h3><span>${esc(d.name)}</span>${d.downloading ? '<span class="tag amber">downloading</span>' : d.present ? '<span class="tag green">here</span>' : '<span class="tag">not yet</span>'}</h3>
      <p>${esc(d.what)}</p><div class="row"><span>${gb(d.bytes)}</span><span>${esc(d.licence)}</span></div></a>`
    view.innerHTML = `<section class="hero"><div class="eyebrow">FORCE VibeCode Hackathon · data</div>
      <h1>Data Atlas <em>: what each dataset holds, what its words mean, and how the pieces fit.</em></h1>
      <p class="lede">Every dataset the event and the tools use, profiled: key numbers, charts with a line on how to read
        them, sample records, and a glossary. Dotted words explain themselves on hover. Almost everything joins on one key, the
        ${T('wellbore', 'wellbore name')}; the ${'<a href="#well">well lookup</a>'} shows one wellbore through all of them.</p></section>
      ${kpis([[ds.length, 'datasets'], [ds.filter((d) => d.origin === 'mail').length, 'from the organisers'], [gb(total), 'on disk'], [ds.filter((d) => d.downloading).length, 'still downloading', ds.some((d) => d.downloading) ? 'warn' : '']])}
      <div class="section-title">From the organisers (in the mail; the most official source)</div><div class="cards">${ds.filter((d) => d.origin === 'mail').map(card).join('')}</div>
      <div class="section-title">Found before the event</div><div class="cards">${ds.filter((d) => d.origin === 'earlier').map(card).join('')}</div>
      <div class="section-title">The life of a field, and where each dataset sits</div>
      ${panel('From licence to plug', `<div class="table-wrap" style="max-height:none">${table([
        ['Stage', (r) => `<b>${r[0]}</b>`], ['What happens', (r) => r[1]], ['Data that records it', (r) => r[2]]], [
        ['Licence', `The state awards a ${T('licence')} to a group of companies.`, 'FactPages (licence); relinquishment reports when it is handed back'],
        ['Explore', `Seismic is shot and interpreted; ${T('wildcat', 'wildcats')} are drilled into ${T('trap', 'traps')}.`, 'Seismic (F3, Adele), well logs, cores, completion reports'],
        ['Discover and appraise', `A well finds oil or gas; ${T('appraisal')} wells measure it.`, 'FactPages (discovery), DST results, RealPore core data, DISKOS-QA passages'],
        ['Develop', `A ${T('pdo', 'PDO')} is approved, platforms are built, ${T('development')} wells drilled.`, 'Volve daily drilling reports, FactPages casing and mud'],
        ['Produce', 'Oil, gas and water flow for decades; output falls with time.', 'FactPages monthly production and reserves'],
        ['Late life', `The field shuts down; every well gets ${T('pa', 'plugged')}; old reservoirs may store CO2.`, 'Completion reports (what is in each well), FactPages status'],
      ])}</div>`)}`
  }

  // ---------- connections ----------
  VIEWS.connect = async () => {
    const l = catalog.links || (await profile('links').catch(() => null))
    if (!l) { view.innerHTML = '<div class="empty">Not profiled yet: <code>uv run python -m sketches.atlas links</code></div>'; return }
    const names = { logs: 'FORCE 2020 logs', diskosqa: 'DISKOS-QA', volve: 'Volve DDRs', realpore: 'RealPore', completion: 'Completion reports' }
    const keys = Object.keys(l.sets).filter((k) => k !== 'factpages')
    view.innerHTML = `<div class="page-head"><div><div class="eyebrow">The glue</div><h1>How the data connects</h1>
      <p class="lede">Nearly every dataset is about wellbores, so the ${T('wellbore', 'wellbore name')} (written one way: 15/9-F-12)
        joins them, with FactPages as the register every name is checked against. The more datasets a wellbore is in,
        the more you can say about it.</p></div></div>
      ${kpis([[num(l.sets.factpages.wellbores), 'wellbores in FactPages'], ...keys.map((k) => [num(l.sets[k].wellbores), `in ${names[k] || k}`])])}
      <div class="grid g2">${panel('Wellbores per dataset, and how many FactPages knows', chart('c-sets'), 'the full bar is every wellbore the dataset names; the dark part is those found in FactPages. A gap means names that need cleaning or wells not in the register.')}
      ${panel('Wellbores shared by two datasets', chart('c-pairs'), 'each cell counts wellbores in both datasets. These overlaps are where cross-checks and joined apps are possible, e.g. logs with core plugs to calibrate porosity.')}</div>
      ${panel('Wellbores in the most datasets', table([['Wellbore', (r) => wellLink(r.wellbore)], ['In', (r) => `<span class="pres">${r.in.map((k) => `<span class="tag">${esc(names[k] || k)}</span>`).join('')}</span>`]], l.richest), 'open one to see all its data on one page.')}`
    plot('c-sets', [
      { type: 'bar', orientation: 'h', name: 'in FactPages', y: keys.map((k) => names[k] || k), x: keys.map((k) => l.sets[k].in_factpages), marker: { color: S(1) } },
      { type: 'bar', orientation: 'h', name: 'not found in FactPages', y: keys.map((k) => names[k] || k), x: keys.map((k) => l.sets[k].wellbores - l.sets[k].in_factpages), marker: { color: S(0) } },
    ], { barmode: 'stack', margin: { l: 140, r: 16, t: 10, b: 40 }, xaxis: { title: { text: 'wellbores' } } })
    const z = keys.map((a) => keys.map((b) => (a === b ? l.sets[a].wellbores : (l.pairs.find((p) => (p.a === a && p.b === b) || (p.a === b && p.b === a)) || {}).n || 0)))
    plot('c-pairs', [{ type: 'heatmap', z, x: keys.map((k) => names[k] || k), y: keys.map((k) => names[k] || k), colorscale: [[0, css('--panel-2')], [1, S(1)]], showscale: false,
      text: z.map((r) => r.map(String)), texttemplate: '%{text}', hovertemplate: '%{y} and %{x}: %{z} wellbores<extra></extra>' }], { margin: { l: 140, r: 16, t: 10, b: 90 }, yaxis: { autorange: 'reversed' } })
  }

  // ---------- well lookup ----------
  VIEWS.well = async (_, name) => {
    view.innerHTML = `<div class="page-head"><div><div class="eyebrow">Across every dataset</div><h1>Well lookup</h1>
      <p class="lede">Type a ${T('wellbore')} name. Everything known about it comes together: the FactPages record,
        ${T('top', 'formation tops')}, ${T('casing')}, ${T('core', 'cores')}, ${T('log')} curves, ${T('plug', 'core plug')} measurements,
        report passages and the ${T('completion_report', 'completion report')} files.</p></div></div>
      <div class="panel"><div class="row end"><label class="field grow">Wellbore<input id="wq" list="wl" placeholder="e.g. 15/9-13, 16/1-2, 34/10-21" value="${esc(name || '')}" /></label>
      <datalist id="wl"></datalist><button class="btn" id="wgo">Look up</button></div><div class="chips" id="wsug" style="margin-top:.7rem"></div></div><div id="wout"></div>`
    const l = catalog.links
    if (l) $('wsug').innerHTML = '<span class="hint">Rich in data:</span> ' + l.richest.slice(0, 10).map((r) => `<button class="chip" data-w="${esc(r.wellbore)}">${esc(r.wellbore)}</button>`).join('')
    $('wsug').onclick = (e) => { const w = e.target.dataset?.w; if (w) location.hash = `well/${encodeURIComponent(w)}` }
    $('wq').oninput = async () => {
      const q = $('wq').value.trim()
      if (q.length < 2) return
      const d = await get(`../detective/api/wellbores?q=${encodeURIComponent(q)}`).catch(() => null)
      if (d) $('wl').innerHTML = d.wellbores.map((w) => `<option value="${esc(w.name)}">`).join('')
    }
    const go = () => { const q = $('wq').value.trim(); if (q) location.hash = `well/${encodeURIComponent(q)}` }
    $('wgo').onclick = go
    $('wq').onkeydown = (e) => { if (e.key === 'Enter') go() }
    if (name) await showWell(name)
  }
  async function showWell(name) {
    const out = $('wout')
    out.innerHTML = '<p><span class="thinking"><span class="spin"></span>Collecting</span></p>'
    const w = await get(`api/well/${encodeURIComponent(name)}`).catch((e) => ({ error: e.message }))
    if (w.error) { out.innerHTML = `<div class="callout err" style="margin-top:1rem">${esc(w.error)}</div>`; return }
    const h = w.header || {}
    const names = { logs: 'FORCE 2020 logs', diskosqa: 'DISKOS-QA passages', volve: 'Volve DDRs', realpore: 'RealPore plugs', completion: 'Completion report' }
    out.innerHTML = `${kpis([[esc(w.name), esc(h.kind || 'wellbore')], [esc(h.content || '–'), T('content', 'content'), 'txt'], [num(h.td), `${T('td', 'TD')} m ${T('md', 'MD')}`], [num(h.water_depth), 'water depth, m'], [esc((h.entry || '').slice(0, 10) || '–'), T('spud', 'spud date')], [esc(h.operator || '–'), T('operator', 'operator'), 'txt']])}
      <div class="panel"><div class="panel-head"><h2>In these datasets</h2><span class="hint">FactPages: ${h.name ? 'yes' : 'no'}</span></div><div class="pres">${Object.entries(w.in || {}).map(([k, v]) => `<span class="tag ${v ? 'green' : ''}">${v ? '✓' : '·'} ${esc(names[k] || k)}</span>`).join('')}</div>
        <p class="muted small" style="margin:.6rem 0 0">${esc([h.field && `Field ${h.field}`, h.discovery && `discovery ${h.discovery}`, h.purpose, h.status, h.formation_td && `TD in ${h.formation_td}`, h.age_td].filter(Boolean).join(' · '))}</p></div>
      <div class="panel"><div class="panel-head"><h2>The wellbore by depth</h2><span class="hint">Depth in m MD, down is deeper</span></div>${chart('w-depth', 620)}
        <p class="how"><b>How to read it:</b> each column is one measurement against depth. ${T('gr', 'GR')} high means shale, low sand or carbonate; ${T('rhob', 'density')} and ${T('nphi', 'neutron')} together tell rock and fluid apart; ${T('rdep', 'resistivity')} (log scale) jumps where oil or gas fills the pores. The right column shows ${T('plug', 'core plug')} porosity, which is what the logs try to estimate. Grey bands are ${T('core', 'cored')} intervals; horizontal lines are ${T('top', 'formation tops')} and ${T('shoe', 'casing shoes')}.</p></div>
      <div class="grid g2">${panel('Formation tops (FactPages)', w.tops.length ? table([['Unit', (r) => esc(r.unit)], ['Level', (r) => esc(r.level)], ['Top m', (r) => num(r.top), 'num'], ['Base m', (r) => num(r.base), 'num']], w.tops, 320) : '<div class="empty">No tops published.</div>')}
        ${panel('Casing and leak-off tests', w.casing.length ? table([['Casing', (r) => esc(r.type)], ['Size', (r) => esc(r.diameter)], ['Shoe m', (r) => num(r.depth), 'num'], ['Hole m', (r) => num(r.hole), 'num'], ['LOT g/cm³', (r) => (r.lot > 0 ? num(r.lot, 2) : '–'), 'num']], w.casing, 320) : '<div class="empty">None published.</div>', `${T('lot', 'LOT')} is the strongest mud the rock below the shoe held.`)}</div>
      ${w.passages ? panel(`Report passages (${w.passage_count} in DISKOS-QA)`, w.passages.map((p) => `<div class="qa"><div class="muted small">${esc(p.doc)}</div><div class="sample" style="max-height:140px">${esc(p.text)}</div></div>`).join('')) : ''}
      ${w.reports && w.reports.length ? panel('Completion report, page by page', '<div id="wrep"></div>', 'the structured JSON of the final well report: every page summarised, tagged and graded; click a page for its full text.') : ''}
      ${w.completion ? panel('Completion report files', table([['Format', (r) => esc(r.Format)], ['Dataset', (r) => esc(r['Dataset Name'])], ['MB', (r) => num(r['File Size (MB)'], 1), 'num'], ['File', (r) => `<span class="mono">${esc(r.FolderFileName)}</span>`]], w.completion, 260), 'the PDF is the scanned original; the JSON is the same report turned into structured text by the dataset\'s pipeline.') : ''}
      ${w.documents.length ? panel('Documents on FactPages', table([['Type', (r) => esc(r.type)], ['Name', (r) => `<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name)}</a>`]], w.documents, 240)) : ''}`
    depthChart(w)
    if ($('wrep')) reportViewer($('wrep'), w.name)
  }
  function depthChart(w) {
    const tracks = [], data = []
    const add = (key, label, opts = {}) => tracks.push({ key, label, ...opts })
    if (w.logs) { if (w.logs.GR) add('GR', 'GR, API'); if (w.logs.RHOB) add('RHOB', 'RHOB, g/cm³'); if (w.logs.NPHI) add('NPHI', 'NPHI, v/v'); if (w.logs.RDEP) add('RDEP', 'RDEP, ohm·m', { log: true }) }
    if (w.logs && w.logs.lith && w.logs.lith.some(Boolean)) add('LITH', 'lithology (label)', { narrow: true })
    if (w.plugs) add('POR', 'plug porosity, %')
    if (!tracks.length) add('NONE', 'no curves or plugs')
    const n = tracks.length, gap = 0.02, wdt = (1 - gap * (n - 1)) / n
    const lay = { margin: { l: 60, r: 10, t: 30, b: 40 }, showlegend: false, yaxis: { autorange: 'reversed', title: { text: 'm MD' } }, shapes: [], annotations: [] }
    tracks.forEach((t, i) => {
      const ax = i ? `xaxis${i + 1}` : 'xaxis', xr = i ? `x${i + 1}` : 'x'
      lay[ax] = { domain: [i * (wdt + gap), i * (wdt + gap) + wdt], type: t.log ? 'log' : 'linear', title: { text: t.label }, side: 'top' }
      if (t.key === 'LITH') { lay[ax].showticklabels = false; lay[ax].range = [0, 1]; data.push({ type: 'scattergl', mode: 'markers', x: w.logs.lith.map(() => 0.5), y: w.logs.depth, xaxis: xr, yaxis: 'y', marker: { symbol: 'square', size: 9, color: w.logs.lith.map((l) => LITH_COLOR[l] || 'rgba(0,0,0,0)') }, text: w.logs.lith, hovertemplate: '%{y:.0f} m: %{text}<extra></extra>' }) }
      else if (t.key === 'POR') data.push({ type: 'scattergl', mode: 'markers', x: w.plugs.porosity, y: w.plugs.md, xaxis: xr, yaxis: 'y', marker: { size: 4, color: S(3) }, text: w.plugs.rock, hovertemplate: '%{y:.1f} m: %{x:.1f} %, %{text}<extra></extra>' })
      else if (t.key !== 'NONE') data.push({ type: 'scattergl', mode: 'lines', x: w.logs[t.key], y: w.logs.depth, xaxis: xr, yaxis: 'y', line: { width: 1.2, color: [S(1), S(2), S(7), S(4)][i % 4] }, hovertemplate: `%{y:.0f} m: %{x:.3~g}<extra>${t.key}</extra>` })
    })
    for (const c of w.cores || []) if (c.top != null && (c.uom || 'm').toLowerCase().startsWith('m')) lay.shapes.push({ type: 'rect', xref: 'paper', x0: 0, x1: 1, y0: c.top, y1: c.base, fillcolor: css('--line-2'), opacity: 0.35, line: { width: 0 }, layer: 'below' })
    for (const t of (w.tops || []).filter((t) => t.level === 'FORMATION' || t.level === 'GROUP')) {
      lay.shapes.push({ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: t.top, y1: t.top, line: { color: css('--muted'), width: t.level === 'GROUP' ? 1 : 0.5, dash: t.level === 'GROUP' ? 'solid' : 'dot' } })
      if (t.level === 'GROUP') lay.annotations.push({ xref: 'paper', x: 1, y: t.top, text: t.unit, showarrow: false, xanchor: 'right', yanchor: 'bottom', font: { size: 10, color: css('--muted') } })
    }
    for (const c of w.casing || []) if (c.depth) lay.shapes.push({ type: 'line', xref: 'paper', x0: 0, x1: 0.015, y0: c.depth, y1: c.depth, line: { color: S(2), width: 3 } })
    plot('w-depth', data, lay)
  }

  // ---------- glossary ----------
  VIEWS.glossary = async () => {
    const all = Object.keys(G).sort((a, b) => G[a][0].localeCompare(G[b][0]))
    const seis = new Set([...SEIS_TERMS, 'pstm', 'stack', 'migration', 'attribute', 'rms', 'spectrum', 'dominant', 'nyquist', 'tuning', 'wavelet', 'polarity', 'ebcdic', 'ieee', 'utm', 'impedance', 'synthetic', 'checkshot', 'vsp', 'iou', 'imbalance', 'split', 'clinoform', 'salt', 'texture', 'dtc', 'rhob'])
    const keys = focus ? [...all.filter((k) => seis.has(k)), ...all.filter((k) => !seis.has(k))] : all
    view.innerHTML = `<div class="page-head"><div><div class="eyebrow">Reference</div><h1>Glossary</h1><p class="lede">${keys.length} terms from
      geology, drilling, production and the datasets, in plain words.${focus ? ' Seismic terms come first.' : ''}</p></div><input id="gq" placeholder="Filter" style="min-width:240px" /></div><div class="gloss" id="gl"></div>`
    const draw = (q = '') => { $('gl').innerHTML = keys.filter((k) => !q || (G[k][0] + G[k][1]).toLowerCase().includes(q)).map((k) => `<div class="t">${esc(G[k][0])}</div><div class="d">${esc(G[k][1])}${G[k][2] ? `<span class="c">${esc(G[k][2])}</span>` : ''}</div>`).join('') }
    draw()
    $('gq').oninput = () => draw($('gq').value.toLowerCase())
  }

  // ---------- FactPages ----------
  const CONTENT = (c) => (/SHOWS/.test(c) ? 'SHOWS' : c === 'DRY' ? 'DRY' : /OIL/.test(c) && /GAS/.test(c) ? 'OIL/GAS' : /OIL/.test(c) ? 'OIL' : /GAS/.test(c) ? 'GAS' : 'OTHER')
  const CONTENT_COLOR = () => ({ OIL: S(3), GAS: S(8), 'OIL/GAS': S(4), SHOWS: S(7), DRY: S(0), OTHER: css('--line-2') })
  const TABLE_HELP = {
    field: 'one row per field: operator, status, hydrocarbon type', field_description: 'Sodir\'s text about each field', field_reserves: 'recoverable and remaining oil, gas, NGL, condensate per field',
    field_production_monthly: 'monthly production per field since 1971', wellbore_exploration: 'every exploration wellbore: dates, depths, result, position', wellbore_development: 'every development wellbore',
    discovery: 'every discovery and its status', licence: 'production licences', company: 'companies', wellbore_formation_top: 'formation tops per wellbore', wellbore_casing_and_lot: 'casing strings and leak-off tests',
    wellbore_mud: 'mud weights by depth', wellbore_dst: 'drill-stem tests: rates and pressures', wellbore_core: 'cored intervals', wellbore_history: 'drilling history as text', wellbore_document: 'links to published well documents (PDF)',
    facility_fixed: 'platforms and installations', discovery_reserves: 'resources in undeveloped discoveries', discovery_description: 'text about each discovery', field_investment_yearly: 'investment per field and year',
    field_operator_hst: 'operator history', strat_litho_overview: 'the lithostratigraphic chart: groups, formations, members',
  }
  VIEWS.factpages = async (d) => {
    const p = await profile('factpages')
    const k = p.kpis
    view.innerHTML = `${head(d)}${plain(
      `Sodir's register of everything on the shelf since 1966: ${num(k.expl + k.dev)} wellbores, ${num(k.fields)} fields, ${num(k.discoveries)} discoveries, ${num(k.licences)} licences, monthly production per field.`,
      'It is the reference: names, positions, dates, depths and results are official here. Every other dataset is checked and joined against it.',
      'Text-to-SQL over the tables (NCS Copilot), tie-back screening, decline forecasts, well planning from offsets.')}
      ${kpis([[num(k.expl), `${T('exploration')} wellbores`], [num(k.dev), `${T('development')} wellbores`], [num(k.producing), `producing ${T('field', 'fields')}`], [num(k.discoveries), T('discovery', 'discoveries')], [num(k.cum_oe), `MSm³ ${T('oe', 'o.e.')} produced since ${k.first_year}`], [num(k.remaining_oe), `MSm³ o.e. ${T('reserves', 'remaining')} (estimate ${k.reserves_year})`]])}
      <div class="split">${panel('Exploration wellbores on the map', `<div id="m-fp" class="map" style="height:520px"></div>${legend(Object.entries(CONTENT_COLOR()).map(([k_, c]) => [c, k_]))}`, `each dot is one ${T('exploration')} wellbore, coloured by what it found (${T('content')}). Dry wells far outnumber finds in new areas; clusters of finds mark the producing areas.`)}
        ${panel('What exploration wells found', chart('c-content', 520), 'about one in three wildcats on the NCS finds something; many finds are small.')}</div>
      <div class="grid g2">${panel('Exploration wells started per year', chart('c-spud'), `${T('wildcat', 'wildcats')} test new ideas, ${T('appraisal')} wells follow up finds. Activity follows the oil price and licensing rounds.`)}
        ${panel('Development wells started per year', chart('c-dev'), 'drilling on producing fields; peaks follow new field developments.')}</div>
      ${panel('Production on the shelf per year', chart('c-prod', 360), `stacked in MSm³ ${T('oe', 'o.e.')} (gas: 1 GSm³ = 1 MSm³ o.e.), whole years only. Oil peaked around 2000; gas took over. Water is shown below, not stacked.`)}
      <div class="grid g2">${panel('Produced water per year', chart('c-water', 260), `${T('water', 'produced water')} grows as fields age. Sodir reports it from 2000.`)}
        ${panel('Fields by status', chart('c-status', 260))}</div>
      <div class="grid g2">${panel('Fields with the most left to produce', chart('c-top', 460), `remaining ${T('reserves')} per field, MSm³ o.e. A few giants (Johan Sverdrup, Troll) hold much of it.`)}
        ${panel('Discoveries by status', table([['Status', (r) => esc(r.k)], ['Discoveries', (r) => num(r.n), 'num'], ['Recoverable MSm³ o.e.', (r) => num(r.oe, 1), 'num']], p.discoveries, 460), `undeveloped ${T('discovery', 'discoveries')} waiting for a decision are candidates for ${T('tieback', 'tie-backs')}.`)}</div>
      ${panel('The 22 tables', table([['Table', (r) => `<span class="mono">${esc(r.table)}</span>`], ['Rows', (r) => num(r.rows), 'num'], ['What is in it', (r) => esc(TABLE_HELP[r.table] || '')]], p.tables, 520), 'the database the tools query is data/ncs.duckdb.')}
      ${terms(['wellbore', 'quadrant', 'exploration', 'wildcat', 'appraisal', 'development', 'content', 'discovery', 'field', 'licence', 'operator', 'oe', 'sm3', 'reserves', 'recoverable', 'water', 'npdid', 'td', 'md', 'kb'])}`
    const cc = CONTENT_COLOR()
    map($('m-fp'), p.points, (x) => cc[CONTENT(x.content)], (x) => `<b>${esc(x.name)}</b><br>${esc(x.content)} · ${x.y || ''}<br><a href="#well/${encodeURIComponent(x.name)}">all data</a>`)
    const grouped = {}
    for (const c of p.content) grouped[CONTENT(c.k)] = (grouped[CONTENT(c.k)] || 0) + c.n
    const gl = Object.entries(grouped).sort((a, b) => b[1] - a[1]).map(([k_, n]) => ({ k: k_, n }))
    plot('c-content', [{ ...bar(gl, { h: true }), marker: { color: gl.map((g) => cc[g.k]) } }], { yaxis: { autorange: 'reversed' }, margin: { l: 80, r: 16, t: 10, b: 40 } })
    const years = [...new Set(p.spud.map((s) => s.y))]
    plot('c-spud', ['WILDCAT', 'APPRAISAL'].map((pp, i) => ({ type: 'bar', name: pp.toLowerCase(), x: years, y: years.map((y) => (p.spud.find((s) => s.y === y && s.p === pp) || {}).n || 0), marker: { color: S(i + 1) } })), { barmode: 'stack' })
    plot('c-dev', [bar(p.dev, { x: 'y', color: S(3) })])
    const prod = p.production
    plot('c-prod', [['oil', 'oil', S(3)], ['gas', 'gas', S(8)], ['ngl', 'NGL and condensate', S(4)]].map(([key, name, color]) => ({ type: 'scatter', mode: 'lines', stackgroup: 'p', name, x: prod.map((r) => r.y), y: prod.map((r) => r[key]), line: { width: 0.5, color }, fillcolor: color, hovertemplate: `%{x}: %{y:.1f} MSm³ o.e.<extra>${name}</extra>` })), { yaxis: { title: { text: 'MSm³ o.e. per year' } } })
    plot('c-water', [{ type: 'scatter', mode: 'lines', x: prod.map((r) => r.y), y: prod.map((r) => r.water), line: { color: S(1), width: 2 }, hovertemplate: '%{x}: %{y:.0f} MSm³<extra></extra>' }], { yaxis: { title: { text: 'MSm³ water' } } })
    plot('c-status', [bar(p.field_status, { h: true, color: S(1) })], { yaxis: { autorange: 'reversed' }, margin: { l: 170, r: 16, t: 10, b: 40 } })
    plot('c-top', [{ ...bar(p.top_fields, { h: true, x: 'field', y: 'remaining', fmt: ' MSm³ o.e.' }), marker: { color: S(1) } }], { yaxis: { autorange: 'reversed' }, margin: { l: 130, r: 16, t: 10, b: 40 } })
  }

  // ---------- well logs ----------
  const LITH_COLOR = { Sandstone: '#e3b505', 'Sandstone/Shale': '#c99a4f', Shale: '#7d8a96', Marl: '#5fa37f', Dolomite: '#a77bd1', Limestone: '#3f86d4', Chalk: '#8fc3ee', Halite: '#e06464', Anhydrite: '#d55181', Tuff: '#e8743b', Coal: '#5a4a3a', Basement: '#9b6b4a' }
  VIEWS.logs = async (d) => {
    const p = await profile('logs')
    const k = p.kpis
    view.innerHTML = `${head(d)}${plain(
      `${k.wells} wells from the Norwegian North Sea and Norwegian Sea, ${num(k.rows)} depth samples, up to ${k.curves} ${T('log')} curves each, and a ${T('lithology')} label at every sample (12 classes) made by geoscientists.`,
      'Reading lithology from logs by hand takes days per well. These labels are the best public benchmark for doing it with machine learning.',
      'Lithology and porosity prediction, log quality checks, missing-curve prediction, joining logs with core plugs (RealPore) to calibrate.')}
      ${kpis([[k.wells, 'wells'], [`${k.train_wells} + ${k.test_wells}`, 'train + hidden test'], [num(k.rows), 'depth samples (one per 15 cm)'], [k.curves, 'curve types'], [k.classes, 'lithology classes'], [num(k.las_files), `${T('las', 'LAS')} files in the mail's copy`]])}
      <div class="grid g2">${panel('How much of each rock type', chart('c-lith', 380), `share of all samples per ${T('lithology')}. ${T('shale', 'Shale')} dominates; rare classes (coal, halite, basement) are where models fail. The competition scored mistakes with a penalty matrix.`)}
        ${panel('Which curves exist', chart('c-avail', 380), 'percent of samples where a curve has a value. GR is almost always there; shear sonic (DTS) rarely. Models must cope with gaps.')}</div>
      <div class="grid g2">${panel('Density against neutron, by rock type', chart('c-cross', 440), `a classic ${T('density-neutron', 'crossplot')}: ${T('sandstone')} sits at low neutron and moderate density, ${T('shale')} at high neutron, ${T('limestone')} at high density. A sample of 12,000 points.`)}
        ${panel('Gamma ray by rock type', chart('c-gr', 440), `box = middle half of the samples, line = median, whiskers = 10th to 90th percentile. ${T('gr', 'GR')} separates shale (high) from sand and carbonate (low), but not sand from limestone: that needs density and PEF.`)}</div>
      <div class="split">${panel('Where the wells are', `<div id="m-logs" class="map" style="height:420px"></div>${legend([[S(1), 'train'], [S(2), 'hidden test']])}`, 'click a well for its curves.')}
        ${panel('Wells', table([['Well', (r) => wellLink(r.well)], ['Set', (r) => esc(r.set)], ['Top m', (r) => num(r.top), 'num'], ['Base m', (r) => num(r.base), 'num'], ['Main rock', (r) => esc(r.main)]], p.wells, 420))}</div>
      ${panel('The curves', table([['Curve', (r) => `<span class="mono">${esc(r.curve)}</span>`], ['Measures', (r) => (G[r.curve.toLowerCase()] ? T(r.curve.toLowerCase(), r.name) : esc(r.name))], ['Samples with a value', (r) => `${r.rows} %`, 'num'], ['Wells with it', (r) => num(r.wells), 'num']], p.availability, 520))}
      ${panel('Stratigraphic groups in the data', chart('c-groups', 320), `samples per ${T('group')} (the label column GROUP). The Nordland, Hordaland and Rogaland groups are the young rocks above; the Viking and Brent groups hold the classic reservoirs.`)}
      ${terms(['log', 'las', 'gr', 'rhob', 'nphi', 'density-neutron', 'rdep', 'dtc', 'pef', 'cali', 'sp', 'lithology', 'sandstone', 'shale', 'limestone', 'marl', 'halite', 'group', 'formation', 'force2020'])}`
    const L_ = p.lith.map((x) => x.k)
    plot('c-lith', [{ ...bar(p.lith, { h: true }), marker: { color: p.lith.map((x) => LITH_COLOR[x.k] || S(0)) } }], { yaxis: { autorange: 'reversed' }, margin: { l: 120, r: 16, t: 10, b: 40 } })
    plot('c-avail', [{ ...bar(p.availability, { h: true, x: 'curve', y: 'rows', fmt: ' %' }), marker: { color: S(1) } }], { yaxis: { autorange: 'reversed' }, xaxis: { range: [0, 100], title: { text: '% of samples' } }, margin: { l: 90, r: 16, t: 10, b: 40 } })
    const cp = p.crossplot
    plot('c-cross', L_.slice(0, 7).map((l) => {
      const idx = cp.lith.map((x, i) => (x === l ? i : -1)).filter((i) => i >= 0)
      return { type: 'scattergl', mode: 'markers', name: l, x: idx.map((i) => cp.nphi[i]), y: idx.map((i) => cp.rhob[i]), marker: { size: 4, color: LITH_COLOR[l], opacity: 0.6 }, hovertemplate: `NPHI %{x:.2f}, RHOB %{y:.2f}<extra>${l}</extra>` }
    }), { xaxis: { title: { text: 'NPHI, v/v' }, range: [-0.05, 0.7] }, yaxis: { title: { text: 'RHOB, g/cm³' }, autorange: 'reversed', range: [3, 1.8] } })
    plot('c-gr', [{ type: 'box', orientation: 'h', y: p.by_lith.map((b) => b.lith), lowerfence: p.by_lith.map((b) => b.GR[0]), q1: p.by_lith.map((b) => b.GR[1]), median: p.by_lith.map((b) => b.GR[2]), q3: p.by_lith.map((b) => b.GR[3]), upperfence: p.by_lith.map((b) => b.GR[4]), marker: { color: S(1) }, line: { width: 1.5 }, fillcolor: 'rgba(0,0,0,0)', hoverinfo: 'y' }], { xaxis: { title: { text: 'GR, API' } }, margin: { l: 120, r: 16, t: 10, b: 40 } })
    map($('m-logs'), p.wells, (w) => (w.set === 'train' ? S(1) : S(2)), (w) => `<b>${esc(w.well)}</b><br>${num(w.top)} to ${num(w.base)} m<br><a href="#well/${encodeURIComponent(w.well)}">curves and all data</a>`, [61, 3], 5.5)
    plot('c-groups', [bar(p.groups, { x: 'GROUP', y: 'rows', color: S(1) })], { margin: { l: 56, r: 16, t: 10, b: 110 } })
  }

  // ---------- DISKOS-QA ----------
  VIEWS.diskosqa = async (d) => {
    const p = await profile('diskosqa')
    const k = p.kpis
    const sc = p.scorecard || {}
    view.innerHTML = `${head(d)}${plain(
      `${num(k.questions)} questions written from ${num(k.passages)} ${T('passage', 'passages')} of ${num(k.documents)} Diskos well reports, each with a reference answer and the passage it comes from. ${num(k.supported)} are ${T('entailed', 'supported')} by their passage.`,
      'Geoscientists spend days finding facts in old reports. A benchmark with known answers lets you measure whether a search or a language model actually finds them, instead of guessing.',
      `Search and question answering over reports (${T('rag', 'RAG')}), with a score: Diskos Detective uses it. Also a test set for the completion reports.`)}
      ${kpis([[num(k.questions), 'questions'], [num(k.supported), T('entailed', 'supported')], [num(k.passages), T('passage', 'passages')], [num(k.wellbores), 'wellbores named'], [num(k.formations), 'formations named'], [num(k.median_chars), 'characters in a median passage']])}
      <div class="grid g2">${panel('Questions by topic', chart('c-topic', 340), 'what the questions are about. Drilling and geology dominate; well-seismic (VSP) and petrophysics are rarer and harder.')}
        ${panel('How each question narrows the search', chart('c-filter', 340), 'questions name a wellbore, field or formation, or nothing. Filtering the search to that name first is what lifts the score.')}</div>
      <div class="grid g2">${panel('Wellbores with the most passages', chart('c-wb', 420), 'some wells are covered by many passages, most by a few.')}
        ${panel('Passage length', chart('c-len', 420), 'characters per passage. The long ones (above 2,000) hide the answer near the end: prompts must not cut them.')}</div>
      ${sc.retrieval ? panel('Scorecard: how well search and answers do', `<div class="grid g2"><div>${table([['Search mode', (r) => esc(r[0])], [T('recall', 'Recall@5'), (r) => `${num(r[1].recall_at_5 * 100, 1)} %`, 'num'], ['MRR@10', (r) => num(r[1].mrr_at_10, 3), 'num']], Object.entries(sc.retrieval))}</div><div>${sc.answers ? table([['Answer mode', (r) => esc(r[0])], ['Correct', (r) => `${num(r[1].accuracy * 100)} %`, 'num'], ['Questions', (r) => r[1].n, 'num'], ['Seconds each', (r) => num(r[1].mean_seconds, 1), 'num']], Object.entries(sc.answers)) : '<div class="empty">No answer run yet.</div>'}</div></div>`, `search: is the right passage in the top 5? Answers: judged against the reference by the model ${esc(sc.model || '')}. Closed book answers from memory only, which shows how little a model knows about specific wells.`) : ''}
      ${panel('Sample questions', p.examples.map((e) => `<div class="qa"><div class="row"><span class="tag">${esc(e.topic)}</span><span class="tag">${esc(e.kind)}</span><span class="muted small">${esc(e.doc)}</span></div><div class="q" style="margin-top:.35rem">${esc(e.q)}</div><div class="a">${esc(e.a)}</div><details><summary>The passage</summary><div class="sample">${esc(e.passage)}</div></details></div>`).join(''))}
      ${terms(['rag', 'passage', 'entailed', 'recall', 'diskos', 'biostratigraphy', 'vsp', 'dst', 'core', 'formation'])}`
    plot('c-topic', [bar(p.topics, { h: true })], { yaxis: { autorange: 'reversed' }, margin: { l: 170, r: 16, t: 10, b: 40 } })
    plot('c-filter', [bar(p.filter_type, { h: true, color: S(3) })], { yaxis: { autorange: 'reversed' }, margin: { l: 120, r: 16, t: 10, b: 40 } })
    plot('c-wb', [bar(p.top_wellbores, { h: true })], { yaxis: { autorange: 'reversed' }, margin: { l: 100, r: 16, t: 10, b: 40 } })
    plot('c-len', [histo(p.length)], { xaxis: { title: { text: 'characters' } }, yaxis: { title: { text: 'passages' } } })
  }

  // ---------- Volve ----------
  VIEWS.volve = async (d) => {
    const p = await profile('volve')
    const k = p.kpis
    view.innerHTML = `${head(d)}${plain(
      `Every ${T('ddr', 'daily drilling report')} from Equinor's Volve field (released openly in 2018): ${num(k.reports)} reports, ${num(k.activities)} activities over ${num(k.wellbores)} wellbores, ${k.first} to ${k.last}.`,
      `A rig costs USD 300k to 500k a day. ${num(k.npt_share, 1)} % of Volve's logged hours are reported as ${T('npt', 'NPT')}, and more hides in slow drilling and repeated work.`,
      'Lost-time analytics (Lost Time Hunter), lessons-learned search, drilling-curve benchmarking, planning the next well from the last.')}
      ${kpis([[num(k.reports), 'daily reports'], [num(k.wellbores), 'wellbores'], [num(k.hours), 'rig hours logged'], [`${num(k.npt_share, 1)} %`, `reported ${T('npt', 'NPT')}`, 'warn'], [num(k.deepest), `deepest ${T('md', 'MD')}, m`]])}
      <div class="grid g2">${panel('Where rig time went', chart('c-major', 360), 'hours per activity class. Drilling makes hole; trips, casing and cementing are needed but make none; interruption is NPT.')}
        ${panel('The 25 biggest activity codes', chart('c-minor', 360), 'the detailed codes inside the classes.')}</div>
      <div class="grid g2">${panel(`Drilling curve: ${esc(p.curve.wellbore)}`, chart('c-curve', 380), `depth against days since the first report. Steep is fast drilling; flat steps are ${T('trip', 'trips')}, ${T('casing')} runs and problems. Comparing these curves between wells is how drilling performance is judged.`)}
        ${panel('Reports per month', chart('c-month', 380), 'when the rigs were working on Volve.')}</div>
      ${panel('Wellbores', table([['Wellbore', (r) => wellLink(r.wellbore)], ['Reports', (r) => num(r.days), 'num'], ['Hours', (r) => num(r.hours), 'num'], ['NPT hours', (r) => num(r.npt), 'num'], ['Max MD m', (r) => num(r.md), 'num']], p.wellbores, 360))}
      ${panel('Sample report lines', table([['Wellbore', (r) => esc(r.wellbore)], ['Start', (r) => esc(r.start)], ['h', (r) => num(r.hours, 1), 'num'], ['Code', (r) => `<span class="mono small">${esc(r.code)}</span>`], ['Comment', (r) => `<span style="white-space:normal">${esc(r.text)}</span>`]], p.examples, 460), 'the free-text comment is where problems are described; codes are often too coarse.')}
      ${terms(['ddr', 'npt', 'rop', 'trip', 'casing', 'shoe', 'mud', 'window', 'kick', 'lot', 'md', 'tvd'])}`
    plot('c-major', [bar(p.major, { h: true, y: 'hours', fmt: ' h' })], { yaxis: { autorange: 'reversed' }, margin: { l: 150, r: 16, t: 10, b: 40 } })
    plot('c-minor', [bar(p.minor.map((m) => ({ k: `${m.major} · ${m.minor}`, n: m.hours })), { h: true, color: S(3), fmt: ' h' })], { yaxis: { autorange: 'reversed', tickfont: { size: 10 } }, margin: { l: 260, r: 16, t: 10, b: 40 } })
    const c = p.curve, majors = [...new Set(c.major)].slice(0, 6)
    plot('c-curve', [{ type: 'scattergl', mode: 'lines', x: c.days, y: c.md, line: { color: S(0), width: 1 }, hoverinfo: 'skip', showlegend: false },
      ...majors.map((m, i) => { const idx = c.major.map((x, j) => (x === m ? j : -1)).filter((j) => j >= 0); return { type: 'scattergl', mode: 'markers', name: m, x: idx.map((j) => c.days[j]), y: idx.map((j) => c.md[j]), marker: { size: 4, color: S(i + 1) }, hovertemplate: `day %{x:.1f}: %{y:.0f} m<extra>${m}</extra>` } })],
    { yaxis: { autorange: 'reversed', title: { text: 'm MD' } }, xaxis: { title: { text: 'days' } } })
    plot('c-month', [bar(p.months, { x: 'm', color: S(1) })])
  }

  // ---------- RealPore ----------
  VIEWS.realpore = async (d) => {
    const p = await profile('realpore')
    const k = p.kpis
    view.innerHTML = `${head(d)}${plain(
      `${num(k.plugs)} ${T('plug', 'core plugs')} from ${num(k.wellbores)} wellbores, each measured in a lab: ${T('porosity')} (${num(k.with_porosity)} plugs), ${T('permeability')} (${num(k.with_perm)}), often ${T('saturation')} and ${T('grain_density', 'grain density')}, plus the geologist's rock description. More than 600 wells were typed in by hand from paper.`,
      'Porosity says how much oil a rock can hold, permeability how fast it flows. Core measurements are the ground truth that logs and seismic are calibrated against, and they are slow and costly to get.',
      'Predict permeability from logs (FORCE wells overlap), reservoir quality maps by formation and depth, analogue search for a new prospect, checking reported porosity in reports.')}
      ${kpis([[num(k.plugs), 'plugs measured'], [num(k.wellbores), 'wellbores'], [`${num(k.median_porosity, 1)} %`, `median ${T('porosity')}`], [`${num(k.median_perm, 1)} mD`, `median ${T('permeability')}`], [num(k.deepest), 'deepest plug, m']])}
      ${panel('Porosity against permeability', chart('c-pp', 480), `each dot is one plug. Permeability is on a log scale: it rises about tenfold for every few percent of porosity. ${T('sandstone', 'Sandstones')} span the widest range; ${T('limestone', 'chalk')} can be porous but tight. A sample of 15,000 plugs.`)}
      <div class="grid g2">${panel('Porosity', chart('c-por', 300), 'percent pore space. Above 20 % is a good reservoir.')}
        ${panel('Permeability', chart('c-perm', 300), 'millidarcy on a log scale. Below 1 mD is tight; above 100 mD flows well.')}</div>
      <div class="grid g2">${panel('Sandstone porosity with depth', chart('c-depth', 380), `median and the 10th to 90th percentile per 250 m. Burial squeezes and cements the sand, so porosity falls with depth: the compaction trend that tells you what to expect at a target depth.`)}
        ${panel('Where the cored wells are', `<div id="m-rp" class="map" style="height:380px"></div>`, 'dots sized evenly; click for the well.')}</div>
      <div class="grid g3">${panel('Rock types', chart('c-rock', 300))}${panel('Grain size', chart('c-grain', 300))}${panel('Cementation', chart('c-cem', 300), 'well-cemented rock has lost pore space to minerals.')}</div>
      ${terms(['core', 'plug', 'porosity', 'permeability', 'md_unit', 'klinkenberg', 'helium', 'saturation', 'grain_density', 'sandstone', 'reservoir'])}`
    const cp = p.crossplot, rocks = [...new Set(cp.rock)]
    const order = p.rocks.map((r) => r.k).filter((r) => rocks.includes(r))
    const first3 = order.slice(0, 3)
    const groups = [...first3.map((r, i) => [r, S(i + 1), (x) => x === r]), ['other', S(0), (x) => !first3.includes(x)]]
    plot('c-pp', groups.map(([name, color, f]) => { const idx = cp.rock.map((x, i) => (f(x) ? i : -1)).filter((i) => i >= 0); return { type: 'scattergl', mode: 'markers', name, x: idx.map((i) => cp.por[i]), y: idx.map((i) => cp.perm[i]), marker: { size: 3.5, color, opacity: 0.55 }, hovertemplate: `%{x:.1f} %, %{y:.3~g} mD<extra>${name}</extra>` } }),
      { xaxis: { title: { text: 'porosity, %' }, range: [0, 40] }, yaxis: { type: 'log', title: { text: 'permeability, mD' } } })
    plot('c-por', [histo(p.porosity, S(3))], { xaxis: { title: { text: '%' } } })
    plot('c-perm', [histo(p.perm, S(1))], { xaxis: { type: 'log', title: { text: 'mD' } } })
    plot('c-depth', [{ type: 'scatter', mode: 'lines', x: p.depth.map((x) => x.p90), y: p.depth.map((x) => x.md), line: { width: 0 }, showlegend: false, hoverinfo: 'skip' },
      { type: 'scatter', mode: 'lines', x: p.depth.map((x) => x.p10), y: p.depth.map((x) => x.md), fill: 'tonextx', fillcolor: 'rgba(91,140,255,.18)', line: { width: 0 }, name: 'P10 to P90', hoverinfo: 'skip' },
      { type: 'scatter', mode: 'lines+markers', x: p.depth.map((x) => x.p50), y: p.depth.map((x) => x.md), line: { color: S(1), width: 2 }, marker: { size: 5 }, name: 'median', hovertemplate: '%{y} m: %{x:.1f} %<extra></extra>' }],
    { yaxis: { autorange: 'reversed', title: { text: 'm MD' } }, xaxis: { title: { text: 'porosity, %' } } })
    map($('m-rp'), p.wells, () => S(3), (w) => `<b>${esc(w.name)}</b><br>${num(w.plugs)} plugs, median ${num(w.por, 1)} %<br><a href="#well/${encodeURIComponent(w.name)}">all data</a>`)
    plot('c-rock', [bar(p.rocks.slice(0, 10), { h: true, color: S(3) })], { yaxis: { autorange: 'reversed' }, xaxis: { type: 'log' }, margin: { l: 110, r: 10, t: 10, b: 40 } })
    plot('c-grain', [bar(p.grain, { h: true, color: S(1) })], { yaxis: { autorange: 'reversed', tickfont: { size: 10 } }, margin: { l: 190, r: 10, t: 10, b: 40 } })
    plot('c-cem', [bar(p.cement, { h: true, color: S(7) })], { yaxis: { autorange: 'reversed', tickfont: { size: 10 } }, margin: { l: 150, r: 10, t: 10, b: 40 } })
  }

  // ---------- text corpus ----------
  const CATS = { g: 'geology, cuttings', l: 'lithology description', b: 'biostratigraphy', d: 'service job report', pp: 'petrophysics', dd: 'drilling data sheet', r: 'rig report, BHA', gc: 'geochemistry', ref: 'references' }
  const SRC = { relinquishment: 'Norway: relinquishment reports', diskos: 'Norway: Diskos reports', uk: 'UK: NSTA well reports', nl: 'Netherlands: NLOG reports' }
  VIEWS.text = async (d) => {
    const p = await profile('text')
    const srcs = Object.keys(SRC).filter((s) => p[s])
    const sum = (f) => srcs.reduce((a, s) => a + p[s][f], 0)
    const rq = p.relinquishment
    view.innerHTML = `${head(d)}${plain(
      `${num(sum('pages'))} pages of text from ${num(sum('documents'))} public documents, read by ${T('ocr', 'OCR')} from scans. Each page carries a flag for whether it reads as real language or ${T('gibberish')}.`,
      'Most of what the industry knows about its wells sits in old scanned reports. This is the largest public collection of that text: training and test material for search and language models.',
      `Search over Norwegian, UK and Dutch reports together; a "why licences fail" analysis from the ${T('relinquishment', 'relinquishment reports')}; a page classifier to drop gibberish before indexing.`)}
      ${kpis([[num(sum('documents')), 'documents'], [num(sum('pages')), 'pages'], ...srcs.map((s) => [`${num(p[s].natural_share, 0)} %`, `real text, ${SRC[s].split(':')[0]} ${SRC[s].split(': ')[1].split(' ')[0]}`])])}
      ${panel('The four sources', table([['Source', (r) => esc(SRC[r])], ['Documents', (r) => num(p[r].documents), 'num'], ['Pages', (r) => num(p[r].pages), 'num'], ['Real text', (r) => `${num(p[r].natural_share, 1)} %`, 'num'], ['Median characters per page', (r) => num(p[r].median_chars), 'num'], ['File', (r) => gb(p[r].bytes), 'num']], srcs), 'pages flagged as not real text are mostly scanned logs, tables and figures.')}
      <div class="grid g2">${panel('Characters per page', chart('c-chars', 320), 'each line is one source, as a share of its own pages (log scale). A full typed page is 2,000 to 4,000 characters; the hump at a few hundred is mostly figures, tables and covers.')}
        ${p.uk && p.uk.tags.length ? panel('UK reports by type', chart('c-tags', 320), 'NSTA\'s own tag per document: end-of-well reports (DRILL_EOWR), geochemistry, cores, well summaries.') : '<div></div>'}</div>
      ${rq ? `<div class="grid g2">${panel(`Relinquished licences (${num(rq.licences)}, ${num(rq.matched)} found in FactPages)`, chart('c-ended', 320), `the end date FactPages gives each licence. A future date means only part of the area was given back and the rest is still held. Each report says why: the prospect was dry, too small, or the seal failed.`)}
        ${panel('Relinquished licences by area', chart('c-area', 320))}</div>` : ''}
      ${p.annotated ? panel(`Hand-classified pages (${num(p.annotated.pages)})`, `<div class="grid g2"><div>${chart('c-ann', 340)}</div><div>${(p.annotated.examples || []).map((e) => `<div class="qa"><span class="tag">${esc(e.k)}</span> <b>${esc(CATS[e.k] || 'unknown')}</b><div class="sample" style="max-height:90px;margin-top:.3rem">${esc(e.text)}</div></div>`).join('')}</div></div>`, 'pages labelled by people with a content category: training data for a page classifier. The file gives only the codes; the meanings are our reading of the sample pages.') : ''}
      ${panel('Sample pages', `<div class="row" style="margin-bottom:.7rem"><div class="seg" id="tsrc">${srcs.map((s, i) => `<button class="${i ? '' : 'on'}" data-s="${s}">${esc(SRC[s].split(': ')[1])}</button>`).join('')}</div><div class="seg" id="tkind"><button class="on" data-k="text">real text</button><button data-k="gibberish">gibberish</button></div></div><div id="tsamples"></div>`)}
      ${terms(['ocr', 'gibberish', 'relinquishment', 'licence', 'diskos', 'completion_report', 'passage', 'rag'])}`
    plot('c-chars', srcs.map((s, i) => { const h = histo(p[s].chars, S(i + 1), true); return { type: 'scatter', mode: 'lines', x: h.x, y: h.y, name: SRC[s].split(': ')[1], line: { color: S(i + 1), width: 2, shape: 'spline' }, hovertemplate: h.hovertemplate } }), { xaxis: { type: 'log', title: { text: 'characters on the page' } }, yaxis: { title: { text: '% of the source\'s pages' } } })
    if (p.uk && p.uk.tags.length) plot('c-tags', [bar(p.uk.tags, { h: true })], { yaxis: { autorange: 'reversed', tickfont: { size: 10 } }, margin: { l: 170, r: 10, t: 10, b: 40 } })
    if (rq) { plot('c-ended', [bar(rq.ended, { color: S(2) })]); plot('c-area', [bar(rq.areas, { h: true, color: S(2) })], { margin: { l: 120, r: 10, t: 10, b: 40 } }) }
    if (p.annotated) plot('c-ann', [bar(p.annotated.categories.map((c) => ({ k: `${c.k}: ${CATS[c.k] || '?'}`, n: c.n })), { h: true, color: S(3) })], { yaxis: { autorange: 'reversed' }, margin: { l: 190, r: 10, t: 10, b: 40 } })
    let src = srcs[0], kind = 'text'
    const draw = () => { const list = (p[src].samples || {})[kind] || []; $('tsamples').innerHTML = list.length ? list.map((s) => `<div class="qa"><div class="muted small mono">${esc(s.file)} · page ${s.page}</div><div class="sample">${esc(s.text)}</div></div>`).join('') : '<div class="empty">No sample.</div>' }
    $('tsrc').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; src = b.dataset.s; for (const x of $('tsrc').children) x.classList.toggle('on', x === b); draw() }
    $('tkind').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; kind = b.dataset.k; for (const x of $('tkind').children) x.classList.toggle('on', x === b); draw() }
    draw()
  }

  // ---------- completion reports ----------
  VIEWS.completion = async (d) => {
    const p = await profile('completion')
    const k = p.kpis, u = p.unpacked
    view.innerHTML = `${head(d)}${plain(
      `The ${T('completion_report', 'final well report')} of ${num(k.wellbores)} wellbores from the early 1970s to the mid 2010s: ${num(k.pdf)} scanned PDFs (${num(k.pdf_gb, 0)} GB) and ${num(k.json)} JSON files where a layout model and other models have turned each page, table and figure into structured text.`,
      'It is the one document that says what happened in a well: rocks, logs, cores, tests, problems, how it was left. Until now it took a person hours per report to dig out; the JSON makes the whole shelf searchable.',
      'Search and question answering over every well (DISKOS-QA as the test), extracting casing, plugs and cement for P&A planning, drilling hazards for new wells, checking FactPages against the reports.')}
      ${kpis([[num(k.wellbores), 'wellbores'], [num(k.pdf), 'PDF reports'], [num(k.json), 'JSON reports'], [`${num(k.pdf_gb, 0)} GB`, 'of PDFs'], [`${num(k.median_mb, 0)} MB`, 'median PDF'], [num(k.in_factpages), 'wellbores found in FactPages']])}
      ${u ? kpis([[num(u.json_files), 'JSON reports unpacked'], [`~${num(u.pages_est)}`, 'pages in all (estimated)'], [num(u.median_pages), 'pages in a median report'], [`${num(u.table_share, 0)} %`, 'of pages hold a table'], [`${num(u.figure_share, 0)} %`, 'of pages hold a figure'], [num(u.wellbore_folders), 'wellbore folders']]) : `<div class="callout warn">The 112 GB archive is still downloading or not yet unpacked, so this page shows the metadata only. Once unpacked, rerun <code>uv run python -m sketches.atlas completion</code>.</div>`}
      ${u ? panel('Read a report', `<div class="row end"><label class="field grow">Wellbore<input id="rq" placeholder="e.g. 15/9-F-5, 30/9-12, 1/2-1" /></label><button class="btn" id="rgo">Open its reports</button></div><div class="chips" style="margin-top:.6rem">${['15/9-F-5', '30/9-12', '35/4-1', '16/10-1', '25/9-1'].map((w) => `<button class="chip" data-w="${w}">${w}</button>`).join('')}</div><div id="rview"></div>`, 'each JSON report is a list of pages. Every page has the OCR text as markdown (tables as markdown tables), an AI summary with tags and figure descriptions, and a quality grade. Click a page to read it; the PDF link opens the scan at that page.') : ''}
      ${u ? `<div class="grid g2">${panel('Page quality', chart('c-q', 280), `the pipeline grades every page. Reliable: clean text. Acceptable: usable with some errors. Uncertain: poor scan. Figure-dominated: mostly a plot or diagram. From ${num(u.pages_sampled)} pages in ${num(u.sampled)} sampled reports.`)}
        ${panel('What the layout model found', chart('c-el', 280), 'blocks on the pages by type. Tables are everywhere: casing, mud, tests, surveys, core analyses.')}</div>
      <div class="grid g2">${panel('What the pages are about', chart('c-tags', 560), 'the AI tags most often attached to pages. Drilling, casing and cementing dominate: these reports are first of all records of how the hole was made.')}
        <div class="stack">${panel('Pages per report', chart('c-pages', 250))}${panel('Share of reliable pages per report', chart('c-rel', 230), 'most reports are mostly clean; a tail of poor scans needs care.')}</div></div>
      ${panel('Sample pages', (u.samples || []).map((x) => `<div class="qa"><div class="row"><span class="tag">${esc(x.wellbore)}</span><span class="tag">page ${x.page}</span><span class="tag">${esc(x.quality)}</span>${x.tags.slice(0, 5).map((t) => `<span class="tag blue">${esc(t)}</span>`).join('')}</div><div class="a" style="margin-top:.4rem">${esc(x.summary)}</div><details><summary>The text</summary><div class="sample">${esc(x.text)}</div></details></div>`).join(''))}` : ''}
      <div class="grid g2">${panel('Wellbores by type', chart('c-type', 280), 'exploration wellbores look for oil and gas; development wellbores produce or inject on a field.')}${panel('Wellbores by decade drilled', chart('c-dec', 280), 'from the FactPages spud date. Most reports are from wells drilled in the 1990s and 2000s; few after 2010, since reports are released only after a confidentiality period.')}</div>
      <div class="grid g2">${panel('Who delivered the reports', chart('c-comp', 420), 'the operator that wrote the report. Statoil and Norsk Hydro appear under their old names.')}
        ${panel('PDF size', chart('c-size', 420), 'megabytes, log scale. Big files are long scanned reports with log plots and enclosures.')}</div>
      ${panel('The metadata columns', table([['Column', (r) => `<span class="mono">${esc(r.k)}</span>`], ['Example', (r) => `<span class="muted">${esc(r.example)}</span>`]], p.columns, 420), 'one row per file. Wellbore Name joins to everything else; FolderFileName is the file inside the archive.')}
      ${terms(['completion_report', 'wellbore', 'exploration', 'development', 'ocr', 'diskos', 'casing', 'core', 'dst', 'pa'])}`
    plot('c-type', [bar(p.types, { h: true })], { margin: { l: 120, r: 10, t: 10, b: 40 } })
    plot('c-dec', [bar(p.decade, { color: S(3) })])
    plot('c-comp', [bar(p.companies, { h: true, color: S(1) })], { yaxis: { autorange: 'reversed', tickfont: { size: 10 } }, margin: { l: 200, r: 10, t: 10, b: 40 } })
    plot('c-size', [histo(p.size, S(7))], { xaxis: { type: 'log', title: { text: 'MB' } } })
    if (u) {
      plot('c-q', [bar(u.quality, { h: true, color: S(3) })], { yaxis: { autorange: 'reversed' }, margin: { l: 130, r: 10, t: 10, b: 40 } })
      plot('c-el', [bar(u.elements, { h: true, color: S(1) })], { yaxis: { autorange: 'reversed' }, xaxis: { type: 'log' }, margin: { l: 130, r: 10, t: 10, b: 40 } })
      plot('c-tags', [bar(u.tags, { h: true, color: S(7) })], { yaxis: { autorange: 'reversed', tickfont: { size: 10 } }, margin: { l: 130, r: 10, t: 10, b: 40 } })
      plot('c-pages', [histo(u.pages, S(1))], { xaxis: { title: { text: 'pages' } } })
      plot('c-rel', [histo(u.reliable, S(3))], { xaxis: { title: { text: '% reliable pages' } } })
      const open = (w) => { $('rq').value = w; reportViewer($('rview'), w) }
      $('rgo').onclick = () => open($('rq').value.trim())
      $('rq').onkeydown = (e) => { if (e.key === 'Enter') open($('rq').value.trim()) }
      for (const c of view.querySelectorAll('.chip[data-w]')) c.onclick = () => open(c.dataset.w)
    }
  }

  // a wellbore's structured reports: pick a report, scan its page summaries, read a page in full
  async function reportViewer(el, w) {
    if (!w) return
    el.innerHTML = '<p><span class="thinking"><span class="spin"></span>Reading the reports</span></p>'
    const d = await get(`api/reports/${encodeURIComponent(w)}`).catch((e) => ({ error: e.message }))
    if (d.error) { el.innerHTML = `<div class="callout err" style="margin-top:.8rem">${esc(d.error)}</div>`; return }
    let ri = 0
    const QC = { Reliable: 'green', Acceptable: 'blue', Uncertain: 'amber', 'Figure-dominated': '' }
    const draw = () => {
      const r = d.reports[ri], pdfUrl = r.pdf ? `api/pdf/${encodeURIComponent(d.folder)}/${encodeURIComponent(r.pdf)}` : ''
      el.innerHTML = `<div style="margin-top:1rem">${d.reports.length > 1 ? `<div class="seg" id="rsel" style="margin-bottom:.7rem">${d.reports.map((x, i) => `<button class="${i === ri ? 'on' : ''}" data-i="${i}">${esc(x.title || x.file)}</button>`).join('')}</div>` : ''}
        <div class="row"><b>${esc(r.title || r.file)}</b><span class="muted small">${r.pages.length} pages · released ${esc((r.released || '').slice(0, 10))}</span>${pdfUrl ? `<a class="btn ghost" href="${pdfUrl}" target="_blank" rel="noopener">Open the PDF</a>` : ''}</div>
        <p class="muted small">${esc(r.quality || '')}</p>
        <div class="split" style="margin-top:.6rem"><div class="table-wrap" style="max-height:560px">${table([['Page', (p) => num(p.n), 'num'], ['Quality', (p) => `<span class="tag ${QC[p.quality] || ''}">${esc(p.quality || '')}</span>`], ['Summary', (p) => `<span style="white-space:normal">${esc(p.summary || '')}</span>`], ['', (p) => (p.tables ? '<span class="tag">table</span>' : '') + (p.figures ? ' <span class="tag">figure</span>' : '')]], r.pages, 560).replace(/<tr>/g, '<tr class="pg">')}</div>
        <div id="rpage"><div class="empty">Click a page to read it.</div></div></div></div>`
      if ($('rsel')) $('rsel').onclick = (e) => { const b = e.target.closest('button'); if (b) { ri = +b.dataset.i; draw() } }
      el.querySelectorAll('tbody tr').forEach((tr, i) => { tr.style.cursor = 'pointer'; tr.onclick = () => { el.querySelectorAll('tbody tr').forEach((x) => x.classList.remove('sel')); tr.classList.add('sel'); page(r, r.pages[i].n, pdfUrl) } })
    }
    const page = async (r, n, pdfUrl) => {
      $('rpage').innerHTML = '<span class="thinking"><span class="spin"></span>Loading</span>'
      const p = await get(`api/page/${encodeURIComponent(w)}?file=${encodeURIComponent(r.file)}&n=${n}`).catch((e) => ({ error: e.message }))
      if (p.error) { $('rpage').innerHTML = `<div class="callout err">${esc(p.error)}</div>`; return }
      $('rpage').innerHTML = `<div class="row"><b>Page ${n}</b><span class="tag">${esc(p.quality || '')}</span>${(p.ai.tags || []).map((t) => `<span class="tag blue">${esc(t)}</span>`).join('')}${pdfUrl ? `<a href="${pdfUrl}#page=${n + 1}" target="_blank" rel="noopener" class="small">scan of this page</a>` : ''}</div>
        <p class="a">${esc(p.ai.page_summary || '')}</p>${(p.ai.figure_details || []).map((f) => `<p class="muted small">${esc(f)}</p>`).join('')}
        <div class="sample" style="max-height:440px">${esc(p.markdown)}</div>
        <p class="muted small">Layout blocks: ${Object.entries(p.elements || {}).map(([k_, v]) => `${esc(k_)} ${v}`).join(' · ')}</p>`
    }
    draw()
  }

  // ---------- seismic ----------
  Object.assign(G, {
    crossline: ['Crossline', 'A row of the 3D grid at right angles to the inlines. An inline section and a crossline section cross at one trace.'],
    timeslice: ['Time slice', 'A horizontal cut through the cube at one two-way time: a map of amplitude. Faults show as lines where the pattern breaks.'],
    bin: ['Bin', 'One cell of the 3D grid. All recordings that bounced off the same patch of ground are stacked into one trace per bin. Adele: 12.5 m by 37.5 m; F3: 25 m.'],
    sample: ['Sample', 'One value on a trace. Both cubes sample every 4 ms.'],
    pstm: ['PSTM', 'Pre-stack time migration: processing that moves echoes to where they truly came from, before stacking, with the vertical axis kept in time. PSDM does the same in depth.'],
    stack: ['Stack', 'The average of many recordings of one bin, which cuts noise. A full offset stack uses every source to receiver distance.'],
    migration: ['Migration', 'Processing that puts dipping layers and faults in their true position; without it, faults blur into curved smiles.'],
    coherence: ['Coherence (semblance)', 'An attribute: how alike neighbouring traces are in a short time window, 0 to 1. Faults and chaotic rock score low. Shown here as 1 minus coherence, so breaks are bright.'],
    attribute: ['Seismic attribute', 'Any number computed from the amplitudes (coherence, RMS, frequency) that brings out one feature.'],
    rms: ['RMS amplitude', 'Root mean square: the average strength of the signal over a window. Used for loudness and QC maps.'],
    spectrum: ['Frequency spectrum', 'How much energy the trace has at each frequency. Higher frequencies resolve thinner layers.'],
    dominant: ['Dominant frequency', 'The frequency with the most energy. Adele about 11 Hz; F3 has a broader band up to about 40 Hz.'],
    nyquist: ['Nyquist frequency', 'The highest frequency a sampling can hold: half the sampling rate, 125 Hz at 4 ms.'],
    tuning: ['Tuning thickness', 'About a quarter of the wavelength (velocity / frequency). Beds thinner than this blur into one reflection. Adele: roughly 70 to 90 m.'],
    wavelet: ['Wavelet', 'The shape of the sound pulse as recorded. Every reflection is a copy of it, scaled by how strong the boundary is.'],
    polarity: ['Polarity', 'Whether a boundary into harder rock shows as a positive (red) or negative (blue) peak. It depends on the processing.'],
    dead: ['Dead trace', 'A trace of all zeros: no data at that bin. Adele\'s 8 westernmost crosslines are dead.'],
    spike: ['Spike', 'A burst of absurd values in a trace, an acquisition or processing error. One Adele trace reaches -350,841 where normal data stays within ±1,600.'],
    clip: ['Clip / gain', 'How strong an amplitude gets full colour. Lower clip (more gain) brings out weak reflections and saturates strong ones.'],
    wiggle: ['Wiggle trace', 'One trace drawn as a line, with the positive half filled: the classic way to look at a single trace.'],
    horizon: ['Horizon', 'One reflector picked and followed across the cube, usually standing for a formation top.'],
    throw: ['Fault throw', 'How far the layers moved up or down across a fault. Small throws hide below the tuning thickness.'],
    clinoform: ['Clinoform', 'Sloping layers at the front of a growing delta. F3\'s Upper North Sea has large ones.'],
    salt: ['Salt diapir', 'Salt is light and flows; it rises in domes and pillars that push the layers above. F3\'s Zechstein.'],
    texture: ['Seismic texture', 'The look of a region: parallel, wavy, chaotic or blank reflections. Facies are told apart by texture.'],
    header_text: ['Textual header', 'The first 3,200 bytes of a SEG-Y file: 40 lines of 80 characters (EBCDIC) saying where, when and how the data was made.'],
    header_bin: ['Binary header', 'The next 400 bytes of a SEG-Y file: numbers for the whole file, such as sample interval, samples per trace and number format.'],
    header_trace: ['Trace header', '240 bytes before every trace: its inline and crossline numbers, coordinates, start time and sample count.'],
    ebcdic: ['EBCDIC', 'An old IBM character encoding. SEG-Y text headers usually use it, so read them as cp500 or cp037, not ASCII.'],
    ieee: ['IEEE / IBM float', 'Two ways of storing 4-byte numbers. SEG-Y format code 5 is IEEE (Adele), code 1 the older IBM float.'],
    scalar: ['Coordinate scalar', 'A trace header number saying how to scale X and Y: -100 means divide by 100. Forgetting it puts the survey 100 times too far away.'],
    utm: ['UTM / MGA', 'A map projection with coordinates in metres east and north within a zone. Adele uses MGA zone 51 (Australia\'s UTM on the GDA94 datum).'],
    impedance: ['Acoustic impedance', 'Density times sound speed. A reflection happens where it changes; its strength is the reflection coefficient (AI2 - AI1) / (AI2 + AI1).'],
    synthetic: ['Synthetic seismogram', 'A trace computed from a well\'s sonic and density logs, to tie the well\'s depths to the seismic times.'],
    checkshot: ['Checkshot', 'A survey that times a surface shot down to known depths in a well: the time to depth link.'],
    iou: ['IoU', 'Intersection over union: overlap of the predicted and true area of a class. Mean IoU over classes is the usual segmentation score, fair to small classes.'],
    imbalance: ['Class imbalance', 'Some labels are far rarer than others (Zechstein 1.5 %). A model can ignore them and still look accurate.'],
    split: ['Train / test split', 'The training block teaches a model; test blocks it never saw check it. F3\'s test 1 lies beside the training block, test 2 on its far side.'],
  })
  const SEIS_TERMS = ['seismic', 'inline', 'crossline', 'timeslice', 'trace', 'sample', 'twt', 'bin', 'amplitude', 'clip', 'wiggle', 'spectrum', 'dominant', 'tuning',
    'coherence', 'fault', 'throw', 'horizon', 'facies', 'texture', 'pstm', 'stack', 'migration', 'segy', 'header_text', 'header_bin', 'header_trace', 'scalar', 'dead', 'spike']
  const FAC = () => [S(1), S(2), S(3), S(4), S(5), S(6)]
  const rgb = (hex) => { const n = parseInt(hex.replace('#', ''), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255] }
  const seisProfile = (c) => get(`api/seis/profile/${c}`)
  const getBin = async (u) => {
    const r = await fetch(u)
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`)
    const [h, w] = r.headers.get('X-Shape').split(',').map(Number)
    return { h, w, buf: await r.arrayBuffer(), labels: r.headers.get('X-Labels') === '1', top: +r.headers.get('X-Top') || 0 }
  }

  // one cube's geometry: slider ranges, survey numbers, where a pixel of each view sits in the cube, and the axes of each view
  function geometry(cube, meta, split) {
    if (cube === 'adele') {
      const g = meta.grid, NI = g.n_inlines, NX = g.n_crosslines, NS = g.samples, ILM = g.bin_m.between_stored_inlines, XLM = g.bin_m.along_inline
      const east = { name: 'crossline', n: NX, line: (p) => 5670 + NX - 1 - p, m: XLM, from: 'the west edge' } // columns run west to east
      return {
        n: { inline: NI, crossline: NX, time: NS },
        label: { inline: (i) => `inline ${4175 + 2 * i}`, crossline: (i) => `crossline ${5670 + i}`, time: (i) => `${num(1500 + 4 * i)} ms` },
        il: (i) => 4175 + 2 * i, xl: (i) => 5670 + i, t: (k) => 1500 + 4 * k,
        // pixel (row, col) of a view -> cube indices [il, xl, k]; the server flips views so east is right and north up
        at: { inline: (r, c, s) => [s.inline, NX - 1 - c, r], crossline: (r, c, s) => [c, s.crossline, r], time: (r, c, s) => [NI - 1 - r, NX - 1 - c, s.time] },
        to: { inline: (il, xl, k) => [k, NX - 1 - xl], crossline: (il, xl, k) => [k, il], time: (il, xl, k) => [NI - 1 - il, NX - 1 - xl] },
        // axes of each view: the horizontal and vertical quantity, its length in pixels, line number at pixel p, metres per pixel
        ax: { inline: { x: east, y: 'time' }, crossline: { x: { name: 'inline', n: NI, line: (p) => 4175 + 2 * p, m: ILM, from: 'the south edge' }, y: 'time' },
          time: { x: east, y: { name: 'inline', n: NI, line: (p) => 4175 + 2 * (NI - 1 - p), m: ILM, from: 'the north edge' } } },
        dist: { inline: [ILM, 'the south edge'], crossline: [XLM, 'the east edge'] }, // where the slider's own position counts from
        xy: (il, xl) => [g.corners_xy.il4175_xl5670[0] - xl * XLM, g.corners_xy.il4175_xl5670[1] + il * ILM], // UTM metres
        vel: 2500,
        // metres from the west edge / south edge of a crossline or inline index, and back
        X: (xl) => (NX - 1 - xl) * XLM, Y: (il) => il * ILM, iX: (x) => NX - 1 - Math.round(x / XLM), iY: (y) => Math.round(y / ILM),
        edges: { inline: ['west · crossline 8400', 'east · crossline 5670', '1,500 ms', '5,500 ms'], crossline: ['south · inline 4175', 'north · inline 4775', '1,500 ms', '5,500 ms'],
          time: ['west · crossline 8400', 'east · crossline 5670', 'north · inline 4775', 'south · inline 4175'] },
        aspect: { time: ((NX - 1) * XLM) / ((NI - 1) * ILM) }, amp: (v) => (v * meta.clip) / 127, gain: +(meta.clip / meta.amplitude.percentiles['99']).toFixed(1),
        start: { inline: 150, crossline: 1365, time: 500 },
      }
    }
    const sp = meta.splits[split], [NI, NX, NS] = sp.shape, [i0, i1] = sp.inlines, [x0, x1] = sp.crosslines, M = meta.bin_m
    const xl = { name: 'crossline', n: NX, line: (p) => x0 + p, m: M, from: `crossline ${x0}` }
    const il = { name: 'inline', n: NI, line: (p) => i0 + p, m: M, from: `inline ${i0}` }
    return {
      n: { inline: NI, crossline: NX, time: NS },
      label: { inline: (i) => `inline ${i0 + i}`, crossline: (i) => `crossline ${x0 + i}`, time: (i) => `${4 * i} ms (sample ${i})` },
      il: (i) => i0 + i, xl: (i) => x0 + i, t: (k) => 4 * k,
      at: { inline: (r, c, s) => [s.inline, c, r], crossline: (r, c, s) => [c, s.crossline, r], time: (r, c, s) => [r, c, s.time] },
      to: { inline: (il, xl, k) => [k, xl], crossline: (il, xl, k) => [k, il], time: (il, xl, k) => [il, xl] },
      ax: { inline: { x: xl, y: 'time' }, crossline: { x: il, y: 'time' }, time: { x: xl, y: il } },
      dist: { inline: [M, `inline ${i0}`], crossline: [M, `crossline ${x0}`] },
      xy: null, vel: 2000,
      X: (xl) => xl * M, Y: (il) => il * M, iX: (x) => Math.round(x / M), iY: (y) => Math.round(y / M),
      edges: { inline: [`crossline ${x0}`, `crossline ${x1}`, '0 ms', '1,016 ms'], crossline: [`inline ${i0}`, `inline ${i1}`, '0 ms', '1,016 ms'], time: [`crossline ${x0}`, `crossline ${x1}`, `inline ${i0}`, `inline ${i1}`] },
      aspect: { time: ((NX - 1) * M) / ((NI - 1) * M) }, amp: (v) => v / 127, gain: +(127 / (sp.percentiles['99'] * 127)).toFixed(1),
      start: { inline: Math.floor(NI / 2), crossline: Math.floor(NX / 2), time: 200 },
    }
  }

  // round tick values between two numbers
  function niceTicks(lo, hi, want) {
    const a = Math.min(lo, hi), b = Math.max(lo, hi), raw = (b - a) / Math.max(1, want), mag = 10 ** Math.floor(Math.log10(raw || 1)), f = raw / mag
    const step = (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * mag, out = []
    for (let v = Math.ceil(a / step - 1e-9) * step; v <= b + step * 1e-9; v += step) out.push(+v.toFixed(8))
    return out
  }

  // the explorer: slices in three directions, amplitude or coherence, F3 labels on top, click for the trace;
  // axes on the image, the slider and axes in line numbers or distance, time or (assumed-velocity) depth
  function explorer(el, cube, meta, onTrace) {
    const st = { axis: 'inline', split: 'train', gain: 0, cmap: 'rwb', layer: 'amp', labels: cube === 'f3', alpha: 0.45, pick: null, hu: 'line', vu: 'time', v: 0 }
    let geo = geometry(cube, meta, st.split), img = null, running = false, want = null
    Object.assign(st, { ...geo.start }, { gain: geo.gain, v: geo.vel })
    // one vertical exaggeration for the section and the 3D box (1 = true scale); the default makes a section about 1.8 wide to 1 tall
    const defVE = () => { const W = (geo.n.crossline - 1) * geo.ax.inline.x.m, dz = (st.v * (geo.t(geo.n.time - 1) - geo.t(0))) / 2000; return Math.max(1, Math.min(20, Math.round((W / dz / 1.8) * 2) / 2)) }
    st.ve = defVE()
    el.innerHTML = `<div class="xsplit" id="xsplit"><div class="xmain" id="xmain"><div class="row" style="gap:.5rem 1rem;flex-wrap:wrap;align-items:center">
        <div class="seg" id="xa">${['inline', 'crossline', 'time'].map((a) => `<button data-a="${a}" class="${a === st.axis ? 'on' : ''}">${a === 'time' ? 'Time slice' : a[0].toUpperCase() + a.slice(1)}</button>`).join('')}</div>
        ${cube === 'f3' ? `<label class="small">Block <select id="xs">${Object.keys(meta.splits).map((s) => `<option value="${s}">${s === 'train' ? 'train' : s.replace('test', 'test ')}</option>`).join('')}</select></label>` : ''}
        <label class="small">Show <select id="xl"><option value="amp">amplitude</option><option value="coh">coherence (faults)</option></select></label>
        <label class="small">Colours <select id="xc"><option value="rwb">red-white-blue</option><option value="grey">grey</option></select></label>
        <label class="small">Gain <input id="xg" type="range" min="0.5" max="10" step="0.1" value="${st.gain}" style="width:110px;vertical-align:middle" /></label>
        ${cube === 'f3' ? `<label class="small"><input id="xf" type="checkbox" checked /> labels</label><label class="small">Label opacity <input id="xo" type="range" min="0" max="0.9" step="0.05" value="${st.alpha}" style="width:80px;vertical-align:middle" /></label>` : ''}
      </div>
      <div class="row" style="gap:.5rem 1rem;flex-wrap:wrap;align-items:center;margin-top:.5rem">
        <span class="small muted">Axes and slider in</span>
        <label class="small">Position <select id="xhu"><option value="line">line numbers</option><option value="dist">distance (m)</option></select></label>
        <label class="small">Vertical <select id="xvu"><option value="time">time (ms)</option><option value="depth">approx. depth (m)</option></select></label>
        <label class="small" id="xvw" hidden>Velocity <input id="xv" type="number" min="1000" max="7000" step="100" value="${st.v}" style="width:76px" /> m/s
          <span class="muted">(assumed: ${cube === 'adele' ? 'no wells in this cube' : 'a guess for the shallow North Sea'}; depth = velocity × time / 2)</span></label>
        <label class="small">Vertical exaggeration <input id="xve" type="range" min="1" max="20" step="0.5" value="${st.ve}" style="width:130px;vertical-align:middle" /> <b id="xvev" class="mono">${st.ve}×</b></label>
        <span class="muted small">the same in the section and the 3D box; 1× is true scale</span>
      </div>
      <div class="row" style="margin:.6rem 0 .4rem;gap:.6rem;align-items:center"><button class="btn sm" id="xm">−</button>
        <span id="xlo" class="small muted mono" style="min-width:64px;text-align:right"></span>
        <input id="xi" type="range" min="0" style="flex:1" /><span id="xhi" class="small muted mono" style="min-width:64px"></span><button class="btn sm" id="xp">+</button>
        <div id="xn" class="mono" style="min-width:190px;text-align:right;line-height:1.3"></div></div>
      <div class="axframe" id="axframe">
        <div class="axt-y" id="xty"></div><svg class="ax" id="xsy"></svg>
        <div class="canvas-wrap" style="position:relative"><canvas id="xcv" style="height:auto;cursor:crosshair"></canvas><div id="xbusy" class="muted small" style="position:absolute;top:6px;right:10px"></div></div>
        <div></div><div></div><svg class="ax" id="xsx"></svg>
        <div></div><div></div><div class="axt-x" id="xtx"></div>
      </div>
      <div class="row small muted" style="justify-content:space-between;margin-top:.25rem"><span id="xe0"></span><span id="xr" class="mono" style="color:var(--ink-2)">Hover for values, click for the trace</span><span id="xe1"></span></div>
      <div class="row" style="justify-content:space-between;margin-top:.5rem"><div class="meta" id="xinfo" style="margin:0"></div><div class="cbar" id="xcb"></div></div>
      <div class="small muted" id="xev" style="margin-top:.3rem"></div>
      ${cube === 'f3' ? legend(meta.facies.map((f, i) => [FAC()[i], f])) : ''}</div>
      <aside class="x3d"><div class="x3h"><b class="x3title">Where you are</b>
          <span class="x3tools row" style="gap:.3rem"><button class="btn sm" data-cam="iso">Reset</button><button class="btn sm" data-cam="top">Top</button><button class="btn sm" data-cam="side">Side</button></span>
          <button class="btn sm" id="x3t" title="Hide or show the 3D model"></button></div>
        <div class="x3body"><div class="x3opts small row" style="gap:.4rem .9rem;margin:.4rem 0"><label><input id="x3a" type="checkbox" checked /> all other slices, faint</label> <label>in <select id="x3d"><option value="this">this direction</option><option value="all">all three directions</option></select></label> <label>sheets <input id="x3n" type="range" min="4" max="60" step="1" value="24" style="width:80px;vertical-align:middle" /> <b id="x3nv" class="mono">24</b></label> <label>faintness <input id="x3o" type="range" min="0.03" max="0.4" step="0.01" value="0.12" style="width:80px;vertical-align:middle" /></label></div><div id="x3" style="height:${Math.round(Math.max(400, Math.min(820, innerHeight * 0.58)))}px"></div><div id="x3info" class="small" style="margin-top:.4rem"></div></div></aside></div>`
    const q = (id) => el.querySelector(`#${id}`)
    const cv = q('xcv')
    const z = (t) => (st.v * t) / 2000 // approximate depth in metres from two-way time in ms
    // the picture has the true shape of the ground it shows: metres across by metres down times the vertical exaggeration,
    // the same numbers the 3D box uses. A narrow section is drawn narrower, not stretched.
    const fit = () => {
      const { x, y } = geo.ax[st.axis]
      const W = (x.n - 1) * x.m, H = y === 'time' ? (z(geo.t(geo.n.time - 1)) - z(geo.t(0))) * st.ve : (y.n - 1) * y.m
      const maxH = Math.max(460, Math.min(1000, innerHeight * 0.68)), avail = Math.max(300, q('xmain').clientWidth - 88)
      let w = avail, h = (w * H) / W
      if (h > maxH) { h = maxH; w = (h * W) / H }
      q('axframe').style.maxWidth = `${Math.round(w + 88)}px`
      cv.style.height = `${Math.round(h)}px`
    }

    // ---- units: what the slider, the axes and the readout say
    const dist = (axis, i) => `${num(i * geo.dist[axis][0])} m from ${geo.dist[axis][1]}`
    function slider(i) { // the two ways of saying where the slice is; the chosen unit leads
      const [line, other] = st.axis === 'time' ? [`${num(geo.t(i))} ms`, `≈ ${num(z(geo.t(i)))} m deep`] : [geo.label[st.axis](i), dist(st.axis, i)]
      const lead = st.axis === 'time' ? st.vu === 'depth' : st.hu === 'dist'
      return lead ? [other, line] : [line, other]
    }
    function sliderLabels() {
      const i = st[st.axis], n = geo.n[st.axis], [a, b] = slider(i)
      q('xn').innerHTML = `<b>${esc(a)}</b><br><span class="muted small">${esc(b)}</span>`
      const end = (j) => { const t = slider(j)[0]; return t.replace(/^(inline|crossline) /, '').replace(/ m from .*/, ' m').replace(/ ms$/, ' ms') }
      q('xlo').textContent = end(0); q('xhi').textContent = end(n - 1)
    }
    const span = (a) => { // the value at the first and last pixel of an axis, in the unit shown
      if (a === 'time') { const t0 = geo.t(0), t1 = geo.t(geo.n.time - 1); return st.vu === 'depth' ? [z(t0), z(t1)] : [t0, t1] }
      return st.hu === 'dist' ? [0, (a.n - 1) * a.m] : [a.line(0), a.line(a.n - 1)]
    }
    const title = (a) => (a === 'time' ? (st.vu === 'depth' ? `approx. depth (m), at ${num(st.v)} m/s` : 'two-way time (ms)') : st.hu === 'dist' ? `distance from ${a.from} (m)` : a.name)

    // ---- decoration: tick axes, colour bar, facts about this slice
    function axes() {
      const { x, y } = geo.ax[st.axis], W = cv.clientWidth, H = cv.clientHeight
      const draw = (svg, a, len, vertical) => {
        const [from, to] = span(a), pos = (v) => ((v - from) / (to - from)) * len
        svg.setAttribute('width', vertical ? 66 : len); svg.setAttribute('height', vertical ? len : 26)
        svg.innerHTML = niceTicks(from, to, vertical ? Math.round(len / 55) : Math.round(len / 105)).map((v) => { const p = pos(v); return vertical
          ? `<line x1="60" x2="66" y1="${p}" y2="${p}"/><text x="56" y="${p + 4}" text-anchor="end">${num(v)}</text>`
          : `<line y1="0" y2="6" x1="${p}" x2="${p}"/><text y="19" x="${p}" text-anchor="middle">${num(v)}</text>` }).join('')
      }
      draw(q('xsx'), x, W, false); draw(q('xsy'), y, H, true)
      q('xtx').textContent = `${title(x)} →`; q('xty').textContent = `${title(y)} ${y === 'time' ? '↓' : ''}`
    }
    function facts() {
      const { x, y } = geo.ax[st.axis], w = (x.n - 1) * x.m
      const km = (m) => `${num(m / 1000, 1)} km`
      const parts = []
      if (y === 'time') {
        const dz = z(geo.t(geo.n.time - 1)) - z(geo.t(0))
        parts.push(`vertical section, ${km(w)} wide`, `${num(geo.t(geo.n.time - 1) - geo.t(0))} ms tall (≈ ${km(dz)} at ${num(st.v)} m/s)`, `${num(x.n)} traces`, `vertical exaggeration ${num(st.ve, 1)}× (1× is true scale)`)
      } else parts.push(`map view, ${km(w)} by ${km((y.n - 1) * y.m)}`, `${num(x.n)} × ${num(y.n)} traces`, `north ${cube === 'adele' ? 'is up' : 'direction not given in the data'}`)
      parts.push(`full colour at ±${num(geo.amp(127) / st.gain, cube === 'f3' ? 2 : 0)}`)
      q('xinfo').innerHTML = parts.map((p) => `<span>${esc(p)}</span>`).join('')
    }
    function bar() {
      const c = geo.amp(127) / st.gain, d = cube === 'f3' ? 2 : 0
      const grey = st.cmap === 'grey' || (img?.labels && st.labels)
      q('xcb').innerHTML = img?.coh
        ? `<span>continuous</span><i style="background:linear-gradient(90deg,#000,#fff)"></i><span>broken (up to ${num(img.top, 2)})</span>`
        : `<span>−${num(c, d)}</span><i style="background:${grey ? 'linear-gradient(90deg,#010101,#808080,#fff)' : 'linear-gradient(90deg,rgb(40,40,255),#fff,rgb(255,40,40))'}"></i><span>+${num(c, d)}</span><span>amplitude</span>`
    }
    // ---- the 3D model: the cube as a transparent box with the slice planes in it, a faint stack of the other slices,
    // and the current plane strong on top; click a plane to move the slices there
    const PLANE = [S(1), S(2), S(3)] // inline, crossline, time
    let three = true, hooked = false, vol = null, volKey = '', sig3 = ''
    const st3 = { all: true, n: 24, op: 0.12, dirs: 'this' }
    try { three = localStorage.getItem('atlas-3d') !== 'closed' } catch { /* no storage: open */ }
    const zOf = (k) => (st.vu === 'depth' ? z(geo.t(k)) : geo.t(k))
    const CAM = { iso: { eye: { x: 1.55, y: -2.1, z: 1.2 }, up: { x: 0, y: 0, z: 1 } }, top: { eye: { x: 0, y: -0.001, z: 3.4 }, up: { x: 0, y: 1, z: 0 } }, side: { eye: { x: 0, y: -3.4, z: 0.03 }, up: { x: 0, y: 0, z: 1 } } }
    const RWB = [[0, 'rgb(40,40,255)'], [0.5, 'rgb(255,255,255)'], [1, 'rgb(255,40,40)']], GREY = [[0, 'rgb(1,1,1)'], [0.5, 'rgb(128,128,128)'], [1, 'rgb(255,255,255)']]
    const flat = { ambient: 1, diffuse: 0, specular: 0 }
    function loadVolume() { // a coarse copy of the cube, once per cube and block
      const key = `${cube}|${st.split}`
      if (volKey === key) return
      volKey = key; vol = null
      fetch(`api/seis/volume/${cube}?split=${st.split}`).then(async (r) => {
        if (!r.ok || volKey !== key) return
        const [ni, nx, nt] = r.headers.get('X-Shape').split(',').map(Number), [si, sx, sz] = r.headers.get('X-Steps').split(',').map(Number)
        vol = { ni, nx, nt, si, sx, sz, data: new Int8Array(await r.arrayBuffer()) }
        sig3 = ''; scene3d()
      }).catch(() => {})
    }
    function scene3d() {
      const box = q('xsplit'), div = q('x3')
      box.classList.toggle('closed', !three)
      q('x3t').textContent = three ? 'Hide' : '3D'
      if (!three || !img || !window.Plotly) return
      loadVolume()
      const NI = geo.n.inline, NX = geo.n.crossline, NS = geo.n.time
      const mx = geo.ax.inline.x.m, my = geo.ax.crossline.x.m, Lx = (NX - 1) * mx, Ly = (NI - 1) * my
      const z0 = zOf(0), z1 = zOf(NS - 1), X0 = geo.X(st.crossline), Y0 = geo.Y(st.inline), Z0 = zOf(st.time)
      const muted = css('--muted'), line = css('--line-2')
      const plane = { inline: (u, v) => [u * Lx, Y0, z0 + v * (z1 - z0)], crossline: (u, v) => [X0, u * Ly, z0 + v * (z1 - z0)], time: (u, v) => [u * Lx, v * Ly, Z0] }
      const sheet = (f, nu = 14, nv = 14) => { const x = [], y = [], zz = []; for (let j = 0; j < nv; j++) { const a = [], b = [], c = []; for (let i = 0; i < nu; i++) { const p = f(i / (nu - 1), j / (nv - 1)); a.push(p[0]); b.push(p[1]); c.push(p[2]) } x.push(a); y.push(b); zz.push(c) } return { x, y, z: zz } }
      const frame = (f) => { const p = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]].map(([u, v]) => f(u, v)); return { x: p.map((a) => a[0]), y: p.map((a) => a[1]), z: p.map((a) => a[2]) } }
      const grey = st.cmap === 'grey' || (img.labels && st.labels)
      const clampv = (v) => Math.max(-1, Math.min(1, v))

      // what moves with the slider: the three planes, their outlines and the marked trace
      const dynamic = () => {
        const surf = [], lines = []
        ;['inline', 'crossline', 'time'].forEach((a, n) => {
          if (a !== st.axis) { // the other two planes: a faint sheet and an outline
            const g = sheet(plane[a])
            surf.push({ ...g, surfacecolor: g.x.map((r) => r.map(() => 0)) })
          } else { // the plane you are looking at, with the slice painted on it
            const gh = Math.min(img.h, 64), gw = Math.min(img.w, 120), x = [], y = [], zz = [], sc = []
            for (let jj = 0; jj < gh; jj++) {
              const rx = [], ry = [], rz = [], rs = [], r = Math.round((jj * (img.h - 1)) / Math.max(1, gh - 1))
              for (let i = 0; i < gw; i++) {
                const c = Math.round((i * (img.w - 1)) / Math.max(1, gw - 1)), [il, xl, k] = geo.at[a](r * img.step, c * img.step, st)
                rx.push(geo.X(xl)); ry.push(geo.Y(il)); rz.push(zOf(k))
                rs.push(img.coh ? img.coh[r * img.w + c] / 255 : clampv((img.data[r * img.w + c] / 127) * st.gain))
              }
              x.push(rx); y.push(ry); zz.push(rz); sc.push(rs)
            }
            surf.push({ x, y, z: zz, surfacecolor: sc })
          }
          lines.push(frame(plane[a]))
        })
        const [il, xl] = st.pick || []
        lines.push(st.pick ? { x: [geo.X(xl), geo.X(xl)], y: [geo.Y(il), geo.Y(il)], z: [z0, z1] } : { x: [null], y: [null], z: [null] })
        return { surf, lines }
      }

      // what stays put while you move: the box, and the faint stack of the other slices
      const stack = () => {
        if (!st3.all || !vol) return []
        const { ni, nx, nt, si, sx, sz, data } = vol, out = []
        const ilO = (i) => i * si, xlO = (jj) => jj * sx, kO = (k) => k * sz + (sz - 1) / 2
        const val = (i, jj, k) => clampv((data[(i * nx + jj) * nt + k] / 127) * st.gain)
        const pick = (n) => [...new Set(Array.from({ length: Math.min(n, st3.n) }, (_, i) => Math.round((i * (n - 1)) / Math.max(1, Math.min(n, st3.n) - 1))))]
        for (const a of st3.dirs === 'all' ? ['inline', 'crossline', 'time'] : [st.axis]) {
          for (const id of pick({ inline: ni, crossline: nx, time: nt }[a])) {
            const X = [], Y = [], Z = [], C = []
            const [rows, cols] = a === 'time' ? [ni, nx] : [nt, a === 'inline' ? nx : ni]
            for (let r = 0; r < rows; r++) {
              const rx = [], ry = [], rz = [], rc = []
              for (let c = 0; c < cols; c++) {
                const [i, jj, k] = a === 'inline' ? [id, c, r] : a === 'crossline' ? [c, id, r] : [r, c, id]
                rx.push(geo.X(xlO(jj))); ry.push(geo.Y(ilO(i))); rz.push(zOf(kO(k))); rc.push(val(i, jj, k))
              }
              X.push(rx); Y.push(ry); Z.push(rz); C.push(rc)
            }
            out.push({ type: 'surface', x: X, y: Y, z: Z, surfacecolor: C, cmin: -1, cmax: 1, colorscale: grey ? GREY : RWB, showscale: false, opacity: st3.op, hoverinfo: 'skip', lighting: flat })
          }
        }
        return out
      }

      const dyn = dynamic()
      const sig = JSON.stringify([cube, st.split, st.axis, st.hu, st.vu, st.v, st.ve, st.cmap, !!(img.labels && st.labels), !!img.coh, Math.round(st.gain * 10), st3, !!vol])
      let nStatic
      if (sig !== sig3 || !div.data) {
        sig3 = sig
        const cs = [[0, 0, z0], [Lx, 0, z0], [Lx, Ly, z0], [0, Ly, z0], [0, 0, z1], [Lx, 0, z1], [Lx, Ly, z1], [0, Ly, z1]]
        const edges = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]]
        const ex = [], ey = [], ez = []
        for (const [a, b] of edges) { ex.push(cs[a][0], cs[b][0], null); ey.push(cs[a][1], cs[b][1], null); ez.push(cs[a][2], cs[b][2], null) }
        const traces = [
          { type: 'mesh3d', x: cs.map((c) => c[0]), y: cs.map((c) => c[1]), z: cs.map((c) => c[2]), i: [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3], j: [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 0, 4], k: [2, 3, 6, 7, 5, 4, 6, 5, 7, 6, 4, 7],
            opacity: 0.05, color: css('--ink-2'), hoverinfo: 'skip', flatshading: true },
          { type: 'scatter3d', mode: 'lines', x: ex, y: ey, z: ez, line: { color: muted, width: 2 }, hoverinfo: 'skip' },
          ...stack(),
        ]
        nStatic = traces.length
        ;['inline', 'crossline', 'time'].forEach((a, n) => {
          const active = a === st.axis, d = dyn.surf[n]
          traces.push(active
            ? { type: 'surface', ...d, cmin: img.coh ? 0 : -1, cmax: 1, showscale: false, opacity: 0.95, hoverinfo: 'none', lighting: flat, colorscale: img.coh ? [[0, '#000'], [1, '#fff']] : grey ? GREY : RWB }
            : { type: 'surface', ...d, showscale: false, opacity: 0.12, hoverinfo: 'none', lighting: flat, colorscale: [[0, PLANE[n]], [1, PLANE[n]]] })
        })
        dyn.lines.forEach((d, n) => traces.push({ type: 'scatter3d', mode: 'lines', ...d, line: { color: n < 3 ? PLANE[n] : css('--ink'), width: n < 3 ? (['inline', 'crossline', 'time'][n] === st.axis ? 6 : 3) : 5 }, hoverinfo: 'skip' }))
        const ticks = (len, m, lineAt, dist) => { const tv = niceTicks(0, len, 5); return { tickvals: tv, ticktext: tv.map((v) => (dist ? num(v) : String(lineAt(Math.round(v / m))))) } }
        const zt = niceTicks(z0, z1, 5), ax = (t, o) => ({ title: { text: t, font: { size: 11, color: muted } }, tickfont: { size: 10, color: muted }, gridcolor: line, zerolinecolor: line, linecolor: line, showbackground: false, ...o })
        const zm = Math.abs(z(geo.t(NS - 1)) - z(geo.t(0))), big = 2 / Math.max(Lx, Ly, st.ve * zm) // the box is drawn at the same vertical exaggeration as the section
        Plotly.react(div, traces, {
          uirevision: 'x3', margin: { l: 0, r: 0, t: 0, b: 0 }, paper_bgcolor: 'rgba(0,0,0,0)', showlegend: false, font: { color: muted },
          scene: { aspectmode: 'manual', aspectratio: { x: Lx * big, y: Ly * big, z: st.ve * zm * big }, bgcolor: 'rgba(0,0,0,0)', camera: CAM.iso,
            xaxis: ax(st.hu === 'dist' ? 'distance (m)' : geo.ax.inline.x.name, { range: [0, Lx], ...ticks(Lx, mx, geo.ax.inline.x.line, st.hu === 'dist') }),
            yaxis: ax(st.hu === 'dist' ? 'distance (m)' : geo.ax.crossline.x.name, { range: [0, Ly], ...ticks(Ly, my, geo.ax.crossline.x.line, st.hu === 'dist') }),
            zaxis: ax(st.vu === 'depth' ? 'depth (m)' : 'time (ms)', { range: [z1, z0], tickvals: zt, ticktext: zt.map((v) => num(v)) }) },
        }, { displayModeBar: false, responsive: true })
      } else { // only the planes moved: update just those traces, not the stack
        nStatic = div.data.length - 7
        const at = (n) => Array.from({ length: n }, (_, i) => nStatic + i)
        Plotly.restyle(div, { x: dyn.surf.map((t) => t.x), y: dyn.surf.map((t) => t.y), z: dyn.surf.map((t) => t.z), surfacecolor: dyn.surf.map((t) => t.surfacecolor) }, at(3))
        Plotly.restyle(div, { x: dyn.lines.map((t) => t.x), y: dyn.lines.map((t) => t.y), z: dyn.lines.map((t) => t.z) }, at(4).map((i) => i + 3))
      }
      if (!hooked) {
        hooked = true
        div.on('plotly_click', (ev) => { // a click on any plane: the three planes meet at that point
          const p = ev.points?.[0]
          if (!p) return
          const clamp = (v, n) => Math.max(0, Math.min(n - 1, v)), dt = geo.t(1) - geo.t(0)
          const il = clamp(geo.iY(p.y), geo.n.inline), xl = clamp(geo.iX(p.x), geo.n.crossline)
          const k = clamp(Math.round(((st.vu === 'depth' ? (2000 * p.z) / st.v : p.z) - geo.t(0)) / dt), geo.n.time)
          Object.assign(st, { inline: il, crossline: xl, time: k, pick: [il, xl, k] })
          pump()
        })
      }
      const dot = (c, t) => `<div><i style="background:${c}"></i>${esc(t)}</div>`
      const km = (m) => `${num(m / 1000, 1)} km`, zm2 = Math.abs(z(geo.t(NS - 1)) - z(geo.t(0)))
      q('x3info').innerHTML = `${dot(PLANE[0], `${geo.label.inline(st.inline)} · ${dist('inline', st.inline)}`)}${dot(PLANE[1], `${geo.label.crossline(st.crossline)} · ${dist('crossline', st.crossline)}`)}${dot(PLANE[2], `${num(geo.t(st.time))} ms · ≈ ${num(z(geo.t(st.time)))} m deep`)}
        <div class="muted" style="margin-top:.3rem">Box: ${km(Lx)} wide (crossline direction) × ${km(Ly)} (inline direction) × ${num(geo.t(NS - 1) - geo.t(0))} ms ≈ ${km(zm2)} deep at ${num(st.v)} m/s, drawn with the same vertical exaggeration as the section (${num(st.ve, 1)}×).
        ${st.pick ? `Marked trace: inline ${geo.il(st.pick[0])}, crossline ${geo.xl(st.pick[1])}.` : ''}</div>
        <div class="muted" style="margin-top:.3rem">${st3.all ? (vol ? `The faint sheets are ${st3.dirs === 'all' ? 'slices in all three directions' : `${st.axis} slices spread through the cube`}, drawn from a coarse copy of the data: they show where things are, not fine detail. The strong plane is the one the slider moves.` : 'Loading the coarse copy of the cube for the faint sheets…') : 'The plane with the picture is the one the slider moves.'}
        Drag to turn it, scroll to zoom, click a plane to put the slices there.</div>`
    }
    q('x3t').onclick = () => {
      three = !three
      try { localStorage.setItem('atlas-3d', three ? 'open' : 'closed') } catch { /* fine */ }
      scene3d()
      if (three) setTimeout(() => { Plotly.Plots.resize(q('x3')); fit(); decorate() }, 60); else setTimeout(() => { fit(); decorate() }, 60)
    }
    q('x3a').onchange = () => { st3.all = q('x3a').checked; scene3d() }
    q('x3d').onchange = () => { st3.dirs = q('x3d').value; scene3d() }
    q('x3n').oninput = () => { st3.n = +q('x3n').value; q('x3nv').textContent = st3.n; scene3d() }
    q('x3o').oninput = () => { st3.op = +q('x3o').value; scene3d() }
    el.querySelectorAll('[data-cam]').forEach((b) => { b.onclick = () => Plotly.relayout(q('x3'), { 'scene.camera': CAM[b.dataset.cam] }) })
    const decorate = () => { axes(); facts(); bar(); scene3d() }

    function paint() {
      if (!img) return
      const { h, w, data, labels, coh } = img
      cv.width = w; cv.height = h
      const g = cv.getContext('2d'), im = g.createImageData(w, h), fc = FAC().map(rgb)
      for (let i = 0; i < h * w; i++) {
        let r, gg, b
        if (coh) { const v = coh[i]; r = gg = b = v } else {
          const v = Math.max(-1, Math.min(1, (data[i] / 127) * st.gain))
          if (st.cmap === 'grey' || (labels && st.labels)) { r = gg = b = 128 + v * 127 } else { r = v > 0 ? 255 : 255 + v * 215; gg = 255 - Math.abs(v) * 215; b = v < 0 ? 255 : 255 - v * 215 }
        }
        if (labels && st.labels) { const c = fc[labels[i]] || [0, 0, 0], a = st.alpha; r = r * (1 - a) + c[0] * a; gg = gg * (1 - a) + c[1] * a; b = b * (1 - a) + c[2] * a }
        const o = i * 4; im.data[o] = r; im.data[o + 1] = gg; im.data[o + 2] = b; im.data[o + 3] = 255
      }
      g.putImageData(im, 0, 0)
      if (st.pick) { // the picked trace, where it crosses this view
        const [pr, pc] = geo.to[st.axis](...st.pick).map((v) => v / (img.step || 1))
        g.strokeStyle = '#111'; g.lineWidth = Math.max(1, w / 500); g.setLineDash([w / 120, w / 160]); g.beginPath()
        if (st.axis === 'time') { g.moveTo(pc, 0); g.lineTo(pc, h); g.moveTo(0, pr); g.lineTo(w, pr) } else { g.moveTo(pc, 0); g.lineTo(pc, h) }
        g.stroke()
      }
      decorate()
    }
    // the latest request wins, but a load in flight always finishes and paints, so dragging updates as it goes
    async function pump(preview = false) {
      want = preview
      if (running) return
      running = true
      while (want !== null) { const p = want; want = null; await load(p) }
      running = false
    }
    async function load(preview = false) {
      const step = preview && cube === 'adele' ? 3 : 1 // a light preview of the big Adele slices while the slider moves
      const n = geo.n[st.axis], i = Math.max(0, Math.min(n - 1, st[st.axis]))
      st[st.axis] = i
      q('xi').max = n - 1; q('xi').value = i; sliderLabels()
      const [e0, e1, e2, e3] = geo.edges[st.axis]
      q('xe0').textContent = `← ${e0}`; q('xe1').textContent = `${e1} →`; q('xev').textContent = `Top: ${e2} · bottom: ${e3}${st.axis === 'time' ? '' : ' (time increases downward)'}`
      q('xbusy').textContent = 'loading…'
      const base = `api/seis/${st.layer === 'coh' ? 'coherence' : 'slice'}/${cube}?axis=${st.axis}&i=${i}&split=${st.split}&step=${step}`
      try {
        const want = [getBin(base)]
        if (st.layer === 'coh' && cube === 'f3' && st.labels) want.push(getBin(`api/seis/slice/${cube}?axis=${st.axis}&i=${i}&split=${st.split}`))
        const [d, lab] = await Promise.all(want)
        if (st.layer === 'coh') img = { step, h: d.h, w: d.w, coh: new Uint8Array(d.buf), labels: lab ? new Uint8Array(lab.buf, lab.h / 2 * lab.w) : null, top: d.top }
        else {
          const h = d.labels ? d.h / 2 : d.h
          img = { step, h, w: d.w, data: new Int8Array(d.buf, 0, h * d.w), labels: d.labels ? new Uint8Array(d.buf, h * d.w) : null }
        }
        q('xbusy').textContent = ''
        fit(); paint()
      } catch (e) { q('xbusy').textContent = e.message }
    }
    const cell = (ev) => {
      const r = cv.getBoundingClientRect()
      return [Math.floor(((ev.clientY - r.top) / r.height) * img.h), Math.floor(((ev.clientX - r.left) / r.width) * img.w)]
    }
    cv.onmousemove = (ev) => {
      if (!img) return
      const [r, c] = cell(ev), i = r * img.w + c
      if (r < 0 || c < 0 || r >= img.h || c >= img.w) return
      const [il, xl, k] = geo.at[st.axis](r * img.step, c * img.step, st)
      const val = img.coh ? `discontinuity ${(img.coh[i] / 255 * img.top).toFixed(2)}` : `amplitude ${num(geo.amp(img.data[i]), cube === 'f3' ? 2 : 0)}${Math.abs(img.data[i]) === 127 ? ' (clipped)' : ''}`
      const xy = geo.xy?.(il, xl)
      q('xr').textContent = `inline ${geo.il(il)} · crossline ${geo.xl(xl)}${xy ? ` · E ${num(xy[0])} N ${num(xy[1])}` : ''} · ${num(geo.t(k))} ms ≈ ${num(z(geo.t(k)))} m · ${val}${img.labels ? ` · ${meta.facies[img.labels[i]]}` : ''}`
    }
    cv.onclick = (ev) => {
      if (!img) return
      const [r, c] = cell(ev)
      const [il, xl, k] = geo.at[st.axis](r * img.step, c * img.step, st)
      st.pick = [il, xl, k]; Object.assign(st, { inline: il, crossline: xl, time: k })
      paint(); onTrace?.({ il, xl, k, split: st.split, geo })
    }
    q('xi').oninput = () => { st[st.axis] = +q('xi').value; sliderLabels(); pump(true) }
    q('xi').onchange = () => pump(false) // released: the full-resolution slice
    q('xm').onclick = () => { st[st.axis] -= 1; pump() }
    q('xp').onclick = () => { st[st.axis] += 1; pump() }
    q('xa').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; st.axis = b.dataset.a; q('xa').querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b)); pump() }
    q('xl').onchange = () => { st.layer = q('xl').value; pump() }
    q('xc').onchange = () => { st.cmap = q('xc').value; paint() }
    q('xg').oninput = () => { st.gain = +q('xg').value; paint() }
    const units = () => { sliderLabels(); decorate() }
    q('xhu').onchange = () => { st.hu = q('xhu').value; units() }
    q('xvu').onchange = () => { st.vu = q('xvu').value; q('xvw').hidden = st.vu !== 'depth'; units() }
    q('xve').oninput = () => { st.ve = +q('xve').value; q('xvev').textContent = `${st.ve}×`; fit(); decorate() }
    q('xv').oninput = () => { st.v = Math.max(500, +q('xv').value || geo.vel); fit(); units() }
    if (cube === 'f3') {
      q('xs').onchange = () => { st.split = q('xs').value; geo = geometry(cube, meta, st.split); Object.assign(st, geo.start, { pick: null }); pump() }
      q('xf').onchange = () => { st.labels = q('xf').checked; st.layer === 'coh' ? pump() : paint() }
      q('xo').oninput = () => { st.alpha = +q('xo').value; paint() }
    }
    addEventListener('resize', () => { fit(); decorate() })
    pump()
    return { go: (axis, i, layer) => { st.axis = axis; st[axis] = i; if (layer) { st.layer = layer; q('xl').value = layer } q('xa').querySelectorAll('button').forEach((x) => x.classList.toggle('on', x.dataset.a === axis)); el.scrollIntoView({ behavior: 'smooth', block: 'start' }); pump() } }
  }

  // one trace: wiggle with the labels behind it, spectrum against the cube's average, and (Adele) its header
  async function traceView(el, cube, meta, { il, xl, split }) {
    el.innerHTML = '<span class="thinking"><span class="spin"></span>Reading the trace</span>'
    const t = await get(`api/seis/trace/${cube}?il=${il}&xl=${xl}&split=${split}`)
    const avg = cube === 'adele' ? meta.spectrum : meta.splits[split].spectrum
    el.innerHTML = `<div class="row" style="gap:1rem;margin-bottom:.5rem"><b>Inline ${t.il} · crossline ${t.xl}</b>${t.rms !== undefined ? `<span class="muted small">RMS ${num(t.rms)} · peak ${num(t.peak)}${t.peak > 10 * meta.amplitude.percentiles['99.9'] ? ' <span class="tag red">spike</span>' : ''}${t.peak === 0 ? ' <span class="tag">dead trace</span>' : ''}</span>` : ''}</div>
      <div class="grid g2"><div>${chart('tw', 460)}<p class="how"><b>How to read it:</b> the ${T('wiggle', 'wiggle')}: amplitude across, time down. Each swing is a boundary between layers; the filled side is positive.${t.labels ? ' The coloured bands behind it are the label (rock unit) at each sample.' : ''}</p></div>
      <div>${chart('tsp', 220)}<p class="how"><b>How to read it:</b> the ${T('spectrum')} of this trace against the cube's average. Energy far below the ${T('nyquist', 'Nyquist')} limit (125 Hz) means coarse vertical detail.</p>
      ${t.header ? `<div class="table-wrap" style="max-height:200px;margin-top:.6rem">${table([['Trace header field', (r) => esc(r.name)], ['Byte', (r) => r.byte, 'num'], ['Value', (r) => num(r.value), 'num mono'], ['Holds', (r) => `<span class="muted">${esc(r.what)}</span>`]], t.header, 200)}</div>` : ''}</div></div>`
    const lo = Math.min(...t.a), hi = Math.max(...t.a), pad = (hi - lo) * 0.05 || 1
    const shapes = []
    if (t.labels) {
      let s0 = 0
      for (let k = 1; k <= t.labels.length; k++) {
        if (k === t.labels.length || t.labels[k] !== t.labels[s0]) { shapes.push({ type: 'rect', xref: 'paper', x0: 0, x1: 1, y0: t.t[s0], y1: t.t[k - 1] + 4, fillcolor: FAC()[t.labels[s0]], opacity: 0.28, line: { width: 0 }, layer: 'below' }); s0 = k }
      }
    }
    plot('tw', [{ x: t.a.map((v) => Math.max(0, v)), y: t.t, type: 'scatter', mode: 'lines', line: { width: 0 }, fill: 'tozerox', fillcolor: css('--ink-2'), hoverinfo: 'skip', showlegend: false },
      { x: t.a, y: t.t, type: 'scatter', mode: 'lines', line: { color: css('--ink'), width: 1 }, showlegend: false, hovertemplate: '%{y} ms: %{x:.4~g}<extra></extra>' }],
    { yaxis: { autorange: 'reversed', title: { text: 'two-way time (ms)' } }, xaxis: { range: [lo - pad, hi + pad], title: { text: 'amplitude' } }, shapes, margin: { l: 64, r: 10, t: 10, b: 44 } })
    plot('tsp', [{ x: avg.hz, y: avg.amp, type: 'scatter', mode: 'lines', name: 'cube average', line: { color: S(0), width: 2, dash: 'dot' } },
      { x: t.hz, y: t.spec, type: 'scatter', mode: 'lines', name: 'this trace', line: { color: S(1), width: 2 } }],
    { xaxis: { title: { text: 'frequency (Hz)' }, range: [0, 80] }, yaxis: { title: { text: 'relative energy' } }, legend: { orientation: 'h', y: 1.18 } })
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }

  const spectrumChart = (id, sp) => plot(id, [{ x: sp.hz, y: sp.amp, type: 'scatter', mode: 'lines', line: { color: S(1), width: 2 }, hovertemplate: '%{x:.1f} Hz: %{y:.2f}<extra></extra>', showlegend: false }],
    { xaxis: { title: { text: 'frequency (Hz)' }, range: [0, 80] }, yaxis: { title: { text: 'relative energy' } },
      shapes: [{ type: 'rect', x0: sp.half_power_hz[0], x1: sp.half_power_hz[1], yref: 'paper', y0: 0, y1: 1, fillcolor: S(1), opacity: 0.1, line: { width: 0 } }],
      annotations: [{ x: (sp.half_power_hz[0] + sp.half_power_hz[1]) / 2, yref: 'paper', y: 1, text: 'half power', showarrow: false, font: { color: css('--muted'), size: 11 } }] })
  const rmsTimeChart = (id, ys, t0, dt, ytitle = 'two-way time (ms)') => plot(id, [{ x: ys, y: ys.map((_, k) => t0 + dt * k), type: 'scatter', mode: 'lines', line: { color: S(1), width: 2 }, hovertemplate: '%{y} ms: %{x:.3~g}<extra></extra>', showlegend: false }],
    { yaxis: { autorange: 'reversed', title: { text: ytitle } }, xaxis: { title: { text: 'RMS amplitude' } } })

  // ---------- seismic overview ----------
  async function seismicOverview() {
    const [a, f] = await Promise.all([seisProfile('adele').catch(() => null), seisProfile('f3').catch(() => null)])
    const ds = catalog.datasets
    const card = (d) => `<a class="card" href="#${d.id}"><h3><span>${esc(d.name)}</span>${d.present ? `<span class="tag ${d.origin === 'mail' ? 'green' : ''}">${d.origin === 'mail' ? 'official' : 'stand-in'}</span>` : '<span class="tag">not yet</span>'}</h3>
      <p>${esc(d.what)}</p><div class="row"><span>${gb(d.bytes)}</span><span>${esc(d.licence)}</span></div></a>`
    const tr = a?.spectrum, f3t = f?.splits.train
    const rowsCmp = [
      ['Where', 'Offshore NW Australia, 13.7° S 123.5° E', 'Dutch North Sea, block F3 (geology close to the southern NCS)'],
      ['Official?', 'Yes, in the organisers\' mail', 'No, found before the event'],
      ['Labels', '<b>None</b> (a blind cube for fault detection)', `<b>Six rock units on every sample</b> (${T('facies')})`],
      ['File', `${T('segy', 'SEG-Y')}, 4-byte ${T('ieee', 'IEEE float')}, full headers`, 'numpy arrays, no headers or coordinates'],
      ['Grid', `301 ${T('inline', 'inlines')} (every second) × 2,731 ${T('crossline', 'crosslines')}`, 'train 401 × 701, test 1 200 × 701, test 2 601 × 200'],
      [T('bin', 'Bin size'), '12.5 m east-west, 37.5 m north-south', '25 m × 25 m'],
      ['Time window', '1,500 to 5,500 ms, 1,001 samples at 4 ms', '255 samples at 4 ms (about 1 s)'],
      ['Area', '34 × 11 km, 384 km²', 'train 17.5 × 10 km; test blocks of 88 and 75 km² beside it'],
      ['Frequency', tr ? `peak ${tr.peak_hz} Hz, half power ${tr.half_power_hz.join(' to ')} Hz (low: deep, old data)` : '', f3t ? `half power ${f3t.spectrum.half_power_hz.join(' to ')} Hz (broad)` : ''],
      ['Amplitudes', 'raw, uncalibrated; 98 % within ±800', 'scaled to −1 … +1'],
      ['Known problems', `1 ${T('spike')} trace, 8 ${T('dead', 'dead')} crosslines on the west edge, alternate inlines missing`, `strong ${T('imbalance', 'class imbalance')}; test 1 has 5× the Scruff of train`],
      ['Good for', 'fault detection without labels, attributes, SEG-Y QC, an interpretation assistant', 'supervised facies segmentation with a real score, look-alike search'],
    ]
    view.innerHTML = `<section class="hero"><div class="eyebrow">FORCE VibeCode Hackathon · seismic</div>
      <h1>Seismic Atlas <em>: the two cubes we have, what is in them, and how to look inside.</em></h1>
      <p class="lede">The team picked a seismic task, so this page shows the seismic only; the other datasets stay on disk. Open a cube to slice
        it in any direction, switch to ${T('coherence')} to see faults, and click any point for its ${T('trace')}, ${T('spectrum')} and header.
        Dotted words explain themselves on hover.</p></section>
      ${kpis([[2, 'cubes'], [a ? num(a.grid.traces) : '–', 'Adele traces'], [f ? num(f.splits.train.counts.reduce((x, y) => x + y, 0) + f.splits.test1.counts.reduce((x, y) => x + y, 0) + f.splits.test2.counts.reduce((x, y) => x + y, 0)) : '–', 'F3 labelled samples'], ['4 ms', 'sample interval (both)'], ['0', 'NCS wells inside either cube', 'warn']])}
      <div class="callout" style="margin:1rem 0">New to seismic? <a href="#learn"><b>Start here</b></a> explains every word with the cube's real numbers. <a href="#resolution"><b>Resolution &amp; granularity</b></a> measures how far apart the data is and what you can see in it.</div>
      <div class="cards">${ds.map(card).join('')}</div>
      <div class="section-title">Seismic in one minute</div>
      ${plain(`A ship fires sound into the sea floor. Every boundary between rock layers with different ${T('impedance', 'acoustic impedance')} echoes some back.
        The echo at one spot is a ${T('trace')}: amplitude against ${T('twt', 'two-way time')}. A 3D survey records a trace in every ${T('bin')} of a grid,
        so the data is a cube: ${T('inline')} × ${T('crossline')} × time ${T('sample')}.`,
        `Seismic is the only picture of the rock between wells. Interpreters pick ${T('horizon', 'horizons')} and ${T('fault', 'faults')} by hand, which
        takes weeks per survey; faults decide where oil is trapped and where a well is risky.`,
        `Red and blue are positive and negative amplitude. Flat continuous stripes are layers; places where they break or step are faults;
        blank or chaotic zones are salt, gas or poor data. Time is not depth: deeper is further down, but the scale is milliseconds.`)}
      <div class="section-title">The two cubes side by side</div>
      ${panel('Adele against F3', `<div class="table-wrap" style="max-height:none">${table([['', (r) => `<b>${r[0]}</b>`], ['Adele 3D (official)', (r) => r[1]], ['F3 Netherlands (stand-in)', (r) => r[2]]], rowsCmp, 2000)}</div>`,
        'neither cube is on the Norwegian shelf, and no well in our data sits inside either. Well ties need the FORCE 2020 sonic and density logs plus a synthetic seismogram; see docs/seismic-guide.md.')}
      ${terms(SEIS_TERMS)}`
  }

  // ---------- Adele ----------
  VIEWS.adele = async (d) => {
    const m = await seisProfile('adele')
    const g = m.grid, pc = m.amplitude.percentiles
    view.innerHTML = `${head(d)}${plain(
      `A 3D ${T('seismic')} survey from offshore NW Australia, ${T('pstm', 'PSTM')} ${T('stack', 'full-offset stack')}, exported from Petrel in 2020. It was the blind cube of FORCE's 2020 fault competition: <b>no labels, horizons or wells</b>.`,
      `Fault picking is the slowest part of interpretation. A good automatic fault pick on a real survey is worth a lot: this cube lets you test one on real, imperfect data.`,
      `Fault detection (start from the ${T('coherence')} view below as a baseline), a SEG-Y QC tool (the spike and dead traces are real test cases), an assistant that explains a section in words.`)}
      ${kpis([[num(g.traces), T('trace', 'traces')], [`${g.n_inlines} × ${num(g.n_crosslines)}`, `${T('inline', 'inlines')} × crosslines`], [`${num(g.t0_ms)}–${num(g.t1_ms)} ms`, `${T('twt', 'TWT')} window`], ['12.5 × 37.5 m', T('bin', 'bin size')], [`${m.spectrum.peak_hz} Hz`, T('dominant', 'dominant frequency')], [num(m.dead.traces), T('dead', 'dead traces'), 'warn'], [m.spikes.length, T('spike', 'spike traces'), m.spikes.length ? 'warn' : '']])}
      <div class="section-title">Explore the cube</div>
      ${panel('Slice through Adele', '<div id="exp"></div>', `pick a direction, then move the slider. Inline and crossline sections are vertical: position across, time down. A ${T('timeslice', 'time slice')} is a map at one time, north up. Switch <b>Show</b> to ${T('coherence')}: bright lines are breaks in the layering, mostly ${T('fault', 'faults')}. Raise the ${T('clip', 'gain')} to see weak deep reflections.`,
        `<span class="row" style="gap:.4rem">${m.spikes.map((s) => `<button class="btn sm" data-go="inline:${(s.il - 4175) / 2}">Show the spike (inline ${s.il})</button>`).join('')}<button class="btn sm" data-go="time:${Math.round((3000 - 1500) / 4)}:coh">Faults at 3,000 ms</button></span>`)}
      <div id="trace" style="margin-top:1rem"></div>
      <div class="section-title">Quality control</div>
      <div class="grid g2">
        ${panel('Loudness map (RMS per trace)', chart('c-rms', 300), [`for each of the ${num(g.traces)} traces: take its ${g.samples} samples, square them, average, take the root (${T('rms', 'RMS amplitude')}). That is one number per trace, drawn at the trace's place on the map (north up). It says how strong the recorded signal is at each spot. It is a picture of the data, not of the geology.`, `even colour means even data. Stripes or blocks usually come from how the data was collected or processed; the blank strip on the west edge is the ${T('dead', 'dead')} crosslines, which are all zeros. Click a spot to open that inline.`])}
        ${panel('Loudness with time', chart('c-rmst', 300), ['the same RMS number, but for each time instead of each trace: the average strength of all traces at every sample, from the top of the window (1,500 ms) down.', 'weak around 2.0 to 2.3 s, strongest at 3.7 to 4.2 s. That is partly geology (strong boundaries) and partly processing, which did not even out the gain, so a model should normalise per window.'])}
        ${panel('Frequency content', chart('c-sp', 300), [`how much of the signal lives at each frequency, averaged over thousands of traces. Frequency is how fast the wiggles go: low frequencies carry the big shapes, high ones the thin layers.`, `the peak is ${m.spectrum.peak_hz} Hz and the shaded band holds half the energy (${m.spectrum.half_power_hz.join(' to ')} Hz). At 3,000 to 4,000 m/s that means a ${T('tuning', 'tuning thickness')} near 70 to 90 m: a layer or fault ${T('throw')} thinner than that blurs. See the <a href="#resolution">Resolution page</a>.`])}
        ${panel('Amplitude distribution', chart('c-amp', 300), [`a histogram: how many samples have each amplitude value (x) as a share of all ${num(g.traces * g.samples / 1e6)} million samples (y).`, `it is symmetric and peaked at zero: most samples are weak, a few are strong. The file header claims −350,841 to 266,022, but only one spike trace reaches that, so clip at about ±${num(pc['99.9'], 0)} (the 99.9th percentile) when you plot or train.`])}
      </div>
      ${panel('Percentiles', table([['Percentile', (r) => r[0]], ['Amplitude', (r) => num(r[1], 1), 'num']], Object.entries(pc).sort((x, y) => x[0] - y[0])), 'use these for clipping and normalising rather than the header\'s min and max.')}
      <div class="section-title">Where it is</div>
      ${panel('Location', '<div id="smap" style="height:320px;border-radius:var(--radius-sm)"></div>', `${esc(g.crs)}. ${esc(g.orientation)}. The grid is square to north, so the text header's latitude and longitude ranges bound it.`)}
      <div class="section-title">Inside the SEG-Y file</div>
      ${panel(T('header_text', 'Textual header'), `<pre class="sample" style="max-height:420px">${esc(m.text_header.join('\n'))}</pre>`, `the first 3,200 bytes, in ${T('ebcdic')}. Lines C18 to C31 say which bytes hold what; this file follows the standard positions. Time shows negative (−5,502 to −1,498) because Petrel counts down; the trace headers use positive times.`)}
      <div class="grid g2">
        ${panel(T('header_bin', 'Binary header'), table([['Field', (r) => esc(r.name)], ['Byte', (r) => r.byte, 'num'], ['Value', (r) => num(r.value), 'num mono'], ['Meaning', (r) => `<span class="muted">${esc(r.what)}</span>`]], m.binary_header, 460), 'one set of numbers for the whole file. The ones that matter: 4,000 µs sample interval, 1,001 samples, format 5 (IEEE float).')}
        ${panel(T('header_trace', 'Trace header (first trace)'), table([['Field', (r) => esc(r.name)], ['Byte', (r) => r.byte, 'num'], ['Value', (r) => num(r.value), 'num mono'], ['Meaning', (r) => `<span class="muted">${esc(r.what)}</span>`]], m.trace_header_sample, 460), `the 240 bytes before each trace. Inline sits at byte 189 and crossline at 193 (also copied elsewhere). X and Y are in centimetres: the ${T('scalar', 'coordinate scalar')} −100 says divide by 100. Click any trace above to see its own header.`)}
      </div>
      ${panel('Read it in Python', `<pre class="sample">import segyio, numpy as np
with segyio.open("data/official/adele/Adele_seismic_survey_NW australia_bind cube_fault_detection.segy", iline=189, xline=193) as f:
    cube = segyio.tools.cube(f)          # (301 inlines, 2731 crosslines, 1001 samples), float32, 3.3 GB in memory
cube = np.clip(cube, -1500, 1500)        # the spike
cube = cube[:, :-8]                      # the dead west edge
# or the int8 copy the Atlas reads (127 = 2,000): np.load("data/atlas/seis/adele_ilxt.npy", mmap_mode="r")</pre>`)}
      ${terms(['segy', 'header_text', 'header_bin', 'header_trace', 'scalar', 'ieee', 'ebcdic', 'utm', 'pstm', 'stack', 'migration', 'coherence', 'attribute', 'tuning', 'throw', 'polarity', 'wavelet', 'dead', 'spike'])}`
    const ex = explorer($('exp'), 'adele', m, (p) => traceView($('trace'), 'adele', m, p))
    view.querySelectorAll('[data-go]').forEach((b) => { b.onclick = () => { const [ax, i, layer] = b.dataset.go.split(':'); ex.go(ax, +i, layer || 'amp') } })
    const R = m.rms_map, xs = R[0].map((_, j) => 5670 + j * m.rms_map_xl_step), ys = R.map((_, i) => 4175 + 2 * i)
    plot('c-rms', [{ type: 'heatmap', z: R, x: xs, y: ys, colorscale: [[0, css('--bg')], [1, S(1)]], zmin: 0, zmax: 450, colorbar: { thickness: 10, tickfont: { color: css('--muted') } }, hovertemplate: 'inline %{y} · crossline %{x}<br>RMS %{z:.0f}<extra></extra>' }],
      { xaxis: { autorange: 'reversed', title: { text: 'crossline (west ← → east)' } }, yaxis: { title: { text: 'inline (south → north)' } } })
    $('c-rms').on('plotly_click', (e) => ex.go('inline', Math.round((e.points[0].y - 4175) / 2)))
    rmsTimeChart('c-rmst', m.rms_time, g.t0_ms, g.dt_ms)
    spectrumChart('c-sp', m.spectrum)
    plot('c-amp', [histo(m.amplitude.hist, S(1), true)], { xaxis: { title: { text: 'amplitude' } }, yaxis: { title: { text: '% of samples' } } })
    const ll = g.latlon, mp = map($('smap'), [], () => '', () => '', [(ll.south + ll.north) / 2, (ll.west + ll.east) / 2], 7)
    const box = L.rectangle([[ll.south, ll.west], [ll.north, ll.east]], { color: S(2), weight: 2, fillOpacity: 0.15 }).bindPopup('Adele 3D survey outline').addTo(mp)
    mp.fitBounds(box.getBounds().pad(1.5))
  }

  // ---------- F3 ----------
  VIEWS.f3 = async (d) => {
    const m = await seisProfile('f3')
    const sp = m.splits, names = Object.keys(sp), lk = m.lookalike
    const share = (s) => s.counts.reduce((x, y) => x + y, 0)
    view.innerHTML = `${head(d)}${plain(
      `A 3D ${T('seismic')} cube from block F3 in the Dutch North Sea, cut into a training block and two test blocks, with every ${T('sample')} labelled by rock unit (${T('facies')}). The benchmark of Alaudah et al. (2019).`,
      'It is the only seismic we have with answers, so a model can be scored, and its geology (North Sea groups over Zechstein salt) is close to the southern Norwegian shelf.',
      `Facies segmentation scored by ${T('iou', 'mean IoU')}, look-alike search (our Seismic Lookalike tool), a model that explains a section in words and is checked against the labels.`)}
      ${kpis([[`${num(share(sp.train) + share(sp.test1) + share(sp.test2))}`, 'labelled samples'], [6, `${T('facies')} classes`], ['25 m', T('bin', 'bin size')], ['255 × 4 ms', 'samples per trace'], [`${(sp.train.share[5] * 100).toFixed(1)} %`, 'Zechstein in train (rarest)', 'warn'], [lk ? `${Math.round(lk.learned * 100)} %` : '–', 'Lookalike: right facies in top 10']])}
      <div class="section-title">Explore the cube</div>
      ${panel('Slice through F3', '<div id="exp"></div>', `choose a block and a direction. The colours are the labels over the grey seismic; drag the small slider to fade them, untick to see the plain amplitude. ${T('coherence', 'Coherence')} shows breaks: the salt and the faults above it. Click anywhere for the trace with its labels.`)}
      <div id="trace" style="margin-top:1rem"></div>
      <div class="section-title">How the blocks are laid out</div>
      <div class="grid g2">
        ${panel('Train and test blocks', chart('c-lay', 320), `in the original F3 numbering. Test 1 lies beside the training block (same crosslines), test 2 beyond its far side (same inlines, new crosslines). A model is trained on one and judged on blocks it never saw: a fair ${T('split', 'split')}.`)}
        ${panel('Share of each rock unit per block', chart('c-share', 320), `${T('imbalance', 'Class imbalance')}: the Lower North Sea fills half of every block, Zechstein under 3 %. Scruff jumps from 3 % in train to 17 % in test 1: the test is harder than the training data suggests.`)}
      </div>
      <div class="grid g2">
        ${panel('Where each unit sits in time', `<div class="row small" style="gap:.4rem;margin-bottom:.4rem">${names.map((s, i) => `<button class="btn sm ${i ? '' : 'on'}" data-dp="${s}">${s.replace('test', 'test ')}</button>`).join('')}</div>${chart('c-depth', 380)}`, 'the share of each unit at each time sample, top down. It reads like a layer cake: young North Sea groups on top, Cretaceous and Jurassic below, salt at the base. Where colours overlap, the units dip or the salt pushes them up.')}
        ${panel('What lies directly on what', '<div id="contacts"></div>', `every place down a trace where one unit gives way to the next, counted. The order almost never breaks (${num(sp.train.upward)} upward steps in train): the labels follow the stratigraphy, a strong rule a model can use.`)}
      </div>
      <div class="grid g2">
        ${panel('How loud each unit is', chart('c-amp', 300), `RMS amplitude per unit (train). Chalk and Scruff are loud, the North Sea clays quiet: amplitude alone already separates some units, the ${T('texture')} the rest.`)}
        ${panel('Seismic Lookalike: right unit in the top 10', chart('c-lk', 300), 'precision of our look-alike search per unit, on held-out sections. Good on the thick upper units, poor on the thin deep ones: exactly the classes a better model must win on.')}
      </div>
      <div class="grid g2">
        ${panel('Frequency content (train)', chart('c-sp', 300), `average ${T('spectrum')}. Broader than Adele's: half the energy spans ${sp.train.spectrum.half_power_hz.join(' to ')} Hz, so finer layering shows.`)}
        ${panel('Loudness with time (train)', chart('c-rmst', 300), 'average amplitude at each sample. Quiet at the very top (the first sample is zero on every trace), loudest in the deep Cretaceous to Zechstein section.')}
      </div>
      ${panel('Read it in Python', `<pre class="sample">import numpy as np
s = np.load("data/seismic/f3/data/train/train_seismic.npy", mmap_mode="r")   # (401 inlines, 701 crosslines, 255 samples), float64, -1..1
l = np.load("data/seismic/f3/data/train/train_labels.npy", mmap_mode="r")    # same shape, uint8 0..5
# 0 Upper North Sea, 1 Middle North Sea, 2 Lower North Sea, 3 Rijnland/Chalk, 4 Scruff, 5 Zechstein
section, labels = s[200].T, l[200].T                                         # one inline: rows are time, columns crosslines</pre>`)}
      ${terms(['facies', 'texture', 'clinoform', 'salt', 'imbalance', 'iou', 'split', 'coherence', 'horizon', 'fault', 'inline', 'crossline', 'timeslice', 'spectrum'])}`
    explorer($('exp'), 'f3', m, (p) => traceView($('trace'), 'f3', m, p))
    const lab = { train: 'train', test1: 'test 1', test2: 'test 2' }
    plot('c-lay', names.map((s, i) => ({ type: 'scatter', mode: 'lines', fill: 'toself', name: lab[s], line: { color: S(i + 1), width: 2 }, opacity: 0.85,
      x: [sp[s].crosslines[0], sp[s].crosslines[1], sp[s].crosslines[1], sp[s].crosslines[0], sp[s].crosslines[0]],
      y: [sp[s].inlines[0], sp[s].inlines[0], sp[s].inlines[1], sp[s].inlines[1], sp[s].inlines[0]], hovertemplate: `${lab[s]}: inlines ${sp[s].inlines.join('–')}, crosslines ${sp[s].crosslines.join('–')}<extra></extra>` })),
    { xaxis: { title: { text: 'crossline' } }, yaxis: { title: { text: 'inline' }, scaleanchor: 'x' } })
    plot('c-share', names.map((s, i) => ({ type: 'bar', name: lab[s], x: m.facies, y: sp[s].share.map((v) => v * 100), marker: { color: S(i + 1) }, hovertemplate: `${lab[s]} · %{x}: %{y:.1f} %<extra></extra>` })),
      { barmode: 'group', yaxis: { title: { text: '% of samples' } } })
    const depth = (s) => plot('c-depth', m.facies.map((f, k) => ({ type: 'scatter', mode: 'lines', stackgroup: 'one', orientation: 'h', name: f, line: { width: 0.5, color: FAC()[k] }, fillcolor: FAC()[k],
      x: sp[s].depth_profile[k].map((v) => v * 100), y: sp[s].depth_profile[k].map((_, j) => j * 4), hovertemplate: `${f} · %{y} ms: %{x:.0f} %<extra></extra>` })),
    { yaxis: { autorange: 'reversed', title: { text: 'time from top of cube (ms)' } }, xaxis: { title: { text: '% of traces' }, range: [0, 100] }, legend: { orientation: 'h', y: 1.16 } })
    depth('train')
    view.querySelectorAll('[data-dp]').forEach((b) => { b.onclick = () => { view.querySelectorAll('[data-dp]').forEach((x) => x.classList.toggle('on', x === b)); depth(b.dataset.dp) } })
    const C = sp.train.contacts, pairs = []
    C.forEach((row, a) => row.forEach((n, b) => { if (n) pairs.push({ a, b, n, tot: row.reduce((x, y) => x + y, 0) }) }))
    pairs.sort((x, y) => y.n - x.n)
    $('contacts').innerHTML = table([['Above', (r) => `<span class="dot" style="background:${FAC()[r.a]}"></span> ${esc(m.facies[r.a])}`], ['Directly below', (r) => `<span class="dot" style="background:${FAC()[r.b]}"></span> ${esc(m.facies[r.b])}`],
      ['Traces', (r) => num(r.n), 'num'], ['Share of that unit\'s base', (r) => `${(r.n / r.tot * 100).toFixed(1)} %`, 'num'], ['', (r) => (r.b < r.a ? '<span class="tag amber">upside down</span>' : '')]], pairs, 380)
    plot('c-amp', [bar(sp.train.amp_by_class.map((x, k) => ({ k: x.k, n: x.rms, c: FAC()[k] })), { h: true, fmt: '' })].map((t) => ({ ...t, marker: { color: FAC() }, hovertemplate: '%{y}: RMS %{x:.3f}<extra></extra>' })),
      { yaxis: { autorange: 'reversed' }, xaxis: { title: { text: 'RMS amplitude' } }, margin: { l: 130, r: 10, t: 10, b: 44 } })
    if (lk) plot('c-lk', [{ type: 'bar', orientation: 'h', y: m.facies, x: m.facies.map((f) => (lk.per_class[f] ?? 0) * 100), marker: { color: FAC() }, hovertemplate: '%{y}: %{x:.0f} %<extra></extra>' }],
      { yaxis: { autorange: 'reversed' }, xaxis: { title: { text: '% right in the top 10' }, range: [0, 100] }, margin: { l: 130, r: 10, t: 10, b: 44 },
        shapes: [{ type: 'line', x0: lk.chance * 100, x1: lk.chance * 100, yref: 'paper', y0: 0, y1: 1, line: { color: css('--muted'), dash: 'dot', width: 1.5 } }],
        annotations: [{ x: lk.chance * 100, yref: 'paper', y: 1.04, text: 'chance', showarrow: false, font: { color: css('--muted'), size: 11 } }] })
    spectrumChart('c-sp', sp.train.spectrum)
    rmsTimeChart('c-rmst', sp.train.rms_time, 0, 4, 'time from top of cube (ms)')
  }

  // ---------- start here: how to read this data, in plain words, with the numbers of the cube in front of you ----------
  Object.assign(G, {
    granularity: ['Granularity', 'How far apart the measurements are, in each direction: time between samples down a trace, and distance between traces across the survey. It sets the smallest thing the data can show.'],
    nyquistk: ['Spatial Nyquist', 'The finest pattern a sampling can hold: two samples per wavelength. Anything finer than this folds back as a false, coarser pattern (aliasing).'],
    autocorr: ['Autocorrelation', 'How much a signal resembles a shifted copy of itself. The lag where it falls to half tells how far you can move before the data looks like something else.'],
    fresnel: ['Fresnel zone', 'The patch of reflector that contributes to one echo: radius about (v/2) x sqrt(time / frequency). Before migration, nothing smaller than this is seen sharply.'],
    voxel: ['Voxel', 'One cell of the cube: a bin wide, a bin long and one sample tall. The 3D equivalent of a pixel.'],
    aliasing: ['Aliasing', 'False patterns made by sampling too coarsely: steep dipping layers look flatter or jump between traces.'],
  })
  const cubeSvg = () => {
    const lab = (x, y, t, o = '') => `<text x="${x}" y="${y}" ${o}>${esc(t)}</text>`
    return `<svg viewBox="0 0 470 310" style="width:100%;max-width:540px;font:12px var(--font)">
      <g fill="none" stroke="var(--line-2)" stroke-width="1.2">
        <polygon points="40,90 300,90 300,250 40,250" fill="var(--panel-2)"/>
        <polygon points="40,90 300,90 390,40 130,40" fill="color-mix(in srgb, var(--s3) 14%, transparent)"/>
        <polygon points="300,90 390,40 390,200 300,250" fill="color-mix(in srgb, var(--s1) 10%, transparent)"/>
        <line x1="130" y1="40" x2="130" y2="200" stroke-dasharray="3 4"/><line x1="130" y1="200" x2="390" y2="200" stroke-dasharray="3 4"/><line x1="130" y1="200" x2="40" y2="250" stroke-dasharray="3 4"/>
      </g>
      <polygon points="40,150 300,150 390,100 130,100" fill="color-mix(in srgb, var(--s4) 28%, transparent)" stroke="var(--s4)" stroke-width="1.2"/>
      <line x1="170" y1="90" x2="170" y2="250" stroke="var(--s2)" stroke-width="2.5"/>
      ${[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => `<circle cx="170" cy="${96 + i * 16}" r="2.6" fill="var(--s2)"/>`).join('')}
      <g fill="var(--ink-2)">
        ${lab(170, 286, 'crossline direction  →', 'text-anchor="middle" fill="var(--s3)"')}
        <g transform="rotate(-29 352 50)">${lab(352, 50, 'inline direction  →', 'text-anchor="middle" fill="var(--s1)"')}</g>
        <g transform="rotate(-90 20 170)">${lab(20, 170, 'time  →  (down)', 'text-anchor="middle"')}</g>
        ${lab(180, 236, 'one TRACE', 'fill="var(--s2)"')}
        ${lab(180, 112, 'one SAMPLE', 'fill="var(--s2)" font-size="11"')}
        ${lab(318, 190, 'time slice', 'fill="var(--s4)"')}
        ${lab(50, 244, 'a section', 'font-size="11"')}
      </g></svg>`
  }
  VIEWS.learn = async () => {
    const [pa, pf] = await Promise.all([seisProfile('adele'), seisProfile('f3')])
    const g = pa.grid, ft = pf.splits.train
    const C = {
      adele: { name: 'Adele', ni: g.n_inlines, nx: g.n_crosslines, ns: g.samples, dt: g.dt_ms, dxA: g.bin_m.along_inline, dxB: g.bin_m.between_stored_inlines, v: 3500, win: g.t1_ms - g.t0_ms, t0: g.t0_ms, traces: g.traces, gb: pa.file_gb, rms: pa.rms_median, spec: pa.spectrum },
      f3: { name: 'F3', ni: ft.shape[0], nx: ft.shape[1], ns: ft.shape[2], dt: 4, dxA: pf.bin_m, dxB: pf.bin_m, v: 2000, win: 4 * (ft.shape[2] - 1), t0: 0, traces: ft.shape[0] * ft.shape[1], gb: 1.2, rms: ft.std, spec: ft.spectrum },
    }
    let cur = 'adele'
    view.innerHTML = `<div class="page-head"><div><div class="eyebrow">Start here</div><h1>How to read this data</h1>
      <p class="lede">A seismic cube is a stack of echoes. This page explains every word you meet in the explorer, with the real numbers of the cube you pick. Dotted words
        explain themselves on hover; the <a href="#resolution">Resolution page</a> goes deeper on distances and detail.</p></div>
      <div class="seg" id="lc"><button data-c="adele" class="on">Adele</button><button data-c="f3">F3</button></div></div><div id="lbody"></div>`
    const draw = () => {
      const c = C[cur], z = (ms) => (c.v * ms) / 2000
      const km = (m) => `${num(m / 1000, 1)} km`
      const qa = (q, a) => `<div class="qa"><div class="q">${q}</div><div class="a">${a}</div></div>`
      $('lbody').innerHTML = `
        <div class="section-title">The cube in one picture (${c.name})</div>
        ${panel('A box of numbers', `<div class="grid g2" style="align-items:center"><div>${cubeSvg()}<p class="small muted" style="margin:.2rem 0 0">Crossline: ${num(c.nx)} traces, ${c.dxA} m apart. Inline: ${num(c.ni)} lines, ${c.dxB} m apart. Time: ${num(c.ns)} samples, ${c.dt} ms apart.</p></div><div>
          <p>Imagine the ground under the sea as a box. A ship went over it and recorded echoes. The data is a <b>${num(c.nx)} × ${num(c.ni)} grid</b> of
            ${T('trace', 'traces')} (one per spot on the map), and each trace is a <b>column of ${num(c.ns)} numbers</b> (${T('sample', 'samples')}) going down.</p>
          <ul style="margin:.4rem 0 0 1.1rem;padding:0;line-height:1.7">
            <li>Across the top is the <b>map</b>: ${T('inline')} and ${T('crossline')} are the two map directions.</li>
            <li>Down is <b>time</b>, not depth: how long the sound took to go down to a layer and back (${T('twt', 'two-way time')}).</li>
            <li>Cut the box vertically and you get a <b>section</b>; cut it horizontally and you get a <b>${T('timeslice', 'time slice')}</b>, a map.</li>
            <li>Total: <b>${num(c.traces)}</b> traces × ${num(c.ns)} samples = <b>${num(c.traces * c.ns / 1e6)} million</b> numbers.</li></ul></div></div>`)}
        <div class="section-title">The questions everyone asks first</div>
        <div class="panel">
        ${qa('How long is it between each measured value?', `<b>${c.dt} ms</b> (${num(c.dt / 1000, 3)} seconds) between neighbouring samples down a trace. That is the time step of the data: sound is recorded every ${c.dt} ms.
          Consecutive ${T('timeslice', 'time slices')} are also ${c.dt} ms apart, so the cube has ${num(c.ns)} of them. Sound travels down and back, so each step is ${c.dt / 2} ms of travel in one direction:
          at about ${num(c.v)} m/s that is roughly <b>${num(z(c.dt), 1)} m of rock per sample</b>. The whole recorded window, ${num(c.win)} ms (${c.t0 ? `${num(c.t0)} to ${num(c.t0 + c.win)} ms` : `0 to ${num(c.win)} ms`}), is about ${km(z(c.win))} of rock at that speed.
          The speed is an assumption: nothing in the data says what the rock speed is.`)}
        ${qa('How far apart are the traces?', c.name === 'Adele'
          ? `<b>${c.dxA} m</b> between neighbouring traces along an inline (the crossline direction) but <b>${c.dxB} m</b> between inlines, because only every second inline was kept: the data is 3× coarser one way than the other.
             A trace is not a point measurement: it describes the ground around it, roughly a wavelength wide (a few hundred metres here).`
          : `<b>${c.dxA} m</b> in both directions (a square grid). A trace describes the ground around it, roughly a wavelength wide.`)}
        ${qa('What is a trace?', `The recording at <b>one spot on the map</b>: one column of ${num(c.ns)} numbers, taken top to bottom in time. It is the answer to "what came back from below this spot, and when?".
          A boundary between two kinds of rock sends part of the sound back, so each wiggle of the trace marks a boundary. Strictly, a trace here is many recordings of that spot combined (a ${T('stack')}) to cut noise.
          Plot one trace as a line and you have the <b>wiggle</b> you see when you click the section. A section is ${num(c.nx)} traces side by side.`)}
        ${qa('What is a sample, and what is amplitude?', `A ${T('sample')} is one number on a trace: the strength of the echo at one instant (${c.dt} ms step). That strength is the ${T('amplitude')}. Zero means nothing came back (no boundary);
          red (positive) and blue (negative) are echoes of opposite sign, which tells you whether the sound passed into harder or softer rock. The units are arbitrary: Adele's typical values are about ±${num(pa.amplitude.percentiles['99'], 0)},
          F3's are scaled to −1…+1. Only the relative size matters.`)}
        ${qa('Is time the same as depth?', `No. The vertical axis is <b>two-way time</b>. To get depth you need the rock speed: depth ≈ speed × time ÷ 2. If the speed is ${num(c.v)} m/s, 1 second of two-way time is ${num(z(1000))} m.
          But speed changes with depth and rock, and this cube has no wells to measure it, so the depth axis in the explorer is an estimate you can change.`)}
        ${qa('What is the loudness map?', `For every trace the page works out one number: how <b>loud</b> it is, the ${T('rms', 'RMS amplitude')} of all ${num(c.ns)} samples (square every sample, average, take the root).
          Then every trace position on the map is coloured by that number. So it is a <b>map of how strong the recorded signal is</b> across the survey, not a geological picture.
          What to look for: even colour means even data; sudden stripes or blocks usually come from how the data was collected or processed (an acquisition footprint); dark patches are weak or empty areas.
          ${c.name === 'Adele' ? 'The dark band on the west edge is 8 crosslines of zeros (dead traces).' : ''}`)}
        ${qa('What is loudness against time?', `The same RMS number, but for each <b>time</b> instead of each trace: average strength of all traces at every sample. It shows where in the window the echoes are strong or weak.
          A big change with depth is usually processing and physics (sound weakens as it travels, then gain is applied), so models should normalise per window.`)}
        ${qa('What is coherence?', `A ${T('coherence', 'coherence')} (semblance) view compares each trace with its neighbours over a short stretch of time. Where layers are continuous the neighbours match (dark here); where a ${T('fault')} cuts them they stop matching (bright).
          Bright lines are candidates for faults, but noise and chaotic rock light up too.`)}
        ${qa('What is the frequency spectrum?', `How fast the wiggles are. Low frequencies (few wiggles per second) see big, thick things; high ones see thin layers but fade quickly in rock. ${c.name}'s energy peaks at ${c.spec.peak_hz} Hz and half of it lies between ${c.spec.half_power_hz.join(' and ')} Hz.
          That decides the smallest layer you can tell apart: a quarter of a wavelength, about ${num((c.v / c.spec.peak_hz) / 4)} m here at ${num(c.v)} m/s.`)}
        ${qa('What are dead traces, spikes and clipping?', `A <b>${T('dead', 'dead trace')}</b> is all zeros: no data at that spot. A <b>${T('spike')}</b> is a burst of absurd values from an error (Adele has one trace reaching −350,841 where normal is within ±1,600). <b>${T('clip', 'Clipping')}</b> means showing every value above a limit in the same full colour, so the picture is not ruled by a few huge numbers.`)}
        </div>
        <div class="section-title">The numbers at a glance</div>
        ${panel('Both cubes side by side', `<div class="wrap">${table([['', (r) => `<b>${r[0]}</b>`], ['Adele (official)', (r) => r[1]], ['F3 (stand-in)', (r) => r[2]]], [
          ['Traces', num(C.adele.traces), num(C.f3.traces)], ['Samples per trace', num(C.adele.ns), num(C.f3.ns)], ['Time between samples', '4 ms', '4 ms'], ['Time window', `${num(C.adele.win)} ms`, `${num(C.f3.win)} ms`],
          ['Distance between traces', '12.5 m along, 37.5 m across', '25 m both ways'], ['Area', `${km(34125)} × ${km(11250)} = 384 km²`, `${km(17500)} × ${km(10000)} (train block)`],
          ['Traces per km²', num(1e6 / (12.5 * 37.5)), num(1e6 / (25 * 25))], ['Numbers in the cube', `${num(C.adele.traces * C.adele.ns / 1e6)} million`, `${num(C.f3.traces * C.f3.ns / 1e6)} million (train)`],
          ['Size on disk', '3.5 GB (SEG-Y)', '1.2 GB (arrays)'], ['Typical trace loudness (RMS)', num(C.adele.rms, 0), num(C.f3.rms, 2)]], 600)}</div>`,
          `rows are the facts you need to plan with: how much detail there is across, how much memory a cube needs, how dense the grid is.`)}
        <div class="callout" style="margin-top:1rem">Next: <a href="#${cur}">open the ${c.name} explorer</a> to slice the cube, or <a href="#resolution">see how fine the detail really is</a>.</div>
        ${terms(['trace', 'sample', 'twt', 'amplitude', 'inline', 'crossline', 'timeslice', 'rms', 'coherence', 'spectrum', 'dead', 'spike', 'clip', 'stack'])}`
    }
    $('lc').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; cur = b.dataset.c; $('lc').querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b)); draw() }
    draw()
  }

  // ---------- resolution and granularity: what the spacing lets you see, measured and calculated ----------
  VIEWS.resolution = async () => {
    const [pa, pf, ra, rf] = await Promise.all([seisProfile('adele'), seisProfile('f3'), get('api/seis/resolution/adele'), get('api/seis/resolution/f3')])
    const C = {
      adele: { name: 'Adele', color: S(1), res: ra, sp: pa.spectrum, dt: 4, dxA: 12.5, dxB: 37.5, dims: [301, 2731, 1001], v: 3500, t: 3500, tmin: 1500, tmax: 5500, band: 'peak' },
      f3: { name: 'F3', color: S(2), res: rf, sp: pf.splits.train.spectrum, dt: 4, dxA: 25, dxB: 25, dims: [401, 701, 255], v: 2000, t: 500, tmin: 50, tmax: 1000, band: 'peak' },
    }
    let cur = 'adele'
    const freq = (c) => ({ peak: c.sp.peak_hz, high: c.sp.half_power_hz[1], max: c.sp.minus20_hz[1] })[c.band]
    const calc = (c) => {
      const f = freq(c), lam = c.v / f, dip = (dx) => { const s = c.v / (4 * f * dx); return s >= 1 ? 90 : (Math.asin(s) * 180) / Math.PI }
      return { f, lam, tune: lam / 4, detect: lam / 20, dz: (c.v * c.dt) / 2000, rF: (c.v / 2) * Math.sqrt(c.t / 1000 / f), lat: lam / 2, dipA: dip(c.dxA), dipB: dip(c.dxB) }
    }
    const verdict = (nyq, k95) => { const x = nyq / k95; return x > 3 ? ['finer than the signal needs', 'green'] : x > 1.5 ? ['comfortable', 'blue'] : ['close to the limit', 'amber'] }
    const AX = [['crossline', 'Along an inline (crossline direction)', S(3)], ['inline', 'Between inlines (inline direction)', S(1)], ['time', 'Down a trace (time)', S(2)]]
    const row = (c, a) => { const r = c.res[a], [v, col] = verdict(r.nyquist, r.k95); const u = a === 'time' ? 'Hz' : 'cycles/km'
      return [`${c.name}: ${a}`, `${num(r.d, 1)} ${r.unit}`, `${num(r.nyquist, 1)} ${u}`, `${num(r.k95, 1)} ${u}`, `${num(r.nyquist / r.k95, 1)}×`, r.half_lag ? `${num(r.half_lag, 0)} ${r.unit}` : '–', r.zero_lag ? `${num(r.zero_lag, 0)} ${r.unit}` : 'none within 60 lags', `<span class="tag ${col}">${v}</span>`] }
    view.innerHTML = `<div class="page-head"><div><div class="eyebrow">Analysis</div><h1>Resolution and granularity</h1>
      <p class="lede">How far apart is the data measured, how much of that detail is real, and what is the smallest thing you can see? Measured from the cubes themselves, then a calculator for your own numbers.</p></div></div>
      ${plain(`${T('granularity')} is the spacing of the measurements in each direction: the time between ${T('sample', 'samples')} down a ${T('trace')}, and the distance between traces on the map. Together they make the ${T('voxel', 'voxels')} of the cube.`,
        'The spacing sets a ceiling on detail, but the sound itself sets a lower one: a pulse of 11 Hz is hundreds of metres long. Detail finer than either cannot be seen, so it pays to know which limit you are at.',
        'Decide how to resample the cube for training, whether filling in the missing inlines is worth it, which features (a fault of 10 m throw, a 15 m sand, a 300 m channel) are visible at all.')}
      ${kpis([['4 ms', 'time between samples, both cubes'], ['12.5 × 37.5 m', 'Adele: between traces along × across'], ['25 × 25 m', 'F3: between traces'], ['≈ 7 m / ≈ 4 m', 'Adele / F3 rock per sample (assumed 3,500 / 2,000 m/s)']])}
      <div class="section-title">1. Measured: how finely is the data really sampled?</div>
      ${panel('Spectrum along each direction', `<div class="grid g3" style="gap:.8rem">${['crossline', 'inline', 'time'].map((a) => chart(`rs-${a}`, 260)).join('')}</div>`,
        ['the average power spectrum of the data along one direction, computed on a block of each cube (Adele: 100 inlines × 800 crosslines × 600 samples in the middle; F3: the whole training block). It shows how much of the signal lives at each detail size: left is smooth and broad, right is fine.',
          'the dashed line is the Nyquist limit, the finest detail the spacing can hold; the shaded part holds 95 % of the energy. If the shading ends far left of the dashed line, the spacing is finer than the signal needs. If energy reaches the dashed line, detail is being lost or folded back (aliasing).'])}
      ${panel('How fast does the data stop resembling itself?', `<div class="grid g2" style="gap:.8rem">${chart('ra-lat', 280)}${chart('ra-t', 280)}</div>`,
        ['the autocorrelation: take the data and compare it with a copy shifted by 1, 2, 3… steps. 1 means identical, 0 means unrelated, below 0 means opposite.',
          'the lag where a curve crosses the dotted 0.5 line is the distance over which neighbours still agree. It is a measure of the real grain of the data. Lateral lags are in metres, time in milliseconds. A wide curve means a smooth, slowly varying image.'])}
      ${panel('The numbers', `<div class="wrap">${table([['Direction', (r) => r[0]], ['Spacing', (r) => r[1], 'num'], ['Nyquist', (r) => r[2], 'num'], ['95 % of energy below', (r) => r[3], 'num'], ['Nyquist ÷ that', (r) => r[4], 'num'],
          ['Correlation falls to 0.5 at', (r) => r[5], 'num'], ['First reaches 0', (r) => r[6], 'num'], ['Verdict', (r) => r[7]]], [row(C.adele, 'crossline'), row(C.adele, 'inline'), row(C.adele, 'time'), row(C.f3, 'crossline'), row(C.f3, 'inline'), row(C.f3, 'time')], 600)}</div>`,
        ['the measured granularity of both cubes. Nyquist ÷ 95 % shows how much finer the sampling is than the signal needs: 4× means you could keep every fourth sample and lose almost nothing.',
          `Adele is sampled far finer than its content needs in all three directions: along an inline by ${num(ra.crossline.nyquist / ra.crossline.k95, 0)}×, between inlines still by ${num(ra.inline.nyquist / ra.inline.k95, 1)}×, in time by ${num(ra.time.nyquist / ra.time.k95, 1)}×. So the missing inlines cost little for smooth reflectors; sharp features such as faults are where they could matter. And Adele could be resampled in time to 8 ms with almost no loss.`])}
      <div class="section-title">2. Calculator: what can you resolve?</div>
      ${panel('Your numbers', `<div class="row" style="gap:.6rem 1.2rem;margin-bottom:.7rem">
          <div class="seg" id="rc"><button data-c="adele" class="on">Adele</button><button data-c="f3">F3</button></div>
          <label class="small">Frequency <select id="rb"><option value="peak">dominant (the peak)</option><option value="high">high end (−6 dB)</option><option value="max">highest usable (−20 dB)</option></select></label>
          <label class="small">Rock speed at the target <input id="rv" type="number" min="1000" max="7000" step="100" style="width:80px" /> m/s</label>
          <label class="small">Two-way time <input id="rt" type="number" step="50" style="width:80px" /> ms</label></div><div id="rres"></div>`,
        ['the calculator takes the measured spectrum of the chosen cube and the rock speed you assume. Speed is unknown (no wells in these cubes), so it is yours to set.', 'change a number and everything below updates. Try 2,500 to 4,500 m/s and watch the thinnest layer, the sideways blur and the dip limit move.'])}
      <div class="grid g2">
        ${panel('Thinnest layer you can separate', chart('rch', 330), ['for each rock speed, the thickness at which the top and bottom of a layer can be told apart (a quarter of the wavelength) against frequency. The shaded bands are the frequencies where each cube holds half its energy.',
          'thinner layers merge into one echo (the tuning effect): you see that something is there but not its thickness. Higher frequency or slower rock means thinner layers resolved.'])}
        ${panel('The grid against the sound (to scale)', '<div id="rscale"></div>', ['a 400 m × 400 m patch of ground, with the cube\'s traces drawn as cells and one circle of half a wavelength (about the best sideways resolution after migration).',
          'if many cells fit inside the circle, the grid is much finer than the sound can see; if the circle is only a cell or two, the grid is the limit.'])}
      </div>
      <div class="section-title">3. Could you see it? A feature checker</div>
      ${panel('Pick a feature', `<div class="pres" id="rp" style="margin-bottom:.6rem"></div><div class="row" style="gap:.6rem 1.2rem;margin-bottom:.7rem">
          <label class="small">Thickness or throw <input id="ft" type="number" min="1" step="1" style="width:80px" /> m</label>
          <label class="small">Width <input id="fw" type="number" min="1" step="5" style="width:90px" /> m</label></div><div id="rchk"></div>`,
        ['thickness is how tall the thing is (a layer\'s thickness, a fault\'s throw); width is how wide. The table counts the samples and traces it spans in each cube and says whether it is resolved, only detected, or lost.',
          'rules of thumb used: separated if thicker than a quarter wavelength; detectable (as a bright or dim event, thickness unknown) down to about a twentieth; a shape needs at least 4 traces across.'])}
      <div class="section-title">4. Planning for machine learning</div>
      ${panel('Patches and voxels', `<div class="row" style="gap:.6rem 1.2rem;margin-bottom:.7rem">${['x', 'y', 't'].map((k, i) => `<label class="small">Patch ${['across inlines', 'along inlines', 'in time'][i]} <input id="pl-${k}" type="number" min="16" step="16" value="128" style="width:70px" /> voxels</label>`).join('')}</div><div id="rpl"></div>`,
        ['a training patch is a small block cut from the cube. Set its size in voxels and see how much ground it covers, how many fit, and how stretched the voxels are.',
          'a model sees voxels as equal cubes, but Adele\'s are 12.5 × 37.5 m wide and several metres tall. The resampled row interpolates the inlines to the finer spacing and thins time to the coarsest step that still keeps the highest usable frequency (2.5 samples per period). The measured numbers above say little is lost.'])}
      ${terms(['granularity', 'nyquistk', 'autocorr', 'fresnel', 'voxel', 'aliasing', 'tuning', 'wavelet', 'spectrum', 'dominant', 'sample', 'trace'])}`

    // ---- measured charts
    const axTitle = { crossline: 'cycles per km', inline: 'cycles per km', time: 'frequency (Hz)' }
    for (const [a, label] of AX.map(([x, l]) => [x, l])) {
      const traces = ['adele', 'f3'].map((n) => { const r = C[n].res[a]; return { x: r.k, y: r.power, type: 'scatter', mode: 'lines', name: C[n].name, line: { color: C[n].color, width: 2 }, hovertemplate: `${C[n].name} %{x:.1f}: %{y:.2e}<extra></extra>` } })
      for (const n of ['adele', 'f3']) { // the sampling limit (dashed) and where 95 % of the energy is already reached (dotted)
        const r = C[n].res[a]
        traces.push({ x: [r.nyquist, r.nyquist], y: [1e-7, 1], type: 'scatter', mode: 'lines', name: `${C[n].name} limit`, line: { color: C[n].color, dash: 'dash', width: 1.5 }, hovertemplate: `${C[n].name}: finest detail the spacing holds (${num(r.nyquist, 1)})<extra></extra>`, showlegend: false },
          { x: [r.k95, r.k95], y: [1e-7, 1], type: 'scatter', mode: 'lines', name: `${C[n].name} 95%`, line: { color: C[n].color, dash: 'dot', width: 1.5 }, hovertemplate: `${C[n].name}: 95 % of the energy is below ${num(r.k95, 1)}<extra></extra>`, showlegend: false })
      }
      plot(`rs-${a}`, traces, { xaxis: { title: { text: axTitle[a] }, type: 'log' }, yaxis: { title: { text: 'relative power' }, type: 'log', range: [-6, 0.1] },
        annotations: [{ text: label, xref: 'paper', yref: 'paper', x: 0, y: 1.14, showarrow: false, font: { size: 12 }, xanchor: 'left' }], margin: { l: 56, r: 10, t: 34, b: 44 } })
    }
    const ac = (a, n, dash) => ({ x: C[n].res[a].lag, y: C[n].res[a].r, type: 'scatter', mode: 'lines', name: `${C[n].name} ${a}`, line: { color: a === 'inline' ? S(3) : C[n].color, width: 2, dash }, hovertemplate: `${C[n].name} ${a} lag %{x:.0f}: %{y:.2f}<extra></extra>` })
    const half = { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 0.5, y1: 0.5, line: { color: css('--muted'), dash: 'dot' } }
    plot('ra-lat', [ac('crossline', 'adele', 'solid'), ac('inline', 'adele', 'dash'), ac('crossline', 'f3', 'solid')].map((t, i) => ({ ...t, line: { ...t.line, color: [S(1), S(3), S(2)][i] } })),
      { xaxis: { title: { text: 'lateral lag (m)' }, range: [0, 800] }, yaxis: { title: { text: 'autocorrelation' } }, shapes: [half], legend: { orientation: 'h', y: 1.16 } })
    plot('ra-t', [ac('time', 'adele', 'solid'), ac('time', 'f3', 'solid')].map((t, i) => ({ ...t, line: { ...t.line, color: [S(1), S(2)][i] } })),
      { xaxis: { title: { text: 'time lag (ms)' }, range: [0, 120] }, yaxis: { title: { text: 'autocorrelation' } }, shapes: [half], legend: { orientation: 'h', y: 1.16 } })

    // ---- calculator
    const dipText = (d) => (d >= 90 ? 'any dip (not aliased)' : `${num(d, 0)}° and flatter`)
    function results() {
      const c = C[cur], k = calc(c)
      $('rres').innerHTML = `<div class="wrap">${table([['Quantity', (r) => `<b>${r[0]}</b>`], ['Value', (r) => r[1], 'num'], ['How it is worked out', (r) => `<span class="muted">${r[2]}</span>`], ['What it means', (r) => r[3]]], [
        ['Frequency used', `${num(k.f, 1)} Hz`, 'measured from the cube', 'how fast the wiggles are'],
        ['Wavelength', `${num(k.lam)} m`, 'speed ÷ frequency', 'the length of one wiggle in the rock'],
        ['Thinnest layer you can separate', `${num(k.tune)} m`, 'wavelength ÷ 4 (tuning thickness)', 'thinner layers blur into one event'],
        ['Thinnest layer you can detect', `${num(k.detect)} m`, 'wavelength ÷ 20 (rule of thumb)', 'seen as a brighter or dimmer event, thickness unknown'],
        ['Rock per sample (vertical)', `${num(k.dz, 1)} m`, 'speed × time step ÷ 2', 'the vertical grid; compare with the thinnest separable layer'],
        ['Samples across one wavelength', `${num(k.lam / k.dz, 0)}`, 'wavelength ÷ rock per sample', 'many means smooth, oversampled in time'],
        ['Sideways blur before migration (Fresnel zone)', `${num(k.rF)} m radius`, `(speed ÷ 2) × √(time ÷ frequency), at ${num(c.t)} ms`, 'smaller features smear into this patch; migration removes most of it'],
        ['Best sideways resolution after migration', `${num(k.lat)} m`, 'wavelength ÷ 2 (rule of thumb)', 'about the smallest lateral detail that is real'],
        ['Traces per resolution cell, along / across', `${num(k.lat / c.dxA, 1)} / ${num(k.lat / c.dxB, 1)}`, 'that distance ÷ trace spacing', 'more than 2 means the grid is not the limit'],
        ['Steepest dip kept unaliased, along / across', `${dipText(k.dipA)} / ${dipText(k.dipB)}`, 'sin(angle) = speed ÷ (4 × frequency × spacing)', 'steeper layers jump between traces and look flatter']], 700)}</div>`
      const xs = Array.from({ length: 90 }, (_, i) => 3 + i * 0.7)
      plot('rch', [
        ...[2000, 3000, 4000, 5000].map((v, i) => ({ x: xs, y: xs.map((f) => v / (4 * f)), type: 'scatter', mode: 'lines', name: `${num(v)} m/s`, line: { width: 1.5, color: [S(3), S(4), S(5), S(7)][i] }, hovertemplate: `${num(v)} m/s, %{x:.0f} Hz: %{y:.0f} m<extra></extra>` })),
        { x: [k.f], y: [k.tune], type: 'scatter', mode: 'markers', name: 'your numbers', marker: { size: 11, color: c.color, line: { width: 2, color: css('--bg') } }, hovertemplate: `${c.name}: ${num(k.f, 1)} Hz, ${num(k.tune)} m<extra></extra>` }],
      { xaxis: { title: { text: 'frequency (Hz)' } }, yaxis: { title: { text: 'thinnest separable layer (m)' }, range: [0, 140] }, legend: { orientation: 'h', y: 1.16 },
        shapes: Object.entries(C).flatMap(([n, cc]) => [{ type: 'rect', x0: cc.sp.half_power_hz[0], x1: cc.sp.half_power_hz[1], yref: 'paper', y0: n === 'adele' ? 0.04 : 0, y1: n === 'adele' ? 1 : 0.04, fillcolor: cc.color, opacity: n === 'adele' ? 0.09 : 0.25, line: { width: 0 } }]),
      })
      scale()
      checker()
      planner()
    }
    function scale() {
      const W = 400, px = 0.8, box = (n) => {
        const c = C[n], k = calc(c), dx = c.dxA, dy = c.dxB, wpx = W * px
        const cols = Array.from({ length: Math.floor(W / dx) + 1 }, (_, i) => i * dx * px), rows = Array.from({ length: Math.floor(W / dy) + 1 }, (_, i) => i * dy * px)
        return `<div><svg viewBox="0 0 ${wpx + 2} ${wpx + 26}" style="width:100%;max-width:330px;font:11px var(--font)">
          <rect x="1" y="1" width="${wpx}" height="${wpx}" fill="var(--panel-2)" stroke="var(--line-2)"/>
          ${cols.map((x) => `<line x1="${x + 1}" x2="${x + 1}" y1="1" y2="${wpx + 1}" stroke="var(--line-2)" stroke-width=".6"/>`).join('')}${rows.map((y) => `<line y1="${y + 1}" y2="${y + 1}" x1="1" x2="${wpx + 1}" stroke="var(--line-2)" stroke-width=".6"/>`).join('')}
          <circle cx="${wpx / 2 + 1}" cy="${wpx / 2 + 1}" r="${(k.lat / 2) * px}" fill="${c.color}" fill-opacity=".18" stroke="${c.color}" stroke-width="2"/>
          <line x1="8" x2="${8 + 100 * px}" y1="${wpx + 14}" y2="${wpx + 14}" stroke="var(--ink-2)" stroke-width="2"/><text x="${14 + 100 * px}" y="${wpx + 18}" fill="var(--ink-2)">100 m</text></svg>
          <div class="small muted"><b>${c.name}</b>: cells ${c.dxA} × ${c.dxB} m; circle = half a wavelength, ${num(k.lat)} m (${num(k.f, 1)} Hz at ${num(c.v)} m/s)</div></div>`
      }
      $('rscale').innerHTML = `<div class="grid g2" style="gap:.8rem">${box('adele')}${box('f3')}</div>`
    }
    // ---- feature checker
    const PRE = [['Fault, 10 m throw', 10, 30], ['Fault, 50 m throw', 50, 50], ['Thin sand, 15 m', 15, 2000], ['Reservoir sand, 60 m', 60, 3000], ['Channel, 15 m × 300 m', 15, 300],
      ['Carbonate build-up, 100 m × 1.5 km', 100, 1500], ['Fracture corridor, 5 m wide', 100, 5], ['Gas chimney, 400 m wide', 800, 400]]
    $('rp').innerHTML = PRE.map((p, i) => `<button class="chip" data-p="${i}" style="cursor:pointer">${esc(p[0])}</button>`).join('')
    $('rp').onclick = (e) => { const b = e.target.closest('[data-p]'); if (!b) return; $('ft').value = PRE[+b.dataset.p][1]; $('fw').value = PRE[+b.dataset.p][2]; checker() }
    $('ft').value = 15; $('fw').value = 300
    function checker() {
      const T_ = +$('ft').value || 1, W_ = +$('fw').value || 1
      const col = (c) => {
        const k = calc(c), r = T_ / k.tune
        const vt = T_ >= k.tune ? ['resolved: top and base separate', 'green'] : T_ >= k.detect ? ['detected only: one blurred event', 'amber'] : ['below detection', 'red']
        const lat = (w, dx) => { const n = w / dx; return [n, n >= 8 ? ['well shaped', 'green'] : n >= 4 ? ['shape visible', 'blue'] : n >= 2 ? ['barely there', 'amber'] : ['missed or aliased', 'red']] }
        const a = lat(W_, c.dxA), b = lat(W_, c.dxB)
        return { k, r, vt, a, b }
      }
      const A = col(C.adele), F = col(C.f3), tag = (v) => `<span class="tag ${v[1]}">${v[0]}</span>`
      $('rchk').innerHTML = `<div class="wrap">${table([['', (r) => `<b>${r[0]}</b>`], ['Adele', (r) => r[1]], ['F3', (r) => r[2]]], [
        ['Samples through it (vertical)', `${num(T_ / A.k.dz, 1)}`, `${num(T_ / F.k.dz, 1)}`],
        ['Thickness against the separable limit', `${num(A.r, 2)}× (limit ${num(A.k.tune)} m)`, `${num(F.r, 2)}× (limit ${num(F.k.tune)} m)`],
        ['Vertical verdict', tag(A.vt), tag(F.vt)],
        ['Traces across it, along an inline', `${num(A.a[0], 1)} ${tag(A.a[1])}`, `${num(F.a[0], 1)} ${tag(F.a[1])}`],
        ['Traces across it, between inlines', `${num(A.b[0], 1)} ${tag(A.b[1])}`, `${num(F.b[0], 1)} ${tag(F.b[1])}`],
        ['Narrower than half a wavelength?', W_ < A.k.lat ? `yes (${num(A.k.lat)} m): blurred sideways` : 'no', W_ < F.k.lat ? `yes (${num(F.k.lat)} m): blurred sideways` : 'no']], 400)}</div>`
    }
    // ---- planner
    function planner() {
      const [px, py, pt] = ['x', 'y', 't'].map((k) => Math.max(16, +$(`pl-${k}`).value || 128))
      const one = (n) => {
        const c = C[n], [NI, NX, NS] = c.dims, k = calc(c), dz = k.dz
        const widthX = px * c.dxA, widthY = py * c.dxB, tall = pt * c.dt, nx = Math.floor(NX / px), ny = Math.floor(NI / py), nt = Math.floor(NS / pt)
        const iso = Math.min(c.dxA, c.dxB), newNI = Math.round((NI - 1) * (c.dxB / iso)) + 1, newDt = Math.max(c.dt, Math.floor(1000 / (2.5 * c.sp.minus20_hz[1]) / c.dt) * c.dt), newNS = Math.round(((NS - 1) * c.dt) / newDt) + 1
        const mb = (n_) => `${num((n_ * 4) / 1e9, 1)} GB`
        return [n, [`${c.dxA} × ${c.dxB} × ${num(dz, 1)} m`, `${num(widthX)} × ${num(widthY)} m wide, ${num(tall)} ms (≈ ${num(tall * c.v / 2000)} m) tall`, `${nx} × ${ny} × ${nt} = ${num(nx * ny * nt)}`,
          `${num((nx * 2 - 1) * (ny * 2 - 1) * Math.max(1, nt * 2 - 1))}`, `${c.dxB / c.dxA === 1 ? 'about equal' : `${num(c.dxB / c.dxA, 1)}× longer one way`}`,
          `${num(newNI)} inlines × ${num(NX)} crosslines × ${num(newNS)} samples (${iso} m × ${iso} m × ${newDt} ms): ${mb(newNI * NX * newNS)} as float32`, `${mb(NI * NX * NS)}`]]
      }
      const A = one('adele')[1], F = one('f3')[1]
      $('rpl').innerHTML = `<div class="wrap">${table([['', (r) => `<b>${r[0]}</b>`], ['Adele', (r) => r[1]], ['F3 (train block)', (r) => r[2]]], [
        ['One voxel is', A[0], F[0]], ['One patch covers', A[1], F[1]], ['Whole patches that fit (across × along × time)', A[2], F[2]], ['Patches with 50 % overlap', A[3], F[3]],
        ['Voxel shape', A[4], F[4]], ['Resampled to near-cubic voxels', A[5], F[5]], ['Original size in memory (float32)', A[6], F[6]]], 600)}</div>`
    }
    // ---- wiring
    const sync = () => { const c = C[cur]; $('rb').value = c.band; $('rv').value = c.v; $('rt').value = c.t; $('rt').min = c.tmin; $('rt').max = c.tmax }
    $('rc').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; cur = b.dataset.c; $('rc').querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b)); sync(); results() }
    $('rb').onchange = () => { C[cur].band = $('rb').value; results() }
    $('rv').oninput = () => { C[cur].v = Math.max(500, +$('rv').value || C[cur].v); results() }
    $('rt').oninput = () => { C[cur].t = Math.max(10, +$('rt').value || C[cur].t); results() }
    $('ft').oninput = checker; $('fw').oninput = checker
    ;['x', 'y', 't'].forEach((k) => { $(`pl-${k}`).oninput = planner })
    sync(); results()
  }

  // ---------- KSAT ----------
  VIEWS.ksat = async (d) => {
    view.innerHTML = `${head(d)}${plain(
      `${T('sar', 'Satellite radar')} images of the North Sea from KSAT, 2.1 GB, for finding oil on the sea surface. Handed out at the event; the format is not known yet.`,
      `Oil damps the small waves, so slicks show as dark patches on radar, day or night and through cloud. Near platforms and pipelines a slick is likely a spill; far from them it may be a natural ${T('seep')}, a sign of oil below.`,
      'A seep finder: dark-spot detection on the images, then FactPages to check what lies under each slick (wells, facilities, fields), and the report passages about microseeps.')}
      <div class="callout warn" style="margin-top:1rem">Not here yet. Put the files in <code>data/official/ksat/</code> and this page will be built for them.</div>
      ${terms(['sar', 'seep', 'facility', 'field', 'source'])}`
  }

  frame().catch((e) => { view.innerHTML = `<div class="callout err">${esc(e.message)}</div>` })
})()
