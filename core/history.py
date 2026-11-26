"""سجل المحادثات (History) — SQLite محلي: محادثات + رسائل + مصادر + تفكير عميق
+ تثبيت وإعادة تسمية + تقييم الردود + مشاركة عامة + مكتبة الملفات + التفريعات.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import time
import uuid

from .config import DB_PATH

_conn: sqlite3.Connection | None = None
_lock = threading.RLock()  # RLock لأن _db() تلتقطه داخل الدوال المغلفة به أيضاً


def _db() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA foreign_keys=ON")
            _conn.execute("""CREATE TABLE IF NOT EXISTS chats(
                id TEXT PRIMARY KEY, title TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL)""")
            _conn.execute("""CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL, role TEXT NOT NULL, agent TEXT,
                content TEXT NOT NULL, thinking TEXT, sources TEXT,
                created REAL NOT NULL)""")
            _conn.execute("""CREATE TABLE IF NOT EXISTS shares(
                id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, title TEXT,
                created REAL NOT NULL, payload TEXT NOT NULL)""")
            _conn.execute("""CREATE TABLE IF NOT EXISTS library(
                id TEXT PRIMARY KEY, name TEXT NOT NULL, stored_name TEXT NOT NULL,
                mime TEXT, size INTEGER NOT NULL DEFAULT 0, kind TEXT,
                text TEXT, chat_id TEXT, message_id INTEGER,
                created REAL NOT NULL)""")
            _conn.execute("""CREATE TABLE IF NOT EXISTS message_versions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL, chat_id TEXT NOT NULL,
                content TEXT NOT NULL, attachments TEXT, created REAL NOT NULL,
                reason TEXT)""")
            # ترقيات آمنة لقواعد البيانات القديمة (لا تفقد أي محادثة)
            _ensure_column(_conn, "chats", "pinned", "INTEGER NOT NULL DEFAULT 0")
            _ensure_column(_conn, "chats", "share_id", "TEXT")
            _ensure_column(_conn, "chats", "shared_at", "REAL")
            _ensure_column(_conn, "messages", "feedback", "TEXT")
            _ensure_column(_conn, "messages", "attachments", "TEXT")
            _ensure_column(_conn, "messages", "edited_at", "REAL")
            _ensure_column(_conn, "messages", "status", "TEXT")
            _ensure_column(_conn, "messages", "error", "TEXT")
            _ensure_column(_conn, "chats", "conversation_feedback", "TEXT")
            _ensure_column(_conn, "chats", "conversation_feedback_at", "REAL")
            _ensure_column(_conn, "chats", "conversation_feedback_dismissed", "INTEGER DEFAULT 0")
            _conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_chat ON messages(chat_id)")
            _conn.execute("CREATE INDEX IF NOT EXISTS idx_chats_pinned ON chats(pinned, updated)")
            _conn.execute("CREATE INDEX IF NOT EXISTS idx_library_created ON library(created)")
            _conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_versions ON message_versions(message_id)")
            _conn.commit()
        return _conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _row_chat(r) -> dict:
    d = {"id": r[0], "title": r[1], "updated": r[2], "messages": r[3],
         "pinned": bool(r[4]), "created": r[5], "share_id": r[6]}
    if len(r) > 7:
        d["conversation_feedback"] = r[7]
        d["conversation_feedback_at"] = r[8] if len(r) > 8 else None
        d["conversation_feedback_dismissed"] = bool(r[9]) if len(r) > 9 and r[9] is not None else False
    return d


# ------------------------------------------------------------------ المحادثات
def create_chat(title: str = "محادثة جديدة") -> str:
    now = time.time()
    cid = uuid.uuid4().hex[:12]
    with _lock:
        _db().execute("INSERT INTO chats(id,title,created,updated) VALUES(?,?,?,?)", (cid, title, now, now))
        _db().commit()
    return cid


def list_chats() -> list[dict]:
    with _lock:
        rows = _db().execute("""
            SELECT c.id, c.title, c.updated,
                   (SELECT COUNT(*) FROM messages m WHERE m.chat_id = c.id) AS n,
                   c.pinned, c.created, c.share_id,
                   c.conversation_feedback, c.conversation_feedback_at, c.conversation_feedback_dismissed
            FROM chats c ORDER BY c.pinned DESC, c.updated DESC""").fetchall()
    return [_row_chat(r) for r in rows]


def get_chat(chat_id: str) -> dict | None:
    with _lock:
        r = _db().execute("""
            SELECT c.id, c.title, c.updated,
                   (SELECT COUNT(*) FROM messages m WHERE m.chat_id = c.id) AS n,
                   c.pinned, c.created, c.share_id,
                   c.conversation_feedback, c.conversation_feedback_at, c.conversation_feedback_dismissed
            FROM chats c WHERE c.id=?""", (chat_id,)).fetchone()
    if not r: return None
    d = _row_chat(r)
    try:
        d["conversation_feedback"] = r[7] if len(r) > 7 else None
        d["conversation_feedback_at"] = r[8] if len(r) > 8 else None
        d["conversation_feedback_dismissed"] = bool(r[9]) if len(r) > 9 and r[9] is not None else False
    except Exception:
        pass
    return d


def rename_chat(chat_id: str, title: str) -> bool:
    with _lock:
        cur = _db().execute("UPDATE chats SET title=? WHERE id=?", (title.strip() or "محادثة", chat_id))
        _db().commit()
    return cur.rowcount > 0


def set_pinned(chat_id: str, pinned: bool) -> bool:
    with _lock:
        cur = _db().execute("UPDATE chats SET pinned=? WHERE id=?", (1 if pinned else 0, chat_id))
        _db().commit()
    return cur.rowcount > 0


def delete_chat(chat_id: str) -> None:
    with _lock:
        _db().execute("DELETE FROM message_versions WHERE chat_id=?", (chat_id,))
        _db().execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        _db().execute("DELETE FROM shares WHERE chat_id=?", (chat_id,))
        _db().execute("UPDATE library SET chat_id=NULL, message_id=NULL WHERE chat_id=?", (chat_id,))
        _db().execute("DELETE FROM chats WHERE id=?", (chat_id,))
        _db().commit()


def search_chats(q: str, limit: int = 30) -> list[dict]:
    """بحث سريع في عناوين المحادثات وفي نص الرسائل."""
    q = (q or "").strip()
    if not q:
        return []
    like = f"%{q}%"
    with _lock:
        rows = _db().execute("""
            SELECT c.id, c.title, c.updated,
                   (SELECT COUNT(*) FROM messages m WHERE m.chat_id=c.id),
                   c.pinned, c.created, c.share_id,
                   (SELECT m.content FROM messages m WHERE m.chat_id=c.id AND m.content LIKE ?
                    ORDER BY m.id DESC LIMIT 1) AS snippet
            FROM chats c
            WHERE c.title LIKE ? OR EXISTS(
                SELECT 1 FROM messages m WHERE m.chat_id=c.id AND m.content LIKE ?)
            ORDER BY c.pinned DESC, c.updated DESC LIMIT ?""",
            (like, like, like, limit)).fetchall()
    out = []
    for r in rows:
        d = _row_chat(r[:7])
        d["snippet"] = (r[7] or "")[:180]
        out.append(d)
    return out


# ------------------------------------------------------------------ الرسائل
def _loads_json(val, default):
    try:
        return json.loads(val) if val else default
    except Exception:
        return default


def _row_msg(r) -> dict:
    # SELECT: role,agent,content,thinking,sources,created,id,feedback,attachments,edited_at,status,error
    role, agent, content, thinking, sources, created = r[:6]
    return {
        "id": r[6] if len(r) > 6 else None,
        "role": role,
        "agent": agent,
        "content": content,
        "thinking": thinking,
        "sources": _loads_json(sources, []),
        "created": created,
        "feedback": r[7] if len(r) > 7 else None,
        "attachments": _loads_json(r[8] if len(r) > 8 else None, []),
        "edited_at": r[9] if len(r) > 9 else None,
        "status": (r[10] if len(r) > 10 and r[10] is not None else "ok"),
        "error": r[11] if len(r) > 11 else None,
    }


_MSG_COLS = ("role,agent,content,thinking,sources,created,id,feedback,attachments,edited_at,status,error")


def get_messages(chat_id: str) -> list[dict]:
    with _lock:
        rows = _db().execute(
            f"SELECT {_MSG_COLS} FROM messages WHERE chat_id=? ORDER BY id", (chat_id,)).fetchall()
    return [_row_msg(r) for r in rows]


def add_message(chat_id: str, role: str, content: str, agent: str | None = None,
                thinking: str | None = None, sources: list | None = None,
                touch_chat: bool = True, attachments: list | None = None,
                status: str = "ok", error: str | None = None) -> int:
    now = time.time()
    with _lock:
        cur = _db().execute(
            "INSERT INTO messages(chat_id,role,agent,content,thinking,sources,created,attachments,status,error) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (chat_id, role, agent, content, thinking,
             json.dumps(sources or [], ensure_ascii=False), now,
             json.dumps(attachments or [], ensure_ascii=False),
             status, error))
        if touch_chat:
            title = None
            if role == "user":
                row = _db().execute("SELECT title FROM chats WHERE id=?", (chat_id,)).fetchone()
                if row and row[0] in ("محادثة جديدة", "New chat", ""):
                    title = content.strip().replace("\n", " ")[:60]
            if title:
                _db().execute("UPDATE chats SET updated=?, title=? WHERE id=?", (now, title, chat_id))
            else:
                _db().execute("UPDATE chats SET updated=? WHERE id=?", (now, chat_id))
        _db().commit()
        return int(cur.lastrowid or 0)


def get_message(chat_id: str, message_id: int) -> dict | None:
    with _lock:
        r = _db().execute(f"SELECT {_MSG_COLS} FROM messages WHERE chat_id=? AND id=?",
                          (chat_id, int(message_id))).fetchone()
    return _row_msg(r) if r else None


def update_message(chat_id: str, message_id: int, *, content: str | None = None,
                   thinking: str | None = None, sources: list | None = None,
                   status: str | None = None, error: str | None = None,
                   attachments: list | None = None, edited_at: float | None = None,
                   clear_error: bool = False) -> bool:
    sets, params = [], []
    if content is not None:
        sets.append("content=?"); params.append(content)
    if thinking is not None:
        sets.append("thinking=?"); params.append(thinking)
    if sources is not None:
        sets.append("sources=?"); params.append(json.dumps(sources, ensure_ascii=False))
    if attachments is not None:
        sets.append("attachments=?"); params.append(json.dumps(attachments, ensure_ascii=False))
    if status is not None:
        sets.append("status=?"); params.append(status)
    if error is not None or clear_error:
        sets.append("error=?"); params.append(error)
    if edited_at is not None:
        sets.append("edited_at=?"); params.append(edited_at)
    if not sets:
        return False
    params.extend([int(message_id), chat_id])
    with _lock:
        cur = _db().execute(f"UPDATE messages SET {', '.join(sets)} WHERE id=? AND chat_id=?", params)
        _db().commit()
    return cur.rowcount > 0


def edit_user_message(chat_id: str, message_id: int, content: str, attachments: list | None = None) -> dict | None:
    """تحرير رسالة مستخدم: يحفظ نسخة قديمة، يحدّث الرسالة، ويحذف كل ما بعدها (لإعادة التوليد النظيف)."""
    now = time.time()
    with _lock:
        row = _db().execute(f"SELECT {_MSG_COLS} FROM messages WHERE chat_id=? AND id=?",
                            (chat_id, int(message_id))).fetchone()
        if not row:
            return None
        msg = _row_msg(row)
        if msg["role"] != "user":
            return None
        _db().execute(
            "INSERT INTO message_versions(message_id,chat_id,content,attachments,created,reason) VALUES(?,?,?,?,?,?)",
            (int(message_id), chat_id, msg["content"],
             json.dumps(msg.get("attachments") or [], ensure_ascii=False), now, "edit"))
        new_atts = attachments if attachments is not None else msg.get("attachments") or []
        _db().execute("UPDATE messages SET content=?, attachments=?, edited_at=?, status='ok', error=NULL WHERE id=? AND chat_id=?",
                      (content, json.dumps(new_atts, ensure_ascii=False), now, int(message_id), chat_id))
        _db().execute("DELETE FROM messages WHERE chat_id=? AND id>?", (chat_id, int(message_id)))
        _db().execute("UPDATE chats SET updated=? WHERE id=?", (now, chat_id))
        _db().commit()
        return get_message(chat_id, int(message_id))


def set_feedback(chat_id: str, message_id: int, feedback: str) -> bool:
    value = (feedback or "").strip().lower()
    if value not in ("", "like", "dislike"):
        return False
    with _lock:
        cur = _db().execute("UPDATE messages SET feedback=? WHERE id=? AND chat_id=?",
                            (value or None, int(message_id), chat_id))
        _db().commit()
    return cur.rowcount > 0




def set_conversation_feedback(chat_id: str, value: str) -> dict | None:
    v = (value or "").strip().lower()
    if v not in ("like", "dislike", "dismiss", ""):
        return None
    with _lock:
        row = _db().execute("SELECT id FROM chats WHERE id=?", (chat_id,)).fetchone()
        if not row:
            return None
        now = time.time()  # نفس الصيغة الرقمية (epoch) المستخدمة في بقية السجل
        if v == "dismiss":
            _db().execute("UPDATE chats SET conversation_feedback=NULL, conversation_feedback_dismissed=1, conversation_feedback_at=?, updated=? WHERE id=?",
                          (now, now, chat_id))
        elif v in ("like", "dislike"):
            _db().execute("UPDATE chats SET conversation_feedback=?, conversation_feedback_dismissed=0, conversation_feedback_at=?, updated=? WHERE id=?",
                          (v, now, now, chat_id))
        else:
            _db().execute("UPDATE chats SET conversation_feedback=NULL, conversation_feedback_dismissed=0, conversation_feedback_at=NULL, updated=? WHERE id=?",
                          (now, chat_id))
        _db().commit()
        r = _db().execute("SELECT conversation_feedback, conversation_feedback_at, conversation_feedback_dismissed FROM chats WHERE id=?", (chat_id,)).fetchone()
    return {
        "conversation_feedback": r[0],
        "conversation_feedback_at": r[1],
        "conversation_feedback_dismissed": bool(r[2]) if r and r[2] is not None else False,
    }

def get_conversation_feedback(chat_id: str) -> dict | None:
    with _lock:
        r = _db().execute("SELECT conversation_feedback, conversation_feedback_at, conversation_feedback_dismissed FROM chats WHERE id=?", (chat_id,)).fetchone()
    if not r:
        return None
    return {
        "conversation_feedback": r[0],
        "conversation_feedback_at": r[1],
        "conversation_feedback_dismissed": bool(r[2]) if r[2] is not None else False,
    }
def delete_messages_after(chat_id: str, message_id: int) -> int:
    """يحذف كل الرسائل بعد message_id (غير شاملة) للمحادثة نفسها."""
    with _lock:
        cur = _db().execute("DELETE FROM messages WHERE chat_id=? AND id>?", (chat_id, int(message_id)))
        _db().execute("UPDATE chats SET updated=? WHERE id=?", (time.time(), chat_id))
        _db().commit()
    return cur.rowcount


def history_tail(chat_id: str, limit: int = 8) -> list[dict]:
    """آخر رسائل المحادثة لتمريرها كسياق للنموذج."""
    with _lock:
        rows = _db().execute(
            "SELECT role, content FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT ?",
            (chat_id, limit)).fetchall()
    out = [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    # ندعم role: user/assistant فقط في سياق النموذج
    return [m for m in out if m["role"] in ("user", "assistant")]


# ------------------------------------------------------------------ التفريع
def branch_chat(chat_id: str, upto_id: int | None = None, title: str | None = None) -> str | None:
    """ينشئ محادثة مستقلة جديدة تحمل السياق حتى الرسالة المحددة (شاملة)."""
    with _lock:
        row = _db().execute("SELECT title FROM chats WHERE id=?", (chat_id,)).fetchone()
        if not row:
            return None
        msgs = get_messages(chat_id)
        if upto_id:
            cut = next((i for i, m in enumerate(msgs) if m["id"] == int(upto_id)), None)
            if cut is not None:
                msgs = msgs[: cut + 1]
        new_title = (title or f"{row[0]} · فرع").strip()[:80]
        new_id = create_chat(new_title)
        for m in msgs:
            _db().execute(
                "INSERT INTO messages(chat_id,role,agent,content,thinking,sources,created,feedback,attachments,edited_at,status,error) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (new_id, m["role"], m.get("agent"), m["content"], m.get("thinking"),
                 json.dumps(m.get("sources") or [], ensure_ascii=False), m["created"],
                 m.get("feedback"), json.dumps(m.get("attachments") or [], ensure_ascii=False),
                 m.get("edited_at"), m.get("status") or "ok", m.get("error")))
        _db().execute("UPDATE chats SET updated=? WHERE id=?", (time.time(), new_id))
        _db().commit()
    return new_id


# ------------------------------------------------------------------ المشاركة العامة
def create_share(chat_id: str, message_ids: list[int] | None = None, title: str | None = None,
                 theme: str | None = None, lang: str | None = None) -> dict | None:
    with _lock:
        row = _db().execute("SELECT title FROM chats WHERE id=?", (chat_id,)).fetchone()
        if not row:
            return None
        msgs = get_messages(chat_id)
        wanted = {int(x) for x in (message_ids or []) if str(x).strip().lstrip("-").isdigit()}
        if wanted:
            msgs = [m for m in msgs if m["id"] in wanted]
        if not msgs:
            return None
        sid = secrets.token_urlsafe(10).replace("-", "").replace("_", "")[:14]
        share_title = (title or row[0] or "Shared conversation").strip()[:120]
        theme_norm = (theme or "").strip().lower()
        if theme_norm not in ("light", "dark"):
            theme_norm = "dark"
        lang_norm = (lang or "").strip().lower()[:2]
        if lang_norm not in ("ar", "en", "fr"):
            lang_norm = "ar"
        payload = {
            "title": share_title,
            "created": time.time(),
            "theme": theme_norm,
            "lang": lang_norm,
            "messages": [{"role": m["role"], "agent": m.get("agent"), "content": m["content"],
                          "thinking": None,  # لا نشارك التفكير الداخلي في الروابط العامة
                          "sources": m.get("sources") or [],
                          "created": m.get("created"), "edited_at": m.get("edited_at"),
                          "attachments": m.get("attachments") or [],
                          "status": m.get("status"), "error": m.get("error")}
                         for m in msgs],
        }
        _db().execute("INSERT INTO shares(id,chat_id,title,created,payload) VALUES(?,?,?,?,?)",
                      (sid, chat_id, share_title, time.time(),
                       json.dumps(payload, ensure_ascii=False)))
        _db().execute("UPDATE chats SET share_id=?, shared_at=? WHERE id=?",
                      (sid, time.time(), chat_id))
        _db().commit()
    return {"id": sid, "title": share_title, "count": len(msgs), "theme": theme_norm, "lang": lang_norm}


def get_share(share_id: str) -> dict | None:
    if not share_id or len(share_id) > 64:
        return None
    with _lock:
        row = _db().execute("SELECT payload, created FROM shares WHERE id=?", (share_id,)).fetchone()
    if not row:
        return None
    try:
        data = json.loads(row[0])
    except Exception:
        return None
    data["shared_at"] = row[1]
    data.setdefault("theme", "dark")
    data.setdefault("lang", "ar")
    return data


def revoke_share(chat_id: str) -> int:
    """إلغاء كل روابط المشاركة للمحادثة: تُحذف اللقطات فوراً ويتوقف الرابط عن العمل."""
    with _lock:
        cur = _db().execute("DELETE FROM shares WHERE chat_id=?", (chat_id,))
        _db().execute("UPDATE chats SET share_id=NULL, shared_at=NULL WHERE id=?", (chat_id,))
        _db().commit()
        return int(cur.rowcount or 0)


def revoke_share_by_id(share_id: str) -> bool:
    if not share_id or len(share_id) > 64:
        return False
    with _lock:
        row = _db().execute("SELECT chat_id FROM shares WHERE id=?", (share_id,)).fetchone()
        if not row:
            return False
        _db().execute("DELETE FROM shares WHERE id=?", (share_id,))
        _db().execute("UPDATE chats SET share_id=NULL, shared_at=NULL WHERE id=? AND share_id=?", (row[0], share_id))
        _db().commit()
        return True


# ------------------------------------------------------------------ المكتبة
def add_library_item(name: str, stored_name: str, mime: str, size: int,
                     chat_id: str | None = None, text: str = "", kind: str = "") -> dict:
    lid = uuid.uuid4().hex[:12]
    now = time.time()
    with _lock:
        _db().execute(
            "INSERT INTO library(id,name,stored_name,mime,size,kind,text,chat_id,created) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (lid, name, stored_name, mime, int(size or 0), kind or _kind_of(mime, name),
             (text or "")[:200_000], chat_id, now))
        _db().commit()
    return get_library_item(lid) or {}


def _kind_of(mime: str, name: str) -> str:
    m = (mime or "").lower()
    ext = (name.rsplit(".", 1)[-1] if "." in name else "").lower()
    if m.startswith("image/") or ext in ("png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "heic"):
        return "image"
    if m.startswith("video/") or ext in ("mp4", "mov", "avi", "mkv"):
        return "video"
    if m.startswith("audio/") or ext in ("mp3", "wav", "m4a", "ogg", "aac", "flac"):
        return "audio"
    if ext == "webm":
        return "audio" if m.startswith("audio/") else "video"
    return "document"


def _row_lib(r) -> dict:
    return {"id": r[0], "name": r[1], "stored_name": r[2], "mime": r[3], "size": r[4],
            "kind": r[5], "text": r[6] or "", "chat_id": r[7], "message_id": r[8],
            "created": r[9], "chat_title": r[10] if len(r) > 10 else None}


def get_library_item(lid: str) -> dict | None:
    with _lock:
        r = _db().execute("""
            SELECT l.id,l.name,l.stored_name,l.mime,l.size,l.kind,l.text,l.chat_id,
                   l.message_id,l.created,c.title
            FROM library l LEFT JOIN chats c ON c.id=l.chat_id WHERE l.id=?""", (lid,)).fetchone()
    return _row_lib(r) if r else None


def list_library(q: str = "", kind: str = "", limit: int = 300) -> list[dict]:
    where, params = [], []
    q_str = (q or "").strip()
    if q_str:
        like = f"%{q_str}%"
        where.append("(l.name LIKE ? OR l.text LIKE ? OR c.title LIKE ?)")
        params += [like, like, like]
    if kind and kind not in ("all", "*"):
        where.append("l.kind=?")
        params.append(kind)
    sql = """SELECT l.id,l.name,l.stored_name,l.mime,l.size,l.kind,l.text,l.chat_id,
                    l.message_id,l.created,c.title
             FROM library l LEFT JOIN chats c ON c.id=l.chat_id"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY l.created DESC LIMIT ?"
    params.append(int(limit))
    with _lock:
        rows = _db().execute(sql, params).fetchall()
    return [_row_lib(r) for r in rows]


def delete_library_item(lid: str) -> dict | None:
    with _lock:
        item = get_library_item(lid)
        if not item:
            return None
        cur = _db().execute("DELETE FROM library WHERE id=?", (lid,))
        _db().commit()
        return item if cur.rowcount > 0 else None


def link_library(ids: list[str], chat_id: str, message_id: int | None = None) -> None:
    ids = [i for i in (ids or []) if i]
    if not ids:
        return
    with _lock:
        for lid in ids:
            _db().execute("UPDATE library SET chat_id=?, message_id=COALESCE(?,message_id) WHERE id=?",
                          (chat_id, message_id, lid))
        _db().commit()


def library_count() -> int:
    with _lock:
        r = _db().execute("SELECT COUNT(*) FROM library").fetchone()
    return int(r[0] if r else 0)
