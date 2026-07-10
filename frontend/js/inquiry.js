/* 문의 등록 페이지 동작 (데모 — 실제 저장 없음) */
(function () {
  var textarea = document.getElementById("question");
  var btn = document.getElementById("submit-btn");
  var toast = document.getElementById("toast");
  var toastTimer = null;

  function showToast() {
    toast.classList.add("show");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toast.classList.remove("show");
    }, 2500);
  }

  btn.addEventListener("click", function () {
    var value = textarea.value.trim();
    if (!value) {
      textarea.focus();
      return;
    }
    // 데모: 실제 등록/API 호출 없이 안내만 표시하고 입력창 초기화
    textarea.value = "";
    showToast();
  });
})();
