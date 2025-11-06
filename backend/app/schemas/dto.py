"""
데이터 전송 객체 (DTO) - Pydantic 스키마
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChatRequest(BaseModel):
    """채팅 요청"""
    message: str = Field(..., min_length=1, description="사용자 메시지")
    session_id: Optional[str] = Field(None, description="세션 ID (없으면 새로 생성)")


class ChatResponse(BaseModel):
    """채팅 응답"""
    session_id: str = Field(..., description="세션 ID")
    reply_text: str = Field(..., description="에이전트 응답")
    report_id: Optional[str] = Field(None, description="생성된 리포트 ID")
    download_url: Optional[str] = Field(None, description="PDF 다운로드 URL")


class MessageDTO(BaseModel):
    """메시지 DTO"""
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class CalcResultDTO(BaseModel):
    """계산 결과 DTO"""
    id: str
    corp_name: str
    corp_code: Optional[str]
    calc_date: datetime
    law_param_version: str
    result_json: Dict[str, Any]
    summary_text: Optional[str]
    pdf_path: Optional[str]

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    """헬스체크 응답"""
    status: str = "ok"
    timestamp: datetime
    db_connected: bool
    warnings: List[str] = []
