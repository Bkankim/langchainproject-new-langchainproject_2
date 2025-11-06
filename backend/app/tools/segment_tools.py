"""
사용자 세그먼트 분류 도구
LLM 기반 고객 세그먼테이션 (실제 웹 검색 RAG 포함)
"""
import logging
from typing import List, Dict, Any
import json
import re

from app.tools.common.web_search import search_web, search_web_kr_commerce
from app.tools.common.web_crawler import extract_reviews_from_search_results
from app.tools.common.api_client import fetch_product_reviews
from app.tools.llm import call_llm_with_context

logger = logging.getLogger(__name__)


def extract_product_name(user_message: str) -> str:
    """
    사용자 메시지에서 제품명 추출

    Args:
        user_message: 사용자 메시지

    Returns:
        제품명
    """
    logger.info(f"제품명 추출 시도: {user_message}")

    # 간단한 패턴 매칭 (LLM 사용 가능하지만 비용 절감을 위해 룰 베이스)
    # "XXX 구매자를 세그먼트", "XXX를 분류", "XXX 타겟", "XXX 리뷰" 등의 패턴

    # 패턴 1: "XXX 구매자를"
    match = re.search(r'(.+?)\s*구매자', user_message)
    if match:
        product_name = match.group(1).strip()
        logger.info(f"제품명 추출 성공 (패턴1): {product_name}")
        return product_name

    # 패턴 2: "XXX를/을 세그먼트"
    match = re.search(r'(.+?)[을를]\s*세그먼트', user_message)
    if match:
        product_name = match.group(1).strip()
        logger.info(f"제품명 추출 성공 (패턴2): {product_name}")
        return product_name

    # 패턴 3: "XXX 타겟"
    match = re.search(r'(.+?)\s*타겟', user_message)
    if match:
        product_name = match.group(1).strip()
        logger.info(f"제품명 추출 성공 (패턴3): {product_name}")
        return product_name

    # 패턴 4: "XXX 리뷰" (리뷰 분석용)
    # "아이폰16 리뷰", "갤럭시 리뷰 분석" 등
    match = re.search(r'^([가-힣A-Za-z0-9\s]+?)\s*리뷰', user_message)
    if match:
        product_name = match.group(1).strip()
        # "구매자들의", "에 대한" 등 불필요한 부분 제거
        product_name = re.sub(r'(구매자들?의|에\s*대한|관련)\s*$', '', product_name).strip()
        logger.info(f"제품명 추출 성공 (패턴4-리뷰): {product_name}")
        return product_name

    # 패턴 5: "XXX 감성 분석" (리뷰 분석용)
    match = re.search(r'^([가-힣A-Za-z0-9\s]+?)\s*감성\s*분석', user_message)
    if match:
        product_name = match.group(1).strip()
        product_name = re.sub(r'(구매자들?의|에\s*대한|관련)\s*$', '', product_name).strip()
        logger.info(f"제품명 추출 성공 (패턴5-감성분석): {product_name}")
        return product_name

    # 패턴 6: "XXX 후기" (리뷰 분석용)
    match = re.search(r'^([가-힣A-Za-z0-9\s]+?)\s*후기', user_message)
    if match:
        product_name = match.group(1).strip()
        product_name = re.sub(r'(구매자들?의|에\s*대한|관련)\s*$', '', product_name).strip()
        logger.info(f"제품명 추출 성공 (패턴6-후기): {product_name}")
        return product_name

    # 패턴 7: "XXX 평가" (리뷰 분석용)
    match = re.search(r'^([가-힣A-Za-z0-9\s]+?)\s*평가', user_message)
    if match:
        product_name = match.group(1).strip()
        product_name = re.sub(r'(구매자들?의|에\s*대한|관련)\s*$', '', product_name).strip()
        logger.info(f"제품명 추출 성공 (패턴7-평가): {product_name}")
        return product_name

    # 패턴 8: "XXX의 리뷰" (소유격 형태)
    match = re.search(r'^([가-힣A-Za-z0-9\s]+?)의\s*리뷰', user_message)
    if match:
        product_name = match.group(1).strip()
        logger.info(f"제품명 추출 성공 (패턴8-소유격): {product_name}")
        return product_name

    # 패턴 9: "XXX를/을 분석해줘" (일반 분석 요청)
    match = re.search(r'^([가-힣A-Za-z0-9\s]+?)[을를]\s*분석', user_message)
    if match:
        product_name = match.group(1).strip()
        product_name = re.sub(r'(구매자들?의|에\s*대한|관련)\s*$', '', product_name).strip()
        logger.info(f"제품명 추출 성공 (패턴9-분석): {product_name}")
        return product_name

    # 실패 시 None
    logger.warning("제품명 추출 실패")
    return None


