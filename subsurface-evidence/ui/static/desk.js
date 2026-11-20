// Strata Desk is local to the 3D workspace. A different view starts a new context for follow-ups.
const DESK_NAME = "Strata Desk";
const DESK_API = new URL("../hackathon/detective/api/strata/ask", location.href);
let closeDesk = () => {};

const DESK_TAGS = new Set("a blockquote br code del em h1 h2 h3 h4 h5 h6 hr li ol p pre strong table tbody td th thead tr ul".split(" "));
function deskMarkdown(text, refs) {
  const parsed = document.createElement("template"), result = document.createDocumentFragment();
  if (globalThis.marked) {
    const renderer = new marked.Renderer();
    renderer.html = (html) => esc(html);
    parsed.innerHTML = marked.parse(text, { renderer, gfm: true, breaks: true, async: false });
  } else parsed.content.textContent = text;
  let linked = 0;
  const copy = (parent, node, cite = true) => {
    if (node.nodeType === Node.TEXT_NODE) {
      if (!cite) { parent.append(node.data); return; }
      let end = 0;
      for (const match of node.data.matchAll(/\[((?:S\d+|F:[\w-]+))\]/g)) {
        parent.append(node.data.slice(end, match.index));
        const source = refs.get(match[1]), ref = document.createElement(source ? "button" : "span");
        ref.textContent = match[0];
        if (source) { ref.type = "button"; ref.className = "desk-cite"; ref.dataset.source = source; linked++; }
        else { ref.className = "desk-unresolved"; ref.title = "No matching source"; }
        parent.append(ref);
        end = match.index + match[0].length;
      }
      parent.append(node.data.slice(end));
      return;
    }
    // Rebuild only formatting elements; never copy generated attributes or load images.
    const tag = node.localName;
    if (!DESK_TAGS.has(tag)) return;
    let dest = document.createElement(tag);
    if (tag === "a") {
      const href = node.getAttribute("href") || "";
      if (/^https?:\/\//i.test(href)) { dest.href = href; dest.target = "_blank"; dest.rel = "noopener noreferrer"; }
      else dest = document.createElement("span");
    }
    if (tag === "ol" && /^\d+$/.test(node.getAttribute("start") || "")) dest.start = Number(node.getAttribute("start"));
    for (const child of node.childNodes) copy(dest, child, cite && !["pre", "code", "a"].includes(tag));
    parent.append(dest);
  };
  for (const child of parsed.content.childNodes) copy(result, child);
  return { result, linked };
}

function mountDesk(pane, readView) {
  const form = $("form", pane), input = $("#desk-question", pane), send = $("button[type=submit]", form);
  const box = $("#desk-transcript", pane), status = $("#desk-status", pane), scope = $("#desk-scope", pane);
  const samples = $("#desk-samples", pane), clear = $("#desk-clear", pane);
  let history = [], lastScope = "", pending = null, serial = 0;
  const article = (role, html) => {
    const el = document.createElement("article");
    el.className = "desk-turn";
    el.innerHTML = `<span class="desk-role">${role}</span>${html}`;
    box.append(el);
    box.scrollTop = box.scrollHeight;
    return el;
  };
  const sync = () => {
    const view = readView();
    scope.textContent = view.interval ? `${view.target} · ${view.interval.wellbore} · ${view.interval.top_md.toFixed(0)}–${view.interval.base_md.toFixed(0)} m MD` : `${view.target} · ${view.region} · no interval selected`;
  };
  const draft = (q) => { if (!pending) { input.value = q; input.focus(); } };
  samples.onclick = (event) => {
    const button = event.target.closest("button[data-question]");
    if (button) draft(button.dataset.question);
  };
  clear.onclick = () => {
    if (pending) return;
    history = [];
    box.replaceChildren(samples);
    samples.hidden = false;
    status.textContent = "";
    input.focus();
  };
  form.onsubmit = async (event) => {
    event.preventDefault();
    const q = input.value.trim();
    if (pending || q.length < 3) return;
    const scene = readView(), key = JSON.stringify(scene), prior = key === lastScope ? history : [];
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort("timeout"), 120_000);
    pending = controller;
    samples.hidden = true;
    input.disabled = send.disabled = clear.disabled = true;
    status.textContent = "Reading sources and composing…";
    const question = article("You", `<p>${esc(q)}</p>`);
    try {
      const res = await fetch(DESK_API, {
        method: "POST", headers: { "content-type": "application/json" }, signal: controller.signal,
        body: JSON.stringify({ q, scene, history: prior }),
      });
      if (!res.ok) {
        const out = res.headers.get("content-type")?.includes("application/json") ? await res.json() : {};
        throw new Error({
          401: "Sign in again, then retry.", 403: "Your session cannot access the evidence service.",
          404: "The evidence service is not available on this deployment.",
          422: "The question or view context is invalid.", 503: "The local GPU is busy. Retry when it is free.",
          504: "The local model took too long. Retry after it warms up.",
        }[res.status] || (typeof out.detail === "string" ? out.detail : `Evidence service returned HTTP ${res.status}.`));
      }
      const out = await res.json();
      if (!pane.isConnected) return;
      const id = `desk-${++serial}`;
      const refs = new Map(out.sources.map((s, i) => [s.ref, `${id}-${i}`]));
      const { result, linked } = deskMarkdown(out.answer, refs);
      const sourceHtml = out.sources.map((s, i) => `<details class="desk-source" id="${id}-${i}">
        <summary><b>[${esc(s.ref)}]</b> ${esc(s.document)}${s.page ? ` · p. ${esc(s.page)}` : ""}</summary>
        <p>${esc(s.text)}</p>${s.excerpted ? '<p class="tip">Excerpt, not the full source.</p>' : ""}</details>`).join("");
      const reply = article(DESK_NAME, `<div class="desk-answer"></div>
        ${out.sources.length && !linked ? '<p class="tip">No source linked in this answer. Treat geological claims as unverified.</p>' : ""}
        ${sourceHtml ? `<details class="desk-sources"><summary>Retrieved evidence · ${out.sources.length} excerpts</summary>${sourceHtml}</details>` : '<p class="tip">No matching source excerpts for this question.</p>'}
        <p class="tip desk-meta">${esc(out.model)} · ${esc(out.seconds)} s</p>`);
      $(".desk-answer", reply).append(result);
      box.scrollTop = box.scrollHeight;
      reply.onclick = (e) => {
        const cite = e.target.closest("[data-source]");
        if (!cite) return;
        const source = $(`#${cite.dataset.source}`, reply);
        source.parentElement.open = true;
        source.open = true;
        source.scrollIntoView({ block: "nearest" });
        $("summary", source).focus({ preventScroll: true });
      };
      lastScope = key;
      history = [...prior, { question: q, answer: out.answer.slice(0, 900) }].slice(-2);
      input.value = "";
      status.textContent = "";
    } catch (error) {
      if (!pane.isConnected) return;
      question.remove();
      samples.hidden = box.querySelector(".desk-turn") != null;
      status.textContent = controller.signal.reason === "timeout" ? "The local model took too long. Retry after it warms up." : error.message;
    } finally {
      clearTimeout(timer);
      pending = null;
      input.disabled = send.disabled = clear.disabled = false;
    }
  };
  closeDesk = () => pending?.abort();
  sync();
  return { sync, draft };
}
