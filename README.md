# AI CS Helper

대한항공 고객 문의(임시 데이터)를 받아 **개인정보 마스킹 → 규정 RAG 검색 → AI 분류/답변 생성 → AI 자체 검수 → 상담원 승인**의 흐름으로 처리하는 AI 고객상담 지원 시스템입니다. AI가 초안을 만들고, 최종 승인/수정은 상담원이 관리자 페이지에서 수행합니다.

## 핵심 컨셉

- **AI 우선(AI-first) 라우팅**: 규정 근거가 조금이라도 있으면 AI가 답변을 시도하고, 정말 근거가 없을 때만 상담원에게 이관합니다.
- **셀프 리뷰 루프**: AI가 생성한 답변을 별도의 AI 검수 단계가 pass/fail로 평가하고, fail이면 반려 사유를 반영해 최대 3회까지 재작성합니다.
- **우아한 실패 처리(graceful degradation)**: 임베딩/LLM/검색이 실패해도 파이프라인 전체를 중단시키지 않고 "상담원 확인 필요" 상태로 안전하게 이관합니다.
- **개인정보 보호**: 외부 AI 서비스(임베딩/LLM)에는 원문이 아니라 마스킹된 텍스트만 전달합니다.
- **완전한 감사 추적**: 마스킹, RAG 검색, 라우팅, 검수, DB 저장 등 모든 단계가 `inquiry_logs` 테이블에 순서대로 기록되어 관리자 페이지에서 처리 과정을 그대로 재생해볼 수 있습니다.

## 아키텍처

```
                         POST /inquiries
                               │
                     main.py: start_inquiry (INSERT)
                               │
                    ┌──────────▼───────────┐
                    │  LangGraph Pipeline  │
                    └──────────┬───────────┘
                               │
                 ① mask_personal_info  (개인정보 마스킹)
                               │
                        ② rag_search    (규정 문서 임베딩 검색, 코사인 유사도)
                               │
                           ③ router     (AI_generate / to_human 판단 + 답변 생성)
                        │           │
             AI_generate│            │to_human
                        ▼             │
                   ④ review            │
                (pass/fail 검수)       │
                  │       │            │
              pass│       │fail        │
                  │  (재시도<3)→router |
                  │       │(재시도=3)  |
                  ▼       ▼            ▼
                 ⑤ final_save (inquiries UPDATE)
                               │
                              END
```

각 단계는 `inquiry_logs` 테이블에 구조화된 로그(모델명, 프롬프트, 토큰 사용량, 소요시간 등)를 남깁니다.

## 디렉터리 구조

```
app/
├── main.py                   # FastAPI 엔트리포인트, REST API
├── logging_config.py         # 전역 로깅 설정
├── clients/
│   ├── http.py               # 공통 HTTP 클라이언트 (재시도/백오프)
│   ├── llm.py                # LiteLLM 프록시 chat completion 호출
│   ├── embedding.py          # Upstage 임베딩 호출
│   ├── supabase.py           # Supabase REST (documents/inquiries)
│   ├── inquiry_logs.py       # 문의 처리 로그 저장/조회
│   └── usage.py              # 토큰 사용량 파싱 유틸
├── graph/
│   ├── state.py               # LangGraph 상태(InquiryState) 정의
│   ├── nodes.py               # 각 단계 노드 함수 (masking/rag/router/review/save)
│   ├── edges.py               # 조건부 라우팅 함수
│   ├── graph.py               # StateGraph 조립 및 컴파일
│   └── prompts.py             # Router/Rewrite/Review 프롬프트 빌더
├── privacy/
│   └── masking.py             # 정규식 기반 개인정보 마스킹 (이메일/주민번호/전화번호 등)
└── rag/
    ├── regulations.py         # 규정 원문 데이터 (id → 텍스트)
    ├── ingest.py              # 규정 임베딩 후 Supabase 적재 스크립트
    └── search.py              # 질의 임베딩 + 코사인 유사도 검색

frontend/ (정적 파일)
├── admin.html                # 상담원 관리자 페이지 (전체 내역/처리대기/통계)
├── inquiry.html              # 고객용 문의 등록 데모 페이지
├── css/
│   └── styles.css            # 공용 스타일시트 (라이트/다크 테마)
└── js/
    ├── log.js                # 콘솔 로깅 헬퍼 (DEBUG 플래그)
    ├── api.js                # 백엔드 REST API 호출 래퍼
    ├── inquiry.js            # 문의 등록 페이지 동작
    └── admin.js              # 관리자 페이지 동작 (목록/상세/통계/타임라인)

scripts/  (개발자용 CLI 도구, app 패키지 재사용)
├── embedding_demo.py         # 콘솔에서 문서 저장(add)/검색(search) 임베딩 동작 확인
├── llm_demo.py               # 콘솔에서 LiteLLM 프록시 응답 확인
└── evaluate_ragas.py         # 완료된 문의의 AI 답변 품질을 RAGAS로 평가

.github/workflows/
├── ci.yml   # 코드 품질 검사 → 단위 테스트 → PR 코멘트
└── cd.yml    # CI 성공 후 GCP VM에 SSH로 배포
```

