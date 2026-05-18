"""파일 입력 소스 — .csv / .json / .txt 자동 판별.

CSV  : 행 1개 = 게시물 1건(슬라이드 1장).
       인식 컬럼: topic,title,body,footer,bullets,hashtags,caption
       bullets  → '|' 로 구분,  hashtags → 공백/쉼표 구분
JSON : {topic,caption,hashtags:[],slides:[{title,body,bullets:[],footer}]}
       또는 그런 객체의 리스트(배치), 또는 {title,body,...} 단축형
TXT  : parsing.parse_many (=== 게시물, --- 슬라이드)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ..models import Content, Slide
from .base import Source
from .parsing import parse_many


def _hashtags(v) -> list[str]:
    if isinstance(v, list):
        return [str(x).lstrip("#").strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        return [p.lstrip("#").strip()
                for p in v.replace(",", " ").split() if p.strip()]
    return []


def _content_from_dict(d: dict) -> Content:
    c = Content(source="file")
    c.topic = str(d.get("topic", "")).strip()
    c.caption = str(d.get("caption", "")).strip()
    c.hashtags = _hashtags(d.get("hashtags") or d.get("tags"))

    slides_raw = d.get("slides")
    if slides_raw is None:                       # 단축형: {title,body,...}
        slides_raw = [{
            "title": d.get("title", ""),
            "body": d.get("body", ""),
            "bullets": d.get("bullets", []),
            "footer": d.get("footer", ""),
        }]
    slides: list[Slide] = []
    for s in slides_raw:
        b = s.get("bullets", [])
        if isinstance(b, str):
            b = [x.strip() for x in b.split("|") if x.strip()]
        slides.append(Slide(
            title=str(s.get("title", "")).strip(),
            body=str(s.get("body", "")).strip(),
            bullets=[str(x).strip() for x in b if str(x).strip()],
            footer=str(s.get("footer", "")).strip(),
        ))
    c.slides = slides or [Slide()]
    return c


class FileSource(Source):
    name = "file"

    def __init__(self, path: str):
        self.path = Path(path)

    def load(self) -> list[Content]:
        if not self.path.exists():
            raise FileNotFoundError(f"입력 파일이 없습니다: {self.path}")
        ext = self.path.suffix.lower()

        if ext == ".json":
            data = json.loads(self.path.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else [data]
            return [_content_from_dict(x) for x in items]

        if ext == ".csv":
            out: list[Content] = []
            with self.path.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    row = {(k or "").strip().lower(): (v or "").strip()
                           for k, v in row.items()}
                    bullets = [x.strip() for x in row.get("bullets", "").split("|")
                               if x.strip()]
                    out.append(_content_from_dict({
                        "topic": row.get("topic", ""),
                        "caption": row.get("caption", ""),
                        "hashtags": row.get("hashtags", ""),
                        "title": row.get("title", ""),
                        "body": row.get("body", ""),
                        "bullets": bullets,
                        "footer": row.get("footer", ""),
                    }))
            return out or [Content(source="file")]

        if ext in (".txt", ".md"):
            return parse_many(self.path.read_text(encoding="utf-8"),
                              source="file")

        raise ValueError(f"지원하지 않는 파일 형식: {ext} (.csv/.json/.txt)")
