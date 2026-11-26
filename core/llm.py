"""عميل LLM موحّد (Streaming) — Ollama محلي + مزودات OpenAI-compatible مجانية.

يُخرج أحداثاً موحدة: {"type": "content"|"thinking", "text": str}
- thinking: نص التفكير العميق (من نماذج reasoning أو من تعليمات [[THINKING]])
- عميل واحد لكل المزودات → بسيط وسهل الصيانة وبدون أي SDK خارجي (httpx فقط).
"""
from __future__ import annotations

import base64
import json
from collections.abc import Iterator

import httpx

OPENAI_BASES = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    # مزود Anthropic (Claude) عبر بوابة متوافقة مع OpenAI — تحقق من عمله: توليد + بث + صور ✓
    "anthropic": "https://api.mwapi.dev/v1",
}

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


class LLMError(RuntimeError):
    """خطأ في استدعاء النموذج مع رسالة عربية مفهومة."""


def _friendly_error(provider: str, status: int | None, body: str) -> str:
    if status == 401 or status == 403:
        return f"مفتاح {provider} غير صالح أو منتهي — راجع الإعدادات (⚙️)."
    if status == 429:
        return f"تجاوزت حدود الاستخدام المجاني مؤقتاً في {provider} — انتظر قليلاً أو جرّب مزوداً آخر."
    if status == 404:
        return f"النموذج غير متاح لهذا المفتاح — غيّر اسم النموذج من الإعدادات ({provider})."
    if status in (500, 502, 503, 504):
        return (f"{provider} مشغول أو غير متاح مؤقتاً (خطأ {status}). أعد المحاولة بعد لحظات "
                f"أو اختر مزوداً آخر من الإعدادات (⚙️).")
    snippet = (body or "")[:350].replace("\n", " ")
    return f"خطأ من {provider} (حالة {status}): {snippet}"


# ------------------------------------------------------------------ Ollama
def _ollama_stream(ollama_url: str, model: str, messages: list[dict],
                   temperature: float, images: list[str]) -> Iterator[dict]:
    url = ollama_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature},
    }
    if images:  # صور بصيغة data URL — يحولها لـ base64 خام يتوقعه Ollama
        b64_list = [i.split(",", 1)[1] for i in images if "," in i]
        payload["messages"] = [
            ({**m, "images": b64_list} if m.get("role") == "user" and i == len(messages) - 1 else m)
            for i, m in enumerate(messages)
        ]
    try:
        with httpx.stream("POST", url, json=payload, timeout=httpx.Timeout(20, read=300)) as r:
            if r.status_code != 200:
                body = r.read().decode("utf-8", "ignore")
                raise LLMError(_friendly_error("Ollama", r.status_code, body))
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except Exception:
                    continue
                msg = chunk.get("message", {}) or {}
                th = msg.get("thinking")
                if th:
                    yield {"type": "thinking", "text": th}
                c = msg.get("content")
                if c:
                    yield {"type": "content", "text": c}
                if chunk.get("error"):
                    raise LLMError(f"خطأ من Ollama: {chunk['error']}")
    except httpx.HTTPError as e:
        raise LLMError(f"تعذر الاتصال بخادم Ollama على {ollama_url} — تأكد أنه يعمل (ollama serve). تفاصيل: {e}") from e


