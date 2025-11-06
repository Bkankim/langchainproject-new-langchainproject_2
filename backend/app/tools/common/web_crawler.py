"""
웹 크롤링 공통 모듈
BeautifulSoup을 사용한 웹 페이지 리뷰 추출
"""
import logging
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


def crawl_reviews_from_url(url: str, max_reviews: int = 10) -> List[str]:
    """
    URL에서 리뷰 텍스트 추출

    Args:
        url: 크롤링할 URL
        max_reviews: 최대 리뷰 개수

    Returns:
        리뷰 텍스트 리스트
    """
    logger.info(f"리뷰 크롤링 시작: {url}")

    try:
        # User-Agent 헤더 추가 (봇 차단 방지)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # 인코딩 처리
        response.encoding = response.apparent_encoding

        soup = BeautifulSoup(response.text, 'lxml')

        # 도메인별 리뷰 추출 전략
        domain = _extract_domain(url)

        if "naver.com" in domain:
            reviews = _extract_naver_reviews(soup, max_reviews)
        elif "coupang.com" in domain:
            reviews = _extract_coupang_reviews(soup, max_reviews)
        elif "11st.co.kr" in domain:
            reviews = _extract_11st_reviews(soup, max_reviews)
        else:
            # 일반적인 리뷰 추출 (휴리스틱)
            reviews = _extract_generic_reviews(soup, max_reviews)

        logger.info(f"리뷰 크롤링 완료: {len(reviews)}개")
        return reviews

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP 요청 실패: {e}")
        return []

    except Exception as e:
        logger.error(f"크롤링 실패: {e}", exc_info=True)
        return []


def _extract_domain(url: str) -> str:
    """URL에서 도메인 추출"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.netloc.lower()


def _extract_naver_reviews(soup: BeautifulSoup, max_reviews: int) -> List[str]:
    """네이버 쇼핑 리뷰 추출"""
    logger.info("네이버 쇼핑 리뷰 추출 시도")

    reviews = []

    # 네이버 쇼핑 리뷰는 동적 로딩되므로 snippet에서 추출
    # 실제로는 Selenium이 필요하지만, snippet만 사용
    review_elements = soup.select('.reviewItems_text__XrSSf, .reviewItems_review__pDEW4, div[class*="review"]')

    for elem in review_elements[:max_reviews]:
        text = elem.get_text(strip=True)
        if text and len(text) > 10:
            reviews.append(text)

    return reviews


def _extract_coupang_reviews(soup: BeautifulSoup, max_reviews: int) -> List[str]:
    """쿠팡 리뷰 추출"""
    logger.info("쿠팡 리뷰 추출 시도")

    reviews = []

    # 쿠팡 리뷰 선택자
    review_elements = soup.select('.sdp-review__article__list__review, div[class*="review-content"]')

    for elem in review_elements[:max_reviews]:
        text = elem.get_text(strip=True)
        if text and len(text) > 10:
            reviews.append(text)

    return reviews


def _extract_11st_reviews(soup: BeautifulSoup, max_reviews: int) -> List[str]:
    """11번가 리뷰 추출"""
    logger.info("11번가 리뷰 추출 시도")

    reviews = []

    review_elements = soup.select('.review_cont, div[class*="review"]')

    for elem in review_elements[:max_reviews]:
        text = elem.get_text(strip=True)
        if text and len(text) > 10:
            reviews.append(text)

    return reviews


def _extract_generic_reviews(soup: BeautifulSoup, max_reviews: int) -> List[str]:
    """
    일반적인 리뷰 추출 (휴리스틱 기반)

    "리뷰", "review", "후기" 등의 키워드가 포함된 요소 탐색
    """
    logger.info("일반 리뷰 추출 시도 (휴리스틱)")

    reviews = []

    # 1. class나 id에 리뷰 관련 키워드 포함된 요소 찾기
    review_keywords = ['review', 'comment', 'feedback', '리뷰', '후기', '평가']

    for keyword in review_keywords:
        # class 속성에 키워드 포함
        elements = soup.find_all(attrs={"class": re.compile(keyword, re.I)})
        for elem in elements:
            text = elem.get_text(strip=True)
            # 적절한 길이의 텍스트만 추출
            if 20 < len(text) < 500:
                reviews.append(text)
                if len(reviews) >= max_reviews:
                    break

        if len(reviews) >= max_reviews:
            break

    # 2. p 태그에서 긴 텍스트 추출 (리뷰일 가능성)
    if len(reviews) < max_reviews:
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if 30 < len(text) < 500:
                reviews.append(text)
                if len(reviews) >= max_reviews:
                    break

    return reviews[:max_reviews]


def extract_reviews_from_search_results(search_results: List[Dict[str, Any]], max_per_url: int = 5) -> List[str]:
    """
    검색 결과 URL들에서 리뷰 크롤링

    Args:
        search_results: search_web() 반환값
        max_per_url: URL당 최대 리뷰 개수

    Returns:
        모든 리뷰 리스트
    """
    logger.info(f"검색 결과 {len(search_results)}개 URL에서 리뷰 크롤링 시작")

    all_reviews = []

    for result in search_results:
        url = result.get("url", "")
        if not url:
            continue

        # 각 URL에서 리뷰 크롤링
        reviews = crawl_reviews_from_url(url, max_per_url)
        all_reviews.extend(reviews)

        # 충분한 리뷰를 수집했으면 중단
        if len(all_reviews) >= 30:
            break

    logger.info(f"총 {len(all_reviews)}개 리뷰 수집 완료")
    return all_reviews
