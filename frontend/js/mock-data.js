/*
 * 데모용 더미 데이터 + 상수.
 * 실제 DB/API 없이 화면을 채우기 위한 목업이다.
 * 카테고리/상태 값은 아직 미정 → 아래 상수만 바꾸면 전체에 반영된다.
 */

// 문의 카테고리 (미정 — 샘플)
const CATEGORIES = ["일반", "긴급", "질문", "후기"];

// 처리 상태 (미정 — 샘플)
const STATUSES = ["접수", "처리중", "완료"];

// "처리대기" 탭에서 보여줄 상태들 (미정 — 확정 시 여기만 수정)
const PENDING_STATUSES = ["접수", "처리중"];

// 답변자 유형
const REVIEWER_AI = "AI";
const REVIEWER_HUMAN = "human";

// 규정 발췌 (app/rag/regulations.py 내용 일부) — retrieved_docs 현실감용
const R = {
  refundPeriod:
    "제1조 (환불 및 교환 기간) 구매자는 상품을 배송받은 날로부터 7일 이내에 환불 또는 교환을 신청할 수 있습니다.",
  shippingFee:
    "제2조 (반품 배송비 부담 주체) 구매자의 단순 변심으로 인한 환불 및 교환의 경우, 왕복 반품 배송비(6,000원)는 구매자가 부담합니다.",
  refundDenied:
    "제3조 (환불 불가 사유) 상품 훼손, 사용 흔적이 있는 경우, 맞춤형 주문 제작 상품 등은 환불이 불가합니다.",
  privacyKeep:
    "제5조 (법령에 따른 개인정보 보관 기간) 계약 또는 청약철회 등에 관한 기록: 5년 (전자상거래법).",
  pointExpire:
    "제6조 (일반 포인트의 유효기간) 일반 포인트의 유효기간은 적립일로부터 1년(365일)이며, 유효기간이 지난 포인트는 매월 말일 자정에 자동으로 소멸됩니다.",
  couponExpire:
    "제7조 (이벤트성 포인트 및 쿠폰 유효기간) 무상으로 발급된 할인 쿠폰은 다운로드 후 7일 이내에 사용해야 하며, 기간 연장이 불가능합니다.",
};

/*
 * 문의 목록.
 * 답변 상태 3종류를 모두 포함한다:
 *  (A) final_answer 있음        → 읽기 전용 표시
 *  (B) ai_answer만 있음         → 편집 가능한 textarea + 저장
 *  (C) 둘 다 없음               → 빈 작성창 (AI가 처리 어렵다고 판단)
 */