# ------------------------------------------------------------------ Gemini الأصلي (بث + تفكير + صور)
def _gemini_stream(model: str, messages: list[dict], temperature: float,
                   api_key: str, images: list[str]) -> Iterator[dict]:
    """المزود الأصلي Gemini: نظام تعليمات + محادثة متعددة الأدوار + صور + تفكير."""
    sys_texts = [m.get("content", "") for m in messages if m.get("role") == "system"]
    contents: list[dict] = []
    for m in messages:
        if m.get("role") == "system":
            continue
        role = "user" if m.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})
    # الصور تُرفق بآخر رسالة مستخدم (السؤال الحالي) — لا برسالة قديمة في التاريخ
    imgs = [i for i in (images or []) if i.startswith("data:")]
    if imgs:
        last_user = next((i for i in range(len(contents) - 1, -1, -1) if contents[i]["role"] == "user"), None)
        if last_user is not None:
            img_parts: list[dict] = []
            for du in imgs:
                try:
                    head, b64 = du.split(",", 1)
                    mime = head.split(":", 1)[1].split(";", 1)[0] or "image/png"
                except Exception:
                    continue
                # Gemini rejects malformed/empty inline image data; skip instead of failing the whole request.
                if not b64 or not mime.startswith("image/"):
                    continue
                img_parts.append({"inlineData": {"mimeType": mime, "data": b64}})
            if img_parts:
                contents[last_user]["parts"] = img_parts + contents[last_user]["parts"]
    body: dict = {"contents": contents, "generationConfig": {"temperature": temperature}}
    if sys_texts:
        body["systemInstruction"] = {"parts": [{"text": "\n\n".join(sys_texts)}]}
    url = f"{GEMINI_BASE}/models/{model}:streamGenerateContent?alt=sse"
    try:
        with httpx.stream("POST", url, headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                          json=body, timeout=httpx.Timeout(30, read=300)) as r:
            if r.status_code != 200:
                txt = r.read().decode("utf-8", "ignore")
                raise LLMError(_friendly_error("Gemini", r.status_code, txt))
            for line in r.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                try:
                    j = json.loads(line[5:])
                except Exception:
                    continue
                if j.get("error"):
                    raise LLMError(_friendly_error("Gemini", j["error"].get("code"), json.dumps(j["error"], ensure_ascii=False)))
                for c in (j.get("candidates") or []):
                    for p in ((c.get("content") or {}).get("parts") or []):
                        t = p.get("text", "")
                        if not t:
                            continue
                        if p.get("thought"):
                            yield {"type": "thinking", "text": t}
                        else:
                            yield {"type": "content", "text": t}
    except httpx.HTTPError as e:
        raise LLMError(f"تعذر الاتصال بخادم Gemini — تحقق من الإنترنت. تفاصيل: {e}") from e


# ------------------------------------------------------------------ OpenAI-compatible
def _openai_stream(provider: str, api_key: str, model: str, messages: list[dict],
                   temperature: float, images: list[str], base: str = "") -> Iterator[dict]:
    base = (base or OPENAI_BASES.get(provider) or "").rstrip("/")
    if not base:
        raise LLMError(f"مزود {provider}: لا يوجد base_url صالح.")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = "http://localhost:8765"
        headers["X-Title"] = "University AI MAS"
    msgs = [dict(m) for m in messages]
    if images:  # صور بصيغة data URL تُمرر كما هي
        last_user = next((i for i in range(len(msgs) - 1, -1, -1) if msgs[i].get("role") == "user"), None)
        if last_user is not None:
            text = msgs[last_user].get("content", "")
            msgs[last_user] = dict(msgs[last_user])
            msgs[last_user]["content"] = [
                {"type": "text", "text": text},
                *[{"type": "image_url", "image_url": {"url": u}} for u in images],
            ]
    payload = {"model": model, "messages": msgs, "stream": True, "temperature": temperature}
    try:
        with httpx.stream("POST", f"{base}/chat/completions", json=payload, headers=headers,
                          timeout=httpx.Timeout(20, read=300)) as r:
            if r.status_code != 200:
                body = r.read().decode("utf-8", "ignore")
                raise LLMError(_friendly_error(provider, r.status_code, body))
            for line in r.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except Exception:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                th = delta.get("reasoning_content") or delta.get("reasoning")
                if th:
                    yield {"type": "thinking", "text": th}
                c = delta.get("content")
                if c:
                    yield {"type": "content", "text": c}
    except httpx.HTTPError as e:
        raise LLMError(f"تعذر الاتصال بخادم {provider} — تحقق من الإنترنت. تفاصيل: {e}") from e


# ------------------------------------------------------------------ الواجهة العامة
def stream_chat(provider: str, model: str, messages: list[dict], *,
                api_key: str = "", ollama_url: str = "http://localhost:11434",
                temperature: float = 0.3, images: list[str] | None = None,
                base_url: str = "") -> Iterator[dict]:
    """images: قائمة روابط data URL للصور (تدعم الرؤية فقط للنماذج القادرة عليها).

    base_url: مطلوب فقط للمزود الاحتياطي «custom» (أي خدمة متوافقة مع OpenAI).
    """
    if provider == "ollama":
        return _ollama_stream(ollama_url, model, messages, temperature, images or [])
    if provider == "gemini":
        if not api_key:
            raise LLMError("لا يوجد مفتاح Gemini — أدخله من الإعدادات (⚙️).")
        return _gemini_stream(model, messages, temperature, api_key, images or [])
    if provider == "custom":
        if not api_key:
            raise LLMError("لا يوجد مفتاح API للمزود الاحتياطي — أدخله من الإعدادات (⚙️).")
        if not (base_url or "").strip():
            raise LLMError("المزود الاحتياطي يحتاج Base URL (مثل https://api.example.com/v1).")
        return _openai_stream("custom", api_key, model, messages, temperature, images or [],
                              base=base_url)
    if provider in OPENAI_BASES:
        if not api_key:
            raise LLMError(f"لا يوجد مفتاح API لمزود {provider} — أدخله من الإعدادات (⚙️).")
        return _openai_stream(provider, api_key, model, messages, temperature, images or [],
                              base=base_url)
    raise LLMError(f"مزود غير معروف: {provider}")


