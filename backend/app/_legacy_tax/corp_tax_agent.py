"""
법인세 에이전트 그래프
Plan → Fetch → LawParam → Calc → Eval → Report
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.db.session import get_db
from app.db.crud import (
    append_message, save_calc_result, create_session, get_session
)
from app.tools.llm import call_llm, format_tool_result_for_llm, TOOL_DEFINITIONS
from app.tools.dart import get_corp_code_by_name, get_basic_financials
from app.tools.tax_rules import get_current_law_params, format_law_params_summary
from app.tools.tax_calc import estimate_tax, evaluate_result, format_calc_result_summary
from app.tools.rag_store import (
    add_calc_result_to_rag, search_past_results_by_corp, build_comparison_table
)
from app.tools.pdf_maker import make_pdf, get_pdf_download_url

logger = logging.getLogger(__name__)


class CorpTaxAgentContext:
    """에이전트 실행 컨텍스트"""

    def __init__(self, session_id: str, user_message: str):
        self.session_id = session_id
        self.user_message = user_message
        self.corp_name: Optional[str] = None
        self.corp_code: Optional[str] = None
        self.financials: Optional[Dict[str, Any]] = None
        self.law_params: Optional[Dict[str, Any]] = None
        self.calc_result: Optional[Dict[str, Any]] = None
        self.evaluation: Optional[Dict[str, Any]] = None
        self.past_results: list = []
        self.comparison_table: Optional[str] = None
        self.pdf_path: Optional[str] = None
        self.report_id: Optional[str] = None
        self.reply_text: str = ""
        self.errors: list = []


class CorpTaxAgent:
    """법인세 계산 에이전트"""

    def __init__(self):
        self.name = "CorpTaxAgent"

    def run(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """
        에이전트 실행 메인 함수

        Args:
            session_id: 세션 ID
            user_message: 사용자 메시지

        Returns:
            실행 결과
        """
        logger.info(f"에이전트 실행 시작 (세션: {session_id})")

        # 컨텍스트 초기화
        context = CorpTaxAgentContext(session_id, user_message)

        try:
            # 1. 컨텍스트 구분 마커 및 사용자 메시지 저장
            with get_db() as db:
                # 시스템 메시지를 먼저 저장 (히스토리 필터링 기준점)
                append_message(db, context.session_id, "system", "--- 새로운 계산 요청 시작 ---")
                # 그 다음 사용자 메시지 저장
                append_message(db, context.session_id, "user", context.user_message)

            # 2. Plan: LLM에게 사용자 요청 분석 및 도구 호출 계획 요청
            self._plan_node(context)

            # 3. 도구 실행 루프 (LLM이 도구 호출을 멈출 때까지)
            max_iterations = 10
            iteration = 0

            while iteration < max_iterations:
                iteration += 1
                logger.info(f"도구 실행 루프: {iteration}회차")

                # LLM 호출 (사용자 메시지는 이미 DB에 저장됨, 빈 문자열 전달)
                llm_response = call_llm(context.session_id, "")

                if not llm_response.get("success"):
                    context.errors.append(llm_response.get("error", "LLM 호출 실패"))
                    break

                # 도구 호출이 있으면 실행
                tool_calls = llm_response.get("tool_calls", [])

                if not tool_calls:
                    # 도구 호출이 없으면 최종 응답
                    context.reply_text = llm_response.get("reply_text", "")
                    break

                # 도구 실행 및 결과 수집
                tool_results = []
                for tool_call in tool_calls:
                    self._execute_tool(context, tool_call)
                    # 도구 실행 결과 요약
                    result_summary = self._get_tool_result_summary(context, tool_call)
                    tool_results.append(result_summary)

                # 도구 결과를 assistant 메시지로 DB에 저장 (LLM이 다음 호출에서 참고)
                if tool_results:
                    results_text = "\n".join(tool_results)
                    with get_db() as db:
                        append_message(db, context.session_id, "assistant", f"도구 실행 결과:\n{results_text}")

            # 4. 최종 응답 생성
            if not context.reply_text:
                context.reply_text = self._generate_final_reply(context)

            # 5. 최종 응답 메시지 저장
            with get_db() as db:
                append_message(db, context.session_id, "assistant", context.reply_text)

            # 5. 응답 반환
            result = {
                "success": True,
                "session_id": context.session_id,
                "reply_text": context.reply_text,
                "report_id": context.report_id,
                "download_url": get_pdf_download_url(context.pdf_path, context.report_id) if context.report_id else None,
                "errors": context.errors
            }

            logger.info("에이전트 실행 완료")
            return result

        except Exception as e:
            logger.error(f"에이전트 실행 실패: {e}", exc_info=True)
            return {
                "success": False,
                "session_id": context.session_id,
                "reply_text": f"죄송합니다. 오류가 발생했습니다: {str(e)}",
                "errors": context.errors + [str(e)]
            }

    def _plan_node(self, context: CorpTaxAgentContext):
        """Plan 노드: 사용자 요청 분석"""
        logger.info("Plan 노드 실행")
        # LLM이 자동으로 계획을 세우므로 여기서는 컨텍스트 초기화만
        pass

    def _execute_tool(self, context: CorpTaxAgentContext, tool_call: Dict[str, Any]):
        """
        도구 실행

        Args:
            context: 에이전트 컨텍스트
            tool_call: 도구 호출 정보
        """
        function_name = tool_call.get("function_name")
        arguments = tool_call.get("arguments", {})

        logger.info(f"도구 실행: {function_name}, 인자: {arguments}")

        try:
            if function_name == "dart_lookup":
                self._dart_lookup_tool(context, arguments)

            elif function_name == "tax_calc_apply":
                self._tax_calc_tool(context, arguments)

            elif function_name == "make_pdf_report":
                self._make_pdf_tool(context, arguments)

            elif function_name == "rag_search":
                self._rag_search_tool(context, arguments)

            else:
                logger.warning(f"알 수 없는 도구: {function_name}")

        except Exception as e:
            logger.error(f"도구 실행 실패 ({function_name}): {e}", exc_info=True)
            context.errors.append(f"{function_name} 실행 실패: {str(e)}")

    def _dart_lookup_tool(self, context: CorpTaxAgentContext, arguments: Dict[str, Any]):
        """DART 조회 도구"""
        corp_name = arguments.get("corp_name", "")
        logger.info(f"DART 조회: {corp_name}")

        # 기업 코드 조회
        corp_code = get_corp_code_by_name(corp_name)
        if not corp_code:
            context.errors.append(f"기업 코드를 찾을 수 없습니다: {corp_name}")
            return

        # 재무 정보 조회
        financials = get_basic_financials(corp_code, corp_name)

        # 컨텍스트 업데이트
        context.corp_name = corp_name
        context.corp_code = corp_code
        context.financials = financials

        logger.info(f"DART 조회 완료: {corp_name}")

    def _tax_calc_tool(self, context: CorpTaxAgentContext, arguments: Dict[str, Any]):
        """법인세 계산 도구"""
        logger.info("법인세 계산 시작")

        # 재무 정보가 없으면 에러
        if not context.financials:
            context.errors.append("재무 정보가 없습니다. 먼저 DART 조회를 실행하세요.")
            return

        # 법령 파라미터 조회
        law_params = get_current_law_params()
        context.law_params = law_params

        # 법인세 계산
        calc_result = estimate_tax(context.financials, law_params)
        context.calc_result = calc_result

        # 평가
        evaluation = evaluate_result(calc_result, context.financials)
        context.evaluation = evaluation

        # DB 저장
        with get_db() as db:
            saved_result = save_calc_result(
                db,
                session_id=context.session_id,
                corp_name=context.corp_name or "Unknown",
                corp_code=context.corp_code,
                law_param_version=law_params.get("version", "unknown"),
                result_json=calc_result,
                summary_text=format_calc_result_summary(calc_result, evaluation)
            )
            context.report_id = saved_result.id

        # RAG 저장
        add_calc_result_to_rag(calc_result, context.corp_name or "Unknown", context.corp_code)

        # 재계산 필요 여부 확인 (평가 신뢰도가 낮으면)
        if evaluation.get("confidence_score", 1.0) < 0.7:
            logger.warning(f"평가 신뢰도 낮음: {evaluation.get('confidence_score')}")
            # 여기서 재계산 로직 추가 가능 (보정 파라미터 적용 등)

        logger.info("법인세 계산 완료")

    def _make_pdf_tool(self, context: CorpTaxAgentContext, arguments: Dict[str, Any]):
        """PDF 생성 도구"""
        logger.info("PDF 생성 시작")

        if not context.calc_result or not context.evaluation:
            context.errors.append("계산 결과가 없습니다. 먼저 법인세 계산을 실행하세요.")
            return

        # 과거 결과 조회 (비교표 생성용)
        if context.corp_name:
            past_results = search_past_results_by_corp(context.corp_name, limit=5)
            context.past_results = past_results

            if past_results:
                context.comparison_table = build_comparison_table(
                    context.calc_result, past_results
                )

        # PDF 생성
        pdf_path = make_pdf(
            context.calc_result,
            context.evaluation,
            context.corp_name or "Unknown",
            context.comparison_table
        )
        context.pdf_path = pdf_path

        # DB 업데이트 (PDF 경로 저장)
        if context.report_id:
            from app.db.models import CalcResult
            with get_db() as db:
                result = db.query(CalcResult).filter_by(id=context.report_id).first()
                if result:
                    result.pdf_path = pdf_path
                    db.commit()

        logger.info(f"PDF 생성 완료: {pdf_path}")

    def _rag_search_tool(self, context: CorpTaxAgentContext, arguments: Dict[str, Any]):
        """RAG 검색 도구"""
        query = arguments.get("query", "")
        corp_name = arguments.get("corp_name")

        logger.info(f"RAG 검색: {query}")

        if corp_name:
            past_results = search_past_results_by_corp(corp_name, limit=5)
        else:
            from app.tools.rag_store import search_rag
            past_results = search_rag(query, k=5)

        context.past_results = past_results

        # 비교표 생성 (현재 결과가 있으면)
        if context.calc_result and past_results:
            context.comparison_table = build_comparison_table(
                context.calc_result, past_results
            )

        logger.info(f"RAG 검색 완료: {len(past_results)}개 결과")

    def _get_tool_result_summary(self, context: CorpTaxAgentContext, tool_call: Dict[str, Any]) -> str:
        """도구 실행 결과 요약 생성"""
        function_name = tool_call.get("function_name")

        if function_name == "dart_lookup":
            if context.financials:
                return f"✓ DART 조회 완료: {context.corp_name} (매출: {context.financials.get('revenue', 0):,.0f}원, 영업이익: {context.financials.get('operating_income', 0):,.0f}원)"
            return f"✓ DART 조회 완료: {context.corp_name}"

        elif function_name == "tax_calc_apply":
            if context.calc_result:
                total_tax = context.calc_result.get('total_tax', 0)
                return f"✓ 법인세 계산 완료: 총 세액 {total_tax:,.0f}원"
            return "✓ 법인세 계산 완료"

        elif function_name == "make_pdf_report":
            if context.pdf_path:
                return f"✓ PDF 리포트 생성 완료: {context.pdf_path}"
            return "✓ PDF 리포트 생성 완료"

        elif function_name == "rag_search":
            if context.past_results:
                return f"✓ 과거 결과 검색 완료: {len(context.past_results)}개 결과 발견"
            return "✓ 과거 결과 검색 완료 (결과 없음)"

        return f"✓ {function_name} 실행 완료"

    def _generate_final_reply(self, context: CorpTaxAgentContext) -> str:
        """최종 응답 생성"""
        reply = ""

        if context.calc_result:
            # 계산 결과가 있으면 요약
            reply += format_calc_result_summary(context.calc_result, context.evaluation or {})
            reply += "\n\n"

        if context.comparison_table:
            # 비교표가 있으면 추가
            reply += context.comparison_table
            reply += "\n\n"

        if context.pdf_path:
            # PDF 생성 완료 메시지
            reply += "PDF 리포트가 생성되었습니다. 다운로드 버튼을 클릭하세요.\n\n"

        # 면책 문구 추가
        reply += "⚠️ 본 결과는 연구·시뮬레이션용 근사치이며 신고/자문 용도로 사용할 수 없습니다.\n"

        if context.errors:
            reply += f"\n경고: {len(context.errors)}개의 오류가 발생했습니다.\n"

        return reply.strip() or "요청을 처리하지 못했습니다. 다시 시도해주세요."


# 싱글톤 인스턴스
agent = CorpTaxAgent()


def run_agent(session_id: str, user_message: str) -> Dict[str, Any]:
    """
    에이전트 실행 헬퍼 함수

    Args:
        session_id: 세션 ID (없으면 새로 생성)
        user_message: 사용자 메시지

    Returns:
        실행 결과
    """
    # 세션 확인 또는 생성
    if not session_id:
        with get_db() as db:
            session = create_session(db)
            session_id = session.id
    else:
        with get_db() as db:
            session = get_session(db, session_id)
            if not session:
                session = create_session(db)
                session_id = session.id

    # 에이전트 실행
    return agent.run(session_id, user_message)
