## 2026-11-12 — desk-routine-inbox

- 숫자: step 7 · 완료 7 · 재시도 0 · error/blocked 0 · 소요 3h43m (`phases_status.py --retro desk-routine-inbox`). `sdd-review` 1회차 지적 없음
- 막힌 지점: ① step 4에서 `routine` 키를 `/nav-counts`에 더하자 기존 키 집합 단언 2곳이 깨졌는데 step 문서가 그 수정을 금지해 한 번 막혔다. 문서에 수정 허용을 적고(`c846a3f`) 재시도했다. 실패 시도는 `sdd-discard/desk-routine-inbox/step4-manual` 브랜치에 남았고 `index.json`의 `retries`는 0이다(손으로 처리한 건이라 러너가 못 셌다). ② step 5(`routine-endpoints`)가 2h48m 걸렸다. 기록이 없어 원인은 `미측정`(step별 `usage`·로그 없음). ③ PR 본문에 스크린샷을 넣을 때 JPEG에 `.png` 이름을 붙여 GitHub 업로드가 422로 거절됐다. `.jpg`로 바꾸자 통과(네트워크 기록으로 확인)
- 원인 축: ① 맥락(step 문서가 기존 테스트 수정 범위를 미리 못 짚음) ② 검증(측정 근거 없음) ③ 도구(`upload_image`의 파일명 확장자와 실제 형식 불일치)
- 남긴 자산: `.claude/rules/non-obvious-patterns.md` 한 줄(스크린샷 업로드 파일명 확장자 = 실제 형식) · `c846a3f`가 step 문서에 남긴 "기존 키 집합 단언 수정 허용" 문구
- 지울 후보: 없음
- 다음 후보: 기술 최신동향 3건 읽기 메뉴 + 읽은 이력 잔디(별도 작업) · 4000자 초과 거절 메시지와 탭 두 개 동시 열기는 화면에서 아직 못 봄(서버 테스트로만 확인) · 문항 수 기준은 첫 2주 쓰며 정함(`미측정`)
