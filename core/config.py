"""إعدادات النظام — تحميل/حفظ config.json وكشف المزود المتاح تلقائياً.

المزودات المدعومة (كلها مجانية):
- ollama      : تشغيل محلي 100% بدون أي API key (الأفضل للخصوصية والسرعة)
- groq        : طبقة مجانية سريعة جداً (مفتاح من console.groq.com)
- openrouter  : نماذج مجانية بلاحقة :free (مفتاح من openrouter.ai)
- gemini      : طبقة Google AI Studio المجانية (مفتاح من aistudio.google.com)
- offline     : بدون أي LLM — يجيب من قاعدة المعرفة والملفات المفهرسة + الأدوات الحتمية
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # university-ai-agents/
DATA_DIR = ROOT / "data"                        # ملفات الطالب للتدريب (الدرويفات تُنزل هنا)
UPLOAD_DIR = ROOT / "uploads"                   # مرفقات الشات
INDEX_DIR = ROOT / "index_store"                # فهرس RAG
CONFIG_PATH = ROOT / "config.json"
DB_PATH = ROOT / "history.db"

for _d in (DATA_DIR, UPLOAD_DIR, INDEX_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG: dict = {
    "provider": "auto",           # auto | ollama | groq | anthropic | openrouter | gemini | offline
    "api_keys": {"groq": "", "openrouter": "", "gemini": "", "anthropic": ""},
    "main_models": {
        "ollama": "llama3.1:8b",
        "groq": "openai/gpt-oss-20b",
        "anthropic": "claude-sonnet-4-6",
        "openrouter": "openrouter/free",
        "gemini": "gemini-2.0-flash",
    },
    "router_models": {
        "ollama": "llama3.2:3b",
        "groq": "llama-3.1-8b-instant",
        "anthropic": "claude-haiku-4-5-20251001",
        "openrouter": "openrouter/free",
        "gemini": "gemini-2.0-flash",
    },
    "model_keys": {"openrouter": {}},   # مفتاح خاص لكل نموذج (لو المفاتيح من حسابات مختلفة)
    # مزود احتياطي تلقائي: يُجرّب في نهاية سلسلة المزودات فقط عند فشل/تعطل الأساسي.
    # provider=custom → أي خدمة متوافقة مع OpenAI عبر base_url.
    # provider=openrouter → يستخدم https://openrouter.ai/api/v1 ويتطلب مفتاح sk-or-.
    "fallback": {"enabled": False, "provider": "custom", "base_url": "", "api_key": "", "model": ""},
    "stt": {"model": "whisper-large-v3-turbo"},                                   # تحويل صوت → نص (Groq Whisper)
    "tts": {"model": "heygen/heygen-voice-1-turbo:free", "voice": "nadine"},      # نص → صوت حقيقي (OpenRouter)
    "embed": {"provider": "auto", "model": "nvidia/nemotron-3-embed-1b:free"},   # بحث دلالي مجاني بدون Ollama
    "ollama_url": "http://localhost:11434",
    "temperature": 0.3,
    "deep_think": True,           # عرض "تفكير عميق" قبل الإجابة
    "web_search": True,           # السماح بالبحث في الإنترنت
    "rag_k": 6,                   # عدد المقاطع المسترجعة لكل سؤال
    "embed_model": "nomic-embed-text",
    "max_agents": 2,              # أقصى عدد وكلاء يشاركون في إجابة واحدة
}


def get_model_key(provider: str, model: str, cfg: dict) -> str:
    """مفتاح النموذج: مفتاح خاص بالنموذج (model_keys) إن وجد وإلا مفتاح المزود."""
    mk = (cfg.get("model_keys") or {}).get(provider) or {}
    key = mk.get(model) if isinstance(mk, dict) else None
    if not key:
        api_keys = cfg.get("api_keys") or {}
        key = api_keys.get(provider, "") if isinstance(api_keys, dict) else ""
    return str(key or "").strip()


def get_fallback(cfg: dict) -> dict | None:
    """يرجع إعدادات المزود الاحتياطي الجاهز فقط، أو None إذا لم يكن مكتملاً.

    - provider=openrouter: يحتاج api_key + model (base_url ثابت رسمياً).
    - provider=custom:     يحتاج api_key + model + base_url (خدمة متوافقة مع OpenAI).
    لا نُرجع إعداداً ناقصاً حتى لا نضيّع وقتاً في محاولة فاشلة.
    """
    fb = cfg.get("fallback") or {}
    if not fb.get("enabled"):
        return None
    key = (fb.get("api_key") or "").strip()
    model = (fb.get("model") or "").strip()
    base = (fb.get("base_url") or "").strip().rstrip("/")
    provider = (fb.get("provider") or "custom").strip().lower()
    if provider == "openrouter":
        if not key or not model:
            return None
        return {"provider": "openrouter", "model": model, "key": key,
                "base_url": "https://openrouter.ai/api/v1"}
    if not (key and model and base):
        return None
    return {"provider": "custom", "model": model, "key": key, "base_url": base}


_ENV_KEY_MAP = {
    # متغير بيئة → اسم المزود. أولوية: متغير البيئة يتجاوز config.json
    # حتى يُنشر المشروع بدون أي مفاتيح حقيقية (النشر الآمن على GitHub).
    "GROQ_API_KEY": "groq",
    "OPENROUTER_API_KEY": "openrouter",
    "GEMINI_API_KEY": "gemini",
    "ANTHROPIC_API_KEY": "anthropic",
}


def _env_keys() -> dict:
    import os

    return {prov: os.environ[var].strip()
            for var, prov in _ENV_KEY_MAP.items()
            if os.environ.get(var, "").strip()}


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG_PATH.exists():
        try:
            user = json.loads(CONFIG_PATH.read_text("utf-8"))
            for k, v in user.items():
                if v is not None:
                    if isinstance(cfg.get(k), dict) and isinstance(v, dict):
                        cfg[k].update(v)
                    else:
                        cfg[k] = v
        except Exception:
            pass  # ملف تالف → نرجع للإعدادات الافتراضية
    # مفاتيح من متغيرات البيئة تتجاوز الملف (للنشر على منصات مثل Railway/Render)
    env_keys = _env_keys()
    if env_keys:
        cfg.setdefault("api_keys", {}).update(env_keys)
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
    _OLLAMA_CACHE.update({"at": 0.0})  # إعدادات جديدة → أعد فحص Ollama فوراً


_OLLAMA_CACHE: dict = {"url": None, "at": 0.0, "models": None}
_OLLAMA_TTL = 12.0  # ثوانٍ — يمنع تكرار مهلة الاتصال في كل طلب صحة/رسالة


def _ollama_models(url: str) -> list[str] | None:
    """يرجع قائمة موديلات Ollama لو الخادم شغال، وإلا None (مع كاش قصير)."""
    now = time.time()
    if _OLLAMA_CACHE["url"] == url and (now - _OLLAMA_CACHE["at"]) < _OLLAMA_TTL:
        return _OLLAMA_CACHE["models"]
    models = None
    try:
        import httpx
        r = httpx.get(url.rstrip("/") + "/api/tags", timeout=0.8)
        if r.status_code == 200:
            models = [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        pass
    _OLLAMA_CACHE.update({"url": url, "at": now, "models": models})
    return models


def pick_ollama_model(models: list[str], wanted: str) -> str:
    """يختار أفضل موديل متاح: المطلوب إن وجد، وإلا أقرب موديل مناسب."""
    valid_models = [m for m in (models or []) if isinstance(m, str) and m]
    if not valid_models:
        return wanted or ""
    if wanted and any(m == wanted or m.startswith(wanted + ":") for m in valid_models):
        return next(m for m in valid_models if m == wanted or m.startswith(wanted + ":"))
    wanted_base = wanted.split(":")[0] if wanted else ""
    if wanted_base:
        base_hit = [m for m in valid_models if m == wanted_base or m.startswith(wanted_base + ":") or wanted_base in m.lower()]
        if base_hit:
            return sorted(base_hit)[-1]
    for pref in ("llama3.1", "llama3.2", "qwen2.5", "mistral", "gemma", "llama3", "phi"):
        hit = [m for m in valid_models if pref in m.lower()]
        if hit:
            return sorted(hit)[-1]
    return valid_models[0]


def resolve_provider(cfg: dict) -> dict:
    """يحدد المزود الفعلي المستخدم حسب الإعدادات والتوفر اللحظي."""
    want = (cfg.get("provider") or "auto").lower()
    keys = cfg.get("api_keys") or {}
    main_models = cfg.get("main_models") or DEFAULT_CONFIG["main_models"]
    ollama_url = cfg.get("ollama_url", DEFAULT_CONFIG["ollama_url"])
    ollama_models = _ollama_models(ollama_url) or []
    ollama_up = bool(ollama_models)

    order = [want] if want != "auto" else ["ollama", "groq", "anthropic", "openrouter", "gemini"]
    for p in order:
        if p == "ollama" and ollama_up:
            model = pick_ollama_model(ollama_models, main_models.get("ollama", ""))
            return {"provider": "ollama", "model": model, "available_models": ollama_models,
                    "ollama_url": ollama_url}
        if p == "groq" and keys.get("groq"):
            return {"provider": "groq", "model": cfg["main_models"]["groq"], "available_models": []}
        if p == "openrouter" and keys.get("openrouter"):
            return {"provider": "openrouter", "model": cfg["main_models"]["openrouter"], "available_models": []}
        if p == "anthropic" and keys.get("anthropic"):
            return {"provider": "anthropic", "model": cfg["main_models"].get("anthropic") or "claude-sonnet-4-6", "available_models": []}
        if p == "gemini" and keys.get("gemini"):
            gemini_model = main_models.get("gemini") or DEFAULT_CONFIG["main_models"]["gemini"]
            return {"provider": "gemini", "model": gemini_model, "available_models": ollama_models}

    return {"provider": "offline", "model": "—", "available_models": ollama_models,
            "ollama_up": ollama_up, "ollama_url": ollama_url}


def provider_supports_vision(provider: str, model: str) -> bool:
    m = (model or "").lower()
    if provider == "gemini":
        return True
    if provider == "anthropic":
        # كل موديلات Claude الحديثة تدعم الرؤية (صور)
        return m.startswith("claude")
    if provider == "ollama":
        return any(k in m for k in ("llava", "vision", "bakllava", "moondream", "minicpm-v", "llama3.2-vision", "gemma3", "gemma4", "qwen2.5vl", "qwen-vl", "phi3.5-vision", "phi4-multimodal"))
    # broad heuristic for OpenAI-compatible providers; allow common vision-capable families
    if any(k in m for k in ("gpt-4o", "gpt-4.1", "gpt-4-turbo", "gpt-5", "omni", "vision", "4v", "claude-3", "claude-sonnet-4", "claude-opus-4", "claude-haiku-4", "llama-3.2-vision", "llama-4", "scout", "maverick", "pixtral", "qwen-vl", "qwen2.5-vl", "qwen2-vl", "gemini", "gemma-4", "gemma-3", "gemma-2", "internvl", "minicpm-v", "moondream")):
        return True
    return False
