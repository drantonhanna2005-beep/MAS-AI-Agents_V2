"""RAG عربي خفيف وسريع: تطبيع عربي + تقسيم مقاطع + BM25 مدمج + بحث دلالي اختياري.

- لا يحتاج أي API خارجي: BM25 مطبَّق داخلياً.
- البحث الدلالي (embeddings) اختياري: يعمل تلقائياً فقط لو Ollama شغال على الجهاز.
- الفهرس يُبنى من مجلد data/ + قاعدة المعرفة الأساسية ويُخزن في index_store/chunks.json.
"""
from __future__ import annotations

import json
import math
import re
import threading
import time
from pathlib import Path

from .config import DATA_DIR, INDEX_DIR
from . import extract

CHUNK_CHARS = 1100
CHUNK_OVERLAP = 180

_ar_marks = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u0640]")
_word_re = re.compile(r"[A-Za-z0-9_]+|[\u0600-\u06FF]+")

_lock = threading.Lock()
_state: dict = {
    "docs": [],
    "bm25": None,
    "vectors": None,
    "embed_model": None,
    "mtime": 0.0,
    "building": False,
    "title_tok": [],
}


# ---------------------------------------------------------------- التطبيع والتجزئة
def normalize_ar(text: str) -> str:
    t = _ar_marks.sub("", text or "")
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه"), ("ؤ", "و"), ("ئ", "ي")):
        t = t.replace(a, b)
    return t.lower()


def _stem(w: str) -> str:
    """تجذير خفيف للعربية (بدون مكتبات): يزيل أدوات التعريف والوصل واللواحق الشائعة."""
    while len(w) > 3 and w[0] in "وفبلك":
        w = w[1:]
    if len(w) > 4 and w.startswith("ال"):
        w = w[2:]
    for suf in ("ات", "ون", "ين", "ية", "ها", "هم", "هن", "كم"):
        if len(w) > 4 and w.endswith(suf):
            w = w[: -len(suf)]
            break
    return w


def tokenize(text: str) -> list[str]:
    return [_stem(w) for w in _word_re.findall(normalize_ar(text)) if len(w) > 1]


def chunk_text(text: str, source: str, title: str) -> list[dict]:
    paras = [p.strip() for p in re.split(r"\n", text) if p.strip()]
    chunks: list[dict] = []
    buf = ""
    for p in paras:
        if len(p) > CHUNK_CHARS:  # فقرة ضخمة → تقطيع قسري
            if buf.strip():
                chunks.append({"source": source, "title": title, "text": buf.strip()})
            for i in range(0, len(p), CHUNK_CHARS):
                pieces = p[i:i + CHUNK_CHARS]
                chunks.append({"source": source, "title": title, "text": pieces.strip()})
            buf = ""
            continue
        if len(buf) + len(p) + 1 > CHUNK_CHARS and buf.strip():
            chunks.append({"source": source, "title": title, "text": buf.strip()})
            buf = buf[-CHUNK_OVERLAP:] if CHUNK_OVERLAP < len(buf) else ""
        buf += ("\n" if buf else "") + p
    if buf.strip():
        chunks.append({"source": source, "title": title, "text": buf.strip()})
    return chunks


# ---------------------------------------------------------------- BM25 داخلي
class BM25:
    """تنفيذ BM25 (Okapi) خفيف — يكفي لآلاف المقاطع بسرعة عالية."""

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.N = len(corpus)
        self.avgdl = (sum(len(d) for d in corpus) / self.N) if self.N else 0.0
        self.tfs: list[dict] = []
        self.doc_len: list[int] = []
        self.df: dict[str, int] = {}
        for d in corpus:
            self.doc_len.append(len(d))
            tf: dict[str, int] = {}
            for w in d:
                tf[w] = tf.get(w, 0) + 1
            self.tfs.append(tf)
            for w in tf:
                self.df[w] = self.df.get(w, 0) + 1

    def _idf(self, w: str) -> float:
        df = self.df.get(w, 0)
        return math.log(1.0 + (self.N - df + 0.5) / (df + 0.5))

    def get_scores(self, query: list[str]) -> list[float]:
        scores = [0.0] * self.N
        if not self.N:
            return scores
        for w in set(query):
            idf = self._idf(w)
            if idf <= 0:
                continue
            for i, tf in enumerate(self.tfs):
                f = tf.get(w)
                if not f:
                    continue
                dl = self.doc_len[i] or 1
                scores[i] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1.0)))
        return scores