def complete(provider: str, model: str, messages: list[dict], **kw) -> tuple[str, str]:
    """استدعاء غير متدفق — يرجع (thinking, content). للراوتر والتصنيف السريع."""
    thinking, content = [], []
    for ev in stream_chat(provider, model, messages, **kw):
        (thinking if ev["type"] == "thinking" else content).append(ev["text"])
    return "".join(thinking), "".join(content)


def file_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


# ------------------------------------------------------------------ الصوت: Whisper (STT) + TTS + Embeddings
GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
OR_TTS_URL = "https://openrouter.ai/api/v1/audio/speech"
OR_EMBED_URL = "https://openrouter.ai/api/v1/embeddings"


def groq_transcribe(data: bytes, filename: str, model: str, api_key: str) -> str:
    """تحويل الصوت لنص عبر Groq Whisper — سريع جداً ودقيق للعربية. يرفع LLMError عند الفشل."""
    if not api_key:
        raise LLMError("تحويل الصوت يحتاج مفتاح Groq مجاني (console.groq.com) في ⚙️ الإعدادات.")
    files = {"file": (filename or "audio.webm", data)}
    form = {"model": model, "temperature": "0", "response_format": "json"}
    try:
        r = httpx.post(GROQ_STT_URL, headers={"Authorization": f"Bearer {api_key}"},
                       files=files, data=form, timeout=120)
    except httpx.HTTPError as e:
        raise LLMError(f"تعذر الاتصال بخدمة تحويل الصوت: {e}") from e
    if r.status_code != 200:
        raise LLMError(_friendly_error("Groq Whisper", r.status_code, r.text))
    return (r.json().get("text") or "").strip()


def groq_transcribe_verbose(data: bytes, filename: str, model: str, api_key: str) -> dict:
    """Whisper مع مقاطع زمنية (verbose_json) — نستخدمها لتقسيم المتحدثين حسب الوقفات.

    ملاحظة صادقة: Whisper لا يفرز المتحدثين acoustically. نعيد المقاطع الزمنية فقط،
    والعميل يقدّر تبدّل المتحدث من الوقفات الطويلة ويسمح للمستخدم بتعديل التسميات.
    """
    if not api_key:
        raise LLMError("تحويل الصوت يحتاج مفتاح Groq مجاني (console.groq.com) في ⚙️ الإعدادات.")
    files = {"file": (filename or "audio.webm", data)}
    form = {"model": model, "temperature": "0", "response_format": "verbose_json",
            "timestamp_granularities[]": "segment"}
    try:
        r = httpx.post(GROQ_STT_URL, headers={"Authorization": f"Bearer {api_key}"},
                       files=files, data=form, timeout=120)
    except httpx.HTTPError as e:
        raise LLMError(f"تعذر الاتصال بخدمة تحويل الصوت: {e}") from e
    if r.status_code != 200:
        raise LLMError(_friendly_error("Groq Whisper", r.status_code, r.text))
    d = r.json()
    segments = []
    for s in d.get("segments") or []:
        t = (s.get("text") or "").strip()
        if t:
            segments.append({"start": float(s.get("start") or 0), "end": float(s.get("end") or 0),
                             "text": t})
    return {"text": (d.get("text") or "").strip(), "segments": segments}


def openrouter_tts(text: str, model: str, voice: str, api_key: str) -> bytes:
    """نص → صوت حقيقي (mp3) عبر OpenRouter. يرفع LLMError عند الفشل."""
    if not api_key:
        raise LLMError("الصوت الحقيقي يحتاج مفتاح OpenRouter مجاني في ⚙️ الإعدادات.")
    payload: dict = {"model": model, "input": text[:1200]}
    if voice:
        payload["voice"] = voice
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
               "HTTP-Referer": "http://localhost:8765", "X-OpenRouter-Title": "University AI MAS"}
    try:
        r = httpx.post(OR_TTS_URL, headers=headers, json=payload, timeout=120)
    except httpx.HTTPError as e:
        raise LLMError(f"تعذر الاتصال بخدمة الصوت: {e}") from e
    if r.status_code != 200:
        raise LLMError(_friendly_error("OpenRouter TTS", r.status_code, r.text))
    if not r.content:
        raise LLMError("خدمة الصوت رجعت ملفاً فارغاً — جرّب نموذج TTS آخر من الإعدادات.")
    return r.content


