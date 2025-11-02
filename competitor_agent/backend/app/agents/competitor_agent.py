"""
경쟁사 분석 에이전트
LLM 기반 제품 정보 추출, 경쟁사 데이터 수집, SWOT 분석, 차별화 전략 제안
"""
import logging
import os
from typing import Dict, Any, Optional, List

from app.db.session import get_db
from app.db.crud import append_message, create_session, get_session
from app.tools.competitor_tools import (
    extract_product_info,
    fetch_competitor_data,
    compare_products_with_llm,
    generate_swot_with_llm,
    generate_differentiation_strategy,
    generate_competitor_report
)

logger = logging.getLogger(__name__)


class CompetitorAgentContext:
    """경쟁사 분석 에이전트 실행 상태 추적"""

    def __init__(self, session_id: str, user_message: str):
        self.session_id = session_id
        self.user_message = user_message

        # Step 1: 제품 정보 추출 결과
        self.product_info: Optional[Dict[str, Any]] = None
        # {"target": str, "competitors": List[str], "category": str}

        # Step 2: 경쟁사 데이터 수집 결과
        self.competitor_data: Optional[List[Dict[str, Any]]] = None
        # [{"name": str, "price": int, "brand": str, ...}, ...]

        # Step 3: 제품 비교 분석 결과
        self.comparison: Optional[Dict[str, Any]] = None
        # {"price_compare": {...}, "trend_compare": {...}}

        # Step 4: SWOT 분석 결과
        self.swot: Optional[Dict[str, List[str]]] = None
        # {"strengths": [str*3], "weaknesses": [str*3], ...}

        # Step 5: 차별화 전략 결과
        self.strategy: Optional[str] = None

        # Step 6: 보고서 생성 결과
        self.report_path: Optional[str] = None

        # 에러 추적
        self.errors: List[str] = []