# ---------------------------------------------------------------- فهرسة
def collect_files(root: Path = DATA_DIR) -> list[Path]:
    files: list[Path] = []
    if root.exists():
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in extract.TEXT_EXTS:
                files.append(p)
            elif p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp3", ".wav", ".m4a", ".mp4", ".mkv", ".mov"):
                files.append(p)  # تُفهرس كبطاقة وصف فقط
    return files


def _describe_media(f: Path) -> dict:
    kind = "صورة" if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp") else "ملف صوتي/فيديو"
    return {"source": str(f.relative_to(DATA_DIR)), "title": f.stem,
            "text": f"[{kind}: {f.name}] — ملف وسائط داخل مجلد بيانات الطالب؛ اطلب عرضه أو صفه بنص لتحليله."}


def build_index(progress=None) -> dict:
    """يبني الفهرس من كل ملفات data/ + قاعدة المعرفة الأساسية."""
    global _state
    with _lock:
        if _state.get("building"):
            return {"busy": True}
        _state["building"] = True
    try:
        from .knowledge import build_knowledge_chunks
        docs: list[dict] = []
        n_files = 0
        for f in collect_files():
            n_files += 1
            rel = str(f.relative_to(DATA_DIR))
            if f.suffix.lower() in extract.TEXT_EXTS:
                text = extract.extract_text(f)
                if text and text.strip():
                    docs.extend(chunk_text(text, source=rel, title=f.stem))
                else:
                    docs.append({"source": rel, "title": f.stem,
                                 "text": f"[ملف: {f.name}] — لم يُعثر على نص قابل للاستخراج (قد يكون صورة ممسوحة)."})
            else:
                docs.append(_describe_media(f))
        docs.extend(build_knowledge_chunks())

        # إزالة التكرار الحرفي (نفس المحتوى مرفوع مرتين)
        seen: set = set()
        uniq: list[dict] = []
        for d in docs:
            hk = (d.get("source", ""), d.get("title", ""), d.get("text", ""))
            if hk in seen:
                continue
            seen.add(hk)
            uniq.append(d)
        docs = uniq

        # ---- Embeddings تزايدية: كاش حسب بصمة النص — إعادة الفهرسة تضيف الجديد فقط (تحصين ضد 429)
        import hashlib

        def _doc_hash(t: str) -> str:
            return hashlib.md5(t.encode("utf-8")).hexdigest()

        engine, emb_model = _embed_engine()
        from .config import load_config
        cfg = load_config()
        emb_map: dict = {}
        if engine != "none":
            try:
                old = json.loads((INDEX_DIR / "chunks.json").read_text("utf-8"))
                old_em = old.get("embeddings") or {}
                if old_em.get("model") == emb_model:
                    emb_map = dict(old_em.get("map") or {})
            except Exception:
                pass
        hashes = [_doc_hash(d["text"]) for d in docs]
        missing_idx = [i for i, h in enumerate(hashes) if h not in emb_map]
        if missing_idx and engine != "none":
            miss_texts = [docs[i]["text"] for i in missing_idx]
            got = None
            for _attempt in range(3):  # تراجع زمني عند 429 عابر
                if engine == "ollama":
                    try:
                        import httpx as _hx
                        rr = _hx.post(cfg.get("ollama_url", "").rstrip("/") + "/api/embed",
                                      json={"model": emb_model, "input": miss_texts}, timeout=600)
                        got = rr.json().get("embeddings") if rr.status_code == 200 else None
                    except Exception:
                        got = None
                else:
                    from core.config import get_model_key
                    from core.llm import openrouter_embed
                    keys = [get_model_key("openrouter", emb_model, cfg), cfg.get("api_keys", {}).get("openrouter", "")]
                    got = openrouter_embed(miss_texts, emb_model, keys)
                if got and len(got) == len(miss_texts):
                    break
                got = None
                time.sleep(3 + _attempt * 7)
            if got and len(got) == len(missing_idx):
                for i, v in zip(missing_idx, got):
                    emb_map[hashes[i]] = v
        vectors = [emb_map.get(h) for h in hashes] if engine != "none" else None
        if vectors and not any(vectors):
            vectors = None
        payload = {"docs": docs, "vectors": vectors,
                   "embeddings": ({"model": emb_model, "map": emb_map} if (engine != "none" and emb_map) else None),
                   "embed_model": (emb_model if (engine != "none" and vectors) else None),
                   "built_at": time.time(), "files": n_files}
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        tmp = INDEX_DIR / "chunks.json.tmp"
        tmp.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
        import os
        os.replace(tmp, INDEX_DIR / "chunks.json")  # كتابة ذرية: القارئ لا يرى ملفاً نصف مكتوب
        _load_index(force=True)
        return {"chunks": len(docs), "files": n_files, "semantic": bool(vectors), "busy": False}
    finally:
        with _lock:
            _state["building"] = False


