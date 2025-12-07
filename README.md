# 🛍️ 커머스 마케팅 AI 에이전트

로컬 실행 가능한 멀티 태스크 커머스 마케팅 AI 에이전트 시스템입니다.

## 📋 개요

이 프로젝트는 **6가지 커머스 마케팅 태스크**를 수행하는 AI 에이전트 시스템입니다:

[📄 프로젝트 발표 자료 (PDF) 보기](assets/presentation.pdf)

[📄 경쟁사 분석 보고서 샘플 (HTML) 보기](assets/sample_report.html)

1. **소비 트렌드 분석** - 제품/키워드의 트렌드 분석
2. **광고 문구 생성** - AI 기반 광고 카피 생성
3. **사용자 세그먼트 분류** - 고객 데이터 클러스터링 및 분류
4. **리뷰 감성 분석** - 제품 리뷰 감성 분석 및 요약
5. **경쟁사 분석** - 경쟁 제품 비교 및 SWOT 분석

6. **🆕 마케팅 전략 종합 보고서** - 모든 분석 결과를 통합하여 종합 마케팅 전략 제시

## 🏗️ 아키텍처

```
사용자 메시지 → 라우터 (키워드 감지) → 적절한 에이전트 실행 → 결과 반환
                                    ↓
                            RAG 검색 (FTS5)
                                    ↓
                            LLM 분석 + 도구 실행
                                    ↓
                            DB 저장 + PDF/HTML 생성
```

### 주요 구성 요소

#### Frontend Stack
- **React 18.2.0+**: 컴포넌트 기반 UI 프레임워크
- **TypeScript 5.2.2+**: 타입 안전성 제공
- **Vite 5.0.8+**: 초고속 개발 서버 및 빌드 도구 (ESBuild 기반)
- **개발 서버**: `http://localhost:5173`
- **빌드**: TypeScript 컴파일 → Vite 번들링 → 최적화된 정적 파일 생성
- **특징**: 라이브러리 의존성 최소화 (순수 React 컴포넌트 구현)

#### Backend Stack
- **FastAPI 0.109.0**: 고성능 비동기 웹 프레임워크
- **Uvicorn**: ASGI 서버 (프로덕션 환경: uvicorn[standard])
- **SQLAlchemy 2.0.25**: ORM (Object-Relational Mapping)
- **Pydantic 2.5.3**: 데이터 검증 및 직렬화
- **OpenAI API (1.40.0+)**: GPT-4 기반 자연어 처리

#### LLM 활용
- **모델**: GPT-4 (gpt-4 또는 gpt-4-turbo)
- **Temperature**: 0.7 (창의성과 일관성 균형)
- **Max Tokens**: 태스크별 2000~8000
- **용도**:
  - 트렌드 인사이트 생성
  - 광고 문구 작성
  - 세그먼트 분석
  - 종합 마케팅 전략 수립

#### Database (SQLite)
- **파일 경로**: `backend/data/marketing.db`
- **주요 테이블**:
  - `Session`: 세션 관리 (UUID 기반)
  - `Message`: 대화 히스토리 저장 (멀티턴 지원)
  - `RagDoc`: RAG 문서 저장 (FTS5 인덱스)
  - `TaskResult`: 태스크 실행 결과 및 메타데이터

#### RAG (Retrieval-Augmented Generation)
- **벡터 스토어**: SQLite FTS5 (Full-Text Search 5)
- **임베딩**: 사용 안 함 (BM25 기반 키워드 검색)
- **인덱스**: `CREATE VIRTUAL TABLE rag_fts USING fts5(doc_id, title, content)`
- **검색 방식**:
  1. FTS5 MATCH 쿼리 (BM25 랭킹)
  2. LIKE 기반 fallback (FTS5 실패 시)
- **Top-k**: 상위 5개 문서 반환
- **필터링**: 카테고리별 (trend, ad, segment, review, competitor)

#### 외부 API
- **Naver DataLab API**: 검색 트렌드 데이터 수집
- **Naver Shopping API**: 제품 정보 및 리뷰 수집
- **웹 크롤링**: BeautifulSoup4 + requests (필요 시)

#### 시각화 및 보고서
- **PDF 생성**: ReportLab 4.0.9
- **차트**: Matplotlib 3.8.2 + Seaborn 0.13.1
- **HTML 보고서**: Jinja2 3.1.3 템플릿 엔진
- **한글 폰트**: MalgunGothic (Windows 기본 폰트)

