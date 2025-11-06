"""
리뷰 감성 분석 도구
감성 분류 및 토픽 추출
"""
import logging
from typing import List, Dict, Any
import json
import re
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation

from app.tools.llm import call_llm_with_context
from app.tools.pdf_generator import create_review_report_pdf

logger = logging.getLogger(__name__)


def analyze_sentiment(reviews: List[str], product_name: str) -> Dict[str, Any]:
    """
    리뷰 감성 분석

    Args:
        reviews: 리뷰 텍스트 리스트

    Returns:
        감성 분석 결과
    """
    logger.info(f"리뷰 감성 분석 시작 ({len(reviews)}개)")

    # 리뷰 텍스트 합치기 (최대 길이 제한)
    combined_reviews = "\n---\n".join(reviews[:30])  # 최대 30개로 제한

    system_prompt = """당신은 시장 분석 전문가이며, 그 중에서도 뛰어난 구매자 리뷰 감성 분석가입니다.
    주어진 제품 리뷰 데이터를 통해 구매자의 리뷰 감성을 분석하세요.
    리뷰별로 긍정, 부정, 중립으로 분류하고, 전체적인 감성 분포와 평균 점수를 계산하세요.
    또한, 각 리뷰에 대한 감성 점수(0~1)도 계산하세요.
    최종 분석 결과를 구조화된 JSON 형식으로 반환하세요.
    {
        "total_reviews": int,
        "sentiment_distribution": {
            "positive": int,
            "negative": int,
            "neutral": int
        },
        "average_score": float,
        "sentiment_by_review": [
            {
                "review": str,
                "sentiment": str,  # "positive", "negative", "neutral"
                "score": float     # 0.0 ~ 1.0
            },
            ...
        ]
        "overall_insights": str (전체적인 인사이트)
    }
    """

    user_prompt = f"""다음은 {product_name} 제품에 대한 리뷰 데이터입니다:
    
    {combined_reviews}

위 리뷰를 분석하여 감성 분포와 평균 점수를 계산하고, 각 리뷰별 감성 및 점수를 평가하세요.
"""
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

        sentiment_data = json.loads(json_str)

        logger.info(f"리뷰 감성 분석 성공: {sentiment_data.get('total_segments')}개")
        return sentiment_data

    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 실패: {e}")
        # 기본 리뷰 감성 분석 반환
        return _create_fallback_sentiment(product_name)

    except Exception as e:
        logger.error(f"LLM 리뷰 감성 분석 실패: {e}")
        return _create_fallback_sentiment(product_name)

    # 모의 데이터
    # return {
    #     "total_reviews": len(reviews),
    #     "sentiment_distribution": {
    #         "positive": 60,
    #         "negative": 20,
    #         "neutral": 20
    #     },
    #     "average_score": 4.2,
    #     "sentiment_by_review": [
    #         {"review": review[:50], "sentiment": "positive", "score": 0.85}
    #         for review in reviews[:3]
    #     ]
    #     "overall_insights": 대체로 긍정적인 반응이 많으며, 배송과 품질에 대한 만족도가 높음.
    # }


def extract_topics(reviews: List[str], num_topics: int = 5) -> List[str]:
    """
    리뷰에서 주요 토픽 추출

    Args:
        reviews: 리뷰 텍스트 리스트
        num_topics: 추출할 토픽 개수

    Returns:
        토픽 리스트
    """
    logger.info(f"토픽 추출 시작 (목표: {num_topics}개)")

    # 텍스트 벡터화
    vectorizer = CountVectorizer(stop_words='english')
    X = vectorizer.fit_transform(reviews)

    # LDA 모델 적용
    lda = LatentDirichletAllocation(n_components=num_topics, random_state=42)
    lda.fit(X)

    topics = []
    feature_names = vectorizer.get_feature_names_out()

    for topic_idx, topic in enumerate(lda.components_):
        top_features_indices = topic.argsort()[-5:][::-1]  # 상위 5개 단어
        top_features = [feature_names[i] for i in top_features_indices]
        topics = top_features.copy()

    logger.info(f"토픽 추출 성공: {topics}")
    return topics

    # 모의 데이터
    #return ["배송", "품질", "가격", "디자인", "내구성"][:num_topics]


