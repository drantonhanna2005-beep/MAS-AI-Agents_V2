/* ============ فريق الوكلاء الأكاديمي — منطق الواجهة (ثنائي اللغة عربي/English) ============ */
"use strict";

/* ---------------- أدوات عامة ---------------- */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

function toast(text, isErr = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isErr ? " err" : "");
  el.textContent = text;
  $("#toastRoot").appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { msg = (await res.json()).error || msg; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

/* ---------------- عارض Markdown مصغّر وآمن ---------------- */
function inlineMd(s) {
  s = esc(s);
  s = s.replace(/`([^`]+)`/g, (_m, c) => `<code>${c}</code>`);
  s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>");
  const safeUrl = (u) => u.replace(/"/g, "%22").replace(/'/g, "%27");
  s = s.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, (_m, tt, u) => `<a href="${safeUrl(u)}" target="_blank" rel="noopener">${tt}</a>`);
  s = s.replace(/(^|[\s>])(https?:\/\/[^\s<]+)/g, (_m, p, u) => `${p}<a href="${safeUrl(u)}" target="_blank" rel="noopener">${u}</a>`);
  s = s.replace(/\[(S\d+|W\d+)\]/g, '<span class="sref">[$1]</span>');
  return s;
}
/* كتلة كود احترافية: عنوان اللغة + نسخ + ملء الشاشة + تظليل خفيف بدون مكتبات (يعمل أثناء البث) */
function _hlCode(code, lang) {
  const escH = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const src = String(code || "");
  const l = (lang || "").toLowerCase();
  // لغات نصية/غير معروفة: نكتفي بالتهريب الآمن
  if (!l || /^(text|txt|plain|plaintext|md|markdown)$/.test(l)) return escH(src);
  const toks = [];
  let i = 0;
  const push = (cls, v) => toks.push(cls ? `<span class="${cls}">${escH(v)}</span>` : escH(v));
  const keywords = {
    common: /^(if|else|for|while|do|switch|case|break|continue|return|try|catch|finally|throw|new|class|function|def|import|from|as|in|is|not|and|or|with|async|await|yield|lambda|pass|raise|except|True|False|None|null|undefined|true|false|const|let|var|export|default|extends|implements|interface|type|public|private|protected|static|void|int|float|double|str|string|bool|boolean|list|dict|map|set|print|echo|SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP|BY|ORDER|LIMIT|CREATE|TABLE|VALUES|AND|OR|NOT|NULL)$/,
  };
  while (i < src.length) {
    const ch = src[i];
    // تعليقات
    if (ch === "/" && src[i + 1] === "/") { let j = i + 2; while (j < src.length && src[j] !== "\n") j++; push("tok-c", src.slice(i, j)); i = j; continue; }
    if (ch === "/" && src[i + 1] === "*") { let j = i + 2; while (j < src.length && !(src[j] === "*" && src[j + 1] === "/")) j++; j = Math.min(src.length, j + 2); push("tok-c", src.slice(i, j)); i = j; continue; }
    if (ch === "#" && !/^#([0-9a-fA-F]{3,8})\b/.test(src.slice(i))) { let j = i + 1; while (j < src.length && src[j] !== "\n") j++; push("tok-c", src.slice(i, j)); i = j; continue; }
    if (ch === "-" && src[i + 1] === "-" && /\s/.test(src[i + 2] || " ")) { let j = i + 2; while (j < src.length && src[j] !== "\n") j++; push("tok-c", src.slice(i, j)); i = j; continue; }
    // سلاسل نصية
    if (ch === '"' || ch === "'" || ch === "`") {
      const q = ch; let j = i + 1; let escp = false;
      while (j < src.length) { const c = src[j]; if (escp) { escp = false; j++; continue; } if (c === "\\") { escp = true; j++; continue; } if (c === q) { j++; break; } if (q !== "`" && c === "\n") break; j++; }
      push("tok-s", src.slice(i, j)); i = j; continue;
    }
    // أرقام
    if (/[0-9]/.test(ch) && (i === 0 || !/[\w$]/.test(src[i - 1]))) {
      let j = i; if (ch === "0" && /[xXbBoO]/.test(src[j + 1] || "")) j += 2;
      while (j < src.length && /[0-9a-fA-F_\.]/.test(src[j])) j++;
      push("tok-n", src.slice(i, j)); i = j; continue;
    }
    // كلمات/معرّفات
    if (/[A-Za-z_\u0600-\u06FF$]/.test(ch)) {
      let j = i + 1; while (j < src.length && /[A-Za-z0-9_\u0600-\u06FF$]/.test(src[j])) j++;
      const w = src.slice(i, j);
      if (keywords.common.test(w) || /^(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP|BY|ORDER|LIMIT|CREATE|TABLE|VALUES|ALTER|DROP|INDEX|INTO|SET|HAVING|DISTINCT|AS)$/.test(w)) push("tok-k", w);
      else if (/^[A-Z][A-Za-z0-9_]*$/.test(w) && !/^[A-Z_]+$/.test(w)) push("tok-t", w);
      else push("", w);
      i = j; continue;
    }
    push("", ch); i++;
  }
  return toks.join("");
}
const CB_LANG_NAMES = { py: "Python", python: "Python", js: "JavaScript", javascript: "JavaScript", ts: "TypeScript",
  typescript: "TypeScript", bash: "Bash", sh: "Shell", zsh: "Zsh", powershell: "PowerShell", ps1: "PowerShell",
  bat: "Batch", cmd: "Batch", json: "JSON", html: "HTML", xml: "XML", css: "CSS", sql: "SQL", java: "Java",
  "c": "C", "cpp": "C++", "c++": "C++", "cs": "C#", "go": "Go", "rs": "Rust", rust: "Rust", php: "PHP",
  yaml: "YAML", yml: "YAML", md: "Markdown", text: "Text", txt: "Text", plaintext: "Text", diff: "Diff",
  dockerfile: "Dockerfile", makefile: "Makefile", kotlin: "Kotlin", kt: "Kotlin", swift: "Swift", r: "R",
  matlab: "MATLAB", arduino: "Arduino", ini: "INI", toml: "TOML", env: ".env" };
const _cbSeq = { n: 0 };
function codeBlockHtml(lang, code) {
  const l = (lang || "").toLowerCase();
  const label = CB_LANG_NAMES[l] || (lang ? lang.toUpperCase() : "Code");
  const id = "cb" + (++_cbSeq.n);
  const safeCode = esc(code);
  const highlighted = _hlCode(code, l);
  return `<div class="codeblock" dir="ltr" data-cbid="${id}">` +
    `<div class="cb-head"><span class="cb-lang" title="${esc(label)}">${esc(label)}</span>` +
    `<span class="cb-actions">` +
    `<button type="button" class="cb-btn" data-cb="copy" title="${esc(t("cb_copy") || "Copy")}"><svg class="ic"><use href="#i-file"/></svg><span class="cb-txt">${esc(t("cb_copy") || "Copy")}</span></button>` +
    `<button type="button" class="cb-btn" data-cb="full" title="${esc(t("cb_fullscreen") || "Full screen")}"><svg class="ic"><use href="#i-expand"/></svg></button>` +
    `</span></div>` +
    `<pre class="cb-pre"><code class="cb-code">${highlighted}</code></pre></div>`;
}
function _cbCodeOf(block) {
  const c = block?.querySelector(".cb-code");
  return c ? (c.textContent || "") : "";
}
async function _copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; }
  catch {
    try { const ta = document.createElement("textarea"); ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select(); const ok = document.execCommand("copy"); ta.remove(); return ok; } catch { return false; }
  }
}
function openCodeFullscreen(block) {
  const code = _cbCodeOf(block);
  const lang = block?.querySelector(".cb-lang")?.textContent || "Code";
  const ov = document.createElement("div");
  ov.className = "cb-modal";
  const langAttr = (block?.querySelector(".cb-code")?.className.match(/language-([\w+#-]+)/)?.[1]) || lang || "";
  const hl = _hlCode(code, langAttr);
  ov.innerHTML = `<div class="cb-modal-card" dir="ltr"><div class="cb-head"><span class="cb-lang">${esc(lang)}</span>` +
    `<span class="cb-actions"><button type="button" class="cb-btn" data-cb="copy"><svg class="ic"><use href="#i-file"/></svg><span class="cb-txt">${esc(t("cb_copy") || "Copy")}</span></button>` +
    `<button type="button" class="cb-btn" data-cb="close" title="${esc(t("cb_close") || "Close")}">✕</button></span></div>` +
    `<pre class="cb-pre cb-pre-full"><code class="cb-code">${hl}</code></pre></div>`;
  document.body.appendChild(ov);
  const close = () => ov.remove();
  ov.addEventListener("click", (e) => { if (e.target === ov) close(); });
  ov.querySelector('[data-cb="close"]')?.addEventListener("click", close);
  ov.querySelector('[data-cb="copy"]')?.addEventListener("click", async (e) => {
    const ok = await _copyText(code); toast(ok ? (t("cb_copied") || "Copied") : (t("cb_copy_fail") || "Copy failed"), !ok);
  });
  const escKey = (e) => { if (e.key === "Escape") { close(); document.removeEventListener("keydown", escKey); } };
  document.addEventListener("keydown", escKey);
}
document.addEventListener("click", async (e) => {
  const btn = e.target.closest?.("[data-cb]");
  if (!btn || btn.closest(".cb-modal")) return;
  const block = btn.closest(".codeblock");
  if (!block) return;
  const act = btn.dataset.cb;
  if (act === "copy") {
    const ok = await _copyText(_cbCodeOf(block));
    const txt = btn.querySelector(".cb-txt"); const old = txt?.textContent || "";
    if (txt) txt.textContent = ok ? (t("cb_copied") || "Copied") : (t("cb_copy_fail") || "Copy failed");
    btn.classList.toggle("ok", ok);
    setTimeout(() => { if (txt) txt.textContent = old; btn.classList.remove("ok"); }, 1400);
  } else if (act === "full") openCodeFullscreen(block);
});
function md(src) {
  const blocks = [];
  src = String(src ?? "").replace(/```([\w+#-]*)[^\n]*\n?([\s\S]*?)```/g, (_m, _l, code) => {
    blocks.push(codeBlockHtml(_l, code.replace(/\n$/, "")));
    return "\u0000" + (blocks.length - 1) + "\u0000";
  });
  const out = [];
  let ul = null, ol = null, table = [];
  const flushLists = () => {
    if (ul) { out.push("<ul>" + ul.join("") + "</ul>"); ul = null; }
    if (ol) { out.push("<ol>" + ol.join("") + "</ol>"); ol = null; }
  };
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter((r) => !/^[\s|:\-]+$/.test(r));
    const cells = (r) => r.replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => inlineMd(c.trim()));
    let html = "<table>";
    rows.forEach((r, ri) => {
      const tag = ri === 0 ? "th" : "td";
      html += "<tr>" + cells(r).map((c) => `<${tag}>${c}</${tag}>`).join("") + "</tr>";
    });
    out.push(html + "</table>");
    table = [];
  };
  for (const line of src.split("\n")) {
    if (/^\s*\|.*\|\s*$/.test(line)) { flushLists(); table.push(line.trim()); continue; }
    flushTable();
    const h = line.match(/^(#{1,6})\s+(.*)/);
    if (h) { flushLists(); out.push(`<h${Math.min(4, h[1].length + 1)}>${inlineMd(h[2])}</h${Math.min(4, h[1].length + 1)}>`); continue; }
    if (/^\s*[-*•]\s+/.test(line)) { if (ol) { out.push("<ol>" + ol.join("") + "</ol>"); ol = null; } (ul ??= []).push("<li>" + inlineMd(line.replace(/^\s*[-*•]\s+/, "")) + "</li>"); continue; }
    if (/^\s*\d+[.)]\s+/.test(line)) { if (ul) { out.push("<ul>" + ul.join("") + "</ul>"); ul = null; } (ol ??= []).push("<li>" + inlineMd(line.replace(/^\s*\d+[.)]\s+/, "")) + "</li>"); continue; }
    if (/^\s*>\s?/.test(line)) { flushLists(); out.push("<blockquote>" + inlineMd(line.replace(/^\s*>\s?/, "")) + "</blockquote>"); continue; }
    if (/^\s*([-*_]\s*){3,}$/.test(line)) { flushLists(); out.push("<hr>"); continue; }
    if (!line.trim()) { flushLists(); continue; }
    flushLists();
    out.push("<p>" + inlineMd(line) + "</p>");
  }
  flushLists(); flushTable();
  return out.join("").replace(/\u0000(\d+)\u0000/g, (_m, i) => blocks[+i] ?? "");
}

/* ---------------- الحالة ---------------- */
const state = {
  chats: [], currentChat: null, agents: [], orch: null,
  attachments: [], streaming: false, health: null, agentHint: null, stickToBottom: true,
  autoTr: false,
  shareMode: false, selectedMsgs: new Set(),
  messages: [],
  voice: null, camStream: null,
};

/* ---------------- عناصر ---------------- */
const els = {
  chatList: $("#chatList"), messages: $("#messages"),
  input: $("#input"), sendBtn: $("#sendBtn"), micBtn: $("#micBtn"),
  attachStrip: $("#attachStrip"), trainRow: $("#trainRow"), trainChk: $("#trainChk"),
  agentBadge: $("#agentBadge"), modelBadge: $("#modelBadge"), indexBadge: $("#indexBadge"),
  chatTitle: $("#chatTitle"), chatSub: $("#chatSub"), convNav: $("#convNav"),
  shareBar: $("#shareBar"), shareCount: $("#shareCount"),
};


/* ---------------- الصحة والحالة العلوية ---------------- */
async function refreshHealth() {
  try {
    state.health = await api("/api/health");
    const h = state.health;
    const names = I18N[LANG].prov_names;
    els.modelBadge.textContent = `${names[h.provider] || h.provider} • ${h.model}`;
    els.modelBadge.classList.toggle("warn", h.provider === "offline");
    els.indexBadge.textContent = h.index.building ? (LANG === "ar" ? "🔄 فهرسة…" : "🔄 Indexing…")
      : `${h.index.chunks} ${LANG === "ar" ? "مقطع معرفة" : "knowledge chunks"}`;
    if (h.library != null) { const lc = $("#libCount"); if (lc) lc.textContent = h.library; }
    if (h.provider === "offline" && !state.offlineNotified) {
      state.offlineNotified = true;
      toast(t("offline_toast"), true);
    }
  } catch { els.modelBadge.textContent = LANG === "ar" ? "الخادم غير متصل" : "Server offline"; }
}

/* ---------------- الفريق (بطاقات) — معرّبة/معرّبة-إنجليزية من الخادم ---------------- */
function agentCardHTML(a, pickable) {
  return `<div class="card ${pickable ? "pick" : ""}" data-agent="${a.id}">
    <div class="e">${a.emoji}</div>
    <div class="n">${esc(a.name)}</div>
    <div class="r">${esc(a.role)}</div>
    <div class="d">${esc(a.description)}</div>
  </div>`;
}
async function loadAgents() {
  const d = await api(`/api/agents?lang=${LANG}`);
  state.agents = d.agents; state.orch = d.orchestrator;
  $("#agentCards").innerHTML = state.agents.map((a) => agentCardHTML(a, true)).join("");
  $$("#agentCards .card").forEach((c) => c.addEventListener("click", () => {
    state.agentHint = c.dataset.agent;
    const a = state.agents.find((x) => x.id === state.agentHint);
    els.agentBadge.textContent = `${a.emoji} ${a.name}`;
    els.input.focus();
    toast(t("t_hint_agent", { a: `${a.emoji} ${a.name}` }));
  }));
}
function agentOf(id) {
  return state.agents.find((a) => a.id === id) || state.orch
    || { id: "orchestrator", emoji: "🧭", name: t("agent_default"), role: "" };
}

/* ---------------- سجل المحادثات ---------------- */
function groupLabel(ts) {
  const d = new Date(ts * 1000), now = new Date();
  const day = 86400000;
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const that = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  if (that === today) return t("grp_today");
  if (today - that === day) return t("grp_yesterday");
  if (today - that < 7 * day) return t("grp_week");
  return d.toLocaleDateString(LANG === "ar" ? "ar-EG" : "en-GB", { month: "long", year: "numeric" });
}
function chatById(id) { return state.chats.find((c) => c.id === id) || null; }
function updateChatTitle() {
  const c = chatById(state.currentChat);
  if (els.chatTitle) els.chatTitle.textContent = c ? c.title : t("title_new_chat");
  if (els.chatSub) els.chatSub.textContent = c
    ? `${c.messages} ${LANG === "ar" ? "رسالة" : "messages"}` : t("toolbar_sub");
  const sb = $("#shareBtn");
  if (sb) sb.disabled = !state.currentChat;
}
async function loadChats(keepCurrent = true) {
  state.chats = (await api("/api/chats")).chats;
  renderChatList();
  if (!keepCurrent) setCurrentChat(null);
  if (state.currentChat && !chatById(state.currentChat)) {
    state.currentChat = null; els.messages.innerHTML = ""; showWelcome(true); renderConvNav();
  }
  updateChatTitle();
}
function renderChatList(filter = "") {
  const f = filter.trim().toLowerCase();
  const items = state.chats.filter((c) => !f || c.title.toLowerCase().includes(f));
  const pinned = items.filter((c) => c.pinned);
  const others = items.filter((c) => !c.pinned);
  let html = "";
  const itemHTML = (c) => `<div class="chat-item ${c.id === state.currentChat ? "active" : ""}" data-id="${c.id}" title="${esc(c.title)}">
      <svg class="ic ci"><use href="#i-file"/></svg>
      <span class="t">${esc(c.title)}</span>
      ${c.pinned ? `<span class="pin-mark" title="${t("pinned")}">●</span>` : ""}
      <span class="acts">
        <button data-act-pin="${c.id}" class="${c.pinned ? "pin on" : "pin"}" title="${c.pinned ? t("unpin") : t("pin")}" aria-label="${c.pinned ? t("unpin") : t("pin")}"><svg class="ic"><use href="#i-pin"/></svg></button>
        <button data-act-rename="${c.id}" title="${t("rename")}" aria-label="${t("rename")}"><svg class="ic"><use href="#i-pencil"/></svg></button>
        <button class="del" data-act-del="${c.id}" title="${t("library_delete")}" aria-label="${t("library_delete")}"><svg class="ic"><use href="#i-trash"/></svg></button>
      </span>
    </div>`;
  if (pinned.length) {
    html += `<div class="list-group pinned-group">${t("pinned")}</div>`;
    html += pinned.map(itemHTML).join("");
  }
  let lastGroup = null;
  for (const c of others) {
    const g = groupLabel(c.updated);
    if (g !== lastGroup) { html += `<div class="list-group">${g}</div>`; lastGroup = g; }
    html += itemHTML(c);
  }
  els.chatList.innerHTML = html || `<div class="list-group">${f ? t("no_results") : t("no_chats")}</div>`;
}
els.chatList.addEventListener("click", async (e) => {
  const pin = e.target.closest("[data-act-pin]");
  if (pin) {
    e.stopPropagation();
    const c = chatById(pin.dataset.actPin);
    if (!c) return;
    await api("/api/chats/" + c.id, { method: "PATCH", body: { pinned: !c.pinned } });
    toast(c.pinned ? t("toast_unpinned") : t("toast_pinned"));
    await loadChats();
    return;
  }
  const ren = e.target.closest("[data-act-rename]");
  if (ren) {
    e.stopPropagation();
    const c = chatById(ren.dataset.actRename);
    if (c) modalRename(c);
    return;
  }
  const del = e.target.closest("[data-act-del]");
  if (del) {
    e.stopPropagation();
    if (!confirm(t("chat_delete_confirm"))) return;
    await api("/api/chats/" + del.dataset.actDel, { method: "DELETE" });
    if (state.currentChat === del.dataset.actDel) {
      state.currentChat = null; els.messages.innerHTML = ""; showWelcome(true); renderConvNav();
    }
    toast(t("toast_deleted"));
    await loadChats();
    updateChatTitle();
    return;
  }
  const item = e.target.closest(".chat-item");
  if (item) openChat(item.dataset.id);
});
$("#searchChats").addEventListener("input", (e) => renderChatList(e.target.value));

function startNewChat() {
  if (state.streaming) return;
  setCurrentChat(null);
  showWelcome(true);
  closeSidebarOnMobile();
  els.input.focus();
}
$("#newChatBtn").addEventListener("click", startNewChat);
$("#newChatTop").addEventListener("click", startNewChat);

function showWelcome(show) { $("#welcome").classList.toggle("hidden", !show); }

async function setCurrentChat(id) {
  if (state.shareMode) exitShareMode();
  state.currentChat = id;
  state.agentHint = null;
  els.agentBadge.textContent = t("agent_default");
  renderChatList($("#searchChats").value);
  if (!id) { els.messages.innerHTML = ""; state.messages = []; renderConvNav(); }
  updateChatTitle();
}
async function openChat(id) {
  // تبديل المحادثة يلغي وضع التعديل القائم (يمنع حفظ تعديل في محادثة خاطئة → 404)
  if (pendingEdit && pendingEdit.chatId && String(pendingEdit.chatId) !== String(id)) {
    clearEditMode(); els.input.value = ""; autosize();
  }
  await setCurrentChat(id);
  showWelcome(false);
  closeSidebarOnMobile();
  try {
    const d = await api(`/api/chats/${id}/messages`);
    state.messages = d.messages || [];
    els.messages.innerHTML = "";
    for (const m of state.messages) {
      if (m.role === "user") addUserMsg(m.content, false, { id: m.id, attachments: m.attachments, created: m.created, edited_at: m.edited_at, status: m.status });
      else addAiMsg({ id: m.id, agent: m.agent, content: m.content, thinking: m.thinking,
                      sources: m.sources, feedback: m.feedback, attachments: m.attachments, created: m.created, status: m.status, error: m.error }, { instant: true });
    }
    if (!state.messages.length) showWelcome(true);
    scrollBottom(true);
    renderConvNav();
    updateChatTitle();
    renderConversationFeedback(chatById(id));  // شريط «هل المحادثة مفيدة؟» أسفل المحادثة
  } catch (e) {
    toast(t("err_generic") + " — " + e.message, true);
  }
}

/* ---------------- إعادة التسمية ---------------- */
function modalRename(chat) {
  const ov = modalShell(t("rename_title"), `
    <div class="field"><label>${t("share_title_label")}</label>
      <input type="text" id="renameInput" value="${esc(chat.title)}" maxlength="120" autocomplete="off"></div>
    <div class="modal-foot">
      <button class="btn primary" id="renameSave">${t("rename_save")}</button>
      <button class="btn ghost" id="renameCancel">${t("share_cancel")}</button>
    </div>`);
  const inp = $("#renameInput", ov);
  setTimeout(() => { inp.focus(); inp.select(); }, 30);
  const save = async () => {
    const title = inp.value.trim();
    if (!title) { inp.focus(); return; }
    await api("/api/chats/" + chat.id, { method: "PATCH", body: { title } });
    ov.remove(); toast(t("toast_renamed"));
    await loadChats();
    if (state.currentChat === chat.id) updateChatTitle();
  };
  $("#renameSave", ov).addEventListener("click", save);
  $("#renameCancel", ov).addEventListener("click", () => ov.remove());
  inp.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); save(); }
    if (e.key === "Escape") ov.remove();
  });
}


