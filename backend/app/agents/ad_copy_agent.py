"""
광고 문구 생성 에이전트
LLM을 활용한 다양한 광고 카피 생성
"""
import json
import logging
from typing import Dict, Any, Optional, List

from app.db.session import get_db
from app.db.crud import (
    append_message,
    create_session,
    get_session,
    get_messages_by_session,
    save_task_result
)
from app.tools.ad_tools import (
    parse_ad_request,
    generate_ad_copy_matrix,
    batch_check_ad_compliance,
    prepare_rag_documents
)
from app.tools.common.rag_base import build_context_from_rag, add_to_rag

logger = logging.getLogger(__name__)

BRIEF_MARKER = "__ad_brief__"
DEFAULT_TONES = ["friendly", "formal", "humor"]
DEFAULT_LENGTHS = ["short", "medium", "long"]


class AdCopyAgentContext:
    """광고 문구 생성 컨텍스트"""

    def __init__(self, session_id: str, user_message: str):
        self.session_id = session_id
        self.user_message = user_message
        self.product_brief: Optional[Dict[str, Any]] = None
        self.length_options: List[str] = []
        self.tone_options: List[str] = []
        self.rag_context: Optional[str] = None
        self.ad_variations: Dict[str, Dict[str, List[str]]] = {}
        self.compliance_results: Dict[str, Any] = {}
        self.rag_doc_ids: List[str] = []
        self.errors: List[str] = []
        self.is_additional_request: bool = False


