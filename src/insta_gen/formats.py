"""formats.yaml 로딩 + 포맷/존 데이터 구조."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Zone:
    name: str
    bind: str
    x: float
    y: float
    w: float
    h: float
    align: str = "left"          # left | center | right
    valign: str = "top"          # top | middle | bottom
    font_size: float = 40
    font_weight: int = 400
    color: str = "#FFFFFF"
    font_family: str = "sans-serif"
    line_height: float = 1.3
    max_lines: int = 0           # 0 = 무제한
    letter_spacing: float = 0.0


@dataclass
class Background:
    mode: str = "solid"          # solid | gradient | image | ai
    color: str = "#111827"
    from_: str = "#6D5DF6"
    to: str = "#1E1B4B"
    angle: float = 135.0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Format:
    id: str
    name: str
    description: str
    width: int
    height: int
    kind: str                    # single | carousel
    background: Background
    zones: list[Zone]

    def zone(self, name: str) -> Zone | None:
        for z in self.zones:
            if z.name == name:
                return z
        return None


def _build_background(raw: dict[str, Any]) -> Background:
    raw = raw or {}
    return Background(
        mode=raw.get("mode", "solid"),
        color=raw.get("color", "#111827"),
        from_=raw.get("from", "#6D5DF6"),
        to=raw.get("to", "#1E1B4B"),
        angle=float(raw.get("angle", 135)),
        extra={k: v for k, v in raw.items()
               if k not in {"mode", "color", "from", "to", "angle"}},
    )


def load_formats(path: str | Path) -> dict[str, Format]:
    """formats.yaml 을 읽어 {id: Format} 딕셔너리로 반환."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    out: dict[str, Format] = {}

    for fid, fraw in (data.get("formats") or {}).items():
        zones: list[Zone] = []
        for z in fraw.get("zones", []):
            zones.append(Zone(
                name=z["name"],
                bind=z.get("bind", z["name"]),
                x=float(z["x"]), y=float(z["y"]),
                w=float(z["w"]), h=float(z["h"]),
                align=z.get("align", "left"),
                valign=z.get("valign", "top"),
                font_size=float(z.get("font_size", 40)),
                font_weight=int(z.get("font_weight",
                                      defaults.get("font_weight", 400))),
                color=z.get("color", defaults.get("color", "#FFFFFF")),
                font_family=z.get("font_family",
                                  defaults.get("font_family", "sans-serif")),
                line_height=float(z.get("line_height",
                                        defaults.get("line_height", 1.3))),
                max_lines=int(z.get("max_lines", 0)),
                letter_spacing=float(z.get("letter_spacing", 0)),
            ))
        out[fid] = Format(
            id=fid,
            name=fraw.get("name", fid),
            description=fraw.get("description", ""),
            width=int(fraw["width"]),
            height=int(fraw["height"]),
            kind=fraw.get("kind", "single"),
            background=_build_background(fraw.get("background", {})),
            zones=zones,
        )
    return out
