/* 관리자 페이지 동작 (데모 — 더미 데이터로 동작, 실제 API 없음) */
(function () {
  "use strict";

  var inquiries = window.MOCK_INQUIRIES;     // 메모리상 작업본 (저장 시 여기 반영)
  var CATEGORIES = window.CATEGORIES;
  var STATUSES = window.STATUSES;
  var PENDING_STATUSES = window.PENDING_STATUSES;

  // 뷰별 상태: 선택 항목 + 필터 + 정렬
  var viewState = {
    all: { selectedId: null, category: "전체", status: "전체", sort: "newest" },
    pending: { selectedId: null, category: "전체", status: "전체", sort: "newest" },
  };

  // ---------- 유틸 ----------
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function el(html) {
    var t = document.createElement("template");
    t.innerHTML = html.trim();
    return t.content.firstChild;
  }
  function reviewerLabel(r) {
    return r === "AI" ? "AI" : "상담원";
  }
  function pct(value, total) {
    return total ? Math.round((value / total) * 100) : 0;
  }

  // 뷰의 기본 데이터 (필터 적용 전) — 탭 배지·통계용
  function baseData(view) {
    if (view === "pending") {
      return inquiries.filter(function (i) {
        return PENDING_STATUSES.indexOf(i.status) >= 0;
      });
    }
    return inquiries.slice();
  }

  // 필터 + 정렬 적용된 표시용 데이터
  function visibleData(view) {
    var s = viewState[view];
    var rows = baseData(view).filter(function (i) {
      if (s.category !== "전체" && i.categories !== s.category) return false;
      if (s.status !== "전체" && i.status !== s.status) return false;
      return true;
    });

    rows.sort(function (a, b) {
      // 처리대기: 긴급 카테고리를 항상 최상단으로
      if (view === "pending") {
        var ua = a.categories === "긴급" ? 0 : 1;
        var ub = b.categories === "긴급" ? 0 : 1;
        if (ua !== ub) return ua - ub;
      }
      var cmp = a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0;
      return s.sort === "oldest" ? cmp : -cmp;
    });
    return rows;
  }

  function findById(id) {
    for (var i = 0; i < inquiries.length; i++) {
      if (inquiries[i].inquiry_id === id) return inquiries[i];
    }
    return null;
  }

  // ---------- 툴바 (필터/정렬) ----------
  function optionList(values, current) {
    return values.map(function (v) {
      return '<option value="' + esc(v) + '"' + (v === current ? " selected" : "") + ">" + esc(v) + "</option>";
    }).join("");
  }

  function buildToolbar(view) {
    var s = viewState[view];
    var statusValues = view === "pending" ? PENDING_STATUSES : STATUSES;
    var toolbar = document.getElementById("toolbar-" + view);
    toolbar.innerHTML =
      '<div class="field"><label>카테고리</label>' +
        '<select data-role="category"><option value="전체"' +
        (s.category === "전체" ? " selected" : "") + ">전체</option>" +
        optionList(CATEGORIES, s.category) + "</select></div>" +
      '<div class="field"><label>상태</label>' +
        '<select data-role="status"><option value="전체"' +
        (s.status === "전체" ? " selected" : "") + ">전체</option>" +
        optionList(statusValues, s.status) + "</select></div>" +
      '<div class="field"><label>정렬</label>' +
        '<select data-role="sort">' +
        '<option value="newest"' + (s.sort === "newest" ? " selected" : "") + ">최신순</option>" +
        '<option value="oldest"' + (s.sort === "oldest" ? " selected" : "") + ">오래된순</option>" +
        "</select></div>";

    toolbar.addEventListener("change", function (e) {
      var role = e.target.getAttribute("data-role");
      if (!role) return;
      viewState[view][role] = e.target.value;
      renderList(view);
    });
  }

  // ---------- 리스트 ----------
  function renderList(view) {
    var container = document.getElementById("list-" + view);
    var rows = visibleData(view);
    container.innerHTML = "";

    if (!rows.length) {
      container.appendChild(el('<div class="list-empty">조건에 맞는 문의가 없습니다.</div>'));
      return;
    }

    rows.forEach(function (item) {
      var node = el(
        '<div class="item" tabindex="0">' +
          '<div class="item-top">' +
            '<span class="badge cat-' + esc(item.categories) + '">' + esc(item.categories) + "</span>" +
            '<span class="item-date">' + esc(item.created_at) + "</span>" +
          "</div>" +
          '<div class="item-q">' + esc(item.question) + "</div>" +
          '<div class="item-badges">' +
            '<span class="badge st-' + esc(item.status) + '">' + esc(item.status) + "</span>" +
            '<span class="badge reviewer-' + esc(item.reviewer_type) + '">' +
              esc(reviewerLabel(item.reviewer_type)) + "</span>" +
          "</div>" +
        "</div>"
      );
      if (viewState[view].selectedId === item.inquiry_id) node.classList.add("selected");
      node.addEventListener("click", function () {
        viewState[view].selectedId = item.inquiry_id;
        renderList(view);
        renderDetail(view);
      });
      container.appendChild(node);
    });
  }

  // ---------- 상세 ----------
  function renderDetail(view) {
    var container = document.getElementById("detail-" + view);
    var id = viewState[view].selectedId;
    var item = id ? findById(id) : null;

    if (!item) {
      container.innerHTML = '<div class="detail-empty">왼쪽 목록에서 문의를 선택하세요.</div>';
      return;
    }

    var docsHtml = item.retrieved_docs && item.retrieved_docs.length
      ? '<ul class="docs">' + item.retrieved_docs.map(function (d) {
          return "<li>" + esc(d) + "</li>";
        }).join("") + "</ul>"
      : '<div class="docs-empty">검색된 참고 문서가 없습니다.</div>';

    var html =
      "<h3>문의 상세</h3>" +
      '<dl class="meta-grid">' +
        "<dt>등록일시</dt><dd>" + esc(item.created_at) + "</dd>" +
        "<dt>카테고리</dt><dd><span class='badge cat-" + esc(item.categories) + "'>" + esc(item.categories) + "</span></dd>" +
        "<dt>상태</dt><dd><span class='badge st-" + esc(item.status) + "'>" + esc(item.status) + "</span></dd>" +
        "<dt>답변자</dt><dd>" + esc(reviewerLabel(item.reviewer_type)) + "</dd>" +
      "</dl>" +
      '<div class="section-label">문의 내용</div>' +
      '<div class="question-box">' + esc(item.question) + "</div>" +
      '<div class="section-label">참고 문서 (RAG)</div>' +
      docsHtml +
      '<div class="section-label">답변</div>' +
      '<div id="answer-slot"></div>';

    container.innerHTML = html;
    renderAnswer(container.querySelector("#answer-slot"), view, item);
  }

  function renderAnswer(slot, view, item) {
    // (A) 최종 답변 있음 → 읽기 전용
    if (item.final_answer) {
      slot.innerHTML =
        '<p class="answer-note">✓ 최종 답변이 등록되었습니다.</p>' +
        '<div class="answer-final">' + esc(item.final_answer) + "</div>";
      return;
    }

    // (B) ai_answer만 있음  /  (C) 둘 다 없음
    // AI 답변이 없는 경우에만 안내 문구를 표시한다.
    var noteHtml = item.ai_answer
      ? ""
      : '<p class="answer-note">AI 답변 없음 — 상담원이 직접 작성해야 합니다.</p>';

    slot.innerHTML =
      noteHtml +
      '<textarea id="answer-input" placeholder="답변을 입력하세요">' +
        esc(item.ai_answer || "") + "</textarea>" +
      '<div class="answer-actions">' +
        '<button type="button" class="btn" id="save-answer">최종 답변으로 저장</button>' +
      "</div>";

    slot.querySelector("#save-answer").addEventListener("click", function () {
      var value = slot.querySelector("#answer-input").value.trim();
      if (!value) {
        slot.querySelector("#answer-input").focus();
        return;
      }
      // 데모: 메모리상 final_answer에 반영 (실제 저장 없음)
      item.final_answer = value;
      renderDetail(view);   // 읽기 전용으로 전환
      renderList(view);
    });
  }

  // ---------- 통계 ----------
  function countBy(keyFn, keys) {
    var map = {};
    keys.forEach(function (k) { map[k] = 0; });
    inquiries.forEach(function (i) {
      var k = keyFn(i);
      if (map[k] === undefined) map[k] = 0;
      map[k]++;
    });
    return map;
  }

  function barsHtml(title, entries, total, colors) {
    var rows = entries.map(function (e, idx) {
      var color = colors ? colors[idx % colors.length] : "var(--accent)";
      var width = total ? (e.value / total) * 100 : 0;
      return (
        '<div class="bar-row">' +
          '<span class="bar-name">' + esc(e.name) + "</span>" +
          '<span class="bar-track"><span class="bar-fill" style="width:' +
            width.toFixed(1) + "%;background:" + color + '"></span></span>' +
          '<span class="bar-val">' + e.value +
            '<small> · ' + pct(e.value, total) + "%</small></span>" +
        "</div>"
      );
    }).join("");
    return '<div class="card chart"><h4>' + esc(title) + '</h4><div class="bars">' + rows + "</div></div>";
  }

  function heatmapHtml(title, rowKeys, colKeys) {
    var counts = {}, max = 0;
    rowKeys.forEach(function (r) {
      counts[r] = {};
      colKeys.forEach(function (c) { counts[r][c] = 0; });
    });
    inquiries.forEach(function (i) {
      if (counts[i.categories] && counts[i.categories][i.status] !== undefined) {
        var v = ++counts[i.categories][i.status];
        if (v > max) max = v;
      }
    });

    var head = "<tr><th></th>" + colKeys.map(function (c) {
      return "<th>" + esc(c) + "</th>";
    }).join("") + "</tr>";

    var body = rowKeys.map(function (r) {
      var cells = colKeys.map(function (c) {
        var v = counts[r][c];
        var ratio = max ? v / max : 0;
        var alpha = v ? (0.10 + ratio * 0.55).toFixed(2) : 0;
        var bg = v ? "rgba(42,120,214," + alpha + ")" : "var(--surface-1)";
        return '<td class="cell" style="background:' + bg + '">' + (v || "") + "</td>";
      }).join("");
      return "<tr><td class=\"rowhead\">" + esc(r) + "</td>" + cells + "</tr>";
    }).join("");

    return (
      '<div class="card chart"><h4>' + esc(title) + "</h4>" +
      '<div class="heatmap"><table><thead>' + head +
      "</thead><tbody>" + body + "</tbody></table></div></div>"
    );
  }

  function renderStats() {
    var total = inquiries.length;
    var aiCount = inquiries.filter(function (i) { return i.reviewer_type === "AI"; }).length;
    var pendingCount = baseData("pending").length;

    var kpiRow = document.getElementById("kpi-row");
    kpiRow.innerHTML =
      '<div class="card kpi"><div class="kpi-label">전체 문의</div>' +
        '<div class="kpi-value">' + total + ' <small>건</small></div>' +
        '<div class="kpi-sub">누적 접수 기준</div></div>' +
      '<div class="card kpi"><div class="kpi-label">AI 자동응답률</div>' +
        '<div class="kpi-value">' + pct(aiCount, total) + '<small>%</small></div>' +
        '<div class="kpi-sub">' + aiCount + ' / ' + total + '건</div></div>' +
      '<div class="card kpi"><div class="kpi-label">처리대기</div>' +
        '<div class="kpi-value">' + pendingCount + ' <small>건</small></div>' +
        '<div class="kpi-sub">전체의 ' + pct(pendingCount, total) + '%</div></div>';

    var catMap = countBy(function (i) { return i.categories; }, CATEGORIES);
    var stMap = countBy(function (i) { return i.status; }, STATUSES);
    var revMap = countBy(function (i) { return i.reviewer_type; }, ["AI", "human"]);

    var catEntries = CATEGORIES.map(function (c) { return { name: c, value: catMap[c] || 0 }; });
    var stEntries = STATUSES.map(function (s) { return { name: s, value: stMap[s] || 0 }; });
    var revEntries = [
      { name: "AI", value: revMap["AI"] || 0 },
      { name: "상담원", value: revMap["human"] || 0 },
    ];

    var catColors = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)"];
    var revColors = ["var(--series-1)", "var(--series-2)"];

    var grid = document.getElementById("charts-grid");
    grid.innerHTML =
      barsHtml("카테고리별", catEntries, total, catColors) +
      barsHtml("상태별", stEntries, total, null) +
      barsHtml("답변자별", revEntries, total, revColors) +
      heatmapHtml("카테고리 × 상태", CATEGORIES, STATUSES);
  }

  // ---------- 탭 ----------
  function switchTab(tab) {
    document.querySelectorAll(".tab").forEach(function (t) {
      t.classList.toggle("active", t.getAttribute("data-tab") === tab);
    });
    document.querySelectorAll(".panel").forEach(function (p) {
      p.classList.toggle("active", p.id === "panel-" + tab);
    });
    if (tab === "stats") renderStats();
  }

  document.getElementById("tabs").addEventListener("click", function (e) {
    var btn = e.target.closest(".tab");
    if (btn) switchTab(btn.getAttribute("data-tab"));
  });

  // ---------- 초기 렌더 ----------
  document.getElementById("pending-count").textContent = baseData("pending").length;
  buildToolbar("all");
  buildToolbar("pending");
  renderList("all");
  renderDetail("all");
  renderList("pending");
  renderDetail("pending");
})();
