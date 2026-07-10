/*
 * 백엔드 API 호출 래퍼.
 * 데모 기준 백엔드는 http://localhost:8000 에서 동작한다.
 * (배포 위치가 바뀌면 API_BASE만 수정하면 된다.)
 */

var API_BASE = "http://localhost:8000";

// 전체 문의 목록 (최신순)
function getInquiries() {
  return fetch(API_BASE + "/inquiries").then(function (res) {
    if (!res.ok) throw new Error("GET /inquiries " + res.status);
    return res.json();
  });
}

// 최종 답변 저장 (관리자 승인/작성)
function patchAnswer(inquiryId, finalAnswer) {
  return fetch(API_BASE + "/inquiries/" + encodeURIComponent(inquiryId), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ final_answer: finalAnswer }),
  }).then(function (res) {
    if (!res.ok) throw new Error("PATCH /inquiries " + res.status);
    return res.json();
  });
}

// 문의 등록 (그래프 파이프라인 실행)
function postInquiry(text) {
  return fetch(API_BASE + "/inquiries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: text }),
  }).then(function (res) {
    if (!res.ok) throw new Error("POST /inquiries " + res.status);
    return res.json();
  });
}

window.API_BASE = API_BASE;
window.getInquiries = getInquiries;
window.patchAnswer = patchAnswer;
window.postInquiry = postInquiry;
