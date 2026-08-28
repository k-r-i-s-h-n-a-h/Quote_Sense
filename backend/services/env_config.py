"""Load backend/.env and provide lazy API clients (avoids crash on import when keys missing)."""
import json
import os
import time

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, "..", ".env")
DEBUG_LOG_PATH = os.path.abspath(os.path.join(BASE_DIR, "../../.cursor/debug-b7c34a.log"))

load_dotenv(ENV_PATH, override=True)

_gemini_client = None
_supabase_client = None


def _agent_debug_log(location, message, data=None, hypothesis_id=None, run_id="pre-fix"):
    # region agent log
    try:
        os.makedirs(os.path.dirname(DEBUG_LOG_PATH), exist_ok=True)
        with open(DEBUG_LOG_PATH, "a") as f:
            f.write(json.dumps({
                "sessionId": "b7c34a",
                "timestamp": int(time.time() * 1000),
                "location": location,
                "message": message,
                "data": data or {},
                "hypothesisId": hypothesis_id,
                "runId": run_id,
            }) + "\n")
    except Exception:
        pass
    # endregion


def _env_file_stats() -> dict:
    try:
        size = os.path.getsize(ENV_PATH)
        with open(ENV_PATH, "rb") as f:
            content = f.read()
        return {
            "path": ENV_PATH,
            "size_on_disk": size,
            "readable_bytes": len(content),
            "corrupted": size > 0 and len(content) == 0,
        }
    except OSError as e:
        return {"path": ENV_PATH, "error": str(e), "corrupted": True}


def env_diagnostics() -> dict:
    stats = _env_file_stats()
    gemini_key = os.getenv("GEMINI_API_KEY") or ""
    supabase_url = os.getenv("SUPABASE_URL") or ""
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    placeholder = gemini_key.startswith("your_") or supabase_url.startswith("https://your-")

    return {
        **stats,
        "gemini_configured": bool(gemini_key) and not gemini_key.startswith("your_"),
        "supabase_configured": bool(supabase_url and supabase_key)
        and not supabase_url.startswith("https://your-"),
        "placeholder_keys": placeholder,
        "missing": [
            k
            for k, v in {
                "GEMINI_API_KEY": gemini_key,
                "SUPABASE_URL": supabase_url,
                "SUPABASE_SERVICE_ROLE_KEY": supabase_key,
            }.items()
            if not v or v.startswith("your_") or v.startswith("https://your-")
        ],
    }


DEFAULT_EXTRACT_MODEL = "gemini-3.5-flash"
DEFAULT_COMPARE_MODEL = "gemini-3.7-flash"


def _gemini_model(env_keys: tuple[str, ...], default: str) -> str:
    for key in env_keys:
        raw = (os.getenv(key) or "").strip()
        if raw:
            return raw
    return default


def gemini_extract_model() -> str:
    """PDF extraction — Flash 3.5 by default (structured JSON, high volume)."""
    return _gemini_model(("GEMINI_EXTRACT_MODEL",), DEFAULT_EXTRACT_MODEL)


def gemini_compare_model() -> str:
    """S6 narrative + chat — Flash 3.7 by default."""
    return _gemini_model(("GEMINI_COMPARE_MODEL",), DEFAULT_COMPARE_MODEL)


def gemini_space_model() -> str:
    """S3 leftover overlay — Flash 3.7; falls back to compare, then extract."""
    return _gemini_model(
        ("GEMINI_SPACE_MODEL", "GEMINI_COMPARE_MODEL"),
        DEFAULT_COMPARE_MODEL,
    )


def gemini_work_model() -> str:
    """S2 leftover work merge — same family as compare unless overridden."""
    return _gemini_model(
        ("GEMINI_WORK_MODEL", "GEMINI_COMPARE_MODEL"),
        DEFAULT_COMPARE_MODEL,
    )


def gemini_is_v3(model: str) -> bool:
    return (model or "").strip().lower().startswith("gemini-3")


def gemini_generate_config(
    types,
    *,
    model: str,
    temperature: float | None = None,
    response_mime_type: str | None = None,
    response_schema=None,
    cached_content=None,
):
    """
    Gemini 3.x often rejects explicit temperature/top_p (including 0.0).
    Omit sampling overrides on 3.x; keep them for 2.5.
    """
    kwargs: dict = {}
    if response_mime_type:
        kwargs["response_mime_type"] = response_mime_type
    if response_schema is not None:
        kwargs["response_schema"] = response_schema
    if cached_content:
        kwargs["cached_content"] = cached_content
    if not gemini_is_v3(model) and temperature is not None:
        kwargs["temperature"] = temperature
    return types.GenerateContentConfig(**kwargs)


def get_gemini_client():
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    diag = env_diagnostics()
    if not diag["gemini_configured"]:
        _agent_debug_log(
            "env_config.py:get_gemini_client",
            "gemini not configured",
            diag,
            hypothesis_id="E",
        )
        raise RuntimeError(
            "GEMINI_API_KEY is missing or invalid. "
            f"Edit {ENV_PATH} — the file may be corrupted (0 readable bytes)."
        )
    from google import genai

    _gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _gemini_client


def get_supabase_client():
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    diag = env_diagnostics()
    if not diag["supabase_configured"]:
        _agent_debug_log(
            "env_config.py:get_supabase_client",
            "supabase not configured",
            diag,
            hypothesis_id="E",
        )
        raise RuntimeError(
            "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing. "
            f"Edit {ENV_PATH} with your Supabase credentials."
        )
    from supabase import create_client

    _supabase_client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )
    return _supabase_client
