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
    리포트 다운로드 (PDF 또는 HTML)

    Args:
        filename: 파일명 (예: segment_report_20240101_123456.pdf, competitor_report_20240101_123456.html)

    Returns:
        파일 스트림
    """
    try:
        logger.info(f"리포트 다운로드 요청: {filename}")

        # 보안: 파일명 검증 (경로 탐색 공격 방지)
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")

        # reports 디렉토리에서 파일 찾기
        file_path = Path("reports") / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="리포트 파일을 찾을 수 없습니다.")

        logger.info(f"리포트 전송: {file_path}")

        # 파일 확장자에 따라 media_type 결정
        if filename.endswith(".html"):
            media_type = "text/html"
        elif filename.endswith(".pdf"):
            media_type = "application/pdf"
        else:
            # 지원하지 않는 형식
            raise HTTPException(status_code=400, detail="지원하지 않는 파일 형식입니다.")

        # 파일 반환
        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리포트 다운로드 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")
