"""
채팅 라우트
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import logging

from app.schemas.dto import ChatRequest, ChatResponse
from app.agents.router import route_to_agent  # 🆕 라우터 사용

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    채팅 엔드포인트

    사용자 메시지를 받아 에이전트를 실행하고 응답 반환
    """
    try:
        logger.info(f"채팅 요청 수신: {request.message[:50]}...")

        # 라우터로 에이전트 실행 🆕
        result = route_to_agent(
            session_id=request.session_id or "",
            user_message=request.message
        )

        # 실패한 경우에도 안내 메시지를 반환 (HTTP 200)
        # 태스크를 못 찾거나 에이전트가 미구현인 경우도 정상 응답으로 처리
        if not result.get("success") and "Unknown task" not in result.get("errors", []):
            # 실제 에러인 경우에만 500 에러
            if "Agent not implemented" not in result.get("errors", []):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("reply_text", "에이전트 실행 실패")
                )

        # 응답 구성
        response = ChatResponse(
            session_id=result["session_id"],
            reply_text=result["reply_text"],
            report_id=result.get("report_id"),
            download_url=result.get("download_url")
        )

        logger.info(f"채팅 응답 반환 (세션: {response.session_id})")

        return response

    except HTTPException:
        raise
    except Exception as e:
        # 상세 에러는 로그에만 기록
        logger.error(f"채팅 처리 실패: {e}", exc_info=True)
        # 사용자에게는 일반적인 메시지만 반환 (내부 정보 유출 방지)
        raise HTTPException(
            status_code=500,
            detail="서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        )