class AdCopyAgent:
    """광고 문구 생성 에이전트"""

    def __init__(self):
        self.name = "AdCopyAgent"

    def run(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """에이전트 실행"""
        logger.info(f"광고 문구 생성 시작 (세션: {session_id})")

        context = AdCopyAgentContext(session_id, user_message)
        context.is_additional_request = self._is_additional_request(user_message)

        try:
            with get_db() as db:
                if not session_id:
                    session = create_session(db)
                    context.session_id = session.id
                else:
                    session = get_session(db, session_id)
                    if not session:
                        session = create_session(db)
                        context.session_id = session.id

                append_message(db, context.session_id, "system", "--- 광고 문구 생성 시작 ---")
                append_message(db, context.session_id, "user", context.user_message)

            # Step 1. 사용자 메시지에서 제품 브리프 추출
            try:
                context.product_brief = parse_ad_request(context.user_message)
            except Exception as parse_error:
                logger.error("제품 정보 파싱 실패", exc_info=True)
                logger.debug(f"제품 정보 파싱 예외: {parse_error}")

            if not context.product_brief or not context.product_brief.get("product_name"):
                fallback = self._load_previous_brief(context.session_id)
                if fallback:
                    context.product_brief = fallback
                else:
                    reply_text = self._build_missing_product_reply()
                    with get_db() as db:
                        append_message(db, context.session_id, "assistant", reply_text)
                    context.errors.append("제품명을 식별하지 못했습니다.")
                    return {
                        "success": False,
                        "session_id": context.session_id,
                        "reply_text": reply_text,
                        "result_data": None,
                        "errors": context.errors
                    }

            # 기본 길이/톤 옵션 설정
            context.length_options = self._normalize_preferences(
                context.product_brief.get("length_preferences"),
                default=DEFAULT_LENGTHS
            )
            context.tone_options = self._normalize_preferences(
                context.product_brief.get("tone_preferences"),
                default=DEFAULT_TONES
            )

            # Step 2. RAG 컨텍스트 확보
            product_name = context.product_brief["product_name"]
            context.rag_context = build_context_from_rag(
                query=product_name,
                category="ad",
                k=3
            )

            # 현재 브리프를 세션에 저장 (후속 요청 지원)
            self._persist_brief(context)

            # Step 3. LLM으로 광고 문구 배리에이션 생성
            suggestions_per_slot = 3 if context.is_additional_request else 2
            extra_instruction = (
                "이전에 제공한 문구와 겹치지 않도록 새로운 관점과 표현을 사용하세요."
                if context.is_additional_request else ""
            )
            context.ad_variations = generate_ad_copy_matrix(
                product_brief=context.product_brief,
                rag_context=context.rag_context,
                tone_options=context.tone_options,
                length_options=context.length_options,
                suggestions_per_slot=suggestions_per_slot,
                extra_instruction=extra_instruction
            )

            total_variations = self._count_variations(context.ad_variations)
            if total_variations == 0:
                reply_text = (
                    "광고 문구를 생성하지 못했습니다. 제품 정보 또는 원하는 톤/길이를 더 구체적으로 알려주세요."
                )
                context.errors.append("생성된 광고 문구가 없습니다.")
                with get_db() as db:
                    append_message(db, context.session_id, "assistant", reply_text)
                return {
                    "success": False,
                    "session_id": context.session_id,
                    "reply_text": reply_text,
                    "result_data": None,
                    "errors": context.errors
                }

            # Step 4. 배리에이션별 규제 검수
            context.compliance_results = batch_check_ad_compliance(context.ad_variations)
            non_compliant_entries = [
                entry for entry in context.compliance_results.get("details", [])
                if not entry.get("is_compliant", True)
            ]
            for entry in non_compliant_entries:
                issues = ", ".join(entry.get("issues", [])) or "원인 미상"
                context.errors.append(
                    f"컴플라이언스 이슈 발견 ({entry.get('tone', '-')}/{entry.get('length', '-')}): {issues}"
                )

            # Step 5. RAG 저장
            self._store_variations_in_rag(context)

            # Step 6. 사용자 응답 생성
            reply_text = self._build_user_reply(context, total_variations, non_compliant_entries)

            with get_db() as db:
                append_message(db, context.session_id, "assistant", reply_text)

            # 종합 보고서용 결과 데이터 구조화
            ad_copies_list = []
            for tone, length_dict in context.ad_variations.items():
                for length, copies in length_dict.items():
                    for copy_text in copies:
                        ad_copies_list.append({
                            "text": copy_text,
                            "tone": tone,
                            "length": length
                        })

            result_data = {
                "product_name": context.product_brief.get("product_name") if context.product_brief else None,
                "target_audience": context.product_brief.get("target_audience") if context.product_brief else None,
                "ad_copies": ad_copies_list,
                "total_variations": len(ad_copies_list),
                "tones": list(context.ad_variations.keys()),
                "compliance_passed": context.compliance_results.get("overall_pass", True) if context.compliance_results else True
            }

            # DB에 태스크 결과 저장
            with get_db() as db:
                save_task_result(
                    db,
                    session_id=context.session_id,
                    task_type="ad_copy",
                    result_data=result_data,
                    product_name=result_data.get("product_name")
                )

            return {
                "success": True,
                "session_id": context.session_id,
                "reply_text": reply_text,
                "result_data": result_data,
                "errors": context.errors
            }

        except Exception as e:
            logger.error(f"광고 문구 생성 실패: {e}", exc_info=True)
            return {
                "success": False,
                "session_id": context.session_id,
                "reply_text": f"오류 발생: {str(e)}",
                "result_data": None,
                "errors": context.errors + [str(e)]
            }

    @staticmethod
    def _normalize_preferences(values: Optional[List[str]], default: List[str]) -> List[str]:
        """사용자 입력 기반 길이/톤 옵션 정규화"""
        if not values:
            return default
        normalized = [value.strip().lower() for value in values if isinstance(value, str) and value.strip()]
        return list(dict.fromkeys(normalized)) or default

    def _store_variations_in_rag(self, context: AdCopyAgentContext) -> None:
        """생성된 광고 문구를 RAG 저장소에 기록"""
        if not context.ad_variations:
            return

        try:
            records = prepare_rag_documents(
                product_brief=context.product_brief,
                variations=context.ad_variations
            )
        except Exception as prep_error:
            logger.warning(f"RAG 문서 준비 실패: {prep_error}")
            context.errors.append(f"RAG 문서를 준비하는 중 문제가 발생했습니다: {prep_error}")
            return

        for record in records:
            try:
                doc_id = add_to_rag(
                    content=record.get("content", ""),
                    metadata=record.get("metadata", {}),
                    category="ad"
                )
                context.rag_doc_ids.append(doc_id)
            except Exception as rag_error:
                logger.warning(f"RAG 저장 실패: {rag_error}")
                context.errors.append(f"RAG 저장 중 오류 발생: {rag_error}")

    @staticmethod
    def _count_variations(variations: Dict[str, Dict[str, List[str]]]) -> int:
        """총 배리에이션 개수 계산"""
        total = 0
        for tone_variants in variations.values():
            for texts in tone_variants.values():
                total += len(texts or [])
        return total

    @staticmethod
    def _build_missing_product_reply() -> str:
        """제품 정보를 찾지 못했을 때 사용자 안내"""
        return (
            "제품이나 서비스 정보를 찾을 수 없습니다. 예시) "
            "'친환경 세제에 대한 광고 문구를 친근한 톤으로 3개 만들어줘'처럼 "
            "제품명, 특징, 원하는 톤을 함께 알려주시면 도움이 됩니다."
        )

    def _build_user_reply(
        self,
        context: AdCopyAgentContext,
        total_variations: int,
        non_compliant_entries: List[Dict[str, Any]]
    ) -> str:
        """사용자에게 전달할 결과 메시지 구성"""
        product_name = context.product_brief.get("product_name", "제품")
        target_audience = context.product_brief.get("target_audience", "")
        campaign_goal = context.product_brief.get("campaign_goal", "")

        tone_labels = {
            "formal": "공식적",
            "friendly": "친근함",
            "humor": "유머러스",
            "casual": "편안함"
        }
        length_labels = {
            "short": "짧게",
            "medium": "중간",
            "long": "길게"
        }

        lines: List[str] = []
        lines.append(f"✍️ **{product_name} 광고 문구 제안**")
        if target_audience:
            lines.append(f"- 타깃: {target_audience}")
        if campaign_goal:
            lines.append(f"- 캠페인 목표: {campaign_goal}")

        if context.is_additional_request:
            lines.append("")
            lines.append("🔁 추가 요청을 반영해 새로운 문구를 제안합니다.")

        lines.append("")
        lines.append(f"총 {total_variations}개의 카피를 길이·톤 조합으로 구성했습니다:")

        for tone in context.tone_options:
            tone_variants = context.ad_variations.get(tone, {})
            if not tone_variants:
                continue
            tone_label = tone_labels.get(tone, tone.capitalize())
            lines.append(f"\n**톤: {tone_label}**")
            for length in context.length_options:
                candidates = tone_variants.get(length, [])
                if not candidates:
                    continue
                length_label = length_labels.get(length, length.capitalize())
                preview = candidates[0].strip()
                lines.append(f"- {length_label}: {preview}")

        compliance_summary = context.compliance_results.get("summary", {})
        passed = compliance_summary.get("passed", 0)
        failed = compliance_summary.get("failed", 0)
        lines.append("")
        lines.append(f"✅ 규제 검수 통과: {passed}개 / ⚠️ 보완 필요: {failed}개")

        if non_compliant_entries:
            lines.append("보완이 필요한 카피는 금지어 또는 표현 제한과 충돌합니다. 아래 항목을 수정하세요:")
            for entry in non_compliant_entries[:3]:
                tone_label = tone_labels.get(entry.get("tone"), entry.get("tone", "-"))
                length_label = length_labels.get(entry.get("length"), entry.get("length", "-"))
                issue_words = ", ".join(entry.get("issues", [])) or "구체적 이슈 확인 필요"
                lines.append(f"- {tone_label} / {length_label}: {issue_words}")
            if len(non_compliant_entries) > 3:
                lines.append(f"  · 추가 보완 필요 항목 {len(non_compliant_entries) - 3}개")

        lines.append("")
        lines.append("필요하면 특정 톤이나 길이만 다시 요청하거나, 제품 특징을 더 알려주시면 카피를 미세 조정할 수 있습니다.")
        lines.append("\n⚠️ 본 결과는 마케팅 참고용 초안입니다. 최종 사용 전 관련 법규와 브랜드 가이드를 다시 확인하세요.")

        return "\n".join(lines)

    @staticmethod
    def _is_additional_request(user_message: str) -> bool:
        """추가 제안 요청 여부 판별"""
        lowered = user_message.lower()
        keywords = ["추가", "더", "또", "extra", "another"]
        return any(keyword in lowered for keyword in keywords)

    def _persist_brief(self, context: AdCopyAgentContext) -> None:
        """현재 세션에 제품 브리프를 저장 (후속 요청 지원)"""
        if not context.product_brief:
            return

        payload = json.dumps(context.product_brief, ensure_ascii=False)
        marker_message = f"{BRIEF_MARKER}:{payload}"

        with get_db() as db:
            append_message(db, context.session_id, "system", marker_message)

    def _load_previous_brief(self, session_id: str) -> Optional[Dict[str, Any]]:
        """세션에서 마지막 제품 브리프를 불러오기"""
        try:
            with get_db() as db:
                rows = [
                    (msg.role, msg.content)
                    for msg in get_messages_by_session(db, session_id)
                ]
        except Exception as e:
            logger.warning(f"이전 브리프 로드 실패: {e}")
            return None

        for role, content in reversed(rows):
            if role != "system":
                continue
            if not content.startswith(BRIEF_MARKER):
                continue
            payload = content[len(BRIEF_MARKER) + 1:].strip()
            try:
                brief = json.loads(payload)
                if brief.get("product_name"):
                    return brief
            except json.JSONDecodeError:
                continue
        return None


agent = AdCopyAgent()


def run_agent(session_id: str, user_message: str) -> Dict[str, Any]:
    if not session_id:
        with get_db() as db:
            session = create_session(db)
            session_id = session.id
    return agent.run(session_id, user_message)
