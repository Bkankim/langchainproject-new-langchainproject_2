# Google Custom Search API 설정 가이드

실제 웹 검색 기반 RAG를 사용하기 위한 Google Custom Search JSON API 설정 방법입니다.

---

## 📋 준비물

- Google 계정
- 신용카드 (무료 할당량 초과 시 과금 방지용)

---

## 🔑 1단계: Google Custom Search API 키 발급

### 1. Google Cloud Console 접속

https://console.cloud.google.com/

### 2. 새 프로젝트 생성 (또는 기존 프로젝트 선택)

1. 상단 프로젝트 선택 드롭다운 클릭
2. "새 프로젝트" 클릭
3. 프로젝트 이름: `commerce-marketing-agent` 입력
4. "만들기" 클릭

### 3. Custom Search API 활성화

1. 좌측 메뉴 → "API 및 서비스" → "라이브러리"
2. 검색창에 `Custom Search API` 입력
3. "Custom Search API" 선택
4. "사용 설정" 클릭

### 4. API 키 생성

1. 좌측 메뉴 → "API 및 서비스" → "사용자 인증 정보"
2. 상단 "+ 사용자 인증 정보 만들기" → "API 키" 클릭
3. 생성된 API 키 복사
4. (권장) "API 키 제한" 클릭 → "API 제한사항" → "Custom Search API만 선택"

**생성된 API 키 예시:**
```
AIzaSyBxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 🔍 2단계: Programmable Search Engine 생성

### 1. Programmable Search Engine 콘솔 접속

https://programmablesearchengine.google.com/

### 2. 새 검색 엔진 생성

1. "시작하기" 또는 "추가" 클릭
2. **검색할 사이트 설정:**
   - 옵션 1: **전체 웹 검색** (권장)
     - "전체 웹 검색" 선택
   - 옵션 2: **특정 사이트만 검색**
     - "검색할 사이트" 입력:
       ```
       shopping.naver.com
       www.coupang.com
       www.11st.co.kr
       prod.danawa.com
       ```
3. **검색 엔진 이름**: `Commerce Review Search`
4. "만들기" 클릭

### 3. 검색 엔진 ID 복사

1. 생성 완료 후 "제어판" 클릭
2. "검색 엔진 ID" 복사

**검색 엔진 ID 예시:**
```
a1b2c3d4e5f6g7h8i
```

---

## ⚙️ 3단계: .env 파일 설정

### 1. .env 파일 생성

`backend/.env` 파일을 생성하고 다음 내용 추가:

```env
# OpenAI API
OPENAI_API_KEY=sk-proj-xxxxx

# Google Custom Search API
GOOGLE_SEARCH_API_KEY=AIzaSyBxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GOOGLE_SEARCH_ENGINE_ID=a1b2c3d4e5f6g7h8i

# Database
DB_URL=sqlite:///./commerce_marketing_agent.db
REPORT_DIR=./reports
```

### 2. 환경 변수 로드 확인

백엔드 서버를 재시작하면 자동으로 로드됩니다:

```bash
cd backend
python -m app.main
```

로그에서 다음 메시지 확인:
```
커머스 마케팅 에이전트 준비 완료
```

---

## 💰 4단계: 무료 할당량 및 비용

### 무료 할당량

- **하루 100회 검색 무료**
- 100회 초과 시 1,000회당 $5 과금

### 비용 절감 팁

1. **캐싱 활용**: 동일한 제품은 재검색하지 않음
2. **검색 결과 수 제한**: `num_results=5` (기본값)
3. **테스트 시 모의 데이터 사용**: API 키 없으면 자동으로 모의 데이터 반환

### 사용량 모니터링

1. Google Cloud Console → "API 및 서비스" → "대시보드"
2. "Custom Search API" 클릭
3. "할당량" 탭에서 사용량 확인

---

## 🧪 5단계: 테스트

### 1. 백엔드 서버 실행

```bash
cd backend
python -m app.main
```

### 2. 프론트엔드 실행

```bash
cd frontend
npm run dev
```

### 3. 채팅창에서 테스트

프롬프트 입력:
```
갤럭시 버즈 구매자를 세그먼트로 분류해줘
```

### 4. 로그 확인

백엔드 터미널에서 다음 로그 확인:

```
INFO - 커머스 사이트 우선 검색: 갤럭시 버즈 리뷰 후기
INFO - Google Search API 호출: query=갤럭시 버즈 리뷰 후기 (site:shopping.naver.com OR ...), num=5
INFO - 웹 검색 완료: 5개 결과
INFO - 검색된 5개 URL에서 리뷰 크롤링 시도
INFO - 리뷰 크롤링 시작: https://shopping.naver.com/...
INFO - 총 25개 리뷰 수집 완료 (중복 제거 후)
```

**✅ 실제 웹 검색이 작동하면 성공!**

---

## ❌ 문제 해결

### 1. API 키가 작동하지 않는 경우

**로그:**
```
WARNING - Google Search API 키가 설정되지 않았습니다. 모의 데이터를 반환합니다.
```

**해결:**
- `.env` 파일이 `backend/` 디렉토리에 있는지 확인
- API 키와 검색 엔진 ID 형식 확인
- 백엔드 서버 재시작

### 2. API 호출 실패

**로그:**
```
ERROR - Google Search API 호출 실패: 403 Client Error: Forbidden
```

**해결:**
- Google Cloud Console에서 Custom Search API가 활성화되었는지 확인
- API 키 제한 설정 확인 (IP 주소, Referrer 제한 없애기)
- 청구 계정 활성화 확인

### 3. 검색 결과가 없는 경우

**로그:**
```
INFO - 웹 검색 완료: 0개 결과
```

**해결:**
- 검색 쿼리 확인
- Programmable Search Engine 설정에서 "전체 웹 검색" 활성화
- 한국어 설정: `hl=ko`, `gl=kr` 파라미터 확인

### 4. 크롤링 실패

**로그:**
```
ERROR - 크롤링 실패: 403 Forbidden
```

**해결:**
- 일부 사이트는 봇 차단 기능 있음 (정상)
- 검색 결과의 snippet만 사용 (크롤링 없이도 작동)
- 필요 시 Selenium 사용 (현재는 BeautifulSoup만 사용)

---

## 🚀 고급 설정 (선택사항)

### 1. 검색 언어 및 지역 변경

`web_search.py:52-53` 수정:

```python
"hl": "en",  # 영어
"gl": "us",  # 미국
```

### 2. 검색 결과 개수 조정

`segment_tools.py:80` 수정:

```python
search_results = search_web_kr_commerce(search_query, num_results=10)  # 10개로 증가
```

### 3. 특정 도메인만 검색

`web_search.py:100` 수정:

```python
commerce_query = f"{query} site:shopping.naver.com"  # 네이버 쇼핑만
```

---

## 📚 참고 자료

- [Google Custom Search JSON API 문서](https://developers.google.com/custom-search/v1/introduction)
- [Programmable Search Engine 가이드](https://developers.google.com/custom-search/docs/tutorial/introduction)
- [API 요금 안내](https://developers.google.com/custom-search/v1/overview#pricing)

---

**구현 완료!** 이제 실제 웹 검색 기반 RAG가 작동합니다. 🎉
