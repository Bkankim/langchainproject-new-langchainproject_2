"""
웹 검색 공통 모듈
Google Custom Search JSON API를 통한 실제 웹 검색 기능
"""
import logging
from typing import List, Dict, Any, Optional
import os
import requests

logger = logging.getLogger(__name__)


def search_web(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Google Custom Search API를 사용한 웹 검색

    Args:
        query: 검색 쿼리
        num_results: 결과 개수 (최대 10)

    Returns:
        검색 결과 리스트
        [
            {
                "title": "제목",
                "url": "URL",
                "snippet": "요약",
                "displayLink": "도메인"
            },
            ...
        ]
    """
    logger.info(f"웹 검색: {query}")

    # API 키 확인
    api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

    if not api_key or not search_engine_id:
        logger.warning("Google Search API 키가 설정되지 않았습니다. 모의 데이터를 반환합니다.")
        return _get_mock_search_results(query, num_results)

    try:
        # Google Custom Search JSON API 호출
        url = "https://www.googleapis.com/customsearch/v1"

        params = {
            "key": api_key,
            "cx": search_engine_id,
            "q": query,
            "num": min(num_results, 10),  # 한 번에 최대 10개
            "hl": "ko",  # 한국어
            "gl": "kr",  # 한국 지역
        }

        logger.info(f"Google Search API 호출: query={query}, num={params['num']}")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # 검색 결과 파싱
        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "displayLink": item.get("displayLink", "")
            })

        logger.info(f"웹 검색 완료: {len(results)}개 결과")
        return results

    except requests.exceptions.RequestException as e:
        logger.error(f"Google Search API 호출 실패: {e}")
        return _get_mock_search_results(query, num_results)

    except Exception as e:
        logger.error(f"웹 검색 실패: {e}", exc_info=True)
        return _get_mock_search_results(query, num_results)


def search_web_kr_commerce(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    한국 커머스 사이트 위주 검색

    네이버 쇼핑, 쿠팡, 11번가 등의 리뷰 페이지를 우선 검색

    Args:
        query: 검색 쿼리
        num_results: 결과 개수

    Returns:
        검색 결과 리스트
    """
    logger.info(f"한국 커머스 검색: {query}")

    # 커머스 사이트 도메인 추가
    commerce_query = f"{query} (site:shopping.naver.com OR site:www.coupang.com OR site:www.11st.co.kr OR site:prod.danawa.com)"

    return search_web(commerce_query, num_results)


def search_news(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    뉴스 검색 (Google Custom Search - News 타입)

    Args:
        query: 검색 쿼리
        num_results: 결과 개수

    Returns:
        뉴스 검색 결과 리스트
    """
    logger.info(f"뉴스 검색: {query}")

    api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

    if not api_key or not search_engine_id:
        logger.warning("Google Search API 키가 설정되지 않았습니다. 모의 데이터를 반환합니다.")
        return _get_mock_news_results(query, num_results)

    try:
        url = "https://www.googleapis.com/customsearch/v1"

        params = {
            "key": api_key,
            "cx": search_engine_id,
            "q": query,
            "num": min(num_results, 10),
            "hl": "ko",
            "gl": "kr",
            "tbm": "nws",  # 뉴스 검색
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "displayLink": item.get("displayLink", ""),
                "published_date": item.get("pagemap", {}).get("metatags", [{}])[0].get("article:published_time", "")
            })

        logger.info(f"뉴스 검색 완료: {len(results)}개 결과")
        return results

    except Exception as e:
        logger.error(f"뉴스 검색 실패: {e}", exc_info=True)
        return _get_mock_news_results(query, num_results)


def _get_mock_search_results(query: str, num_results: int) -> List[Dict[str, Any]]:
    """모의 검색 결과 반환 (API 키 없을 때)"""
    logger.info(f"모의 검색 결과 반환: {query}")

    return [
        {
            "title": f"검색 결과 {i+1}: {query}",
            "url": f"https://example.com/result{i+1}",
            "snippet": f"이것은 {query}에 대한 검색 결과 {i+1}입니다. 실제 Google Search API를 사용하려면 .env에 GOOGLE_SEARCH_API_KEY와 GOOGLE_SEARCH_ENGINE_ID를 설정하세요.",
            "displayLink": "example.com"
        }
        for i in range(num_results)
    ]


def _get_mock_news_results(query: str, num_results: int) -> List[Dict[str, Any]]:
    """모의 뉴스 결과 반환 (API 키 없을 때)"""
    logger.info(f"모의 뉴스 결과 반환: {query}")

    return [
        {
            "title": f"뉴스 {i+1}: {query}",
            "url": f"https://news.example.com/article{i+1}",
            "snippet": f"{query} 관련 뉴스입니다.",
            "displayLink": "news.example.com",
            "published_date": "2025-10-29"
        }
        for i in range(num_results)
    ]
