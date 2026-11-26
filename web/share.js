"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
function fmtTime(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, { year:"numeric", month:"short", day:"2-digit", hour:"2-digit", minute:"2-digit" });
}
function inlineMd(s) {
  s = esc(s);
  s = s.replace(/`([^`]+)`/g, (_m, c) => `<code>${c}</code>`);
  s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  s = s.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
  const safeUrl = (u) => u.replace(/"/g, "%22").replace(/'/g, "%27");
  s = s.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, (_m, tt, u) => `<a href="${safeUrl(u)}" target="_blank" rel="noopener">${tt}</a>`);
  s = s.replace(/(^|[\s>])(https?:\/\/[^\s<]+)/g, (_m, p, u) => `${p}<a href="${safeUrl(u)}" target="_blank" rel="noopener">${u}</a>`);
  return s;
}
function md(src) {
  const blocks = [];
  const hl = (code, lang) => {
    const e = (s) => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
    const srcC = String(code || ""); const l = (lang||"").toLowerCase();
    if (!l || /^(text|txt|plain|plaintext|md|markdown)$/.test(l)) return e(srcC);
    const toks=[]; let i=0; const push=(c,v)=>toks.push(c?`<span class="${c}">${e(v)}</span>`:e(v));
    const kw=/^(if|else|for|while|do|switch|case|break|continue|return|try|catch|finally|throw|new|class|function|def|import|from|as|in|is|not|and|or|with|async|await|yield|lambda|pass|raise|except|True|False|None|null|undefined|true|false|const|let|var|export|default|extends|implements|interface|type|public|private|protected|static|void|int|float|double|str|string|bool|boolean|list|dict|map|set|print|echo)$/;
    while(i<srcC.length){const ch=srcC[i];
      if(ch==="/"&&srcC[i+1]==="/"){let j=i+2;while(j<srcC.length&&srcC[j]!=="\n")j++;push("tok-c",srcC.slice(i,j));i=j;continue;}
      if(ch==="/"&&srcC[i+1]==="*"){let j=i+2;while(j<srcC.length&&!(srcC[j]==="*"&&srcC[j+1]==="/"))j++;j=Math.min(srcC.length,j+2);push("tok-c",srcC.slice(i,j));i=j;continue;}
      if(ch==="#"&&!/^#([0-9a-fA-F]{3,8})\b/.test(srcC.slice(i))){let j=i+1;while(j<srcC.length&&srcC[j]!=="\n")j++;push("tok-c",srcC.slice(i,j));i=j;continue;}
      if(ch==='"'||ch==="'"||ch==="`"){const q=ch;let j=i+1,ep=false;while(j<srcC.length){const c=srcC[j];if(ep){ep=false;j++;continue;}if(c==="\\"){ep=true;j++;continue;}if(c===q){j++;break;}if(q!=="`"&&c==="\n")break;j++;}push("tok-s",srcC.slice(i,j));i=j;continue;}
      if(/[0-9]/.test(ch)&&(i===0||!/[\w$]/.test(srcC[i-1]))){let j=i;if(ch==="0"&&/[xXbBoO]/.test(srcC[j+1]||""))j+=2;while(j<srcC.length&&/[0-9a-fA-F_\.]/.test(srcC[j]))j++;push("tok-n",srcC.slice(i,j));i=j;continue;}
      if(/[A-Za-z_\u0600-\u06FF$]/.test(ch)){let j=i+1;while(j<srcC.length&&/[A-Za-z0-9_\u0600-\u06FF$]/.test(srcC[j]))j++;const w=srcC.slice(i,j);if(kw.test(w)||/^(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP|BY|ORDER|LIMIT|CREATE|TABLE|VALUES|ALTER|DROP|INDEX|INTO|SET|HAVING|DISTINCT|AS)$/.test(w))push("tok-k",w);else if(/^[A-Z][A-Za-z0-9_]*$/.test(w)&&!/^[A-Z_]+$/.test(w))push("tok-t",w);else push("",w);i=j;continue;}
      push("",ch);i++;
    } return toks.join("");
  };
  src = String(src ?? "").replace(/```([\w+-]*)\n?([\s\S]*?)```/g, (_m, lang, code) => {
    const safeLang = esc((lang || "").trim());
    const raw = code.replace(/\n$/, "");
    blocks.push(`<div class="code-block" dir="ltr"><div class="code-head"><span>${safeLang || "code"}</span><span class="code-actions"><button class="code-copy" data-copy-code title="Copy">⧉ Copy</button><button class="code-full" data-full-code title="Full screen">⛶</button></span></div><pre><code class="${safeLang ? `language-${safeLang}` : ""}">${hl(raw, lang)}</code></pre></div>`);
    return "\u0000" + (blocks.length - 1) + "\u0000";
  });
  const out = [];
  let ul = null, ol = null, table = [];
  const flushLists = () => { if (ul) { out.push("<ul>" + ul.join("") + "</ul>"); ul = null; } if (ol) { out.push("<ol>" + ol.join("") + "</ol>"); ol = null; } };
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter((r) => !/^[\s|:\-]+$/.test(r));
    const cells = (r) => r.replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => inlineMd(c.trim()));
    let html = "<div class='table-wrap'><table>";
    rows.forEach((r, ri) => { const tag = ri === 0 ? "th" : "td"; html += "<tr>" + cells(r).map((c) => `<${tag}>${c}</${tag}>`).join("") + "</tr>"; });
    out.push(html + "</table></div>"); table = [];
  };
  for (const line of src.split("\n")) {
    if (/^\s*\|.*\|\s*$/.test(line)) { flushLists(); table.push(line.trim()); continue; }
    flushTable();
    const h = line.match(/^(#{1,6})\s+(.*)/);
    if (h) { flushLists(); const lvl=Math.min(4,h[1].length+1); out.push(`<h${lvl}>${inlineMd(h[2])}</h${lvl}>`); continue; }
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
let SHARE_LANG = "ar";
const L = (ar, en) => (SHARE_LANG === "ar" ? ar : en);
function attachmentURL(a) {
  if (a.dataUrl) return a.dataUrl;
  if (a.library_id) return `/api/library/${encodeURIComponent(a.library_id)}/file`;
  return "";
}
function renderAttachments(atts=[]) {
  const items = (atts||[]).filter(a => a && (a.name || a.library_id || a.dataUrl));
  if (!items.length) return "";
  return `<div class="share-atts">${items.map(a => {
    const url = attachmentURL(a);
    const name = esc(a.name || L('مرفق', 'attachment'));
    const isImg = (a.kind==='image') || /^image\//.test(a.mime||a.type||'') || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(a.name||'');
    const isAudio = (a.kind==='audio') || /^audio\//.test(a.mime||a.type||'') || /\.(mp3|wav|m4a|ogg|webm|aac|flac)$/i.test(a.name||'');
    const isVideo = (a.kind==='video') || /^video\//.test(a.mime||a.type||'') || /\.(mp4|mov|mkv|webm|avi)$/i.test(a.name||'');
    if (isImg && url) {
      return `<figure class="share-att img"><img src="${esc(url)}" alt="${name}" loading="lazy" class="share-img" data-full="${esc(url)}"><figcaption><span>${name}</span>${url?`<a href="${esc(url)}" download="${name}">${L('تحميل', 'Download')}</a>`:''}</figcaption></figure>`;
    }
    if (isVideo && url) {
      return `<figure class="share-att media"><video controls preload="metadata" src="${esc(url)}"></video><figcaption><span>${name}</span><a href="${esc(url)}" download="${name}">${L('تحميل', 'Download')}</a></figcaption></figure>`;
    }
    if (isAudio && url) {
      return `<figure class="share-att media"><audio controls preload="metadata" src="${esc(url)}"></audio><figcaption><span>${name}</span><a href="${esc(url)}" download="${name}">${L('تحميل', 'Download')}</a></figcaption></figure>`;
    }
    if (url) return `<div class="share-att file"><span>${name}</span><a href="${esc(url)}" download="${name}">${L('تحميل', 'Download')}</a></div>`;
    return `<div class="share-att file"><span>${name}</span></div>`;
  }).join("")}</div>`;
}
function showLightbox(src, name='') {
  let lb = document.querySelector('.share-lightbox');
  if (!lb) {
    lb = document.createElement('div');
    lb.className = 'share-lightbox';
    lb.innerHTML = `<div class="share-lightbox-inner"><button class="share-lightbox-close" aria-label="Close">×</button><img alt=""><div class="share-lightbox-cap"></div></div>`;
    document.body.appendChild(lb);
    lb.addEventListener('click', (e)=>{ if (e.target === lb || e.target.closest('.share-lightbox-close')) lb.classList.remove('open'); });
    document.addEventListener('keydown', (e)=>{ if (e.key === 'Escape') lb.classList.remove('open'); });
  }
  lb.querySelector('img').src = src;
  lb.querySelector('.share-lightbox-cap').textContent = name || '';
  lb.classList.add('open');
}

async function init() {
  const sid = location.pathname.split("/").filter(Boolean).pop();
  if (!sid) { document.body.textContent = "Not found"; return; }
  try {
    const res = await fetch("/api/share/" + encodeURIComponent(sid));
    const d = await res.json();
    if (!res.ok || d.error) throw new Error(d.error || "Not found");
    SHARE_LANG = (d.lang === 'en' || d.lang === 'fr') ? 'en' : 'ar';
    const theme = (d.theme === 'light' || d.theme === 'dark') ? d.theme : 'dark';
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    document.documentElement.lang = SHARE_LANG;
    document.documentElement.dir = SHARE_LANG === 'ar' ? 'rtl' : 'ltr';
    document.body.dataset.theme = theme;
    const title = d.title || L("محادثة مشتركة", "Shared conversation");
    document.getElementById("shareTitle").textContent = title;
    const when = fmtTime(d.shared_at || d.created);
    const count = d.count || (d.messages||[]).length;
    document.getElementById("shareMeta").textContent = SHARE_LANG === 'ar' ? `${count} رسائل • ${when}` : `${count} messages • ${when}`;
    const cp = document.getElementById('copyLink'); if (cp) cp.textContent = L('نسخ الرابط', 'Copy link');
    const op = document.querySelector('.actions a'); if (op) op.textContent = L('فتح MAS AI', 'Open MAS AI');
    document.title = title + " — MAS AI Agents";
    const msgs = document.getElementById("shareMsgs");
    msgs.innerHTML = (d.messages || []).map((m) => {
      const who = m.role === "user" ? L("أنت", "You") : (m.agent || L("المساعد", "Assistant"));
      const whenStr = fmtTime(m.created);
      const edited = m.edited_at ? ` <span class="edited">(${L('عُدّلت', 'edited')} ${esc(fmtTime(m.edited_at))})</span>` : "";
      return `<article class="share-msg ${m.role === "user" ? "user" : "ai"}">
        <div class="meta"><span class="who">${esc(who)}</span><span class="time">${esc(whenStr)}${edited}</span></div>
        <div class="body md">${md(m.content || "")}</div>
        ${renderAttachments(m.attachments || [])}
        ${m.thinking ? `<details class="share-think"><summary>${L('تفكير عميق', 'Deep thinking')}</summary><div class="think-body">${esc(m.thinking)}</div></details>` : ""}
      </article>`;
    }).join("");
  } catch (e) {
    document.getElementById("shareTitle").textContent = "Link not found";
    document.getElementById("shareMsgs").innerHTML = `<div class="share-msg"><div class="body">This shared conversation is unavailable or has been removed.</div></div>`;
  }

  document.addEventListener('click', async (e) => {
    const copyBtn = e.target.closest('[data-copy-code]');
    if (copyBtn) {
      const pre = copyBtn.closest('.code-block')?.querySelector('pre') || copyBtn.closest('.code-full-card')?.querySelector('pre');
      const text = pre?.innerText || '';
      try { await navigator.clipboard.writeText(text); copyBtn.textContent=L('تم النسخ','Copied'); setTimeout(()=>copyBtn.textContent=L('نسخ','Copy'), 1200); } catch {}
      return;
    }
    const img = e.target.closest('.share-img');
    if (img) { showLightbox(img.dataset.full || img.src, img.alt || ''); return; }
    const fullBtn = e.target.closest('[data-full-code]');
    if (fullBtn) {
      const blk = fullBtn.closest('.code-block');
      const code = blk?.querySelector('pre')?.innerText || '';
      const lang = blk?.querySelector('.code-head span')?.textContent || 'code';
      let fm = document.querySelector('.code-full-modal');
      if (!fm) {
        fm = document.createElement('div'); fm.className = 'code-full-modal';
        fm.innerHTML = `<div class="code-full-card" dir="ltr"><div class="code-head"><span class="cf-lang"></span><span class="code-actions"><button class="code-copy" data-copy-code>⧉ Copy</button><button class="code-close" title="Close">✕</button></span></div><pre class="cf-pre"><code></code></pre></div>`;
        document.body.appendChild(fm);
        fm.addEventListener('click', (ev) => { if (ev.target === fm || ev.target.closest('.code-close')) fm.classList.remove('open'); });
        document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') fm.classList.remove('open'); });
      }
      fm.querySelector('.cf-lang').textContent = lang;
      fm.querySelector('pre code').textContent = code;
      fm.classList.add('open');
      return;
    }
  });

  const copyLink = document.getElementById("copyLink");
  copyLink?.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href); }
    catch { const i = document.createElement("input"); i.value = location.href; document.body.appendChild(i); i.select(); document.execCommand("copy"); i.remove(); }
    copyLink.textContent = "Copied ✓";
    setTimeout(() => (copyLink.textContent = L('نسخ الرابط', 'Copy link')), 1800);
  });
}
init();
