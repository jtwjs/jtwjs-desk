# 디자인 레퍼런스 기록

> 남의 화면은 로컬에만 둔다(`.gitignore`가 이 폴더의 `README.md`만 허용). 다른 머신에서는 아래 출처를 보고 다시 구한다. 기록일: 2026-11-11.

## 기준

**Better Stack**을 UI/UX 기준으로 쓴다(구조 + 다크 톤까지, Finn 결정). 요소 수는 Better Stack만큼 늘리지 않는다 — `brief.md`의 「복잡도 원칙」 참고. Mobbin의 디자인 문서는 형식 틀과 컴포넌트 이름 참고로만 쓴다.

## 로컬 사본 (커밋 안 함)

| 파일 | 무엇 | 출처 |
|---|---|---|
| `betterstack-uptime-reporting.webp` | Better Stack Uptime > Reporting > Resolved 화면. 원본 이름 `file.png`였으나 실제 형식은 WebP(VP8 손실 압축, 1440×1020). 하단에 Mobbin 큐레이션 표기 | Finn이 저장한 이미지 |
| `betterstack-telemetry-live-tail.png` | Better Stack Telemetry > Live tail 화면(2535×1464, 무손실). 로그 시각이 2025-08-13 | Finn이 저장한 이미지 |
| `DESIGN-mobbin.md` | Mobbin 자체 디자인 언어를 분석한 문서(562줄). 라이트 톤 · 알약 컨트롤 · 마케팅 사이트 기준 | Finn이 제공한 파일 |

웹에서 내려받은 파일은 없다. 위 셋은 모두 Finn이 이미 갖고 있던 로컬 파일을 복사했다.

## 출처 URL

- Better Stack 공식 브랜드 가이드: https://betterstack.com/docs/brand/ — 브랜드 색 4개(로고 색), 로고 · 색 이미지가 라이트/다크로 나뉨. 글꼴 · 상태색 · UI 토큰 설명 없음
- SaaSFrame의 Better Uptime 화면(이미지 내용은 아직 못 봄, 2023년 등록분): https://www.saasframe.io/examples/better-uptime-monitors-dashboard · https://www.saasframe.io/examples/better-uptime-incidents-dashboard
- Tailwind CSS v3.4.17 기본 팔레트(상태색 기준 세트): https://v3.tailwindcss.com/docs/customizing-colors — v4는 값이 달라서 v3로 고정
- Mobbin: https://mobbin.com — 위 Uptime 이미지의 큐레이션 출처. Mobbin 안의 Better Stack 화면은 못 찾음(로그인 필요)

## 가져올 것 / 가져오지 않을 것

### Better Stack (Uptime · Telemetry 화면)

| 가져올 것 | 가져오지 않을 것 |
|---|---|
| 다크 톤: 바탕 세 단(콘텐츠 < 패널 · 레일 · 칩 · 표 헤더 < 올림면)과 한 단 밝은 구분선, 그림자 없음 | 아이콘 레일(제품 전환용, desk는 제품이 하나) · 둘째 컬럼 서브 내비 |
| 좌측 메뉴 패널 + **그룹 펼침**(부모 항목 · 들여쓴 하위 항목 · 왼쪽 가는 세로선) + 제목 옆 접기 버튼 | breadcrumb · 기간 선택 · Export CSV |
| 화면 제목 + 한 줄 설명 | 검색창 · 프리셋 · 시간 범위 · 저장/설정 아이콘 버튼 |
| 필터 칩 행(`라벨 \| 값 ⌄`) — 필요한 화면에만, 한 줄 | 도넛 · 히스토그램 차트 |
| 조밀한 표: muted 헤더, 열 이름 말줄임, 행 구분선, 줄 맨 앞 상태 **점 + 라벨** | 우하단 채팅 버튼 · 사용자 아바타/배지 · 브랜드 요소 |
| KPI 칸(주간 롤업에만) | 필터 항목을 여러 줄로 쌓는 구성 |
| 표 아래 한 줄 대기 문구(예: `Waiting for logs…`) · hover 툴팁 | 본문 전체를 고정폭으로 쓰기(고정폭은 ID · 경로에만) |