## 처리 파이프라인 상세

1. **`start_inquiry`** (`main.py` → `nodes.py`): 그래프 실행 전 `inquiries` 테이블에 먼저 INSERT해서 `inquiry_id`를 확보합니다. 이후 파이프라인이 중간에 실패해도 이 id로 "상담원 확인 필요" 처리(부분 성공)를 할 수 있습니다.
2. **`mask_personal_info`**: 이메일, 주민등록번호, 카드번호, 전화번호, 이름/주소/계좌번호/여권번호 등을 정규식으로 마스킹합니다.
3. **`rag_search`**: 마스킹된 질의를 임베딩하고, `documents` 테이블 전체와 코사인 유사도를 계산해 상위 5건을 가져옵니다. 실패 시 `rag_failed=True`로 표시하고 다음 단계로 넘깁니다.
4. **`router`**: 검색된 규정과 질의로 LLM에 분류/답변 생성을 요청합니다. `rag_failed`면 LLM 호출 없이 즉시 상담원 이관. 재시도 시에는 반려 사유를 반영한 재작성 프롬프트를 사용합니다.
5. **`review`**: 생성된 답변이 규정과 부합하는지 별도 LLM이 pass/fail로 검수합니다. fail이면 반려 사유와 함께 `router`로 되돌아가 재생성(최대 3회, `MAX_RETRY`).
6. **`final_save`**: 최종 상태를 `inquiries` 테이블에 UPDATE하고 파이프라인 완료 로그를 남깁니다.

이후 상담원이 관리자 페이지(`admin.html`)에서 AI 답변을 검토, 승인 또는 직접 수정하여 `PATCH /inquiries/{id}`로 최종 답변을 등록합니다.

## 기술 스택

