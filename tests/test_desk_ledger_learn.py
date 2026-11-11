"""desk/ledger.py 중 학습 카드 · phase 관련 순수 함수 (step 2)."""
import unittest

from desk import ledger

INBOX = """# 학습 수신함 (지어낸 픽스처)

<!-- 카드 형식
## YYYY-MM-DD · 제목
- 종류: 기술 | 직무 | 도메인 | 막힌 질문
- vault:
-->
---

## 2026-01-02 · 샘플 개념 A
- 종류: 기술 · 출처: AI 설명
- 이 레포 어디: `src/sample/app.tsx`, `src/other/x.py`
- 요지: 샘플 요지 첫 줄
- 상태: 모름
- vault:

## 2026-01-03 · 샘플 개념 B
- 종류: 도메인 · 출처: 내가 물음
- 층: 회사
- 이 레포 어디: `docs/sample.md`
- 요지: 도메인 요지
- 상태: 설명 들음
- vault: 1_MyBrain/sample/b.md

## 2026-01-04 · 샘플 직무 C
- 종류: 직무
- 상태: 모름
- vault:

## 2026-01-05 · 샘플 질문 D
- 종류: 막힌 질문 · 출처: 빈틈 3곳
- 상태: 모름

## 이건 카드 헤딩이 아니다
- 종류: 기술
"""


class TestParseInbox(unittest.TestCase):
    def setUp(self):
        self.cards = ledger.parse_inbox(INBOX)

    def test_주석_안_예시_헤딩은_카드가_아니다(self):
        titles = [c["title"] for c in self.cards]
        self.assertNotIn("제목", titles)
        self.assertEqual(titles, ["샘플 개념 A", "샘플 개념 B", "샘플 직무 C", "샘플 질문 D"])

    def test_필드를_파싱한다(self):
        a = self.cards[0]
        self.assertEqual(a["date"], "2026-01-02")
        self.assertEqual(a["kind"], "기술")
        self.assertEqual(a["status"], "모름")
        self.assertEqual(a["where"], "src/sample/app.tsx")
        self.assertEqual(a["vault"], "")
        self.assertEqual(a["summary"], "샘플 요지 첫 줄")

    def test_종류_꼬리와_막힌_질문을_읽는다(self):
        self.assertEqual(self.cards[1]["kind"], "도메인")
        self.assertEqual(self.cards[3]["kind"], "막힌 질문")

    def test_vault_값이_있으면_읽는다(self):
        self.assertEqual(self.cards[1]["vault"], "1_MyBrain/sample/b.md")

    def test_없는_줄은_빈_문자열이다(self):
        self.assertEqual(self.cards[3]["vault"], "")
        self.assertEqual(self.cards[3]["where"], "")

    def test_빈_텍스트는_빈_목록이다(self):
        self.assertEqual(ledger.parse_inbox(""), [])


class TestReviewCards(unittest.TestCase):
    def test_vault가_빈_기술_도메인_막힌질문만_남기고_직무는_뺀다(self):
        cards = ledger.parse_inbox(INBOX)
        titles = [c["title"] for c in ledger.review_cards(cards)]
        self.assertEqual(titles, ["샘플 개념 A", "샘플 질문 D"])


class TestClassifyArea(unittest.TestCase):
    def test_도메인_종류는_경로와_무관하게_domain(self):
        self.assertEqual(ledger.classify_area("src/sample/app.tsx", "도메인"), "domain")

    def test_fe_신호(self):
        self.assertEqual(ledger.classify_area("src/a/b.tsx", "기술"), "fe")
        self.assertEqual(ledger.classify_area("src/components/x", "기술"), "fe")

    def test_be_신호(self):
        self.assertEqual(ledger.classify_area("svc/run.py", "기술"), "be")
        self.assertEqual(ledger.classify_area("src/main/x", "기술"), "be")

    def test_infra_신호(self):
        self.assertEqual(ledger.classify_area("Dockerfile", "기술"), "infra")
        self.assertEqual(ledger.classify_area(".github/workflows/ci.yml", "기술"), "infra")
        self.assertEqual(ledger.classify_area("infra/main.tf", "기술"), "infra")

    def test_둘_이상_맞으면_fe_be_infra_순(self):
        self.assertEqual(ledger.classify_area("app/server/x.py", "기술"), "fe")
        self.assertEqual(ledger.classify_area("deploy/run.py", "기술"), "be")

    def test_하나도_안_맞으면_미분류(self):
        self.assertEqual(ledger.classify_area("docs/sample.md", "기술"), "미분류")
        self.assertEqual(ledger.classify_area("", "기술"), "미분류")


class TestFullstackOrder(unittest.TestCase):
    def test_모름_설명들음_내말로_순서이고_모르는_값은_맨_뒤_같은_상태는_입력_순서(self):
        cards = [
            {"title": "1", "status": "내 말로 설명 가능"},
            {"title": "2", "status": "이상한 값"},
            {"title": "3", "status": "설명 들음"},
            {"title": "4", "status": "모름"},
            {"title": "5", "status": "모름"},
        ]
        got = [c["title"] for c in ledger.fullstack_order(cards)]
        self.assertEqual(got, ["4", "5", "3", "1", "2"])


class TestKeys(unittest.TestCase):
    def test_같은_제목은_같은_키_다른_제목은_다른_키(self):
        k = ledger.card_key("샘플 개념 A")
        self.assertEqual(k, ledger.card_key("샘플 개념 A"))
        self.assertNotEqual(k, ledger.card_key("샘플 개념 B"))
        self.assertRegex(k, r"^card-[0-9a-f]{8}$")

    def test_phase_키(self):
        self.assertEqual(ledger.phase_key("desk"), "phase-desk")


class TestSkippedPhases(unittest.TestCase):
    def test_skipped만_뽑고_reflect_없거나_틀리면_건너뛴다(self):
        indexes = [
            ("a", {"reflect": {"understanding_check": "skipped"}}),
            ("b", {"reflect": {"understanding_check": "done"}}),
            ("c", {"steps": []}),
            ("d", {"reflect": "skipped"}),
            ("e", {"reflect": None}),
            ("f", "깨진 값"),
            ("g", {"reflect": {"understanding_check": "skipped"}}),
        ]
        self.assertEqual(ledger.skipped_phases(indexes), ["a", "g"])


if __name__ == "__main__":
    unittest.main()
