"""Lazy Gemini client so FastAPI can start even if google-genai loads slowly."""

import os
from functools import lru_cache

from dotenv import load_dotenv

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(_BACKEND_DIR, ".env"))
load_dotenv(os.path.join(os.path.dirname(_BACKEND_DIR), ".env"))


@lru_cache(maxsize=1)
def get_gemini_client():
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Add it to backend/.env")
    return genai.Client(api_key=api_key)


def get_genai_types():
    from google.genai import types

    return types
