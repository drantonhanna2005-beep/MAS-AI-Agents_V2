"""ترجمة احترافية بمحركين احتياطيين:

1) النموذج اللغوي المُعد (Ollama/Groq/OpenRouter/Gemini) — الأدق سياقياً،
   ويحافظ على تنسيق Markdown والجداول والروابط ومراجع [S1]/[W1].
2) محرك Google Translate المجاني (بدون مفتاح) كبديل عند غياب نموذج.

القواعد: تقسيم النص الطويل على حدود الفقرات، لا يُرجع أبداً نصاً فارغاً —
وإن فشل المحركان يُرفع خطأ برسالة عربية واضحة.
"""
from __future__ import annotations

import html
import threading
import httpx

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}

_LANG_NAMES = {"en": "English", "ar": "العربية الفصحى الواضحة"}
_SUPPORTED = ("ar", "en")
_QCACHE: dict = {}
_QCACHE_LOCK = threading.Lock()


def _split(text: str, size: int = 1800) -> list[str]:
    parts: list[str] = []
    cur = ""
    for para in text.split("\n\n"):
        if len(cur) + len(para) + 2 <= size:
            cur += ("\n\n" + para) if cur else para
            continue
        if cur:
            parts.append(cur)
            cur = ""
        while len(para) > size:  # فقرة عملاقة → تقطيع قسري على حدود كلمات
            cut = para.rfind(" ", 0, size)
            cut = cut if cut >= size // 2 else size
            parts.append(para[:cut])
            para = para[cut:].lstrip()
        cur = para
    if cur:
        parts.append(cur)
    return parts or [text]


def llm_translate(text: str, target: str, cfg: dict, prov: dict) -> str | None:
    """ترجمة بالنموذج اللغوي — يرجع None لو لا يوجد مزود، ويرفع LLMError لو فشل الاتصال."""
    if prov.get("provider") == "offline":
        return None
    from core.llm import complete
    model = prov.get("model") or (cfg.get("main_models") or {}).get(prov.get("provider", ""))
    from core.config import get_model_key
    system = (
        f"You are a professional translator. Translate the user's text into {_LANG_NAMES.get(target, target)} "
        "with expert accuracy. STRICT RULES: keep Markdown formatting, tables, code blocks, URLs, "
        "and citation markers like [S1] or [W1] exactly as they are (never translate the markers). "
        "Do not add any explanation, notes, or the original text — output ONLY the translation."
    )
    out: list[str] = []
    for part in _split(text):
        _, content = complete(
            prov["provider"], model,
            [{"role": "system", "content": system}, {"role": "user", "content": part}],
            api_key=get_model_key(prov["provider"], model, cfg),
            ollama_url=cfg.get("ollama_url", ""),
            temperature=0.1,
        )
        if not content.strip():
            return None
        out.append(content.strip())
    return "\n\n".join(out)


def google_translate(text: str, target: str) -> str:
    """محرك جوجل المجاني (بدون مفتاح) — بمحاولتين عند 429 العابر."""
    import time
    out: list[str] = []
    for part in _split(text, size=600):
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                r = httpx.get(
                    "https://translate.googleapis.com/translate_a/single",
                    params={"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": part},
                    headers=_UA, timeout=20,
                )
                r.raise_for_status()
                data = r.json()
                sentences = data[0] if isinstance(data, list) and data else []
                seg = "".join((s[0] or "") for s in sentences if isinstance(s, list) and s and s[0])
                if not seg.strip():
                    raise ValueError("empty translation segment")
                out.append(seg)
                last_exc = None
                break
            except Exception as e:
                last_exc = e
                if attempt == 0:
                    time.sleep(1.2)
        if last_exc:
            raise last_exc
    return "\n\n".join(out)


def mymemory_translate(text: str, target: str) -> str:
    """محرك MyMemory المجاني (بدون مفتاح) — احتياط ثالث، حد يومي ~5000 حرف مجهول."""
    src = "en" if target == "ar" else "ar"
    out: list[str] = []
    for part in _split(text, size=480):
        r = httpx.get(
            "https://api.mymemory.translated.net/get",
            params={"q": part, "langpair": f"{src}|{target}"},
            headers=_UA, timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        status = str(data.get("responseStatus", ""))
        txt = (data.get("responseData") or {}).get("translatedText") or ""
        txt = html.unescape(txt)
        if status not in ("200", "200.0") or not txt.strip():
            raise ValueError(str(data.get("responseDetails") or "empty result"))
        out.append(txt)
    return "\n\n".join(out)


def quick_translate(text: str, target: str) -> str | None:
    """ترجمة سريعة بلا نموذج لغوي (جوجل ثم MyMemory) مع كاش — لاستعلامات البحث ثنائية اللغة."""
    text = (text or "").strip()
    if not text or target not in _SUPPORTED:
        return None
    ck = (target, text)
    with _QCACHE_LOCK:
        if ck in _QCACHE:
            return _QCACHE[ck]
    out = None
    try:
        out = google_translate(text, target)
    except Exception:
        try:
            out = mymemory_translate(text, target)
        except Exception:
            out = None
    if out:
        with _QCACHE_LOCK:
            if len(_QCACHE) > 200:
                _QCACHE.clear()
            _QCACHE[ck] = out
    return out


def translate(text: str, target: str, cfg: dict | None = None, prov: dict | None = None) -> dict:
    """نقطة الدخول — يرجع {"translated": str, "engine": "llm"|"google"} أو يرفع خطأ مفهوماً."""
    text = (text or "").strip()
    if target not in _SUPPORTED:
        target = "en"
    if not text:
        raise ValueError("لا يوجد نص للترجمة.")
    if cfg is None or prov is None:
        from core.config import load_config, resolve_provider
        cfg = cfg or load_config()
        prov = prov or resolve_provider(cfg)
    # 1) النموذج اللغوي (الأدق)
    try:
        res = llm_translate(text, target, cfg, prov)
        if res:
            return {"translated": res, "engine": "llm"}
    except Exception:
        pass
    # 2) Gemini مباشرة (مفتاح المستخدم — ثابت ومجاني)
    gk = (cfg.get("api_keys") or {}).get("gemini", "")
    if gk:
        try:
            from core.llm import complete
            gm = (cfg.get("main_models") or {}).get("gemini") or "gemini-2.0-flash"
            sys_p = (f"You are a professional translator. Translate the user's text into {_LANG_NAMES[target]} "
                     "with expert accuracy. Keep Markdown formatting, tables, URLs, and [S1]/[W1] markers "
                     "exactly as they are. Output ONLY the translation.")
            parts = _split(text)
            out = []
            for part in parts:
                _, c = complete("gemini", gm,
                                [{"role": "system", "content": sys_p}, {"role": "user", "content": part}],
                                api_key=gk, ollama_url=cfg.get("ollama_url", ""), temperature=0.1)
                if not (c or "").strip():
                    out = []
                    break
                out.append(c.strip())
            if out and len(out) == len(parts):
                return {"translated": "\n\n".join(out), "engine": "gemini"}
        except Exception:
            pass
    # 3) محرك جوجل المجاني
    try:
        return {"translated": google_translate(text, target), "engine": "google"}
    except Exception:
        pass
    # 4) محرك MyMemory المجاني
    try:
        return {"translated": mymemory_translate(text, target), "engine": "mymemory"}
    except Exception as e:
        raise RuntimeError(
            "تعذرت الترجمة: لا يوجد نموذج لغوي مُعد والمحركان المجانيان غير متاحين (تحقق من الإنترنت). "
            f"تفاصيل: {e}"
        ) from e