const MOCK_INQUIRIES = [
  {
    inquiry_id: "a1f0c2e4-0001-4a10-9c01-000000000001",
    created_at: "2026-07-08 09:12",
    question: "지난주에 산 티셔츠가 사이즈가 안 맞아요. 교환 가능한가요?",
    categories: "질문",
    status: "완료",
    reviewer_type: REVIEWER_AI,
    retrieved_docs: [R.refundPeriod, R.shippingFee],
    ai_answer:
      "안녕하세요. 상품을 배송받으신 날로부터 7일 이내라면 교환 신청이 가능합니다. 단순 변심에 의한 교환의 경우 왕복 배송비 6,000원이 부담되는 점 참고 부탁드립니다.",
    final_answer:
      "안녕하세요, 고객님. 배송받으신 날로부터 7일 이내라면 사이즈 교환이 가능합니다. 단순 변심 교환은 왕복 배송비 6,000원이 발생하니 참고해 주세요. 교환 접수 도와드릴까요?",
  },
  {
    inquiry_id: "a1f0c2e4-0002-4a10-9c01-000000000002",
    created_at: "2026-07-09 14:03",
    question: "적립한 포인트가 갑자기 사라졌어요. 왜 없어진 건가요?",
    categories: "일반",
    status: "처리중",
    reviewer_type: REVIEWER_AI,
    retrieved_docs: [R.pointExpire],
    ai_answer:
      "일반 포인트의 유효기간은 적립일로부터 1년(365일)이며, 기간이 지난 포인트는 매월 말일 자정에 자동 소멸됩니다. 소멸 예정 포인트는 소멸 30일 전 안내드리고 있습니다.",
    final_answer: null,
  },
  {
    inquiry_id: "a1f0c2e4-0003-4a10-9c01-000000000003",
    created_at: "2026-07-09 18:47",
    question:
      "주문한 상품에 하자가 있어서 사진 첨부합니다. 환불하고 싶은데 배송비는 누가 내나요?",
    categories: "긴급",
    status: "처리중",
    reviewer_type: REVIEWER_AI,
    retrieved_docs: [R.refundPeriod, R.shippingFee],
    ai_answer:
      "상품 하자로 인한 환불의 경우 반품 배송비는 판매자가 부담합니다. 접수해 주시면 확인 후 환불 처리해 드리겠습니다.",
    final_answer: null,
  },
  {
    inquiry_id: "a1f0c2e4-0004-4a10-9c01-000000000004",
    created_at: "2026-07-10 08:21",
    question: "탈퇴하면 제 개인정보는 바로 삭제되나요?",
    categories: "질문",
    status: "접수",
    reviewer_type: REVIEWER_AI,
    retrieved_docs: [R.privacyKeep],
    ai_answer:
      "회원 탈퇴 시 개인정보는 지체 없이 파기하는 것이 원칙이나, 전자상거래법 등 관계법령에 따라 일정 기간(예: 계약·청약철회 기록 5년) 보관될 수 있습니다.",
    final_answer: null,
  },
  {
    inquiry_id: "a1f0c2e4-0005-4a10-9c01-000000000005",
    created_at: "2026-07-10 10:05",
    question:
      "담당자님 진짜 화나네요. 어제부터 계속 연락했는데 왜 답이 없죠? 당장 책임자 바꿔주세요.",
    categories: "긴급",
    status: "접수",
    reviewer_type: REVIEWER_HUMAN,
    retrieved_docs: [],
    ai_answer: null,
    final_answer: null,
  },
  {
    inquiry_id: "a1f0c2e4-0006-4a10-9c01-000000000006",
    created_at: "2026-07-06 11:32",
    question: "쿠폰 받았는데 유효기간이 언제까지인가요?",
    categories: "질문",
    status: "완료",
    reviewer_type: REVIEWER_AI,
    retrieved_docs: [R.couponExpire],
    ai_answer:
      "무상으로 발급된 할인 쿠폰은 다운로드 후 7일 이내에 사용하셔야 하며, 기간 연장은 불가능합니다.",
    final_answer:
      "무상 발급 할인 쿠폰은 다운로드 후 7일 이내 사용하셔야 하며 연장은 불가합니다. 마이페이지 > 쿠폰함에서 정확한 만료일을 확인하실 수 있어요.",
  },
  {
    inquiry_id: "a1f0c2e4-0007-4a10-9c01-000000000007",
    created_at: "2026-07-05 16:58",
    question: "배송 정말 빠르고 포장도 꼼꼼하네요! 잘 쓰겠습니다 :)",
    categories: "후기",
    status: "완료",
    reviewer_type: REVIEWER_AI,
    retrieved_docs: [],
    ai_answer:
      "따뜻한 후기 남겨주셔서 진심으로 감사드립니다! 앞으로도 좋은 상품과 서비스로 보답하겠습니다.",
    final_answer:
      "소중한 후기 감사합니다, 고객님! 만족하셨다니 저희도 기쁩니다. 앞으로도 좋은 상품으로 찾아뵙겠습니다 :)",
  },
  {
    inquiry_id: "a1f0c2e4-0008-4a10-9c01-000000000008",
    created_at: "2026-07-07 13:19",
    question: "맞춤 제작으로 주문한 반지인데 마음에 안 들어서 환불하고 싶어요.",
    categories: "일반",
    status: "처리중",
    reviewer_type: REVIEWER_AI,
    retrieved_docs: [R.refundDenied],
    ai_answer:
      "맞춤형 주문 제작 상품은 환불이 불가한 상품에 해당합니다. 다만 상품에 하자가 있는 경우에는 환불이 가능하니 자세한 상황을 알려주시면 확인해 드리겠습니다.",
    final_answer: null,
  },
  {
    inquiry_id: "a1f0c2e4-0009-4a10-9c01-000000000009",
    created_at: "2026-07-10 09:48",
    question: "제 계좌로 결제된 금액이 두 번 빠져나갔는데 확인 부탁드립니다. 카드번호는 1234-5678-...",
    categories: "긴급",
    status: "접수",
    reviewer_type: REVIEWER_HUMAN,
    retrieved_docs: [],
    ai_answer: null,
    final_answer: null,
  },
  {
    inquiry_id: "a1f0c2e4-0010-4a10-9c01-000000000010",
    created_at: "2026-07-04 20:11",
    question: "환불 신청했는데 언제 입금되나요?",
    categories: "일반",
    status: "완료",
    reviewer_type: REVIEWER_HUMAN,
    retrieved_docs: [R.refundPeriod],
    ai_answer:
      "환불은 승인 후 카드사·결제수단에 따라 영업일 기준 3~5일 정도 소요될 수 있습니다.",
    final_answer:
      "환불 승인 완료되었고, 결제하신 카드사 기준 영업일 3~5일 내 입금 예정입니다. 지연 시 다시 문의 주세요!",
  },
  {
    inquiry_id: "a1f0c2e4-0011-4a10-9c01-000000000011",
    created_at: "2026-07-08 22:40",
    question: "후기 이벤트 포인트는 언제 들어오나요?",
    categories: "후기",
    status: "처리중",
    reviewer_type: REVIEWER_AI,
    retrieved_docs: [R.pointExpire],
    ai_answer:
      "이벤트로 지급되는 포인트는 별도 공지가 없는 한 지급일로부터 30일간 유효하며, 후기 확인 후 순차 지급됩니다.",
    final_answer: null,
  },
  {
    inquiry_id: "a1f0c2e4-0012-4a10-9c01-000000000012",
    created_at: "2026-07-03 15:27",
    question: "교환 절차가 어떻게 되나요? 처음이라 잘 모르겠어요.",
    categories: "질문",
    status: "완료",
    reviewer_type: REVIEWER_AI,
    retrieved_docs: [R.refundPeriod, R.shippingFee],
    ai_answer:
      "배송받으신 날로부터 7일 이내에 마이페이지 > 주문내역에서 교환 신청이 가능합니다. 단순 변심 시 왕복 배송비가 발생할 수 있습니다.",
    final_answer:
      "마이페이지 > 주문내역 > 교환신청에서 접수하시면 됩니다. 배송 후 7일 이내 신청 가능하고, 단순 변심 교환은 왕복 배송비 6,000원이 발생해요. 도와드릴까요?",
  },
];

// 전역 노출 (클래식 script 로드 방식)
window.CATEGORIES = CATEGORIES;
window.STATUSES = STATUSES;
window.PENDING_STATUSES = PENDING_STATUSES;
window.MOCK_INQUIRIES = MOCK_INQUIRIES;