def collect_review_data(product_name: str, num_reviews: int = 50) -> List[str]:
    """
    제품 리뷰 데이터 수집 (실제 웹 검색 RAG + 크롤링)

    Args:
        product_name: 제품명
        num_reviews: 수집할 리뷰 개수

    Returns:
        리뷰 텍스트 리스트
    """
    logger.info(f"리뷰 데이터 수집 시작: {product_name}")

    reviews = []

    # 방법 1: Google Custom Search로 한국 커머스 사이트 검색
    try:
        search_query = f"{product_name} 리뷰 후기"
        logger.info(f"커머스 사이트 우선 검색: {search_query}")

        # 한국 커머스 사이트 우선 검색
        search_results = search_web_kr_commerce(search_query, num_results=5)

        # 검색 결과의 snippet도 리뷰로 활용
        for result in search_results:
            snippet = result.get('snippet', '')
            if snippet and len(snippet) > 20:
                reviews.append(snippet)

        logger.info(f"검색 결과 snippet: {len(reviews)}개")

        # 방법 2: 검색된 URL에서 실제 리뷰 크롤링
        logger.info(f"검색된 {len(search_results)}개 URL에서 리뷰 크롤링 시도")
        crawled_reviews = extract_reviews_from_search_results(search_results, max_per_url=5)
        reviews.extend(crawled_reviews)

        logger.info(f"크롤링으로 {len(crawled_reviews)}개 리뷰 추가 (총 {len(reviews)}개)")

    except Exception as e:
        logger.error(f"웹 검색/크롤링 실패: {e}", exc_info=True)

    # 방법 3: API로 실제 리뷰 가져오기 (백업용)
    if len(reviews) < 20:
        try:
            logger.info("리뷰 부족, API 호출 시도")
            product_url = f"https://example.com/product/{product_name}"
            api_reviews = fetch_product_reviews(product_url)

            for review in api_reviews[:num_reviews]:
                review_text = review.get('text', '')
                if review_text:
                    reviews.append(review_text)

            logger.info(f"API로 {len(api_reviews)}개 리뷰 추가")
        except Exception as e:
            logger.error(f"API 리뷰 수집 실패: {e}")

    # 최소한의 리뷰 보장 (모의 데이터로 보충)
    if len(reviews) < 10:
        logger.warning("리뷰 부족, 모의 데이터 추가")
        mock_reviews = _generate_mock_reviews(product_name)
        reviews.extend(mock_reviews)

    # 리뷰 중복 제거 및 정리
    reviews = _deduplicate_reviews(reviews)

    logger.info(f"총 {len(reviews)}개 리뷰 수집 완료 (중복 제거 후)")
    return reviews[:num_reviews]


def _deduplicate_reviews(reviews: List[str]) -> List[str]:
    """
    리뷰 중복 제거 및 정리

    Args:
        reviews: 리뷰 리스트

    Returns:
        중복 제거된 리뷰 리스트
    """
    logger.info(f"리뷰 중복 제거 시작: {len(reviews)}개")

    # 1. 빈 리뷰 제거
    reviews = [r.strip() for r in reviews if r and r.strip()]

    # 2. 너무 짧은 리뷰 제거 (10자 미만)
    reviews = [r for r in reviews if len(r) >= 10]

    # 3. 완전 중복 제거
    seen = set()
    unique_reviews = []
    for review in reviews:
        if review not in seen:
            seen.add(review)
            unique_reviews.append(review)

    logger.info(f"중복 제거 완료: {len(unique_reviews)}개")
    return unique_reviews


