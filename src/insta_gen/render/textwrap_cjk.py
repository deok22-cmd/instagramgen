"""폰트 측정 없이 동작하는 근사 줄바꿈.

원리
----
실제 글리프 폭을 재려면 폰트 파일이 필요하지만, 입력 단계(SVG 생성)에서는
래스터라이저가 없을 수 있다. 그래서 문자 종류별 평균 폭 비율(상대값)로
폭을 추정한다. 한글/CJK 는 정사각(폭≈font_size), 라틴 소문자는 좁다.
P8(PNG)에서 실측 기반으로 교체할 수 있도록 함수 단위로 격리해 둔다.

규칙
----
* 줄바꿈: CJK 는 글자 단위, 라틴은 단어(공백) 단위로 끊는다.
* 입력의 명시적 개행("\\n")은 그대로 유지한다.
* max_lines 초과 시 마지막 줄 끝을 "…" 로 줄인다.
"""

from __future__ import annotations


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (
        0x1100 <= o <= 0x11FF or    # 한글 자모
        0x3000 <= o <= 0x303F or    # CJK 구두점
        0x3040 <= o <= 0x30FF or    # 히라가나/가타카나
        0x3130 <= o <= 0x318F or    # 한글 호환 자모
        0x3400 <= o <= 0x4DBF or    # CJK 확장 A
        0x4E00 <= o <= 0x9FFF or    # CJK 통합 한자
        0xAC00 <= o <= 0xD7A3 or    # 한글 음절
        0xFF00 <= o <= 0xFFEF       # 전각
    )


def char_width(ch: str, font_size: float) -> float:
    """문자 1개의 근사 렌더 폭(px)."""
    if ch == "\t":
        return font_size * 2.0
    if _is_cjk(ch):
        return font_size * 1.0
    if ch == " ":
        return font_size * 0.30
    if ch in ".,:;!|'`il":
        return font_size * 0.28
    if ch.isdigit():
        return font_size * 0.56
    if ch.isupper() or ch in "WM@%&":
        return font_size * 0.68
    return font_size * 0.54


def _text_width(s: str, font_size: float) -> float:
    return sum(char_width(c, font_size) for c in s)


def _tokenize(line: str) -> list[str]:
    """CJK 글자=토큰, 라틴 단어=토큰, 연속 공백=토큰."""
    tokens: list[str] = []
    buf = ""
    for ch in line:
        if _is_cjk(ch):
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
        elif ch == " ":
            if buf and not buf.endswith(" "):
                tokens.append(buf)
                buf = ""
            if buf.endswith(" ") or buf == "":
                buf += " "
            else:
                buf = " "
        else:
            if buf.endswith(" "):
                tokens.append(buf)
                buf = ""
            buf += ch
    if buf:
        tokens.append(buf)
    return tokens


def wrap_text(
    text: str,
    max_width: float,
    font_size: float,
    *,
    max_lines: int = 0,
) -> list[str]:
    """텍스트를 max_width(px)에 맞춰 줄 리스트로 반환."""
    if not text:
        return []

    lines: list[str] = []
    for raw in text.split("\n"):
        if raw.strip() == "":
            lines.append("")
            continue

        cur = ""
        cur_w = 0.0
        for tok in _tokenize(raw):
            tw = _text_width(tok, font_size)

            # 줄 첫 토큰이 공백이면 버린다
            if not cur and tok.strip() == "":
                continue

            # 현재 줄에 더 넣으면 넘침 → 줄 마감
            if cur and cur_w + tw > max_width:
                lines.append(cur.rstrip())
                cur, cur_w = "", 0.0
                if tok.strip() == "":
                    continue

            # 토큰 자체가 한 줄보다 길면 글자 단위 강제 분할
            if tw > max_width:
                for c in tok:
                    cw = char_width(c, font_size)
                    if cur and cur_w + cw > max_width:
                        lines.append(cur.rstrip())
                        cur, cur_w = "", 0.0
                    cur += c
                    cur_w += cw
            else:
                cur += tok
                cur_w += tw

        lines.append(cur.rstrip())

    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1].rstrip()
        # "…" 자리 확보를 위해 끝 글자 제거
        while last and _text_width(last + "…", font_size) > max_width:
            last = last[:-1]
        lines[-1] = (last + "…") if last else "…"

    return lines
