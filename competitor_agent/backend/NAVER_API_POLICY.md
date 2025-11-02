# 네이버 API 이용약관 준수 정책

본 프로젝트는 네이버 오픈 API 이용약관을 철저히 준수합니다.

## 핵심 규칙 (절대 준수)

### 1. 공식 API만 사용 ✓
```python
# ✅ 허용: 공식 API 사용
url = "https://openapi.naver.com/v1/search/shop.json"

# ❌ 금지: 웹 크롤링, 스크래핑
# BeautifulSoup, Selenium 등을 이용한 네이버 쇼핑 페이지 크롤링 절대 금지
```

**구현 파일**: `backend/app/tools/competitor_tools.py`
- `fetch_from_naver_shopping_api()` 함수만 사용
- 크롤링 로직 없음 (주석으로 명시)

### 2. Rate Limit 준수 (초당 10건) ✓
```python
# 초당 10건 = 0.1초 간격
class NaverAPIRateLimiter:
    def __init__(self, calls_per_second: int = 10):
        self.min_interval = 1.0 / calls_per_second  # 0.1초
```

**구현 방식**:
- Thread-safe Rate Limiter 클래스
- API 호출 전 `_naver_rate_limiter.wait_if_needed()` 자동 호출
- 병렬 요청 시에도 안전하게 처리

**테스트**:
```bash
# 5개 제품 검색 시 소요 시간: 약 0.5초 (5 × 0.1초)
time curl -X POST http://localhost:30560/chat -d '{"message": "..."}'
```

### 3. 크롤링 절대 금지 ✓
```python
# ❌ 절대 사용 금지
# import requests
# from bs4 import BeautifulSoup
# response = requests.get("https://shopping.naver.com/...")
# soup = BeautifulSoup(response.text, 'html.parser')

# ❌ 절대 사용 금지
# from selenium import webdriver
# driver.get("https://shopping.naver.com/...")
```

**금지 사항**:
- BeautifulSoup 사용 금지
- Selenium/Playwright로 네이버 쇼핑 접근 금지
- HTML 파싱 금지
- CSS Selector 사용 금지

**Fallback Chain**:
```
네이버 쇼핑 API (공식) → Mock 데이터
(크롤링 단계 없음)
```

## 추가 보안 조치

### User-Agent 설정
```python
headers = {
    "X-Naver-Client-Id": NAVER_CLIENT_ID,
    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    "User-Agent": "Mozilla/5.0 (compatible; CommerceMarketingAI/1.0)"
}
```

### Timeout 설정
```python
response = requests.get(url, headers=headers, params=params, timeout=10)
```

### 에러 처리
```python
except requests.HTTPError as e:
    if status_code == 429:
        # Rate Limit 초과 (초당 10건 위반)
    elif status_code == 403:
        # 접근 금지 (크롤링 의심 또는 이용약관 위반)
    elif status_code == 401:
        # 인증 실패 (API 키 오류)
```

## 모니터링

### 로그 확인
```bash
# Rate Limit 대기 로그
grep "\[Rate Limit\]" backend.log

# API 호출 로그
grep "\[API\]" backend.log

# 에러 로그
grep "ERROR" backend.log | grep "네이버"
```

### 성공 지표
- ✅ API 호출 성공률 > 95%
- ✅ Rate Limit 초과 (429) = 0건
- ✅ 접근 금지 (403) = 0건
- ✅ 평균 응답 시간 < 500ms

## 위반 시 조치

### 403 Forbidden 발생 시
1. **즉시 중단**: API 호출 중단
2. **원인 분석**:
   - Rate Limit 위반 여부 확인
   - 크롤링 로직 혼입 여부 확인
3. **재시도 금지**: 24시간 대기
4. **네이버 개발자센터 확인**: API 사용 상태 점검

### 429 Too Many Requests 발생 시
1. **Rate Limiter 검증**: `calls_per_second` 설정 확인
2. **로그 분석**: 실제 호출 간격 확인
3. **재시도 간격 증가**: 0.1초 → 0.2초 (초당 5건)

## 책임 및 면책

본 프로젝트는 네이버 API 이용약관을 준수하기 위해 최선을 다하고 있습니다.
- 공식 API만 사용
- Rate Limit 준수
- 크롤링 금지

위 정책을 위반한 경우, 네이버 개발자센터의 조치(API 키 차단 등)에 대한 책임은 사용자에게 있습니다.

## 참고 문서

- [네이버 오픈 API 이용 가이드](https://developers.naver.com/docs/common/openapiguide/)
- [네이버 검색 API - 쇼핑](https://developers.naver.com/docs/serviceapi/search/shopping/shopping.md)
- [네이버 API 공통 가이드](https://developers.naver.com/docs/common/openapiguide/apilist.md)

---

**최종 업데이트**: 2025-11-01
**담당자**: 경쟁사 분석 에이전트 팀
