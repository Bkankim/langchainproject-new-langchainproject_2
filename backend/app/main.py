"""
FastAPI 메인 애플리케이션
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import logging
import sys

from app.config import validate_config, REPORT_DIR
from app.db.session import init_db
from app.routes import chat, report
from app.schemas.dto import HealthResponse

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="커머스 마케팅 에이전트 API",
    description="커머스 마케팅 분석 및 리포트 생성 API (트렌드 분석, 광고 문구, 사용자 세그먼트, 리뷰 분석, 경쟁사 분석)",
    version="0.1.0"
)

# CORS 설정 (프론트엔드 접근 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite 기본 포트
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """
    앱 시작 시 실행
    - DB 초기화
    - 설정 검증
    - 디렉토리 생성
    """
    logger.info("=" * 60)
    logger.info("커머스 마케팅 에이전트 시작")
    logger.info("=" * 60)

    # 1. 디렉토리 생성
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"리포트 디렉토리: {REPORT_DIR}")

    # 2. 설정 검증
    warnings = validate_config()
    if warnings:
        logger.warning("설정 경고:")
        for warning in warnings:
            logger.warning(f"  {warning}")

    # 3. DB 초기화
    try:
        init_db()
        logger.info("데이터베이스 초기화 완료")
    except Exception as e:
        logger.error(f"데이터베이스 초기화 실패: {e}")
        raise

    logger.info("=" * 60)
    logger.info("커머스 마케팅 에이전트 준비 완료")
    logger.info("API 문서: http://localhost:8000/docs")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """앱 종료 시 실행"""
    logger.info("커머스 마케팅 에이전트 종료")


# 라우터 등록
app.include_router(chat.router, tags=["Chat"])
app.include_router(report.router, tags=["Report"])


@app.get("/", tags=["Root"])
async def root():
    """루트 엔드포인트"""
    return {
        "service": "커머스 마케팅 에이전트 API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/healthz", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """헬스체크 엔드포인트"""
    from app.config import validate_config

    # DB 연결 확인
    db_connected = True
    try:
        from app.db.session import get_db
        with get_db() as db:
            db.execute("SELECT 1")
    except:
        db_connected = False

    warnings = validate_config()

    return HealthResponse(
        status="ok" if db_connected else "degraded",
        timestamp=datetime.utcnow(),
        db_connected=db_connected,
        warnings=warnings
    )


if __name__ == "__main__":
    import uvicorn

    # 개발 서버 실행
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
