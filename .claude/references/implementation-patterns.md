# 구현 패턴 — 증상 → 변환 → 검증

> **이 파일은 자동으로 로드되지 않는다.** `.claude/rules/functional-programming.md`의 ⏬ 트리거에 걸렸을 때만 열린다. 그래서 길어도 된다 — 평소 비용은 0이다.

각 패턴은 **증상(언제) → 변환(어떻게) → 검증(됐는지 아는 법)** 3단이다.

---

## 1. 함수형 코어 + 가변 쉘

**증상** — 테스트를 쓰려는데 목(mock)이 2개 이상 필요하다. "이걸 어떻게 테스트하지"가 먼저 든다.

**변환** — **결정하는 부분**(순수)과 **작용하는 부분**(부수효과)을 가른다.

```ts
// Before — 결정과 작용이 한 덩어리. 목 없이는 테스트 불가
const processOrder = (order: Order, db: Database) => {
  if (order.total > 1000) order.discount = 0.1   // 결정 + 변이
  db.save(order)                                  // 작용
}

// After
const decideDiscount = (order: Order): Order =>   // 코어: 목 0개로 테스트
  order.total > 1000 ? { ...order, discount: 0.1 } : order

const processOrder = (order: Order, db: Database) => {
  db.save(decideDiscount(order))                  // 쉘: 얇다
}
```

**검증** — 코어 테스트에 목이 **0개**인가. 쉘에 남은 줄이 **한두 줄**인가.

---

## 2. 암묵적 입력 승격

**증상** — 함수 안에서 전역 설정·현재 시각·난수·환경변수를 읽는다. 테스트에서 그걸 흉내 내야 한다.

**변환** — **인자로 올린다.** 값을 만드는 책임은 호출부로.

```ts
// Before
const isExpired = (item: Item) => Date.now() > item.expiresAt   // 시각이 암묵적 입력

// After
const isExpired = (item: Item, now: number) => now > item.expiresAt
// 호출부: isExpired(item, Date.now())
```

**검증** — 같은 인자로 부르면 **몇 번을 불러도 같은 값**이 나오는가. 테스트에서 시각·난수를 조작할 필요가 사라졌는가.

---

## 3. 암묵적 출력 격리

**증상** — 함수가 값도 돌려주면서 로깅·저장·이벤트 발행도 한다.

**변환** — **결과를 값으로 반환**하고, 작용은 호출부에서.

```ts
// Before
const calc = (price: number) => {
  const vat = price * rate      // 암묵적 입력
  logger.info(`vat=${vat}`)     // 암묵적 출력
  return price + vat
}

// After
const calc = (price: number, rate: number) =>
  ({ total: price + price * rate, vat: price * rate })

const { total, vat } = calc(1000, 0.2)
logger.info(`vat=${vat}`)       // 작용은 바깥
```

**검증** — 이 함수를 호출해도 **바깥세상에 아무 일도 안 생기는가**.

---

## 4. 카피-온-라이트 (중첩 포함)

**증상** — 중첩된 데이터를 수정해야 한다. 최상위만 복사했는데 원본이 같이 바뀐다.

**변환** — **쓰기를 읽기로 바꾼다.** 복사 → 수정 → 반환. 중첩은 **경로를 따라 내려가며** 복사한다.

```ts
// ❌ 얕은 복사 — 안쪽은 여전히 공유된다
const next = { ...state }
next.items[0].done = true        // 원본도 바뀐다

// ✅ 경로를 따라 복사
const next = {
  ...state,
  items: state.items.map((it, i) =>
    i === 0 ? { ...it, done: true } : it
  ),
}
```

**검증** — 원본을 나중에 읽어도 **바뀌지 않았는가**. 배열은 `push`/`splice`/`sort` 대신 `map`/`filter`/`concat`/`toSorted`를 썼는가.

---

## 5. 추상화 수준 정렬

**증상** — 한 함수에 도메인 규칙(할인 정책)과 저수준 조작(인덱스 루프)이 같이 있다.

**변환** — 본문을 **같은 계층의 것들로만** 구성하고, 낮은 것은 아래로 위임한다.

```ts
// Before — 비즈니스 규칙과 배열 인덱스가 한 곳에
const applyDiscount = (cart: Item[]) => {
  let total = 0
  for (let i = 0; i < cart.length; i++) total += cart[i].price
  return total > 50000 ? total * 0.9 : total
}

// After — 본문이 전부 같은 높이
const applyDiscount = (cart: Item[]) => {
  const total = sumPrices(cart)
  return isEligible(total) ? discount(total) : total
}
```

**검증** — 본문의 각 줄이 **비슷한 높이의 이름**으로 읽히는가. *"쓰는 쪽에서 어떤 자료구조인지 알아야 한다면"* 아직 낮은 계층이 새어 있다.

---

## 6. 실패를 값으로

**증상** — `try/catch`가 실행 흐름을 갈라놓아 어디로 튈지 읽기 어렵다. 예외를 잡는 곳과 던지는 곳이 멀다.

**변환** — **예상 가능한 실패**는 반환값으로 표현한다. 예외는 *진짜 예외적인 것*에만 남긴다.

```ts
// Before
const parse = (s: string) => {
  const n = Number(s)
  if (Number.isNaN(n)) throw new Error("invalid")   // 흐름이 갈라진다
  return n
}

// After
type Result<T> = { ok: true; value: T } | { ok: false; error: string }

const parse = (s: string): Result<number> => {
  const n = Number(s)
  return Number.isNaN(n) ? { ok: false, error: "invalid" } : { ok: true, value: n }
}
```

**검증** — 호출부가 **분기로 읽히는가**(try/catch 없이). 실패가 타입에 드러나 **처리를 빼먹으면 컴파일러가 잡는가**.

---

## 패턴을 늘리기 전에

7번째 패턴은 **같은 종류의 지적이 리뷰에서 3회 반복된 뒤**에 추가한다(`BACKLOG.md`).
두 번까지는 우연이고 세 번째가 패턴이다.
