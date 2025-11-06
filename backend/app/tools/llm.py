"""
LLM 래퍼 - OpenAI Chat Completions API
함수 호출(도구) 지원
"""
import logging
from typing import List, Dict, Any, Optional
import json

from openai import OpenAI

from app.config import OPENAI_API_KEY, OPENAI_MODEL
from app.db.session import get_db
from app.db.crud import get_messages_by_session, append_message

logger = logging.getLogger(__name__)

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY and OPENAI_API_KEY != 'YOUR_OPENAI_KEY' else None


# 도구(함수) 정의
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "dart_lookup",
            "description": "DART(전자공시)에서 기업의 재무 정보를 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "corp_name": {
                        "type": "string",
                        "description": "조회할 기업명 (예: 삼성전자)"
                    }
                },
                "required": ["corp_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tax_calc_apply",
            "description": "법인세를 계산합니다. dart_lookup을 먼저 실행한 후에만 호출하세요. 재무 정보는 이전 단계에서 자동으로 사용됩니다.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "make_pdf_report",
            "description": "계산 결과를 PDF 리포트로 생성합니다. tax_calc_apply 실행 후 반드시 호출해야 합니다. 사용자가 PDF를 요청한 경우 필수입니다.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "과거 계산 결과를 검색합니다. 특정 기업의 이전 계산 결과를 조회할 때 사용합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색 쿼리 (기업명 또는 키워드)"
                    },
                    "corp_name": {
                        "type": "string",
                        "description": "특정 기업으로 필터링 (옵션)"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


def call_llm(
    session_id: str,
    user_message: str,
    system_prompt: Optional[str] = None
) -> Dict[str, Any]:
    """
    LLM 호출 (멀티턴 지원)

    Args:
        session_id: 세션 ID
        user_message: 사용자 메시지
        system_prompt: 시스템 프롬프트 (옵션)

    Returns:
        LLM 응답 (텍스트 및 도구 호출 포함)
    """
    if not client:
        logger.error("OpenAI 클라이언트가 초기화되지 않았습니다.")
        return {
            "success": False,
            "error": "OpenAI API 키가 설정되지 않았습니다. .env 파일을 확인하세요.",
            "reply_text": "죄송합니다. LLM 서비스에 연결할 수 없습니다."
        }

    try:
        # 1. 세션 히스토리 로드 및 메시지 구성
        messages = []

        # 시스템 프롬프트
        if not system_prompt:
            system_prompt = _get_default_system_prompt()

        messages.append({
            "role": "system",
            "content": system_prompt
        })

        # 히스토리 추가 - DB 세션 내에서 데이터 추출
        # 현재 요청 컨텍스트만 포함 (마지막 "--- 새로운 계산 요청 시작 ---" 이후의 메시지만)
        with get_db() as db:
            history = get_messages_by_session(db, session_id)

            # 마지막 시스템 구분 메시지를 찾음
            start_idx = 0
            for i in range(len(history) - 1, -1, -1):
                if history[i].role == "system" and "새로운 계산 요청 시작" in history[i].content:
                    start_idx = i + 1  # 시스템 메시지 다음부터
                    break

            # 현재 요청의 메시지만 추가 (최대 20개로 제한)
            relevant_history = history[start_idx:]
            for msg in relevant_history[-20:]:
                # 시스템 구분 메시지는 제외
                if msg.role == "system" and "새로운 계산 요청 시작" in msg.content:
                    continue
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # 현재 사용자 메시지 추가 (DB에 없는 경우만)
        if user_message:
            messages.append({
                "role": "user",
                "content": user_message
            })

        # 3. LLM 호출
        logger.info(f"LLM 호출 (세션: {session_id}, 메시지 수: {len(messages)})")

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=2000
        )

        # 4. 응답 파싱
        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        result = {
            "success": True,
            "reply_text": message.content or "",
            "tool_calls": [],
            "finish_reason": finish_reason
        }

        # 도구 호출이 있는 경우
        if message.tool_calls:
            for tool_call in message.tool_calls:
                result["tool_calls"].append({
                    "id": tool_call.id,
                    "function_name": tool_call.function.name,
                    "arguments": json.loads(tool_call.function.arguments)
                })

        logger.info(f"LLM 응답 수신 (도구 호출: {len(result['tool_calls'])}개)")

        return result

    except Exception as e:
        logger.error(f"LLM 호출 실패: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "reply_text": f"죄송합니다. 오류가 발생했습니다: {str(e)}"
        }