def _load_index(force: bool = False) -> None:
    path = INDEX_DIR / "chunks.json"
    if not path.exists():
        _state.update({"docs": [], "bm25": None, "vectors": None, "mtime": 0.0, "title_tok": []})
        return
    mtime = path.stat().st_mtime
    if not force and mtime == _state.get("mtime"):
        return
    try:
        payload = json.loads(path.read_text("utf-8"))
        docs = payload.get("docs", [])
        bm25 = BM25([tokenize(d["text"]) for d in docs])
        title_tok = [set(tokenize(d.get("title", ""))) for d in docs]
        _state.update({"docs": docs, "bm25": bm25, "vectors": payload.get("vectors"),
                       "embed_model": payload.get("embed_model"), "mtime": mtime,
                       "title_tok": title_tok})
    except Exception as e:
        import logging
        logging.getLogger("rag").warning(f"Failed to load index from {path}: {e}")
        _state.update({"docs": [], "bm25": None, "vectors": None, "mtime": 0.0, "title_tok": []})


def fill_embeddings() -> dict:
    """شفاء ذاتي: يكمل vectors الناقصة فقط (كاش حسب بصمة النص) — بعد انتهاء 429."""
    global _state
    with _lock:
        if _state.get("building"):
            return {"busy": True}
        _state["building"] = True
    try:
        path = INDEX_DIR / "chunks.json"
        if not path.exists():
            return {"skipped": True}
        payload = json.loads(path.read_text("utf-8"))
        docs = payload.get("docs") or []
        if not docs:
            return {"skipped": True}
        engine, emb_model = _embed_engine()
        if engine == "none":
            return {"skipped": True}
        em = payload.get("embeddings") or {}
        if (em.get("model") or "") != emb_model:
            em = {"model": emb_model, "map": {}}
        emap: dict = dict(em.get("map") or {})
        import hashlib
        hashes = [hashlib.md5(d["text"].encode("utf-8")).hexdigest() for d in docs]
        missing_idx = [i for i, h in enumerate(hashes) if h not in emap]
        if not missing_idx:
            payload["embeddings"] = {"model": emb_model, "map": emap}
            payload["vectors"] = [emap.get(h) for h in hashes]
            payload["embed_model"] = emb_model
            tmp = INDEX_DIR / f"chunks_{int(time.time() * 1000)}.tmp"
            tmp.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
            import os
            os.replace(tmp, path)
            _load_index(force=True)
            return {"skipped": False, "semantic": True}
        miss_texts = [docs[i]["text"] for i in missing_idx]
        got = None
        for _ in range(2):
            if engine == "ollama":
                from core.config import load_config
                try:
                    import httpx as _hx
                    rr = _hx.post(load_config().get("ollama_url", "").rstrip("/") + "/api/embed",
                                  json={"model": emb_model, "input": miss_texts}, timeout=600)
                    got = rr.json().get("embeddings") if rr.status_code == 200 else None
                except Exception:
                    got = None
            else:
                from core.config import get_model_key
                from core.llm import openrouter_embed
                keys = [get_model_key("openrouter", emb_model, load_config()),
                        load_config().get("api_keys", {}).get("openrouter", "")]
                got = openrouter_embed(miss_texts, emb_model, keys)
            if got and len(got) == len(missing_idx):
                break
            got = None
            time.sleep(6)
        if not got:
            return {"skipped": False, "semantic": False}
        for i, v in zip(missing_idx, got):
            emap[hashes[i]] = v
        payload["embeddings"] = {"model": emb_model, "map": emap}
        payload["vectors"] = [emap.get(h) for h in hashes]
        payload["embed_model"] = emb_model
        tmp = INDEX_DIR / f"chunks_{int(time.time() * 1000)}.tmp"
        tmp.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
        import os
        os.replace(tmp, path)
        _load_index(force=True)
        return {"skipped": False, "semantic": True}
    except Exception as e:
        return {"error": str(e)}
    finally:
        with _lock:
            _state["building"] = False


