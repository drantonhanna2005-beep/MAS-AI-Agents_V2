"""خادم موقع فريق الوكلاء — نقطة تشغيل واحدة:  python app.py

شغّل ثم افتح: http://localhost:8765
"""
from __future__ import annotations

import json
import re
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))  # ضمان استيراد core/ وagents/ على أي إعداد بايثون

try:  # ترميز عربي سليم في كونسول ويندوز
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from core import cvgen, extract, feedback, gpatool, history, knowledge, rag, university_ingest
from core.config import (DATA_DIR, ROOT, UPLOAD_DIR, load_config, resolve_provider,
                         save_config, get_fallback)
from agents.orchestrator import run_stream
from agents.registry import AGENTS, ORCHESTRATOR

WEB_DIR = ROOT / "web"
app = FastAPI(title="University AI MAS — فريق الوكلاء الأكاديمي", version="1.0.0")

# ---------------------------------------------------------------- تشخيص منظم
# سجل مختصر لكل طلب API: معرّف ارتباط + المسار + الحالة + الزمن.
# لا نسجّل الأجسام أو المفاتيح أو محتوى المستخدم إطلاقاً.
import logging
import uuid as _uuid

_log = logging.getLogger("mas")
if not _log.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(logging.INFO)


@app.middleware("http")
async def _request_logger(request: Request, call_next):
    rid = _uuid.uuid4().hex[:12]
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001 — نُعيد الخطأ بعد تسجيله مع معرّف الارتباط
        ms = (time.perf_counter() - started) * 1000
        _log.error("rid=%s %s %s -> 500 (%.0fms) %s",
                   rid, request.method, request.url.path, ms, type(exc).__name__)
        raise
    ms = (time.perf_counter() - started) * 1000
    path = request.url.path
    if path.startswith("/api/") or path.startswith("/share/"):
        _log.info("rid=%s %s %s -> %s (%.0fms)",
                  rid, request.method, path, response.status_code, ms)
    response.headers["X-Request-ID"] = rid
    return response

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-store, max-age=0"})


