"""
데이터베이스 모델 정의
SQLAlchemy를 사용한 SQLite 테이블 정의
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON, Integer, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()


def generate_uuid():
    """UUID 생성 헬퍼"""
    return str(uuid.uuid4())


class Session(Base):
    """채팅 세션 테이블"""
    __tablename__ = 'sessions'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 관계 정의
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    """채팅 메시지 테이블 (멀티턴 히스토리)"""
    __tablename__ = 'messages'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey('sessions.id'), nullable=False)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 관계 정의
    session = relationship("Session", back_populates="messages")


# 법인세 관련 테이블 제거됨 (LawParamSnapshot, DartCache, CalcResult)


class RagDoc(Base):
    """RAG 문서 저장 테이블 (커머스 마케팅용)"""
    __tablename__ = 'rag_docs'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    category = Column(String(50), nullable=False)  # 'trend', 'ad', 'segment', 'review', 'competitor'
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)  # 검색 대상 텍스트
    meta_json = Column(JSON, nullable=True)  # 태스크별 메타데이터
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TaskResult(Base):
    """태스크 실행 결과 저장 테이블 (종합 보고서용)"""
    __tablename__ = 'task_results'

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey('sessions.id'), nullable=False, index=True)
    task_type = Column(String(20), nullable=False)  # 'trend', 'ad_copy', 'segment', 'review', 'competitor'

    # 핵심: 구조화된 데이터 (JSON)
    result_data = Column(JSON, nullable=False)

    # 메타데이터
    product_name = Column(String(200), nullable=True)  # 분석 대상 제품명
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 생성된 파일 경로 (선택)
    pdf_path = Column(String(500), nullable=True)
    html_path = Column(String(500), nullable=True)

    # 관계 정의
    session = relationship("Session", backref="task_results")


# FTS5 가상 테이블은 raw SQL로 생성 (session.py에서 처리)
# CREATE VIRTUAL TABLE rag_fts USING fts5(doc_id, title, content)
