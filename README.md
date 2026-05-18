# Instagram Template Generator

주제 소스(텍스트 / 파일 / URL / AI 키워드) → 정규화 콘텐츠 → 인스타그램
디자인 포맷 → **SVG** 출력 → (배경 자동/수동) → **PNG** 출력까지 단계적으로
처리하는 Python CLI 도구.

## 현재 상태

| 단계 | 내용 | 상태 |
|------|------|------|
| P0 | 프로젝트 스캐폴드 + venv + 설정 | ✅ 완료 |
| P1 | 콘텐츠 모델 + 텍스트/파일 소스 | ✅ 완료 |
| P2 | 인스타그램 디자인 포맷 카탈로그(5종) | ✅ 완료 |
| P3 | SVG 렌더(단색/그라데이션 + CJK 줄바꿈) | ✅ 완료 |
| P4 | HTML 원고 소스(로컬) | ✅ 완료 · URL fetch는 후속 |
| P5 | 키워드/요약 → AI 텍스트(Gemini 기본·OpenAI 대체) | ✅ 완료 |
| P6 | 수동 배경 이미지 임베드 | ✅ 완료 |
| P7 | Gemini 배경 이미지 자동생성 → SVG 연결 | ⬜ 다음 |
| P8 | SVG → PNG 내보내기(한글 폰트 포함) | ⬜ 예정 |
| P9 | 캐러셀·배치 파이프라인 통합·마무리 | ⬜ 예정 |
| P4+ | URL 원격 fetch (parse_html 재사용) | ⬜ 후속 |

## 다음 세션 이어가기

1. **환경 복구**: `git clone` 후 venv 재생성
   ```powershell
   cd "<repo>"
   C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   $env:PYTHONPATH="src"; $env:PYTHONUTF8="1"
   ```
   (이 PC는 시스템 Python이 PATH에 없음 — 위 절대경로 사용)
2. **동작 확인**: `.\.venv\Scripts\python.exe -m insta_gen formats`
3. **AI 사용 시**: `$env:GEMINI_API_KEY="<키>"` (파일에 저장 금지)
4. **다음 작업 = P7**: Gemini로 배경 이미지 생성 → 기존 `--bg "image:..."`
   (P6) 경로에 연결. `src/insta_gen/ai/`에 이미지 호출 추가, `--bg "ai:..."`
   스펙을 `render/background.py`의 `BackgroundSpec`에 확장.
   그 다음 우선순위: P8(SVG→PNG, 업로드용) → P9(배치) → P4+(URL fetch).
5. 전체 단계·결정사항은 이 표와 아래 문서 참조. (Claude 메모리에도 기록됨)

## 빠른 시작 (Windows PowerShell)

```powershell
$env:PYTHONPATH = "src"; $env:PYTHONUTF8 = "1"

# 1) 사용 가능한 디자인 포맷 보기
.\.venv\Scripts\python.exe -m insta_gen formats

# 2) 직접 텍스트 → SVG
.\.venv\Scripts\python.exe -m insta_gen generate `
  --source text --text "topic: 생산성`n아침을 바꾸는 5가지 습관`n작은 변화가 하루를 바꿉니다." `
  --format square_basic

# 3) 파일(CSV/JSON/TXT) → SVG (배치/캐러셀)
.\.venv\Scripts\python.exe -m insta_gen generate `
  --source file --input examples\sample.json --format carousel_cardnews

# 4) HTML 블로그 원고 → 8장 카드뉴스
.\.venv\Scripts\python.exe -m insta_gen generate `
  --source html --input src\insta_gen\260518\sample.html `
  --format carousel_cardnews --max-slides 8 --handle "@your_handle" --name ilsan_rose

# 5) AI: 키워드 → 카드뉴스 8장 (Gemini)
$env:GEMINI_API_KEY = "..."
.\.venv\Scripts\python.exe -m insta_gen generate `
  --source keyword --text "일산 호수공원 장미축제 노을 명소" `
  --format carousel_cardnews --max-slides 8 --handle "@your_handle"

# 6) AI: 긴 HTML 원고 → 의미 기반 8장 재구성
.\.venv\Scripts\python.exe -m insta_gen generate `
  --source html --input src\insta_gen\260518\sample.html `
  --ai-summarize --max-slides 8 --format carousel_cardnews --handle "@your_handle"