## 🚀 빠른 시작

### 1. 필수 요구사항

- Python 3.10+
- Node.js 16+
- OpenAI API 키

### 2. 환경변수 설정

```bash
# .env.example을 .env로 복사
cp .env.example .env

# .env 파일을 열어서 API 키 입력
# 필수: OPENAI_API_KEY
# 선택: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET (없으면 모의 데이터 사용)
```

### 3. 설치 및 실행

**터미널 1 - 백엔드:**
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

**터미널 2 - 프론트엔드:**
```bash
cd frontend
npm install
npm run dev
```

**브라우저 접속:**
```
http://localhost:5173
```

### 백엔드 실행 명령어 설명

- `uvicorn app.main:app --reload`
  - **uvicorn**: FastAPI의 공식 ASGI 서버
  - `app.main:app`: `app/main.py` 모듈의 `app` 객체 실행
  - `--reload`: 코드 변경 시 자동 재시작 (개발 모드)

옵션 추가:
```bash
# 포트 변경
uvicorn app.main:app --reload --port 8080

# 외부 접속 허용
uvicorn app.main:app --reload --host 0.0.0.0

# 로그 레벨 조정
uvicorn app.main:app --reload --log-level debug
```

### 4. 사용 예시

채팅창에 다음과 같이 입력하세요:

✅ **활성화된 에이전트 (5개)**:
- **세그먼트 분류**: "에어팟 프로 구매자를 세그먼트로 분류해줘"
- **트렌드 분석** (PDF 다운로드): "스마트워치 최근 3개월 트렌드 알려줘"
- **광고 문구 생성** (멀티턴 지원): "친환경 세제 광고 문구 만들어줘" → "더 만들어줘"
- **경쟁사 분석** (HTML 보고서): "아이폰 15와 갤럭시 S24 비교 분석해줘"
- **리뷰 감성 분석**: "에어팟 프로 리뷰 분석해줘"

## 📁 프로젝트 구조

```
├── backend/
│   └── app/
│       ├── agents/
│       │   ├── router.py              # 키워드 기반 라우터
│       │   ├── trend_agent.py         # 트렌드 분석 에이전트
│       │   ├── ad_copy_agent.py       # 광고 문구 생성 에이전트
│       │   ├── segment_agent.py       # 세그먼트 분류 에이전트
│       │   ├── review_agent.py        # 리뷰 감성 분석 에이전트
│       │   ├── competitor_agent.py    # 경쟁사 분석 에이전트
│       │   └── synthesis_agent.py     # 종합 보고서 에이전트
│       ├── tools/
│       │   ├── common/                # 공통 도구
│       │   │   ├── web_search.py      # 웹 검색
│       │   │   ├── api_client.py      # 외부 API 클라이언트
│       │   │   └── rag_base.py        # RAG 인프라
│       │   ├── trend_tools.py         # 트렌드 분석 도구
│       │   ├── ad_tools.py            # 광고 문구 도구
│       │   ├── segment_tools.py       # 세그먼트 분류 도구
│       │   ├── review_tools.py        # 리뷰 분석 도구
│       │   ├── competitor_tools.py    # 경쟁사 분석 도구
│       │   ├── synthesis_tools.py     # 종합 보고서 도구
│       │   └── pdf_generator.py       # PDF 생성 유틸리티
│       ├── db/                        # 데이터베이스
│       │   ├── models.py              # SQLAlchemy 모델
│       │   ├── crud.py                # CRUD 연산
│       │   └── database.py            # DB 연결 설정
│       ├── routes/                    # API 라우트
│       │   └── chat.py                # 채팅 엔드포인트
│       └── schemas/                   # DTO
└── frontend/                          # React 채팅 UI
    ├── src/
    │   ├── App.tsx                    # 메인 컴포넌트
    │   ├── main.tsx                   # 진입점
    │   └── vite-env.d.ts              # TypeScript 타입 선언
    ├── package.json
    └── vite.config.ts
```

## 🎯 각 에이전트 상세 구현

### 1️⃣ 소비 트렌드 분석 (Trend Agent)

**파일**: `backend/app/agents/trend_agent.py`, `backend/app/tools/trend_tools.py`

**구현 파이프라인 (7단계)**:

