"""콘텐츠 + 포맷 + 배경 → SVG 문서.

단일 포맷이면 1장, 캐러셀이면 슬라이드 수만큼 SVG 를 만든다.
텍스트는 zone(box) 안에서 align/valign 에 따라 배치하고, CJK 인식
줄바꿈으로 tspan 을 쌓는다.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from ..formats import Format, Zone
from ..models import Content, RenderedSVG, Slide
from .background import Background, render_background_svg
from .textwrap_cjk import wrap_text

# 첫 줄 베이스라인 보정(글자 윗공간) — ascent 근사
_ASCENT = 0.80


def _anchor(align: str) -> tuple[str, float]:
    """(text-anchor, x 오프셋 비율) — 비율은 zone.w 에 곱한다."""
    if align == "center":
        return "middle", 0.5
    if align == "right":
        return "end", 1.0
    return "start", 0.0


def _render_zone(z: Zone, text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""

    is_bullets = z.bind == "bullets"
    anchor, ax = _anchor(z.align)
    x = z.x + z.w * ax
    line_h = z.font_size * z.line_height

    # 줄 구성
    if is_bullets:
        lines: list[str] = []
        for raw in [b for b in text.split("\n") if b.strip()]:
            wrapped = wrap_text(raw, z.w - z.font_size, z.font_size)
            for i, ln in enumerate(wrapped):
                lines.append(("• " + ln) if i == 0 else ("  " + ln))
        if z.max_lines:
            lines = lines[: z.max_lines]
    else:
        lines = wrap_text(text, z.w, z.font_size, max_lines=z.max_lines)

    if not lines:
        return ""

    block_h = len(lines) * line_h
    if z.valign == "middle":
        top = z.y + (z.h - block_h) / 2
    elif z.valign == "bottom":
        top = z.y + z.h - block_h
    else:
        top = z.y
    first_baseline = top + z.font_size * _ASCENT

    ls = (f' letter-spacing="{z.letter_spacing}"'
          if z.letter_spacing else "")
    spans = []
    for i, ln in enumerate(lines):
        y = first_baseline + i * line_h
        spans.append(
            f'<tspan x="{x:.1f}" y="{y:.1f}">{escape(ln)}</tspan>'
        )
    return (
        f'<text text-anchor="{anchor}" '
        f'font-family="{escape(z.font_family)}" '
        f'font-size="{z.font_size}" font-weight="{z.font_weight}" '
        f'fill="{escape(z.color)}"{ls}>'
        f'{"".join(spans)}</text>'
    )


def _render_one(fmt: Format, content: Content, slide: Slide,
                bg: Background, page_no: int, total: int) -> str:
    defs, bg_rect = render_background_svg(bg, fmt.width, fmt.height)
    body_parts = [bg_rect]
    for z in fmt.zones:
        txt = content.field_value(z.bind, slide, page_no=page_no, total=total)
        body_parts.append(_render_zone(z, txt))

    defs_block = f"<defs>{defs}</defs>" if defs else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{fmt.width}" height="{fmt.height}" '
        f'viewBox="0 0 {fmt.width} {fmt.height}">'
        f'{defs_block}{"".join(p for p in body_parts if p)}'
        f'</svg>'
    )


def render(content: Content, fmt: Format, bg: Background) -> list[RenderedSVG]:
    """포맷 종류에 따라 SVG 문서 리스트 생성."""
    if fmt.kind == "carousel":
        slides = content.slides
        total = len(slides)
        return [
            RenderedSVG(
                index=i,
                svg=_render_one(fmt, content, s, bg, i + 1, total),
                width=fmt.width, height=fmt.height,
            )
            for i, s in enumerate(slides)
        ]

    # single: 첫 슬라이드만 사용
    return [
        RenderedSVG(
            index=0,
            svg=_render_one(fmt, content, content.primary, bg, 1, 1),
            width=fmt.width, height=fmt.height,
        )
    ]
