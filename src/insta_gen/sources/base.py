"""주제 소스 공통 규약.

모든 소스는 `load() -> list[Content]` 를 구현한다. 단건이면 길이 1 리스트,
파일/배치면 여러 건. 렌더 계층은 소스 종류를 알 필요가 없다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Content


class Source(ABC):
    name: str = "base"

    @abstractmethod
    def load(self) -> list[Content]:
        ...
