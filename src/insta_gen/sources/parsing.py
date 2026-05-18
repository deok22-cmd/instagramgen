"""구조화 텍스트 파서 (텍스트 소스 / .txt 파일 공용).

표기 규칙
---------
* 메타 라인(접두사):  ``topic:``  ``footer:``  ``caption:``  ``tags:``
* ``- `` 또는 ``* `` 로 시작 → 불릿
* 그 외 첫 일반 라인 → 제목, 이후 일반 라인 → 본문
* ``---``  한 줄  → 슬라이드 구분 (캐러셀)
* ``===``  한 줄  → 게시물(Content) 구분 (배치)

예)
    topic: 생산성
    아침 루틴 5가지
    하루를 바꾸는 작은 습관들.
    - 기상 후 물 한 잔
    - 5분 스트레칭
    tags: 생산성 아침루틴 자기계발
"""

from __future__ import annotations

from ..models import Content, Slide

_META = ("topic:", "footer:", "caption:", "tags:", "hashtags:")


def _split_hashtags(s: str) -> list[str]:
    parts = s.replace(",", " ").split()
    return [p.lstrip("#").strip() for p in parts if p.strip()]


def _parse_slide(block: str) -> tuple[Slide, dict]:
    slide = Slide()
    meta: dict = {}
    body_lines: list[str] = []

    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            if body_lines and body_lines[-1] != "":
                body_lines.append("")
            continue

        low = line.lower()
        if low.startswith("topic:"):
            meta["topic"] = line.split(":", 1)[1].strip()
        elif low.startswith("footer:"):
            slide.footer = line.split(":", 1)[1].strip()
        elif low.startswith("caption:"):
            meta["caption"] = line.split(":", 1)[1].strip()
        elif low.startswith(("tags:", "hashtags:")):
            meta["hashtags"] = _split_hashtags(line.split(":", 1)[1])
        elif line.startswith(("- ", "* ")):
            slide.bullets.append(line[2:].strip())
        elif not slide.title:
            slide.title = line
        else:
            body_lines.append(line)

    slide.body = "\n".join(body_lines).strip()
    return slide, meta


def parse_post(text: str, *, source: str = "text") -> Content:
    """슬라이드 구분(---) 포함한 단일 게시물 → Content."""
    blocks = _split_on_marker(text, "---") or [text]

    content = Content(source=source)
    content.slides = []
    for blk in blocks:
        slide, meta = _parse_slide(blk)
        if not slide.is_empty():
            content.slides.append(slide)
        if meta.get("topic"):
            content.topic = meta["topic"]
        if meta.get("caption"):
            content.caption = meta["caption"]
        if meta.get("hashtags"):
            content.hashtags = meta["hashtags"]
    if not content.slides:
        content.slides = [Slide()]
    return content


def parse_many(text: str, *, source: str = "text") -> list[Content]:
    """=== 로 구분된 여러 게시물 → Content 리스트."""
    posts = _split_on_marker(text, "===")
    out = [parse_post(p, source=source) for p in posts if p.strip()]
    return out or [parse_post(text, source=source)]


def _split_on_marker(text: str, marker: str) -> list[str]:
    """한 줄이 정확히 marker 인 지점에서 분리."""
    chunks: list[list[str]] = [[]]
    for line in text.splitlines():
        if line.strip() == marker:
            chunks.append([])
        else:
            chunks[-1].append(line)
    return ["\n".join(c).strip() for c in chunks if "\n".join(c).strip()]
