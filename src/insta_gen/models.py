"""정규화된 콘텐츠 데이터 모델.

모든 주제 소스(텍스트/파일/URL/AI)는 최종적으로 `Content` 리스트로 변환된다.
렌더러는 `Content` 만 알면 되고 입력 출처는 신경 쓰지 않는다 (소스/렌더 분리).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Slide:
    """게시물 한 장(또는 캐러셀 한 컷)의 텍스트 구성."""

    title: str = ""
    body: str = ""
    bullets: list[str] = field(default_factory=list)
    footer: str = ""

    def is_empty(self) -> bool:
        return not (self.title or self.body or self.bullets or self.footer)


@dataclass
class Content:
    """게시물 1건. 단일 포맷이면 slides[0]만, 캐러셀이면 여러 장 사용."""

    topic: str = ""                       # 상단 아이브로우/카테고리
    slides: list[Slide] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    caption: str = ""                     # 인스타 게시 캡션(이미지에는 안 들어감)
    source: str = ""                      # text | file | url | ai
    language: str = "ko"

    def __post_init__(self) -> None:
        if not self.slides:
            self.slides = [Slide()]

    @property
    def primary(self) -> Slide:
        return self.slides[0]

    def field_value(self, name: str, slide: Slide, *, page_no: int = 1,
                     total: int = 1) -> str:
        """포맷 zone.bind 이름 → 실제 텍스트 변환."""
        if name == "topic":
            return self.topic
        if name == "title":
            return slide.title
        if name == "body":
            return slide.body
        if name == "footer":
            return slide.footer
        if name == "bullets":
            return "\n".join(slide.bullets)
        if name == "hashtags":
            return " ".join(
                h if h.startswith("#") else f"#{h}" for h in self.hashtags
            )
        if name == "caption":
            return self.caption
        if name == "page":
            return f"{page_no} / {total}" if total > 1 else ""
        return ""


@dataclass
class RenderedSVG:
    """렌더 결과 한 장."""

    index: int           # 0-based 슬라이드 번호
    svg: str             # SVG 문서 문자열
    width: int
    height: int