class CompetitorAgent:
    """경쟁사 분석 에이전트"""

    def __init__(self):
        self.name = "CompetitorAgent"

    def run(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """
        에이전트 워크플로우 실행
        1. 제품 정보 추출 (LLM)
        2. 경쟁사 데이터 수집 (API)
        3. 제품 비교 분석 (LLM)
        4. SWOT 분석 생성 (LLM)
        5. 차별화 전략 생성 (LLM)
        6. HTML 보고서 생성
        """
        logger.info(f"경쟁사 분석 시작 (세션: {session_id})")

        context = CompetitorAgentContext(session_id, user_message)

        try:
            # 세션 확인/생성
            with get_db() as db:
                if not session_id:
                    session = create_session(db)
                    context.session_id = session.id
                else:
                    session = get_session(db, session_id)
                    if not session:
                        session = create_session(db)
                        context.session_id = session.id

                append_message(db, context.session_id, "system", "--- 경쟁사 분석 시작 ---")
                append_message(db, context.session_id, "user", context.user_message)

            # Step 1: 제품 정보 추출
            logger.info("Step 1: 제품 정보 추출")
            context.product_info = extract_product_info(context.user_message)

            if not context.product_info.get("target"):
                context.errors.append("제품명을 찾을 수 없습니다.")
                reply_text = "제품명을 명확히 지정해주세요. 예: '아이폰 15와 갤럭시 S24 비교 분석해줘'"
                with get_db() as db:
                    append_message(db, context.session_id, "assistant", reply_text)
                return {
                    "success": False,
                    "session_id": context.session_id,
                    "reply_text": reply_text,
                    "result_data": None,
                    "errors": context.errors
                }

            # Step 2: 경쟁사 데이터 수집
            logger.info(f"Step 2: '{context.product_info['target']}' 경쟁사 데이터 수집")
            context.competitor_data = fetch_competitor_data(
                context.product_info["target"],
                context.product_info.get("competitors", []),
                context.product_info.get("category", "일반")
            )

            if not context.competitor_data:
                context.errors.append("경쟁사 데이터를 수집할 수 없습니다.")
                reply_text = f"'{context.product_info['target']}'에 대한 데이터를 찾을 수 없습니다."
                with get_db() as db:
                    append_message(db, context.session_id, "assistant", reply_text)
                return {
                    "success": False,
                    "session_id": context.session_id,
                    "reply_text": reply_text,
                    "result_data": None,
                    "errors": context.errors
                }

            # Step 3: 제품 비교 분석
            logger.info(f"Step 3: 제품 비교 분석 ({len(context.competitor_data)}개)")
            context.comparison = compare_products_with_llm(context.competitor_data)

            # Step 4: SWOT 분석
            logger.info("Step 4: SWOT 분석 생성")
            context.swot = generate_swot_with_llm(
                context.comparison,
                context.competitor_data
            )

            # Step 5: 차별화 전략
            logger.info("Step 5: 차별화 전략 생성")
            context.strategy = generate_differentiation_strategy(context.swot)

            # Step 6: HTML 보고서 생성
            logger.info("Step 6: HTML 보고서 생성")
            context.report_path = generate_competitor_report(
                context.product_info,
                context.competitor_data,
                context.comparison,
                context.swot,
                context.strategy
            )

            # Step 7: 최종 응답 생성
            reply_text = self._generate_final_response(context)

            with get_db() as db:
                append_message(db, context.session_id, "assistant", reply_text)

            # 보고서 파일명만 추출
            report_filename = os.path.basename(context.report_path) if context.report_path else None

            return {
                "success": True,
                "session_id": context.session_id,
                "reply_text": reply_text,
                "result_data": {
                    "product_info": context.product_info,
                    "swot": context.swot,
                    "strategy": context.strategy,
                    "competitor_count": len(context.competitor_data) - 1
                },
                "report_id": report_filename,
                "download_url": f"/report/{report_filename}" if report_filename else None,
                "errors": context.errors
            }

        except Exception as e:
            logger.error(f"경쟁사 분석 실패: {e}", exc_info=True)
            error_msg = f"경쟁사 분석 중 오류가 발생했습니다: {str(e)}"

            with get_db() as db:
                append_message(db, context.session_id, "assistant", error_msg)

            return {
                "success": False,
                "session_id": context.session_id,
                "reply_text": error_msg,
                "result_data": None,
                "errors": context.errors + [str(e)]
            }

    def _generate_final_response(self, context: CompetitorAgentContext) -> str:
        """최종 응답 생성"""
        target_product = context.product_info.get("target", "알 수 없음")
        competitors = context.product_info.get("competitors", [])
        competitor_count = len(competitors)

        response = f"**{target_product} 경쟁사 분석 완료**\n\n"

        if competitor_count > 0:
            response += f"총 {competitor_count}개 경쟁사를 비교 분석했습니다.\n"
            response += f"경쟁사: {', '.join(competitors)}\n\n"
        else:
            response += f"제품 단독 분석을 수행했습니다.\n\n"

        # SWOT 요약
        response += "**SWOT 분석 요약:**\n"
        response += f"- 강점: {len(context.swot.get('strengths', []))}개\n"
        response += f"- 약점: {len(context.swot.get('weaknesses', []))}개\n"
        response += f"- 기회: {len(context.swot.get('opportunities', []))}개\n"
        response += f"- 위협: {len(context.swot.get('threats', []))}개\n\n"

        # 차별화 전략
        if context.strategy:
            # 전략 첫 200자만 미리보기
            strategy_preview = context.strategy[:200].replace("\n", " ").strip()
            response += f"**차별화 전략:** {strategy_preview}...\n\n"

        # 보고서 다운로드 안내
        if context.report_path:
            response += "**상세 분석 보고서**가 생성되었습니다.\n"
            response += "HTML 보고서를 다운로드하여 비교 테이블과 전체 전략을 확인하세요.\n"

        response += "\n본 결과는 AI 기반 분석이며 참고용으로만 사용하세요."

        return response


agent = CompetitorAgent()


def run_agent(session_id: str, user_message: str) -> Dict[str, Any]:
    """
    라우터에서 호출하는 표준 인터페이스

    Args:
        session_id: 세션 ID
        user_message: 사용자 메시지

    Returns:
        표준 응답 형식
    """
    if not session_id:
        with get_db() as db:
            session = create_session(db)
            session_id = session.id
    return agent.run(session_id, user_message)
