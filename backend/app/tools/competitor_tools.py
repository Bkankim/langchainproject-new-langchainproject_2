"""
경쟁사 분석 도구 함수 (Layer 1)
LLM 기반 제품 정보 추출, API 데이터 수집, SWOT 분석, 보고서 생성

네이버 API 이용약관 준수:
- 공식 API만 사용 (openapi.naver.com)
- Rate Limit: 초당 10건 (0.1초 간격)
- 크롤링 절대 금지
"""
import logging
import os
import json
import re
import requests
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from threading import Lock
import pandas as pd
from io import StringIO

from app.tools.llm import call_llm_with_context
from app.tools.common.web_search import search_web

logger = logging.getLogger(__name__)

# 네이버 API 키 - 환경변수에서 직접 읽기 (trend_tools.py와 동일한 방식)
NAVER_CLIENT_ID = os.getenv("NAVER_SHOPPING_CLIENT_ID") or os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_SHOPPING_CLIENT_SECRET") or os.getenv("NAVER_CLIENT_SECRET")

# 카테고리별 벤치마크 평가 지표 템플릿
# 주의: 리뷰/평점 데이터는 네이버 쇼핑 API에서 제공하지 않음
BENCHMARK_TEMPLATES = {
    "스마트폰": {
        "metrics": [
            {"name": "가격 경쟁력", "key": "price_score"},
            {"name": "브랜드 파워", "key": "brand_score"},
            {"name": "종합 점수", "key": "total_score"}
        ]
    },
    "노트북": {
        "metrics": [
            {"name": "가격 경쟁력", "key": "price_score"},
            {"name": "브랜드 파워", "key": "brand_score"},
            {"name": "종합 점수", "key": "total_score"}
        ]
    },
    "태블릿": {
        "metrics": [
            {"name": "가격 경쟁력", "key": "price_score"},
            {"name": "브랜드 파워", "key": "brand_score"},
            {"name": "종합 점수", "key": "total_score"}
        ]
    },
    "기타": {
        "metrics": [
            {"name": "가격 경쟁력", "key": "price_score"},
            {"name": "브랜드 파워", "key": "brand_score"},
            {"name": "종합 점수", "key": "total_score"}
        ]
    }
}

# Chart.js 레이더 차트 HTML 템플릿
CHART_HTML_TEMPLATE = """
<div style="max-width: 800px; margin: 20px auto;">
    <h3 style="text-align: center; margin-bottom: 20px;">📊 벤치마크 비교 차트</h3>
    <canvas id="benchmarkRadarChart"></canvas>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
const ctx = document.getElementById('benchmarkRadarChart');
const chartData = {chart_data_json};

new Chart(ctx, {
    type: 'radar',
    data: chartData,
    options: {
        responsive: true,
        maintainAspectRatio: true,
        scales: {
            r: {
                beginAtZero: true,
                max: 100,
                ticks: {
                    stepSize: 20
                }
            }
        },
        plugins: {
            legend: {
                position: 'bottom'
            },
            title: {
                display: false
            }
        }
    }
});
</script>
"""

# Chart.js 파이 차트 HTML 템플릿 (시장점유율 분석용)
PIE_CHART_HTML_TEMPLATE = """
<div style="max-width: 800px; margin: 20px auto;">
    <h3 style="text-align: center; margin-bottom: 20px;">📊 시장점유율 분석</h3>
    <canvas id="marketShareChart"></canvas>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
const marketCtx = document.getElementById('marketShareChart');
const marketData = {market_data_json};

new Chart(marketCtx, {
    type: 'pie',
    data: {
        labels: marketData.labels,
        datasets: [{
            data: marketData.shares,
            backgroundColor: [
                'rgba(255, 99, 132, 0.8)',
                'rgba(54, 162, 235, 0.8)',
                'rgba(255, 206, 86, 0.8)',
                'rgba(75, 192, 192, 0.8)',
                'rgba(153, 102, 255, 0.8)'
            ],
            borderWidth: 2,
            borderColor: '#fff'
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: {
                position: 'right',
                labels: {
                    padding: 15,
                    font: {
                        size: 12
                    }
                }
            },
            tooltip: {
                callbacks: {
                    label: function(context) {
                        return context.label + ': ' + context.parsed + '%';
                    }
                }
            }
        }
    }
});
</script>
"""

# Rate Limiter: 네이버 API 초당 10건 제한 준수
class NaverAPIRateLimiter:
    """
    네이버 API Rate Limit 준수 (초당 10건)
    Thread-safe 구현
    """
    def __init__(self, calls_per_second: int = 10):
        self.min_interval = 1.0 / calls_per_second  # 0.1초
        self.last_call_time = 0.0
        self.lock = Lock()

    def wait_if_needed(self):
        """API 호출 전 Rate Limit 체크 및 대기"""
        with self.lock:
            current_time = time.time()
            time_since_last_call = current_time - self.last_call_time

            if time_since_last_call < self.min_interval:
                wait_time = self.min_interval - time_since_last_call
                logger.debug(f"[Rate Limit] {wait_time:.3f}초 대기")
                time.sleep(wait_time)

            self.last_call_time = time.time()

# 전역 Rate Limiter 인스턴스 (싱글톤 패턴)
_naver_rate_limiter = NaverAPIRateLimiter(calls_per_second=10)


def fetch_ugc_mentions(product_name: str) -> Dict[str, int]:
    """
    블로그 + 카페 언급수 조회 (네이버 검색 API)

    온라인 반응도 측정을 위한 실제 UGC 데이터 수집.
    리뷰 데이터가 아닌 제품 관심도 측정 지표입니다.

    Args:
        product_name: 제품명 (검색 쿼리)

    Returns:
        {
            "blog_count": int,     # 블로그 언급 수
            "cafe_count": int,     # 카페 언급 수
            "total": int           # 합계
        }

    네이버 API 사용:
    - Blog Search API: /v1/search/blog.json
    - Cafe Search API: /v1/search/cafearticle.json
    - 인증: Client ID/Secret (비로그인 오픈 API)
    - Rate Limit: 초당 10건 (자동 준수)
    """
    logger.info(f"UGC 언급수 조회 시작: {product_name}")

    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        logger.warning("[UGC] 네이버 API 키 미설정 - 기본값 반환")
        return {"blog_count": 0, "cafe_count": 0, "total": 0}

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "User-Agent": "Mozilla/5.0 (compatible; CommerceMarketingAI/1.0)"
    }

    blog_count = 0
    cafe_count = 0

    # 1. 블로그 검색
    try:
        _naver_rate_limiter.wait_if_needed()
        blog_url = "https://openapi.naver.com/v1/search/blog.json"
        blog_response = requests.get(
            blog_url,
            headers=headers,
            params={"query": product_name, "display": 100, "sort": "sim"},
            timeout=10
        )

        if blog_response.status_code == 200:
            blog_data = blog_response.json()
            blog_count = blog_data.get("total", 0)
            logger.info(f"[UGC] 블로그 언급: {blog_count}건")
        else:
            logger.warning(f"[UGC] 블로그 API 오류: {blog_response.status_code}")

    except requests.Timeout:
        logger.error("[UGC] 블로그 API 타임아웃 (10초)")
    except Exception as e:
        logger.error(f"[UGC] 블로그 API 예외: {e}")

    # 2. 카페 검색
    try:
        _naver_rate_limiter.wait_if_needed()
        cafe_url = "https://openapi.naver.com/v1/search/cafearticle.json"
        cafe_response = requests.get(
            cafe_url,
            headers=headers,
            params={"query": product_name, "display": 100, "sort": "sim"},
            timeout=10
        )

        if cafe_response.status_code == 200:
            cafe_data = cafe_response.json()
            cafe_count = cafe_data.get("total", 0)
            logger.info(f"[UGC] 카페 언급: {cafe_count}건")
        else:
            logger.warning(f"[UGC] 카페 API 오류: {cafe_response.status_code}")

    except requests.Timeout:
        logger.error("[UGC] 카페 API 타임아웃 (10초)")
    except Exception as e:
        logger.error(f"[UGC] 카페 API 예외: {e}")

    total = blog_count + cafe_count
    logger.info(f"[UGC] 총 언급: {total}건 (블로그 {blog_count} + 카페 {cafe_count})")

    return {
        "blog_count": blog_count,
        "cafe_count": cafe_count,
        "total": total
    }