#### Step 1: 키워드 추출
- **방식**: 정규표현식 + LLM Fallback
- **구현**: [trend_tools.py:56-101](backend/app/tools/trend_tools.py#L56-L101)
- **로직**:
  1. 53개 불용어 필터링 (`"를", "을", "트렌드", "분석"` 등)
  2. 다중 패턴 매칭: `"A 트렌드"`, `"A의 인기도"`, `"A 검색량"` 등
  3. 실패 시 LLM에게 키워드 추출 요청

#### Step 2: 시간 범위 파싱
- **구현**: [trend_tools.py:103-169](backend/app/tools/trend_tools.py#L103-L169)
- **지원 표현**: "3개월", "1년", "최근 6개월", "지난 2년"
- **기본값**: 180일 (6개월)
- **반환**: `start_date`, `end_date`, `time_unit`, `days`

#### Step 3: 트렌드 데이터 수집
- **API**: Naver DataLab (`https://openapi.naver.com/v1/datalab/search`)
- **구현**: [trend_tools.py:171-234](backend/app/tools/trend_tools.py#L171-L234)
- **인증**: `X-Naver-Client-Id`, `X-Naver-Client-Secret` 헤더
- **요청 형식**:
  ```json
  {
    "startDate": "2024-01-01",
    "endDate": "2024-04-01",
    "timeUnit": "date",
    "keywordGroups": [
      {"groupName": "키워드", "keywords": ["키워드"]}
    ]
  }
  ```
- **Fallback**: API 실패 시 mock 데이터 생성 (정규분포 기반)

#### Step 4: 데이터 분석
- **구현**: [trend_tools.py:237-318](backend/app/tools/trend_tools.py#L237-L318)
- **계산 지표**:
  - **평균**: `np.mean(ratio_values)`
  - **최신값**: `ratio_values[-1]`
  - **성장률**: `(latest - avg) / avg * 100`
  - **모멘텀**: 최근 7일 vs 전체 평균 비교
  - **최고치**: `max(ratio_values)`
  - **변동성**: `np.std(ratio_values)`
- **시그널 분류**: 5단계 (`"강한 상승세"`, `"상승세"`, `"보합"`, `"하락세"`, `"강한 하락세"`)

#### Step 5: 키워드 클러스터링
- **구현**: [trend_tools.py:664-731](backend/app/tools/trend_tools.py#L664-L731)
- **방식**: LLM 기반 (OpenAI GPT-4)
- **프롬프트 요청**: "3-5개 클러스터로 묶고 각 클러스터에 대한 인사이트 제공"
- **Fallback**: 규칙 기반 클러스터링 (품사 태깅)

#### Step 6: 인사이트 생성
- **구현**: [trend_tools.py:588-661](backend/app/tools/trend_tools.py#L588-L661)
- **LLM 프롬프트**: "실행 가능한 마케팅 제안 3가지 도출"
- **Fallback**: 규칙 기반 인사이트 (시그널에 따른 템플릿)

#### Step 7: PDF 보고서 생성
- **구현**: [pdf_generator.py:269-539](backend/app/tools/pdf_generator.py#L269-L539)
- **구성 요소**:
  - 제품명 + 분석 기간
  - 주요 지표 테이블 (6개 지표)
  - 시계열 차트 (Matplotlib Line Chart)
  - 키워드 클러스터 테이블
  - 실행 가능한 인사이트
- **한글 폰트**: MalgunGothic 등록

**출력**:
- **DB 저장**: `TaskResult` 테이블 (JSON 형식)
- **파일**: `backend/reports/trend_report_{timestamp}.pdf`
- **응답**: 분석 요약 텍스트 + PDF 다운로드 링크

---

### 2️⃣ 광고 문구 생성 (Ad Copy Agent)

**파일**: `backend/app/agents/ad_copy_agent.py`, `backend/app/tools/ad_tools.py`

**구현 파이프라인 (5단계)**:

#### Step 1: 제품 정보 추출
- **구현**: [ad_copy_agent.py:65-80](backend/app/agents/ad_copy_agent.py#L65-L80)
- **방식**: 정규표현식 패턴 매칭
- **패턴**: `"[제품명] 광고"`, `"[제품명] 카피"`, `"[제품명] 문구"` 등

#### Step 2: RAG 검색 (과거 광고 문구 참조)
- **구현**: [ad_copy_agent.py:82-88](backend/app/agents/ad_copy_agent.py#L82-L88)
- **쿼리**: 제품명 + "광고" 키워드로 FTS5 검색
- **Top-k**: 3개 유사 문구 검색
- **목적**: 일관된 브랜드 톤 & 매너 유지

#### Step 3: LLM 문구 생성
- **구현**: [ad_tools.py:45-120](backend/app/tools/ad_tools.py#L45-L120)
- **프롬프트 구성**:
  - 제품 정보 (제품명, 카테고리, 특징)
  - 타겟 오디언스 (연령, 관심사)
  - 톤 & 매너 (친근함, 전문성, 유머)
  - 과거 문구 예시 (RAG 결과)
- **생성 개수**: 5개 (짧은/중간/긴 문구 혼합)
- **Temperature**: 0.8 (창의성 강조)

#### Step 4: 멀티턴 지원 (이어서 생성)
- **구현**: [ad_copy_agent.py:95-110](backend/app/agents/ad_copy_agent.py#L95-L110)
- **조건**: 대화 히스토리에서 이전 광고 문구 작업 감지
- **동작**: 이전 컨텍스트 유지하며 추가 문구 생성

#### Step 5: DB 저장 및 RAG 인덱싱
- **구현**: [ad_copy_agent.py:112-135](backend/app/agents/ad_copy_agent.py#L112-L135)
- **TaskResult 저장**: `product_name`, `ad_copies` (JSON)
- **RagDoc 인덱싱**: 생성된 문구를 FTS5에 저장하여 향후 참조 가능

**출력**:
- **형식**: 마크다운 테이블 (번호, 문구, 길이, 톤)
- **DB**: `TaskResult` + `RagDoc` 이중 저장

---

### 3️⃣ 사용자 세그먼트 분류 (Segment Agent)

**파일**: `backend/app/agents/segment_agent.py`, `backend/app/tools/segment_tools.py`

**구현 파이프라인 (4단계)**:

#### Step 1: 제품명 추출
- **구현**: [segment_agent.py:60-75](backend/app/agents/segment_agent.py#L60-L75)
- **패턴**: `"[제품명] 구매자"`, `"[제품명] 고객"`, `"[제품명] 세그먼트"` 등

#### Step 2: 리뷰 데이터 수집
- **구현**: [segment_tools.py:55-120](backend/app/tools/segment_tools.py#L55-L120)
- **소스**:
  1. 웹 검색 (Google/Naver)
  2. Naver Shopping API (리뷰 크롤링)
  3. Fallback: 50개 mock 리뷰 생성
- **데이터 필드**: `review_text`, `rating`, `author`, `date`

#### Step 3: LLM 기반 세그먼트 분석
- **구현**: [segment_tools.py:125-200](backend/app/tools/segment_tools.py#L125-L200)
- **프롬프트**:
  ```
  다음 리뷰 데이터를 분석하여 3-5개 고객 세그먼트로 분류하세요.
  각 세그먼트에 대해:
  1. 세그먼트 이름
  2. 인구통계학적 특성 (연령, 성별, 직업)
  3. 구매 동기 및 니즈
  4. 추천 마케팅 전략
  ```
- **출력 구조**: JSON 형태의 세그먼트 배열

#### Step 4: PDF 보고서 생성
- **구현**: [pdf_generator.py:89-266](backend/app/tools/pdf_generator.py#L89-L266)
- **구성**:
  - 제품명 + 세그먼트 개수
  - 각 세그먼트별 테이블:
    - 특성
    - 니즈
    - 마케팅 전략
  - 시각화: 세그먼트별 비율 파이 차트

**출력**:
- **파일**: `backend/reports/segment_report_{timestamp}.pdf`
- **DB**: `TaskResult` 테이블에 JSON 저장

---

### 4️⃣ 리뷰 감성 분석 (Review Agent)

**파일**: `backend/app/agents/review_agent.py`, `backend/app/tools/review_tools.py`

**구현 상태**: ⚠️ **개발 중** (Mock 응답)

**계획된 구현**:

#### Step 1: 리뷰 수집
- **소스**: Naver Shopping API, 크롤링
- **수량**: 100개 이상 권장

#### Step 2: 감성 분석
- **방식 1**: LLM 기반 (GPT-4) - 긍정/부정/중립 분류
- **방식 2**: 한국어 감성 사전 (KNU Sentiment Lexicon)
- **방식 3**: Fine-tuned BERT 모델 (KoBERT)

#### Step 3: 주제 추출
- **방식**: LDA (Latent Dirichlet Allocation) 또는 LLM
- **목표**: 주요 언급 주제 5-7개 도출

#### Step 4: 키워드 빈도 분석
- **방식**: TF-IDF + 형태소 분석 (KoNLPy)
- **시각화**: 워드 클라우드 (Matplotlib)

---

### 5️⃣ 경쟁사 분석 (Competitor Agent)

**파일**: `backend/app/agents/competitor_agent.py`, `backend/app/tools/competitor_tools.py`

**구현 상태**: ⚠️ **개발 중** (Mock 응답)

**계획된 구현**:

#### Step 1: 제품 정보 수집
- **소스**: Naver Shopping API, 웹 크롤링
- **데이터**: 가격, 스펙, 리뷰 개수, 평점

#### Step 2: SWOT 분석
- **방식**: LLM 기반 (GPT-4)
- **입력**: 제품 A vs 제품 B 비교 데이터
- **출력**: Strengths, Weaknesses, Opportunities, Threats

#### Step 3: 가격 비교
- **시각화**: Bar Chart (Matplotlib/Chart.js)
- **지표**: 최저가, 평균가, 최고가

#### Step 4: HTML 보고서 생성
- **템플릿**: Jinja2
- **구성**:
  - SWOT 매트릭스 (Chart.js Radar Chart)
  - 가격 비교 막대 그래프
  - 스펙 비교 테이블
- **출력**: `backend/reports/competitor_report_{timestamp}.html`

---

### 6️⃣ 마케팅 전략 종합 보고서 (Synthesis Agent)

**파일**: `backend/app/agents/synthesis_agent.py`, `backend/app/tools/synthesis_tools.py`

**구현 파이프라인 (6단계)**:

#### Step 1: 세션 검증
- **구현**: [synthesis_agent.py:34-54](backend/app/agents/synthesis_agent.py#L34-L54)
- **조건**: 세션에 2개 이상의 완료된 태스크 필요
- **오류 처리**: 태스크 부족 시 안내 메시지 반환

#### Step 2: 모든 태스크 결과 집계
- **구현**: [synthesis_agent.py:59-94](backend/app/agents/synthesis_agent.py#L59-L94)
- **쿼리**: `SELECT * FROM task_result WHERE session_id = :sid`
- **데이터 구조화**: 태스크 타입별로 result_data 추출

#### Step 3: 토큰 추정
- **구현**: [synthesis_tools.py:96-98](backend/app/tools/synthesis_tools.py#L96-L98)
- **목적**: 너무 많은 데이터 시 요약 필요 판단
- **기준**: 8000 토큰 이상 시 경고

#### Step 4: LLM 종합 분석
- **구현**: [synthesis_tools.py:107-247](backend/app/tools/synthesis_tools.py#L107-L247)
- **프롬프트 구성**:
  ```
  당신은 경험이 풍부한 마케팅 전략 컨설턴트입니다.
  다음 분석 결과들을 종합하여 실행 가능한 통합 마케팅 전략 보고서를 작성하세요:

  1. Executive Summary
  2. 시장 환경 분석
  3. 고객 인사이트
  4. 마케팅 전략 제안
  5. 실행 계획
  ```
- **모델**: GPT-4
- **Max Tokens**: 8000
- **Temperature**: 0.7

#### Step 5: PDF 보고서 생성 (텍스트 전용)
- **구현**: [synthesis_tools.py:317-479](backend/app/tools/synthesis_tools.py#L317-L479)
- **구성**:
  - 제품명 + 생성 날짜
  - 분석된 태스크 요약 (트렌드, 세그먼트, 광고 등)
  - LLM 생성 전략 텍스트 (마크다운 파싱)
  - 페이지 넘버링 + 한글 폰트 처리
- **주의**: ⚠️ 차트 생성 시도했으나 실패로 제거 (텍스트만 포함)

#### Step 6: 응답 조합
- **구현**: [synthesis_agent.py:114-129](backend/app/agents/synthesis_agent.py#L114-L129)
- **출력**:
  - 분석된 태스크 목록 (체크마크 포함)
  - 보고서 구성 요약
  - PDF 다운로드 링크
  - 다음 단계 제안

**주요 기술적 도전**:
- ❌ **실패한 시도**: LLM이 차트 생성 코드를 작성하도록 했으나, 코드가 PDF에 그대로 삽입되는 버그 발생
- ✅ **현재 솔루션**: 텍스트 전용 보고서 (차트 제거)
- 💡 **향후 개선 방향**: 수동으로 정의된 3-4개 차트 타입을 LLM이 선택하도록 구현

## 🗄️ 데이터베이스 스키마

**파일**: `backend/app/db/models.py`

### 1. Session 테이블
```python
class Session(Base):
    __tablename__ = "session"

    id = Column(String, primary_key=True)  # UUID v4
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    task_results = relationship("TaskResult", back_populates="session", cascade="all, delete-orphan")
```

**용도**: 사용자 세션 관리 (멀티턴 대화 추적)

---

### 2. Message 테이블
```python
class Message(Base):
    __tablename__ = "message"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("session.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # "user" | "assistant" | "system"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("Session", back_populates="messages")
```

**용도**: 대화 히스토리 저장 (멀티턴 컨텍스트 제공)

---

### 3. RagDoc 테이블
```python
class RagDoc(Base):
    __tablename__ = "rag_doc"

    id = Column(String, primary_key=True)  # UUID v4
    category = Column(String, nullable=False, index=True)  # "trend", "ad", "segment" 등
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)  # FTS5 인덱싱 대상
    meta_json = Column(JSON, nullable=True)  # 추가 메타데이터
    created_at = Column(DateTime, default=datetime.utcnow)
```

**FTS5 Virtual Table**:
```sql
CREATE VIRTUAL TABLE rag_fts USING fts5(
    doc_id UNINDEXED,
    title,
    content,
    content='rag_doc',
    content_rowid='rowid'
);
```

**용도**:
- RAG 검색 (과거 분석 결과 참조)
- 광고 문구 일관성 유지
- 트렌드 패턴 학습

**검색 쿼리 예시**:
```sql
-- FTS5 MATCH (BM25 랭킹)
SELECT doc_id FROM rag_fts
WHERE rag_fts MATCH '스마트워치 트렌드'
ORDER BY rank
LIMIT 5;
```

---

### 4. TaskResult 테이블
```python
class TaskResult(Base):
    __tablename__ = "task_result"

    id = Column(String, primary_key=True)  # UUID v4
    session_id = Column(String, ForeignKey("session.id", ondelete="CASCADE"), nullable=False, index=True)
    task_type = Column(String, nullable=False)  # "trend", "ad_copy", "segment" 등
    product_name = Column(String, nullable=True)
    result_data = Column(JSON, nullable=False)  # 태스크 결과 (구조화된 JSON)
    pdf_path = Column(String, nullable=True)  # PDF 파일 경로
    html_path = Column(String, nullable=True)  # HTML 파일 경로
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    session = relationship("Session", back_populates="task_results")
```

**용도**:
- 태스크 실행 결과 저장
- 종합 보고서 생성 시 데이터 집계
- 세션별 분석 이력 관리

**result_data 구조 예시 (Trend)**:
```json
{
  "keyword": "스마트워치",
  "time_window": {"start": "2024-01-01", "end": "2024-04-01"},
  "analysis": {
    "average": 45.2,
    "latest": 52.3,
    "growth": 15.7,
    "momentum": 8.5,
    "peak": 68.9,
    "volatility": 12.3,
    "signal": "상승세"
  },
  "clusters": [
    {"name": "건강 관리", "keywords": ["운동", "심박수"], "insight": "..."}
  ],
  "insights": ["실행 가능한 제안 1", "실행 가능한 제안 2"]
}
```

---

## 🔧 핵심 기술 구현 상세

### 1. 라우터 (Router) 메커니즘

**파일**: `backend/app/agents/router.py`

**구현**: [router.py:54-76](backend/app/agents/router.py#L54-L76)

```python
AGENT_MAP = {
    "trend": {
        "keywords": ["트렌드", "검색량", "인기도", "관심도"],
        "runner": run_trend_agent
    },
    "ad_copy": {
        "keywords": ["광고", "카피", "문구", "슬로건"],
        "runner": run_ad_copy_agent
    },
    "segment": {
        "keywords": ["세그먼트", "고객", "타겟", "분류"],
        "runner": run_segment_agent
    },
    # ... (생략)
}

def route_to_agent(user_message: str) -> Optional[str]:
    """사용자 메시지에서 키워드 감지하여 적절한 에이전트 선택"""
    for agent_name, config in AGENT_MAP.items():
        if any(keyword in user_message for keyword in config["keywords"]):
            return agent_name
    return None
```

**동작 원리**:
1. 사용자 메시지 수신
2. 키워드 매칭 (정규표현식 또는 포함 검사)
3. 매칭된 에이전트 runner 실행
4. 실행 결과 반환

---

### 2. RAG 검색 구현

**파일**: `backend/app/db/crud.py`

**FTS5 검색** [crud.py:97-127](backend/app/db/crud.py#L97-L127):
```python
def search_rag_docs(
    db: Session,
    query: str,
    category: Optional[str] = None,
    limit: int = 5
) -> List[RagDoc]:
    """
    FTS5를 사용한 전체 텍스트 검색

    Args:
        query: 검색어
        category: 필터링할 카테고리 (선택)
        limit: 반환 개수

    Returns:
        관련성 높은 문서 리스트 (BM25 랭킹)
    """
    try:
        # FTS5 MATCH 쿼리
        fts_query = text("""
            SELECT doc_id FROM rag_fts
            WHERE rag_fts MATCH :query
            ORDER BY rank
            LIMIT :limit
        """)
        fts_results = db.execute(fts_query, {"query": query, "limit": limit}).fetchall()

        doc_ids = [row[0] for row in fts_results]

        # 실제 문서 조회
        docs_query = db.query(RagDoc).filter(RagDoc.id.in_(doc_ids))
        if category:
            docs_query = docs_query.filter(RagDoc.category == category)

        return docs_query.all()

    except Exception as e:
        logger.warning(f"FTS5 검색 실패, LIKE로 fallback: {e}")
        # Fallback: LIKE 기반 검색
        query_pattern = f"%{query}%"
        docs_query = db.query(RagDoc).filter(
            or_(
                RagDoc.title.like(query_pattern),
                RagDoc.content.like(query_pattern)
            )
        )
        if category:
            docs_query = docs_query.filter(RagDoc.category == category)

        return docs_query.limit(limit).all()
```

**특징**:
- **Primary**: BM25 기반 FTS5 검색 (관련성 랭킹)
- **Fallback**: LIKE 기반 substring 검색
- **필터링**: 카테고리별 선택적 검색
- **임베딩 불필요**: 키워드 기반 검색으로 빠른 성능

---

### 3. PDF 생성 파이프라인

**파일**: `backend/app/tools/pdf_generator.py`

**한글 폰트 등록** [pdf_generator.py:35-86](backend/app/tools/pdf_generator.py#L35-L86):
```python
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def register_korean_font():
    """Windows 시스템 폰트에서 MalgunGothic 등록"""
    font_paths = [
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\gulim.ttc",
        # ... (다른 경로 fallback)
    ]

    for path in font_paths:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont('MalgunGothic', path))
            return True

    raise FileNotFoundError("한글 폰트를 찾을 수 없습니다")
```

**차트 생성 (Matplotlib)** [pdf_generator.py:150-220](backend/app/tools/pdf_generator.py#L150-L220):
```python
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

def create_trend_chart(trend_data: List[Dict], output_path: str):
    """시계열 트렌드 차트 생성"""
    # 한글 폰트 설정
    font_path = "C:/Windows/Fonts/malgun.ttf"
    font_prop = fm.FontProperties(fname=font_path)
    plt.rcParams['font.family'] = font_prop.get_name()

    # 데이터 추출
    dates = [item['period'] for item in trend_data]
    values = [item['ratio'] for item in trend_data]

    # 차트 생성
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, values, marker='o', linewidth=2, color='#4285F4')
    ax.set_xlabel('날짜', fontproperties=font_prop)
    ax.set_ylabel('검색 관심도', fontproperties=font_prop)
    ax.set_title('트렌드 분석', fontproperties=font_prop, fontsize=16)
    ax.grid(True, alpha=0.3)

    # 파일 저장
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
```

**PDF 조합** [pdf_generator.py:269-539](backend/app/tools/pdf_generator.py#L269-L539):
```python
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, Image, PageBreak

def generate_trend_pdf(analysis_data: Dict, output_path: str):
    """트렌드 분석 PDF 보고서 생성"""
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    story = []

    # 스타일 정의
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontName='MalgunGothic')
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontName='MalgunGothic')

    # 1. 제목
    story.append(Paragraph(f"{product_name} 트렌드 분석 보고서", title_style))
    story.append(Spacer(1, 20))

    # 2. 지표 테이블
    metrics_table = Table([
        ['평균', f"{analysis['average']:.1f}"],
        ['최신값', f"{analysis['latest']:.1f}"],
        ['성장률', f"{analysis['growth']:.1f}%"],
        # ...
    ])
    story.append(metrics_table)

    # 3. 차트 삽입
    chart_path = "/tmp/trend_chart.png"
    create_trend_chart(trend_data, chart_path)
    story.append(Image(chart_path, width=400, height=250))

    # 4. 빌드
    doc.build(story)
```

---

### 4. 멀티턴 대화 처리

**파일**: `backend/app/routes/chat.py`

**구현** [chat.py:45-120](backend/app/routes/chat.py#L45-L120):
```python
@router.post("/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    # 1. 세션 조회/생성
    if not request.session_id:
        session = Session(id=str(uuid.uuid4()))
        db.add(session)
    else:
        session = db.query(Session).filter(Session.id == request.session_id).first()
        if not session:
            raise HTTPException(404, "세션을 찾을 수 없습니다")

    # 2. 사용자 메시지 저장
    user_msg = Message(
        session_id=session.id,
        role="user",
        content=request.message
    )
    db.add(user_msg)
    db.commit()

    # 3. 대화 히스토리 조회 (최근 10개)
    history = db.query(Message)\
        .filter(Message.session_id == session.id)\
        .order_by(Message.created_at.desc())\
        .limit(10)\
        .all()
    history.reverse()  # 시간순 정렬

    # 4. 에이전트 라우팅 및 실행
    agent_name = route_to_agent(request.message)
    if agent_name:
        runner = AGENT_MAP[agent_name]["runner"]
        response_text = await runner(
            message=request.message,
            session_id=session.id,
            history=history,  # 컨텍스트 전달
            db=db
        )
    else:
        response_text = "어떤 분석을 원하시나요? (트렌드/광고/세그먼트/리뷰/경쟁사)"

    # 5. 어시스턴트 응답 저장
    assistant_msg = Message(
        session_id=session.id,
        role="assistant",
        content=response_text
    )
    db.add(assistant_msg)
    db.commit()

    return {
        "session_id": session.id,
        "response": response_text,
        "agent_used": agent_name
    }
```

**특징**:
- UUID 기반 세션 관리
- 대화 히스토리 컨텍스트 제공
- 세션별 태스크 결과 격리

---

## 👥 팀 협업 가이드

### 각 팀원의 작업 범위

**팀원 1: 트렌드 분석**
- `backend/app/agents/trend_agent.py` 구현
- `backend/app/tools/trend_tools.py` 구현
- Google Trends, Naver DataLab API 연동

**팀원 2: 광고 문구 생성**
- `backend/app/agents/ad_copy_agent.py` 구현
- `backend/app/tools/ad_tools.py` 구현
- LLM 프롬프트 최적화

**팀원 3: 사용자 세그먼트 분류**
- `backend/app/agents/segment_agent.py` 구현
- `backend/app/tools/segment_tools.py` 구현
- scikit-learn 클러스터링 알고리즘 적용

**팀원 4: 리뷰 감성 분석**
- `backend/app/agents/review_agent.py` 구현
- `backend/app/tools/review_tools.py` 구현
- 크롤링 또는 API로 리뷰 수집, 감성 분석

**팀원 5: 경쟁사 분석**
- `backend/app/agents/competitor_agent.py` 구현
- `backend/app/tools/competitor_tools.py` 구현
- 가격 비교, SWOT 분석 로직

### 작업 흐름

1. 각 팀원은 자신의 에이전트/툴 파일을 구현
2. `.env`에 필요한 API 키 추가
3. `backend/app/agents/router.py`에서 에이전트 활성화:
   ```python
   from app.agents.trend_agent import run_agent as run_trend
   AGENT_MAP["trend"]["runner"] = run_trend
   ```
4. 채팅창에서 키워드로 테스트

## 🔑 환경 변수 설정

`backend/.env` 파일에서 설정:

```env
# 필수
OPENAI_API_KEY=your_openai_key_here

# 선택 (태스크별 필요 시)
NAVER_DATALAB_CLIENT_ID=your_naver_client_id_here
NAVER_SHOPPING_CLIENT_ID=your_naver_shopping_client_id_here
GOOGLE_CUSTOM_SEARCH_API_KEY=your_google_search_key_here
```

## 🧪 테스트

백엔드가 실행된 상태에서:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "트렌드 분석해줘", "session_id": ""}'
```

## 📝 라이선스

MIT License

## 🤝 기여

이슈나 PR을 환영합니다!

## 📞 문의

프로젝트 관련 문의는 이슈로 남겨주세요.
