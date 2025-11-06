"""
CRUD 유틸리티 함수
"""
from sqlalchemy.orm import Session
from sqlalchemy import text, desc
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import logging

from app.db.models import (
    Session as ChatSession,
    Message,
    RagDoc,
    TaskResult,
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
        # 폴백: 단순 LIKE 검색
        logger.info("폴백: 단순 LIKE 검색 사용")
        return db.query(RagDoc).filter(
            RagDoc.content.like(f"%{query}%")
        ).limit(k).all()


def add_rag_doc(
    db: Session,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    category: str = "general"
) -> str:
    """
    RAG 문서 저장 후 FTS 색인

    Args:
        db: DB 세션
        content: 저장할 본문
        metadata: 추가 메타데이터(JSON)
        category: 카테고리

    Returns:
        저장된 문서 ID
    """
    metadata = metadata or {}
    title = metadata.get("title") or metadata.get("product_name")

    if not title:
        first_line = content.splitlines()[0] if content else category
        title = first_line[:200] if first_line else f"{category} 기록"

    doc = RagDoc(
        id=generate_uuid(),
        category=category,
        title=title,
        content=content,
        meta_json=metadata,
        created_at=datetime.utcnow()
    )

    db.add(doc)
    db.commit()
    db.refresh(doc)

    # FTS5 색인 업데이트
    try:
        db.execute(text(
            "INSERT INTO rag_fts (doc_id, title, content) VALUES (:doc_id, :title, :content)"
        ), {"doc_id": doc.id, "title": doc.title, "content": doc.content})
        db.commit()
        logger.info(f"RAG 문서 저장 및 색인 완료: {doc.id}")
    except Exception as e:
        logger.warning(f"RAG FTS 색인 실패: {e}")

    return doc.id


def search_rag_docs(
    db: Session,
    query: str,
    category: Optional[str] = None,
    k: int = 5
) -> List[Dict[str, Any]]:
    """
    카테고리 필터를 포함한 RAG 검색

    Args:
        db: DB 세션
        query: 검색어
        category: 카테고리 필터
        k: 반환 개수

    Returns:
        검색 결과 딕셔너리 리스트
    """
    docs = search_rag_fts(db, query, k * 2)

    if category:
        docs = [doc for doc in docs if doc.category == category]

    if not docs:
        # FTS 결과가 없으면 직접 검색
        query_obj = db.query(RagDoc)
        if category:
            query_obj = query_obj.filter(RagDoc.category == category)
        docs = query_obj.filter(RagDoc.content.like(f"%{query}%")).order_by(
            desc(RagDoc.created_at)
        ).limit(k).all()

    results: List[Dict[str, Any]] = []
    for doc in docs[:k]:
        results.append({
            "id": doc.id,
            "category": doc.category,
            "title": doc.title,
            "content": doc.content,
            "metadata": doc.meta_json or {},
            "created_at": doc.created_at.isoformat() if doc.created_at else None
        })

    return results


# ==================== TaskResult ====================

def save_task_result(
    db: Session,
    session_id: str,
    task_type: str,
    result_data: Dict[str, Any],
    product_name: Optional[str] = None,
    pdf_path: Optional[str] = None,
    html_path: Optional[str] = None
) -> TaskResult:
    """
    태스크 실행 결과를 DB에 저장

    Args:
        db: DB 세션
        session_id: 세션 ID
        task_type: 태스크 타입 ('trend', 'ad_copy', 'segment', 'review', 'competitor')
        result_data: 구조화된 결과 데이터 (dict)
        product_name: 분석 대상 제품명
        pdf_path: 생성된 PDF 경로
        html_path: 생성된 HTML 경로

    Returns:
        저장된 TaskResult 객체
    """
    task_result = TaskResult(
        id=generate_uuid(),
        session_id=session_id,
        task_type=task_type,
        result_data=result_data,
        product_name=product_name,
        pdf_path=pdf_path,
        html_path=html_path,
        created_at=datetime.utcnow()
    )

    db.add(task_result)
    db.commit()
    db.refresh(task_result)

    logger.info(f"태스크 결과 저장 완료: {task_type} (세션: {session_id})")
    return task_result


def get_task_results_by_session(
    db: Session,
    session_id: str,
    task_type: Optional[str] = None,
    product_name: Optional[str] = None
) -> List[TaskResult]:
    """
    세션의 태스크 결과 조회

    Args:
        db: DB 세션
        session_id: 세션 ID
        task_type: 특정 태스크만 조회 (선택)
        product_name: 특정 제품만 조회 (선택)

    Returns:
        TaskResult 리스트 (시간순)
    """
    query = db.query(TaskResult).filter(TaskResult.session_id == session_id)

    if task_type:
        query = query.filter(TaskResult.task_type == task_type)

    if product_name:
        query = query.filter(TaskResult.product_name == product_name)

    results = query.order_by(TaskResult.created_at).all()
    logger.info(f"태스크 결과 조회: {len(results)}개 (세션: {session_id}, 제품: {product_name or '전체'})")
    return results


def get_latest_task_result(
    db: Session,
    session_id: str,
    task_type: str
) -> Optional[TaskResult]:
    """
    특정 태스크의 가장 최근 결과 조회

    Args:
        db: DB 세션
        session_id: 세션 ID
        task_type: 태스크 타입

    Returns:
        가장 최근 TaskResult 또는 None
    """
    return db.query(TaskResult).filter(
        TaskResult.session_id == session_id,
        TaskResult.task_type == task_type
    ).order_by(desc(TaskResult.created_at)).first()