@app.get("/sw.js")
def service_worker():
    """Service worker at the site root so its scope covers the whole app."""
    resp = FileResponse(WEB_DIR / "sw.js", media_type="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@app.get("/share/{sid}")
def shared_page(sid: str):
    """صفحة عامة للقراءة فقط — لا تحتوي أي مفاتيح أو أدوات تحكم."""
    resp = FileResponse(WEB_DIR / "share.html")
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------- الحالة العامة
_semantic_fill_started = False


@app.get("/api/health")
def health():
    global _semantic_fill_started
    cfg = load_config()
    prov = resolve_provider(cfg)
    from core.config import get_model_key
    stt_model = (cfg.get("stt") or {}).get("model") or "whisper-large-v3-turbo"
    tts_model = (cfg.get("tts") or {}).get("model") or "heygen/heygen-voice-1-turbo:free"
    result = {
        "ok": True,
        "provider": prov["provider"],
        "model": prov["model"],
        "available_models": prov.get("available_models", []),
        "ollama": {"up": bool(prov.get("available_models")), "url": cfg.get("ollama_url")},
        "index": rag.stats(),
        "deep_think": bool(cfg.get("deep_think")),
        "web_search": bool(cfg.get("web_search")),
        "stt": {"available": bool(get_model_key("groq", stt_model, cfg) or cfg.get("api_keys", {}).get("gemini")),
                "model": stt_model},
        "tts": {"available": bool(get_model_key("openrouter", tts_model, cfg)), "model": tts_model,
                "voice": (cfg.get("tts") or {}).get("voice") or "nadine"},
        "embed": rag._embed_engine()[0],
        "library": history.library_count(),
    }
    fb = cfg.get("fallback") or {}
    result["fallback"] = {
        "enabled": bool(fb.get("enabled")),
        "configured": get_fallback(cfg) is not None,
        "provider": fb.get("provider") or "custom",
        "model": fb.get("model") or "",
        "base_url": fb.get("base_url") or "",
    }
    # شفاء ذاتي: فهرس بدون vectors + محرك متاح → احسب الدلالي في الخلفية مرة واحدة لكل تشغيل
    try:
        idx = result["index"]
        if (not idx["semantic"] and not idx["building"] and idx["chunks"]
                and rag._embed_engine()[0] != "none" and not _semantic_fill_started):
            _semantic_fill_started = True
            threading.Thread(target=rag.fill_embeddings, daemon=True).start()
    except Exception:
        pass
    return result


@app.get("/api/agents")
def agents(lang: str = "ar"):
    from agents.registry import localized, ORCHESTRATOR as ORCH
    orc = localized(ORCH, lang)
    return {"orchestrator": orc, "agents": [localized(a, lang) for a in AGENTS]}


@app.get("/api/links")
def links(lang: str = "ar"):
    if (lang or "ar")[:2] == "en":
        out = [{**l, "name": l.get("name_en") or l["name"], "category": l.get("category_en") or l["category"]}
               for l in knowledge.ALL_LINKS]
        return {"links": out}
    return {"links": knowledge.ALL_LINKS}


# ---------------------------------------------------------------- الإعدادات
@app.get("/api/settings")
def get_settings():
    cfg = load_config()
    masked = {**cfg, "api_keys": {k: ("•" * 8 if v else "") for k, v in cfg.get("api_keys", {}).items()}}
    if isinstance(masked.get("fallback"), dict):
        masked["fallback"] = {**masked["fallback"],
                              "api_key": ("•" * 8 if masked["fallback"].get("api_key") else "")}
    return masked


@app.post("/api/settings")
def set_settings(body: dict):
    cfg = load_config()
    for key in ("provider", "temperature", "deep_think", "web_search", "rag_k", "ollama_url",
                "main_models", "router_models", "embed_model", "max_agents", "auto_translate",
                "model_keys", "stt", "tts", "embed"):
        if key in body and body[key] is not None:
            cfg[key] = body[key]
    if isinstance(body.get("api_keys"), dict):
        for k, v in body["api_keys"].items():
            if v == "__clear__":
                cfg["api_keys"][k] = ""  # حذف صريح للمفتاح
            elif v and set(v) != {"•"}:  # لا نستبدل مفتاحاً محفوظاً بنقاط القناع
                cfg["api_keys"][k] = v.strip()
    if isinstance(body.get("fallback"), dict):
        fb = {**(cfg.get("fallback") or {})}
        for k in ("enabled", "provider", "base_url", "model"):
            if k in body["fallback"]:
                fb[k] = body["fallback"][k]
        fk = body["fallback"].get("api_key")
        if fk == "__clear__":
            fb["api_key"] = ""
        elif fk and set(fk) != {"•"}:
            fb["api_key"] = fk.strip()
        cfg["fallback"] = fb
    save_config(cfg)
    return health()


@app.post("/api/fallback/test")
def test_fallback():
    """اختبار حقيقي للمزود الاحتياطي (بدون كشف المفتاح في الاستجابة)."""
    cfg = load_config()
    fb = get_fallback(cfg)
    if not fb:
        return {"ok": False, "error": "المزود الاحتياطي غير مكتمل: يحتاج enabled + api_key + model"
                                      " + base_url (أو provider=openrouter مع مفتاح sk-or-)."}
    from core.llm import complete
    try:
        _, content = complete(fb["provider"], fb["model"],
                              [{"role": "user", "content": "Reply with exactly: OK"}],
                              api_key=fb["key"], temperature=0.0,
                              base_url=fb.get("base_url", ""))
        return {"ok": True, "reply": (content or "").strip()[:200],
                "provider": fb["provider"], "model": fb["model"]}
    except Exception as e:  # noqa: BLE001 - نُعيد سبب الفشل الحقيقي للمستخدم
        return {"ok": False, "error": str(e), "provider": fb["provider"], "model": fb["model"]}


# ---------------------------------------------------------------- المحادثات والسجل
@app.post("/api/chats")
def create_chat(body: dict | None = None):
    title = ((body or {}).get("title") or "محادثة جديدة")
    return {"id": history.create_chat(title)}


@app.get("/api/chats")
def list_chats():
    return {"chats": history.list_chats()}


@app.get("/api/chats/search")
def search_chats(q: str = ""):
    return {"results": history.search_chats(q)}


@app.get("/api/chats/{cid}")
def chat_meta(cid: str):
    chat = history.get_chat(cid)
    if not chat:
        return JSONResponse({"error": "محادثة غير موجودة"}, status_code=404)
    return {"chat": chat}


@app.get("/api/chats/{cid}/messages")
def chat_messages(cid: str):
    titles = {c["id"]: c for c in history.list_chats()}
    if cid not in titles:
        return JSONResponse({"error": "محادثة غير موجودة"}, status_code=404)
    return {"messages": history.get_messages(cid)}


@app.patch("/api/chats/{cid}")
def update_chat(cid: str, body: dict):
    if "title" in body:
        history.rename_chat(cid, str(body.get("title") or "محادثة"))
    if "pinned" in body:
        history.set_pinned(cid, bool(body.get("pinned")))
    return {"ok": True, "chat": history.get_chat(cid)}


@app.delete("/api/chats/{cid}")
def delete_chat(cid: str):
    history.delete_chat(cid)
    return {"ok": True}


@app.post("/api/chats/{cid}/branch")
def branch_chat(cid: str, body: dict):
    """تفريع مستقل: ينسخ السياق حتى الرسالة المحددة فقط دون المساس بالأصل."""
    mid = body.get("message_id")
    try:
        mid = int(mid) if mid is not None else None
    except Exception:
        mid = None
    title = str(body.get("title") or "").strip() or None
    new_id = history.branch_chat(cid, upto_id=mid, title=title)
    if not new_id:
        return JSONResponse({"error": "تعذر إنشاء التفريع"}, status_code=404)
    return {"ok": True, "id": new_id, "chat": history.get_chat(new_id)}


@app.post("/api/chats/{cid}/share")
def create_share(cid: str, body: dict, request: Request):
    """Create a read-only public share snapshot for selected messages."""
    ids = body.get("message_ids") or []
    if not isinstance(ids, list):
        ids = []
    theme = str(body.get("theme") or "").strip().lower()
    lang = str(body.get("lang") or "").strip().lower()[:2]
    result = history.create_share(cid, ids, title=body.get("title"), theme=theme, lang=lang)
    if not result:
        return JSONResponse({"error": "No messages to share"}, status_code=400)
    base_url = str(request.base_url).rstrip("/")
    return {**result, "url": f"{base_url}/share/{result['id']}", "path": f"/share/{result['id']}"}


@app.get("/api/share/{sid}")
def read_share(sid: str):
    data = history.get_share(sid)
    if not data:
        return JSONResponse({"error": "الرابط غير صالح أو تم حذفه"}, status_code=404)
    return data


@app.delete("/api/share/{sid}")
def revoke_share(sid: str):
    if not history.revoke_share_by_id(sid):
        return JSONResponse({"error": "الرابط غير موجود"}, status_code=404)
    return {"ok": True, "revoked": sid}


@app.delete("/api/chats/{cid}/share")
def revoke_chat_share(cid: str):
    removed = history.revoke_share(cid)
    return {"ok": True, "revoked": removed}


@app.patch("/api/chats/{cid}/messages/{mid}/feedback")
def message_feedback(cid: str, mid: int, body: dict):
    ok = history.set_feedback(cid, mid, str(body.get("feedback") or ""))
    if not ok:
        return JSONResponse({"error": "تعذر حفظ التقييم"}, status_code=400)
    return {"ok": True}



@app.post("/api/chats/{cid}/conversation-feedback")
def set_conversation_feedback(cid: str, body: dict):
    val = str((body or {}).get("value") or "").strip().lower()
    res = history.set_conversation_feedback(cid, val)
    if not res:
        return JSONResponse({"error": "Invalid feedback or chat not found"}, status_code=400)
    return {"ok": True, **res}


@app.post("/api/chats/{cid}/messages")
def add_local_message(cid: str, body: dict):
    """Save a local/system assistant message into chat history."""
    role = body.get("role") or "assistant"
    content = str(body.get("content") or "").strip()
    if not content:
        return JSONResponse({"error": "content required"}, status_code=400)
    mid = history.add_message(cid, role, content, agent=body.get("agent"), sources=body.get("sources"),
                              attachments=body.get("attachments"), status=str(body.get("status") or "ok"),
                              error=body.get("error"))
    return {"ok": True, "id": mid, "message": history.get_message(cid, mid)}


@app.patch("/api/chats/{cid}/messages/{mid}")
def edit_message(cid: str, mid: int, body: dict):
    content = str(body.get("content") or "").strip()
    if not content:
        return JSONResponse({"error": "content required"}, status_code=400)
    attachments = body.get("attachments")
    if attachments is not None and not isinstance(attachments, list):
        attachments = None
    # Validate chat exists
    chat = history.get_chat(cid)
    if not chat:
        return JSONResponse({"error": "chat not found", "code": "chat_not_found"}, status_code=404)
    # Validate message exists and belongs to chat
    existing = history.get_message(cid, mid)
    if not existing:
        return JSONResponse({"error": "message not found", "code": "message_not_found"}, status_code=404)
    if existing.get("role") != "user":
        return JSONResponse({"error": "only user messages can be edited", "code": "not_editable"}, status_code=400)
    msg = history.edit_user_message(cid, mid, content, attachments=attachments)
    if not msg:
        # Race/stale: recheck
        existing2 = history.get_message(cid, mid)
        if not existing2:
            return JSONResponse({"error": "message not found after edit attempt", "code": "message_not_found"}, status_code=404)
        return JSONResponse({"error": "edit failed", "code": "edit_failed"}, status_code=409)
    return {"ok": True, "message": msg}


@app.post("/api/chats/{cid}/messages/{mid}/retry")
def retry_message(cid: str, mid: int, body: dict | None = None):
    body = body or {}
    msg = history.get_message(cid, mid)
    if not msg:
        return JSONResponse({"error": "message not found"}, status_code=404)
    if msg.get("role") == "assistant":
        msgs = history.get_messages(cid)
        idx = next((i for i, m in enumerate(msgs) if m.get("id") == mid), None)
        if idx is None:
            return JSONResponse({"error": "context not found"}, status_code=404)
        user_msg = next((m for m in reversed(msgs[:idx]) if m.get("role") == "user"), None)
        if not user_msg:
            return JSONResponse({"error": "no user message to retry"}, status_code=400)
        history.delete_messages_after(cid, int(user_msg["id"]))
        target_user = user_msg
    else:
        history.delete_messages_after(cid, mid)
        target_user = msg

    message = str(target_user.get("content") or "").strip()
    message = re.sub(r"\n\s*📎.*$", "", message, flags=re.S).strip()
    attachments = target_user.get("attachments") or []
    lang = (body.get("lang") or "ar")[:2]

    def gen():
        primary_agent = None
        final = {"thinking": "", "content": "", "sources": []}
        saved_id = None
        error_text = None
        try:
            for chunk in run_stream(chat_id=cid, message=message,
                                    attachments=attachments,
                                    agent_hint=body.get("agent_hint") or None,
                                    regenerate=False, lang=lang):
                line = chunk.strip()
                if line.startswith("data:"):
                    try:
                        ev = json.loads(line[5:])
                        if ev.get("type") == "route" and ev.get("agents"):
                            primary_agent = ev["agents"][0]["id"]
                        elif ev.get("type") == "done":
                            final = {"thinking": ev.get("thinking", ""), "content": ev.get("content", ""),
                                     "sources": ev.get("sources", [])}
                        elif ev.get("type") == "error":
                            error_text = ev.get("text")
                    except Exception:
                        pass
                yield chunk
        except Exception as e:
            error_text = error_text or str(e)
        finally:
            if final["content"]:
                saved_id = history.add_message(cid, "assistant", final["content"], agent=primary_agent,
                                               thinking=final["thinking"] or None, sources=final["sources"],
                                               status="ok")
            elif error_text:
                saved_id = history.add_message(cid, "assistant", f"⚠️ {error_text}", agent=primary_agent,
                                               status="error", error=str(error_text))
        if saved_id:
            msg_obj = history.get_message(cid, saved_id)
            yield "data: " + json.dumps({"type": "saved", "message_id": saved_id, "message": msg_obj}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


@app.post("/api/chat/stream")
def chat_stream(body: dict):
    chat_id = str(body.get("chat_id") or "")
    message = str(body.get("message") or "").strip()
    regenerate = bool(body.get("regenerate"))
    if not chat_id or (not message and not regenerate):
        return JSONResponse({"error": "chat_id and message required"}, status_code=400)

    user_mid = None
    attachments = body.get("attachments") or []
    skip_user_save = bool(body.get("skip_user_save"))
    if not regenerate and not skip_user_save:
        names = [a.get("name") for a in attachments if a.get("name")]
        user_content = message + (("\n\n📎 " + "، ".join(names)) if names else "")
        att_meta = []
        for a in attachments:
            if not (a.get("name") or a.get("library_id") or a.get("dataUrl")):
                continue
            mobj = {k: a.get(k) for k in ("name","type","size","library_id","mime","kind","dataUrl") if a.get(k) is not None}
            if isinstance(mobj.get("dataUrl"), str) and len(mobj["dataUrl"]) > 4096:
                mobj.pop("dataUrl", None)
            att_meta.append(mobj)
        user_mid = history.add_message(chat_id, "user", user_content, attachments=att_meta, status="ok")
        lib_ids = [a.get("library_id") for a in attachments if a.get("library_id")]
        if lib_ids:
            history.link_library(lib_ids, chat_id, user_mid)

    def gen():
        primary_agent = None
        final = {"thinking": "", "content": "", "sources": []}
        saved_id = None
        error_text = None
        if user_mid:
            um = history.get_message(chat_id, user_mid)
            yield "data: " + json.dumps({"type": "user_saved", "message_id": user_mid, "message": um}, ensure_ascii=False) + "\n\n"
        try:
            for chunk in run_stream(chat_id=chat_id, message=message,
                                    attachments=attachments,
                                    agent_hint=body.get("agent_hint") or None,
                                    regenerate=regenerate,
                                    lang=(body.get("lang") or "ar")[:2]):
                line = chunk.strip()
                if line.startswith("data:"):
                    try:
                        ev = json.loads(line[5:])
                        if ev.get("type") == "route" and ev.get("agents"):
                            primary_agent = ev["agents"][0]["id"]
                        elif ev.get("type") == "done":
                            final = {"thinking": ev.get("thinking", ""),
                                     "content": ev.get("content", ""),
                                     "sources": ev.get("sources", [])}
                        elif ev.get("type") == "error":
                            error_text = ev.get("text") or error_text
                    except Exception:
                        pass
                yield chunk
        except Exception as e:
            error_text = error_text or str(e)
            yield "data: " + json.dumps({"type": "error", "text": str(e)}, ensure_ascii=False) + "\n\n"
        finally:
            if final["content"] and saved_id is None:
                saved_id = history.add_message(chat_id, "assistant", final["content"], agent=primary_agent,
                                               thinking=final["thinking"] or None, sources=final["sources"], status="ok")
            elif error_text and saved_id is None:
                saved_id = history.add_message(chat_id, "assistant", f"⚠️ {error_text}", agent=primary_agent,
                                               status="error", error=str(error_text))
        if saved_id:
            msg_obj = history.get_message(chat_id, saved_id)
            yield "data: " + json.dumps({"type": "saved", "message_id": saved_id, "message": msg_obj}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


# ---------------------------------------------------------------- الملفات والتدريب
_reindex_wanted = threading.Event()
_reindex_guard = threading.Lock()


def _bg_reindex():
    """Queue a rebuild; never drop a request that arrives while a build is running."""
    _reindex_wanted.set()
    with _reindex_guard:
        if getattr(_bg_reindex, "_running", False):
            return
        _bg_reindex._running = True

    def worker():
        try:
            while _reindex_wanted.is_set():
                _reindex_wanted.clear()
                while rag.is_building():
                    time.sleep(0.5)
                rag.build_index()
        finally:
            with _reindex_guard:
                _bg_reindex._running = False
            # A request may have arrived between the loop check and clearing the flag.
            if _reindex_wanted.is_set():
                _bg_reindex()

    threading.Thread(target=worker, daemon=True).start()


@app.post("/api/upload")
def upload(file: UploadFile = File(...), train: bool = Form(False), chat_id: str = Form(""),
           origin: str = Form("chat")):
    safe = f"{int(time.time())}_{Path(file.filename or 'file').name}".replace("\\", "_").replace("/", "_")
    dest = UPLOAD_DIR / safe
    if dest.exists():  # تجنب تعارض الاسم في نفس الثانية
        safe = f"{int(time.time() * 1000)}_{Path(file.filename or 'file').name}".replace("\\", "_").replace("/", "_")
        dest = UPLOAD_DIR / safe
    size = 0
    with dest.open("wb") as f:  # دالة متزامنة → تعمل في Threadpool ولا تعلق بث الشات
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            f.write(chunk)
    text = ""
    if dest.suffix.lower() in extract.TEXT_EXTS:
        text = extract.extract_text(dest)
    saved_to = None
    if train:
        train_dir = DATA_DIR / "من_الشات"
        train_dir.mkdir(parents=True, exist_ok=True)
        # Re-uploading a file with the same original name updates it instead of
        # leaving the old timestamped copy in the index (stale/duplicate facts).
        original_name = Path(file.filename or safe).name
        for old in list(train_dir.iterdir()):
            try:
                if old.is_file() and old.name != safe and old.name.endswith("_" + original_name):
                    old.unlink()
            except Exception:
                pass
        target = train_dir / safe
        target.write_bytes(dest.read_bytes())
        saved_to = str(target.relative_to(DATA_DIR))
        _bg_reindex()
    # كل ملف يُحفظ تلقائياً في المكتبة الشخصية (حتى لو لم يُستخدم في محادثة بعد)
    lib = history.add_library_item(
        name=Path(file.filename or safe).name, stored_name=safe,
        mime=file.content_type or "", size=size,
        chat_id=(chat_id or None), text=text, kind=history._kind_of(file.content_type or "", file.filename or ""))
    return {"name": file.filename, "size": size, "text_chars": len(text or ""),
            "text": (text or "")[:8000], "saved_to": saved_to,
            "library_id": lib.get("id"), "kind": lib.get("kind"), "mime": lib.get("mime"),
            "origin": origin}



@app.post("/api/reindex")
def reindex():
    if rag.is_building():
        return {"started": False, "busy": True}
    _bg_reindex()
    return {"started": True}


# ---------------------------------------------------------------- المكتبة الشخصية
@app.get("/api/library")
def library(q: str = "", kind: str = "all"):
    items = history.list_library(q=q, kind=kind)
    return {"items": items, "count": len(items)}


@app.get("/api/library/{lid}/file")
def library_file(lid: str, download: bool = False):
    item = history.get_library_item(lid)
    if not item:
        return JSONResponse({"error": "الملف غير موجود"}, status_code=404)
    path = (UPLOAD_DIR / item["stored_name"]).resolve()
    try:
        if not path.is_relative_to(UPLOAD_DIR.resolve()) or not path.is_file():
            raise FileNotFoundError
    except Exception:
        return JSONResponse({"error": "الملف غير موجود على القرص"}, status_code=404)
    headers = {"Cache-Control": "private, max-age=3600"}
    if download:
        return FileResponse(str(path), filename=item["name"], media_type=item.get("mime") or "application/octet-stream",
                            headers=headers)
    return FileResponse(str(path), media_type=item.get("mime") or "application/octet-stream", headers=headers)


@app.delete("/api/library/{lid}")
def library_delete(lid: str):
    item = history.delete_library_item(lid)
    if not item:
        return JSONResponse({"error": "الملف غير موجود"}, status_code=404)
    removed_train = False
    for folder in (UPLOAD_DIR, DATA_DIR / "من_الشات"):
        path = (folder / item["stored_name"]).resolve()
        try:
            if path.is_relative_to(folder.resolve()) and path.is_file():
                path.unlink()
                removed_train = removed_train or folder != UPLOAD_DIR
        except Exception:
            pass
    if removed_train:
        _bg_reindex()   # remove the deleted document's chunks from retrieval
    return {"ok": True, "reindexing": removed_train}


@app.post("/api/library/link")
def library_link(body: dict):
    history.link_library(body.get("ids") or [], str(body.get("chat_id") or ""),
                         body.get("message_id"))
    return {"ok": True}


# ---------------------------------------------------------------- مصدر الجامعة (الاستهلاك 읽-only)
@app.get("/api/university/status")
def university_status():
    """إحصائيات معالجة دليل الجامعة المصدر (للواجهة فقط؛ لا يُعدّل أي ملف مصدر)."""
    return university_ingest.get_status()


@app.post("/api/university/reindex")
def university_reindex():
    """إعادة معالجة دليل الجامعة بشكل تزايدية (آمن، يُحفظ الملفات المصدرية)."""
    if getattr(university_reindex, "_running", False):
        return {"started": False, "busy": True}
    university_reindex._running = True
    try:
        status = university_ingest.process_university()
        return {"started": True, "status": status}
    finally:
        university_reindex._running = False


# ---------------------------------------------------------------- التغذية الراجعة والاختبارات الانحدارية
@app.post("/api/feedback")
def api_feedback(body: dict):
    """يسجّل تغذية راجعة على إجابة وكيل. لو كان dislike ومؤكّد يُسجّل كحالة انحدار."""
    fid = feedback.record_feedback(
        chat_id=str(body.get("chat_id") or ""),
        message_id=int(body.get("message_id") or 0),
        question=str(body.get("question") or ""),
        agent=str(body.get("agent") or "research"),
        answer=str(body.get("answer") or ""),
        sources=body.get("sources") or [],
        feedback=str(body.get("feedback") or ""),
        category=body.get("category"),
        root_cause=body.get("root_cause"),
        confirmed=bool(body.get("confirmed", False)),
    )
    return {"ok": True, "feedback_id": fid}


@app.get("/api/feedback/stats")
def api_feedback_stats():
    return feedback.get_stats()


@app.get("/api/feedback/regression-cases")
def api_regression_cases():
    return {"cases": feedback.list_regression_cases()}


@app.post("/api/feedback/regression-run")
def api_regression_run(body: dict):
    """يُعيد تشغيل حالة انحدار (أو جميع الحالات لو لم يُمرّر case_id).
    يستخدم الدالة الفعلية لتشغيل الوكيل عبر /api/chat/stream غير متزامن؛ هنا ن錄 المحاولة فقط.
    """
    case_id = body.get("case_id")
    cases = feedback.list_regression_cases()
    if case_id:
        cases = [c for c in cases if c.get("id") == case_id]
    results = []
    # لا يوجد Runner فعّال هنا (يتطلب SSE); نُسجّل المحاولة كنتيجة غير محسومة pending.
    for c in cases:
        results.append({
            "case_id": c.get("id"),
            "question": c.get("question"),
            "category": c.get("category"),
            "root_cause": c.get("root_cause"),
            "status": "pending_sse_runner",
            "note": "يُنفّذ عبر واجهة المتصفح/E2E ويُسجّل نتيجته في regression_runs.",
        })
    return {"run_count": len(results), "results": results}


# ---------------------------------------------------------------- الأدوات
@app.post("/api/tools/gpa")
def tool_gpa(body: dict):
    lang = (body.get("lang") or "ar")[:2]
    try:
        res = gpatool.calc(body.get("rows") or [], scale=body.get("scale") or "egypt5",
                           previous_gpa=body.get("previous_gpa"), previous_hours=body.get("previous_hours"),
                           lang=lang)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    res["markdown"] = gpatool.to_markdown(res, lang=lang)
    return res


@app.post("/api/tools/cv/analyze")
def tool_cv_analyze(body: dict):
    return cvgen.analyze(body.get("profile") or {}, body.get("track") or "General",
                         lang=(body.get("lang") or "ar")[:2])


@app.post("/api/tools/cv/html")
def tool_cv_html(body: dict):
    return {"html": cvgen.render_html(body.get("profile") or {}, body.get("lang") or "ar",
                                      body.get("theme") or {})}


@app.post("/api/tools/cv/pdf")
def tool_cv_pdf(body: dict):
    html = cvgen.render_html(body.get("profile") or {}, (body.get("lang") or "ar")[:2],
                             body.get("theme") or {})
    out = UPLOAD_DIR / f"CV_{int(time.time())}.pdf"
    if cvgen.html_to_pdf(html, out):
        return FileResponse(str(out), filename="CV.pdf", media_type="application/pdf")
    return JSONResponse({"error": "تعذر توليد PDF تلقائياً — استخدم المعاينة ثم Ctrl+P",
                         "html": html}, status_code=502)


@app.post("/api/tools/cv/docx")
def tool_cv_docx(body: dict):
    path = cvgen.render_docx(body.get("profile") or {}, (body.get("lang") or "ar")[:2], body.get("theme") or {})
    return FileResponse(str(path), filename="CV.docx",
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.post("/api/tools/tts")
def tool_tts(body: dict):
    """نص → صوت حقيقي mp3 عبر OpenRouter (HeyGen/Fish). يفشل برسالة واضحة إن لا مفتاح."""
    from core.config import get_model_key
    from core.llm import openrouter_tts
    cfg = load_config()
    tts = cfg.get("tts") or {}
    model = tts.get("model") or "heygen/heygen-voice-1-turbo:free"
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "لا يوجد نص للنطق"}, status_code=400)
    try:
        audio = openrouter_tts(text[:1200], model, tts.get("voice") or "",
                               get_model_key("openrouter", model, cfg))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "no-cache"})