/* ---------------- رسائل ---------------- */
function fmtMsgTime(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(LANG === "ar" ? "ar-EG" : "en-GB", { hour: "2-digit", minute: "2-digit", year: "numeric", month: "2-digit", day: "2-digit" });
}
function isNearBottom(el, px = 140) { return el.scrollHeight - el.scrollTop - el.clientHeight < px; }
function scrollBottom(force = false) {
  const sc = $("#chatScroll");
  if (!sc) return;
  const near = isNearBottom(sc, 220);
  if (force || (near && state.stickToBottom !== false)) {
    // المسافات الطويلة جداً: قفزة فورية (التمرير الملس يُستغرق >1.5ث ويبدو معلقاً)
    const distance = sc.scrollHeight - sc.scrollTop - sc.clientHeight;
    if (distance > 1500) {
      const prev = sc.style.scrollBehavior;
      sc.style.scrollBehavior = "auto";
      sc.scrollTop = sc.scrollHeight;
      sc.style.scrollBehavior = prev;
    } else {
      sc.scrollTop = sc.scrollHeight;
    }
  }
  scheduleNavUpdate(); updateScrollBtn();
}
function updateScrollBtn() {
  const btn = $("#scrollBottomBtn"); const sc = $("#chatScroll");
  if (!btn || !sc) return;
  btn.classList.toggle("show", !isNearBottom(sc, 180));
}
function attachmentURL(att) {
  if (!att) return "";
  if (att.dataUrl) return att.dataUrl;
  if (att.library_id) return `/api/library/${encodeURIComponent(att.library_id)}/file`;
  return "";
}
function renderMsgAttachments(atts = []) {
  const items = (atts || []).filter(a => a && (a.name || a.library_id || a.dataUrl));
  if (!items.length) return "";
  return `<div class="msg-atts">${items.map((a) => {
    const url = attachmentURL(a);
    const isImg = (a.kind === "image") || /^image\//.test(a.mime || a.type || "") || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(a.name || "");
    const isAudio = (a.kind === "audio") || /^audio\//.test(a.mime || a.type || "") || /\.(mp3|wav|m4a|ogg|aac|flac)$/i.test(a.name || "");
    const isVideo = (a.kind === "video") || /^video\//.test(a.mime || a.type || "") || /\.(mp4|mov|mkv|webm|avi)$/i.test(a.name || "");
    const safeName = esc(a.name || t("attachment") || "attachment");
    if (isImg && url) {
      return `<div class="msg-att img"><img src="${esc(url)}" alt="${safeName}" loading="lazy" class="att-thumb" data-full="${esc(url)}" data-name="${safeName}">
        <div class="msg-att-bar"><span title="${safeName}">${safeName}</span><a href="${esc(url)}" download="${safeName}" class="att-dl" data-no-preview="1" title="${t("download")||"Download"}"><svg class="ic"><use href="#i-download"/></svg></a></div></div>`;
    }
    if (isVideo && url) {
      return `<div class="msg-att media"><video controls preload="metadata" src="${esc(url)}"></video>
        <div class="msg-att-bar"><span title="${safeName}">${safeName}</span><a href="${esc(url)}" download="${safeName}" class="att-dl" data-no-preview="1" title="${t("download")||"Download"}"><svg class="ic"><use href="#i-download"/></svg></a></div></div>`;
    }
    if (isAudio && url) {
      return `<div class="msg-att media"><audio controls preload="metadata" src="${esc(url)}"></audio>
        <div class="msg-att-bar"><span title="${safeName}">${safeName}</span><a href="${esc(url)}" download="${safeName}" class="att-dl" data-no-preview="1" title="${t("download")||"Download"}"><svg class="ic"><use href="#i-download"/></svg></a></div></div>`;
    }
    return `<div class="msg-att file"><div class="att-file-ic"><svg class="ic"><use href="#i-file"/></svg></div><div class="att-file-meta"><b title="${safeName}">${safeName}</b><small>${esc(a.mime||a.type||a.kind||"")}</small></div>${url?`<a href="${esc(url)}" download="${safeName}" class="att-dl" data-no-preview="1" title="${t("download")||"Download"}"><svg class="ic"><use href="#i-download"/></svg></a>`:""}</div>`;
  }).join("")}</div>`;
}
function openImagePreview(url, name="") {
  if (!url) return;
  const ov = modalShell(name || t("preview") || "Preview", `<div class="img-preview-wrap"><img src="${esc(url)}" alt="${esc(name)}" class="img-preview"></div><div class="modal-foot"><a class="btn primary" href="${esc(url)}" download="${esc(name||'image')}"><svg class="ic"><use href="#i-download"/></svg>${t("download")||"Download"}</a><button class="btn ghost" id="imgPrevClose">${t("close")||"Close"}</button></div>`);
  $("#imgPrevClose", ov)?.addEventListener("click", () => ov.remove());
}
function normalizeUserText(text) { return String(text||"").replace(/\n\s*📎.*$/s, "").trim(); }

function addUserMsg(text, animate = true, meta = {}) {
  showWelcome(false);
  const div = document.createElement("div");
  div.className = "msg user";
  // Always set data-mid from meta.id, even if it's 0 or falsy
  div.dataset.mid = meta.id != null ? String(meta.id) : "";
  div.dataset.role = "user";
  const atts = meta.attachments || [];
  const cleanText = normalizeUserText(text);
  div.innerHTML = `
    <div class="msg-check"><input type="checkbox" aria-label="${t("share")}"></div>
    <div class="msg-main">
      <div class="bubble"><div class="msg-text">${esc(cleanText)}</div>${renderMsgAttachments(atts)}</div>
      <div class="msg-meta"><span class="msg-time" data-kind="created">${fmtMsgTime(meta.created) || ""}</span>${meta.edited_at?`<span class="msg-edited">(${t("edited")||"edited"} ${fmtMsgTime(meta.edited_at)})</span>`:""}${meta.status==="error"?`<span class="msg-status err">${t("failed")||"Failed"}</span>`:""}</div>
      <div class="msg-actions">
        <button data-act="copy" title="${t("act_copy")}"><svg class="ic"><use href="#i-file"/></svg><span>${t("act_copy")}</span></button>
        <button data-act="edit" title="${t("edit")||"Edit"}" ${meta.id == null ? 'style="display:none"' : ''}><svg class="ic"><use href="#i-pencil"/></svg><span>${t("edit")||"Edit"}</span></button>
        <button data-act="retry" title="${t("retry")||"Retry"}"><svg class="ic"><use href="#i-refresh"/></svg><span>${t("retry")||"Retry"}</span></button>
        <button data-act="branch" title="${t("branch_new")}"><svg class="ic"><use href="#i-branch"/></svg><span>${t("branch")}</span></button>
        <button data-act="share-one" title="${t("share")}"><svg class="ic"><use href="#i-share"/></svg><span>${t("share")}</span></button>
      </div>
    </div>`;
  div._msgData = { text: cleanText, attachments: atts, created: meta.created, edited_at: meta.edited_at, status: meta.status || "ok" };
  div.addEventListener("click", (e) => {
    if (e.target.closest('[data-no-preview="1"]')) return;
    const img = e.target.closest('.att-thumb');
    if (img) { openImagePreview(img.dataset.full || img.src, img.dataset.name || ""); return; }
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const act = btn.dataset.act;
    if (act === "copy") navigator.clipboard.writeText(div._msgData.text || cleanText).then(() => toast(t("t_copied"))).catch(() => {});
    if (act === "edit") startEditUserMsg(div);
    if (act === "retry") retryFromMessage(div.dataset.mid, "user");
    if (act === "branch") branchFrom(div.dataset.mid);
    if (act === "share-one") enterShareMode(div.dataset.mid);
  });
  els.messages.appendChild(div);
  scrollBottom(animate);
  renderConvNav();
  return div;
}

function setFeedbackUI(holder, value) {
  const up = holder.root.querySelector('[data-act="like"]');
  const down = holder.root.querySelector('[data-act="dislike"]');
  if (up) { up.classList.toggle("on", value === "like"); up.setAttribute("aria-pressed", value === "like"); }
  if (down) { down.classList.toggle("on", value === "dislike"); down.setAttribute("aria-pressed", value === "dislike"); }
}

async function toggleFeedback(holder, value) {
  const next = holder.feedback === value ? "" : value;
  holder.feedback = next;
  setFeedbackUI(holder, next);
  toast(next ? t("feedback_saved") : t("feedback_removed"));
  if (!state.currentChat || !holder.messageId) { holder.pendingFeedback = next; return; }
  try {
    await api(`/api/chats/${state.currentChat}/messages/${holder.messageId}/feedback`,
      { method: "PATCH", body: { feedback: next } });
  } catch (e) { toast(t("toast_feedback_fail"), true); }
}

async function branchFrom(mid) {
  if (!state.currentChat) { toast(t("toast_branch_fail"), true); return; }
  try {
    const title = `${(chatById(state.currentChat)?.title || t("title_untitled"))} · ${t("title_branch")}`;
    const res = await api(`/api/chats/${state.currentChat}/branch`, {
      method: "POST", body: { message_id: mid ? Number(mid) : null, title },
    });
    await loadChats();
    await openChat(res.id);
    toast(t("branch_created"));
  } catch (e) { toast(t("toast_branch_fail") + " — " + e.message, true); }
}

function addAiMsg(data, { instant = false } = {}) {
  const a = agentOf(data.agent);
  const div = document.createElement("div");
  div.className = "msg ai";
  if (data.id != null) div.dataset.mid = String(data.id);
  div.dataset.role = "assistant";
  if (data.status) div.dataset.status = data.status;
  div.innerHTML = `
    <div class="msg-check"><input type="checkbox" aria-label="${t("share")}"></div>
    <div class="head"><div class="avatar">${a.emoji || "dY-"}</div>
      <div class="who">${esc(a.name || t("agent_default"))}<small>${a.role ? esc(a.role) : ""}</small></div></div>
    ${data.thinking ? `<details class="think"><summary>${t("think_title")}</summary><div class="tbody"></div></details>` : ""}
    <div class="body"></div>
    <div class="src-row hidden"></div>
    <div class="msg-meta"><span class="msg-time" data-kind="created">${fmtMsgTime(data.created) || ""}</span>${data.status === "error" ? `<span class="msg-status err">${t("failed")||"Failed"}</span>` : ""}</div>
    <div class="msg-actions">
      <button data-act="copy" title="${t("act_copy")}"><svg class="ic"><use href="#i-file"/></svg><span>${t("act_copy")}</span></button>
      <button data-act="speak" title="${t("act_speak")}"><svg class="ic"><use href="#i-speaker"/></svg><span>${t("act_speak")}</span></button>
      <button data-act="translate" title="${t("translate_title")}"><svg class="ic"><use href="#i-globe"/></svg><span>${LANG === "ar" ? "EN" : "AR"}</span></button>
      <button data-act="regen" title="${t("act_regen")}"><svg class="ic"><use href="#i-refresh"/></svg><span>${t("act_regen")}</span></button>
      <button data-act="retry" title="${t("retry")||"Retry"}" ${data.status !== "error" ? 'style="display:none"' : ""}><svg class="ic"><use href="#i-refresh"/></svg><span>${t("retry")||"Retry"}</span></button>
      <span class="sep"></span>
      <button data-act="like" title="${t("feedback_like")}" aria-label="${t("feedback_like")}" aria-pressed="false"><svg class="ic"><use href="#i-thumb-up"/></svg></button>
      <button data-act="dislike" class="dislike" title="${t("feedback_dislike")}" aria-label="${t("feedback_dislike")}" aria-pressed="false"><svg class="ic"><use href="#i-thumb-down"/></svg></button>
      <span class="sep"></span>
      <button data-act="share-one" title="${t("share")}"><svg class="ic"><use href="#i-share"/></svg><span>${t("share")}</span></button>
      <button data-act="branch" title="${t("branch_new")}"><svg class="ic"><use href="#i-branch"/></svg><span>${t("branch")}</span></button>
    </div>`;
  const body = $(".body", div);
  const holder = { root: div, body, srcRow: $(".src-row", div), raw: instant ? (data.content || "") : "",
                   messageId: data.id ?? null, feedback: data.feedback || "", pendingFeedback: null,
                   created: data.created || null, status: data.status || "ok", error: data.error || null };
  div.dataset.holder = "1"; div._holder = holder;
  if (instant) {
    body.innerHTML = md(data.content || "");
    if (data.thinking) { const tb = $(".tbody", div); if (tb) tb.textContent = data.thinking; }
    renderSources(holder.srcRow, data.sources || []);
    setFeedbackUI(holder, holder.feedback);
  } else {
    body.innerHTML = `<span class="typing"><i></i><i></i><i></i></span>`;
  }
  div.addEventListener("click", async (e) => {
    if (e.target.closest('[data-no-preview="1"]')) return;
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const act = btn.dataset.act;
    if (act === "copy") { await navigator.clipboard.writeText(holder.raw || body.innerText); toast(t("t_copied")); }
    if (act === "speak") speak(holder.raw || body.innerText, btn);
    if (act === "translate") await translateMsg(holder, btn);
    if (act === "regen") regenerate();
    if (act === "retry") retryFromMessage(div.dataset.mid, "assistant");
    if (act === "like") toggleFeedback(holder, "like");
    if (act === "dislike") toggleFeedback(holder, "dislike");
    if (act === "share-one") enterShareMode(div.dataset.mid);
    if (act === "branch") branchFrom(div.dataset.mid);
  });
  els.messages.appendChild(div);
  scrollBottom(true);
  scheduleNavUpdate();
  return holder;
}

