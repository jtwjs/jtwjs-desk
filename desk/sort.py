"""세션 상태의 유휴 판정 · 유효 상태 계산 · 정렬 순서.

`now`는 전부 인자로 받는다(모듈 안에서 `time.time()`을 직접 부르지 않는다,
implementation-patterns.md 패턴 2 — 암묵적 입력 승격).
"""

_IDLE_THRESHOLD_SECONDS = 600  # 10분, ADR-002

_SORT_ORDER = {
    "승인 대기": 0,
    "신호 없음": 1,
    "입력 대기": 2,
    "작업 중": 3,
    "완료": 4,
}
_UNKNOWN_SORT_KEY = 5


def is_idle(status: str, last_at: float, now: float) -> bool:
    """작업 중 상태인데 마지막 활동이 10분을 넘었는가."""
    return status == "작업 중" and (now - last_at) > _IDLE_THRESHOLD_SECONDS


def effective_status(status: str, last_at: float, now: float) -> str:
    """유휴면 '신호 없음', 아니면 원래 상태 그대로."""
    return "신호 없음" if is_idle(status, last_at, now) else status


def sort_key(effective_status_value: str) -> int:
    """정렬 순서: 승인 대기(0) > 신호 없음(1) > 입력 대기(2) > 작업 중(3) > 완료(4).

    모르는 값은 가장 뒤로 보낸다(5).
    """
    return _SORT_ORDER.get(effective_status_value, _UNKNOWN_SORT_KEY)


def sort_sessions(sessions: list, now: float) -> list:
    """각 세션에 effectiveStatus를 적용해 sort_key 오름차순으로 정렬한 새 리스트.

    원본 리스트와 세션 딕셔너리는 바뀌지 않는다(카피-온-라이트).
    """

    def with_effective_status(session: dict) -> dict:
        status = session.get("status")
        last_at = session.get("lastAt", 0)
        return {**session, "effectiveStatus": effective_status(status, last_at, now)}

    decorated = [with_effective_status(s) for s in sessions]
    return sorted(decorated, key=lambda s: sort_key(s["effectiveStatus"]))
