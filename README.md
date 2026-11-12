# jtwjs-desk

Claude Code 세션을 여러 개 동시에 돌리면 어느 세션이 막혔는지, 내가 판정할 일이 어디에 쌓였는지 흩어져 놓치기 쉽다. 그걸 한 화면(`127.0.0.1`)에 모아 보는 Claude Code 플러그인.

<img width="720" alt="판정 화면" src="https://github.com/user-attachments/assets/977da575-b5bd-4c6a-acdc-b79b5fb5fb02" />

- **훅은 토큰을 쓰지 않는다**: 상태 파일만 쓰고 끝낸다. 모델에 글을 넣지 않는다.
- **로컬 전용**: 서버는 `127.0.0.1`에만 열리고, 쓰기 요청은 토큰 헤더를 요구한다. 외부 패키지 없이 Python 표준 라이브러리만 쓴다.

## 화면

좌측 메뉴에서 고른다. 보이는 탭만 15초 간격으로 갱신한다.

| 메뉴 | 보여 주는 것 | 쓰기 |
|---|---|---|
| 트랙 | 세션별 상태(작업 중 · 승인 대기 · 막힘) | 없음 |
| 판정 | 지휘가 올린 선택지. 고르면 지휘가 읽어 반영 | 선택 |
| 복습함 | 복습 대기 카드 | 완료 표시 |
| 3역량 | AI 워크플로우 · 적극성 · 풀스택 기록 | 없음 |
| 주간 롤업 | 이번 주 세션 · 커밋 · 학습 카드 | 없음 |
| 레포 건강도 | 레포별 점수와 등급 | 없음 |
| 회고 | wiki가 올린 질문에 답을 남기는 우편함 | 답 쓰기 |
| 기술 동향 | 오늘의 글, 안 읽은 글, 북마크, 읽은 이력 잔디 | 읽음 · 북마크 |

## 동작

```
Claude Code 훅 ──▶ ~/.jtwjs-desk/ (상태 파일)  ◀── page/server.py ──▶ 브라우저
지휘 ── scripts/desk.py ask / picks ──▶ 판정 파일 ◀───────┘
wiki ──▶ 동향 · 회고 질문 파일 ──(읽기)──▶ desk ──(덧붙이기)──▶ 읽음 · 북마크 · 회고 답 파일
```

- 다른 레포의 기록은 읽기만 한다. wiki가 쓰는 파일은 desk가 고치지 않고, desk가 쓰는 파일은 wiki가 고치지 않는다.
- 채점·일일 허브 스크립트는 실행하지 않는다.

## 시작

요구: Python 3

```bash
claude --plugin-dir /path/to/jtwjs-desk    # 로컬 플러그인으로 로드
```

세션을 시작하면 `SessionStart` 훅이 서버를 띄운다. 기본 포트는 `47615`.

## 판정 올리기 · 읽기 (지휘용 CLI)

```bash
python3 scripts/desk.py ask <repo> -                # stdin의 JSON 질문을 올림
python3 scripts/desk.py picks --new --repo <repo>   # 반영 안 된 새 선택 읽기
python3 scripts/desk.py applied <repo> <id>         # 반영 완료 표시
python3 scripts/desk.py prune --days 7              # 오래된 것 정리
```

절차는 [`skills/decision-inbox`](skills/decision-inbox/SKILL.md).

## 설정

| 항목 | 기본값 | 바꾸는 법 |
|---|---|---|
| 설정 파일 | `~/.config/jtwjs-desk/config.json` | `DESK_CONFIG` |
| 상태 디렉터리 | `~/.jtwjs-desk/` | `DESK_HOME` |
| 포트 | `47615` | `DESK_PORT` |

설정 파일이 없으면 `conductor.json`으로 폴백하고, 폴백 중임을 화면 위 안내 줄로 알린다.

`config.json`의 파일 경로 키로 기능을 켠다. 비어 있으면 화면이 「설정 없음」 이유를 보여 준다.

| 키 | 용도 |
|---|---|
| `routine_questions` · `routine_answers` | 회고 질문(읽기) · 답(덧붙이기) |
| `trends_items` | 기술 동향 글(읽기). 한 줄에 `{id, date, title, url, summary}` |
| `trends_reads` · `trends_marks` | 읽음 · 북마크(덧붙이기) |

## 개발

```bash
python3 -m unittest discover -s tests    # 519개
```

```
desk/      순수 로직 (설정 · 원장 읽기 · 롤업 · 동향 · 검증)
hooks/     훅 진입점 (상태 파일만 씀)
page/      서버 + 단일 HTML
scripts/   지휘용 CLI
skills/    decision-inbox
docs/      기능별 PRD · ARCHITECTURE · ADR
```

의존 방향: `scripts/` · `hooks/` · `page/` → `desk/`. 셋은 서로 import하지 않는다.
기여 규칙은 [CLAUDE.md](CLAUDE.md), 하네스 사용법은 [.claude/README.md](.claude/README.md).

## 상태

개인용 도구, private 레포. 화면 재설계(다크 · 좌측 메뉴)는 구현됐고, 설계는 [`.claude/design/`](.claude/design/)에 있다.
