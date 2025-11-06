"""
사용자 세그먼트 자동 분류 에이전트
LLM 기반 고객 세그먼테이션 (웹 검색 → 데이터 수집 → 분류 → PDF)
"""
import logging
from typing import Dict, Any, Optional

from app.db.session import get_db
from app.db.crud import append_message, create_session, get_session, save_task_result
from app.tools.segment_tools import (
    extract_product_name,
    collect_review_data,
    classify_segments_with_llm,
    generate_segment_pdf
)

logger = logging.getLogger(__name__)


class SegmentAgentContext:
    """세그먼트 분류 컨텍스트"""

    def __init__(self, session_id: str, user_message: str):
        self.session_id = session_id
        self.user_message = user_message
        self.product_name: Optional[str] = None
        self.reviews: list = []
        self.segments: Optional[Dict[str, Any]] = None
        self.pdf_path: Optional[str] = None
        self.errors: list = []


class SegmentAgent:
    """세그먼트 분류 에이전트"""

    def __init__(self):
        self.name = "SegmentAgent"

    def run(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """에이전트 실행 - LLM 기반 세그먼트 분류 파이프라인"""
        logger.info(f"세그먼트 분류 시작 (세션: {session_id})")

        context = SegmentAgentContext(session_id, user_message)

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

                append_message(db, context.session_id, "system", "--- 세그먼트 분류 시작 ---")
                append_message(db, context.session_id, "user", context.user_message)

            # Step 1: 제품명 추출
            logger.info("Step 1: 제품명 추출")
            context.product_name = extract_product_name(context.user_message)

            if not context.product_name:
                context.errors.append("제품명을 찾을 수 없습니다.")
                reply_text = "제품명을 명확히 지정해주세요. 예: '에어팟 프로 구매자를 세그먼트로 분류해줘'"
                with get_db() as db:
                    append_message(db, context.session_id, "assistant", reply_text)
                return {
                    "success": False,
                    "session_id": context.session_id,
                    "reply_text": reply_text,
                    "result_data": None,
                    "errors": context.errors
                }

            # Step 2: 리뷰 데이터 수집
            logger.info(f"Step 2: '{context.product_name}' 리뷰 데이터 수집")
            context.reviews = collect_review_data(context.product_name)

            if not context.reviews:
                context.errors.append("리뷰 데이터를 수집할 수 없습니다.")
                reply_text = f"'{context.product_name}'에 대한 데이터를 찾을 수 없습니다. 다른 제품을 시도해보세요."
                with get_db() as db:
                    append_message(db, context.session_id, "assistant", reply_text)
                return {
                    "success": False,
                    "session_id": context.session_id,
                    "reply_text": reply_text,
                    "result_data": None,
                    "errors": context.errors
                }

            # Step 3: LLM으로 세그먼트 분류
            logger.info(f"Step 3: LLM 세그먼트 분류 ({len(context.reviews)}개 리뷰)")
            context.segments = classify_segments_with_llm(context.reviews, context.product_name)

            # Step 4: PDF 생성
            logger.info("Step 4: PDF 리포트 생성")
            context.pdf_path = generate_segment_pdf(
                context.segments,
                context.product_name
            )

            # Step 5: 최종 응답 생성
            reply_text = self._generate_final_response(context)

            with get_db() as db:
                append_message(db, context.session_id, "assistant", reply_text)

            # PDF 파일명만 추출 (reports\file.pdf -> file.pdf)
            import os
            pdf_filename = os.path.basename(context.pdf_path) if context.pdf_path else None

            # 종합 보고서용 결과 데이터 구조화
            result_data = {
                "product_name": context.product_name,
                "num_segments": len(context.segments),
                "segments": context.segments
            }

            # DB에 태스크 결과 저장
            with get_db() as db:
                save_task_result(
                    db,
                    session_id=context.session_id,
                    task_type="segment",
                    result_data=result_data,
                    product_name=context.product_name,
                    pdf_path=context.pdf_path
                )

            return {
                "success": True,
                "session_id": context.session_id,
                "reply_text": reply_text,
                "result_data": result_data,
                "report_id": pdf_filename,  # PDF 다운로드용 (파일명만)
                "download_url": f"/report/{pdf_filename}" if pdf_filename else None,
                "errors": context.errors
            }

        except Exception as e:
            logger.error(f"세그먼트 분류 실패: {e}", exc_info=True)
            error_msg = f"세그먼트 분류 중 오류가 발생했습니다: {str(e)}"

            with get_db() as db:
                append_message(db, context.session_id, "assistant", error_msg)

            return {
                "success": False,
                "session_id": context.session_id,
                "reply_text": error_msg,
                "result_data": None,
                "errors": context.errors + [str(e)]
            }

    def _generate_final_response(self, context: SegmentAgentContext) -> str:
        """최종 응답 생성"""
        segments = context.segments

        response = f"📊 **{context.product_name} 구매자 세그먼트 분석 완료**\n\n"
        response += f"총 {len(context.reviews)}개의 리뷰를 분석하여 {segments.get('total_segments', 0)}개 세그먼트를 발견했습니다.\n\n"

        # 각 세그먼트 요약
        response += "**세그먼트 개요:**\n"
        for i, segment in enumerate(segments.get('segments', []), 1):
            name = segment.get('name', f'세그먼트 {i}')
            percentage = segment.get('percentage', 0)
            characteristics = segment.get('characteristics', '특성 없음')

            response += f"\n{i}. **{name}** ({percentage}%)\n"
            response += f"   - {characteristics[:100]}...\n"

        # 전체 인사이트
        if segments.get('overall_insights'):
            response += f"\n**전체 인사이트:**\n{segments['overall_insights'][:200]}...\n"

        # PDF 다운로드 안내
        if context.pdf_path:
            response += f"\n\n📄 **상세 분석 리포트**가 생성되었습니다.\n"
            response += f"PDF를 다운로드하여 세그먼트별 특성과 마케팅 전략을 확인하세요.\n"

        response += "\n\n⚠️ 본 결과는 온라인 리뷰 데이터 기반 분석이며, 참고용으로만 사용하세요."

        return response


agent = SegmentAgent()


def run_agent(session_id: str, user_message: str) -> Dict[str, Any]:
    if not session_id:
        with get_db() as db:
            session = create_session(db)
            session_id = session.id
    return agent.run(session_id, user_message)