def calculate_popularity_signal(product_data: Dict, category: str = "기타") -> Dict[str, Any]:
    """
    제품 인기도 신호 계산 (리뷰가 아닌 온라인 반응도)

    실제 리뷰 데이터가 아닌 판매 가능성과 UGC 언급량을 결합한 지표입니다.
    순위 산정에는 반영하지 않으며 참고용으로만 제공됩니다.

    Args:
        product_data: 제품 데이터 딕셔너리
            필수: name, brand, price, mall (리스트)
            선택: search_rank
        category: 제품 카테고리 (가격 비교용)

    Returns:
        {
            "level": str,             # "높음", "보통", "낮음"
            "ugc_mentions": int,      # 블로그+카페 총 언급 수
            "ugc_breakdown": Dict,    # 블로그/카페 세부 데이터
            "popularity_score": float,  # 내부 점수 (0-100)
            "factors": Dict           # 세부 지표들
        }

    계산 방식:
    - 판매 가능성 (50%): mall diversity, brand power, price factor, rank score
    - UGC 언급량 (50%): 블로그 + 카페 검색 결과 수
    """
    logger.info(f"인기도 신호 계산 시작: {product_data.get('name', 'Unknown')}")

    # 브랜드별 가중치 (기존 정의 재사용)
    brand_weights = {
        "Apple": 95, "Samsung": 90, "삼성": 90, "삼성전자": 90,
        "LG": 85, "Xiaomi": 75, "샤오미": 75,
        "Oppo": 70, "Vivo": 70, "Unknown": 50
    }

    # 카테고리별 평균 가격 (간소화)
    category_avg_prices = {
        "스마트폰": 800000,
        "노트북": 1500000,
        "태블릿": 600000,
        "기타": 500000
    }
    category_avg = category_avg_prices.get(category, 500000)

    # 1. 판매 가능성 지표 계산
    # 1-1. Mall Diversity (유통 채널 다양성)
    mall_list = product_data.get("mall", [])
    mall_diversity = min((len(mall_list) / 4.0) * 100, 100)  # 4개 이상 = 100점

    # 1-2. Brand Power (브랜드 파워)
    brand = product_data.get("brand", "Unknown")
    brand_power = brand_weights.get(brand, 50)

    # 1-3. Price Factor (가격 요인)
    price = product_data.get("price", 0)

    # 고가 플래그십 예외 처리
    flagship_brands = ["Samsung", "삼성", "삼성전자", "Apple", "LG"]
    is_flagship = brand in flagship_brands and price > category_avg * 1.5

    if is_flagship:
        # 플래그십은 비싸도 인기 많음
        price_factor = 80
        logger.info(f"[인기도] 플래그십 예외 적용: {brand} {price:,}원 > {category_avg * 1.5:,.0f}원")
    elif price > 0 and category_avg > 0:
        # 일반 제품: 저렴할수록 좋음
        price_factor = max(0, (1 - (price / category_avg)) * 100)
    else:
        price_factor = 50  # 중립

    # 1-4. Rank Score (검색 순위)
    search_rank = product_data.get("search_rank", 5)
    rank_score = ((5 - search_rank + 1) / 5.0) * 100

    # 판매 가능성 종합 (가중 평균)
    sales_potential = (
        mall_diversity * 0.30 +
        brand_power * 0.30 +
        price_factor * 0.20 +
        rank_score * 0.20
    )

    # 2. UGC 언급량 점수
    product_name = product_data.get("name", "")
    ugc_data = fetch_ugc_mentions(product_name)
    ugc_total = ugc_data["total"]

    # 1,000건 기준 100점 환산 (선형 스케일)
    ugc_score = min(100, (ugc_total / 1000) * 100)

    # 3. 복합 점수 (50:50)
    popularity_score = (sales_potential * 0.5) + (ugc_score * 0.5)

    # 4. 레벨 분류 (숫자 제거!)
    if popularity_score >= 75:
        level = "높음"
    elif popularity_score >= 50:
        level = "보통"
    else:
        level = "낮음"

    logger.info(
        f"[인기도] {product_name}: {level} "
        f"(점수 {popularity_score:.1f} = 판매 {sales_potential:.1f} + UGC {ugc_score:.1f})"
    )

    return {
        "level": level,
        "ugc_mentions": ugc_total,
        "ugc_breakdown": ugc_data,
        "popularity_score": round(popularity_score, 1),
        "factors": {
            "sales_potential": round(sales_potential, 1),
            "ugc_score": round(ugc_score, 1),
            "mall_diversity": round(mall_diversity, 1),
            "brand_power": brand_power,
            "price_factor": round(price_factor, 1),
            "rank_score": round(rank_score, 1)
        }
    }


