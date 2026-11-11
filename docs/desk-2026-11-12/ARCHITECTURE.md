# ARCHITECTURE: desk 화면 재설계 구현

기본 구조(계층·경계·읽기 규약)는 `docs/desk-2026-11-03`·`docs/desk-2026-11-11`을 그대로 승계한다. 여기서는 바뀌는 것만 적는다.

## 변경 범위

| 파일 | 변경 |
|---|---|
| `page/index.html` | CSS 변수 전부 다크 토큰으로 교체, 상단 탭 → 좌측 메뉴, 공통 컴포넌트, 6개 화면 렌더 재배치 |
| `page/server.py` | `GET /nav-counts`, `GET /fonts/PretendardVariable.woff2`(그 파일 하나만) 추가 |
| `page/fonts/` | Pretendard 가변 woff2 + OFL 1.1 라이선스 사본(신규) |
| `desk/` | 변경 없음 (건수는 기존 `list_judgments` · `build_review`를 재사용) |
| `hooks/` · `scripts/` | 변경 없음 |

## 엔드포인트 (추가)

`GET /nav-counts` → `{"judge": N, "review": N}`. `check_host` 통과 필요. 기존 두 집계 함수를 호출해 세기만 한다. 아무것도 쓰지 않는다(ADR-009).

`GET /fonts/PretendardVariable.woff2` → 파일 바이트(`font/woff2`). `check_host` 통과 필요, 허용 이름 한 개 외에는 404(경로 조작 불가). 쓰기 없음. 서버가 `/`만 주던 구조라 폰트를 오프라인으로 주려면 이 경로가 필요하다(ADR-016 임시).

## UI 구조

```
body
├ nav#menu   (펼침 264 / 접힘 64, 상태는 localStorage 아님 — 세션 중 메모리만)
│  ├ 항목 6 (트랙 · 판정[배지] · 복습함[배지] · 3역량[그룹] · 주간 · 건강도)
│  └ 접기 버튼
└ main
   └ 화면 6 (보이는 것만 폴링 — ADR-010)
```

- 토큰은 `:root` CSS 변수 한 곳. 컴포넌트 CSS는 변수만 참조하고 색을 직접 쓰지 않는다
- 배지 폴링은 메뉴가 항상 보이므로 `/nav-counts`를 15초 주기로 따로 부른다(탭 폴링과 별개)
- 의존 방향·`page/`가 `hooks/`·`scripts/`를 import하지 않는 규칙 불변

## 테스트 전략 (testing.md §0 기준)

| 대상 | 테스트 |
|---|---|
| `/nav-counts` 집계(pick 없는 판정 수, 복습 items 수, 설정 없음·경로 없음) | 필수(도메인 판정) — 서버 테스트 |
| 메뉴·컴포넌트·화면 CSS/렌더 | 제외(프레젠테이션). 기존 `/` 토큰 치환 테스트가 회귀를 막는다 |
| 통합 | 서버를 띄워 `/` 와 `/nav-counts` 응답 확인 1개 |

## 확인 필요

- 실렌더(브라우저) 확인은 사람이 한다. 서버 테스트 통과는 화면 확인이 아니다