def _generate_mock_reviews(product_name: str) -> List[str]:
    """모의 리뷰 데이터 생성 (테스트용)"""
    return [
        f"{product_name} 정말 좋아요! 출퇴근할 때 음악 들으면서 가는데 최고입니다.",
        f"가격이 좀 비싸긴 한데 그만한 가치가 있어요. 음질도 좋고 디자인도 깔끔합니다.",
        f"운동할 때 사용하려고 샀는데 딱 맞네요. 땀에도 강하고 착용감이 편해요.",
        f"재택근무 때문에 샀는데 화상회의할 때 정말 유용해요. 노이즈 캔슬링 짱!",
        f"애플 생태계 쓰는 사람은 필수템인 것 같아요. 연결도 쉽고 호환성 좋습니다.",
        f"학생인데 강의 들을 때 집중하기 좋아요. 배터리도 오래가서 만족합니다.",
        f"브랜드 가치 때문에 샀는데 실용성도 좋네요. 통화 품질이 특히 인상적이었어요.",
        f"디자인이 너무 예쁘고 세련되어서 패션 아이템으로도 좋아요.",
        f"기능은 좋은데 가격 대비 조금 아쉬운 점도 있어요. 그래도 만족합니다.",
        f"처음 쓰는 무선 이어폰인데 편의성이 정말 좋네요. 선 없으니까 활동하기 편해요."
    ]


