"""명령줄 인터페이스.

사용 예
-------
  python -m insta_gen formats
  python -m insta_gen generate --source text --text "..." --format square_basic
  python -m insta_gen generate --source file --input examples/sample.json \\
      --format carousel_cardnews --bg "gradient:#6D5DF6-#1E1B4B@135"
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from .ai import AIError, content_to_text, summarize_to_slides
from .formats import load_formats
from .render import render
from .render.background import BackgroundSpec
from .sources import build_source

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORMATS_PATH = PROJECT_ROOT / "config" / "formats.yaml"


def _slugify(s: str, fallback: str = "post") -> str:
    s = re.sub(r"[^\w가-힣]+", "-", (s or "").strip()).strip("-").lower()
    return s[:40] or fallback


def _resolve_date(date_arg: str | None, input_path: str | None) -> str:
    """출력 폴더용 yymmdd 결정.

    우선순위: --date  >  입력 경로 안의 6자리 폴더(예: src/.../260518/..)
              >  오늘 날짜.
    """
    if date_arg:
        d = re.sub(r"\D", "", date_arg)
        if len(d) != 6:
            raise ValueError(f"--date 는 yymmdd 6자리여야 합니다: {date_arg!r}")
        return d
    if input_path:
        for part in Path(input_path).parts:
            if re.fullmatch(r"\d{6}", part):
                return part
    return datetime.now().strftime("%y%m%d")


def cmd_formats(_: argparse.Namespace) -> int:
    formats = load_formats(FORMATS_PATH)
    print(f"사용 가능한 포맷 ({len(formats)}):\n")
    for fid, f in formats.items():
        print(f"  {fid:<20} {f.width}x{f.height:<5} [{f.kind}]  {f.name}")
        print(f"  {'':<20} {f.description}\n")
    return 0


def _fit_slides(content, n: int):
    """슬라이드 수를 정확히 n장으로 맞춤(초과 시 커버·마지막은 유지하고 중간만 컷)."""
    s = content.slides
    if n <= 0 or len(s) <= n:
        return content
    if n == 1:
        content.slides = [s[0]]
    elif n == 2:
        content.slides = [s[0], s[-1]]
    else:
        content.slides = [s[0]] + s[1:-1][: n - 2] + [s[-1]]
    return content


def cmd_generate(a: argparse.Namespace) -> int:
    formats = load_formats(FORMATS_PATH)
    if a.format not in formats:
        print(f"[오류] 알 수 없는 포맷: {a.format}", file=sys.stderr)
        print(f"  가능: {', '.join(formats)}", file=sys.stderr)
        return 2
    fmt = formats[a.format]

    ai_n = a.max_slides or 8        # 키워드/요약 시 기본 8장
    try:
        source = build_source(a.source, text=a.text, path=a.input,
                               handle=a.handle or "", n_slides=ai_n,
                               model=a.ai_model, refresh=a.ai_refresh)
        contents = source.load()
        bg = BackgroundSpec.parse(a.bg).resolve(fmt)
        if a.ai_summarize:
            summarized = []
            for c in contents:
                sc = summarize_to_slides(
                    content_to_text(c), n_slides=ai_n,
                    topic_hint=c.topic, model=a.ai_model,
                    handle=a.handle or "", refresh=a.ai_refresh)
                summarized.append(sc)
            contents = summarized
            print(f"[AI] {len(contents)}건을 {ai_n}장으로 재구성했습니다.")
    except (ValueError, NotImplementedError, FileNotFoundError,
            AIError) as e:
        print(f"[오류] {e}", file=sys.stderr)
        return 2

    # 결정적 소스(text/file/html)에서만 기계적 N장 컷 적용.
    # keyword/ai-summarize 는 AI가 이미 정확히 N장 생성.
    if a.max_slides and not (a.source == "keyword" or a.ai_summarize):
        for c in contents:
            orig = len(c.slides)
            _fit_slides(c, a.max_slides)
            if orig > len(c.slides):
                print(f"[안내] 슬라이드 {orig}장 → {len(c.slides)}장으로 조정 "
                      f"(중간 {orig - len(c.slides)}장 생략). 의미 기반 "
                      "재구성은 --ai-summarize 사용.")

    try:
        date_code = _resolve_date(a.date, a.input)
    except ValueError as e:
        print(f"[오류] {e}", file=sys.stderr)
        return 2

    out_root = Path(a.out)
    written: list[Path] = []
    multi = len(contents) > 1
    for ci, content in enumerate(contents, 1):
        keyword = _slugify(a.name or content.primary.title or content.topic)
        # 출력 = output/<yymmdd>/<keyword>/
        target = out_root / date_code / keyword
        target.mkdir(parents=True, exist_ok=True)
        # 같은 keyword 폴더에 여러 콘텐츠가 들어갈 때만 번호 접두
        fbase = f"{keyword}-{ci:02d}" if (multi and a.name) else keyword
        for r in render(content, fmt, bg):
            suffix = f"-{r.index + 1:02d}" if fmt.kind == "carousel" else ""
            fp = target / f"{fbase}-{a.format}{suffix}.svg"
            fp.write_text(r.svg, encoding="utf-8")
            written.append(fp)

    print(f"생성 완료: {len(written)}개 SVG → "
          f"{out_root}\\{date_code}\\<keyword>\\")
    for w in written:
        print(f"  - {w.relative_to(out_root).as_posix()}")
    return 0


def cmd_preview(a: argparse.Namespace) -> int:
    out_dir = Path(a.out)
    svgs = sorted(p for p in out_dir.rglob("*.svg"))
    if not svgs:
        print(f"[안내] {out_dir}/ 에 SVG가 없습니다. 먼저 generate 하세요.",
              file=sys.stderr)
        return 1
    cards = "".join(
        f'<figure><img src="{rel}" loading="lazy"/>'
        f'<figcaption>{rel}</figcaption></figure>'
        for rel in (s.relative_to(out_dir).as_posix() for s in svgs)
    )
    html = (
        '<!doctype html><meta charset="utf-8">'
        '<title>insta_gen preview</title>'
        '<style>body{background:#0b0f17;color:#cbd5e1;font-family:sans-serif;'
        'margin:24px}h1{font-size:16px}.grid{display:flex;flex-wrap:wrap;'
        'gap:20px}figure{margin:0;width:300px}img{width:300px;border-radius:12px;'
        'background:#1e293b;box-shadow:0 4px 16px #0008}figcaption{font-size:12px;'
        'margin-top:6px;color:#94a3b8;word-break:break-all}</style>'
        f'<h1>insta_gen — {len(svgs)} SVG</h1>'
        f'<div class="grid">{cards}</div>'
    )
    idx = out_dir / "index.html"
    idx.write_text(html, encoding="utf-8")
    print(f"미리보기: {idx}  (브라우저로 열기)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="insta_gen",
        description="인스타그램 템플릿 제너레이터 (P1–P3: 텍스트/파일 → SVG)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("formats", help="사용 가능한 디자인 포맷 목록")

    pv = sub.add_parser("preview",
                        help="output/ SVG들을 브라우저용 index.html로 모음")
    pv.add_argument("--out", default=str(PROJECT_ROOT / "output"),
                    help="대상 디렉토리 (기본: output/)")

    g = sub.add_parser("generate", help="SVG 생성")
    g.add_argument("--source", default="text",
                   choices=["text", "file", "html", "url", "keyword"],
                   help="주제 소스 (text, file, html, keyword)")
    g.add_argument("--text",
                   help="--source text 입력 텍스트 / keyword 일 때 키워드")
    g.add_argument("--input",
                   help="--source file(.csv/.json/.txt) / html(.html) 경로")
    g.add_argument("--format", default="square_basic", help="디자인 포맷 ID")
    g.add_argument("--bg", default=None,
                   help='배경. 예: "solid:#0F172A" / '
                        '"gradient:#6D5DF6-#1E1B4B@135" / '
                        '"image:assets/bg.png?dim=30&scrim=bottom"')
    g.add_argument("--max-slides", type=int, default=0, dest="max_slides",
                   help="슬라이드 수. text/file/html=상한(초과 시 컷), "
                        "keyword/--ai-summarize=정확히 N장. 0=기본(AI는 8)")
    g.add_argument("--ai-summarize", action="store_true", dest="ai_summarize",
                   help="소스 내용을 OpenAI로 의미 기반 N장 재구성 "
                        "(긴 HTML/글 → 압축)")
    g.add_argument("--ai-model", default=None, dest="ai_model",
                   help="텍스트 모델 override (기본: settings.text_model)")
    g.add_argument("--ai-refresh", action="store_true", dest="ai_refresh",
                   help="AI 응답 캐시 무시하고 재생성")
    g.add_argument("--handle", default="",
                   help="슬라이드 푸터/브랜드 핸들 (예: @your_handle)")
    g.add_argument("--date", default=None,
                   help="출력 폴더 yymmdd. 미지정 시 입력경로의 6자리 폴더 "
                        "→ 없으면 오늘 날짜")
    g.add_argument("--out", default=str(PROJECT_ROOT / "output"),
                   help="출력 루트. 실제 저장은 <out>/<yymmdd>/<keyword>/")
    g.add_argument("--name", help="출력 파일 베이스명 (미지정=제목 슬러그)")
    return p


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    a = p.parse_args(argv)
    if a.command == "formats":
        return cmd_formats(a)
    if a.command == "generate":
        return cmd_generate(a)
    if a.command == "preview":
        return cmd_preview(a)
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
