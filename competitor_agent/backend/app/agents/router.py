"""
에이전트 라우터
사용자 메시지에서 키워드를 감지해 적절한 에이전트로 라우팅
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# 에이전트 임포트는 파일 생성 후 활성화
# from app.agents.trend_agent import run_agent as run_trend
# from app.agents.ad_copy_agent import run_agent as run_ad
from app.agents.segment_agent import run_agent as run_segment  # ✅ 활성화
# from app.agents.review_agent import run_agent as run_review
from app.agents.competitor_agent import run_agent as run_competitor  # ✅ 활성화


# 키워드 → 에이전트 매핑
AGENT_MAP = {
    "trend": {
        "keywords": ["트렌드", "유행", "인기", "검색량", "관심도", "소비"],
        "runner": None,  # run_trend로 교체
        "name": "소비 트렌드 분석",
        "description": "특정 키워드나 제품의 트렌드를 분석합니다."
    },
    "ad_copy": {
        "keywords": ["광고", "문구", "카피", "헤드라인", "슬로건", "마케팅"],
        "runner": None,  # run_ad로 교체
        "name": "광고 문구 생성",
        "description": "제품/서비스에 맞는 광고 문구를 생성합니다."
    },
    "segment": {
        "keywords": ["세그먼트", "고객분류", "타겟", "페르소나", "클러스터", "그룹"],
        "runner": None,  # run_segment로 교체
        "name": "사용자 세그먼트 분류",
        "description": "사용자 데이터를 세그먼트로 분류합니다."
    },
    "review": {
        "keywords": ["리뷰", "감성", "평가", "후기", "댓글", "의견"],
        "runner": None,  # run_review로 교체
        "name": "리뷰 감성 분석",
        "description": "제품 리뷰의 감성을 분석하고 요약합니다."
    },
    "competitor": {
        "keywords": ["경쟁사", "비교", "가격", "시장", "벤치마크", "경쟁"],
        "runner": None,  # run_competitor로 교체
        "name": "경쟁사 분석",
        "description": "경쟁 제품/서비스를 분석하고 비교합니다."
    }
}


def detect_task(user_message: str) -> Optional[str]:
    """
    사용자 메시지에서 태스크 감지

    Args:
        user_message: 사용자 메시지

    Returns:
        태스크 키 (trend, ad_copy, segment, review, competitor)
        또는 None (매칭 없음)
    """
    message_lower = user_message.lower()

    # 각 태스크의 키워드를 확인
    for task_key, config in AGENT_MAP.items():
        for keyword in config["keywords"]:
            if keyword in message_lower:
                logger.info(f"태스크 감지: {task_key} (키워드: {keyword})")
                return task_key

    logger.warning(f"태스크를 감지하지 못함: {user_message[:50]}...")
    return None


def get_available_tasks() -> str:
    """
    사용 가능한 태스크 목록 텍스트 반환

    Returns:
        태스크 목록 문자열
    """
    task_list = "🛍️ 커머스 마케팅 AI 에이전트 - 사용 가능한 태스크:\n\n"

    for task_key, config in AGENT_MAP.items():
        keywords_str = ", ".join(config["keywords"][:3])
        task_list += f"• **{config['name']}**\n"
        task_list += f"  - 설명: {config['description']}\n"
        task_list += f"  - 키워드: {keywords_str}\n\n"

    task_list += "예시:\n"
    task_list += '- "최근 반려동물 관련 트렌드 분석해줘"\n'
    task_list += '- "친환경 세제 광고 문구 만들어줘"\n'
    task_list += '- "이 제품 리뷰 감성 분석해줘"\n'

    return task_list


def route_to_agent(session_id: str, user_message: str) -> Dict[str, Any]:
    """
    메시지를 적절한 에이전트로 라우팅

    Args:
        session_id: 세션 ID
        user_message: 사용자 메시지

    Returns:
        에이전트 실행 결과
        {
            "success": bool,
            "session_id": str,
            "reply_text": str,
            "result_data": dict,  # 태스크별 결과
            "errors": list
        }
    """
    logger.info(f"라우터 시작 (세션: {session_id})")

    # 태스크 감지
    task_key = detect_task(user_message)

    # 매칭되는 태스크가 없으면 안내 메시지
    if not task_key:
        return {
            "success": False,
            "session_id": session_id,
            "reply_text": get_available_tasks(),
            "result_data": None,
            "errors": ["Unknown task"]
        }

    # 에이전트 실행
    agent_config = AGENT_MAP[task_key]
    agent_runner = agent_config["runner"]

    # 에이전트가 아직 구현되지 않은 경우
    if agent_runner is None:
        logger.warning(f"에이전트 미구현: {task_key}")
        return {
            "success": False,
            "session_id": session_id,
            "reply_text": (
                f"✋ **{agent_config['name']}** 에이전트는 현재 개발 중입니다.\n\n"
                f"이 태스크는 곧 사용 가능합니다!\n\n"
                f"다른 태스크를 시도해보시거나, 팀원이 이 에이전트를 구현 중입니다.\n\n"
                f"{get_available_tasks()}"
            ),
            "result_data": None,
            "errors": [f"Agent not implemented: {task_key}"]
        }

    # 감지된 에이전트 실행
    logger.info(f"에이전트 실행: {agent_config['name']}")
    try:
        result = agent_runner(session_id, user_message)
        logger.info(f"에이전트 완료: {task_key}")
        return result
    except Exception as e:
        logger.error(f"에이전트 실행 실패 ({task_key}): {e}", exc_info=True)
        return {
            "success": False,
            "session_id": session_id,
            "reply_text": f"에이전트 실행 중 오류가 발생했습니다: {str(e)}",
            "result_data": None,
            "errors": [str(e)]
        }


# 팀원이 에이전트 구현 후 활성화할 코드:
# AGENT_MAP["trend"]["runner"] = run_trend
# AGENT_MAP["ad_copy"]["runner"] = run_ad
AGENT_MAP["segment"]["runner"] = run_segment  # ✅ 활성화
# AGENT_MAP["review"]["runner"] = run_review
AGENT_MAP["competitor"]["runner"] = run_competitor  # ✅ 활성화
