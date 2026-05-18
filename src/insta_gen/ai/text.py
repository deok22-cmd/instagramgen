"""AI 텍스트 생성 (프로바이더 추상화: gemini 기본 / openai 대체).

기능
----
* expand_keyword     : 키워드/짧은 주제 → 카드뉴스 콘텐츠(정확히 N장)
* summarize_to_slides: 긴 원고 → 의미 있는 N장으로 재구성/압축

설계 메모
---------
* 프롬프트/파싱/캐시는 프로바이더 무관. 호출만 provider 로 분기.
* (provider, model, system, user) 해시로 assets/cache/ai 캐시 →
  같은 입력 재호출 비용 0, 캐시가 있으면 키 없이도 동작(재현/오프라인).
* 응답은 JSON 강제(gemini=response_mime_type / openai=json_object) 후 파싱.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..config import (
    PROJECT_ROOT,
    ai_provider,
    load_settings,
    missing_key_help,
    provider_api_key,
    text_model,
)
from ..models import Content, Slide


class AIError(RuntimeError):
    """AI 단계의 사용자 표시용 오류(키 누락/호출 실패 등)."""


_SYS = (
    "당신은 한국어 인스타그램 카드뉴스 카피라이터입니다. "
    "입력된 사실에만 근거하여 과장이나 허위 없이, 간결하고 가독성 높은 "
    "카드 문구를 작성합니다. 출력은 한국어이며 지정된 JSON 형식만 반환합니다."
)


def _schema(n: int) -> str:
    return (
        f"정확히 {n}장의 슬라이드를 만드세요. 1번=표지(role:cover), "
        f"{n}번=마무리/CTA(role:cta), 그 사이는 본문(role:content).\n"
        "아래 JSON 객체 하나만 반환(설명·코드블록 금지):\n"
        '{"topic":"8자 이내 카테고리",'
        '"caption":"인스타 캡션 2~4문장",'
        '"hashtags":["태그",...(8~12개, # 없이)],'
        '"slides":[{"role":"cover|content|cta",'
        '"title":"22자 이내 핵심 한 줄",'
        '"body":"90자 이내 설명, 없으면 빈 문자열",'
        '"bullets":["25자 이내",...(최대 5개, 없으면 빈 배열)]}]}\n'
        "제목은 짧고 강하게, 본문은 1~2문장. 표지 title은 후킹 카피."
    )


def build_keyword_prompt(keyword: str, n: int) -> tuple[str, str]:
    user = (
        f"주제/키워드: {keyword}\n\n"
        "이 주제로 사람들이 저장하고 싶어지는 정보형 카드뉴스를 "
        "작성하세요.\n" + _schema(n)
    )
    return _SYS, user


def build_summarize_prompt(raw_text: str, n: int,
                           topic_hint: str = "") -> tuple[str, str]:
    hint = f" 주제 힌트: {topic_hint}." if topic_hint else ""
    user = (
        "다음 원고를 인스타 카드뉴스로 재구성하세요. 핵심 정보를 "
        f"빠짐없이 살리되 카드 분량에 맞게 압축합니다.{hint}\n\n"
        f"=== 원고 시작 ===\n{raw_text}\n=== 원고 끝 ===\n\n" + _schema(n)
    )
    return _SYS, user


def cache_key(provider: str, model: str, system: str, user: str) -> str:
    raw = json.dumps({"p": provider, "m": model, "s": system, "u": user},
                     ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _cache_file(key: str) -> Path:
    d = PROJECT_ROOT / "assets" / "cache" / "ai"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


# --- 프로바이더별 호출 -----------------------------------------------------
def _call_gemini(system: str, user: str, model: str, api_key: str) -> dict:
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise AIError("google-genai 패키지가 없습니다: "
                      "pip install google-genai") from e
    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )
        return json.loads(resp.text or "{}")
    except Exception as e:
        raise AIError(f"Gemini 호출 실패: {e}") from e


def _call_openai(system: str, user: str, model: str, api_key: str) -> dict:
    try:
        from openai import OpenAI
    except ImportError as e:
        raise AIError("openai 패키지가 없습니다: pip install openai") from e
    try:
        resp = OpenAI(api_key=api_key).chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception as e:
        raise AIError(f"OpenAI 호출 실패: {e}") from e


_DISPATCH = {"gemini": _call_gemini, "openai": _call_openai}


def generate_json(system: str, user: str, *, model: str | None = None,
                  settings: dict | None = None, refresh: bool = False) -> dict:
    settings = settings or load_settings()
    provider = ai_provider(settings)
    if provider not in _DISPATCH:
        raise AIError(f"알 수 없는 AI 프로바이더: {provider} "
                      "(gemini | openai)")
    resolved_model = text_model(provider, settings, override=model)

    cf = _cache_file(cache_key(provider, resolved_model, system, user))
    if cf.exists() and not refresh:
        return json.loads(cf.read_text(encoding="utf-8"))

    api_key = provider_api_key(provider, settings)
    if not api_key:
        raise AIError(missing_key_help(provider, settings))

    data = _DISPATCH[provider](system, user, resolved_model, api_key)
    cf.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                  encoding="utf-8")
    return data


# --- JSON → Content --------------------------------------------------------
def to_content(data: dict, *, source: str, handle: str = "") -> Content:
    slides: list[Slide] = []
    for s in (data.get("slides") or []):
        b = s.get("bullets") or []
        if isinstance(b, str):
            b = [x.strip() for x in b.split("|") if x.strip()]
        slides.append(Slide(
            title=str(s.get("title", "")).strip(),
            body=str(s.get("body", "")).strip(),
            bullets=[str(x).strip() for x in b if str(x).strip()][:5],
            footer=handle,
        ))
    if not slides:
        raise AIError("AI 응답에 슬라이드가 없습니다.")
    tags = [str(t).lstrip("#").strip()
            for t in (data.get("hashtags") or []) if str(t).strip()]
    return Content(
        topic=str(data.get("topic", "")).strip(),
        slides=slides,
        hashtags=tags,
        caption=str(data.get("caption", "")).strip(),
        source=source,
        language="ko",
    )


def content_to_text(content: Content) -> str:
    """기존 Content(예: HTML 추출) → 요약 입력용 평문 아웃라인."""
    out: list[str] = []
    if content.topic:
        out.append(f"[주제] {content.topic}")
    for sl in content.slides:
        if sl.title:
            out.append(f"# {sl.title}")
        if sl.body:
            out.append(sl.body)
        out.extend(f"- {b}" for b in sl.bullets)
    if content.caption:
        out.append(content.caption)
    return "\n".join(out)


# --- 공개 API --------------------------------------------------------------
def expand_keyword(keyword: str, *, n_slides: int, model: str | None = None,
                   handle: str = "", refresh: bool = False) -> Content:
    settings = load_settings()
    system, user = build_keyword_prompt(keyword.strip(), n_slides)
    data = generate_json(system, user, model=model, settings=settings,
                          refresh=refresh)
    return to_content(data, source="ai", handle=handle)


def summarize_to_slides(raw_text: str, *, n_slides: int,
                        topic_hint: str = "", model: str | None = None,
                        handle: str = "", refresh: bool = False) -> Content:
    settings = load_settings()
    system, user = build_summarize_prompt(
        raw_text.strip()[:12000], n_slides, topic_hint)   # 토큰/비용 가드
    data = generate_json(system, user, model=model, settings=settings,
                          refresh=refresh)
    return to_content(data, source="ai", handle=handle)
