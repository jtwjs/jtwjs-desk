## 2026-11-13 — desk-tech-trends

- 숫자: step 8 · 완료 8 · 재시도 1 · error/blocked 0 · 소요 55m (`phases_status.py --retro desk-tech-trends`). `sdd-review` 1회차 지적 🟡 3건(미커밋 수정으로 해소), 🔴 없음
- 막힌 지점: ① step 4(`trends-get`)가 1회 재시도됐다. `/nav-counts` 키에 `trends`를 더하자 기존 키 집합 단언(`tests/test_desk_redesign_integration.py:36`)이 깨졌고, GREEN 단계에서 그 테스트 파일을 고치자 러너가 되돌리고 실패시켰다(`attempts` 기록). 앞 phase(`desk-routine-inbox`)에서 같은 키 집합 단언으로 한 번 막혔던 것과 같은 종류다. ② 리뷰가 오늘 화면의 `slice(0, 3)`을 잡았다. 서버는 오늘 글 전체를 세는데(배지·잔디 total) 화면이 3건만 그려 4번째 글이 숨었다. 8 step이 모두 통과한 뒤에야 나왔다. ③ Finn이 안내 텍스트 제거·북마크 버튼 글자 고정을 요청했다(화면 확인 뒤 나온 제품 결정이라 막힘은 아님)
- 원인 축: ① 맥락(앞 phase의 같은 함정이 step 문서 템플릿에 안 넘어옴 — 이번엔 step 문서에 적었는데도 에이전트가 GREEN에서 고침) ② 검증(서버 응답 단위 테스트와 화면 렌더가 따로 통과, 비명백 패턴 「서버 · 화면」과 같은 계열) ③ 해당 없음
- 남긴 자산: `.claude/rules/non-obvious-patterns.md` 두 줄(`/nav-counts` 키 집합 단언 · 화면이 서버 집계를 자르지 않기) · `tests/test_desk_trends.py`의 `test_오늘_글이_4건이면_split은_4건을_다_준다`
- 지울 후보: 없음
- 다음 후보: 건수 계산 실패 시 다른 메뉴 건수 유지(단위 테스트만)·북마크 버튼 키보드 포커스 링·잔디 hover 툴팁은 브라우저로 못 봄(`미측정`) · 현행 탭은 `작업: 화면` 탭과 함께 정리할 때 만든다(Finn 결정 B)