function renderSources(row, sources) {
  if (!sources || !sources.length) { row.classList.add("hidden"); return; }
  row.classList.remove("hidden");
  row.innerHTML = `<span class="lbl">${t("sources")}</span>` + sources.map((s) => {
    const label = `#${s.ref || ""} ${s.title}`.trim();
    return s.url
      ? `<a class="src" href="${esc(s.url)}" target="_blank" rel="noopener" title="${esc(s.source)}">${esc(label)} 🌐</a>`
      : `<span class="src" title="${esc(s.source)}">${esc(label)}</span>`;
  }).join("");
}

/* ---------------- مشاركة المحادثة (لقطة عامة للقراءة فقط) ---------------- */
function enterShareMode(preselectId) {
  if (!state.currentChat) { toast(t("share_none"), true); return; }
  const msgs = $$(".msg", els.messages).filter((m) => m.dataset.mid);
  if (!msgs.length) { toast(t("share_none"), true); return; }
  state.shareMode = true;
  document.body.classList.add("share-mode");
  els.shareBar.hidden = false;
  msgs.forEach((el) => {
    const cb = $(".msg-check input", el);
    if (!cb) return;
    cb.checked = preselectId ? String(el.dataset.mid) === String(preselectId) : true;
    cb.onchange = updateShareBar;
  });
  updateShareBar();
  els.shareBar.scrollIntoView({ block: "nearest" });
}
function exitShareMode() {
  state.shareMode = false;
  document.body.classList.remove("share-mode");
  els.shareBar.hidden = true;
  $$(".msg-check input", els.messages).forEach((cb) => { cb.checked = false; });
}
function updateShareBar() {
  const all = $$(".msg", els.messages).filter((m) => m.dataset.mid);
  const selected = all.filter((m) => $(".msg-check input", m)?.checked);
  state.selectedMsgs = new Set(selected.map((m) => m.dataset.mid));
  els.shareCount.textContent = `${selected.length} / ${all.length}`;
  const sa = $("#shareSelectAll");
  if (sa) {
    sa.checked = all.length > 0 && selected.length === all.length;
    sa.indeterminate = selected.length > 0 && selected.length < all.length;
  }
  const create = $("#shareCreate");
  if (create) create.disabled = selected.length === 0;
}
$("#shareSelectAll")?.addEventListener("change", (e) => {
  $$(".msg", els.messages).filter((m) => m.dataset.mid).forEach((m) => {
    const cb = $(".msg-check input", m); if (cb) cb.checked = e.target.checked;
  });
  updateShareBar();
});
$("#shareCancel")?.addEventListener("click", exitShareMode);
$("#shareCreate")?.addEventListener("click", async () => {
  const ids = [...state.selectedMsgs].map((x) => Number(x)).filter((n) => !Number.isNaN(n));
  if (!ids.length) { toast(t("share_none"), true); return; }
  const btn = $("#shareCreate");
  btn.disabled = true;
  try {
    const theme = document.documentElement.dataset.theme || "dark";
    const res = await api(`/api/chats/${state.currentChat}/share`, {
      method: "POST", body: { message_ids: ids, title: chatById(state.currentChat)?.title, theme, lang: LANG },
    });
    exitShareMode();
    modalShareLink(res);
    toast(t("share_created"));
  } catch (e) {
    toast(t("toast_share_fail") + " — " + e.message, true);
    btn.disabled = false;
  }
});
$("#shareBtn")?.addEventListener("click", () => enterShareMode(null));

function modalShareLink(res) {
  const ov = modalShell(t("share_link_title"), `
    <div class="note">${t("share_link_hint")}</div>
    <div class="field"><label>${t("share")}</label>
      <input type="text" id="shareUrl" readonly value="${esc(res.url)}"></div>
    <div class="note">${t("share_public_note")} • ${t("share_messages_count", { n: res.count })}</div>
    <div class="modal-foot">
      <button class="btn primary" id="shareCopy"><svg class="ic"><use href="#i-file"/></svg>${t("share_copy")}</button>
      <a class="btn" id="shareOpen" href="${esc(res.url)}" target="_blank" rel="noopener"><svg class="ic"><use href="#i-open"/></svg>${t("share_open")}</a>
      <button class="btn ghost" id="shareRevoke">${t("share_revoke")}</button>
      <button class="btn ghost" id="shareDone">${t("share_done")}</button>
    </div>`);
  const inp = $("#shareUrl", ov);
  $("#shareCopy", ov).addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(res.url); }
    catch { inp.select(); document.execCommand("copy"); }
    toast(t("share_link_copied"));
  });
  $("#shareRevoke", ov)?.addEventListener("click", async () => {
    try {
      await api(`/api/share/${encodeURIComponent(res.id)}`, { method: "DELETE" });
      ov.remove(); toast(t("share_revoked"));
      if (state.currentChat) loadChats();
    } catch (e) { toast(t("toast_error") + " — " + e.message, true); }
  });
  $("#shareDone", ov).addEventListener("click", () => ov.remove());
  setTimeout(() => inp.select(), 40);
}

/* ---------------- شريط التنقل بين الأسئلة ---------------- */
let navRaf = null;
function scheduleNavUpdate() {
  if (navRaf) return;
  navRaf = requestAnimationFrame(() => { navRaf = null; updateNavActive(); });
}
function renderConvNav() {
  if (!els.convNav) return;
  const users = $$(".msg.user", els.messages);
  if (!users.length) { els.convNav.innerHTML = ""; els.convNav.style.display = "none"; return; }
  els.convNav.style.display = "";
  els.convNav.innerHTML = users.map((el, i) => {
    const txt = ($(".bubble", el)?.innerText || "").replace(/\s+/g, " ").trim().slice(0, 110);
    return `<button class="nav-mark" data-i="${i}" aria-label="${esc(txt)}">
      <span class="nav-tip"><b>${LANG === "ar" ? "سؤال" : "Q"} ${i + 1}</b>${esc(txt || "…")}</span>
    </button>`;
  }).join("");
  $$(".nav-mark", els.convNav).forEach((b) => b.addEventListener("click", () => {
    const el = $$(".msg.user", els.messages)[+b.dataset.i];
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      el.classList.add("flash");
      setTimeout(() => el.classList.remove("flash"), 1100);
    }
  }));
  updateNavActive();
}
function updateNavActive() {
  if (!els.convNav) return;
  const marks = $$(".nav-mark", els.convNav);
  if (!marks.length) return;
  const users = $$(".msg.user", els.messages);
  const sc = $("#chatScroll");
  const probe = sc.scrollTop + Math.min(190, sc.clientHeight * .32);
  let active = 0;
  users.forEach((el, i) => { if (el.offsetTop <= probe) active = i; });
  marks.forEach((m, i) => m.classList.toggle("active", i === active));
}
const chatScroll = $("#chatScroll");
chatScroll?.addEventListener("scroll", () => { scheduleNavUpdate(); state.stickToBottom = isNearBottom(chatScroll, 180); updateScrollBtn(); }, { passive: true });
$("#scrollBottomBtn")?.addEventListener("click", () => { state.stickToBottom = true; scrollBottom(true); });
window.addEventListener("resize", () => { renderConvNav(); });

/* Bottom horizontal rail: a single, subtle native scrollbar for the chat and
   wide tables/code blocks. It remains hidden unless real horizontal overflow exists. */
(() => {
  const rail = $("#chatHorizontalRail");
  const railInner = $(".chat-horizontal-inner", rail);
  const spacer = $("#chatHorizontalSpacer");
  if (!rail || !railInner || !spacer || !chatScroll) return;
  rail.setAttribute("aria-label", LANG === "ar" ? "تمرير المحادثة أفقياً" : "Horizontal conversation scrolling");

  let targets = [];
  let maxRange = 0;
  let syncTimer = 0;
  let syncing = false;
  let activeTarget = null;
  const lastLeft = new WeakMap();
  const rtlScrollType = (() => {
    const outer = document.createElement("div"), inner = document.createElement("div");
    outer.dir = "rtl";
    outer.style.cssText = "position:absolute;top:-1000px;width:4px;height:1px;overflow:scroll;visibility:hidden";
    inner.style.cssText = "width:8px;height:1px";
    outer.appendChild(inner); document.body.appendChild(outer);
    if (outer.scrollLeft > 0) { outer.remove(); return "default"; }
    outer.scrollLeft = 1;
    const type = outer.scrollLeft === 0 ? "negative" : "reverse";
    outer.remove(); return type;
  })();
  const horizontalTargets = () => [chatScroll, ...$$("#messages table, #messages pre, #messages .cb-pre", chatScroll)]
    .filter((el, i, all) => all.indexOf(el) === i && el.clientWidth > 0 && el.scrollWidth - el.clientWidth > 1)
    .sort((a, b) => maxFor(b) - maxFor(a));
  const primaryTarget = () => targets[0] || null;
  const isRtl = (el) => getComputedStyle(el).direction === "rtl";
  const maxFor = (el) => Math.max(0, el.scrollWidth - el.clientWidth);
  const visualLeftOffset = (el) => {
    const max = maxFor(el);
    if (!isRtl(el)) return Math.max(0, Math.min(max, el.scrollLeft));
    if (rtlScrollType === "negative") return Math.max(0, Math.min(max, max + el.scrollLeft));
    if (rtlScrollType === "default") return Math.max(0, Math.min(max, max - el.scrollLeft));
    return Math.max(0, Math.min(max, el.scrollLeft));
  };
  const setVisualLeftOffset = (el, offset) => {
    const max = maxFor(el);
    const x = Math.max(0, Math.min(max, offset));
    if (!isRtl(el)) el.scrollLeft = x;
    else if (rtlScrollType === "negative") el.scrollLeft = x - max;
    else if (rtlScrollType === "default") el.scrollLeft = max - x;
    else el.scrollLeft = x;
  };
  const refreshTargets = () => {
    targets = horizontalTargets();
    maxRange = targets.reduce((m, el) => Math.max(m, maxFor(el)), 0);
    if (!targets.includes(activeTarget)) activeTarget = primaryTarget();
    const visible = maxRange > 1;
    rail.hidden = !visible;
    if (!visible) { rail.scrollLeft = 0; return; }
    const totalWidth = Math.ceil(rail.clientWidth + maxRange);
    railInner.style.width = `${totalWidth}px`;
    spacer.style.width = `${totalWidth}px`;
    // Match the range/position of the primary target (normally the chat viewport),
    // not an arbitrary per-message region. The thumb always describes the main chat.
    const primary = primaryTarget();
    if (primary && !syncing) rail.scrollLeft = (visualLeftOffset(primary) / maxFor(primary)) * maxRange;
    targets.forEach((el) => lastLeft.set(el, el.scrollLeft));
  };
  const syncTargetsFromRail = () => {
    if (!maxRange) return;
    const el = activeTarget && targets.includes(activeTarget) ? activeTarget : primaryTarget();
    if (!el) return;
    const ratio = rail.scrollLeft / maxRange;
    syncing = true;
    // The rail maps to the active target. Keep all other wide regions at the
    // same proportional visual offset, so a track can navigate a wide table
    // even if a wider code block determines the rail's total range.
    targets.forEach((target) => {
      setVisualLeftOffset(target, ratio * maxFor(target));
      lastLeft.set(target, target.scrollLeft);
    });
    clearTimeout(syncTimer);
    syncTimer = setTimeout(() => { syncing = false; }, 90);
  };
  rail.addEventListener("scroll", syncTargetsFromRail, { passive: true });
  const onTargetScroll = (e) => {
    const el = e.currentTarget;
    const left = el.scrollLeft;
    const previous = lastLeft.get(el);
    lastLeft.set(el, left);
    if (syncing || previous === undefined || Math.abs(left - previous) < 0.5) return;
    activeTarget = el;
    const range = maxFor(el);
    if (range > 1 && maxRange > 1) {
      const ratio = visualLeftOffset(el) / range;
      rail.scrollLeft = ratio * maxRange;
      syncing = true;
      targets.forEach((target) => {
        if (target === el) return;
        setVisualLeftOffset(target, ratio * maxFor(target));
        lastLeft.set(target, target.scrollLeft);
      });
      clearTimeout(syncTimer);
      syncTimer = setTimeout(() => { syncing = false; }, 90);
    }
  };
  const bindTargets = () => {
    const next = horizontalTargets();
    for (const el of targets) if (!next.includes(el)) el.removeEventListener("scroll", onTargetScroll);
    targets = next;
    if (!activeTarget || !targets.includes(activeTarget)) activeTarget = primaryTarget();
    for (const el of targets) {
      if (!lastLeft.has(el)) lastLeft.set(el, el.scrollLeft);
      el.removeEventListener("scroll", onTargetScroll);
      el.addEventListener("scroll", onTargetScroll, { passive: true });
    }
    refreshTargets();
  };

  const resizeObserver = window.ResizeObserver ? new ResizeObserver(bindTargets) : null;
  if (resizeObserver) { resizeObserver.observe(chatScroll); resizeObserver.observe(els.messages); }
  const mutationObserver = window.MutationObserver ? new MutationObserver(bindTargets) : null;
  mutationObserver?.observe(els.messages, { childList: true, subtree: true, characterData: true });
  window.addEventListener("resize", bindTargets, { passive: true });
  bindTargets();
})();

async function translateMsg(holder, btn) {
  const raw = (holder.raw || "").trim() || holder.body.innerText.trim();
  if (!raw) { toast(t("tr_fail"), true); return; }
  const target = LANG === "ar" ? "en" : "ar";
  holder.translated ??= {};
  if (holder.translated[target]) { holder.translated[target].open = true; scrollBottom(); return; }
  const old = btn.textContent;
  btn.textContent = "⏳";
  btn.disabled = true;
  let block = holder.root.querySelector(`details.tr[data-target="${target}"]`);
  if (!block) {
    holder.srcRow.insertAdjacentHTML("beforebegin",
      `<details class="think tr" data-target="${target}"><summary>${t("tr_loading")}</summary><div class="tbody"></div></details>`);
    block = holder.root.querySelector(`details.tr[data-target="${target}"]`);
    block.open = true;
    scrollBottom();
  }
  try {
    const res = await api("/api/tools/translate", { method: "POST", body: { text: raw, target } });
    const engineLabel = res.engine === "llm" ? t("tr_engine_llm")
      : res.engine === "google" ? t("tr_engine_google") : t("tr_engine_mymemory");
    $("summary", block).textContent = `${t("tr_block")} (${target.toUpperCase()}) — ${engineLabel}`;
    $(".tbody", block).innerHTML = md(res.translated);
    holder.translated[target] = block;
  } catch (e) {
    block.remove();
    toast(t("tr_fail") + " — " + e.message, true);
  } finally {
    btn.textContent = old;
    btn.disabled = false;
    scrollBottom();
  }
}

/* ---------------- الصوت (نطق + مايك بلغة الواجهة) ---------------- */
/* ---------------- الصوت: نطق حقيقي (OpenRouter TTS) مع fallback المتصفح ---------------- */
let curAudio = null, curAudioBtn = null;
async function speak(text, btn) {
  if (curAudio) { curAudio.pause(); curAudio = null; if (curAudioBtn) curAudioBtn.textContent = t("act_speak"); curAudioBtn = null; return; }
  if (speechSynthesis.speaking) { speechSynthesis.cancel(); btn.textContent = t("act_speak"); return; }
  const clean = text.replace(/[#*`>|_\-]/g, " ").trim();
  if (!clean) return;
  if (state.health?.tts?.available) {
    btn.textContent = "⏳";
    try {
      const res = await fetch("/api/tools/tts", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: clean.slice(0, 1100) }),
      });
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.error || "HTTP " + res.status); }
      const blob = await res.blob();
      if (!blob.type.startsWith("audio")) throw new Error("bad audio");
      curAudio = new Audio(URL.createObjectURL(blob));
      curAudioBtn = btn; btn.textContent = t("act_stop");
      curAudio.onended = () => { btn.textContent = t("act_speak"); if (curAudioBtn === btn) curAudioBtn = null; };
      await curAudio.play();
      return;
    } catch (e) {
      toast(t("tts_fail") + e.message, true);
      btn.textContent = t("act_speak");
    }
  }
  const u = new SpeechSynthesisUtterance(clean.slice(0, 2500));
  const pref = LANG === "ar" ? "ar" : "en";
  const v = speechSynthesis.getVoices().find((x) => x.lang && x.lang.startsWith(pref));
  if (v) u.voice = v;
  u.lang = v ? v.lang : (LANG === "ar" ? "ar-EG" : "en-US");
  u.onend = () => (btn.textContent = t("act_speak"));
  btn.textContent = t("act_stop");
  speechSynthesis.speak(u);
}

/* ---------------- الإدخال الصوتي المباشر (تحويل فوري + عدة متحدثين) ---------------- */
let rec = null, mediaRec = null, mediaChunks = [], recStream = null;
const Voice = {
  overlay: null, running: false, paused: false, multi: false, speaker: 1,
  segments: [], interim: "", startedAt: 0, timer: null, lastFinal: 0,
  rec: null, mediaRec: null, stream: null, chunks: [], processing: false, cloud: false,
};