# 7) 브라우저 미리보기 생성 → output\index.html 열기
.\.venv\Scripts\python.exe -m insta_gen preview
```

## 디자인 포맷 (config/formats.yaml)

| ID | 크기 | 종류 | 용도 |
|----|------|------|------|
| `square_basic` | 1080×1080 | single | 범용 정보 카드 |
| `square_quote` | 1080×1080 | single | 인용구 |
| `portrait_feed` | 1080×1350 | single | 4:5 피드(도달률↑) |
| `story` | 1080×1920 | single | 스토리/릴스 커버 |
| `carousel_cardnews` | 1080×1350 | carousel | 다중 슬라이드 카드뉴스 |

포맷·색·좌표·폰트는 모두 `config/formats.yaml` 에서 코드 수정 없이 조정 가능.

## 입력 형식

**구조화 텍스트 / .txt** — `topic:` `footer:` `caption:` `tags:` 접두사,
`- ` 불릿, 한 줄 `---`=슬라이드 구분, 한 줄 `===`=게시물 구분.

**.csv** — 컬럼 `topic,title,body,bullets,footer,hashtags`
(bullets는 `|` 구분, 행 1개=게시물 1건).

**.json** — `{topic, caption, hashtags[], slides[{title,body,bullets[],footer}]}`
또는 그 객체의 배열, 또는 `{title,body,...}` 단축형.

**.html (블로그 원고)** — `<h1>`=커버 제목, `.intro-box`=커버 본문,
`<h2>`=섹션별 카드 1장(이후 첫 단락=본문), `.step-box`=불릿,
`span.tag`=해시태그. `<script>/<style>/.recommend-area/.img-area`는 제외.
`--max-slides N`으로 장수 상한(초과 시 커버·마지막 유지, 중간 컷),
`--handle`로 푸터 일괄 지정. 형식이 다른 원고도 '있으면 활용·없으면 생략'
방식이라 깨지지 않음. 정밀한 N장 요약/재구성은 P5(AI) 예정.

예제: `examples/` 폴더. `examples/make_test_bg.py`는 테스트 배경 PNG 생성기.

## 배경 옵션

```
--bg "solid:#0F172A"
--bg "gradient:#6D5DF6-#1E1B4B@135"            # @각도(deg)
--bg "image:assets/test_bg.png"                # 이미지 배경 (cover 크롭)
--bg "image:assets/bg.jpg?dim=35&scrim=bottom" # 가독성 오버레이
(미지정 시 포맷 기본 배경)
```

**이미지 배경 옵션** (`image:경로?opt=val&...`)

| 옵션 | 값 | 설명 | 기본 |
|------|-----|------|------|
| `dim` | 0~100 | 검정 오버레이 불투명도(%) | 0 |
| `scrim` | top \| bottom \| both | 가독성용 어둠 그라데이션 | 없음 |
| `fit` | cover \| contain | 캔버스 맞춤 | cover |
| `embed` | data \| link | base64 내장 / 파일 경로 참조 | data |

기본은 base64 내장이라 SVG 한 파일만으로 이식 가능. 테스트 배경이 없으면:
`python examples\make_test_bg.py assets\test_bg.png 1080 1080`

AI 자동 배경 생성은 P7에서 동일한 `image:` 경로를 재사용해 추가됩니다.

## AI 텍스트 (P5)

프로바이더 추상화 — 기본 **Gemini**, `config/settings.yaml`의 `ai.provider`로
`openai` 전환 가능. 모델 기본값: Gemini=`gemini-2.5-flash`, OpenAI=`gpt-4o-mini`
(`--ai-model`로 override).

**키 설정** (파일보다 환경변수 권장):
```powershell
$env:GEMINI_API_KEY = "..."     # 또는 GOOGLE_API_KEY
# OpenAI 사용 시: $env:OPENAI_API_KEY = "..."
```

| 용도 | 명령 |
|------|------|
| 키워드 → 카드뉴스 | `--source keyword --text "키워드" --max-slides 8` |
| 긴 글 의미 재구성 | `--source html --input x.html --ai-summarize --max-slides 8` |

- `--ai-summarize`는 text/file/html 어디에나 적용 — 원고를 정확히 N장으로 압축
- 응답은 `assets/cache/ai/`에 (프로바이더+모델+프롬프트) 해시로 캐시 →
  같은 입력은 무료·즉시, **캐시가 있으면 키 없이도 동작**. 무시하려면 `--ai-refresh`
- 결정적 추출(`html` 단독)과 달리 사실 압축·재배열까지 수행

## 구조

```
config/formats.yaml      디자인 포맷 카탈로그
src/insta_gen/
  models.py              Content / Slide / RenderedSVG
  formats.py             formats.yaml 로더
  sources/               주제 소스 (text, file, [url, keyword])
  render/                SVG 빌더 + CJK 줄바꿈 + 배경
  cli.py                 CLI (formats / generate / preview)
examples/                샘플 입력
output/                  생성 결과
  <yymmdd>/<keyword>/      *.svg  (날짜·키워드별 분리)
  index.html               preview (하위폴더 재귀)
```

**출력 경로 규칙**: SVG는 `output/<yymmdd>/<keyword>/` 에 저장됩니다.
- `<yymmdd>`: `--date` > 입력경로의 6자리 폴더(예: `src/.../260518/`) > 오늘
- `<keyword>`: `--name` > 제목/주제 슬러그 (배치는 콘텐츠별 폴더)