@app.post("/api/tools/stt")
async def tool_stt(file: UploadFile = File(...), diarize: bool = Form(False)):
    """صوت → نص: Groq Whisper أولاً ثم Gemini (دقة عالية للعربية، مجاني)."""
    from core.config import get_model_key
    from core.llm import gemini_transcribe, groq_transcribe, groq_transcribe_verbose
    cfg = load_config()
    stt_model = (cfg.get("stt") or {}).get("model") or "whisper-large-v3-turbo"
    data = await file.read()
    if not data:
        return JSONResponse({"error": "ملف صوت فارغ"}, status_code=400)
    filename = file.filename or "audio.webm"
    mime = file.content_type or "audio/webm"
    errors: list[str] = []
    groq_key = get_model_key("groq", stt_model, cfg)
    if groq_key:
        try:
            if diarize:
                d = groq_transcribe_verbose(data, filename, stt_model, groq_key)
                if d.get("text"):
                    return {"text": d["text"], "segments": d.get("segments") or [],
                            "engine": "groq-whisper"}
            text = groq_transcribe(data, filename, stt_model, groq_key)
            if text:
                return {"text": text, "segments": [], "engine": "groq-whisper"}
        except Exception as e:
            errors.append(f"Groq: {e}")
    gem_key = cfg.get("api_keys", {}).get("gemini", "")
    if gem_key:
        gm = (cfg.get("stt") or {}).get("gemini_model") or "gemini-flash-lite-latest"
        for model in ([gm, "gemini-3.6-flash"] if gm != "gemini-3.6-flash" else [gm]):
            try:
                text = gemini_transcribe(data, mime, gem_key, model)
                if text:
                    return {"text": text, "segments": [], "engine": f"gemini:{model}"}
            except Exception as e:
                errors.append(f"Gemini: {e}")
    if not groq_key and not gem_key:
        return JSONResponse({"error": "تحويل الصوت يحتاج مفتاح Gemini أو Groq مجاني في ⚙️ الإعدادات."}, status_code=502)
    return JSONResponse({"error": "تعذر تحويل الصوت: " + " | ".join(errors)[:300]}, status_code=502)