### Mobbin 디자인 문서 (`DESIGN-mobbin.md`)

| 가져올 것 | 가져오지 않을 것 |
|---|---|
| DESIGN.md 형식 틀(색 · 타입 · 반경 · 간격 · 컴포넌트 · Do/Don't) | 라이트 팔레트 · 알약(stadium) 컨트롤 |
| 컴포넌트 이름 참고(`ex-app-shell-row` · `ex-data-table-cell` · `ex-empty-state-card` · `ex-toast`) | 히어로 스케일 · 마키 · 가격표 · 푸터 · 포트레이트 · 떠 있는 상단 알약 내비 · 상업용 파랑 배지 의미 |
| "그림자 없이 톤 차이와 헤어라인으로 계층을 만든다"는 원칙(Better Stack에서도 같은 방식이 보임) | 의미색 없는 단색 상태 표기(desk는 상태 구분이 본업) |

### Linear · Vercel · GitHub

설계 세션에서 AI가 추천한 이름이다. **화면은 못 봤다**(이름만, 미확인). Vercel은 Geist Badge 문서에 의미별 색 규칙(초록=정상 · 빨강=에러 · 노랑=경고 · 파랑=정보 · 회색=중립)이 공식으로 있음을 확인했지만, 이번 상태색 제안은 이 문서를 쓰지 않는다(스타일 문서를 둘 섞으면 톤이 섞인다).

## 측정 기록 (참고용, 값 정본은 DESIGN.md 단계에서 확정)

두 이미지의 픽셀을 읽기 전용으로 읽어 영역별 최빈색과 글자색(배경에서 가장 먼 색)을 뽑았다.

- 방법 주의: macOS 이미지 로더의 기본 색 변환을 거치면 값이 밝아진다(예: `#1F2432`가 `#293041`로 어긋남을 확인). **변환 전 성분값**을 썼다. WebP는 손실 압축이라 ±3 정도 오차가 있다
- 얇은 글자의 색은 배경과 섞여 실제보다 흐리게 잡힌다. 증감 표시의 붉은색, 차트 막대 색은 못 쟀다(`미측정`)

| 역할 | Live tail(PNG, 기준값) | Uptime Reporting(WebP) |
|---|---|---|
| 콘텐츠 바탕 | `#202432` | `#1F2432` |
| 패널 · 레일 · 칩 · 표 헤더 | `#232837` | `#212838` |
| 올림면(선택 항목) · 구분선 | `#2A303F` | `#283140` |
| 요약 카드 안쪽 | — | `#1F2432`(콘텐츠 바탕과 같음, 테두리로 구분) |
| 글자 · 주 | `#FFFFFF` | `#FFFFFF` |
| 글자 · 본문 | `#B9BFCF` | `#A9ADBC` |
| 글자 · 흐림 | `#959DB6` | `#999FB2` ~ `#A2ABBC` |
| 글자 · 희미(축 숫자) | `#656D84` | — |
| 강조 | `#7E87F0` | 도넛 `#8895FF` · 선택 막대 `#8D8DD6` |

공식 브랜드 색(로고 색): `#5B63D3` · `#7C87F7` · `#0B0C14` · `#FFFFFF`. **`#0B0C14`는 UI 바탕이 아니다**(측정 결과 UI 바탕은 위 표의 `#202432` 계열).

## 못 구한 것 (후속)

- 목록 · 빈 · 에러 화면 캡처(Better Stack의 모니터 목록 등). Finn이 SaaSFrame 페이지나 Mobbin에서 캡처해 이 폴더에 넣으면 `design-critique`의 레퍼런스 실측 전에 채운다
- Linear · GitHub · Mobbin 앱 화면
