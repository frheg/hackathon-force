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
  const panel = (title, body, how = '', hint = '') => `<div class="panel"><div class="panel-head"><h2>${title}</h2>${hint ? `<span class="hint">${hint}</span>` : ''}</div>${body}${how ? `<p class="how"><b>How to read it:</b> ${how}</p>` : ''}</div>`
  const chart = (id, h = 320) => `<div id="${id}" class="chart" style="height:${h}px"></div>`
  const kpis = (list) => `<div class="kpis" style="margin:1rem 0">${list.map(([v, k, cls = '']) => `<div class="kpi ${cls}"><div class="v">${v}</div><div class="k">${k}</div></div>`).join('')}</div>`
  const table = (cols, rows_, max = 400) => `<div class="table-wrap" style="max-height:${max}px"><table><thead><tr>${cols.map(([h, , c]) => `<th class="${c || ''}">${h}</th>`).join('')}</tr></thead><tbody>${rows_.map((r) => `<tr>${cols.map(([, f, c]) => `<td class="${c || ''}">${f(r)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`
  const plain = (what, why, use) => `<div class="plain"><div><h3>What it is</h3><p>${what}</p></div><div><h3>Why it matters</h3><p>${why}</p></div><div><h3>What you could build</h3><p>${use}</p></div></div>`
  function map(el, points, colorOf, popup, view = [63, 6], zoom = 4.5) {
    const dark = matchMedia('(prefers-color-scheme: dark)').matches
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
  let catalog = null
  const VIEWS = {}
  async function frame() {
    catalog = await get('api/catalog')
    const item = (d) => `<a href="#${d.id}" data-v="${d.id}">${esc(d.name)}<span class="count ${d.downloading ? 'busy' : ''}">${d.downloading ? 'loading' : d.present ? gb(d.bytes) : 'not yet'}</span></a>`
    $('side').innerHTML = `
      <a class="brand" href="#overview"><span class="brand-mark"></span><span><b>Data Atlas</b></span></a>
      <nav class="nav"><a href="#overview" data-v="overview">Overview</a><a href="#connect" data-v="connect">How the data connects</a>
        <a href="#well" data-v="well">Well lookup</a><a href="#glossary" data-v="glossary">Glossary</a></nav>
      <div class="nav-group"><div>From the organisers</div><nav class="nav">${catalog.datasets.filter((d) => d.origin === 'mail').map(item).join('')}</nav></div>
      <div class="nav-group"><div>Found before the event</div><nav class="nav">${catalog.datasets.filter((d) => d.origin === 'earlier').map(item).join('')}</nav></div>
      <div class="side-foot"><a href="../">Subsurface Studio</a><p style="margin:.5rem 0 0">The data behind the tools, explained.</p></div>`
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
  const head = (d, extra = '') => `<div class="page-head"><div><div class="eyebrow">${d.origin === 'mail' ? 'From the organisers' : 'Found before the event'}</div><h1>${esc(d.name)}</h1>
      <p class="lede">${esc(d.what)}</p>
      <div class="meta"><span>Licence <b>${esc(d.licence)}</b></span><span>On disk <b>${gb(d.bytes)}</b>${d.downloading ? ' <span class="tag amber">downloading</span>' : ''}</span>
        <span>Folder <b class="mono">data/${esc(d.path)}</b></span>${d.source ? `<span><a href="${esc(d.source)}" target="_blank" rel="noopener">Source</a></span>` : ''}${d.built ? `<span>Profiled <b>${esc(d.built)}</b></span>` : ''}</div></div>${extra}</div>`
  const profile = (n) => get(`api/profile/${n}`)

  // ---------- overview ----------
  VIEWS.overview = async () => {
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
    const keys = Object.keys(G).sort((a, b) => G[a][0].localeCompare(G[b][0]))
    view.innerHTML = `<div class="page-head"><div><div class="eyebrow">Reference</div><h1>Glossary</h1><p class="lede">${keys.length} terms from
      geology, drilling, production and the datasets, in plain words.</p></div><input id="gq" placeholder="Filter" style="min-width:240px" /></div><div class="gloss" id="gl"></div>`
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
  function drawSection(canvas, sec) {
    const [h, w] = sec.shape
    const a = new Int8Array(Uint8Array.from(atob(sec.data), (c) => c.charCodeAt(0)).buffer)
    canvas.width = w; canvas.height = h
    const g = canvas.getContext('2d'), im = g.createImageData(w, h)
    for (let i = 0; i < h * w; i++) { // diverging: blue (negative) through white to red (positive), the seismic convention
      const v = a[i] / 127, o = i * 4
      im.data[o] = v > 0 ? 255 : 255 + v * 200; im.data[o + 1] = 255 - Math.abs(v) * 200; im.data[o + 2] = v < 0 ? 255 : 255 - v * 200; im.data[o + 3] = 255
    }
    g.putImageData(im, 0, 0)
  }
  async function seismicView(d, which) {
    const p = await profile('seismic')
    const a = p.adele, f = p.f3
    const isAdele = which === 'adele'
    view.innerHTML = `${head(d)}${plain(
      isAdele ? `A 3D ${T('seismic')} survey from the Northwest Shelf of Australia in ${T('segy', 'SEG-Y')}, the industry's file format. ${a ? `${num(a.traces)} ${T('trace', 'traces')} of ${num(a.samples)} samples each.` : ''} Used in FORCE 2020 to find ${T('fault', 'faults')}.`
        : `A 3D ${T('seismic')} cube from block F3 in the Dutch North Sea, with every sample labelled by rock unit (${T('facies')}). ${f ? `${num(f.shape[0])} ${T('inline', 'inlines')} by ${num(f.shape[1])} traces by ${num(f.shape[2])} samples.` : ''}`,
      'Interpreters spend weeks picking horizons and faults by hand in a cube like this before a well is placed. Seismic is the only picture of the rock between wells.',
      isAdele ? 'Fault detection, SEG-Y reading and QC, attribute maps, tying wells to seismic. The cube has no labels, so you judge results by eye or against an interpreter.'
        : 'Facies classification with known answers (Seismic Lookalike uses it), similarity search, explaining a section in words.')}
      ${isAdele && a ? kpis([[num(a.traces), T('trace', 'traces')], [num(a.n_inlines), T('inline', 'inlines')], [num(a.n_crosslines), 'crosslines'], [num(a.samples), 'samples per trace'], [`${num(a.dt_ms, 1)} ms`, 'sample interval'], [`${num(a.record_ms)} ms`, `record length (${T('twt', 'TWT')})`]]) : ''}
      ${!isAdele && f ? kpis([[num(f.shape[0]), T('inline', 'inlines')], [num(f.shape[1]), 'traces per inline'], [num(f.shape[2]), 'samples per trace'], [f.facies.length, `${T('facies')} classes`], [`${num(f.gb, 1)} GB`, 'on disk']]) : ''}
      ${isAdele ? (a ? `${panel(`Inline ${a.section.inline}`, `<div class="canvas-wrap"><canvas id="sec"></canvas></div>`, `a vertical slice through the cube. Across is position, down is ${T('twt', 'time')} (deeper). Red and blue are positive and negative ${T('amplitude', 'amplitudes')}: layer boundaries. Breaks and offsets in the layers are ${T('fault', 'faults')}.`)}
        <div class="grid g2">${panel('Amplitude distribution', chart('c-amp', 300), 'how strong the echoes are. Symmetric around zero; the tails are the bright reflectors.')}
        ${panel('The SEG-Y text header', `<pre class="sample" style="max-height:300px">${esc(a.header)}</pre>`, 'the first 3,200 characters of every SEG-Y file: who shot it, how it was processed, where the coordinates sit in the trace headers.')}</div>`
        : '<div class="empty">Not profiled yet.</div>')
        : (f ? `${panel('Rock units in the labels', chart('c-fac', 300), 'samples per class (every 10th inline). The labels make this a benchmark: a model\'s facies can be scored.')}
          <div class="callout">Sections with labels and similarity search live in the <a href="../seismic/">Seismic Lookalike</a> tool.</div>` : '<div class="empty">Not profiled yet.</div>')}
      ${terms(['seismic', 'inline', 'trace', 'twt', 'amplitude', 'segy', 'fault', 'facies', 'trap', 'seal'])}`
    if (isAdele && a) { drawSection($('sec'), a.section); plot('c-amp', [histo(a.amplitude, S(1))], { xaxis: { title: { text: 'amplitude' } } }) }
    if (!isAdele && f) plot('c-fac', [bar(f.facies, { h: true })], { yaxis: { autorange: 'reversed' }, margin: { l: 150, r: 10, t: 10, b: 40 } })
  }
  VIEWS.adele = (d) => seismicView(d, 'adele')
  VIEWS.f3 = (d) => seismicView(d, 'f3')

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
