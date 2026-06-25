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