$("#micBtn").addEventListener("click", openVoicePanel);

function openVoicePanel() {
  if (Voice.overlay) return;
  const ov = document.createElement("div");
  ov.className = "overlay";
  ov.innerHTML = `<div class="modal voice-panel">
    <div class="modal-head"><b>${t("voice_title")}</b>
      <button class="x" id="vClose" aria-label="${t("voice_close")}"><svg class="ic"><use href="#i-x"/></svg></button></div>
    <div class="modal-body">
      <div class="voice-top">
        <div class="voice-status"><span id="vDot" class="voice-dot"></span><span id="vStatus">${t("voice_ready")}</span></div>
        <span id="vTimer" class="voice-timer">00:00</span>
        <div class="voice-modes">
          <button class="voice-mode on" data-vmode="single">${t("voice_single")}</button>
          <button class="voice-mode" data-vmode="multi">${t("voice_multi")}</button>
        </div>
      </div>
      <div class="voice-live" id="vLive"><div class="voice-empty">${t("voice_ready")} — ${t("voice_live")}</div></div>
      <div class="voice-note">${t("voice_note")}</div>
      <div class="voice-controls">
        <button class="btn primary" id="vStart"><svg class="ic"><use href="#i-mic"/></svg>${t("voice_start")}</button>
        <button class="btn ghost hidden" id="vPause"><svg class="ic"><use href="#i-pause"/></svg>${t("voice_pause")}</button>
        <button class="btn ghost hidden" id="vStop"><svg class="ic"><use href="#i-stop"/></svg>${t("voice_stop")}</button>
        <span class="grow"></span>
        <button class="btn ghost" id="vClear">${t("voice_clear")}</button>
        <button class="btn primary hidden" id="vInsert"><svg class="ic"><use href="#i-check"/></svg>${t("voice_insert")}</button>
        <button class="btn hidden" id="vSend">${t("voice_send")}</button>
      </div>
    </div>
  </div>`;
  ov.addEventListener("click", (e) => { if (e.target === ov) closeVoicePanel(); });
  $("#modalRoot").appendChild(ov);
  Voice.overlay = ov;
  $("#vClose", ov).addEventListener("click", closeVoicePanel);
  $("#vStart", ov).addEventListener("click", startVoice);
  $("#vPause", ov).addEventListener("click", toggleVoicePause);
  $("#vStop", ov).addEventListener("click", () => stopVoice(true));
  $("#vClear", ov).addEventListener("click", () => {
    Voice.segments = []; Voice.interim = ""; Voice.speaker = 1; renderVoiceLive();
    $("#vInsert", ov).classList.add("hidden"); $("#vSend", ov).classList.add("hidden");
  });
  $("#vInsert", ov).addEventListener("click", () => insertVoice(false));
  $("#vSend", ov).addEventListener("click", () => insertVoice(true));
  $$(".voice-mode", ov).forEach((b) => b.addEventListener("click", () => {
    $$(".voice-mode", ov).forEach((x) => x.classList.toggle("on", x === b));
    Voice.multi = b.dataset.vmode === "multi";
    Voice.speaker = 1;
    renderVoiceLive();
  }));
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) toast(t("voice_unsupported"), true);
}

function voiceEl(id) { return Voice.overlay ? $("#" + id, Voice.overlay) : null; }
function voiceStatus(text, live = false) {
  const s = voiceEl("vStatus"), d = voiceEl("vDot");
  if (s) s.textContent = text;
  if (d) d.classList.toggle("live", !!live);
}
function fmtClock(sec) {
  const s = Math.max(0, Math.floor(sec));
  return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
}
function voiceTick() {
  const el = voiceEl("vTimer");
  if (el) el.textContent = fmtClock((Date.now() - Voice.startedAt) / 1000);
}
function renderVoiceLive() {
  const box = voiceEl("vLive");
  if (!box) return;
  if (!Voice.segments.length && !Voice.interim) {
    box.innerHTML = `<div class="voice-empty">${Voice.running ? t("voice_listening") : t("voice_ready")} — ${t("voice_live")}</div>`;
    return;
  }
  box.innerHTML = Voice.segments.map((s, i) => `
    <div class="voice-seg">
      ${Voice.multi ? `<span class="voice-spk s${s.speaker}" data-seg="${i}" title="${t("voice_estimated")}">${t("voice_speaker")} ${s.speaker}</span>` : ""}
      <span class="vtext">${esc(s.text)}</span>
      <span class="vtime">${fmtClock(s.at || 0)}</span>
    </div>`).join("") +
    (Voice.interim ? `<div class="voice-interim">${esc(Voice.interim)}</div>` : "");
  $$(".voice-spk", box).forEach((b) => b.addEventListener("click", () => {
    const seg = Voice.segments[+b.dataset.seg];
    if (!seg) return;
    seg.speaker = seg.speaker >= 4 ? 1 : seg.speaker + 1;
    renderVoiceLive();
  }));
  box.scrollTop = box.scrollHeight;
}
function addVoiceSegment(text) {
  text = (text || "").trim();
  if (!text) return;
  const now = Date.now();
  if (Voice.multi && Voice.segments.length && now - Voice.lastFinal > 1500) {
    Voice.speaker = Voice.speaker >= 4 ? 1 : Voice.speaker + 1;
  }
  Voice.segments.push({ speaker: Voice.speaker, text, at: (now - Voice.startedAt) / 1000 });
  Voice.lastFinal = now;
  Voice.interim = "";
  renderVoiceLive();
}

function startVoice() {
  if (Voice.running) return;
  Voice.running = true;
  Voice.paused = false;
  Voice.startedAt = Date.now();
  Voice.lastFinal = 0;
  Voice.interim = "";
  Voice.processing = false;
  if (!Voice.timer) Voice.timer = setInterval(voiceTick, 500);
  voiceTick();
  voiceStatus(t("voice_listening"), true);
  $("#micBtn")?.classList.add("rec");
  voiceEl("vStart")?.classList.add("hidden");
  voiceEl("vPause")?.classList.remove("hidden");
  voiceEl("vStop")?.classList.remove("hidden");
  voiceEl("vInsert")?.classList.add("hidden");
  voiceEl("vSend")?.classList.add("hidden");
  voiceEl("vPause").innerHTML = `<svg class="ic"><use href="#i-pause"/></svg>${t("voice_pause")}`;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  // استراتيجية مزدوجة احترافية: معاينة حية من المتصفح (اختيارية) + تسجيل صوتي كامل متوازٍ
  // يُرسل عند الإيقاف إلى Whisper المتعدد اللغات — فلا تضيع كلمة مهما انقطع تعرّف المتصفح
  // أو تبدّل المتحدث بين العربية والإنجليزية والفرنسية في نفس الجملة (code-switching).
  Voice.livePreview = !!SR;
  startFullRecorder();          // دائماً: المصدر النهائي الموثوق
  if (SR) startLiveRec(SR);     // معاينة فورية فقط (تُستبدل بنص Whisper النهائي)
}

function startLiveRec(SR) {
  if (!Voice.running || Voice.paused) return;
  try {
    const r = new SR();
    r.lang = LANG === "ar" ? "ar-EG" : "en-US";
    r.interimResults = true;
    r.continuous = true;
    r.maxAlternatives = 1;
    Voice.rec = r;
    Voice.cloud = false;
    r.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) addVoiceSegment(res[0].transcript);
        else interim += res[0].transcript;
      }
      Voice.interim = interim.trim();
      renderVoiceLive();
    };
    r.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        toast(t("voice_permission"), true);
        stopVoice(false);
      }
    };
    r.onend = () => {
      if (Voice.running && !Voice.paused) {
        setTimeout(() => { if (Voice.running && !Voice.paused) startLiveRec(SR); }, 220);
      }
    };
    r.start();
  } catch {
    // بعض المتصفحات تحتاج إعادة إنشاء الكائن بعد كل جلسة
    setTimeout(() => { if (Voice.running && !Voice.paused) startLiveRec(SR); }, 350);
  }
}

async function startFullRecorder() {
  Voice.cloud = true;
  if (!window.MediaRecorder) { Voice.cloud = false; return; }  // لا MediaRecorder → نكتفي بالمعاينة الحية
  const session = (Voice.session = (Voice.session || 0) + 1);
  try {
    // قيود استوديو: قناة واحدة 48kHz مع تهدئة الصدى/الضجيج وتعويض الكسب تلقائيًا —
    // أفضل وضوح لمتحدث واحد ولقاءات متعددّي المتحدثين، وبأقل فقد ممكن قبل Whisper
    Voice.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
        sampleRate: 48000,
        sampleSize: 16,
      },
    });
  } catch { toast(t("voice_permission"), true); Voice.cloud = false; return; }
  if (session !== Voice.session || !Voice.running) {
    // أُوقف التسجيل أثناء انتظار إذن/فتح الميكروفون — لا نترك مساراً مفتوحاً.
    try { Voice.stream?.getTracks().forEach((x) => x.stop()); } catch {}
    Voice.stream = null; Voice.cloud = false; return;
  }
  // أفضل ترميز متاح (webm/opus أوسع دعم؛ وإلا mp4؛ وإلا الافتراضي)
  let mime = "";
  for (const m of ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"]) {
    if (MediaRecorder.isTypeSupported(m)) { mime = m; break; }
  }
  try {
    Voice.mediaRec = mime ? new MediaRecorder(Voice.stream, { mimeType: mime }) : new MediaRecorder(Voice.stream);
  } catch { Voice.mediaRec = new MediaRecorder(Voice.stream); mime = ""; }
  Voice.recMime = mime || (Voice.mediaRec.mimeType || "audio/webm");
  Voice.chunks = [];
  Voice.mediaRec.ondataavailable = (e) => { if (e.data && e.data.size) Voice.chunks.push(e.data); };
  Voice.mediaRec.onerror = (e) => { console.warn("MediaRecorder error", e.error || e); };
  Voice.mediaRec.onstop = async () => {
    // اقرأ النوع قبل التصفير، واجمع كل القطع بالترتيب (timeslice يضمن وصول آخر جزء)
    const type = Voice.recMime || "audio/webm";
    const chunks = Voice.chunks.slice();
    Voice.mediaRec = null;
    try { Voice.stream?.getTracks().forEach((x) => x.stop()); } catch {}
    Voice.stream = null;
    if (!Voice.finalizeFull || !chunks.length) return;
    await transcribeCloud(new Blob(chunks, { type }));
  };
  // timeslice=500ms: قطع كل نصف ثانية — أدق في استعادة آخر كلمات عند الإيقاف
  // أو الانقطاع، مع ضمان تسليم الجزء الأخير عند stop() بدون فقد
  Voice.mediaRec.start(500);
}

async function transcribeCloud(blob) {
  voiceStatus(t("voice_processing"), false);
  Voice.processing = true;
  try {
    let out = blob, ext = blob.type.includes("mp4") ? "mp4" : "webm";
    try { out = await blobToWav(blob); ext = "wav"; } catch {}
    const fd = new FormData();
    fd.append("file", out, "speech." + ext);
    fd.append("diarize", Voice.multi ? "true" : "false");
    const res = await fetch("/api/tools/stt", { method: "POST", body: fd });
    const d = await res.json().catch(() => ({}));
    if (!res.ok || d.error) {
      // فشل Whisper/Gemini → حافظ على نص المعاينة الحية إن وُجد (لا نفقد ما التقطناه)
      if (!Voice.segments.length) toast((d.error || ("HTTP " + res.status)), true);
      else voiceStatus(t("voice_partial_fallback") || "⚠️ تعذر التحويل الدقيق — استُخدم نص المعاينة", false);
    } else if (d.text) {
      // النص النهائي من Whisper (متعدد اللغات تلقائياً) هو المرجع — يحل محل معاينة المتصفح الناقصة
      const segs = (d.segments && d.segments.length) ? d.segments : [{ start: 0, end: 0, text: d.text }];
      let prevEnd = 0, spk = 1;
      Voice.segments = segs.map((s, i) => {
        if (Voice.multi && i > 0 && (s.start - prevEnd) > 1.2) spk = spk >= 4 ? 1 : spk + 1;
        prevEnd = s.end || s.start;
        return { speaker: spk, text: s.text, at: s.start || 0 };
      });
      Voice.interim = "";
      renderVoiceLive();
    } else if (!Voice.segments.length) toast(t("voice_empty"), true);
  } catch (e) {
    toast(t("mic_fail") + e.message, true);
  } finally {
    Voice.processing = false;
    finishVoice();
  }
}

function toggleVoicePause() {
  if (!Voice.running) return;
  if (!Voice.paused) {
    Voice.paused = true;
    Voice.rec?.stop();
    if (Voice.mediaRec?.state === "recording") Voice.mediaRec.pause();
    voiceStatus(t("voice_paused"), false);
    const b = voiceEl("vPause");
    if (b) b.innerHTML = `<svg class="ic"><use href="#i-play"/></svg>${t("voice_resume")}`;
  } else {
    Voice.paused = false;
    voiceStatus(t("voice_listening"), true);
    if (Voice.cloud && Voice.mediaRec?.state === "paused") Voice.mediaRec.resume();
    else if (Voice.cloud && !Voice.mediaRec) startFullRecorder();
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SR) startLiveRec(SR);
    const b = voiceEl("vPause");
    if (b) b.innerHTML = `<svg class="ic"><use href="#i-pause"/></svg>${t("voice_pause")}`;
  }
}

function stopVoice(finalize = true) {
  Voice.running = false;
  Voice.paused = false;
  Voice.finalizeFull = !!finalize;   // إيقاف = أرسل التسجيل الكامل لـ Whisper | إغلاق/إلغاء = تجاهل
  const hadActiveRecorder = !!(Voice.mediaRec && Voice.mediaRec.state !== "inactive");
  try { Voice.rec?.stop(); } catch {}
  Voice.rec = null;
  if (hadActiveRecorder) {
    try { Voice.mediaRec.requestData(); } catch {}   // إجبار تسليم آخر جزء قبل الإيقاف
    try { Voice.mediaRec.stop(); } catch {}   // onstop يُرسل للـ STT إن كان finalize
  }
  Voice.session = (Voice.session || 0) + 1;   // إلغاء أي بدء تسجيل لم يكتمل بعد
  if (Voice.timer) { clearInterval(Voice.timer); Voice.timer = null; }
  $("#micBtn")?.classList.remove("rec");
  voiceEl("vPause")?.classList.add("hidden");
  voiceEl("vStop")?.classList.add("hidden");
  if (finalize) {
    if (Voice.cloud && hadActiveRecorder) {
      // Never expose the partial live-preview transcript as final while the
      // complete recording is still on its way to Whisper. onstop/transcribeCloud
      // will call finishVoice() once the authoritative full transcript is ready.
      Voice.processing = true;
      voiceStatus(t("voice_processing") || "Processing…", false);
      voiceEl("vInsert")?.classList.add("hidden");
      voiceEl("vSend")?.classList.add("hidden");
    } else if (!Voice.processing) {
      finishVoice();
    }
  }
}

function finishVoice() {
  const has = Voice.segments.length > 0;
  voiceStatus(has ? t("voice_ready") : t("voice_empty"), false);
  voiceEl("vInsert")?.classList.toggle("hidden", !has);
  voiceEl("vSend")?.classList.toggle("hidden", !has);
  voiceEl("vStart")?.classList.toggle("hidden", has);
  renderVoiceLive();
}

function voiceTranscript() {
  if (Voice.multi) {
    return Voice.segments.map((s) => `[${t("voice_speaker")} ${s.speaker} • ${fmtClock(s.at)}] ${s.text}`).join("\n");
  }
  return Voice.segments.map((s) => s.text).join(" ");
}

function insertVoice(sendNow = false) {
  if (Voice.processing) { toast(t("voice_processing") || "Still transcribing…", true); return; }
  const txt = voiceTranscript().trim();
  if (!txt) { toast(t("voice_empty"), true); return; }
  els.input.value = (els.input.value.trim() ? els.input.value.trim() + " " : "") + txt;
  autosize();
  els.input.focus();
  closeVoicePanel();
  if (sendNow) send();
}

function closeVoicePanel() {
  stopVoice(false);
  try { Voice.stream?.getTracks().forEach((x) => x.stop()); } catch {}
  Voice.stream = null;
  Voice.overlay?.remove();
  Voice.overlay = null;
  Voice.segments = []; Voice.interim = ""; Voice.speaker = 1; Voice.cloud = false; Voice.processing = false;
  $("#micBtn")?.classList.remove("rec");
}


/* تحويل تسجيل المتصفح (webm/ogg) إلى WAV 16kHz أحادي — الصيغة المثالية لدقة التعرف */
async function blobToWav(blob) {
  const arrayBuf = await blob.arrayBuffer();
  const AC = window.AudioContext || window.webkitAudioContext;
  const ac = new AC();
  const audioBuf = await ac.decodeAudioData(arrayBuf);
  const ch0 = audioBuf.getChannelData(0);
  const ch1 = audioBuf.numberOfChannels > 1 ? audioBuf.getChannelData(1) : null;
  const srcRate = audioBuf.sampleRate, dstRate = 16000;
  const ratio = srcRate / dstRate;
  const outLen = Math.max(1, Math.floor(ch0.length / ratio));
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const pos = i * ratio, i0 = Math.floor(pos), i1 = Math.min(ch0.length - 1, i0 + 1), f = pos - i0;
    const s = ch1 ? (ch0[i0] + ch1[i0]) / 2 : ch0[i0];
    const s2 = ch1 ? (ch0[i1] + ch1[i1]) / 2 : ch0[i1];
    out[i] = s + (s2 - s) * f;
  }
  const buffer = new ArrayBuffer(44 + out.length * 2);
  const view = new DataView(buffer);
  const wstr = (o, s) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
  wstr(0, "RIFF"); view.setUint32(4, 36 + out.length * 2, true); wstr(8, "WAVE");
  wstr(12, "fmt "); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, dstRate, true); view.setUint32(28, dstRate * 2, true); view.setUint16(32, 2, true);
  view.setUint16(34, 16, true); wstr(36, "data"); view.setUint32(40, out.length * 2, true);
  let off = 44;
  for (let i = 0; i < out.length; i++) {
    const v = Math.max(-1, Math.min(1, out[i]));
    view.setInt16(off, v < 0 ? v * 0x8000 : v * 0x7FFF, true);
    off += 2;
  }
  await ac.close();
  return new Blob([buffer], { type: "audio/wav" });
}