def is_building() -> bool:
    return bool(_state.get("building"))


def stats() -> dict:
    _load_index()
    return {"chunks": len(_state["docs"]), "semantic": bool(_state.get("vectors")),
            "building": is_building()}


# ---------------------------------------------------------------- بحث دلالي اختياري (Ollama أو OpenRouter مجاناً)
def _embed_engine() -> tuple[str, str]:
    """يرجع (المحرك، النموذج): ollama | openrouter | none حسب الإعدادات والتوفر."""
    from core.config import load_config, get_model_key, _ollama_models
    cfg = load_config()
    emb = cfg.get("embed") or {}
    want = (emb.get("provider") or "auto").lower()
    or_model = emb.get("model") or "nvidia/nemotron-3-embed-1b:free"
    or_key = get_model_key("openrouter", or_model, cfg)
    if want == "openrouter":
        return ("openrouter", or_model) if or_key else ("none", "")
    if want == "ollama":
        url = cfg.get("ollama_url", "").rstrip("/")
        if url and _ollama_models(url):
            model = emb.get("model") or emb.get("embed_model") or cfg.get("embed_model") or "nomic-embed-text"
            return ("ollama", model)
        return ("none", "")
    # auto: Ollama أولاً (محلي وأسرع) وإلا OpenRouter مجاناً
    url = cfg.get("ollama_url", "").rstrip("/")
    if url and _ollama_models(url):
        model = emb.get("model") or emb.get("embed_model") or cfg.get("embed_model") or "nomic-embed-text"
        return ("ollama", model)
    if or_key:
        return ("openrouter", or_model)
    return ("none", "")


def _embed_query(text: str) -> list[float] | None:
    engine, model = _embed_engine()
    if engine == "none":
        return None
    if engine == "ollama":
        from core.config import load_config
        cfg = load_config()
        url = cfg.get("ollama_url", "").rstrip("/")
        try:
            import httpx
            r = httpx.post(url + "/api/embed", json={"model": model, "input": [text]}, timeout=30)
            if r.status_code == 200:
                embs = r.json().get("embeddings")
                if embs:
                    return embs[0]
        except Exception:
            pass
        return None
    from core.config import load_config, get_model_key
    from core.llm import openrouter_embed
    cfg = load_config()
    keys = [get_model_key("openrouter", model, cfg), cfg.get("api_keys", {}).get("openrouter", "")]
    embs = openrouter_embed([text], model, keys)
    return embs[0] if embs else None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def _norm(vals: list[float]) -> list[float]:
    """تطبيع بقسمة على الأقصى — يحافظ على النسب الحقيقية بين النتائج."""
    mx = max(vals) if vals else 0.0
    if mx <= 1e-9:
        return [0.0 for _ in vals]
    return [v / mx for v in vals]