def gemini_transcribe(data: bytes, mime: str, api_key: str, model: str = "gemini-flash-lite-latest") -> str:
    """تحويل صوت → نص عبر Gemini (يفهم الصوت مباشرة بدقة عالية للعربية). يرفع LLMError عند الفشل."""
    if not api_key:
        raise LLMError("تحويل الصوت يحتاج مفتاح Gemini أو Groq مجاني في ⚙️ الإعدادات.")
    payload = {
        "contents": [{
            "parts": [
                {"text": "Transcribe this audio verbatim in its original language (Arabic or English). "
                         "Return ONLY the transcription text, no commentary, no quotes."},
                {"inlineData": {"mimeType": mime or "audio/wav", "data": base64.b64encode(data).decode("ascii")}},
            ]
        }],
        "generationConfig": {"temperature": 0},
    }
    try:
        r = httpx.post(f"{GEMINI_BASE}/models/{model}:generateContent",
                       headers={"x-goog-api-key": api_key}, json=payload, timeout=180)
    except httpx.HTTPError as e:
        raise LLMError(f"تعذر الاتصال بخدمة Gemini للصوت: {e}") from e
    if r.status_code != 200:
        raise LLMError(_friendly_error("Gemini STT", r.status_code, r.text))
    candidates = r.json().get("candidates") or []
    if not candidates:
        prompt_feedback = r.json().get("promptFeedback")
        raise LLMError(f"لم يرجع Gemini أي نص: {prompt_feedback or 'محتوى محجوب'}")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


def gemini_extract_document(data: bytes, mime: str, api_key: str,
                            model: str = "gemini-flash-lite-latest") -> str:
    """استخراج نص من مستند ممسوح/صورة PDF عبر Gemini (OCR حقيقي) عند فشل pypdf."""
    if not api_key:
        raise LLMError("OCR يحتاج مفتاح Gemini مجاني في ⚙️ الإعدادات.")
    payload = {
        "contents": [{
            "parts": [
                {"text": "Extract ALL readable text from this document exactly as written, preserving "
                         "headings, tables (use | between cells), numbers and the original language. "
                         "If it is a scanned document, perform OCR. Return only the extracted text."},
                {"inlineData": {"mimeType": mime or "application/pdf",
                                "data": base64.b64encode(data).decode("ascii")}},
            ]
        }],
        "generationConfig": {"temperature": 0},
    }
    try:
        r = httpx.post(f"{GEMINI_BASE}/models/{model}:generateContent",
                       headers={"x-goog-api-key": api_key}, json=payload, timeout=180)
    except httpx.HTTPError as e:
        raise LLMError(f"تعذر الاتصال بخدمة Gemini لاستخراج المستند: {e}") from e
    if r.status_code != 200:
        raise LLMError(_friendly_error("Gemini OCR", r.status_code, r.text))
    try:
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except Exception as e:
        raise LLMError(f"رد غير متوقع من Gemini OCR: {e}") from e


def openrouter_embed(texts: list[str], model: str, keys: list[str] | str) -> list[list[float]] | None:
    """بحث دلالي مجاني بدون Ollama — يجرّب كل المفاتيح المتاحة بالترتيب ويقسم الدفعات تلقائياً."""
    key_list = [keys] if isinstance(keys, str) else list(keys)
    key_list = [k.strip() for k in key_list if k and k.strip()]
    if not key_list or not texts:
        return None
    import time as _t
    headers_common = {"Content-Type": "application/json",
                      "HTTP-Referer": "http://localhost:8765", "X-OpenRouter-Title": "University AI MAS"}
    all_embs: list = []
    BS = 24
    for i in range(0, len(texts), BS):
        batch = texts[i:i + BS]
        got = None
        for key in dict.fromkeys(key_list):
            try:
                r = httpx.post(OR_EMBED_URL, headers={"Authorization": f"Bearer {key}", **headers_common},
                               json={"model": model, "input": batch, "encoding_format": "float"},
                               timeout=httpx.Timeout(30, read=180))
                if r.status_code == 200:
                    data = r.json().get("data") or []
                    embs = [d.get("embedding") for d in data]
                    if embs and all(embs) and len(embs) == len(batch):
                        got = embs
                        break
            except Exception:
                continue
        if not got:
            return None
        all_embs.extend(got)
        if i + BS < len(texts):
            _t.sleep(0.6)
    return all_embs if len(all_embs) == len(texts) else None