/* ---------------- المرفقات ---------------- */
$("#attachBtn").addEventListener("click", () => $("#fileInput").click());
$("#fileInput").addEventListener("change", async (e) => {
  for (const file of e.target.files) await addAttachment(file);
  e.target.value = "";
});

/* ---------------- السحب والإفلات: أي نوع ملفات، من أي مكان في الصفحة ---------------- */
(() => {
  const ov = document.getElementById("dropOverlay");
  if (!ov) return;
  let depth = 0;
  const hasFiles = (e) => e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files");
  window.addEventListener("dragenter", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault(); depth++; ov.hidden = false;
  });
  window.addEventListener("dragover", (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
    ov.hidden = false;
  });
  window.addEventListener("dragleave", (e) => {
    if (!hasFiles(e)) return;
    depth = Math.max(0, depth - 1);
    if (!depth) ov.hidden = true;
  });
  window.addEventListener("drop", async (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault(); depth = 0; ov.hidden = true;
    const files = Array.from(e.dataTransfer.files || []);
    if (!files.length) return;
    if (!state.currentChat) startNewChat();
    for (const f of files) await addAttachment(f, { origin: "drop" });
    toast(t("drop_done", { n: files.length }));
    els.input.focus();
  });
})();
async function addAttachment(file, opts = {}) {
  const att = { name: file.name, size: file.size, type: file.type, file, text: "", dataUrl: null,
                library_id: null, kind: opts.kind || "" };
  if (file.type.startsWith("image/")) {
    att.dataUrl = await new Promise((res) => {
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.readAsDataURL(file);
    });
    // تقسيم تلقائي للصور الكبيرة — بعض البوابات ترفض طلبات الصور الضخمة
    att.dataUrl = await downscaleImage(att.dataUrl);
  }
  state.attachments.push(att);
  renderAttachments();
  try {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("train", els.trainChk.checked ? "true" : "false");
    if (state.currentChat) fd.append("chat_id", state.currentChat);
    fd.append("origin", opts.origin || "chat");
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    const d = await res.json();
    att.text = d.text || "";
    att.library_id = d.library_id || null;
    att.kind = d.kind || att.kind;
    att.mime = d.mime || att.type;
    if (d.saved_to) { toast(t("t_train_added", { n: file.name })); refreshHealth(); }
    else if (d.text_chars > 0) toast(t("t_text_ok", { n: file.name }));
    else if (d.library_id) toast(t("toast_upload_lib"));
    renderAttachments();
  } catch { toast(t("t_upload_fail"), true); }
}

async function addLibraryAttachment(item) {
  if (!item) return;
  let dataUrl = null;
  if (item.kind === "image") {
    try {
      const r = await fetch(`/api/library/${item.id}/file`);
      const blob = await r.blob();
      dataUrl = await new Promise((res) => {
        const fr = new FileReader(); fr.onload = () => res(fr.result); fr.readAsDataURL(blob);
      });
    } catch {}
  }
  state.attachments.push({
    name: item.name, size: item.size || 0, type: item.mime || "", file: null,
    text: item.text || "", dataUrl, library_id: item.id, kind: item.kind || "",
  });
  renderAttachments();
  toast(t("library_reused"));
}

function renderAttachments() {
  els.attachStrip.classList.toggle("hidden", !state.attachments.length);
  els.trainRow.classList.toggle("hidden", !state.attachments.length);
  els.attachStrip.innerHTML = state.attachments.map((a, i) => `
    <div class="att">
      ${a.dataUrl ? `<img class="thumb" src="${a.dataUrl}">` : `<span class="icon">${iconFor(a)}</span>`}
      <div class="meta"><b>${esc(a.name)}</b><small>${fmtSize(a.size)}${a.text ? " • ✓" : ""}</small></div>
      <button class="rm" data-i="${i}" title="✕">✕</button>
    </div>`).join("");
  $$(".att .rm", els.attachStrip).forEach((b) => b.addEventListener("click", () => {
    state.attachments.splice(+b.dataset.i, 1);
    renderAttachments();
  }));
}
function iconFor(a) {
  if (a.type.startsWith("audio/")) return "🎵";
  if (a.type.startsWith("video/")) return "🎬";
  const ext = (a.name.split(".").pop() || "").toLowerCase();
  return { pdf: "📕", docx: "📘", xlsx: "📊", csv: "📊", pptx: "📙", txt: "📄", md: "📄", json: "🧾" }[ext] || "📎";
}
const fmtSize = (n) => n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : (n / 1024).toFixed(0) + " KB";

/* تصغير الصور الكبيرة تلقائياً قبل الإرسال (حتى 2048px وحتى ~1.5MB بترميز base64)
   حتى لا يرفضها المزود — البوابة تقطع الاتصال فوق ذلك حجمًا (مُثبت بالاختبار) */
async function downscaleImage(dataUrl, maxSide = 2048, maxBytes = 1_500_000) {
  try {
    if (!dataUrl.startsWith("data:image/") || dataUrl.length * 0.75 <= maxBytes) return dataUrl;
    const img = new Image();
    await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = dataUrl; });
    const side = Math.max(img.naturalWidth, img.naturalHeight);
    if (side <= 0) return dataUrl;
    const scale = Math.min(1, maxSide / side);
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
    canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
    let out = canvas.toDataURL("image/webp", 0.92);
    if (out.length * 0.75 > maxBytes) out = canvas.toDataURL("image/jpeg", 0.88);
    return out.length < dataUrl.length ? out : dataUrl;
  } catch { return dataUrl; }
}

/* ---------------- الكاميرا المباشرة ---------------- */
$("#cameraBtn").addEventListener("click", openCamera);
async function openCamera() {
  let facing = "environment";
  let stream = null;
  const ov = modalShell(t("camera_title"), `
    <div class="cam-stage">
      <video id="camVideo" autoplay playsinline muted></video>
      <img id="camPreview" class="hidden" alt="preview">
      <div id="camHint" class="cam-hint">${t("camera_hint")}</div>
    </div>
    <div class="cam-actions">
      <button class="btn ghost" id="camSwitch" title="${t("camera_switch")}"><svg class="ic"><use href="#i-cam-switch"/></svg>${t("camera_switch")}</button>
      <button class="cam-shutter" id="camShoot" aria-label="${t("camera_capture")}"><span></span></button>
      <button class="btn ghost hidden" id="camRetake">${t("camera_retake")}</button>
      <button class="btn primary hidden" id="camUse"><svg class="ic"><use href="#i-check"/></svg>${t("camera_confirm")}</button>
      <button class="btn ghost" id="camCancel">${t("camera_cancel")}</button>
    </div>`, false, () => { try { stream?.getTracks().forEach((x) => x.stop()); } catch {} });

  const video = $("#camVideo", ov), preview = $("#camPreview", ov);
  const shoot = $("#camShoot", ov), retake = $("#camRetake", ov), use = $("#camUse", ov);
  let shotBlob = null, shotUrl = null;

  async function start() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: facing, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false,
      });
      video.srcObject = stream;
      video.classList.toggle("mirror", facing === "user");
      await video.play().catch(() => {});
      $("#camHint", ov).classList.remove("hidden");
    } catch (e) {
      const denied = e && (e.name === "NotAllowedError" || e.name === "SecurityError");
      toast(denied ? t("camera_denied") : t("camera_error") + " — " + (e.message || e), true);
      ov.remove();
    }
  }
  function reset() {
    if (shotUrl) { URL.revokeObjectURL(shotUrl); shotUrl = null; }
    shotBlob = null;
    preview.classList.add("hidden"); preview.removeAttribute("src");
    video.classList.remove("hidden");
    shoot.classList.remove("hidden"); retake.classList.add("hidden"); use.classList.add("hidden");
    $("#camHint", ov).classList.remove("hidden");
  }
  shoot.addEventListener("click", () => {
    if (!video.videoWidth) return;
    const c = document.createElement("canvas");
    c.width = video.videoWidth; c.height = video.videoHeight;
    c.getContext("2d").drawImage(video, 0, 0, c.width, c.height);
    c.toBlob((b) => {
      if (!b) return;
      shotBlob = b; shotUrl = URL.createObjectURL(b);
      preview.src = shotUrl;
      preview.classList.remove("hidden"); video.classList.add("hidden");
      $("#camHint", ov).classList.add("hidden");
      shoot.classList.add("hidden"); retake.classList.remove("hidden"); use.classList.remove("hidden");
    }, "image/jpeg", 0.92);
  });
  retake.addEventListener("click", reset);
  $("#camCancel", ov).addEventListener("click", () => ov.remove());
  $("#camSwitch", ov).addEventListener("click", async () => {
    facing = facing === "environment" ? "user" : "environment";
    try { stream?.getTracks().forEach((x) => x.stop()); } catch {}
    reset();
    await start();
  });
  use.addEventListener("click", async () => {
    if (!shotBlob) return;
    const file = new File([shotBlob], `camera-${Date.now()}.jpg`, { type: "image/jpeg" });
    ov.remove();
    await addAttachment(file, { origin: "camera", kind: "image" });
    toast(t("camera_captured"));
  });
  await start();
}


/* ---------------- الإرسال والبث ---------------- */
function autosize() {
  els.input.style.height = "auto";
  els.input.style.height = Math.min(190, els.input.scrollHeight) + "px";
}
els.input.addEventListener("input", autosize);
els.input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
$("#sendBtn").addEventListener("click", send);
function bindChips() {
  $$(".chip").forEach((c) => c.onclick = () => {
    els.input.value = c.textContent.replace(/[📅🧮💼🏠🔗🎯]$/u, "").trim();
    autosize(); send();
  });
}
bindChips();

let pendingEdit = null;
function clearEditMode() { pendingEdit = null; delete els.input.dataset.editing; els.sendBtn.title = t("send_title") || "Send"; }
async function startEditUserMsg(div) {
  if (state.streaming) return;
  const data = div._msgData || {};
  const mid = div.dataset.mid;
  // Validate that we have a persisted message ID and a real chat id. Editing an
  // optimistic/unsaved message used to build /api/chats/null/... and surface 404.
  if (!mid || !/^\d+$/.test(String(mid))) {
    toast(t("no_message_id") || "Cannot edit: message ID not found", true);
    return;
  }
  if (!state.currentChat) {
    toast(t("edit_failed") || "Cannot edit this message right now", true);
    return;
  }
  // اربط التعديل بمحادثته الأصلية — لو بدّل المستخدم المحادثة قبل الحفظ لا يحدث 404 خاطئ
  pendingEdit = { id: mid, chatId: state.currentChat, originalText: data.text || "", attachments: (data.attachments || []).slice() };
  els.input.value = data.text || ""; autosize(); els.input.focus();
  els.input.dataset.editing = mid;
  els.sendBtn.title = t("save_edit") || "Save edit";
  toast(t("editing_msg") || "Editing message");
}
async function retryFromMessage(mid) {
  if (state.streaming || !state.currentChat || !mid) return;
  const sel = `.msg[data-mid="${CSS.escape(String(mid))}"]`;
  const target = $(sel, els.messages);
  const btn = target?.querySelector('[data-act="retry"]');
  if (btn) btn.disabled = true;
  if (target) {
    let n = target; const toRemove = [];
    while (n) { toRemove.push(n); n = n.nextElementSibling; }
    if (target.classList.contains('ai')) toRemove.forEach(el => el.remove());
    else toRemove.slice(1).forEach(el => el.remove());
  }
  await streamChat({ retry_message_id: Number(mid), lang: LANG });
}

async function ensureChat() {
  if (state.currentChat) return state.currentChat;
  const d = await api("/api/chats", { method: "POST", body: {} });
  state.currentChat = d.id;
  renderChatList();
  updateChatTitle();
  return d.id;
}

async function send() {
  const text = els.input.value.trim();
  if (!text || state.streaming) return;
  const chatId = await ensureChat();

  if (els.input.dataset.editing && pendingEdit?.id) {
    const editChat = pendingEdit.chatId || state.currentChat;
    const originalMid = pendingEdit.id;
    const ar = LANG === "ar";
    if (!editChat || !/^\d+$/.test(String(originalMid))) {
      toast(t("edit_failed") || "Cannot edit this message right now", true);
      clearEditMode();
      return;
    }
    els.sendBtn.disabled = true;
    const patch = (mid) => api(`/api/chats/${editChat}/messages/${mid}`, {
      method: "PATCH", body: { content: text, attachments: pendingEdit.attachments }
    });
    let res = null;
    try {
      try {
        res = await patch(originalMid);
      } catch (first) {
        const msg = String(first.message || "");
        // A stale id is the real cause of the intermittent 404: the message was
        // re-saved/re-generated or the list was re-rendered from a different chat.
        // Refresh the authoritative list and match the original text before giving up.
        if (/404|not found|message_not_found/i.test(msg)) {
          const list = await api(`/api/chats/${editChat}/messages`).catch(() => null);
          const want = normalizeUserText(pendingEdit.originalText || "").trim();
          const found = (list?.messages || []).find((m) => m.role === "user" &&
            (want ? normalizeUserText(m.content || "").trim() === want : String(m.id) === String(originalMid)));
          if (found && String(found.id) !== String(originalMid)) {
            res = await patch(found.id);
          } else if (found) {
            res = await patch(found.id);
          } else {
            throw first;
          }
        } else if (/fetch|network|Failed/i.test(msg)) {
          await new Promise((r) => setTimeout(r, 600));
          res = await patch(originalMid); // safe single retry for transient network failure
        } else {
          throw first;
        }
      }
      clearEditMode();
      els.input.value = ""; autosize();
      if (state.currentChat !== editChat) { state.currentChat = editChat; renderChatList(); updateChatTitle(); }
      await openChat(editChat);
      const editAtts = res?.message?.attachments || pendingEdit.attachments || [];
      await streamChat({ chat_id: editChat, message: text, attachments: editAtts, lang: LANG, __skipUserAdd: true, skip_user_save: true });
    } catch (e) {
      const m = String(e.message || "");
      let hint = "";
      if (/404|not found|message_not_found/i.test(m)) hint = ar ? " — الرسالة لم تعد موجودة أو تغيّرت المحادثة. أعد فتح المحادثة وحاول مجدداً." : " — the message no longer exists or the chat changed. Reopen the chat and retry.";
      else if (/fetch|network|Failed/i.test(m)) hint = ar ? " — تعذر الاتصال بالخادم. تحقق من التشغيل." : " — server unreachable.";
      toast((t("edit_failed") || "Edit failed") + ": " + m + hint, true);
      clearEditMode();
      await openChat(editChat).catch(() => {});
    }
    finally { els.sendBtn.disabled = false; }
    return;
  }

  els.input.value = ""; autosize();
  const attachments = state.attachments.slice();
  state.attachments = []; renderAttachments();
  const libIds = attachments.map((a) => a.library_id).filter(Boolean);
  if (libIds.length) api("/api/library/link", { method: "POST", body: { ids: libIds, chat_id: chatId } }).catch(() => {});
  const userDiv = addUserMsg(text, true, { attachments, created: Date.now()/1000, status: "sending" });
  await streamChat({ chat_id: chatId, message: text, attachments, lang: LANG, __userDiv: userDiv });
}

async function regenerate() {
  if (state.streaming || !state.currentChat) return;
  const msgs = $$(".msg.ai").filter(m => m.dataset.mid);
  const last = msgs[msgs.length - 1];
  if (last?.dataset.mid) return retryFromMessage(last.dataset.mid);
  await streamChat({ chat_id: state.currentChat, message: "", regenerate: true, lang: LANG });
}

function finalizeStream(holder) {
  $(".typing", holder.body)?.remove();
  holder.root.querySelectorAll("details.think.live").forEach(d => { d.classList.remove("live"); d.open = false; });
  state.streaming = false; els.sendBtn.disabled = false;
  refreshHealth(); loadChats().then(()=>{ updateChatTitle(); renderConvNav(); });
  updateScrollBtn();
}