def extract_product_info(user_message: str) -> Dict[str, Any]:
    """
    사용자 메시지에서 제품 정보 추출 (LLM)

    Args:
        user_message: 사용자 입력

    Returns:
        {"target": str, "competitors": List[str], "category": str}
    """
    logger.info(f"제품 정보 추출 시작: {user_message[:50]}...")

    system_prompt = """
당신은 제품명 추출 전문가입니다.
사용자 메시지에서 다음을 추출하세요:
1. 우리 제품명 (첫 번째로 언급된 제품)
2. 경쟁사 제품명 리스트 (나머지 제품들, 1~5개)
3. 제품 카테고리 (추론)

JSON 형식으로만 응답:
{
    "target": "제품명",
    "competitors": ["경쟁사1", "경쟁사2"],
    "category": "카테고리"
}

예시:
- 입력: "아이폰 15 프로와 갤럭시 S24 울트라 비교"
- 출력: {"target": "아이폰 15 프로", "competitors": ["갤럭시 S24 울트라"], "category": "스마트폰"}

- 입력: "LG 그램 17 경쟁사 분석"
- 출력: {"target": "LG 그램 17", "competitors": [], "category": "노트북"}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]

    response = call_llm_with_context(messages)

    if not response.get("success"):
        logger.error(f"LLM 호출 실패: {response.get('error')}")
        return {
            "target": None,
            "competitors": [],
            "category": "일반"
        }

    # JSON 파싱
    reply_text = response.get("reply_text", "")
    try:
        # JSON 추출 (```json ... ``` 또는 {...} 형태)
        json_match = re.search(r'\{.*\}', reply_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            logger.info(f"제품 정보 추출 성공: target={result.get('target')}, competitors={len(result.get('competitors', []))}개")
            return result
        else:
            logger.warning("JSON 형식을 찾을 수 없음, 기본값 반환")
            return {
                "target": None,
                "competitors": [],
                "category": "일반"
            }
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 실패: {e}")
        return {
            "target": None,
            "competitors": [],
            "category": "일반"
        }


def fetch_from_naver_shopping_api(product_name: str) -> Optional[Dict[str, Any]]:
    """
    네이버 쇼핑 API로 제품 정보 가져오기

    Args:
        product_name: 검색할 제품명

    Returns:
        제품 데이터 딕셔너리 또는 None (실패 시)
    """
    # 디버깅: API 키 로드 상태 확인
    logger.info(f"[DEBUG] NAVER_CLIENT_ID: {NAVER_CLIENT_ID[:10]}... (길이: {len(NAVER_CLIENT_ID) if NAVER_CLIENT_ID else 0})")
    logger.info(f"[DEBUG] NAVER_CLIENT_SECRET: {'설정됨' if NAVER_CLIENT_SECRET else '없음'} (길이: {len(NAVER_CLIENT_SECRET) if NAVER_CLIENT_SECRET else 0})")

    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        logger.warning("네이버 API 키가 설정되지 않음, Mock 데이터 사용")
        return None

    # Rate Limit 준수: 초당 10건 제한
    _naver_rate_limiter.wait_if_needed()

    url = "https://openapi.naver.com/v1/search/shop.json"
    logger.info(f"[DEBUG] API 호출 시도: {url} (검색어: {product_name})")
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "User-Agent": "Mozilla/5.0 (compatible; CommerceMarketingAI/1.0)"  # 이용약관 권장
    }
    params = {
        "query": product_name,
        "display": 5,  # 상위 5개 검색
        "sort": "sim"  # 유사도순
    }

    try:
        logger.info(f"[DEBUG] 요청 파라미터: {params}")
        response = requests.get(url, headers=headers, params=params, timeout=10)  # Timeout 10초로 증가
        logger.info(f"[DEBUG] 응답 상태 코드: {response.status_code}")

        # 응답 본문 일부 로그 (디버깅용)
        logger.info(f"[DEBUG] 응답 본문 (처음 200자): {response.text[:200]}")

        response.raise_for_status()

        data = response.json()
        items = data.get("items", [])

        if not items:
            logger.warning(f"네이버 쇼핑 API: '{product_name}' 검색 결과 없음")
            logger.info(f"[DEBUG] 전체 응답: {data}")
            return None

        # 첫 번째 검색 결과 사용
        item = items[0]

        # HTML 태그 제거
        title = re.sub(r'<[^>]+>', '', item.get("title", product_name))

        # 가격 파싱 (lprice: 최저가)
        price = int(item.get("lprice", "0"))

        product_data = {
            "name": title,
            "brand": item.get("brand", "Unknown"),
            "price": price,
            "mall": [item.get("mallName", "온라인몰")],
            "category": item.get("category1", "일반"),
            "reviews": {
                "count": 0,  # API에서 제공 안함
                "rating": 0.0  # API에서 제공 안함
            },
            "source": {
                "provider": "네이버 쇼핑 API",
                "url": item.get("link", ""),
                "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "reliability": "official_api"
            }
        }

        logger.info(f"  [API] {product_name} → {price:,}원 (네이버 쇼핑)")
        return product_data

    except requests.HTTPError as e:
        status_code = e.response.status_code if e.response else 0

        if status_code == 429:
            logger.error(f"[Rate Limit 초과] 네이버 API 호출 제한 초과 (429)")
            logger.error("조치: Rate Limiter 설정 확인 필요 (현재: 초당 10건)")
        elif status_code == 403:
            logger.error(f"[접근 금지] 네이버 쇼핑 접근 차단 (403)")
            logger.error("원인: 크롤링 의심 또는 이용약관 위반 가능성")
            logger.error("조치: 공식 API만 사용 중인지 확인, Rate Limit 준수 확인")
        elif status_code == 401:
            logger.error(f"[인증 실패] API 키 오류 (401)")
            logger.error("조치: CLIENT_ID/SECRET 확인 필요")
        else:
            logger.error(f"네이버 쇼핑 API HTTP 오류: {status_code} - {e}")

        return None

    except requests.RequestException as e:
        logger.error(f"네이버 쇼핑 API 네트워크 오류: {e}")
        return None

    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"네이버 쇼핑 API 응답 파싱 실패: {e}")
        return None


def classify_product_category(product_name: str) -> str:
    """
    제품명으로 카테고리 자동 분류 (Rule-based)

    Args:
        product_name: 제품명

    Returns:
        카테고리 (스마트폰/노트북/태블릿/기타)
    """
    name_lower = product_name.lower()

    # 태블릿 키워드 (더 구체적이므로 우선 체크)
    tablet_keywords = ["아이패드", "ipad", "갤럭시탭", "galaxy tab", "탭", "tab", "태블릿", "tablet"]
    if any(kw in name_lower for kw in tablet_keywords):
        return "태블릿"

    # 스마트폰 키워드
    smartphone_keywords = ["아이폰", "iphone", "갤럭시", "galaxy", "샤오미", "xiaomi", "폰", "phone"]
    if any(kw in name_lower for kw in smartphone_keywords):
        return "스마트폰"

    # 노트북 키워드
    laptop_keywords = ["맥북", "macbook", "그램", "gram", "노트북", "laptop", "프레스티지"]
    if any(kw in name_lower for kw in laptop_keywords):
        return "노트북"

    return "기타"


def calculate_benchmark_scores(
    products: List[Dict[str, Any]],
    category: str
) -> Dict[str, Any]:
    """
    제품들의 벤치마크 점수 계산 (0-100점)

    Args:
        products: 제품 데이터 리스트
        category: 제품 카테고리

    Returns:
        {
            "labels": ["가격 경쟁력", "브랜드 파워", ...],
            "datasets": [
                {"label": "제품1", "data": [75, 90, ...]},
                ...
            ],
            "scores": {
                "제품1": {"price_score": 75, "brand_score": 90, ...},
                ...
            }
        }
    """
    if not products:
        return {"labels": [], "datasets": [], "scores": {}}

    # 벤치마크 템플릿 가져오기
    template = BENCHMARK_TEMPLATES.get(category, BENCHMARK_TEMPLATES["기타"])
    labels = [metric["name"] for metric in template["metrics"]]

    # 브랜드별 가중치 (높을수록 좋음)
    brand_weights = {
        "Apple": 95,
        "Samsung": 90,
        "삼성": 90,
        "삼성전자": 90,
        "LG": 85,
        "Xiaomi": 75,
        "샤오미": 75,
        "Oppo": 70,
        "Vivo": 70,
        "Unknown": 50
    }

    # 가격 수집 (정규화용)
    prices = [p["price"] for p in products if p["price"] > 0]
    min_price = min(prices) if prices else 1

    scores = {}
    datasets = []

    for product in products:
        product_name = product["name"]

        # 1. 가격 경쟁력 (낮을수록 좋음 → 역수)
        if product["price"] > 0:
            price_score = round((min_price / product["price"]) * 100, 1)
        else:
            price_score = 0.0

        # 2. 브랜드 파워
        brand = product.get("brand", "Unknown")
        brand_score = brand_weights.get(brand, 50)

        # 3. 종합 점수 (검증된 지표만 사용: 가격, 브랜드)
        # 주의: 리뷰/평점 데이터는 네이버 API에서 제공하지 않아 제외
        verified_scores = [price_score, brand_score]
        total_score = round(sum(verified_scores) / len(verified_scores), 1) if verified_scores else 0.0

        # 점수 저장
        product_scores = {
            "price_score": price_score,
            "brand_score": brand_score,
            "total_score": total_score
        }
        scores[product_name] = product_scores

        # Chart.js 데이터셋 생성
        dataset = {
            "label": product_name,
            "data": [
                price_score,
                brand_score,
                total_score
            ]
        }
        datasets.append(dataset)

    return {
        "labels": labels,
        "datasets": datasets,
        "scores": scores
    }


# StatCounter CSV 캐시 (24시간 TTL)
_statcounter_cache = {
    "data": None,
    "timestamp": 0,
    "ttl": 86400  # 24시간 (초 단위)
}


def fetch_statcounter_csv_market_share(
    region: str = "KR",
    category: str = "mobile",
    stat_type: str = "vendor"
) -> Optional[Dict[str, float]]:
    """
    StatCounter GlobalStats에서 CSV 데이터 다운로드

    공식 CSV 다운로드 기능을 사용하여 시장점유율 데이터를 가져옵니다.

    라이선스 준수:
    - 출처: StatCounter GlobalStats (https://gs.statcounter.com)
    - 라이선스: CC BY-SA 3.0 (https://creativecommons.org/licenses/by-sa/3.0/)
    - 조건: 출처 명시 및 링크 제공

    Args:
        region: ISO 국가 코드 (KR=한국, US=미국, ww=전세계)
        category: 기기 카테고리 (mobile, desktop, tablet)
        stat_type: 통계 타입 (vendor=제조사, browser, os 등)

    Returns:
        시장점유율 딕셔너리 (예: {"Samsung": 66.76, "Apple": 22.52, "Xiaomi": 0.8})
        실패 시 None 반환

    Examples:
        >>> data = fetch_statcounter_csv_market_share()
        >>> print(data)
        {'Samsung': 66.76, 'Apple': 22.52, 'Xiaomi': 0.8, 'Oppo': 1.2, ...}
    """
    # 1. 캐시 확인 (24시간 이내 데이터가 있으면 재사용)
    current_time = time.time()
    if (_statcounter_cache["data"] is not None and
        current_time - _statcounter_cache["timestamp"] < _statcounter_cache["ttl"]):
        remaining_time = _statcounter_cache["ttl"] - (current_time - _statcounter_cache["timestamp"])
        logger.info(f"[StatCounter CSV] 캐시 사용 (남은 시간: {remaining_time:.0f}초)")
        return _statcounter_cache["data"]

    # 2. URL 파라미터 생성 (전월 데이터 - 당월은 아직 집계 안 됨)
    now = datetime.now()
    # 전월 계산
    if now.month == 1:
        target_month = 12
        target_year = now.year - 1
    else:
        target_month = now.month - 1
        target_year = now.year

    params = {
        "device_hidden": category,
        "statType_hidden": stat_type,
        "region_hidden": region,
        "granularity": "monthly",
        "fromMonth": str(target_month),
        "fromYear": str(target_year),
        "toMonth": str(target_month),
        "toYear": str(target_year),
        "csv": "1"  # CSV 포맷 요청
    }

    # 3. CSV 다운로드
    url = "https://gs.statcounter.com/chart.php"

    try:
        logger.info(f"[StatCounter CSV] 다운로드 시작: {region} {category} {stat_type}")

        response = requests.get(
            url,
            params=params,
            timeout=30,
            headers={
                'User-Agent': 'CompetitorAnalysisBot/2.0 (Educational Project; CC BY-SA 3.0 Compliant)'
            }
        )
        response.raise_for_status()

        # 4. CSV 파싱 (pandas 사용)
        df = pd.read_csv(StringIO(response.text))

        # 5. 데이터 검증
        if df.empty:
            logger.warning("[StatCounter CSV] 빈 데이터 반환")
            return None

        # 6. 최신 월의 데이터 추출 (0이 아닌 값이 있는 마지막 행)
        # CSV 끝에 미래 월 데이터 (모두 0)가 있을 수 있으므로 역순으로 검색
        latest_row = None
        for idx in range(len(df) - 1, -1, -1):
            row = df.iloc[idx]
            # Date 이외의 컬럼에 0이 아닌 값이 있는지 확인
            has_non_zero = False
            for col in df.columns:
                if col not in ["Date", "Unnamed: 0"]:
                    try:
                        value = float(row[col])
                        if value > 0:
                            has_non_zero = True
                            break
                    except (ValueError, TypeError):
                        continue

            if has_non_zero:
                latest_row = row
                logger.info(f"[StatCounter CSV] 유효 데이터 발견: {row['Date']}")
                break

        if latest_row is None:
            logger.warning("[StatCounter CSV] 유효한 데이터 행 없음")
            return None

        # 7. 딕셔너리로 변환 (Date 컬럼 제외)
        market_shares = {}
        for col in df.columns:
            if col not in ["Date", "Unnamed: 0"]:  # 날짜 컬럼과 인덱스 컬럼 제외
                try:
                    value = float(latest_row[col])
                    market_shares[col] = value
                except (ValueError, TypeError) as e:
                    logger.warning(f"[StatCounter CSV] 컬럼 '{col}' 파싱 실패: {e}")
                    continue

        # 8. 결과 검증
        if not market_shares:
            logger.warning("[StatCounter CSV] 유효한 데이터 없음")
            return None

        # 9. 캐시 저장
        _statcounter_cache["data"] = market_shares
        _statcounter_cache["timestamp"] = current_time

        logger.info(f"[StatCounter CSV] 다운로드 성공: {len(market_shares)}개 벤더")
        logger.debug(f"[StatCounter CSV] 데이터: {market_shares}")

        return market_shares

    except requests.RequestException as e:
        logger.error(f"[StatCounter CSV] 네트워크 에러: {e}")
        return None
    except pd.errors.ParserError as e:
        logger.error(f"[StatCounter CSV] CSV 파싱 에러: {e}")
        return None
    except Exception as e:
        logger.error(f"[StatCounter CSV] 알 수 없는 에러: {e}")
        return None


def _extract_brand_from_product_name(product_name: str) -> Optional[str]:
    """
    제품명에서 브랜드명 추출

    Args:
        product_name: 제품명 (예: "삼성 갤럭시 S24 울트라")

    Returns:
        브랜드명 (예: "Samsung") 또는 None
    """
    brand_keywords = {
        "Samsung": ["삼성", "Samsung", "갤럭시", "Galaxy"],
        "Apple": ["Apple", "아이폰", "iPhone", "애플"],
        "Xiaomi": ["샤오미", "Xiaomi", "Mi", "Redmi", "POCO"],
        "LG": ["LG", "엘지"],
        "Google": ["Google", "Pixel", "구글", "픽셀"],
        "Huawei": ["Huawei", "화웨이", "Honor"],
        "Oppo": ["Oppo", "오포"],
        "Vivo": ["Vivo", "비보"],
        "OnePlus": ["OnePlus", "원플러스", "1+"],
        "Motorola": ["Motorola", "모토로라", "Moto"],
        "Sony": ["Sony", "소니", "Xperia"],
        "Asus": ["Asus", "에이수스", "ROG"],
        "Lenovo": ["Lenovo", "레노버"]
    }

    product_upper = product_name.upper()

    for brand, keywords in brand_keywords.items():
        for keyword in keywords:
            if keyword.upper() in product_upper:
                return brand

    return None


def _find_brand_in_statcounter(
    brand: Optional[str],
    statcounter_data: Dict[str, float]
) -> Optional[float]:
    """
    StatCounter 데이터에서 브랜드 점유율 찾기

    Args:
        brand: 브랜드명 (예: "Samsung")
        statcounter_data: StatCounter 점유율 데이터

    Returns:
        점유율 (%) 또는 None
    """
    if not brand or not statcounter_data:
        return None

    # 대소문자 무시하고 매칭
    for stat_brand, share in statcounter_data.items():
        if stat_brand.lower() == brand.lower():
            return share

    return None


def _calculate_naver_adjustment(product: Dict[str, Any]) -> float:
    """
    네이버 Shopping 데이터 기반 미세 조정 계산

    Args:
        product: 제품 데이터

    Returns:
        조정 계수 (-0.5 ~ +0.5)
        - 양수: 온라인에서 인기 많음 → 점유율 상향
        - 음수: 온라인에서 인기 적음 → 점유율 하향
    """
    # 판매 채널 수 (많을수록 좋음)
    mall_count = len(product.get("mall", []))
    mall_score = min(mall_count / 4.0, 1.0)  # 4개 이상이면 1.0

    # 사용자 평가 (높을수록 좋음)
    rating = product.get("reviews", {}).get("rating", 0.0)
    rating_score = rating / 5.0 if rating > 0 else 0.5  # 평가 없으면 중립

    # 복합 점수 (0-1 범위)
    combined_score = (mall_score * 0.5) + (rating_score * 0.5)

    # -0.5 ~ +0.5 범위로 변환 (0.5를 중심으로)
    return combined_score - 0.5


def _calculate_with_statcounter_anchor(
    products: List[Dict[str, Any]],
    statcounter_data: Dict[str, float]
) -> Dict[str, float]:
    """
    StatCounter 데이터를 anchor로 사용한 점유율 계산

    Args:
        products: 제품 데이터 리스트
        statcounter_data: StatCounter 점유율 데이터

    Returns:
        시장점유율 딕셔너리 (합계 100%)
    """
    market_shares = {}

    for product in products:
        product_name = product["name"]

        # 1. 제품명에서 브랜드 추출
        brand = _extract_brand_from_product_name(product_name)

        # 2. StatCounter 데이터에서 브랜드 점유율 찾기
        statcounter_share = _find_brand_in_statcounter(brand, statcounter_data)

        if statcounter_share is not None and statcounter_share > 0:
            # StatCounter 데이터 있음: Anchor-Based Calibration
            base_share = statcounter_share

            # 네이버 데이터로 미세 조정 (±5%)
            adjustment = _calculate_naver_adjustment(product)
            adjusted_share = base_share * (1 + adjustment * 0.05)

            market_shares[product_name] = max(0.1, adjusted_share)  # 최소 0.1%

            logger.debug(f"[Anchor] {product_name}: StatCounter {base_share}% → 조정 {adjusted_share:.2f}%")
        else:
            # StatCounter 데이터 없음: 마이너 브랜드로 작은 값 할당
            market_shares[product_name] = 1.0
            logger.debug(f"[Anchor] {product_name}: 마이너 브랜드 (1.0%)")

    # 3. 정규화 (합계 100%)
    total = sum(market_shares.values())
    if total > 0:
        normalized = {k: round(v / total * 100, 1) for k, v in market_shares.items()}
    else:
        # 엣지 케이스: 모두 0이면 균등 배분
        equal_share = round(100.0 / len(products), 1)
        normalized = {k: equal_share for k in market_shares.keys()}

    logger.info(f"[Anchor] 시장점유율 계산 완료 (StatCounter 기반): {len(normalized)}개 제품")

    return normalized


def _calculate_legacy(products: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    기존 복합 지표 방식 (Fallback용)

    StatCounter 데이터가 없을 때 사용하는 온라인 쇼핑 데이터 기반 계산
    """
    # 브랜드별 가중치
    brand_weights = {
        "Apple": 95,
        "Samsung": 90,
        "삼성": 90,
        "삼성전자": 90,
        "LG": 85,
        "Xiaomi": 75,
        "샤오미": 75,
        "Unknown": 50
    }

    # 가격 정규화 (낮을수록 좋음)
    prices = [p["price"] for p in products if p["price"] > 0]
    max_price = max(prices) if prices else 1
    min_price = min(prices) if prices else 1

    market_share_scores = []

    for product in products:
        # 1. 판매 채널 다양성 (0-100점)
        mall_count = len(product.get("mall", []))
        if mall_count == 0:
            mall_count = 1  # 엣지 케이스 처리
        mall_count_weight = min(100, mall_count * 25)  # 4개 이상이면 100점

        # 2. 브랜드 인지도 (0-100점)
        brand = product.get("brand", "Unknown")
        brand_power_weight = brand_weights.get(brand, 50)

        # 3. 가격 경쟁력 (0-100점, 낮을수록 좋음)
        if product["price"] > 0 and max_price > 0:
            # 정규화: 최저가 100점, 최고가 0점
            price_competitiveness = 100 * (1 - (product["price"] - min_price) / (max_price - min_price))
        else:
            price_competitiveness = 0.0

        # 4. 카테고리 내 포지션 (리뷰 기반, 0-100점)
        review_count = product.get("reviews", {}).get("count", 0)
        rating = product.get("reviews", {}).get("rating", 0.0)

        # 리뷰 점수: 개수와 평점 종합
        category_position = min(100, (review_count / 10) + (rating * 10))

        # 5. 복합 지표 계산 (가중 평균)
        market_share_score = (
            mall_count_weight * 0.3 +      # 판매 채널 30%
            brand_power_weight * 0.4 +      # 브랜드 파워 40%
            price_competitiveness * 0.2 +   # 가격 경쟁력 20%
            category_position * 0.1         # 카테고리 포지션 10%
        )

        market_share_scores.append({
            "name": product["name"],
            "score": market_share_score
        })

    # 총합 계산
    total_score = sum(item["score"] for item in market_share_scores)

    # 엣지 케이스: 모든 점수가 0인 경우 균등 배분
    if total_score == 0:
        equal_share = round(100.0 / len(products), 1)
        return {item["name"]: equal_share for item in market_share_scores}

    # 정규화: 총합 100% 맞추기
    market_shares = {}
    for item in market_share_scores:
        share_percentage = round((item["score"] / total_score) * 100, 1)
        market_shares[item["name"]] = share_percentage

    # 반올림 오차 보정 (총합을 정확히 100.0%로)
    total_shares = sum(market_shares.values())
    if total_shares != 100.0:
        # 첫 번째 제품에 오차 보정
        first_product = market_share_scores[0]["name"]
        market_shares[first_product] = round(market_shares[first_product] + (100.0 - total_shares), 1)

    logger.info(f"[Legacy] 시장점유율 계산 완료 (온라인 쇼핑 기반): {len(market_shares)}개 제품")
    return market_shares


def calculate_market_shares(
    products: List[Dict[str, Any]],
    category: str
) -> Dict[str, float]:
    """
    제품들의 시장점유율 계산

    StatCounter GlobalStats 데이터를 anchor로 사용하여 현실적인 점유율 계산.
    StatCounter 데이터가 없으면 기존 네이버 Shopping 기반 복합 지표로 Fallback.

    Args:
        products: 제품 데이터 리스트
        category: 제품 카테고리 (스마트폰, 노트북 등)

    Returns:
        {"제품명": 점유율(%), ...} 딕셔너리 (소수점 1자리, 합계 100%)
    """
    if not products:
        return {}

    # 제품 1개인 경우: 100% 반환
    if len(products) == 1:
        return {products[0]["name"]: 100.0}

    # StatCounter 데이터 가져오기 (한국 모바일 시장)
    statcounter_data = fetch_statcounter_csv_market_share(region="KR", category="mobile")

    if statcounter_data:
        # Anchor-Based Calibration 사용
        logger.info("[시장점유율] StatCounter 데이터 사용 (현실 시장 반영)")
        return _calculate_with_statcounter_anchor(products, statcounter_data)
    else:
        # Fallback: 기존 복합 지표 방식
        logger.warning("[시장점유율] StatCounter 데이터 없음, 기존 방식 사용 (온라인 쇼핑 기반)")
        return _calculate_legacy(products)


def analyze_market_positioning_with_llm(
    products: List[Dict],
    market_shares: Dict[str, float],
    category: str
) -> Dict[str, Any]:
    """
    LLM을 사용하여 시장 포지셔닝 분석 수행

    제공된 제품 데이터와 점유율 정보를 바탕으로 시장 구도를 질적으로 분석합니다.
    - 시장 리더, 도전자, 틈새 플레이어 식별
    - 가격대별 경쟁 구도 분석
    - 브랜드 전략 차이점 도출

    Args:
        products: 제품 정보 리스트 (이름, 가격, 브랜드 등 포함)
        market_shares: 제품별 시장 점유율 딕셔너리 {"제품명": 점유율(%), ...}
        category: 제품 카테고리명

    Returns:
        시장 포지셔닝 분석 결과 딕셔너리:
        {
            "market_leader": {"product": "...", "share": ..., "analysis": "..."},
            "challengers": [{"product": "...", "share": ..., "analysis": "..."}, ...],
            "niche_players": [...],
            "price_segments": {
                "premium": ["제품1", ...],
                "mid_range": [...],
                "budget": [...]
            },
            "strategic_insights": "전체 시장 구도 분석..."
        }

    엣지 케이스:
        - 제품 1개: "독점 시장" 분석 반환
        - LLM 응답 파싱 실패: {"strategic_insights": "간단한 텍스트 분석"} 반환
    """
    # 엣지 케이스: 제품이 1개뿐인 경우 독점 시장 분석
    if len(products) <= 1:
        product_name = products[0].get("name", "Unknown") if products else "Unknown"
        return {
            "market_leader": {
                "product": product_name,
                "share": 100.0,
                "analysis": "독점 시장입니다. 경쟁사가 없거나 데이터가 부족합니다."
            },
            "challengers": [],
            "niche_players": [],
            "price_segments": {
                "premium": [],
                "mid_range": [product_name] if products else [],
                "budget": []
            },
            "strategic_insights": "현재 시장에서 유일한 제품이거나 경쟁 데이터가 부족합니다."
        }

    # 제품 데이터를 텍스트로 포맷팅 (LLM 프롬프트용)
    products_text = []
    for prod in products:
        name = prod.get("name", "Unknown")
        price = prod.get("price", 0)
        brand = prod.get("brand", "Unknown")
        share = market_shares.get(name, 0.0)
        products_text.append(
            f"- 제품명: {name}\n"
            f"  브랜드: {brand}\n"
            f"  가격: {price:,}원\n"
            f"  시장 점유율: {share:.1f}%"
        )
    products_str = "\n\n".join(products_text)

    # LLM 프롬프트 구성
    system_prompt = """
당신은 시장 분석 전문가입니다.
제공된 제품 데이터와 점유율 정보를 바탕으로 시장 포지셔닝을 분석하세요.

분석 항목:
1. 시장 리더 (가장 높은 점유율)
2. 도전자들 (2-3위)
3. 틈새 시장 플레이어 (나머지)
4. 가격대별 경쟁 구도
5. 브랜드 전략 차이점

JSON 형식으로 응답:
{
    "market_leader": {
        "product": "제품명",
        "share": 45.3,
        "analysis": "시장 리더 분석..."
    },
    "challengers": [{"product": "...", "share": ..., "analysis": "..."}],
    "niche_players": [{"product": "...", "share": ..., "analysis": "..."}],
    "price_segments": {
        "premium": ["제품1", ...],
        "mid_range": [...],
        "budget": [...]
    },
    "strategic_insights": "전체 시장 구도 분석..."
}
"""

    user_prompt = f"""
제품 카테고리: {category}

제품별 데이터:
{products_str}

위 형식으로 JSON 응답하세요.
"""

    # LLM 호출
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        llm_result = call_llm_with_context(messages=messages)

        if not llm_result.get("success"):
            raise ValueError(f"LLM 호출 실패: {llm_result.get('error', 'Unknown error')}")

        llm_response = llm_result.get("reply_text", "")

        # JSON 파싱 (정규식으로 JSON 블록 추출)
        import re
        import json

        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if json_match:
            positioning_data = json.loads(json_match.group(0))

            # 필수 필드 검증
            required_fields = ["market_leader", "challengers", "niche_players",
                             "price_segments", "strategic_insights"]
            if all(field in positioning_data for field in required_fields):
                return positioning_data
            else:
                raise ValueError("LLM 응답에 필수 필드가 누락되었습니다.")
        else:
            raise ValueError("LLM 응답에서 JSON을 찾을 수 없습니다.")

    except Exception as e:
        # Fallback: 간단한 텍스트 분석
        logger.warning(f"시장 포지셔닝 분석 실패: {e}")

        # 점유율 기준 정렬
        sorted_products = sorted(
            [(name, share) for name, share in market_shares.items()],
            key=lambda x: x[1],
            reverse=True
        )

        fallback_text = f"{category} 시장 분석 (간략):\n"
        if sorted_products:
            fallback_text += f"- 시장 리더: {sorted_products[0][0]} ({sorted_products[0][1]:.1f}%)\n"
            if len(sorted_products) > 1:
                fallback_text += f"- 주요 경쟁자: {', '.join([p[0] for p in sorted_products[1:3]])}\n"

        return {
            "strategic_insights": fallback_text
        }


def fetch_product_info_from_web_search(product_name: str, category: str) -> Optional[Dict[str, Any]]:
    """
    Google Custom Search를 사용하여 제품 정보 수집

    Args:
        product_name: 제품명
        category: 제품 카테고리

    Returns:
        제품 데이터 딕셔너리 또는 None (실패 시)
    """
    logger.info(f"Google Search로 제품 정보 수집 시도: {product_name}")

    try:
        # 가격 정보 검색
        search_query = f"{product_name} 가격 스펙"
        search_results = search_web(search_query, num_results=3)

        if not search_results:
            logger.warning(f"  ✗ {product_name}: 검색 결과 없음")
            return None

        # 검색 결과에서 제품 정보 추출 (snippet 분석)
        combined_text = "\n".join([result.get('snippet', '') for result in search_results[:3]])

        # LLM을 사용하여 텍스트에서 제품 정보 추출
        system_prompt = """
당신은 제품 정보 추출 전문가입니다.
검색 결과 텍스트에서 제품 가격과 브랜드를 추출하세요.

JSON 형식으로만 응답:
{
    "brand": "브랜드명",
    "price": 가격(숫자만),
    "found": true/false
}

예시:
- 입력: "삼성 갤럭시 S24 최저가 1,200,000원..."
- 출력: {"brand": "Samsung", "price": 1200000, "found": true}
"""

        user_prompt = f"""제품명: {product_name}
카테고리: {category}

검색 결과:
{combined_text}

위 텍스트에서 제품 정보를 추출하세요."""

        llm_response = call_llm_with_context(messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])

        if not llm_response.get("success"):
            logger.warning(f"  ✗ {product_name}: LLM 호출 실패")
            return None

        # JSON 파싱
        reply_text = llm_response.get("reply_text", "")
        json_match = re.search(r'\{.*\}', reply_text, re.DOTALL)
        if json_match:
            extracted_info = json.loads(json_match.group(0))

            if extracted_info.get("found"):
                product_data = {
                    "name": product_name,
                    "brand": extracted_info.get("brand", "Unknown"),
                    "price": extracted_info.get("price", 0),
                    "mall": ["온라인"],
                    "category": category,
                    "reviews": {
                        "count": 0,
                        "rating": 0.0
                    },
                    "source": {
                        "provider": "Google Search",
                        "url": search_results[0].get('url', ''),
                        "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "reliability": "web_search"
                    }
                }
                logger.info(f"  ✓ {product_name}: Google Search 데이터 사용 ({product_data['price']:,}원)")
                return product_data

        logger.warning(f"  ✗ {product_name}: 정보 추출 실패")
        return None

    except Exception as e:
        logger.error(f"  ✗ {product_name}: Google Search 실패 ({e})")
        return None


def fetch_competitor_data(
    target_product: str,
    competitor_products: List[str],
    category: str
) -> List[Dict[str, Any]]:
    """
    경쟁사 제품 데이터 수집 (Fallback: 네이버 API → Google Search → Mock)

    Args:
        target_product: 우리 제품명
        competitor_products: 경쟁사 제품명 리스트
        category: 제품 카테고리

    Returns:
        [{"name": str, "price": int, "brand": str, "source": {...}, ...}, ...]
    """
    logger.info(f"경쟁사 데이터 수집 시작: {target_product} vs {competitor_products}")

    all_products = [target_product] + competitor_products
    results = []

    # Fallback Chain: 네이버 쇼핑 API → Google Search → Mock 데이터
    for i, product_name in enumerate(all_products):
        product_data = None

        # 1순위: 네이버 쇼핑 API
        try:
            api_data = fetch_from_naver_shopping_api(product_name)
            if api_data:
                product_data = api_data
                logger.info(f"  ✓ {product_name}: 네이버 API 데이터 사용")
        except Exception as e:
            logger.warning(f"  ✗ {product_name}: 네이버 API 호출 실패 ({e})")

        # 2순위: Google Custom Search
        if not product_data:
            try:
                search_data = fetch_product_info_from_web_search(product_name, category)
                if search_data:
                    product_data = search_data
                    logger.info(f"  ✓ {product_name}: Google Search 데이터 사용")
            except Exception as e:
                logger.warning(f"  ✗ {product_name}: Google Search 실패 ({e})")

        # 3순위: Mock 데이터 (모든 방법 실패 시)
        if not product_data:
            brand = _infer_brand(product_name)
            price_range = _get_price_range_by_category(category)
            base_price = price_range[0] + (i * 50000)

            product_data = {
                "name": product_name,
                "brand": brand,
                "price": base_price,
                "mall": ["네이버스토어", "쿠팡"] if i == 0 else ["오픈마켓", "자사몰"],
                "category": category,
                "reviews": {
                    "count": 420 - (i * 100),
                    "rating": 4.5 + (i * 0.1)
                },
                "source": {
                    "provider": "Mock 데이터",
                    "url": "",
                    "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "reliability": "mock"
                }
            }
            logger.info(f"  ℹ {product_name}: Mock 데이터 사용 ({product_data['price']:,}원)")

        results.append(product_data)

    logger.info(f"경쟁사 데이터 수집 완료: {len(results)}개 제품")
    return results


def _infer_brand(product_name: str) -> str:
    """제품명에서 브랜드 추론"""
    brands = {
        "아이폰": "Apple",
        "맥북": "Apple",
        "에어팟": "Apple",
        "갤럭시": "Samsung",
        "LG 그램": "LG",
        "다이슨": "Dyson",
        "샤오미": "Xiaomi"
    }

    for keyword, brand in brands.items():
        if keyword in product_name:
            return brand

    return "Unknown"


def _get_price_range_by_category(category: str) -> tuple:
    """카테고리별 가격 범위 반환"""
    ranges = {
        "스마트폰": (1000000, 1500000),
        "노트북": (1500000, 2500000),
        "가전": (300000, 1000000),
        "화장품": (30000, 100000),
        "패션": (50000, 300000)
    }

    return ranges.get(category, (100000, 500000))


def compare_products_with_llm(
    products_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    제품 비교 분석 (LLM)

    Args:
        products_data: 제품 데이터 리스트 (우리 + 경쟁사)

    Returns:
        {"price_compare": {...}, "trend_compare": {...}, ...}
    """
    logger.info(f"제품 비교 분석 시작: {len(products_data)}개 제품")

    if not products_data or len(products_data) < 2:
        logger.warning("비교할 제품이 부족합니다")
        return {
            "price_compare": {},
            "brand_compare": {},
            "channel_compare": {},
            "trend_compare": {}
        }

    system_prompt = """
당신은 제품 비교 분석 전문가입니다.
아래 제품 데이터를 비교 분석하세요.

비교 항목:
1. 가격 비교 (price_compare)
2. 브랜드 포지셔닝 (brand_compare)
3. 유통 채널 (channel_compare)
4. 트렌드/인기도 (trend_compare)

JSON 형식으로만 응답:
{
    "price_compare": {
        "target": 가격,
        "competitor_avg": 평균가격,
        "diff": "분석"
    },
    "brand_compare": {
        "target": "브랜드 설명",
        "competitors": "경쟁사 브랜드 설명"
    },
    "channel_compare": {
        "target": ["채널1", "채널2"],
        "competitors": ["채널1", "채널2", "채널3"]
    },
    "trend_compare": {
        "target": "트렌드 설명",
        "competitors": "경쟁사 트렌드 설명"
    }
}
"""

    user_content = f"제품 데이터:\n{json.dumps(products_data, ensure_ascii=False, indent=2)}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    response = call_llm_with_context(messages)

    if not response.get("success"):
        logger.error(f"LLM 호출 실패: {response.get('error')}")
        return {
            "price_compare": {},
            "brand_compare": {},
            "channel_compare": {},
            "trend_compare": {}
        }

    # JSON 파싱
    reply_text = response.get("reply_text", "")
    try:
        json_match = re.search(r'\{.*\}', reply_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))
            logger.info("제품 비교 분석 성공")
            return result
        else:
            logger.warning("JSON 형식을 찾을 수 없음")
            return {
                "price_compare": {},
                "brand_compare": {},
                "channel_compare": {},
                "trend_compare": {}
            }
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 실패: {e}")
        return {
            "price_compare": {},
            "brand_compare": {},
            "channel_compare": {},
            "trend_compare": {}
        }


def generate_swot_with_llm(
    comparison: Dict[str, Any],
    products_data: List[Dict[str, Any]]
) -> Dict[str, List[str]]:
    """
    SWOT 분석 생성 (LLM)

    Args:
        comparison: 제품 비교 분석 결과
        products_data: 제품 데이터 리스트

    Returns:
        {"strengths": [str*3], "weaknesses": [str*3],
         "opportunities": [str*2], "threats": [str*2]}
    """
    logger.info("SWOT 분석 생성 시작")

    if not products_data or len(products_data) < 1:
        logger.warning("제품 데이터가 부족합니다")
        return {
            "strengths": ["분석 불가"],
            "weaknesses": ["분석 불가"],
            "opportunities": ["분석 불가"],
            "threats": ["분석 불가"]
        }

    target = products_data[0]
    competitors = products_data[1:] if len(products_data) > 1 else []

    # 프롬프트 생성
    system_prompt = """
당신은 전자상거래 제품의 마케팅 전략 컨설턴트입니다.
아래에 [우리상품]과 [경쟁상품]의 데이터를 제공합니다.

위 데이터를 '근거로만' SWOT을 작성하세요.
- Strengths: 3개 (우리의 내부 강점만, 위 데이터에서 찾을 것)
- Weaknesses: 3개 (가격/트렌드/채널에서 경쟁사보다 불리한 점만)
- Opportunities: 2개 (시장/트렌드/채널 확장 근거로만)
- Threats: 2개 (경쟁사 활동이나 가격 인하 가능성으로만)
- 데이터에 없는 일반적 표현('브랜드 인지도 강화 필요')은 쓰지 말 것.

JSON 형식으로만 응답:
{
    "strengths": ["항목1", "항목2", "항목3"],
    "weaknesses": ["항목1", "항목2", "항목3"],
    "opportunities": ["항목1", "항목2"],
    "threats": ["항목1", "항목2"]
}
"""

    # 데이터 포맷팅
    competitor_info = ""
    if competitors:
        for i, comp in enumerate(competitors, 1):
            competitor_info += f"\n[경쟁상품 {i}]\n"
            competitor_info += f"- 브랜드: {comp['brand']}\n"
            competitor_info += f"- 가격: {comp['price']:,}원\n"
            competitor_info += f"- 유통채널: {', '.join(comp['mall'])}\n"
            competitor_info += f"- 리뷰: {comp['reviews']['count']}개 (평점 {comp['reviews']['rating']})\n"
            # 트렌드 데이터는 선택적 (API 데이터에는 없음)
            if 'trend' in comp and 'growth' in comp['trend']:
                competitor_info += f"- 트렌드: {comp['trend']['growth']}\n"

    # 타겟 제품 트렌드 정보 (선택적)
    target_trend = ""
    if 'trend' in target and 'growth' in target['trend']:
        target_trend = f"\n- 트렌드: {target['trend']['growth']}"

    user_content = f"""
[우리상품]
- 이름: {target['name']}
- 브랜드: {target['brand']}
- 가격: {target['price']:,}원
- 유통채널: {', '.join(target['mall'])}
- 리뷰: {target['reviews']['count']}개 (평점 {target['reviews']['rating']}){target_trend}
{competitor_info}

[비교 분석 결과]
{json.dumps(comparison, ensure_ascii=False, indent=2)}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    response = call_llm_with_context(messages)

    if not response.get("success"):
        logger.error(f"LLM 호출 실패: {response.get('error')}")
        return {
            "strengths": ["LLM 호출 실패"],
            "weaknesses": ["LLM 호출 실패"],
            "opportunities": ["LLM 호출 실패"],
            "threats": ["LLM 호출 실패"]
        }

    # JSON 파싱
    reply_text = response.get("reply_text", "")
    try:
        json_match = re.search(r'\{.*\}', reply_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(0))

            # 항목 수 검증
            if len(result.get("strengths", [])) != 3:
                logger.warning(f"Strengths 항목 수 부족: {len(result.get('strengths', []))}개")
            if len(result.get("weaknesses", [])) != 3:
                logger.warning(f"Weaknesses 항목 수 부족: {len(result.get('weaknesses', []))}개")
            if len(result.get("opportunities", [])) != 2:
                logger.warning(f"Opportunities 항목 수 부족: {len(result.get('opportunities', []))}개")
            if len(result.get("threats", [])) != 2:
                logger.warning(f"Threats 항목 수 부족: {len(result.get('threats', []))}개")

            logger.info("SWOT 분석 생성 성공")
            return result
        else:
            logger.warning("JSON 형식을 찾을 수 없음")
            return {
                "strengths": ["JSON 파싱 실패"],
                "weaknesses": ["JSON 파싱 실패"],
                "opportunities": ["JSON 파싱 실패"],
                "threats": ["JSON 파싱 실패"]
            }
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 실패: {e}")
        return {
            "strengths": ["JSON 파싱 실패"],
            "weaknesses": ["JSON 파싱 실패"],
            "opportunities": ["JSON 파싱 실패"],
            "threats": ["JSON 파싱 실패"]
        }


def generate_differentiation_strategy(
    swot: Dict[str, List[str]]
) -> str:
    """
    차별화 전략 생성 (LLM)

    Args:
        swot: SWOT 분석 결과

    Returns:
        차별화 전략 텍스트 (최소 3개 액션 아이템)
    """
    logger.info("차별화 전략 생성 시작")

    system_prompt = """
당신은 마케팅 전략 컨설턴트입니다.
SWOT 분석 결과를 기반으로 차별화 전략을 제안하세요.

전략 구조:
1. S-O 전략: 강점으로 기회 활용
2. W-O 전략: 약점 보완하여 기회 잡기
3. S-T 전략: 강점으로 위협 대응
4. W-T 전략: 약점과 위협 최소화

각 전략당 최소 1개, 총 최소 3개의 구체적 액션 아이템 제안.

일반적인 표현("브랜드 인지도 강화")보다는 구체적 액션("20~30대 여성층 타겟 인스타그램 광고 집행") 선호.
"""

    user_content = f"SWOT 분석 결과:\n{json.dumps(swot, ensure_ascii=False, indent=2)}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]

    response = call_llm_with_context(messages)

    if not response.get("success"):
        logger.error(f"LLM 호출 실패: {response.get('error')}")
        return "차별화 전략 생성 실패: LLM 호출 오류"

    strategy_text = response.get("reply_text", "")
    logger.info(f"차별화 전략 생성 성공: {len(strategy_text)} 문자")
    return strategy_text


def generate_competitor_report(
    product_info: Dict[str, Any],
    products_data: List[Dict[str, Any]],
    comparison: Dict[str, Any],
    swot: Dict[str, List[str]],
    strategy: str
) -> str:
    """
    HTML 보고서 생성

    Args:
        product_info: 제품 정보 (target, competitors, category)
        products_data: 제품 데이터 리스트
        comparison: 비교 분석 결과
        swot: SWOT 분석 결과
        strategy: 차별화 전략

    Returns:
        보고서 파일 경로
    """
    logger.info("HTML 보고서 생성 시작")

    # 보고서 템플릿
    html_template = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>경쟁사 분석 보고서 - {target_product}</title>
    <style>
        body {{
            font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
            border-left: 4px solid #4CAF50;
            padding-left: 15px;
        }}
        .metadata {{
            background-color: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .source-info {{
            background-color: #e8f5e9;
            border: 1px solid #4CAF50;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .source-info h3 {{
            margin-top: 0;
            color: #2e7d32;
        }}
        .source-item {{
            margin: 10px 0;
            padding: 10px;
            background-color: white;
            border-radius: 3px;
        }}
        .source-item .product-name {{
            font-weight: bold;
            color: #333;
        }}
        .source-item .provider {{
            color: #4CAF50;
            font-size: 0.9em;
        }}
        .source-item .reliability {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.85em;
            margin-left: 10px;
        }}
        .source-item .reliability.official {{
            background-color: #4CAF50;
            color: white;
        }}
        .source-item .reliability.mock {{
            background-color: #FF9800;
            color: white;
        }}
        .source-item .timestamp {{
            color: #888;
            font-size: 0.85em;
        }}
        .swot {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 20px 0;
        }}
        .swot-item {{
            border: 2px solid #ddd;
            padding: 20px;
            border-radius: 8px;
        }}
        .swot-item.strengths {{
            border-color: #4CAF50;
            background-color: #f1f8f4;
        }}
        .swot-item.weaknesses {{
            border-color: #f44336;
            background-color: #fef1f1;
        }}
        .swot-item.opportunities {{
            border-color: #2196F3;
            background-color: #f1f6fb;
        }}
        .swot-item.threats {{
            border-color: #FF9800;
            background-color: #fff8f1;
        }}
        .swot-item h3 {{
            margin-top: 0;
            color: #333;
        }}
        .swot-item ul {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        .swot-item li {{
            margin: 8px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .strategy {{
            background-color: #fffbf0;
            border-left: 4px solid #FF9800;
            padding: 20px;
            margin: 20px 0;
            white-space: pre-wrap;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #888;
            font-size: 0.9em;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>경쟁사 분석 보고서</h1>

        <div class="metadata">
            <p><strong>생성일시:</strong> {timestamp}</p>
            <p><strong>분석 대상:</strong> {target_product}</p>
            <p><strong>경쟁사:</strong> {competitors}</p>
            <p><strong>제품 카테고리:</strong> {category}</p>
        </div>

        <div class="source-info">
            <h3>📊 데이터 출처</h3>
            {source_info_html}
        </div>

        <h2>1. 제품 비교</h2>
        {comparison_table}

        <h2>2. 벤치마크 분석</h2>
        {benchmark_section}

        <h2>3. 시장점유율 분석</h2>
        {market_share_section}

        <h2>4. SWOT 분석</h2>
        <div class="swot">
            <div class="swot-item strengths">
                <h3>강점 (Strengths)</h3>
                <ul>{strengths_html}</ul>
            </div>
            <div class="swot-item weaknesses">
                <h3>약점 (Weaknesses)</h3>
                <ul>{weaknesses_html}</ul>
            </div>
            <div class="swot-item opportunities">
                <h3>기회 (Opportunities)</h3>
                <ul>{opportunities_html}</ul>
            </div>
            <div class="swot-item threats">
                <h3>위협 (Threats)</h3>
                <ul>{threats_html}</ul>
            </div>
        </div>

        <h2>5. 차별화 전략</h2>
        <div class="strategy">{strategy}</div>

        <div class="footer">
            <p>본 보고서는 AI 기반 분석 결과이며 참고용으로만 사용하시기 바랍니다.</p>
            <p>커머스 마케팅 AI 에이전트 - 경쟁사 분석</p>
        </div>
    </div>
</body>
</html>
"""

    # 데이터 포맷팅
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target_product = product_info.get("target", "알 수 없음")
    competitors = ", ".join(product_info.get("competitors", [])) or "없음"
    category = product_info.get("category", "일반")

    # 비교 테이블 생성
    comparison_table = "<table><thead><tr><th>제품명</th><th>브랜드</th><th>가격</th><th>유통채널</th><th>리뷰</th></tr></thead><tbody>"
    for product in products_data:
        comparison_table += f"""
        <tr>
            <td>{product['name']}</td>
            <td>{product['brand']}</td>
            <td>{product['price']:,}원</td>
            <td>{', '.join(product['mall'])}</td>
            <td>{product['reviews']['count']}개 ({product['reviews']['rating']}점)</td>
        </tr>
        """
    comparison_table += "</tbody></table>"

    # 벤치마크 분석 생성
    benchmark_data = calculate_benchmark_scores(products_data, category)

    # Chart.js 데이터를 JSON으로 변환
    chart_data_json = json.dumps({
        "labels": benchmark_data["labels"],
        "datasets": benchmark_data["datasets"]
    }, ensure_ascii=False)

    # 벤치마크 섹션 HTML 생성
    benchmark_section = CHART_HTML_TEMPLATE.replace("{chart_data_json}", chart_data_json)

    # 벤치마크 점수 테이블 추가
    benchmark_section += """
    <h3 style="margin-top: 30px;">📋 상세 점수표</h3>
    <table>
        <thead>
            <tr>
                <th>제품명</th>
                <th>가격 경쟁력</th>
                <th>브랜드 파워</th>
                <th>종합 점수</th>
            </tr>
        </thead>
        <tbody>
    """

    for product_name, scores in benchmark_data["scores"].items():
        benchmark_section += f"""
            <tr>
                <td><strong>{product_name}</strong></td>
                <td>{scores['price_score']}점</td>
                <td>{scores['brand_score']}점</td>
                <td><strong>{scores['total_score']}점</strong></td>
            </tr>
        """

    benchmark_section += """
        </tbody>
    </table>
    <p style="color: #666; font-size: 0.9em; margin-top: 10px;">
        * 모든 점수는 0-100점 척도입니다. 종합 점수는 검증된 지표(가격, 브랜드)의 평균입니다.
    </p>
    <p style="color: #666; font-size: 0.9em; margin-top: 5px;">
        ⚠️ 참고: 네이버 쇼핑 API는 리뷰/평점 데이터를 제공하지 않습니다.
    </p>
    """

    # 온라인 반응도 섹션 추가 (참고용)
    benchmark_section += """
    <div style="background-color: #e3f2fd; padding: 20px; border-radius: 8px; border-left: 5px solid #2196f3; margin: 25px 0;">
        <h3 style="color: #1565c0; margin-top: 0;">📊 온라인 반응도 (참고)</h3>
        <p style="color: #666; font-size: 0.95em; line-height: 1.6; margin-bottom: 15px;">
            <strong>중요:</strong> 실제 리뷰 데이터가 아닌 판매 가능성과 블로그/카페 언급량을 결합한 지표입니다.<br>
            <strong>⚠️ 순위 산정에는 반영하지 않으며</strong>, 온라인 관심도 참고용으로만 제공됩니다.
        </p>
        <table>
            <thead>
                <tr>
                    <th>제품명</th>
                    <th>온라인 반응도</th>
                    <th>블로그+카페 언급</th>
                    <th>세부 지표</th>
                </tr>
            </thead>
            <tbody>
    """

    # 각 제품에 대해 온라인 반응도 계산
    for product in products_data:
        try:
            popularity = calculate_popularity_signal(product, category)

            # 레벨 색상 설정
            if popularity["level"] == "높음":
                level_color = "#4caf50"
            elif popularity["level"] == "보통":
                level_color = "#ff9800"
            else:
                level_color = "#9e9e9e"

            # 세부 지표 HTML
            factors = popularity["factors"]
            factors_html = f"""
                <small>
                    판매가능성: {factors['sales_potential']}점<br>
                    UGC점수: {factors['ugc_score']}점
                </small>
            """

            benchmark_section += f"""
                <tr>
                    <td><strong>{product['name']}</strong></td>
                    <td>
                        <span style="display: inline-block; padding: 5px 12px; background-color: {level_color};
                                     color: white; border-radius: 4px; font-weight: bold;">
                            {popularity['level']}
                        </span>
                    </td>
                    <td>{popularity['ugc_mentions']:,}건</td>
                    <td>{factors_html}</td>
                </tr>
            """
        except Exception as e:
            logger.error(f"온라인 반응도 계산 실패 ({product.get('name', 'Unknown')}): {e}")
            benchmark_section += f"""
                <tr>
                    <td><strong>{product.get('name', 'Unknown')}</strong></td>
                    <td colspan="3" style="color: #999;">계산 불가</td>
                </tr>
            """

    benchmark_section += """
            </tbody>
        </table>
        <p style="color: #666; font-size: 0.85em; margin-top: 15px; line-height: 1.6;">
            <strong>계산 방식:</strong> 판매 가능성(유통채널, 브랜드, 가격, 검색순위) 50% +
            블로그/카페 언급량 50%를 결합하여 레벨 분류 (높음 ≥75점, 보통 50-74점, 낮음 <50점)
        </p>
    </div>
    """

    # 시장점유율 분석 생성
    market_shares = calculate_market_shares(products_data, category)
    market_positioning = analyze_market_positioning_with_llm(products_data, market_shares, category)

    # 파이 차트 데이터를 JSON으로 변환
    market_data_json = json.dumps({
        "labels": list(market_shares.keys()),
        "shares": list(market_shares.values())
    }, ensure_ascii=False)

    # 시장점유율 섹션 HTML 생성
    market_share_section = PIE_CHART_HTML_TEMPLATE.replace("{market_data_json}", market_data_json)

    # 시장점유율 테이블 추가
    market_share_section += """
    <h3 style="margin-top: 30px;">📊 점유율 상세</h3>
    <table>
        <thead>
            <tr>
                <th>제품명</th>
                <th>시장 점유율</th>
                <th>순위</th>
            </tr>
        </thead>
        <tbody>
    """

    # 점유율 기준 정렬
    sorted_shares = sorted(market_shares.items(), key=lambda x: x[1], reverse=True)
    for rank, (product_name, share) in enumerate(sorted_shares, 1):
        rank_emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else ""
        market_share_section += f"""
            <tr>
                <td><strong>{product_name}</strong></td>
                <td><strong>{share:.1f}%</strong></td>
                <td>{rank_emoji} {rank}위</td>
            </tr>
        """

    market_share_section += """
        </tbody>
    </table>

    <!-- StatCounter 출처 및 라이선스 -->
    <div style="background-color: #e8f5e9; padding: 20px; border-radius: 8px; border-left: 5px solid #4caf50; margin: 25px 0;">
        <h4 style="color: #2e7d32; margin-top: 0;">📊 데이터 출처</h4>
        <p style="color: #666; line-height: 1.8; margin-bottom: 10px;">
            시장점유율 데이터는 <strong><a href="https://gs.statcounter.com" target="_blank" style="color: #2e7d32;">StatCounter GlobalStats</a></strong>의
            실제 웹 트래픽 데이터를 기반으로 계산되었습니다.
        </p>
        <p style="color: #666; font-size: 0.9em; margin-bottom: 0;">
            <strong>라이선스:</strong> <a href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank" style="color: #2e7d32;">CC BY-SA 3.0</a><br>
            <strong>데이터 범위:</strong> 한국 모바일 시장 (전월 기준)<br>
            <strong>방법론:</strong> StatCounter 웹 트래픽 데이터 (95%) + Naver Shopping 트렌드 (5% 조정)
        </p>
    </div>

    <!-- 데이터 해석 주의사항 -->
    <div style="background-color: #fff3e0; padding: 20px; border-radius: 8px; border-left: 5px solid #ff9800; margin: 25px 0;">
        <h4 style="color: #e65100; margin-top: 0; display: flex; align-items: center;">
            <span style="font-size: 1.3em; margin-right: 8px;">⚠️</span>
            데이터 해석 주의사항
        </h4>
        <ul style="color: #666; line-height: 1.8; margin-bottom: 0; padding-left: 20px;">
            <li><strong>웹 트래픽 데이터 기반</strong> 추정치로, StatCounter GlobalStats 및 Naver Shopping 데이터를 활용합니다.</li>
            <li>실제 판매량 통계가 아닌 <strong>온라인 활동 기반 추정</strong>이므로 실제 시장점유율과 차이가 있을 수 있습니다.</li>
            <li>오프라인 중심 브랜드(예: 삼성, Apple)는 과소평가, 온라인 중심 브랜드(예: Xiaomi)는 과대평가 가능성이 있습니다.</li>
            <li><strong>🚫 리뷰/평점 데이터 제약</strong>: 네이버 쇼핑 API는 리뷰/평점을 제공하지 않습니다.
                대신 <strong>"온라인 반응도"</strong> 지표(판매 가능성 + 블로그/카페 언급량)를 제공하나,
                <strong style="color: #d32f2f;">실제 리뷰가 아니므로 순위 산정에는 반영하지 않습니다.</strong>
            </li>
            <li><strong>✅ 권장 활용</strong>: 온라인 마케팅 전략, 디지털 트렌드 분석, 온라인 경쟁 포지셔닝, 블로그/카페 관심도 파악</li>
            <li><strong>❌ 주의 활용</strong>: 투자자 보고서, 전체 시장 규모 추정, 오프라인 매장 전략, 실제 사용자 만족도 평가</li>
        </ul>
    </div>

    <p style="color: #666; font-size: 0.9em; margin-top: 15px; padding: 12px; background-color: #f5f5f5; border-radius: 5px;">
        <strong>📊 계산 방식:</strong> <strong>Anchor-Based Calibration</strong> 방식을 사용합니다.
        StatCounter GlobalStats의 실제 시장점유율(95%)을 앵커로 삼고, Naver Shopping 데이터(유통 채널, 리뷰)를 활용한 ±5% 미세 조정을 적용합니다.
        <br>
        <strong>🌐 주요 데이터 소스:</strong>
        <a href="https://gs.statcounter.com" target="_blank" style="color: #4caf50;">StatCounter GlobalStats</a> (웹 트래픽) +
        Naver Shopping API (온라인 쇼핑 트렌드)
    </p>
    """

    # LLM 시장 포지셔닝 분석 추가
    if "strategic_insights" in market_positioning:
        market_share_section += f"""
    <h3 style="margin-top: 30px;">🎯 시장 포지셔닝 분석</h3>
    <div style="background-color: #f9f9f9; padding: 20px; border-radius: 5px; border-left: 4px solid #4CAF50;">
        <p style="white-space: pre-line;">{market_positioning["strategic_insights"]}</p>
    </div>
    """

        # 상세 분석이 있는 경우 추가 정보 표시
        if "market_leader" in market_positioning:
            leader = market_positioning["market_leader"]
            market_share_section += f"""
    <h4 style="margin-top: 20px;">📈 시장 리더</h4>
    <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px;">
        <p><strong>{leader.get("product", "")}</strong> ({leader.get("share", 0):.1f}%)</p>
        <p style="color: #666;">{leader.get("analysis", "")}</p>
    </div>
    """

        if "challengers" in market_positioning and market_positioning["challengers"]:
            market_share_section += """
    <h4 style="margin-top: 20px;">⚔️ 주요 도전자</h4>
    """
            for challenger in market_positioning["challengers"]:
                market_share_section += f"""
    <div style="background-color: #fff3e0; padding: 15px; border-radius: 5px; margin-bottom: 10px;">
        <p><strong>{challenger.get("product", "")}</strong> ({challenger.get("share", 0):.1f}%)</p>
        <p style="color: #666;">{challenger.get("analysis", "")}</p>
    </div>
    """

    # SWOT HTML 생성
    strengths_html = "\n".join([f"<li>{s}</li>" for s in swot.get("strengths", [])])
    weaknesses_html = "\n".join([f"<li>{w}</li>" for w in swot.get("weaknesses", [])])
    opportunities_html = "\n".join([f"<li>{o}</li>" for o in swot.get("opportunities", [])])
    threats_html = "\n".join([f"<li>{t}</li>" for t in swot.get("threats", [])])

    # 데이터 출처 HTML 생성
    source_info_html = ""
    for product in products_data:
        source = product.get("source", {})
        provider = source.get("provider", "알 수 없음")
        url = source.get("url", "")
        crawled_at = source.get("crawled_at", "")
        reliability = source.get("reliability", "unknown")

        # 신뢰도 표시
        reliability_class = "official" if reliability == "official_api" else "mock"
        reliability_text = "공식 API" if reliability == "official_api" else "모의 데이터"

        source_info_html += f"""
        <div class="source-item">
            <div class="product-name">{product['name']}</div>
            <div class="provider">출처: {provider} <span class="reliability {reliability_class}">{reliability_text}</span></div>
            {f'<div style="font-size: 0.85em; color: #666;">URL: <a href="{url}" target="_blank">{url[:80]}...</a></div>' if url else ''}
            <div class="timestamp">수집 시간: {crawled_at}</div>
        </div>
        """

    # HTML 렌더링
    html_content = html_template.format(
        target_product=target_product,
        timestamp=timestamp,
        competitors=competitors,
        category=category,
        source_info_html=source_info_html,
        comparison_table=comparison_table,
        benchmark_section=benchmark_section,
        market_share_section=market_share_section,
        strengths_html=strengths_html,
        weaknesses_html=weaknesses_html,
        opportunities_html=opportunities_html,
        threats_html=threats_html,
        strategy=strategy
    )

    # 파일 저장 (reports 디렉토리 사용 - segment_agent 패턴 준수)
    filename = f"competitor_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    output_dir = "reports"
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"HTML 보고서 생성 완료: {filepath}")
    return filepath
