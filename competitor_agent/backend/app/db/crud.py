"""
CRUD 유틸리티 함수
"""
from sqlalchemy.orm import Session
from sqlalchemy import text, desc, func
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import logging

from app.db.models import (
    Session as ChatSession,
    Message,
    RagDoc,
    generate_uuid
)

logger = logging.getLogger(__name__)


# ==================== Session ====================

def create_session(db: Session) -> ChatSession:
    """새 채팅 세션 생성"""
    session = ChatSession(id=generate_uuid())
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info(f"새 세션 생성: {session.id}")
    return session


def get_session(db: Session, session_id: str) -> Optional[ChatSession]:
    """세션 조회"""
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()


# ==================== Message ====================

def append_message(db: Session, session_id: str, role: str, content: str) -> Message:
    """메시지 추가"""
    message = Message(
        id=generate_uuid(),
        session_id=session_id,
        role=role,
        content=content
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_messages_by_session(db: Session, session_id: str) -> List[Message]:
    """세션의 모든 메시지 조회 (시간순)"""
    return db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at).all()


# ==================== RagDoc ====================

def upsert_rag_doc(
    db: Session,
    doc_type: str,
    title: str,
    content: str,
    meta_json: Optional[Dict[str, Any]] = None
) -> RagDoc:
    """RAG 문서 저장 (FTS5 색인 포함)"""
    doc = RagDoc(
        id=generate_uuid(),
        doc_type=doc_type,
        title=title,
        content=content,
        meta_json=meta_json or {}
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # FTS5 테이블에 색인
    try:
        db.execute(text(
            "INSERT INTO rag_fts (doc_id, title, content) VALUES (:doc_id, :title, :content)"
        ), {"doc_id": doc.id, "title": title, "content": content})
        db.commit()
        logger.info(f"RAG 문서 및 FTS5 색인 저장: {doc.id}")
    except Exception as e:
        logger.error(f"FTS5 색인 저장 실패: {e}")
        # FTS5 실패해도 문서는 저장됨

    return doc


def search_rag_fts(db: Session, query: str, k: int = 5) -> List[RagDoc]:
    """FTS5 기반 RAG 검색"""
    try:
        # FTS5로 검색
        result = db.execute(text(
            """
            SELECT doc_id FROM rag_fts
            WHERE rag_fts MATCH :query
            ORDER BY rank
            LIMIT :k
            """
        ), {"query": query, "k": k})

        doc_ids = [row[0] for row in result.fetchall()]

        if not doc_ids:
            logger.info(f"FTS5 검색 결과 없음: {query}")
            return []

        # doc_id로 실제 문서 조회
        docs = db.query(RagDoc).filter(RagDoc.id.in_(doc_ids)).all()
        logger.info(f"FTS5 검색 완료: {len(docs)}개 문서 반환")
        return docs

    except Exception as e:
        logger.error(f"FTS5 검색 실패: {e}")
        # 폴백: 단순 LIKE 검색 (SQL Injection 방어)
        logger.info("폴백: 단순 LIKE 검색 사용")
        return db.query(RagDoc).filter(
            RagDoc.content.like(func.concat('%', query, '%'))
        ).limit(k).all()
