"""배경 렌더링.

P3: solid / gradient
P6: image  — 수동 배경 이미지 임베드 (cover-fit + 가독성 오버레이/스크림)
P7: ai     — 자동생성(같은 image 경로 재사용 예정)

CLI 배경 문자열 (`--bg`)
------------------------
    solid:#0F172A
    gradient:#6D5DF6-#1E1B4B@135
    image:assets/bg.jpg
    image:assets/bg.jpg?dim=35
    image:assets/bg.jpg?scrim=bottom
    image:C:\\img\\bg.png?fit=contain&dim=20&scrim=bottom&embed=link

image 옵션
    dim    0~100   검정 오버레이 불투명도(%)            기본 0
    scrim  top|bottom|both   가독성용 어둠 그라데이션    기본 none
    fit    cover|contain     캔버스 맞춤                 기본 cover
    embed  data|link         data=base64 내장(이식성) /  기본 data
                             link=파일 경로 참조
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from ..formats import Background, Format

_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".gif": "image/gif",
}


def _parse_opts(s: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in s.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip().lower()] = v.strip()
    return out


@dataclass
class BackgroundSpec:
    mode: str = "default"        # default | solid | gradient | image
    color: str = ""
    from_: str = ""
    to: str = ""
    angle: float = 135.0
    image_path: str = ""
    opts: dict[str, str] = field(default_factory=dict)

    @classmethod
    def parse(cls, raw: str | None) -> "BackgroundSpec":
        if not raw:
            return cls(mode="default")
        raw = raw.strip()

        if raw.startswith("solid:"):
            return cls(mode="solid", color=raw.split(":", 1)[1].strip())

        if raw.startswith("gradient:"):
            spec = raw.split(":", 1)[1].strip()
            angle = 135.0
            if "@" in spec:
                spec, ang = spec.rsplit("@", 1)
                angle = float(ang)
            frm, to = spec.split("-", 1)
            return cls(mode="gradient", from_=frm.strip(),
                       to=to.strip(), angle=angle)

        if raw.startswith("image:"):
            rest = raw.split(":", 1)[1].strip()
            # 경로에는 '?' 가 올 수 없으므로 첫 '?' 에서 옵션 분리
            path, _, qs = rest.partition("?")
            return cls(mode="image", image_path=path.strip(),
                       opts=_parse_opts(qs))

        raise ValueError(
            f"배경 형식을 해석할 수 없습니다: {raw!r}\n"
            "  예) solid:#0F172A | gradient:#6D5DF6-#1E1B4B@135 | "
            "image:assets/bg.jpg?dim=30&scrim=bottom"
        )

    def resolve(self, fmt: Format) -> Background:
        """포맷 기본값과 합쳐 최종 Background 결정."""
        base = fmt.background
        if self.mode == "default":
            return base
        if self.mode == "solid":
            return Background(mode="solid", color=self.color or base.color)
        if self.mode == "gradient":
            return Background(mode="gradient",
                              from_=self.from_ or base.from_,
                              to=self.to or base.to, angle=self.angle)
        if self.mode == "image":
            return _resolve_image(self, base)
        return base


def _resolve_image(spec: "BackgroundSpec", base: Background) -> Background:
    p = Path(spec.image_path).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p)
    if not p.exists():
        raise FileNotFoundError(f"배경 이미지를 찾을 수 없습니다: {p}")

    ext = p.suffix.lower()
    mime = _MIME.get(ext)
    if not mime:
        raise ValueError(
            f"지원하지 않는 이미지 형식: {ext} "
            f"({', '.join(sorted(_MIME))})"
        )

    embed = spec.opts.get("embed", "data").lower()
    if embed == "link":
        href = p.as_uri()
    else:
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        href = f"data:{mime};base64,{b64}"

    extra: dict[str, Any] = {
        "href": href,
        "fit": spec.opts.get("fit", "cover").lower(),
        "dim": max(0.0, min(100.0, float(spec.opts.get("dim", 0)))) / 100.0,
        "scrim": spec.opts.get("scrim", "").lower(),
        "fallback": base.color if base.mode == "solid" else "#0B0F17",
    }
    return Background(mode="image", color=extra["fallback"], extra=extra)


def _scrim_def(kind: str) -> str:
    """가독성용 어둠 그라데이션 정의 (id='scrim')."""
    if kind == "top":
        stops = ('<stop offset="0%" stop-color="#000" stop-opacity="0.70"/>'
                 '<stop offset="45%" stop-color="#000" stop-opacity="0"/>')
    elif kind == "both":
        stops = ('<stop offset="0%" stop-color="#000" stop-opacity="0.65"/>'
                 '<stop offset="40%" stop-color="#000" stop-opacity="0"/>'
                 '<stop offset="60%" stop-color="#000" stop-opacity="0"/>'
                 '<stop offset="100%" stop-color="#000" stop-opacity="0.75"/>')
    else:  # bottom (기본)
        stops = ('<stop offset="50%" stop-color="#000" stop-opacity="0"/>'
                 '<stop offset="100%" stop-color="#000" stop-opacity="0.78"/>')
    return (f'<linearGradient id="scrim" x1="0" y1="0" x2="0" y2="1">'
            f'{stops}</linearGradient>')


def render_background_svg(bg: Background, width: int,
                          height: int) -> tuple[str, str]:
    """(defs 조각, 배경 그래픽 조각) 반환. 그래픽은 텍스트보다 먼저 그려진다."""
    if bg.mode == "image":
        e = bg.extra
        par = ("xMidYMid slice" if e.get("fit", "cover") == "cover"
               else "xMidYMid meet")
        parts = [
            f'<rect width="{width}" height="{height}" '
            f'fill="{escape(e["fallback"])}"/>',
            f'<image x="0" y="0" width="{width}" height="{height}" '
            f'preserveAspectRatio="{par}" href="{escape(e["href"])}"/>',
        ]
        defs = ""
        if e.get("dim", 0) > 0:
            parts.append(
                f'<rect width="{width}" height="{height}" fill="#000" '
                f'fill-opacity="{e["dim"]:.3f}"/>'
            )
        if e.get("scrim"):
            defs = _scrim_def(e["scrim"])
            parts.append(
                f'<rect width="{width}" height="{height}" fill="url(#scrim)"/>'
            )
        return defs, "".join(parts)

    if bg.mode == "gradient":
        import math

        rad = math.radians(bg.angle)
        x2 = 0.5 + math.cos(rad) / 2
        y2 = 0.5 + math.sin(rad) / 2
        x1, y1 = 1 - x2, 1 - y2
        defs = (
            f'<linearGradient id="bg" x1="{x1:.4f}" y1="{y1:.4f}" '
            f'x2="{x2:.4f}" y2="{y2:.4f}">'
            f'<stop offset="0%" stop-color="{escape(bg.from_)}"/>'
            f'<stop offset="100%" stop-color="{escape(bg.to)}"/>'
            f'</linearGradient>'
        )
        rect = f'<rect width="{width}" height="{height}" fill="url(#bg)"/>'
        return defs, rect

    rect = f'<rect width="{width}" height="{height}" fill="{escape(bg.color)}"/>'
    return "", rect