def call_llm_with_context(
    messages: List[Dict[str, str]],
    tools: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """
    컨텍스트를 직접 제공하여 LLM 호출

    Args:
        messages: 메시지 리스트
        tools: 도구 정의 (옵션)

    Returns:
        LLM 응답
    """
    if not client:
        logger.error("OpenAI 클라이언트가 초기화되지 않았습니다.")
        return {
            "success": False,
            "error": "OpenAI API 키가 설정되지 않았습니다.",
            "reply_text": "LLM 서비스에 연결할 수 없습니다."
        }

    try:
        kwargs = {
            "model": OPENAI_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 2000
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)

        message = response.choices[0].message

        result = {
            "success": True,
            "reply_text": message.content or "",
            "tool_calls": [],
            "finish_reason": response.choices[0].finish_reason
        }

        if message.tool_calls:
            for tool_call in message.tool_calls:
                result["tool_calls"].append({
                    "id": tool_call.id,
                    "function_name": tool_call.function.name,
                    "arguments": json.loads(tool_call.function.arguments)
                })

        return result

    except Exception as e:
        logger.error(f"LLM 호출 실패: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "reply_text": f"오류: {str(e)}"
        }


def _get_default_system_prompt() -> str:
    """
    기본 시스템 프롬프트

    Returns:
        시스템 프롬프트 텍스트
    """
    return """당신은 법인세 계산을 돕는 AI 에이전트입니다.

**필수 실행 순서 (절대 생략 불가):**

1단계: dart_lookup(corp_name) - 기업 재무 정보 조회
2단계: tax_calc_apply() - 법인세 계산
3단계: make_pdf_report() - PDF 리포트 생성

**중요 규칙:**
1. 사용자가 기업명을 언급하면 즉시 dart_lookup(기업명) 호출
2. "✓ DART 조회 완료" 확인 → tax_calc_apply() 호출
3. "✓ 법인세 계산 완료" 확인 → make_pdf_report() 호출
4. 사용자가 PDF를 요청했다면 3단계 모두 필수!
5. 같은 도구를 반복 호출하지 마세요

**도구 사용법:**
- dart_lookup(corp_name): 기업명을 정확히 추출해서 전달 (예: "삼성전자", "SK하이닉스")
- tax_calc_apply(): 파라미터 없음 (이전 단계 결과 자동 사용)
- make_pdf_report(): 파라미터 없음 (이전 단계 결과 자동 사용)
- rag_search(query): 과거 결과 비교 요청 시에만 사용

**주의사항:**
- 사용자 메시지에서 기업명을 정확히 추출하세요
- 기업명이 불명확하면 사용자에게 물어보세요
- 모든 단계를 순서대로 완료하세요

**면책 문구 (모든 최종 응답에 포함):**
"⚠️ 본 결과는 연구·시뮬레이션용 근사치이며 신고/자문 용도로 사용할 수 없습니다."
"""


def format_tool_result_for_llm(tool_name: str, result: Any) -> str:
    """
    도구 실행 결과를 LLM이 이해할 수 있는 형식으로 변환

    Args:
        tool_name: 도구 이름
        result: 도구 실행 결과

    Returns:
        포맷팅된 결과 문자열
    """
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False, indent=2)
    elif isinstance(result, str):
        return result
    else:
        return str(result)