async function consumeSSE(res, holder, buf, stateRef) {
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let acc = "";
  const ensureThink = () => {
    if (!stateRef.thinkEl) {
      const bodyEl = $(".body", holder.root);
      if (bodyEl) bodyEl.insertAdjacentHTML("beforebegin", `<details class="think live" open><summary>${t("think_title")}</summary><div class="tbody"></div></details>`);
      else holder.root.insertAdjacentHTML("beforeend", `<details class="think live" open><summary>${t("think_title")}</summary><div class="tbody"></div></details>`);
      stateRef.thinkEl = $("details.think:not(.tr)", holder.root);
    }
    return $(".tbody", stateRef.thinkEl);
  };
  const handleEvent = (ev) => {
    switch (ev.type) {
      case "route": {
        const a = agentOf(ev.agents?.[0]?.id);
        const av = holder.root.querySelector(".avatar"); if (av) av.textContent = a.emoji || "dY-";
        const extra = ev.agents?.length > 1 ? ` + ${ev.agents.length - 1}` : (a.role ? esc(a.role) : "");
        const who = holder.root.querySelector(".who"); if (who) who.innerHTML = `${esc(a.name)}<small>${extra}</small>`;
        break;
      }
      case "thinking": { const tb = ensureThink(); tb.textContent += ev.delta || ""; scrollBottom(); break; }
      case "content": {
        if (stateRef.firstContent) { $(".typing", holder.body)?.remove(); stateRef.firstContent = false; if (stateRef.thinkEl) { stateRef.thinkEl.classList.remove("live"); stateRef.thinkEl.open = false; } }
        buf.push(ev.delta || "");
        if (!stateRef.ctext) { stateRef.ctext = document.createElement("div"); stateRef.ctext.className = "ai-text"; holder.body.appendChild(stateRef.ctext); }
        stateRef.ctext.innerHTML = md(buf.join(""));
        scrollBottom(); break;
      }
      case "tool": { holder.body.insertAdjacentHTML("beforeend", md(ev.markdown || "")); scrollBottom(); break; }
      case "suggest_tool": {
        const label = (ev.tools||[]).includes("gpa") ? t("btn_gpa") + " dYr" : t("btn_cv") + " dY'�";
        holder.body.insertAdjacentHTML("beforeend", `<div style="margin-top:10px"><button class="btn primary" data-tool="${(ev.tools||[])[0]}">${LANG==="ar"?"افتح ":"Open "}${label}</button></div>`);
        $$("[data-tool]", holder.body).forEach((b) => b.addEventListener("click", () => openModal(b.dataset.tool)));
        scrollBottom(); break;
      }
      case "sources": renderSources(holder.srcRow, ev.sources || []); break;
      case "error": { toast(ev.text, true); holder.status="error"; holder.error=ev.text; const rb=holder.root.querySelector('[data-act="retry"]'); if(rb) rb.style.display=''; break; }
      case "user_saved": {
        if (stateRef.userDiv && ev.message) {
          stateRef.userDiv.dataset.mid = ev.message.id;
          const tm = stateRef.userDiv.querySelector('.msg-time'); if(tm) tm.textContent = fmtMsgTime(ev.message.created);
          const st = stateRef.userDiv.querySelector('.msg-status.pending'); if(st) st.remove();
          const eb = stateRef.userDiv.querySelector('[data-act="edit"]'); if (eb) eb.style.display = '';
          if (stateRef.userDiv._msgData) { stateRef.userDiv._msgData.created = ev.message.created; stateRef.userDiv._msgData.status = "ok"; }
        } break;
      }
      case "saved": {
        holder.messageId = ev.message_id || ev.message?.id || holder.messageId;
        setTimeout(() => renderConversationFeedback(chatById(state.currentChat)), 60);
        if (holder.messageId != null) holder.root.dataset.mid = holder.messageId;
        holder.created = ev.message?.created || holder.created || Date.now()/1000;
        holder.status = ev.message?.status || "ok";
        const tm = holder.root.querySelector('.msg-time'); if (tm) tm.textContent = fmtMsgTime(holder.created);
        const rb=holder.root.querySelector('[data-act="retry"]'); if(rb) rb.style.display = holder.status === "error" ? '' : 'none';
        if (holder.status === "error") { const meta=holder.root.querySelector('.msg-meta'); if(meta && !meta.querySelector('.msg-status.err')) meta.insertAdjacentHTML('beforeend', `<span class="msg-status err">${t("failed")||"Failed"}</span>`); }
        break;
      }
      case "done": {
        const finalText = String(ev.content || "");
        const streamed = buf.join("");
        if (stateRef.thinkEl) { stateRef.thinkEl.classList.remove("live"); stateRef.thinkEl.open = false; }
        if (finalText.trim() && finalText.trim() !== streamed.trim()) {
          // الخادم يملك النسخة النهائية الموثوقة (بعد إزالة التفكير المسرّب أو إضافة وكيل ثانٍ).
          buf.length = 0; buf.push(finalText);
          holder.raw = finalText;
          if (!stateRef.ctext) { stateRef.ctext = document.createElement("div"); stateRef.ctext.className = "ai-text"; holder.body.appendChild(stateRef.ctext); }
          stateRef.ctext.innerHTML = md(finalText);
        } else {
          holder.raw = streamed || holder.raw;
        }
        holder.sources = ev.sources || []; renderSources(holder.srcRow, holder.sources); break;
      }
    }
  };
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    acc += dec.decode(value, { stream: true });
    let idx;
    while ((idx = acc.indexOf("\n\n")) >= 0) {
      const line = acc.slice(0, idx).trim(); acc = acc.slice(idx + 2);
      if (!line.startsWith("data:")) continue;
      let ev; try { ev = JSON.parse(line.slice(5)); } catch { continue; }
      handleEvent(ev);
    }
  }
}

async function streamChat(payload) {
  state.streaming = true;
  state.stickToBottom = isNearBottom($("#chatScroll"), 180);
  els.sendBtn.disabled = true;
  showWelcome(false);
  const holder = addAiMsg({ agent: state.agentHint || "orchestrator", content: "", created: Date.now()/1000, status: "streaming" });
  const buf = [];
  const stateRef = { thinkEl: null, firstContent: true, ctext: null, userDiv: payload.__userDiv || null };
  const cleanPayload = { ...payload }; delete cleanPayload.__userDiv; delete cleanPayload.__skipUserAdd;
  try {
    let res;
    if (cleanPayload.retry_message_id) {
      const mid = cleanPayload.retry_message_id;
      res = await fetch(`/api/chats/${state.currentChat}/messages/${mid}/retry`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lang: LANG }) });
    } else {
      res = await fetch("/api/chat/stream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cleanPayload) });
    }
    if (!res.ok) throw new Error("HTTP " + res.status);
    await consumeSSE(res, holder, buf, stateRef);
  } catch (e) {
    holder.status = "error"; holder.error = e.message; holder.raw = holder.raw || `⚠️ ${e.message}`;
    $(".typing", holder.body)?.remove();
    holder.body.innerHTML = md(holder.raw);
    const meta = holder.root.querySelector('.msg-meta'); if (meta) meta.innerHTML = `<span class="msg-time">${fmtMsgTime(Date.now()/1000)}</span><span class="msg-status err">${t("failed")||"Failed"}</span>`;
    const rb = holder.root.querySelector('[data-act="retry"]'); if (rb) rb.style.display = '';
    toast((t("t_conn_err")||"Connection error: ") + e.message, true);
  } finally {
    finalizeStream(holder);
  }
}

$("#reindexBtn").addEventListener("click", async () => {
  const r = await api("/api/reindex", { method: "POST", body: {} });
  toast(r.busy ? t("t_reindex_busy") : t("t_reindex_started"));
  const timer = setInterval(async () => {
    await refreshHealth();
    if (state.health && !state.health.index.building) { clearInterval(timer); toast(t("t_reindex_done")); }
  }, 2500);
  setTimeout(() => clearInterval(timer), 120000);
});

/* ---------------- الثيم واللغة ---------------- */
const themeBtn = $("#themeBtn");
function applyTheme(th) {
  document.documentElement.dataset.theme = th;
  const use = themeBtn?.querySelector("use");
  if (use) use.setAttribute("href", th === "light" ? "#i-moon" : "#i-sun");
  try { localStorage.setItem("mas-theme", th); } catch {}
}
themeBtn?.addEventListener("click", () =>
  applyTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light"));

document.addEventListener("langchange", async () => {
  await loadAgents().catch(() => {});
  renderChatList($("#searchChats").value);
  els.agentBadge.textContent = t("agent_default");
  refreshHealth();
  updateChatTitle();
  if (state.currentChat) await openChat(state.currentChat).catch(() => {});
  else renderConvNav();
  updateScrollBtn();
  bindChips();
});

/* ---------------- النوافذ ---------------- */
function openModal(kind) { ({ settings: modalSettings, agents: modalAgents, links: modalLinks, gpa: modalGPA, cv: modalCV, library: modalLibrary }[kind] || (() => {}))(); }
$$("[data-open]").forEach((b) => b.addEventListener("click", () => openModal(b.dataset.open)));
$("#searchBtn")?.addEventListener("click", modalSearch);

function modalShell(title, bodyHTML, wide = false, onClose = null) {
  const ov = document.createElement("div");
  ov.className = "overlay";
  ov.innerHTML = `<div class="modal ${wide ? "wide" : ""}">
    <div class="modal-head"><b>${title}</b><button class="x" aria-label="Close">✕</button></div>
    <div class="modal-body">${bodyHTML}</div></div>`;
  const close = () => { ov.remove(); try { onClose?.(); } catch {} };
  ov.addEventListener("click", (e) => { if (e.target === ov || e.target.closest(".x")) close(); });
  $("#modalRoot").appendChild(ov);
  return ov;
}

function parseModelKeys(raw) {
  const out = {};
  for (const line of String(raw || "").split("\n")) {
    const i = line.indexOf("=");
    if (i < 1) continue;
    const model = line.slice(0, i).trim();
    const key = line.slice(i + 1).trim();
    if (model && key && !key.startsWith("•")) out[model] = key;
  }
  return out;
}

/* ------- نافذة الإعدادات ------- */
async function modalSettings() {
  const s = await api("/api/settings");
  const h = state.health;
  const models = (h?.available_models || []).map((m) => `<option value="${esc(m)}" ${s.main_models?.ollama === m ? "selected" : ""}>${esc(m)}</option>`).join("");
  const mkLines = Object.entries(s.model_keys?.openrouter || {}).map(([k, v]) => k + "=" + v).join("\n");
  const ov = modalShell(t("m_set_title"), `
    <div class="note">${t("m_set_note")}</div>
    <div class="grid2">
      <div class="field"><label>${t("set_provider")}</label>
        <select id="sProv">
          <option value="auto" ${s.provider === "auto" ? "selected" : ""}>${t("prov_auto")}</option>
          <option value="ollama" ${s.provider === "ollama" ? "selected" : ""}>${t("prov_ollama")}</option>
          <option value="groq" ${s.provider === "groq" ? "selected" : ""}>${t("prov_groq")}</option>
          <option value="anthropic" ${s.provider === "anthropic" ? "selected" : ""}>${t("prov_ant")}</option>
          <option value="openrouter" ${s.provider === "openrouter" ? "selected" : ""}>${t("prov_or")}</option>
          <option value="gemini" ${s.provider === "gemini" ? "selected" : ""}>${t("prov_gem")}</option>
          <option value="offline" ${s.provider === "offline" ? "selected" : ""}>${t("prov_off")}</option>
        </select></div>
      <div class="field"><label>${t("set_ollama_model")}</label>
        <input type="text" id="sOllamaModel" value="${esc(s.main_models?.ollama || "llama3.1:8b")}" list="ollamaModels">
        <datalist id="ollamaModels">${models}</datalist></div>
      <div class="field"><label>${t("set_groq_key")}</label><input type="password" id="sGroq" value="${esc(s.api_keys?.groq || "")}" placeholder="gsk_..."></div>
      <div class="field"><label>${t("set_or_key")}</label><input type="password" id="sOR" value="${esc(s.api_keys?.openrouter || "")}" placeholder="sk-or-..."></div>
      <div class="field"><label>${t("set_ant_key")}</label><input type="password" id="sAnt" value="${esc(s.api_keys?.anthropic || "")}" placeholder="sk-..."></div>
      <div class="field"><label>${t("set_gem_key")}</label><input type="password" id="sGem" value="${esc(s.api_keys?.gemini || "")}" placeholder="AIza..."></div>
      <div class="field"><label>${t("set_ollama_url")}</label><input type="text" id="sOllamaUrl" value="${esc(s.ollama_url || "http://localhost:11434")}"></div>
      <div class="field"><label>${t("set_temp")}<span id="tempVal">${s.temperature ?? 0.3}</span></label>
        <input type="range" id="sTemp" min="0" max="1" step="0.05" value="${s.temperature ?? 0.3}"></div>
      <div class="field"><label>${t("set_groq_model")}</label><input type="text" id="sGroqModel" value="${esc(s.main_models?.groq || "")}" list="groqChatModels">
        <datalist id="groqChatModels"><option value="openai/gpt-oss-120b"><option value="openai/gpt-oss-20b"><option value="qwen/qwen3-32b"><option value="llama-3.3-70b-versatile"><option value="llama-3.1-8b-instant"></datalist></div>
      <div class="field"><label>${t("set_or_model")}</label><input type="text" id="sORModel" value="${esc(s.main_models?.openrouter || "")}" list="orChatModels">
        <datalist id="orChatModels"><option value="openrouter/free"><option value="google/gemma-4-26b-a4b-it:free"><option value="google/gemma-4-31b-it:free"><option value="nvidia/nemotron-3-embed-1b:free"></datalist></div>
      <div class="field"><label>${t("set_ant_model")}</label><input type="text" id="sAntModel" value="${esc(s.main_models?.anthropic || "claude-sonnet-4-6")}" list="antChatModels">
        <datalist id="antChatModels"><option value="claude-sonnet-4-6"><option value="claude-sonnet-5"><option value="claude-opus-5"><option value="claude-haiku-4-5-20251001"></datalist></div>
      <div class="field"><label>${t("set_gem_model")}</label><input type="text" id="sGemModel" value="${esc(s.main_models?.gemini || "")}"></div>
      <div class="field"><label>${t("stt_model")}</label><input type="text" id="sStt" value="${esc(s.stt?.model || "whisper-large-v3-turbo")}" list="sttModels">
        <datalist id="sttModels"><option value="whisper-large-v3-turbo"><option value="whisper-large-v3"></datalist></div>
      <div class="field"><label>${t("tts_model")}</label><input type="text" id="sTts" value="${esc(s.tts?.model || "heygen/heygen-voice-1-turbo:free")}" list="ttsModels">
        <datalist id="ttsModels"><option value="heygen/heygen-voice-1-turbo:free"><option value="fish-audio/s2.1-pro-free:free"></datalist></div>
      <div class="field"><label>${t("tts_voice")}</label><input type="text" id="sTtsVoice" value="${esc(s.tts?.voice || "nadine")}" list="voiceList">
        <datalist id="voiceList"><option value="nadine"><option value="jennifer"><option value="davis"></datalist></div>
      <div class="field"><label>${t("embed_provider")}</label>
        <select id="sEmbP">
          <option value="auto" ${(s.embed?.provider || "auto") === "auto" ? "selected" : ""}>${t("emb_auto")}</option>
          <option value="ollama" ${s.embed?.provider === "ollama" ? "selected" : ""}>${t("emb_ollama")}</option>
          <option value="openrouter" ${s.embed?.provider === "openrouter" ? "selected" : ""}>${t("emb_openrouter")}</option>
        </select></div>
      <div class="field"><label>${t("embed_model")}</label><input type="text" id="sEmbM" value="${esc(s.embed?.model || "nvidia/nemotron-3-embed-1b:free")}" list="embModels">
        <datalist id="embModels"><option value="nvidia/nemotron-3-embed-1b:free"><option value="nvidia/nemotron-3.5-embed-8b:free"><option value="liquid/lfm-2.5-embedding-350m:free"></datalist></div>
    </div>
    <div class="field"><label>${t("or_keys_title")}</label>
      <textarea id="sModelKeys" rows="4" placeholder="model-id=sk-or-...">${esc(mkLines)}</textarea>
      <div class="note">${t("or_keys_hint")}</div></div>
    <div class="field"><label>${t("fb_title")}</label>
      <label class="switch"><input type="checkbox" id="sFbEn" ${s.fallback?.enabled ? "checked" : ""}> ${t("fb_enable")}</label>
      <div class="grid2" style="margin-top:8px">
        <div class="field"><label>${t("fb_type")}</label>
          <select id="sFbProv">
            <option value="custom" ${(s.fallback?.provider || "custom") === "custom" ? "selected" : ""}>${t("fb_custom")}</option>
            <option value="openrouter" ${s.fallback?.provider === "openrouter" ? "selected" : ""}>${t("fb_openrouter")}</option>
          </select></div>
        <div class="field"><label>${t("fb_base")}</label><input type="text" id="sFbUrl" value="${esc(s.fallback?.base_url || "")}" placeholder="https://api.example.com/v1"></div>
        <div class="field"><label>${t("fb_model")}</label><input type="text" id="sFbModel" value="${esc(s.fallback?.model || "")}" placeholder="model-id"></div>
        <div class="field"><label>${t("fb_key")}</label><input type="password" id="sFbKey" value="${esc(s.fallback?.api_key || "")}" placeholder="sk-..."></div>
      </div>
      <div class="note" id="sFbMsg">${t("fb_hint")}</div>
      <button class="btn" id="sFbTest" type="button">${t("fb_test")}</button>
    </div>
    <label class="switch"><input type="checkbox" id="sDeep" ${s.deep_think ? "checked" : ""}> ${t("set_deep")}</label>
    <label class="switch"><input type="checkbox" id="sWeb" ${s.web_search ? "checked" : ""}> ${t("set_web")}</label>
    <label class="switch"><input type="checkbox" id="sAutoTr" ${s.auto_translate ? "checked" : ""}> ${t("set_auto_tr")}</label>
    <div class="note">${t("set_clear_note")}</div>
    <div class="modal-foot"><button class="btn primary" id="sSave">${t("save")}</button></div>`);
  $("#sTemp", ov).addEventListener("input", (e) => ($("#tempVal", ov).textContent = e.target.value));
  $("#sFbTest", ov).addEventListener("click", async () => {
    const btn = $("#sFbTest", ov), msg = $("#sFbMsg", ov), old = btn.textContent;
    btn.disabled = true; btn.textContent = t("fb_testing");
    try {
      await api("/api/settings", { method: "POST", body: { fallback: {
        enabled: $("#sFbEn", ov).checked,
        provider: $("#sFbProv", ov).value,
        base_url: $("#sFbUrl", ov).value.trim(),
        model: $("#sFbModel", ov).value.trim(),
        api_key: $("#sFbKey", ov).value.trim(),
      } } });
      const r = await api("/api/fallback/test", { method: "POST", body: {} });
      msg.textContent = r.ok
        ? `✅ ${r.provider} / ${r.model}: ${r.reply || "OK"}`
        : `❌ ${r.error || "failed"}`;
      msg.style.color = r.ok ? "#1a7f37" : "#c0392b";
    } catch (e) {
      msg.textContent = "❌ " + (e.message || e);
      msg.style.color = "#c0392b";
    } finally { btn.disabled = false; btn.textContent = old; }
  });
  $("#sSave", ov).addEventListener("click", async () => {
    await api("/api/settings", {
      method: "POST",
      body: {
        provider: $("#sProv", ov).value,
        ollama_url: $("#sOllamaUrl", ov).value.trim(),
        main_models: {
          ollama: $("#sOllamaModel", ov).value.trim(),
          groq: $("#sGroqModel", ov).value.trim() || undefined,
          anthropic: $("#sAntModel", ov).value.trim() || undefined,
          openrouter: $("#sORModel", ov).value.trim() || undefined,
          gemini: $("#sGemModel", ov).value.trim() || undefined,
        },
        api_keys: { groq: $("#sGroq", ov).value.trim(), openrouter: $("#sOR", ov).value.trim(), gemini: $("#sGem", ov).value.trim(), anthropic: $("#sAnt", ov).value.trim() },
        stt: { model: $("#sStt", ov).value.trim() || "whisper-large-v3-turbo" },
        tts: { model: $("#sTts", ov).value.trim() || "heygen/heygen-voice-1-turbo:free",
               voice: $("#sTtsVoice", ov).value.trim() || "nadine" },
        embed: { provider: $("#sEmbP", ov).value,
                 model: $("#sEmbM", ov).value.trim() || "nvidia/nemotron-3-embed-1b:free" },
        model_keys: { openrouter: parseModelKeys($("#sModelKeys", ov).value) },
        fallback: {
          enabled: $("#sFbEn", ov).checked,
          provider: $("#sFbProv", ov).value,
          base_url: $("#sFbUrl", ov).value.trim(),
          model: $("#sFbModel", ov).value.trim(),
          api_key: $("#sFbKey", ov).value.trim(),
        },
        temperature: parseFloat($("#sTemp", ov).value),
        deep_think: $("#sDeep", ov).checked,
        web_search: $("#sWeb", ov).checked,
        auto_translate: $("#sAutoTr", ov).checked,
      },
    });
    state.autoTr = $("#sAutoTr", ov).checked;
    ov.remove(); toast(t("t_saved")); refreshHealth();
  });
}

/* ------- نافذة الفريق ------- */
function modalAgents() {
  const ov = modalShell(t("m_agents_title"), `
    <div class="agents-grid">
      ${state.orch ? agentCardHTML(state.orch, false) : ""}
      ${state.agents.map((a) => agentCardHTML(a, true)).join("")}
    </div>
    <div class="note">${t("m_agents_note")}</div>`, true);
  $$(".card.pick", ov).forEach((c) => c.addEventListener("click", () => {
    state.agentHint = c.dataset.agent;
    const a = state.agents.find((x) => x.id === state.agentHint);
    els.agentBadge.textContent = `${a.emoji} ${a.name}`;
    ov.remove(); els.input.focus();
    toast(t("t_switch_agent", { a: a.name, e: a.emoji }));
  }));
}

/* ------- نافذة الروابط ------- */
async function modalLinks() {
  const d = await api(`/api/links?lang=${LANG}`);
  const icons = { "جروبات": "💬", "Groups": "💬", "درويفات": "📁", "Drives": "📁", "جامعة": "🏛️", "University": "🏛️", "مراجع": "🔖", "References": "🔖" };
  const groups = {};
  for (const l of d.links) (groups[l.category] ??= []).push(l);
  modalShell(t("m_links_title"), Object.entries(groups).map(([cat, items]) => `
    <div class="link-group"><h3>${icons[cat] || "🔗"} ${esc(cat)}</h3>
      ${items.map((l) => `<div class="link-item"><span>${esc(l.name)}</span>
        <a class="btn" href="${esc(l.url)}" target="_blank" rel="noopener">${t("open")}</a></div>`).join("")}
    </div>`).join(""));
}

/* ------- نافذة حاسبة GPA ------- */
function toLatinDigits(v) {
  return String(v ?? "")
    .replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)))
    .replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)));
}
const GPA_GRADES = {
  egypt5: ["ممتاز", "جيد جدا", "جيد", "مقبول", "ضعيف", "راسب"],
  standard4: ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "F"],
};
function gpaRowHTML(r = {}) {
  return `<div class="gpa-row">
    <input class="g-course" type="text" placeholder="${t("g_course_ph")}" value="${esc(r.course || "")}">
    <input class="g-hours" type="number" min="0.5" step="0.5" inputmode="decimal" placeholder="${t("g_hours_ph")}" value="${r.hours ?? ""}">
    <input class="g-grade" type="text" list="gGradeOptions" autocomplete="off" placeholder="${t("g_grade_ph")}" value="${esc(r.grade || "")}">
    <button class="btn g-del" title="✕">✕</button></div>`;
}
function modalGPA() {
  const ov = modalShell(t("m_gpa_title"), `
    <div class="field"><label>${t("g_scale")}</label>
      <select id="gScale">
        <option value="egypt5">${t("g_scale5")}</option>
        <option value="standard4">${t("g_scale4")}</option>
      </select></div>
    <div class="gpa-head">${t("g_head")}</div>
    <div id="gRows">${gpaRowHTML()}${gpaRowHTML()}${gpaRowHTML()}</div>
    <datalist id="gGradeOptions"></datalist>
    <div class="gpa-hint">${t("g_grades_hint")}</div>
    <button class="btn" id="gAdd">${t("g_add")}</button>
    <div class="grid2" style="margin-top:12px">
      <div class="field"><label>${t("g_prev")}</label><input type="number" id="gPrev" step="0.01" min="0" placeholder="${t("g_prev_ph")}"></div>
      <div class="field"><label>${t("g_prevh")}</label><input type="number" id="gPrevH" step="1" min="0" placeholder="${t("g_prevh_ph")}"></div>
    </div>
    <div id="gResult"></div>
    <div class="modal-foot">
      <button class="btn primary" id="gCalc">${t("g_calc")}</button>
      <button class="btn hidden" id="gSave">${t("g_save_chat")}</button>
    </div>`, true);
  const rowsEl = $("#gRows", ov);
  const gradeList = $("#gGradeOptions", ov);
  const scaleSel = $("#gScale", ov);
  const syncGrades = () => {
    const grades = GPA_GRADES[scaleSel.value] || [];
    gradeList.innerHTML = grades.map((g) => `<option value="${esc(g)}"></option>`).join("");
  };
  scaleSel.addEventListener("change", syncGrades);
  syncGrades();
  $("#gAdd", ov).addEventListener("click", () => rowsEl.insertAdjacentHTML("beforeend", gpaRowHTML()));
  rowsEl.addEventListener("click", (e) => { if (e.target.closest(".g-del")) e.target.closest(".gpa-row").remove(); });
  let lastMd = "";
  $("#gCalc", ov).addEventListener("click", async () => {
    const btn = $("#gCalc", ov);
    const rows = [];
    const problems = [];
    $$(".gpa-row", rowsEl).forEach((r, i) => {
      const course = $(".g-course", r).value.trim();
      const hoursRaw = $(".g-hours", r).value.trim();
      const grade = $(".g-grade", r).value.trim();
      if (!course && !hoursRaw && !grade) return;     // صف فارغ لم يلمسه المستخدم
      const label = course || `#${i + 1}`;
      if (!grade) { problems.push(`${label}: ${t("g_need_grade")}`); return; }
      const hours = parseFloat(toLatinDigits(hoursRaw));
      if (!(hours > 0)) { problems.push(`${label}: ${t("g_need_hours")}`); return; }
      rows.push({ course, hours, grade });
    });
    if (problems.length) { toast(problems.join(" • "), true); if (!rows.length) return; }
    if (!rows.length) { toast(t("t_gpa_need"), true); return; }
    const body = { rows, scale: scaleSel.value, lang: LANG };
    const pg = parseFloat(toLatinDigits($("#gPrev", ov).value)), ph = parseFloat(toLatinDigits($("#gPrevH", ov).value));
    if (!isNaN(pg)) body.previous_gpa = pg;
    if (!isNaN(ph) && ph > 0) body.previous_hours = ph;
    const oldHtml = btn.innerHTML;
    btn.disabled = true; btn.classList.add("loading");
    try {
      const res = await api("/api/tools/gpa", { method: "POST", body });
      if (res.error) { toast(res.error, true); return; }
      lastMd = res.markdown;
      $("#gResult", ov).innerHTML = `<div class="gpa-result">${md(lastMd)}</div>`;
      $("#gSave", ov).classList.remove("hidden");
    } catch (e) {
      // خطأ تحقق/شبكة: رسالة واضحة داخل النافذة بدون unhandled rejection.
      toast(e.message || t("toast_error"), true);
      $("#gResult", ov).innerHTML = `<div class="gpa-result gpa-error">${esc(e.message || t("toast_error"))}</div>`;
    } finally {
      btn.disabled = false; btn.classList.remove("loading"); btn.innerHTML = oldHtml;
    }
  });
  $("#gSave", ov).addEventListener("click", async () => {
    if (!lastMd) return;
    const cid = await ensureChat();
    const userLine = LANG === "ar" ? "🧮 احسب لي معدلي من الحاسبة" : "🧮 Calculate my GPA from the calculator";
    await api(`/api/chats/${cid}/messages`, { method: "POST", body: { role: "user", content: userLine } });
    await api(`/api/chats/${cid}/messages`, { method: "POST", body: { role: "assistant", agent: "calc", content: lastMd } });
    showWelcome(false);
    addUserMsg(userLine, false);
    addAiMsg({ agent: "calc", content: lastMd, thinking: null, sources: [] }, { instant: true });
    ov.remove();
    toast(t("t_gpa_saved"));
  });
}