패키지 관리는 [uv](https://docs.astral.sh/uv/)를 사용합니다 (`uv.lock` 존재, `requires-python >= 3.11`).

| 구분 | 라이브러리 |
|---|---|
| 웹 프레임워크 | FastAPI, Uvicorn |
| 파이프라인 오케스트레이션 | LangGraph, langchain-core, langchain-openai |
| 데이터 처리 | pandas |
| RAG 평가 | ragas |
| 환경설정 | python-dotenv |
| 개발/테스트 | pytest, ruff, httpx |

## API 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| GET | `/health` | 헬스 체크 |
| POST | `/inquiries` | 신규 문의 등록 및 파이프라인 실행 |
| GET | `/inquiries` | 전체 문의 목록 (최신순) |
| GET | `/inquiries/{id}` | 문의 상세 조회 |
| GET | `/inquiries/{id}/logs` | 문의 처리 로그 조회 (실행 순서대로) |
| POST | `/inquiries/{id}/logs/actions` | 수정 시작/취소 등 UI 행동 로깅 |
| PATCH | `/inquiries/{id}` | 상담원 최종 답변 저장 (승인/수정/직접작성 자동 판별) |
| DELETE | `/inquiries/{id}` | 문의 삭제 |

## 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `LOG_LEVEL` | `INFO` | 로그 레벨 |
| `SUPABASE_INQUIRIES_TABLE` | `inquiries` | 문의 테이블명 |
| `SUPABASE_INQUIRY_LOGS_TABLE` | `inquiry_logs` | 처리 로그 테이블명 |
| `HTTP_TIMEOUT` | `15` | 일반 HTTP 요청 타임아웃(초) |
| `HTTP_LLM_TIMEOUT` | `120` | LLM 요청 타임아웃(초) |
| `HTTP_MAX_RETRIES` | `3` | 일시적 오류(429/5xx/연결끊김) 재시도 횟수 |
| `HTTP_RETRY_BACKOFF` | `0.5` | 재시도 백오프 기준(초) |

## 배포 (Docker)

`docker-compose.yml`로 3개 서비스가 함께 뜹니다.

| 서비스 | 이미지/빌드 | 포트 | 역할 |
|---|---|---|---|
| `backend` | 로컬 `Dockerfile` 빌드 | `${BACKEND_PORT:-8000}` → 8000 | FastAPI 앱 |
| `litellm` | `docker.litellm.ai/berriai/litellm:latest` | 4000 | LLM/임베딩 프록시 (모델 라우팅, 폴백, rpm 제한) |
| `frontend` | `nginx:alpine` | 8080 → 80 | `frontend/` 정적 파일(admin.html, inquiry.html 등) 서빙 |

`backend`는 `litellm` 서비스에 의존하며(`depends_on`), 컨테이너 내부에서는 `LITELLM_BASE_URL=http://litellm:4000/v1`로 접근합니다(로컬 개발 시 `.env`의 `http://localhost:4000/v1`을 오버라이드).

### Dockerfile (멀티스테이지)

- **Builder**: `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` 이미지에서 `uv sync --frozen --no-dev`로 프로덕션 의존성만 `.venv`에 설치.
- **Runner**: 순정 `python:3.12-slim-bookworm`에 빌더의 `.venv`만 복사 + `app/`, `scripts/` 소스 복사 후 `uvicorn app.main:app` 실행.
- 컨테이너 실제 런타임은 **Python 3.12** (pyproject.toml의 `requires-python`은 `>=3.11`로 개발 환경 최소 버전만 명시).
- `scripts/`(개발자용 CLI 도구: `evaluate_ragas.py` 등)도 이미지에 함께 복사되지만, `uv sync --frozen --no-dev`는 `ragas`/`langchain-openai` 등 런타임 의존성만 설치하므로 컨테이너 안에서 바로 실행 가능합니다.

### LiteLLM 모델 라우팅 (`litellm_config.yaml`)

| 모델 별칭 | 실제 제공자/모델 | 비고 |
|---|---|---|
| `cs-chat` | Upstage `solar-pro3` | 메인 채팅 모델. `LITELLM_CHAT_MODEL=cs-chat`로 설정해 사용 |
| `cs-chat-fallback` | Gemini `gemini-3-flash-preview` | `cs-chat` 실패 시 LiteLLM이 자동 폴백 |
| `cs-embedding-query` | Upstage `embedding-query` | 질의 임베딩용 모델 별칭 |
| `cs-embedding-passage` | Upstage `embedding-passage` | 문서 임베딩용 모델 별칭 |


### 실행 (Docker Compose)

```bash
docker compose up -d --build
# backend  : http://localhost:8000
# litellm  : http://localhost:4000
# frontend : http://localhost:8080
```

`.env` 파일에 아래 "환경 변수" 표의 값들과 함께 `GEMINI_API_KEY`(폴백 모델용)를 채워야 합니다.

## CI/CD (GitHub Actions)

### CI — `AI CS Helper CI` (`.github/workflows/ci.yml`)

`app/**`, `tests/**`, `main.py`, `pyproject.toml`, `uv.lock` 등이 변경된 채 `main`에 push되거나 그쪽으로 PR이 열릴 때 실행됩니다(문서(`.md`)만 바뀌면 스킵). 동일 브랜치에 연달아 push하면 이전 실행은 취소됩니다(`concurrency`).

1. **lint**: `uv run ruff check . --output-format=github` + `uv run ruff format . --check`
2. **test** (`lint` 성공 후): `uv run pytest -v --tb=short`. `SUPABASE_URL`, `SUPABASE_KEY`, `UPSTAGE_*`, `LITELLM_*` 등을 GitHub Secrets에서 주입.
3. **comment** (PR일 때만, 항상 실행): lint/test 결과를 표 형태로 PR에 코멘트. 실패 시 이 Job도 실패 처리.

### CD (`.github/workflows/cd.yml`)

`AI CS Helper CI` 워크플로가 **완료(성공)**되고 그 대상이 **`main` 브랜치**였을 때만 배포가 실행됩니다(`workflow_run` 트리거 + 조건 필터). `appleboy/ssh-action`으로 GCP VM에 접속해:

```bash
git fetch origin main && git reset --hard origin/main
docker compose build
docker compose up -d
docker image prune -f
```

를 실행합니다. 필요한 Secrets: `GCP_VM_HOST`, `GCP_VM_USER`, `GCP_VM_SSH_KEY`, `GCP_VM_PROJECT_PATH`.

## 실행 방법

```bash
# 의존성 설치 (uv.lock 기준)
uv sync

# 1) 규정 문서 임베딩 및 적재 (최초 1회 또는 규정 변경 시)
uv run python -m app.rag.ingest

# 2) API 서버 실행
uv run uvicorn app.main:app --reload

# 3) 프론트엔드
#    inquiry.html 로 고객 문의 등록, admin.html 로 상담원 검토/승인
```

개발/테스트 도구(`pytest`, `ruff`, `httpx`)는 `uv sync --dev`로 함께 설치됩니다.

## 개발자 도구 (`scripts/`)

앱의 클라이언트 코드(`app.clients.*`)를 그대로 재사용하는 콘솔 스크립트들입니다. 프로젝트 루트에서 실행합니다.

```bash
# 임베딩 저장/검색 콘솔 데모
uv run python scripts/embedding_demo.py add
uv run python scripts/embedding_demo.py search

# LiteLLM 프록시 응답 확인
uv run python scripts/llm_demo.py

# 완료된 문의(final_answer 존재)의 AI 답변 품질을 RAGAS로 평가
uv run python scripts/evaluate_ragas.py --sample-per-category 3   # 카테고리별로 3개 평가
uv run python scripts/evaluate_ragas.py --limit 10                # 최신 10개 평가
uv run python scripts/evaluate_ragas.py --category 긴급 --output urgent_result.csv
```

`evaluate_ragas.py`는 `ai_answer`(AI 초안)를 response로, 사람이 승인/수정한 `final_answer`를 reference로, `retrieved_docs`를 context로 삼아 **"AI 초안이 사람이 최종 승인한 답변에 얼마나 가까운가"**를 측정합니다. 평가 지표는 `faithfulness`(환각 여부), `context_precision`, `context_recall`, `answer_correctness` 4가지이며(`answer_relevancy`는 알려진 LLM 호환 버그로 비활성화), 결과는 CSV로 저장되고 전체/카테고리별 평균이 콘솔에 출력됩니다. LiteLLM은 평가용 LLM으로, Upstage 임베딩은 평가용 임베딩으로 재사용합니다.

> 참고: `embedding_demo.py`는 `app.clients.embedding.embed`와 `app.rag.search.search`를, `llm_demo.py`는 `app.clients.llm.ask`를 가져다 씁니다. 이 README의 다른 곳에서 확인한 `app/clients/llm.py`·`app/rag/search.py`에는 `_with_usage` 접미사가 붙은 함수(`ask_with_usage`, `search_with_usage`)만 보였는데, 두 스크립트가 기대하는 단순 래퍼(`ask`, `search`)가 해당 파일에 실제로 존재하는지는 확인이 필요합니다.

## 프론트엔드

정적 파일(HTML/CSS/바닐라 JS)로만 구성되어 있으며, Docker Compose에서는 `nginx:alpine`이 `frontend/`를 그대로 서빙합니다.

- **`inquiry.html` + `js/inquiry.js`**: 문의 내용을 입력받아 `postInquiry()`로 `POST /inquiries`를 호출합니다. 성공/실패 여부를 하단 토스트로 안내하고, 요청 중에는 등록 버튼을 비활성화합니다.
- **`admin.html` + `js/admin.js`**: 부팅 시 `getInquiries()`로 전체 문의를 불러와 화면 상태(`viewState`)를 구성합니다.
  - **전체 처리내역 / 처리대기** 탭: 카테고리·상태 필터, 최신/오래된순 정렬을 지원하며, 처리대기 탭에서는 "긴급" 카테고리가 항상 최상단에 옵니다.
  - 문의를 선택하면 상세 패널에 메타정보, 참고 규정 문서, 답변 영역, 그리고 `getInquiryLogs()`로 불러온 **AI 처리 타임라인**(마스킹→RAG→라우팅→검수→저장 각 단계)이 렌더링됩니다. 타임라인 항목은 이벤트명에 따라 성공/경고/오류/DB/사람 처리로 색이 구분됩니다.
  - AI 답변이 있으면 "승인" 또는 "수정" 후 `patchAnswer()`로 저장하고, 없으면 상담원이 직접 작성해 등록합니다. 수정 시작/취소는 `postLogAction()`으로 별도 로깅됩니다(`recordUiAction`).
  - **통계** 탭: 전체 문의 수 / AI 자동응답률 / 처리대기 건수 KPI 카드와, 카테고리별·상태별·답변자별 가로 막대 차트, 카테고리 × 상태 히트맵을 클라이언트에서 직접 집계해 그립니다.
  - 백엔드 연결에 실패하면(`getInquiries()` reject) 오프라인 배너를 띄우고, 저장·삭제 동작은 DB에 반영되지 않는 로컬 미리보기 모드로 동작합니다.
- **`js/api.js`**: 모든 API 호출의 단일 창구. `API_BASE`가 배포된 백엔드 주소(현재 `http://34.50.51.111:8000`)로 하드코딩되어 있어, 배포 위치가 바뀌면 이 값만 수정하면 됩니다. 로컬 개발 시에는 `http://localhost:8000` 등으로 바꿔서 사용해야 합니다.
- **`js/log.js`**: `DEBUG` 플래그로 켜고 끌 수 있는 콘솔 로깅 헬퍼(`log`/`logError`). 데모/디버깅용입니다.
- **`css/styles.css`**: 두 페이지가 공유하는 순수 CSS 스타일시트.
  - `prefers-color-scheme`로 라이트/다크 테마를 모두 지원하며, 모든 색상은 CSS 커스텀 프로퍼티(`--surface-1`, `--page`, `--text-primary` 등)로 관리됩니다.
  - 카테고리/시리즈 색상(`--series-1~4`)과 히트맵용 시퀀셜 블루 램프(`--seq-100~700`)를 별도로 정의해 통계 탭의 차트에 사용합니다.
  - 상단바, 탭, 리스트+상세 2단 레이아웃(`.split`), 배지(`.badge`), AI 처리 타임라인(`.timeline`), KPI 카드, 가로 막대 차트, 히트맵 등 관리자 페이지의 주요 UI 컴포넌트 스타일을 포함합니다.

## 데이터 모델 (Supabase)

- **`documents`**: 규정 원문 임베딩 저장 (`content`, `metadata`, `embedding`)
- **`inquiries`**: 문의별 상태 (`question`, `retrieved_docs`, `categories`, `ai_answer`, `final_answer`, `status`, `reviewer_type` 등)
- **`inquiry_logs`**: 문의별 처리 단계 로그 (`stage`, `event`, `title`, `message`, `data`, `sequence` 순서)

## 참고 사항

- `regulations.py`의 `REGULATIONS` 딕셔너리에 규정을 추가한 뒤 `ingest.py`를 다시 실행하면 전체 문서를 삭제하고 새로 임베딩·적재합니다.
- 임베딩 적재 시 RPM/TPM 제한(`EmbeddingRateLimiter`)과 Supabase statement timeout 시 배치 자동 분할 저장 로직이 포함되어 있습니다.
- Lint/format은 `ruff`(line-length 100, `E`/`F`/`I` 규칙, `E501` 무시), 테스트는 `pytest`(`test_*.py` / `*_test.py` 패턴)로 실행합니다: `uv run ruff check .`, `uv run pytest`.
- `js/api.js`의 `API_BASE`는 특정 GCP VM IP로 하드코딩되어 있으므로, 백엔드 배포 주소가 바뀌면 이 파일을 함께 갱신해야 합니다.
