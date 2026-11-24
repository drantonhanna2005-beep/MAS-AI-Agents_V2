"""إعدادات النظام — config.json محلي أو متغيرات بيئة آمنة.

ترتيب المصادر: القيم الافتراضية < config.json < متغيرات البيئة/.env.
المفاتيح السرية لا تُعاد من هذا الملف إلى واجهة المستخدم؛ نقاط النهاية تُقنّعها.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
UPLOAD_DIR = ROOT / "uploads"
INDEX_DIR = ROOT / "index_store"
CONFIG_PATH = ROOT / "config.json"
DB_PATH = ROOT / "history.db"

for _directory in (DATA_DIR, UPLOAD_DIR, INDEX_DIR):
    _directory.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG: dict = {
    "provider": "auto",
    "api_keys": {"groq": "", "openrouter": "", "gemini": ""},
    "main_models": {
        "ollama": "llama3.1:8b",
        "groq": "openai/gpt-oss-20b",
        "openrouter": "openrouter/free",
        "gemini": "gemini-2.0-flash",
    },
    "router_models": {
        "ollama": "llama3.2:3b",
        "groq": "llama-3.1-8b-instant",
        "openrouter": "openrouter/free",
        "gemini": "gemini-2.0-flash",
    },
    "model_keys": {"openrouter": {}},
    "stt": {"model": "whisper-large-v3-turbo"},
    "tts": {"model": "heygen/heygen-voice-1-turbo:free", "voice": "nadine"},
    "embed": {"provider": "auto", "model": "nvidia/nemotron-3-embed-1b:free"},
    "ollama_url": "http://localhost:11434",
    "temperature": 0.3,
    "deep_think": True,
    "web_search": True,
    "rag_k": 6,
    "embed_model": "nomic-embed-text",
    "max_agents": 2,
}

_ENV_KEYS = {
    "MAS_PROVIDER": ("provider", None),
    "GROQ_API_KEY": ("api_keys", "groq"),
    "OPENROUTER_API_KEY": ("api_keys", "openrouter"),
    "GEMINI_API_KEY": ("api_keys", "gemini"),
    "OLLAMA_URL": ("ollama_url", None),
    "MAS_OLLAMA_MODEL": ("main_models", "ollama"),
    "MAS_GROQ_MODEL": ("main_models", "groq"),
    "MAS_OPENROUTER_MODEL": ("main_models", "openrouter"),
    "MAS_GEMINI_MODEL": ("main_models", "gemini"),
}
_ALLOWED_PROVIDERS = {"auto", "ollama", "groq", "openrouter", "gemini", "offline"}


def _read_dotenv(path: Path | None = None) -> dict[str, str]:
    """Read only supported KEY=VALUE entries; never execute .env as code."""
    values: dict[str, str] = {}
    try:
        for raw in (path or ROOT / ".env").read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            name, separator, value = line.partition("=")
            name = name.strip()
            if not separator or name not in _ENV_KEYS:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[name] = value
    except OSError:
        pass
    return values


def _is_configured_secret(value: str) -> bool:
    value = (value or "").strip()
    lowered = value.lower()
    return bool(value) and not (lowered.startswith("your_") or "placeholder" in lowered or lowered == "changeme")


def _apply_runtime_config(cfg: dict, dotenv: dict[str, str] | None = None) -> None:
    """Apply supported .env/OS values; OS environment takes precedence."""
    values = dotenv if dotenv is not None else _read_dotenv()
    for env_name, (section, child) in _ENV_KEYS.items():
        value = os.environ.get(env_name, values.get(env_name, "")).strip()
        if not value:
            continue
        if section == "api_keys":
            if _is_configured_secret(value):
                cfg[section][child] = value
        elif section == "provider":
            if value.lower() in _ALLOWED_PROVIDERS:
                cfg[section] = value.lower()
        elif child:
            cfg[section][child] = value
        else:
            cfg[section] = value


def _apply_runtime_config_for_test(dotenv: dict[str, str] | None = None) -> dict:
    """Fresh config with runtime overrides; useful for isolated unit tests."""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    _apply_runtime_config(cfg, dotenv)
    return cfg


def get_model_key(provider: str, model: str, cfg: dict) -> str:
    """Return model-specific key if set; otherwise provider key."""
    model_keys = (cfg.get("model_keys") or {}).get(provider) or {}
    key = model_keys.get(model) if isinstance(model_keys, dict) else None
    if not key:
        api_keys = cfg.get("api_keys") or {}
        key = api_keys.get(provider, "") if isinstance(api_keys, dict) else ""
    return str(key or "").strip()


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG_PATH.exists():
        try:
            user = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(user, dict):
                for key, value in user.items():
                    if value is not None:
                        if isinstance(cfg.get(key), dict) and isinstance(value, dict):
                            cfg[key].update(value)
                        else:
                            cfg[key] = value
        except (OSError, ValueError, TypeError):
            # Keep defaults if a local config file is unavailable or malformed.
            pass
    _apply_runtime_config(cfg)
    return cfg


def save_config(cfg: dict) -> None:
    tmp_path = CONFIG_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(CONFIG_PATH)


def _ollama_models(url: str) -> list[str] | None:
    """Return locally available Ollama models, or None if the server is down."""
    try:
        import httpx
        response = httpx.get(url.rstrip("/") + "/api/tags", timeout=1.5)
        if response.status_code == 200:
            models = response.json().get("models") or []
            return [item["name"] for item in models if isinstance(item, dict) and item.get("name")]
    except Exception:
        pass
    return None


def pick_ollama_model(models: list[str], wanted: str) -> str:
    """Choose the requested model or the closest installed model."""
    valid_models = [model for model in (models or []) if isinstance(model, str) and model]
    if not valid_models:
        return wanted or ""
    if wanted and any(model == wanted or model.startswith(wanted + ":") for model in valid_models):
        return next(model for model in valid_models if model == wanted or model.startswith(wanted + ":"))
    wanted_base = wanted.split(":")[0] if wanted else ""
    if wanted_base:
        matches = [model for model in valid_models if model == wanted_base or model.startswith(wanted_base + ":") or wanted_base in model.lower()]
        if matches:
            return sorted(matches)[-1]
    for prefix in ("llama3.1", "llama3.2", "qwen2.5", "mistral", "gemma", "llama3", "phi"):
        matches = [model for model in valid_models if prefix in model.lower()]
        if matches:
            return sorted(matches)[-1]
    return valid_models[0]


def resolve_provider(cfg: dict) -> dict:
    """Select the active configured model provider."""
    wanted = str(cfg.get("provider") or "auto").lower()
    keys = cfg.get("api_keys") or {}
    main_models = cfg.get("main_models") or DEFAULT_CONFIG["main_models"]
    ollama_url = cfg.get("ollama_url", DEFAULT_CONFIG["ollama_url"])
    ollama_models = _ollama_models(ollama_url) or []
    providers = [wanted] if wanted != "auto" else ["ollama", "groq", "openrouter", "gemini"]
    for provider in providers:
        if provider == "ollama" and ollama_models:
            model = pick_ollama_model(ollama_models, main_models.get("ollama", ""))
            return {"provider": "ollama", "model": model, "available_models": ollama_models, "ollama_url": ollama_url}
        if provider == "groq" and keys.get("groq"):
            return {"provider": "groq", "model": main_models.get("groq") or DEFAULT_CONFIG["main_models"]["groq"], "available_models": ollama_models}
        openrouter_model = main_models.get("openrouter") or DEFAULT_CONFIG["main_models"]["openrouter"]
        if provider == "openrouter" and (keys.get("openrouter") or get_model_key("openrouter", openrouter_model, cfg)):
            return {"provider": "openrouter", "model": openrouter_model, "available_models": ollama_models}
        if provider == "gemini" and keys.get("gemini"):
            return {"provider": "gemini", "model": main_models.get("gemini") or DEFAULT_CONFIG["main_models"]["gemini"], "available_models": ollama_models}
    return {"provider": "offline", "model": "—", "available_models": ollama_models,
            "ollama_up": bool(ollama_models), "ollama_url": ollama_url}


def provider_supports_vision(provider: str, model: str) -> bool:
    model_name = (model or "").lower()
    if provider == "gemini":
        return True
    if provider == "ollama":
        return any(key in model_name for key in (
            "llava", "vision", "bakllava", "moondream", "minicpm-v", "llama3.2-vision",
            "gemma3", "gemma4", "qwen2.5vl", "qwen-vl", "phi3.5-vision", "phi4-multimodal",
        ))
    return any(key in model_name for key in (
        "gpt-4o", "gpt-4.1", "gpt-4-turbo", "gpt-5", "omni", "vision", "4v",
        "claude-3", "claude-sonnet-4", "claude-opus-4", "claude-haiku-4",
        "llama-3.2-vision", "llama-4", "scout", "maverick", "pixtral", "qwen-vl",
        "qwen2.5-vl", "qwen2-vl", "gemini", "gemma-3", "internvl", "minicpm-v", "moondream",
    ))
