"""
데이터베이스 세션 관리 및 초기화
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session as DBSession
from contextlib import contextmanager
import logging

from app.config import DB_URL
from app.db.models import Base

logger = logging.getLogger(__name__)

# 엔진 생성
engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DB_URL else {},
    echo=False  # SQL 로깅 (디버깅 시 True)
)

# 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    데이터베이스 초기화
    - 테이블 생성
    - FTS5 가상 테이블 생성
    """
    logger.info("데이터베이스 초기화 시작...")

    # 일반 테이블 생성
    Base.metadata.create_all(bind=engine)
    logger.info("일반 테이블 생성 완료")

    # FTS5 가상 테이블 생성 (SQLite 전용)
    if "sqlite" in DB_URL:
        try:
            with engine.connect() as conn:
                # 기존 FTS5 테이블 확인
                result = conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='rag_fts'"
                ))
                if not result.fetchone():
                    conn.execute(text(
                        "CREATE VIRTUAL TABLE rag_fts USING fts5(doc_id, title, content)"
                    ))
                    conn.commit()
                    logger.info("FTS5 가상 테이블 생성 완료")
                else:
                    logger.info("FTS5 가상 테이블이 이미 존재합니다")
        except Exception as e:
            logger.error(f"FTS5 테이블 생성 실패: {e}")
            logger.warning("FTS5 없이 계속 진행합니다 (검색 기능 제한)")

    logger.info("데이터베이스 초기화 완료")


@contextmanager
def get_db():
    """
    데이터베이스 세션 컨텍스트 매니저
    Usage:
        with get_db() as db:
            db.query(...)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"데이터베이스 오류: {e}")
        raise
    finally:
        db.close()


def get_db_session() -> DBSession:
    """
    FastAPI 의존성 주입용 세션 생성기
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
