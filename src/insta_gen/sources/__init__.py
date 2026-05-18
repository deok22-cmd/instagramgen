"""주제 소스 계층.

P1: text, file   /   P4: html(로컬), url   /   P5: keyword(AI)
모두 동일한 Source 규약(load() -> list[Content]).
"""

from .base import Source
from .file_source import FileSource
from .html_source import HtmlSource
from .keyword_source import KeywordSource
from .text_source import TextSource

__all__ = [
    "Source", "TextSource", "FileSource", "HtmlSource", "KeywordSource",
    "build_source",
]


def build_source(kind: str, *, text: str | None = None,
                 path: str | None = None, handle: str = "",
                 n_slides: int = 8, model: str | None = None,
                 refresh: bool = False) -> Source:
    """CLI 인자 → Source 인스턴스."""
    if kind == "text":
        if not text:
            raise ValueError("--source text 에는 --text 가 필요합니다.")
        return TextSource(text)
    if kind == "file":
        if not path:
            raise ValueError("--source file 에는 --input 경로가 필요합니다.")
        return FileSource(path)
    if kind == "html":
        if not path:
            raise ValueError("--source html 에는 --input HTML 경로가 필요합니다.")
        return HtmlSource(path, handle=handle)
    if kind == "keyword":
        return KeywordSource(text or "", n_slides=n_slides, model=model,
                             handle=handle, refresh=refresh)
    if kind == "url":
        raise NotImplementedError(
            "'url' 소스(원격 fetch)는 후속 단계에서 추가됩니다. "
            "지금은 페이지를 저장해 --source html --input 파일.html 로 쓰세요."
        )
    raise ValueError(f"알 수 없는 소스 종류: {kind}")