# ---------------------------------------------------------------- استرجاع
def search(query: str, k: int = 6, min_score: float = 0.12) -> list[dict]:
    """يرجع أفضل k مقاطع مطابقة مع نتيجة مدمجة (كلمات + دلالي إن توفر)."""
    _load_index()
    docs: list[dict] = _state["docs"]
    bm25: BM25 | None = _state["bm25"]
    if not docs or bm25 is None:
        return []
    q = tokenize(query)
    if not q:
        return []
    kw = _norm(bm25.get_scores(q))
    vectors = _state.get("vectors")
    sem: list[float] | None = None
    if vectors:
        qv = _embed_query(query)
        if qv:
            sem = _norm([_cosine(qv, vec) if vec else 0.0 for vec in vectors[:len(docs)]])
    # Filename/extension matching: «ملف Python» should find .py files even when
    # the body never contains the word "Python" (keyword-only fallback).
    ext_alias = {"python": "py", "word": "docx", "excel": "xlsx", "spreadsheet": "xlsx",
                 "powerpoint": "pptx", "slides": "pptx", "text": "txt", "markdown": "md",
                 "javascript": "js", "code": "py", "csv": "csv", "pdf": "pdf"}
    source_tok: list[set] = _state.get("source_tok") or []
    if not source_tok:
        source_tok = [set(tokenize(f"{d.get('source','')} {d.get('title','')}")) for d in docs]
    combined: list[tuple[float, int]] = []
    title_tok: list[set] = _state.get("title_tok") or [set() for _ in docs]
    q_set = set(q)
    for i in range(len(docs)):
        title_bonus = 0.22 * min(1.0, sum(1 for t in q_set if t in title_tok[i]) / 2)
        src_hits = sum(1 for t in q_set
                       if t in source_tok[i] or (ext_alias.get(t) and ext_alias[t] in source_tok[i]))
        source_bonus = 0.26 * min(1.0, src_hits / 2)
        s = 0.62 * kw[i] + (0.38 * sem[i] if sem else 0.0) + title_bonus + source_bonus
        combined.append((s, i))
    combined.sort(reverse=True)
    out: list[dict] = []
    seen_texts: set[str] = set()
    for score, i in combined[: k * 3]:
        if len(out) >= k:
            break
        if score < min_score:
            break
        d = docs[i]
        key = d["text"][:80]
        if key in seen_texts:
            continue
        seen_texts.add(key)
        out.append({**d, "score": round(score, 4)})
    return out


def build_context(query: str, k: int = 6) -> tuple[str, list[dict]]:
    """يبني بلوك السياق [S1]..[Sn] + قائمة المصادر الموحّدة."""
    hits = search(query, k=k)
    if not hits:
        return "", []
    lines = ["=== مقاطع من قاعدة معرفة الفريق وملفات الطالب (استند إليها واستشهد برقمها) ==="]
    sources: list[dict] = []
    for i, h in enumerate(hits, 1):
        lines.append(f"[S{i}] (المصدر: {h['title']} — {h['source']})\n{h['text']}")
        src = {"ref": f"S{i}", "title": h["title"], "source": h["source"]}
        if h["source"].startswith("http"):
            src["url"] = h["source"]
        sources.append(src)
    return "\n\n".join(lines), sources


def build_university_context(query: str, k: int = 6) -> tuple[str, list[dict]]:
    """يبني بلوك سياق من ملفات الجامعة المرفوعة (المادة الخاصة بالطالب) بنفس صيغة [S1]..[Sn].
    يُستدعى من المنسّق عند الحاجة لاسترجاع محتوى المواد الدراسية الفعلية.
    """
    from . import university_ingest as ui
    hits = ui.search_university(query, k=k)
    if not hits:
        return "", []
    lines = ["=== مقاطع من موادك الدراسية (جامعة سفنكس — المستوى الثالث الترم الأول) (استند إليها واستشهد برقمها) ==="]
    sources: list[dict] = []
    for i, h in enumerate(hits, 1):
        md = h.get("metadata") or {}
        # بادئة U لتجنب التصادم مع ترقيم S1..Sn الخاص بفهرس RAG العام.
        ref = f"U{i}"
        lines.append(f"[{ref}] (المصدر: {h.get('title','')} — {md.get('source_rel','')})\n{h.get('text','')}")
        sources.append({
            "ref": ref,
            "title": h.get("title", ""),
            "source": h.get("source", ""),
            "metadata": md,
        })
    return "\n\n".join(lines), sources
