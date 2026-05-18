"""키워드 → AI 카드뉴스 콘텐츠 소스 (P5)."""

from __future__ import annotations

from ..ai.text import expand_keyword
from ..models import Content
from .base import Source


class KeywordSource(Source):
    name = "keyword"

    def __init__(self, keyword: str, *, n_slides: int = 8,
                 model: str | None = None, handle: str = "",
                 refresh: bool = False):
        self.keyword = keyword or ""
        self.n_slides = n_slides
        self.model = model
        self.handle = handle
        self.refresh = refresh

    def load(self) -> list[Content]:
        if not self.keyword.strip():
            raise ValueError("--source keyword 에는 --text 로 키워드를 주세요.")
        return [expand_keyword(
            self.keyword, n_slides=self.n_slides, model=self.model,
            handle=self.handle, refresh=self.refresh,
        )]