/* ------- نافذة بناء CV ------- */
function modalCV() {
  const ov = modalShell(t("m_cv_title"), `
    <div class="grid2">
      <div class="field"><label>${t("c_name")}</label><input type="text" id="cName" placeholder="${t("c_name_ph")}"></div>
      <div class="field"><label>${t("c_title")}</label><input type="text" id="cTitle" placeholder="${t("c_title_ph")}"></div>
      <div class="field"><label>${t("c_email")}</label><input type="text" id="cEmail" placeholder="${t("c_email_ph")}"></div>
      <div class="field"><label>${t("c_phone")}</label><input type="text" id="cPhone" placeholder="${t("c_phone_ph")}"></div>
      <div class="field"><label>${t("c_city")}</label><input type="text" id="cCity" placeholder="${t("c_city_ph")}"></div>
      <div class="field"><label>${t("c_track")}</label>
        <select id="cTrack">
          <option value="AI">${t("track_AI")}</option>
          <option value="Cyber">${t("track_Cyber")}</option>
          <option value="Bioinformatics">${t("track_Bioinformatics")}</option>
          <option value="Web">${t("track_Web")}</option>
          <option value="Data">${t("track_Data")}</option>
          <option value="General">${t("track_General")}</option>
        </select></div>
      <div class="field"><label>${t("c_li")}</label><input type="text" id="cLi" placeholder="${t("c_li_ph")}"></div>
      <div class="field"><label>${t("c_gh")}</label><input type="text" id="cGh" placeholder="${t("c_gh_ph")}"></div>
    </div>
    <div class="field"><label>${t("c_summary")}</label>
      <textarea id="cSummary" rows="3" placeholder="${t("c_summary_ph")}"></textarea></div>
    <div class="field"><label>${t("c_edu")}</label>
      <textarea id="cEdu" rows="2" placeholder="${t("c_edu_ph")}"></textarea></div>
    <div class="field"><label>${t("c_exp")}</label>
      <textarea id="cExp" rows="3" placeholder="${t("c_exp_ph")}"></textarea></div>
    <div class="field"><label>${t("c_proj")}</label>
      <textarea id="cProj" rows="3" placeholder="${t("c_proj_ph")}"></textarea></div>
    <div class="field"><label>${t("c_skills")}</label>
      <textarea id="cSkills" rows="2" placeholder="${t("c_skills_ph")}"></textarea></div>
    <div class="grid2">
      <div class="field"><label>${t("c_langs")}</label><input type="text" id="cLangs" placeholder="${t("c_langs_ph")}"></div>
      <div class="field"><label>${t("c_courses")}</label><input type="text" id="cCourses" placeholder="${t("c_courses_ph")}"></div>
    </div>
    <div id="cvOut"></div>
    <div class="grid2">
      <div class="field"><label>${LANG === "ar" ? "🎨 لون التمييز" : "🎨 Accent"}</label>
        <select id="cAccent">
          <option value="navy">${LANG === "ar" ? "كحلي رسمي" : "Navy"}</option>
          <option value="teal">${LANG === "ar" ? "تركواز" : "Teal"}</option>
          <option value="burgundy">${LANG === "ar" ? "نبيتي" : "Burgundy"}</option>
          <option value="forest">${LANG === "ar" ? "أخضر داكن" : "Forest"}</option>
          <option value="graphite">${LANG === "ar" ? "رمادي" : "Graphite"}</option>
          <option value="royal">${LANG === "ar" ? "أزرق ملكي" : "Royal"}</option>
        </select></div>
      <div class="field"><label for="cPages">${LANG === "ar" ? "📄 عدد الصفحات" : "📄 Pages"}</label>
        <select id="cPages">
          <option value="1">${LANG === "ar" ? "صفحة واحدة" : "1 page"}</option>
          <option value="2" selected>${LANG === "ar" ? "صفحتان" : "2 pages"}</option>
          <option value="3">${LANG === "ar" ? "3 صفحات" : "3 pages"}</option>
          <option value="4">${LANG === "ar" ? "4 صفحات" : "4 pages"}</option>
          <option value="5">${LANG === "ar" ? "5 صفحات" : "5 pages"}</option>
          <option value="6">${LANG === "ar" ? "6 صفحات" : "6 pages"}</option>
          <option value="8">${LANG === "ar" ? "8 صفحات" : "8 pages"}</option>
        </select></div>
      <div class="field"><label>${LANG === "ar" ? "📐 الخط" : "📐 Density"}</label>
        <select id="cDens">
          <option value="auto" selected>${LANG === "ar" ? "تلقائي (حسب الصفحات)" : "Auto (by pages)"}</option>
          <option value="compact">${LANG === "ar" ? "مضغوط" : "Compact"}</option>
          <option value="normal">${LANG === "ar" ? "عادي" : "Normal"}</option>
          <option value="large">${LANG === "ar" ? "كبير" : "Large"}</option>
        </select></div>
      <div class="field"><label>${LANG === "ar" ? "🗂️ النمط" : "🗂️ Style"}</label>
        <select id="cStyle">
          <option value="classic">${LANG === "ar" ? "كلاسيكي ATS" : "Classic ATS"}</option>
          <option value="modern">${LANG === "ar" ? "عصري" : "Modern"}</option>
        </select></div>
      <div class="field"><label>${LANG === "ar" ? "🌐 لغة الملف" : "🌐 File language"}</label>
        <select id="cLang">
          <option value="ar" ${LANG === "ar" ? "selected" : ""}>العربية</option>
          <option value="en" ${LANG === "en" ? "selected" : ""}>English</option>
        </select></div>
    </div>
    <div class="modal-foot">
      <button class="btn primary" id="cAnalyze">${t("c_analyze")}</button>
      <button class="btn primary" id="cPdf">${LANG === "ar" ? "📄 تحميل PDF" : "📄 Download PDF"}</button>
      <button class="btn" id="cHtml">${t("c_html")}</button>
      <button class="btn" id="cDocx">${t("c_docx")}</button>
    </div>`, true);

  const readProfile = () => ({
    full_name: $("#cName", ov).value.trim(), job_title: $("#cTitle", ov).value.trim(),
    email: $("#cEmail", ov).value.trim(), phone: $("#cPhone", ov).value.trim(), city: $("#cCity", ov).value.trim(),
    linkedin: $("#cLi", ov).value.trim(), github: $("#cGh", ov).value.trim(),
    summary: $("#cSummary", ov).value.trim(),
    education: $("#cEdu", ov).value.trim().split("\n").filter(Boolean).map((l) => { const [degree, institution, year] = l.split("|").map((x) => x.trim()); return { degree, institution, year }; }),
    experience: $("#cExp", ov).value.trim().split("\n").filter(Boolean).map((l) => { const [role, company, period, bullet] = l.split("|").map((x) => x.trim()); return { role, company, period, bullets: [bullet].filter(Boolean) }; }),
    projects: $("#cProj", ov).value.trim().split("\n").filter(Boolean).map((l) => { const [name, tech, bullet] = l.split("|").map((x) => x.trim()); return { name, tech, bullets: [bullet].filter(Boolean) }; }),
    skills: $("#cSkills", ov).value.split(/[,،]/).map((x) => x.trim()).filter(Boolean),
    languages: $("#cLangs", ov).value.split(/[,،]/).map((x) => x.trim()).filter(Boolean),
    courses: $("#cCourses", ov).value.split(/[,،]/).map((x) => x.trim()).filter(Boolean),
  });

  const readTheme = () => ({ accent: $("#cAccent", ov).value, density: $("#cDens", ov).value, style: $("#cStyle", ov).value,
  pages: Number($("#cPages", ov)?.value || 2) });
  const cvLang = () => $("#cLang", ov).value;

  $("#cAnalyze", ov).addEventListener("click", async () => {
    const res = await api("/api/tools/cv/analyze", { method: "POST", body: { profile: readProfile(), track: $("#cTrack", ov).value, lang: cvLang() } });
    const checks = res.checks.map((c) => `<div class="cv-check"><span class="ic">${c.ok ? "✅" : c.partial ? "🟡" : "❌"}</span>
      <span><b>${esc(c.check)}</b> — ${esc(c.tip)}</span></div>`).join("");
    $("#cvOut", ov).innerHTML = `<div class="cv-score">
      <div style="display:flex;align-items:center;gap:14px">
        <div class="big">${res.score}<span style="font-size:16px">/100</span></div>
        <div><b>${esc(res.label)}</b><br><small style="color:var(--txt2)">${t("cv_track_note")} ${esc(res.track)}</small></div>
      </div><hr style="border-color:var(--line);margin:10px 0">${checks}
      ${res.missing_keywords.length ? `<div class="note">${t("kw_suggest")}${res.missing_keywords.map(esc).join("، ")}</div>` : ""}
    </div>`;
  });
  $("#cHtml", ov).addEventListener("click", async () => {
    const res = await api("/api/tools/cv/html", { method: "POST", body: { profile: readProfile(), lang: cvLang(), theme: readTheme() } });
    const blob = new Blob([res.html], { type: "text/html;charset=utf-8" });
    window.open(URL.createObjectURL(blob), "_blank");
    toast(t("t_cv_print"));
  });
  $("#cPdf", ov).addEventListener("click", async () => {
    const btn = $("#cPdf", ov); btn.textContent = "⏳"; btn.disabled = true;
    try {
      const res = await fetch("/api/tools/cv/pdf", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: readProfile(), lang: cvLang(), theme: readTheme() }) });
      if (res.ok) {
        const blob = await res.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob); a.download = "CV.pdf"; a.click();
        toast(LANG === "ar" ? "📄 تم تحميل CV.pdf" : "📄 CV.pdf downloaded");
      } else {
        const d = await res.json().catch(() => ({}));
        if (d.html) {
          const blob = new Blob([d.html], { type: "text/html;charset=utf-8" });
          window.open(URL.createObjectURL(blob), "_blank");
          toast(t("t_cv_print"));
        } else toast(d.error || "PDF failed", true);
      }
    } catch (e) { toast(t("t_cv_fail") + e.message, true); }
    finally { btn.textContent = LANG === "ar" ? "📄 تحميل PDF" : "📄 Download PDF"; btn.disabled = false; }
  });
  $("#cDocx", ov).addEventListener("click", async () => {
    const res = await fetch("/api/tools/cv/docx", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile: readProfile(), lang: cvLang(), theme: readTheme() }) });
    if (!res.ok) { toast(t("t_cv_fail"), true); return; }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "CV.docx"; a.click();
    toast(t("t_cv_docx"));
  });
}