@app.post("/api/tools/translate")
def tool_translate(body: dict):
    """ترجمة احترافية: النموذج اللغوي أولاً ثم محرك جوجل المجاني كبديل."""
    from core import translate as tx
    text = str(body.get("text") or "").strip()
    target = (body.get("target") or "en")[:2]
    if not text:
        return JSONResponse({"error": "لا يوجد نص للترجمة" if target == "ar" else "No text to translate"},
                            status_code=400)
    try:
        return tx.translate(text, target)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=502)


# ---------------------------------------------------------------- التشغيل
def _free_port(start: int, tries: int = 10) -> int:
    port = start
    for _ in range(tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return start


def main():
    import argparse
    import uvicorn
    p = argparse.ArgumentParser(description="فريق الوكلاء الأكاديمي — AI MAS")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()
    port = _free_port(args.port)
    url = f"http://{args.host}:{port}"
    print("=" * 60)
    print("🧠 فريق الوكلاء الأكاديمي — يعمل الآن على:", url)
    print("   اضغط Ctrl+C للإيقاف. لا تغلق هذه النافذة أثناء الاستخدام.")
    print("=" * 60)
    if not args.no_browser:
        threading.Timer(1.2, webbrowser.open, [url]).start()
    uvicorn.run(app, host=args.host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
