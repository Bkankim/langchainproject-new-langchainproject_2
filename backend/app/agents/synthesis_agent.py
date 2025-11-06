"""
마케팅 전략 종합 보고서 에이전트
여러 태스크 결과를 통합하여 최종 마케팅 전략 제시
"""
import logging
import re
from typing import Dict, Any, Optional

from app.db.session import get_db
from app.db.crud import (
    append_message,
    create_session,
    get_session,
    get_task_results_by_session
)
from app.tools.synthesis_tools import (
    estimate_tokens,
    synthesize_marketing_strategy,
    generate_synthesis_pdf
)
from app.tools.llm import call_llm_with_context

logger = logging.getLogger(__name__)


def extract_product_name_from_message(user_message: str, session_id: str) -> Optional[str]:
    """
    사용자 메시지에서 제품명 추출

    Args:
        user_message: 사용자 메시지
        session_id: 세션 ID (로깅용)

    Returns:
        추출된 제품명 또는 None (전체 제품)
    """
    # 불필요한 접두어 제거 (우선 처리)
    cleaned_message = user_message
    prefixes_to_remove = [
        r'^마지막으로\s+',
        r'^이제\s+',
        r'^그럼\s+',
        r'^자\s+',
        r'^이번에는\s+',
        r'^다음으로\s+',
    ]

    for prefix in prefixes_to_remove:
        cleaned_message = re.sub(prefix, '', cleaned_message)

    # 정규표현식 패턴 매칭 시도
    patterns = [
        r'(.+?)\s*(?:에\s*대한|의|에\s*관한)\s*종합',
        r'(.+?)\s*종합\s*보고서',
        r'(.+?)\s*마케팅\s*전략',
    ]

    for pattern in patterns:
        match = re.search(pattern, cleaned_message)
        if match:
            product_name = match.group(1).strip()
            # 추가 정리: 불용어 제거
            stopwords = ['그', '저', '이', '그것', '저것', '이것']
            if product_name not in stopwords:
                logger.info(f"정규표현식으로 제품명 추출: '{product_name}' (원본: '{user_message}', 세션: {session_id})")
                return product_name

    # LLM을 사용하여 제품명 추출 시도
    try:
        system_prompt = """당신은 제품명 추출 전문가입니다.
사용자 메시지에서 종합 보고서를 작성할 제품명을 추출하세요.

규칙:
1. 제품명만 추출 (다른 설명 제외)
2. 제품명이 명확하지 않으면 "NONE" 반환
3. 한 줄로만 응답

예시:
- 입력: "신라면에 대한 종합 보고서 만들어줘"
- 출력: 신라면

- 입력: "종합 보고서 작성해줘"
- 출력: NONE
"""

        response = call_llm_with_context(messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ])

        if response.get("success"):
            extracted = response.get("reply_text", "").strip()
            if extracted and extracted != "NONE":
                logger.info(f"LLM으로 제품명 추출: '{extracted}' (세션: {session_id})")
                return extracted
    except Exception as e:
        logger.warning(f"LLM 제품명 추출 실패: {e}")

    # 추출 실패 - 전체 제품 종합
    logger.info(f"제품명 추출 실패, 전체 제품 종합으로 진행 (세션: {session_id})")
    return None