/* ---------------- المكتبة الشخصية ---------------- */
let libState = { q: "", kind: "all", items: [] };
async function modalLibrary() {
  const ov = modalShell(t("library_title"), `
    <div class="lib-toolbar">
      <div class="lib-search"><svg class="ic"><use href="#i-search"/></svg>
        <input type="search" id="libSearch" placeholder="${t("library_search_ph")}" autocomplete="off"></div>
      <div class="lib-tabs">
        <button class="lib-tab on" data-kind="all">${t("library_all")}</button>
        <button class="lib-tab" data-kind="image">${t("library_images")}</button>
        <button class="lib-tab" data-kind="document">${t("library_docs")}</button>
        <button class="lib-tab" data-kind="audio">${t("library_audio")}</button>
        <button class="lib-tab" data-kind="video">${t("library_video")}</button>
      </div>
    </div>
    <div id="libGrid" class="lib-grid"><div class="lib-empty">…</div></div>`, true);
  const grid = $("#libGrid", ov);
  let timer = null;

  async function load() {
    try {
      const d = await api(`/api/library?q=${encodeURIComponent(libState.q)}&kind=${encodeURIComponent(libState.kind)}`);
      libState.items = d.items || [];
      render();
    } catch (e) { grid.innerHTML = `<div class="lib-empty">${t("err_generic")}</div>`; }
  }
  function iconOf(kind) {
    return kind === "image" ? "i-image" : kind === "audio" ? "i-speaker" : kind === "video" ? "i-camera" : "i-file";
  }
  function render() {
    if (!libState.items.length) {
      grid.innerHTML = `<div class="lib-empty">${t("library_empty")}</div>`;
      return;
    }
    grid.innerHTML = libState.items.map((it) => {
      const when = new Date(it.created * 1000).toLocaleDateString(LANG === "ar" ? "ar-EG" : "en-GB",
        { day: "2-digit", month: "short", year: "numeric" });
      const thumb = it.kind === "image"
        ? `<img src="/api/library/${it.id}/file" alt="${esc(it.name)}" loading="lazy">`
        : `<svg class="ic"><use href="#${iconOf(it.kind)}"/></svg>`;
      return `<div class="lib-card" data-lid="${it.id}">
        <div class="lib-thumb" data-lib-open="${it.id}" role="button" tabindex="0">${thumb}
          <span class="kind">${esc(it.kind || "file")}</span></div>
        <div class="lib-body">
          <b title="${esc(it.name)}">${esc(it.name)}</b>
          <small>${esc((it.mime || "").split("/").pop() || it.kind)} • ${fmtSize(it.size || 0)} • ${when}</small>
          <span class="src-chat" data-lib-chat="${it.chat_id || ""}" title="${esc(it.chat_title || t("library_unknown_source"))}">
            ${it.chat_title ? t("library_source") + " " + esc(it.chat_title) : t("library_unknown_source")}</span>
        </div>
        <div class="lib-actions">
          <button data-lib-use="${it.id}" title="${t("library_add_chat")}"><svg class="ic"><use href="#i-plus"/></svg></button>
          <button data-lib-open="${it.id}" title="${t("library_open")}"><svg class="ic"><use href="#i-open"/></svg></button>
          <a href="/api/library/${it.id}/file?download=1" title="${t("library_download")}"><button><svg class="ic"><use href="#i-download"/></svg></button></a>
          <button class="del" data-lib-del="${it.id}" title="${t("library_delete")}"><svg class="ic"><use href="#i-trash"/></svg></button>
        </div>
      </div>`;
    }).join("");
  }
  grid.addEventListener("click", async (e) => {
    const use = e.target.closest("[data-lib-use]");
    if (use) {
      const it = libState.items.find((x) => x.id === use.dataset.libUse);
      if (it) { await addLibraryAttachment(it); ov.remove(); refreshHealth(); }
      return;
    }
    const del = e.target.closest("[data-lib-del]");
    if (del) {
      if (!confirm(t("library_delete_confirm"))) return;
      await api("/api/library/" + del.dataset.libDel, { method: "DELETE" });
      toast(t("toast_lib_deleted")); refreshHealth(); load();
      return;
    }
    const open = e.target.closest("[data-lib-open]");
    if (open) {
      const it = libState.items.find((x) => x.id === open.dataset.libOpen);
      if (it) libPreview(it);
      return;
    }
    const chat = e.target.closest("[data-lib-chat]");
    if (chat && chat.dataset.libChat) {
      ov.remove(); openChat(chat.dataset.libChat);
    }
  });
  $("#libSearch", ov).addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => { libState.q = e.target.value; load(); }, 220);
  });
  $$(".lib-tab", ov).forEach((b) => b.addEventListener("click", () => {
    $$(".lib-tab", ov).forEach((x) => x.classList.toggle("on", x === b));
    libState.kind = b.dataset.kind; load();
  }));
  await load();
}

function libPreview(it) {
  let inner;
  if (it.kind === "image") inner = `<img src="/api/library/${it.id}/file" alt="${esc(it.name)}">`;
  else if ((it.mime || "").includes("pdf")) inner = `<iframe src="/api/library/${it.id}/file" title="${esc(it.name)}"></iframe>`;
  else if ((it.mime || "").startsWith("audio")) inner = `<audio controls style="width:100%;padding:16px" src="/api/library/${it.id}/file"></audio>`;
  else if ((it.mime || "").startsWith("video")) inner = `<video controls style="width:100%;max-height:58vh" src="/api/library/${it.id}/file"></video>`;
  else if (it.text) inner = `<pre>${esc(it.text.slice(0, 20000))}</pre>`;
  else inner = `<div class="lib-empty">${t("library_unknown_source")}</div>`;
  const ov = modalShell(`📄 ${esc(it.name)}`, `
    <div class="lib-preview">${inner}</div>
    <div class="modal-foot">
      <button class="btn primary" id="pvUse"><svg class="ic"><use href="#i-plus"/></svg>${t("library_add_chat")}</button>
      <a class="btn" href="/api/library/${it.id}/file?download=1"><svg class="ic"><use href="#i-download"/></svg>${t("library_download")}</a>
      <button class="btn ghost" id="pvClose">${t("share_done")}</button>
    </div>`, true);
  $("#pvUse", ov).addEventListener("click", async () => {
    await addLibraryAttachment(it); ov.remove(); refreshHealth();
    $$(".overlay").forEach((x) => x.remove());
  });
  $("#pvClose", ov).addEventListener("click", () => ov.remove());
}

/* ---------------- البحث السريع ---------------- */
function modalSearch() {
  const ov = modalShell(t("search_title"), `
    <div class="search-modal">
      <div class="search-input"><svg class="ic"><use href="#i-search"/></svg>
        <input type="search" id="quickSearch" placeholder="${t("search_ph2")}" autocomplete="off" spellcheck="false"></div>
      <div class="search-results" id="quickResults"><div class="search-empty">${t("search_hint")}</div></div>
    </div>`);
  const inp = $("#quickSearch", ov), out = $("#quickResults", ov);
  let timer = null, results = [];
  function renderResults() {
    if (!results.length) { out.innerHTML = `<div class="search-empty">${t("search_no_results")}</div>`; return; }
    out.innerHTML = results.map((c, i) => `<div class="search-item" data-i="${i}">
      <svg class="ic"><use href="#i-file"/></svg>
      <div class="st"><b>${esc(c.title)}</b><small>${esc(c.snippet || (c.messages + " " + (LANG === "ar" ? "رسالة" : "messages")))}</small></div>
      ${c.pinned ? `<span class="pin-mark">📌</span>` : ""}
    </div>`).join("");
    $$(".search-item", out).forEach((el) => el.addEventListener("click", () => {
      const c = results[+el.dataset.i]; if (c) { ov.remove(); openChat(c.id); }
    }));
  }
  inp.addEventListener("input", () => {
    clearTimeout(timer);
    const q = inp.value.trim();
    timer = setTimeout(async () => {
      if (!q) { results = state.chats.slice(0, 8); renderResults(); return; }
      try { results = (await api("/api/chats/search?q=" + encodeURIComponent(q))).results || []; }
      catch { results = []; }
      renderResults();
    }, 180);
  });
  inp.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && results[0]) { ov.remove(); openChat(results[0].id); }
  });
  setTimeout(() => inp.focus(), 40);
  results = state.chats.slice(0, 8);
  renderResults();
}

/* ---------------- الشريط الجانبي (تحكم واحد موحّد) ---------------- */
function isMobile() { return window.matchMedia("(max-width: 860px)").matches; }
function setSidebar(open) {
  const sb = $("#sidebar"), bd = $("#sidebarBackdrop"), btn = $("#sbTop");
  sb.classList.toggle("collapsed", !open);
  if (btn) btn.setAttribute("aria-expanded", String(open));
  if (bd) bd.hidden = !(open && isMobile());
  try { localStorage.setItem("mas-sidebar", open ? "open" : "collapsed"); } catch {}
}
function toggleSidebar() { setSidebar($("#sidebar").classList.contains("collapsed")); }
function closeSidebarOnMobile() { if (isMobile()) setSidebar(false); }
$("#sbTop")?.addEventListener("click", toggleSidebar);
$("#sbClose")?.addEventListener("click", () => setSidebar(false));
$("#sidebarBackdrop")?.addEventListener("click", () => setSidebar(false));
window.addEventListener("resize", () => {
  const bd = $("#sidebarBackdrop");
  if (bd) bd.hidden = !(!$("#sidebar").classList.contains("collapsed") && isMobile());
});

/* ---------------- اختصارات لوحة المفاتيح ---------------- */
document.addEventListener("keydown", (e) => {
  const overlays = $$(".overlay");
  if (e.key === "Escape") {
    if (overlays.length) { overlays[overlays.length - 1].remove(); return; }
    if (state.shareMode) { exitShareMode(); return; }
    if (isMobile() && !$("#sidebar").classList.contains("collapsed")) setSidebar(false);
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    if (!overlays.length) modalSearch();
  }
});

/* ---------------- الإقلاع ---------------- */
async function loadSettingsFlags() {
  try {
    const s = await api("/api/settings");
    state.autoTr = !!s.auto_translate;
  } catch {}
}

async function init() {
  applyTheme(localStorage.getItem("mas-theme") || "dark");
  applyI18n();
  const savedSb = localStorage.getItem("mas-sidebar");
  setSidebar(savedSb ? savedSb === "open" : !isMobile());
  await Promise.all([refreshHealth(), loadAgents(), loadChats(), loadSettingsFlags()]);
  updateChatTitle();
  renderConvNav();
  if ("speechSynthesis" in window) speechSynthesis.getVoices();
}
init().catch((e) => toast(t("t_init_err") + e.message, true));

/* ---------------- PWA: تثبيت التطبيق + Service Worker ---------------- */
let _pwaPrompt = null;
function initPWA() {
  const standalone = window.matchMedia?.("(display-mode: standalone)")?.matches || window.navigator.standalone === true;
  if ("serviceWorker" in navigator && location.protocol !== "file:" && !standalone) {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
  }
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    _pwaPrompt = e;
    if (standalone) return;
    const dismissedAt = Number(localStorage.getItem("mas-pwa-dismissed") || 0);
    if (dismissedAt && Date.now() - dismissedAt < 14 * 24 * 3600 * 1000) return;
    showPWAInstallBanner();
  });
  window.addEventListener("appinstalled", () => {
    document.getElementById("pwaBanner")?.remove();
    _pwaPrompt = null;
    toast(t("pwa_installed") || "تم تثبيت التطبيق ✅");
  });
}
function showPWAInstallBanner() {
  if (document.getElementById("pwaBanner")) return;
  const isAr = (state.lang || document.documentElement.lang || "ar").startsWith("ar");
  const b = document.createElement("div");
  b.id = "pwaBanner";
  b.className = "pwa-banner";
  b.setAttribute("role", "dialog");
  b.setAttribute("aria-live", "polite");
  b.innerHTML = `<img src="/static/assets/fav/icon-64.png" alt="" class="pwa-ico">
    <div class="pwa-txt"><b>${esc(t("pwa_title") || (isAr ? "ثبّت MAS AI على جهازك" : "Install MAS AI on your device"))}</b>
      <small>${esc(t("pwa_sub") || (isAr ? "تطبيق سريع يعمل في نافذة مستقلة — بدون متجر." : "A fast standalone app — no app store needed."))}</small></div>
    <button type="button" class="pwa-install" id="pwaInstall">${esc(t("pwa_install") || (isAr ? "تثبيت" : "Install"))}</button>
    <button type="button" class="pwa-close" id="pwaClose" aria-label="${esc(t("pwa_dismiss") || (isAr ? "إغلاق" : "Dismiss"))}">✕</button>`;
  document.body.appendChild(b);
  document.getElementById("pwaInstall")?.addEventListener("click", async () => {
    if (!_pwaPrompt) { b.remove(); return; }
    _pwaPrompt.prompt();
    try { await _pwaPrompt.userChoice; } catch {}
    _pwaPrompt = null;
    b.remove();
  });
  document.getElementById("pwaClose")?.addEventListener("click", () => {
    localStorage.setItem("mas-pwa-dismissed", String(Date.now()));
    b.remove();
  });
}
initPWA();



function renderConversationFeedback(chat) {
  const existing = document.getElementById('convFeedbackPrompt');
  if (existing) existing.remove();
  if (!chat || !state.currentChat) return;
  const fb = chat.conversation_feedback;
  const dismissed = !!chat.conversation_feedback_dismissed;
  if (fb || dismissed) return;
  const msgs = $$('.msg', els.messages).filter(m => !m.classList.contains('typing'));
  if (msgs.length < 2) return;
  const wrap = document.createElement('div');
  wrap.id = 'convFeedbackPrompt';
  wrap.className = 'conv-feedback';
  const isAr = (state.lang || document.documentElement.lang || 'ar').startsWith('ar');
  const q = t('feedback_helpful') || (isAr ? 'هل هذه المحادثة مفيدة حتى الآن؟' : 'Is this conversation helpful so far?');
  wrap.setAttribute('role', 'group');
  wrap.setAttribute('aria-label', q);
  wrap.innerHTML = `
    <div class="conv-feedback-inner">
      <span class="conv-feedback-q">${esc(q)}</span>
      <div class="conv-feedback-actions">
        <button class="conv-fb-btn like" data-v="like" type="button" title="${esc(t('feedback_like')||'Helpful')}" aria-label="${esc(t('feedback_like')||'Helpful')}">👍</button>
        <button class="conv-fb-btn dislike" data-v="dislike" type="button" title="${esc(t('feedback_dislike')||'Not helpful')}" aria-label="${esc(t('feedback_dislike')||'Not helpful')}">👎</button>
        <button class="conv-fb-btn dismiss" data-v="dismiss" type="button" title="${esc(t('feedback_dismiss')||'Dismiss')}" aria-label="${esc(t('feedback_dismiss')||'Dismiss')}">✕</button>
      </div>
    </div>`;
  let busy = false;
  wrap.querySelectorAll('[data-v]').forEach(btn => btn.addEventListener('click', async () => {
    if (busy) return;
    busy = true;
    const v = btn.dataset.v;
    const chatId = state.currentChat;
    if (!chatId) { busy = false; return; }
    try {
      const res = await api(`/api/chats/${chatId}/conversation-feedback`, {method:'POST', body:{value:v}});
      const c = chatById(chatId);
      if (c) {
        c.conversation_feedback = res.conversation_feedback ?? (v === 'dismiss' ? null : v);
        c.conversation_feedback_dismissed = !!res.conversation_feedback_dismissed || v === 'dismiss';
        c.conversation_feedback_at = res.conversation_feedback_at || Date.now() / 1000;
      }
      wrap.remove();
      if (v !== 'dismiss') toast(t('feedback_thanks') || (isAr ? 'شكرًا لملاحظاتك' : 'Thanks for your feedback'));
    } catch(e) {
      busy = false;
      toast((t('toast_error') || 'Error') + ': ' + (e.message || e), true);
    }
  }));
  els.messages.appendChild(wrap);
}