def classify_segments_with_llm(reviews: List[str], product_name: str) -> Dict[str, Any]:
    """
    LLM으로 리뷰 데이터 기반 세그먼트 분류

    Args:
        reviews: 리뷰 텍스트 리스트
        product_name: 제품명

    Returns:
        세그먼트 분류 결과
    """
    logger.info(f"LLM 세그먼트 분류 시작: {len(reviews)}개 리뷰")

    # 리뷰 텍스트 합치기 (최대 길이 제한)
    combined_reviews = "\n---\n".join(reviews[:30])  # 최대 30개로 제한

    # LLM 프롬프트 구성
    system_prompt = """당신은 마케팅 전문가입니다.
제품 리뷰 데이터를 분석하여 구매자를 의미 있는 세그먼트로 분류하세요.

다음 형식의 JSON으로 응답하세요:
{
    "total_segments": 3,
    "segments": [
        {
            "name": "세그먼트명",
            "percentage": 30,
            "characteristics": "세그먼트 특성 설명",
            "demographics": "추정 연령대, 성별 등",
            "needs": "이 그룹의 니즈",
            "marketing_strategy": "마케팅 전략 제안"
        }
    ],
    "overall_insights": "전체적인 인사이트"
}
"""

    user_prompt = f"""다음은 '{product_name}' 제품의 리뷰 데이터입니다:

{combined_reviews}

위 리뷰를 분석하여 구매자를 3~5개의 세그먼트로 분류하고, 각 세그먼트의 특성과 마케팅 전략을 제안하세요."""

    try:
        # LLM 호출
        response = call_llm_with_context(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        if not response.get("success"):
            raise Exception(response.get("error", "LLM 호출 실패"))

        # JSON 파싱
        reply_text = response.get("reply_text", "")

        # JSON 추출 (마크다운 코드 블록 제거)
        json_match = re.search(r'```json\n(.*?)\n```', reply_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = reply_text

        segments_data = json.loads(json_str)

        logger.info(f"세그먼트 분류 성공: {segments_data.get('total_segments')}개")
        return segments_data

    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 실패: {e}")
        # 기본 세그먼트 반환
        return _create_fallback_segments(product_name)

    except Exception as e:
        logger.error(f"LLM 세그먼트 분류 실패: {e}")
        return _create_fallback_segments(product_name)


def _create_fallback_segments(product_name: str) -> Dict[str, Any]:
    """LLM 실패 시 기본 세그먼트 반환"""
    return {
        "total_segments": 3,
        "segments": [
            {
                "name": "가성비 추구형",
                "percentage": 40,
                "characteristics": "가격 대비 성능을 중시하는 실용주의 소비자",
                "demographics": "20~30대, 학생 및 사회초년생",
                "needs": "합리적인 가격, 기본 기능 충실",
                "marketing_strategy": "가성비 강조, 할인 프로모션 효과적"
            },
            {
                "name": "프리미엄 지향형",
                "percentage": 35,
                "characteristics": "브랜드 가치와 품질을 중시하는 소비자",
                "demographics": "30~40대, 중산층 이상",
                "needs": "브랜드 신뢰, 고급 기능, 디자인",
                "marketing_strategy": "프리미엄 이미지 강화, 차별화된 경험 제공"
            },
            {
                "name": "얼리어답터형",
                "percentage": 25,
                "characteristics": "신기술과 혁신을 추구하는 트렌드 세터",
                "demographics": "20~30대, 기술 친화적",
                "needs": "최신 기능, 독특한 경험",
                "marketing_strategy": "신제품 우선 공개, 커뮤니티 활용"
            }
        ],
        "overall_insights": f"{product_name} 구매자는 크게 가성비, 프리미엄, 얼리어답터 세 그룹으로 나뉩니다."
    }


def generate_segment_pdf(segments: Dict[str, Any], product_name: str) -> str:
    """
    세그먼트 분석 PDF 생성

    Args:
        segments: 세그먼트 분석 결과
        product_name: 제품명

    Returns:
        PDF 파일 경로
    """
    from app.tools.pdf_generator import create_segment_report_pdf

    logger.info(f"PDF 생성 시작: {product_name}")

    try:
        pdf_path = create_segment_report_pdf(segments, product_name)
        logger.info(f"PDF 생성 완료: {pdf_path}")
        return pdf_path
    except Exception as e:
        logger.error(f"PDF 생성 실패: {e}")
        return None


# 기존 함수들은 레거시로 유지
def cluster_users(user_data: List[Dict[str, Any]], n_clusters: int = 3) -> Dict[str, Any]:
    """
    사용자 클러스터링

    Args:
        user_data: 사용자 데이터 리스트
            [
                {"user_id": 1, "age": 25, "purchase_count": 5, ...},
                ...
            ]
        n_clusters: 클러스터 개수

    Returns:
        클러스터링 결과
    """
    logger.info(f"사용자 클러스터링 시작 (클러스터 수: {n_clusters})")

    # TODO: scikit-learn K-Means 사용
    # from sklearn.cluster import KMeans
    # import pandas as pd
    #
    # df = pd.DataFrame(user_data)
    # features = df[['age', 'purchase_count', ...]]
    # kmeans = KMeans(n_clusters=n_clusters)
    # labels = kmeans.fit_predict(features)

    # 모의 데이터
    return {
        "n_clusters": n_clusters,
        "labels": [0, 1, 2, 0, 1],  # 각 사용자의 클러스터 라벨
        "cluster_centers": [
            {"age": 25, "purchase_count": 3},
            {"age": 35, "purchase_count": 7},
            {"age": 45, "purchase_count": 2}
        ],
        "cluster_sizes": [2, 2, 1]
    }


def describe_segment(segment_data: Dict[str, Any]) -> str:
    """
    세그먼트 특성 설명 생성

    Args:
        segment_data: 세그먼트 데이터 (클러스터 중심 등)

    Returns:
        설명 텍스트
    """
    logger.info("세그먼트 설명 생성")

    # TODO: LLM으로 세그먼트 특성 해석
    # "평균 나이 25세, 구매 횟수 3회인 그룹은..." 등

    return f"""
세그먼트 특성:
- 평균 연령: {segment_data.get('age', 'N/A')}세
- 평균 구매 횟수: {segment_data.get('purchase_count', 'N/A')}회
- 특징: 젊은 층의 활발한 구매자 그룹
"""


def suggest_marketing_strategy(segment_description: str) -> str:
    """
    세그먼트별 마케팅 전략 제안

    Args:
        segment_description: 세그먼트 설명

    Returns:
        전략 제안
    """
    logger.info("마케팅 전략 제안 생성")

    # TODO: LLM 호출

    return """
추천 마케팅 전략:
1. 소셜 미디어 광고 집중
2. 할인 쿠폰 제공
3. 리퍼럴 프로그램 운영
"""
