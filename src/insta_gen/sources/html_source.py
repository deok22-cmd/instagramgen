"""HTML 원고 → 카드뉴스 콘텐츠 (P4 1차: 로컬 HTML 파일).

표준 라이브러리 `html.parser` 만 사용 (의존성 추가 없음).

블로그 원고의 일반 구조를 활용해 결정적으로 분해한다:

    <h1>           → 커버 슬라이드 제목
    .intro-box     → 커버 본문(도입 요약)
    <h2>           → 섹션 1개 = 카드 1장 (제목)
      이후 본문 단락  → 섹션 본문 (첫 단락만, 문장 경계로 정리)
      .step-box      → 섹션 불릿 (① ② … 의 굵은 소제목)
    span.tag       → 해시태그
    <script>/<style>/.recommend-area/.img-area → 제외

원고마다 형식이 다를 수 있으므로(태그가 없거나 div 구조가 달라도) 깨지지 않게
'가능하면 활용, 없으면 건너뜀' 방식으로 동작한다. 마지막에 CTA 슬라이드를
자동으로 덧붙인다. URL 입력은 후속 단계에서 같은 파서를 재사용한다.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from ..models import Content, Slide
from .base import Source

# div.class 가 이 안에 있으면 그 안의 텍스트는 통째로 무시
_SKIP_DIV = {"recommend-area", "img-area", "img-caption", "tags"}
_RAW_TAGS = {"script", "style"}


def _classes(attrs: list[tuple[str, str | None]]) -> str:
    for k, v in attrs:
        if k == "class":
            return v or ""
    return ""


class _Section:
    __slots__ = ("title", "text", "bullets")

    def __init__(self, title: str = "") -> None:
        self.title = title
        self.text: list[str] = []
        self.bullets: list[str] = []


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.intro: list[str] = []
        self.sections: list[_Section] = []
        self.hashtags: list[str] = []
        self._div_classes: list[str] = []
        self._raw = 0           # script/style 깊이
        self._sink: str | None = None   # h1 | h2 | intro | section | tag | bullet
        self._cur: _Section | None = None

    # --- 상태 헬퍼 ---------------------------------------------------------
    def _in(self, cls: str) -> bool:
        return cls in self._div_classes

    def _skipping(self) -> bool:
        return self._raw > 0 or any(c in _SKIP_DIV for c in self._div_classes)

    # --- 태그 처리 ---------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        if tag in _RAW_TAGS:
            self._raw += 1
            return
        if tag == "div":
            self._div_classes.append(_classes(attrs))
            if self._in("intro-box"):
                self._sink = "intro"
            return
        if tag == "br" and self._sink == "section" and self._cur:
            self._cur.text.append("\n")
            return
        if self._skipping():
            if tag == "span" and "tag" in _classes(attrs):
                self.hashtags.append("")
                self._sink = "tag"
            return
        if tag == "h1":
            self._sink = "h1"
        elif tag == "h2":
            self._flush_section()
            self._cur = _Section()
            self.sections.append(self._cur)
            self._sink = "h2"
        elif tag == "h3" and self._cur:
            self._sink = "section"
            self._cur.text.append("\n")
        elif tag == "strong" and self._in("step-box") and self._cur:
            self._cur.bullets.append("")
            self._sink = "bullet"

    def handle_endtag(self, tag):
        if tag in _RAW_TAGS:
            self._raw = max(0, self._raw - 1)
            return
        if tag == "div":
            if self._div_classes:
                self._div_classes.pop()
            if self._sink == "intro" and not self._in("intro-box"):
                self._sink = None
            return
        if tag in ("h1",) and self._sink == "h1":
            self._sink = None
        elif tag == "h2" and self._sink == "h2":
            self._sink = "section"          # 이후 텍스트는 섹션 본문
        elif tag == "strong" and self._sink == "bullet":
            self._sink = "section"
        elif tag == "span" and self._sink == "tag":
            self._sink = None

    def handle_data(self, data):
        if self._raw:
            return
        # 스킵 영역(이미지 캡션·추천글 등) 텍스트가 섹션 본문으로 새지 않게
        if self._skipping() and self._sink != "tag":
            return
        if self._sink is None or not data.strip():
            return
        s = self._sink
        if s == "h1":
            self.title += data
        elif s == "intro":
            self.intro.append(data)
        elif s == "h2" and self._cur is not None:
            self._cur.title += data
        elif s == "bullet" and self._cur and self._cur.bullets:
            self._cur.bullets[-1] += data
        elif s == "tag" and self.hashtags:
            self.hashtags[-1] += data
        elif s == "section" and self._cur is not None:
            self._cur.text.append(data)

    def _flush_section(self):
        # 별도 정리 불필요 — 리스트에 이미 추가됨
        pass


# --- 텍스트 정리 ----------------------------------------------------------
_WS = re.compile(r"[ \t ]+")
_SENT_END = re.compile(r"(?<=[다요.!?。])\s")


def _clean(s: str) -> str:
    return _WS.sub(" ", s.replace("\r", "")).strip()


def _first_paragraph(parts: list[str], limit: int = 230) -> str:
    raw = "".join(parts)
    paras = [_clean(p) for p in re.split(r"\n{2,}", raw)]
    paras = [p for p in paras if len(p) > 1]
    if not paras:
        return ""
    body = paras[0]
    # 한 문장이 안 될 만큼 짧을 때만 다음 단락 합침(한국어 문장 ≈ 30~60자)
    if len(body) < 30 and len(paras) > 1:
        body = _clean(body + " " + paras[1])
    if len(body) <= limit:
        return body
    cut = body[:limit]
    sents = list(_SENT_END.finditer(cut))
    if sents and sents[-1].start() > limit * 0.5:
        return cut[: sents[-1].start() + 1].strip()
    return cut.rstrip() + "…"


def _strip_label(s: str) -> str:
    # 선행 이모지/라벨("📍 핵심 요약") 제거
    s = _clean(s)
    s = re.sub(r"^[^\w가-힣]*핵심\s*요약\s*[:：]?\s*", "", s)
    return s


def _norm_tag(s: str) -> str:
    return "#" + re.sub(r"\s+", "", s.lstrip("#")).strip()


def parse_html(html: str, *, handle: str = "") -> Content:
    p = _Parser()
    p.feed(html)

    title = _clean(p.title)
    intro = _strip_label("".join(p.intro))
    tags = [_norm_tag(t) for t in p.hashtags if t.strip()]

    # 커버 제목은 첫 구분자(— | · :) 앞부분만 — 긴 SEO 제목 정리
    cover_title = re.split(r"\s*[—\-–|·:]\s*", title, maxsplit=1)[0].strip() \
        if title else "제목 없음"

    slides: list[Slide] = []
    # 커버
    slides.append(Slide(
        title=cover_title,
        body=_first_paragraph([intro], limit=160) if intro else "",
        footer=handle,
    ))
    # 섹션 → 카드
    for sec in p.sections:
        st = _clean(sec.title)
        if not st:
            continue
        bullets = []
        for b in sec.bullets:
            b = _clean(re.sub(r"^[①-⑩0-9]+[.)\s]*", "", b)).strip()
            if b and b not in bullets:
                bullets.append(b)
        slides.append(Slide(
            title=st,
            body=_first_paragraph(sec.text),
            bullets=bullets[:6],
            footer=handle,
        ))
    # CTA
    slides.append(Slide(
        title="저장하고 다시 보기 📌",
        body="도움이 됐다면 팔로우하고 다음 글도 받아보세요.",
        footer=handle,
    ))

    caption = title
    if tags:
        caption = f"{title}\n\n{' '.join(tags)}"

    return Content(
        topic=tags[0].lstrip("#") if tags else "",
        slides=slides,
        hashtags=[t.lstrip("#") for t in tags],
        caption=caption,
        source="html",
        language="ko",
    )


class HtmlSource(Source):
    name = "html"

    def __init__(self, path: str, *, handle: str = ""):
        self.path = Path(path)
        self.handle = handle

    def load(self) -> list[Content]:
        if not self.path.exists():
            raise FileNotFoundError(f"HTML 파일이 없습니다: {self.path}")
        html = self.path.read_text(encoding="utf-8", errors="replace")
        return [parse_html(html, handle=self.handle)]
