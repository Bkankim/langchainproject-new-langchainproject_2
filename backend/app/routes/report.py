"""
리포트 다운로드 라우트 (커머스 마케팅)
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/report/{filename}")
async def download_report(filename: str):
    """
    PDF 리포트 다운로드

    Args:
        filename: PDF 파일명 (예: segment_report_20240101_123456.pdf)

    Returns:
        PDF 파일 스트림
    """
    try:
        logger.info(f"리포트 다운로드 요청: {filename}")

        # 보안: 파일명 검증 (경로 탐색 공격 방지)
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")

        # reports 디렉토리에서 파일 찾기
        pdf_path = Path("reports") / filename

        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="리포트 파일을 찾을 수 없습니다.")

        logger.info(f"리포트 전송: {pdf_path}")

        # 파일 반환
        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리포트 다운로드 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")