class SynthesisAgent:
    """종합 보고서 생성 에이전트"""

    def __init__(self):
        self.name = "SynthesisAgent"

    def run(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """에이전트 실행"""
        logger.info(f"종합 보고서 생성 시작 (세션: {session_id})")

        try:
            # 세션 확인
            with get_db() as db:
                if not session_id:
                    return {
                        "success": False,
                        "session_id": None,
                        "reply_text": "세션 ID가 필요합니다.",
                        "result_data": None,
                        "errors": ["No session_id"]
                    }

                session = get_session(db, session_id)
                if not session:
                    return {
                        "success": False,
                        "session_id": session_id,
                        "reply_text": "유효하지 않은 세션입니다.",
                        "result_data": None,
                        "errors": ["Invalid session"]
                    }

                append_message(db, session_id, "system", "--- 마케팅 전략 종합 보고서 생성 시작 ---")
                append_message(db, session_id, "user", user_message)

            # Step 1: 사용자 메시지에서 제품명 추출
            target_product = extract_product_name_from_message(user_message, session_id)

            if target_product:
                logger.info(f"특정 제품에 대한 종합 보고서 요청: '{target_product}'")
            else:
                logger.info(f"전체 제품에 대한 종합 보고서 요청")

            # Step 2: 세션의 태스크 결과 조회 (제품 필터링 적용)
            with get_db() as db:
                task_results = get_task_results_by_session(
                    db,
                    session_id,
                    product_name=target_product  # 제품 필터링
                )

                # DB 세션이 닫히기 전에 필요한 데이터를 추출하고 중복 제거
                deduped_results = {}
                for result in task_results:
                    # 동일 세션·상품에서 반복된 태스크는 최신 결과만 유지
                    product_key = result.product_name or "__no_product__"
                    dedup_key = (result.task_type, product_key)
                    current = deduped_results.get(dedup_key)
                    if current is None or current["created_at"] < result.created_at:
                        deduped_results[dedup_key] = {
                            "task_type": result.task_type,
                            "product_name": result.product_name,
                            "result_data": result.result_data,
                            "created_at": result.created_at
                        }

                task_data_list = sorted(
                    deduped_results.values(),
                    key=lambda item: item["created_at"]
                )

            if not task_data_list:
                if target_product:
                    reply_text = f"""'{target_product}'에 대한 실행된 태스크가 없습니다.

먼저 '{target_product}'에 대한 다음 태스크들을 실행해주세요:
- 트렌드 분석: "{target_product} 트렌드 분석해줘"
- 광고 문구 생성: "{target_product} 광고 문구 만들어줘"
- 세그먼트 분류: "{target_product} 세그먼트 분석해줘"
- 리뷰 감성 분석: "{target_product} 리뷰 분석해줘"
- 경쟁사 분석: "{target_product} 경쟁사 분석해줘"

💡 여러 제품을 함께 종합하려면 제품명 없이 "종합 보고서 만들어줘"라고 요청하세요.
"""
                else:
                    reply_text = """아직 실행된 태스크가 없습니다.

먼저 다음 태스크들을 실행해주세요:
- 트렌드 분석
- 광고 문구 생성
- 세그먼트 분류
- 리뷰 감성 분석
- 경쟁사 분석

예시: "에어팟 프로 트렌드 분석해줘"
"""
                with get_db() as db:
                    append_message(db, session_id, "assistant", reply_text)

                return {
                    "success": False,
                    "session_id": session_id,
                    "reply_text": reply_text,
                    "result_data": None,
                    "errors": ["No task results found"]
                }

            # Step 2: 토큰 크기 확인
            token_count = estimate_tokens(task_data_list)
            logger.info(f"추정 토큰 수: {token_count}")

            # Step 3: 종합 분석 실행
            logger.info(f"{len(task_data_list)}개 태스크 결과 종합 중...")
            synthesis_text = synthesize_marketing_strategy(task_data_list)

            # Step 4: PDF 보고서 생성
            logger.info("Step 4: PDF 보고서 생성")
            product_name = task_data_list[0].get('product_name', '제품') if task_data_list else '제품'
            pdf_path = generate_synthesis_pdf(task_data_list, synthesis_text, product_name)

            # PDF 파일명 추출
            import os
            pdf_filename = os.path.basename(pdf_path) if pdf_path else None

            # Step 5: 최종 응답 생성
            task_summary = [f"- {r['task_type']}: {r['product_name'] or 'N/A'}" for r in task_data_list]

            # 대상 제품 목록 생성
            unique_products = set(r['product_name'] for r in task_data_list if r['product_name'])
            if target_product:
                scope_text = f"'{target_product}' 단일 제품"
            elif len(unique_products) == 1:
                scope_text = f"'{list(unique_products)[0]}' 단일 제품"
            else:
                scope_text = f"총 {len(unique_products)}개 제품 ({', '.join(sorted(unique_products))})"

            reply_text = f"""✅ **마케팅 전략 종합 보고서 생성 완료**

**📊 분석 범위:** {scope_text}

**분석된 태스크 ({len(task_data_list)}개):**
{chr(10).join(task_summary)}

**📄 종합 보고서 구성:**
1. Executive Summary (핵심 요약)
2. 시장 환경 분석
3. 고객 인사이트
4. 마케팅 전략 제안
5. 실행 계획

💡 **다음 단계:**
PDF 보고서를 다운로드하여 상세 분석 결과를 확인하세요.
"""

            with get_db() as db:
                append_message(db, session_id, "assistant", reply_text)

            return {
                "success": True,
                "session_id": session_id,
                "reply_text": reply_text,
                "result_data": {
                    "num_tasks": len(task_data_list),
                    "tasks": [r['task_type'] for r in task_data_list],
                    "synthesis": synthesis_text,
                    "product_name": product_name
                },
                "report_id": pdf_filename,
                "download_url": f"/report/{pdf_filename}" if pdf_filename else None,
                "errors": []
            }

        except Exception as e:
            logger.error(f"종합 보고서 생성 실패: {e}", exc_info=True)
            return {
                "success": False,
                "session_id": session_id,
                "reply_text": f"오류 발생: {str(e)}",
                "result_data": None,
                "errors": [str(e)]
            }


agent = SynthesisAgent()


def run_agent(session_id: str, user_message: str) -> Dict[str, Any]:
    if not session_id:
        with get_db() as db:
            session = create_session(db)
            session_id = session.id
    return agent.run(session_id, user_message)