def summarize_reviews(reviews: List[str], product_name: str) -> str:
    """
    리뷰 요약 생성

    Args:
        reviews: 리뷰 텍스트 리스트

    Returns:
        요약 텍스트
    """
    logger.info("리뷰 요약 생성")

    # 리뷰 텍스트 합치기 (최대 길이 제한)
    combined_reviews = "\n---\n".join(reviews[:30])  # 최대 30개로 제한

    system_prompt = """다음은 특정 제품에 대한 구매자 리뷰 데이터입니다.
주어진 제품 리뷰 데이터를 3~5가지 주요 포인트로 요약하세요.
간결하고 명확하게 작성하세요.
긍정적인 부분과 부정적인 부분, 전반적인 반응(긍정적/부정적)을 반드시 포함하세요.
예시 형식은 다음과 같습니다.
반드시 아래의 형식을 준수해 답변하세요.

리뷰 요약:
- 전반적으로 긍정적인 평가
- 배송 속도에 대한 칭찬 많음
- 일부 품질 문제 지적
- 가격 대비 만족도 높음
"""

    user_prompt = f"""다음은 {product_name} 제품에 대한 리뷰 데이터입니다:
    
{combined_reviews}

위 리뷰를 분석하여 주요 포인트로 요약하세요.
"""
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
        
        # 요약 텍스트 반환
        reply_text = response.get("reply_text", "")
        logger.info("리뷰 요약 생성 성공")
        return reply_text
    
    except Exception as e:
        logger.error(f"리뷰 요약 생성 실패: {e}")
        return "리뷰 요약을 생성하는 데 실패했습니다."

    # 모의 데이터
#     return """
# 리뷰 요약:
# - 전반적으로 긍정적인 평가
# - 배송 속도에 대한 칭찬 많음
# - 일부 품질 문제 지적
# - 가격 대비 만족도 높음
# """


def identify_improvement_areas(sentiment_result: Dict[str, Any]) -> List[str]:
    """
    개선 영역 식별

    Args:
        sentiment_result: 감성 분석 결과

    Returns:
        개선 영역 리스트
    """
    logger.info("개선 영역 식별")

    # 감성 분석 결과를 LLM에 전달하여 개선점 도출
    system_prompt = """당신은 고객 경험 개선 전문가입니다.
주어진 리뷰 감성 분석 결과를 바탕으로 제품 및 서비스의 개선이 필요한 영역을 도출하세요.
각 개선점은 구체적이고 실행 가능한 형태로 작성하세요.
1~5개의 주요 개선점을 제안하세요.
최종 분석 결과를 다음과 같은 JSON 형식으로 반환하세요.
{
    "improvement_areas": [
        "개선점 1",
        "개선점 2",
        ...
    ]
}

"""
    user_prompt = f"""다음은 제품 리뷰 감성 분석 결과입니다:
{json.dumps(sentiment_result, ensure_ascii=False, indent=2)}
위 결과를 분석하여 제품 및 서비스의 개선이 필요한 영역을 도출하세요.
"""
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

        improvement_data = json.loads(json_str)
        improvement_areas = improvement_data.get("improvement_areas", [])

        logger.info(f"개선 영역 식별 성공: {improvement_areas}")
        return improvement_areas
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 실패: {e}")
        return []
    
    except Exception as e:
        logger.error(f"개선 영역 식별 실패: {e}")
        return []

    # 모의 데이터
    # return [
    #     "일부 제품의 품질 관리 강화 필요",
    #     "고객 서비스 응답 속도 개선",
    #     "포장 상태 점검"
    # ]


def generate_review_report_pdf(sentiment_result: Dict[str, Any], topics: List[str], summary: str, improvements_area: List[str], product_name: str) -> str:
    """
    리뷰 분석 리포트 PDF 생성

    Args:
        sentiment_result: 감성 분석 결과
        topics: 추출된 토픽 리스트
        summary: 리뷰 요약 텍스트
        improvements_area: 개선 영역 리스트
        product_name: 제품명

    Returns:
        생성된 PDF 파일 경로
    """
    logger.info("리뷰 분석 리포트 PDF 생성")

    try:
        pdf_path = create_review_report_pdf(
            sentiment_result=sentiment_result,
            topics=topics,
            summary=summary,
            improvements_area=improvements_area,
            product_name=product_name
        )
        logger.info(f"리뷰 분석 리포트 PDF 생성 성공: {pdf_path}")
        return pdf_path
    
    except Exception as e:
        logger.error(f"리뷰 분석 리포트 PDF 생성 실패: {e}")
        return None
    
    # 모의 데이터
    # return "/path/to/generated/review_report.pdf"


def _create_fallback_sentiment(product_name: str) -> Dict[str, Any]:
    """기본 리뷰 감성 분석 반환"""
    return {
        "total_reviews": 0,
        "sentiment_distribution": {
            "positive": 0,
            "negative": 0,
            "neutral": 0
        },
        "average_score": 0.0,
        "sentiment_by_review": [],
        "overall_insights": f"{product_name}에 대한 리뷰 데이터가 충분하지 않아 감성 분석을 수행할 수 없습니다."
    }