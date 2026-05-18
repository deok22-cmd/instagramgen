"""테스트용 배경 PNG 생성 (표준 라이브러리만 사용, Pillow 불필요).

사용:
    python examples/make_test_bg.py assets/test_bg.png 1080 1080

대각선 그라데이션 + 약한 비네팅으로 사진 비슷한 톤을 만든다. 실제 사진/
AI 이미지가 없을 때 P6(수동 배경) 동작 확인용.
"""

from __future__ import annotations

import struct
import sys
import zlib


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def make_png(path: str, w: int, h: int) -> None:
    c1 = (0x6D, 0x5D, 0xF6)   # 보라
    c2 = (0x0E, 0xA5, 0xE9)   # 청록
    rows = bytearray()
    cx, cy = w / 2, h / 2
    maxd = (cx ** 2 + cy ** 2) ** 0.5
    for y in range(h):
        rows.append(0)  # PNG filter type 0 (None)
        for x in range(w):
            t = (x + y) / (w + h)                       # 대각선 보간
            vig = 1 - 0.35 * (((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / maxd)
            for ch in range(3):
                v = (c1[ch] * (1 - t) + c2[ch] * t) * vig
                rows.append(max(0, min(255, int(v))))

    raw = zlib.compress(bytes(rows), 9)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # 8bit RGB
    with open(path, "wb") as f:
        f.write(sig)
        f.write(_chunk(b"IHDR", ihdr))
        f.write(_chunk(b"IDAT", raw))
        f.write(_chunk(b"IEND", b""))
    print(f"생성: {path} ({w}x{h})")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "assets/test_bg.png"
    W = int(sys.argv[2]) if len(sys.argv) > 2 else 1080
    H = int(sys.argv[3]) if len(sys.argv) > 3 else 1080
    make_png(out, W, H)
