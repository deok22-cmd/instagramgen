"""설정 로딩 (config/settings.yaml 선택적 + 기본값 + 환경변수).

AI 프로바이더는 provider 추상화: 기본 gemini, openai 대체 가능.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# provider 별 기본 텍스트 모델 (settings 로 override 가능)
DEFAULT_TEXT_MODEL = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
}

_DEFAULTS: dict[str, Any] = {
    "ai": {"provider": "gemini"},          # gemini | openai
    "brand": {"handle": "", "default_format": "square_basic"},
    "gemini": {
        "api_key_env": "GEMINI_API_KEY",   # 없으면 GOOGLE_API_KEY 도 시도
        "api_key": "",
        "text_model": "",                  # 빈값 → DEFAULT_TEXT_MODEL
        "image_model": "imagen-3.0-generate-002",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "api_key": "",
        "text_model": "",
        "image_model": "gpt-image-1",
    },
    "paths": {"output_dir": "output", "cache_dir": "assets/cache"},
}


def _merge(base: dict, over: dict | None) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings() -> dict[str, Any]:
    p = PROJECT_ROOT / "config" / "settings.yaml"
    data: dict = {}
    if p.exists():
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return _merge(_DEFAULTS, data)


def ai_provider(settings: dict | None = None) -> str:
    s = settings or load_settings()
    return (s.get("ai", {}).get("provider") or "gemini").lower()


def provider_api_key(provider: str, settings: dict | None = None) -> str:
    """환경변수 우선(gemini는 GOOGLE_API_KEY 도 시도), 없으면 settings."""
    s = settings or load_settings()
    sec = s.get(provider, {}) or {}
    env_name = sec.get("api_key_env", "")
    val = os.environ.get(env_name, "") if env_name else ""
    if not val and provider == "gemini":
        val = os.environ.get("GOOGLE_API_KEY", "")
    return val or sec.get("api_key", "") or ""


def text_model(provider: str, settings: dict | None = None,
                override: str | None = None) -> str:
    if override:
        return override
    s = settings or load_settings()
    return (s.get(provider, {}) or {}).get("text_model") \
        or DEFAULT_TEXT_MODEL.get(provider, "")


def missing_key_help(provider: str, settings: dict | None = None) -> str:
    s = settings or load_settings()
    env_name = (s.get(provider, {}) or {}).get("api_key_env", "")
    alt = " (또는 GOOGLE_API_KEY)" if provider == "gemini" else ""
    return (
        f"{provider} API 키가 없습니다. 환경변수 {env_name}{alt} 를 설정하거나 "
        f"config/settings.yaml 의 {provider}.api_key 에 넣으세요.\n"
        f'  PowerShell:  $env:{env_name} = "..."\n'
        "  (캐시된 응답이 있으면 키 없이도 동작합니다.)"
    )
