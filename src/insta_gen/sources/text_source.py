"""직접 텍스트 입력 소스."""

from __future__ import annotations

from ..models import Content
from .base import Source
from .parsing import parse_many


class TextSource(Source):
    name = "text"

    def __init__(self, text: str):
        self.text = text

    def load(self) -> list[Content]:
        return parse_many(self.text, source="text")
