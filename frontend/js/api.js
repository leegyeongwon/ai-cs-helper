/*
 * 백엔드 API 호출 래퍼.
 * 데모 기준 백엔드는 http://localhost:8000 에서 동작한다.
 * (배포 위치가 바뀌면 API_BASE만 수정하면 된다.)
 */

var API_BASE = "http://localhost:8000";

// 전체 문의 목록 (최신순)
function getInquiries() {
  log("GET", API_BASE + "/inquiries");
  return fetch(API_BASE + "/inquiries").then(function (res) {
    if (!res.ok) throw new Error("GET /inquiries " + res.status);
    return res.json();
  }).then(function (data) {
    log("GET /inquiries ->", data.length, "건");
    return data;
  }).catch(function (err) {
    logError("GET /inquiries 실패:", err.message);
    throw err;
  });
}

// 최종 답변 저장 (관리자 승인/작성)
function patchAnswer(inquiryId, finalAnswer) {
  log("PATCH /inquiries/" + inquiryId);
  return fetch(API_BASE + "/inquiries/" + encodeURIComponent(inquiryId), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ final_answer: finalAnswer }),
  }).then(function (res) {
    if (!res.ok) throw new Error("PATCH /inquiries " + res.status);
    return res.json();
  }).then(function (data) {
    log("PATCH /inquiries/" + inquiryId + " -> 저장 완료");
    return data;
  }).catch(function (err) {
    logError("PATCH /inquiries 실패:", err.message);
    throw err;
  });
}

// 상담 내역 영구 삭제
function deleteInquiry(inquiryId) {
  log("DELETE /inquiries/" + inquiryId);
  return fetch(API_BASE + "/inquiries/" + encodeURIComponent(inquiryId), {
    method: "DELETE",
  }).then(function (res) {
    if (!res.ok) throw new Error("DELETE /inquiries " + res.status);
    return res.json();
  }).then(function (data) {
    log("DELETE /inquiries/" + inquiryId + " -> 삭제 완료");
    return data;
  }).catch(function (err) {
    logError("DELETE /inquiries 실패:", err.message);
    throw err;
  });
}

// 문의 등록 (그래프 파이프라인 실행)
function postInquiry(text) {
  log("POST /inquiries (" + text.length + "자)");
  return fetch(API_BASE + "/inquiries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: text }),
  }).then(function (res) {
    if (!res.ok) throw new Error("POST /inquiries " + res.status);
    return res.json();
  }).then(function (data) {
    log("POST /inquiries -> inquiry_id=" + data.inquiry_id);
    return data;
  }).catch(function (err) {
    logError("POST /inquiries 실패:", err.message);
    throw err;
  });
}

window.API_BASE = API_BASE;
window.getInquiries = getInquiries;
window.patchAnswer = patchAnswer;
window.postInquiry = postInquiry;
window.deleteInquiry = deleteInquiry;
