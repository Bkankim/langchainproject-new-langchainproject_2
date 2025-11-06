"""
외부 API 클라이언트 공통 모듈
네이버쇼핑, 쿠팡 등 커머스 API 호출
"""
import logging
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)


class CommerceAPIClient:
    """커머스 API 클라이언트 베이스 클래스"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = requests.Session()

    def get(self, url: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """GET 요청"""
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"API 요청 실패: {e}")
            return {"error": str(e)}


class NaverShoppingClient(CommerceAPIClient):
    """네이버쇼핑 API 클라이언트"""

    BASE_URL = "https://openapi.naver.com/v1/search/shop.json"

    def search_products(self, query: str, display: int = 10) -> Dict[str, Any]:
        """
        상품 검색

        Args:
            query: 검색어
            display: 결과 개수

        Returns:
            검색 결과
        """
        logger.info(f"네이버쇼핑 검색: {query}")

        # TODO: 팀원이 실제 API 키 설정 및 호출 구현
        # 현재는 모의 데이터 반환

        return {
            "items": [
                {
                    "title": f"상품 {i+1}",
                    "link": f"https://shopping.naver.com/product{i+1}",
                    "image": "https://via.placeholder.com/150",
                    "lprice": str((i+1) * 10000),
                    "mallName": "샘플몰"
                }
                for i in range(display)
            ]
        }


def fetch_product_reviews(product_url: str) -> list:
    """
    상품 리뷰 가져오기 (크롤링)

    Args:
        product_url: 상품 URL

    Returns:
        리뷰 리스트
    """
    logger.info(f"리뷰 크롤링: {product_url}")

    # TODO: 팀원이 BeautifulSoup, Selenium 등으로 크롤링 구현
    # 현재는 모의 데이터 반환

    return [
        {
            "rating": 5,
            "text": "정말 좋은 제품입니다!",
            "date": "2025-10-28"
        },
        {
            "rating": 4,
            "text": "가격 대비 괜찮아요.",
            "date": "2025-10-27"
        },
        {
            "rating": 3,
            "text": "보통입니다.",
            "date": "2025-10-26"
        }
    ]
