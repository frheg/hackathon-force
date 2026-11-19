// Dark/light choice, shared by every page. Loaded in <head> so the saved choice is set before the first paint.
// No saved choice: follow the system. The choice lives in this browser only.
;(() => {
  const root = document.documentElement
  const KEY = 'studio-theme'
  const saved = () => { try { return localStorage.getItem(KEY) } catch { return null } }
  const isDark = () => getComputedStyle(root).colorScheme.startsWith('dark')
  const apply = (t) => { if (t === 'dark' || t === 'light') root.dataset.theme = t; else delete root.dataset.theme }
  apply(saved())
  // the left menu: open or collapsed, remembered; set before first paint so there is no flash
  const SIDE = 'studio-side'
  const sideClosed = () => { try { return localStorage.getItem(SIDE) === 'closed' } catch { return false } }
  const setSide = (closed) => {
    if (closed) root.dataset.side = 'closed'; else delete root.dataset.side
    try { localStorage.setItem(SIDE, closed ? 'closed' : 'open') } catch { /* fine */ }
    dispatchEvent(new Event('resize')) // charts and canvases fit the new width
  }
  if (sideClosed()) root.dataset.side = 'closed'
  document.addEventListener('DOMContentLoaded', () => {
    if (!document.querySelector('.shell')) return
    const b = document.createElement('button')
    b.className = 'side-toggle'
    b.type = 'button'
    b.title = 'Hide or show the menu'
    b.setAttribute('aria-label', 'Hide or show the menu')
    b.innerHTML = '<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2" y="3" width="14" height="12" rx="2"/><line x1="7" y1="3" x2="7" y2="15"/></svg>'
    b.onclick = () => setSide(!root.dataset.side)
    document.body.appendChild(b)
  })
  window.theme = {
    isDark,
    toggle() {
      const next = isDark() ? 'light' : 'dark'
      try { localStorage.setItem(KEY, next) } catch { /* private window: the choice lasts until reload */ }
      apply(next)
      dispatchEvent(new Event('themechange'))
    },
    // the sidebar button: its label names the mode it switches to
    button() {
      const b = document.createElement('button')
      b.className = 'btn ghost theme-btn'
      b.type = 'button'
      const label = () => { b.textContent = isDark() ? 'Light mode' : 'Dark mode' }
      b.onclick = () => { this.toggle(); label() }
      label()
      matchMedia('(prefers-color-scheme: dark)').addEventListener('change', label)
      return b
    },
  }
})()
