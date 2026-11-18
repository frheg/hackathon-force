// The frame around every page: the sidebar with all apps, helpers for calls, numbers and charts.
// A page sets <body data-app="copilot" data-root=".."> and puts its content in <main class="page">.
;(() => {
  const body = document.body
  const root = body.dataset.root || '.'
  const current = body.dataset.app || ''

  for (const href of [
    'https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap',
  ]) {
    const l = document.createElement('link')
    l.rel = 'stylesheet'
    l.href = href
    document.head.appendChild(l)
  }

  const content = document.createElement('div')
  content.className = 'content'
  while (body.firstChild) content.appendChild(body.firstChild)
  const side = document.createElement('aside')
  side.className = 'side'
  const shell = document.createElement('div')
  shell.className = 'shell'
  shell.append(side, content)
  const menu = document.createElement('button')
  menu.className = 'menu-btn'
  menu.textContent = 'Menu'
  menu.onclick = () => side.classList.toggle('open')
  body.append(shell, menu)

  fetch(`${root}/api/apps`)
    .then((r) => r.json())
    .then(({ groups, apps }) => {
      const nav = groups
        .map((g) => {
          const items = apps
            .filter((a) => a.group === g.id)
            .map(
              (a) =>
                `<a href="${root}/${a.path}/" class="${a.path === current ? 'on' : ''}"><span class="dot" style="background:${g.color}"></span>${esc(a.name)}${a.fresh ? '<span class="new">new</span>' : ''}</a>`,
            )
            .join('')
          return items ? `<div class="nav-group"><div>${esc(g.name)}</div><nav class="nav">${items}</nav></div>` : ''
        })
        .join('')
      side.innerHTML = `
        <a class="brand" href="${root}/"><span class="brand-mark"></span><span><b>Subsurface Studio</b></span></a>
        <nav class="nav"><a href="${root}/" class="${current ? '' : 'on'}">Overview</a></nav>
        ${nav}
        <div class="side-foot"><label class="field">Language model<select id="model-pick"></select></label>
          <p style="margin:.6rem 0 0">FORCE VibeCode Hackathon<br />Stavanger, November 2026<br /><a href="${root}/status/">Connections</a></p></div>`
      models()
    })
    .catch(() => {})

  // helpers the pages share
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim()

  // the model every call uses, chosen in the sidebar (empty: the server default)
  const store = { get: (k) => { try { return localStorage.getItem(k) || "" } catch { return "" } }, set: (k, v) => { try { localStorage.setItem(k, v) } catch {} } }
  async function models() {
    const sel = document.getElementById("model-pick")
    if (!sel) return
    const d = await fetch(`${root}/api/models`).then((r) => r.json()).catch(() => null)
    if (!d) return
    const chosen = store.get("studio.model")
    sel.innerHTML = d.models.map((m) => `<option value="${esc(m)}" ${m === (chosen || d.default) ? "selected" : ""}>${esc(m)}${m === d.default ? " (default)" : ""}</option>`).join("")
    sel.onchange = () => store.set("studio.model", sel.value === d.default ? "" : sel.value)
  }

  async function call(url, body) {
    const headers = { "X-Model": store.get("studio.model") }
    if (body !== undefined) headers["Content-Type"] = "application/json"
    const r = await fetch(url, body === undefined ? { headers } : { method: "POST", headers, body: JSON.stringify(body) })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
    return d
  }

  // run fn while showing a spinner in el and disabling btn; errors land in el
  async function busy(btn, el, text, fn) {
    if (btn) btn.disabled = true
    if (el) el.innerHTML = `<span class="thinking"><span class="spin"></span>${esc(text)}</span>`
    try {
      const out = await fn()
      if (el) el.innerHTML = ''
      return out
    } catch (e) {
      if (el) el.innerHTML = `<div class="callout err small">${esc(e.message)}</div>`
      throw e
    } finally {
      if (btn) btn.disabled = false
    }
  }

  const num = (v, d = 1) => (v === null || v === undefined || Number.isNaN(+v) ? '–' : (+v).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: 0 }))

  // Plotly layout in the page's colours
  function plotLayout(extra = {}) {
    const ink = css('--ink-2'), grid = css('--line'), muted = css('--muted')
    const axis = (a = {}) => ({ gridcolor: grid, zerolinecolor: grid, linecolor: grid, tickfont: { color: muted, size: 11 }, title: { font: { color: muted, size: 12 } }, ...a })
    const base = {
      paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { family: 'Geist, Inter, system-ui, sans-serif', color: ink, size: 12 },
      margin: { l: 56, r: 20, t: 16, b: 40 }, hoverlabel: { bgcolor: css('--panel-2'), bordercolor: css('--line-2'), font: { color: css('--ink') } },
      legend: { orientation: 'h', y: 1.1, font: { color: ink } }, xaxis: axis(), yaxis: axis(),
    }
    for (const [k, v] of Object.entries(extra)) base[k] = /^[xy]axis\d*$/.test(k) ? axis(v) : v
    return base
  }
  const plotConfig = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d', 'toggleSpikelines'] }
  const palette = () => [css('--accent'), css('--blue'), css('--amber'), css('--violet'), css('--red'), css('--green'), '#94a3b8']

  // a map of the shelf: Esri ocean basemap (bathymetry, coast, names) so open sea is never a blank grey
  function shelfMap(el, view = [62.5, 4], zoom = 5) {
    const m = L.map(el, { scrollWheelZoom: false, zoomSnap: 0.5 }).setView(view, zoom)
    // dark: Esri dark grey canvas; light: Esri ocean (bathymetry). Both show coast and names.
    const dark = matchMedia("(prefers-color-scheme: dark)").matches
    const esri = "https://server.arcgisonline.com/ArcGIS/rest/services"
    const [base, ref, native] = dark ? ["Canvas/World_Dark_Gray_Base", "Canvas/World_Dark_Gray_Reference", 15] : ["Ocean/World_Ocean_Base", "Ocean/World_Ocean_Reference", 9]
    L.tileLayer(`${esri}/${base}/MapServer/tile/{z}/{y}/{x}`, { maxZoom: 13, maxNativeZoom: native, attribution: "Esri, GEBCO, NOAA, Garmin" }).addTo(m)
    L.tileLayer(`${esri}/${ref}/MapServer/tile/{z}/{y}/{x}`, { maxZoom: 13, maxNativeZoom: native }).addTo(m)
    return m
  }

  window.studio = { esc, css, call, busy, num, plotLayout, plotConfig, palette, shelfMap }
})()
