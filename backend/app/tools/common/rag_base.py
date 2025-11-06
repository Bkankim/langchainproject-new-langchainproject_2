"""
RAG (Retrieval-Augmented Generation) 공통 인프라
벡터 저장소, 검색 등 공통 기능
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.db.session import get_db
from app.db.crud import search_rag_docs, add_rag_doc

logger = logging.getLogger(__name__)


def add_to_rag(
    content: str,
    metadata: Dict[str, Any],
    category: str = "general"
) -> str:
    """
    RAG 저장소에 문서 추가

    Args:
        content: 문서 내용
        metadata: 메타데이터 (JSON)
        category: 카테고리 (trend, ad, segment, review, competitor)

    Returns:
        문서 ID
    """
    logger.info(f"RAG 저장: 카테고리={category}")

    with get_db() as db:
        doc_id = add_rag_doc(
            db,
            content=content,
            metadata=metadata,
            category=category
        )

    logger.info(f"RAG 저장 완료: {doc_id}")
    return doc_id


def search_rag(
    query: str,
    category: Optional[str] = None,
    k: int = 5
) -> List[Dict[str, Any]]:
    """
    RAG 저장소에서 검색

    Args:
        query: 검색 쿼리
        category: 카테고리 필터 (옵션)
        k: 결과 개수

    Returns:
        검색 결과 리스트
    """
    logger.info(f"RAG 검색: {query}, 카테고리={category}")

    with get_db() as db:
        results = search_rag_docs(db, query, category, k)

    logger.info(f"RAG 검색 완료: {len(results)}개 결과")
    return results


def build_context_from_rag(
    query: str,
    category: Optional[str] = None,
    k: int = 3
) -> str:
    """
    RAG 검색 결과로 컨텍스트 구성

    Args:
        query: 검색 쿼리
        category: 카테고리
        k: 결과 개수

    Returns:
        컨텍스트 텍스트
    """
    results = search_rag(query, category, k)

    if not results:
        return "관련된 과거 데이터가 없습니다."

    context = "관련 과거 데이터:\n\n"
    for i, result in enumerate(results, 1):
        context += f"{i}. {result.get('content', '')[:200]}...\n\n"

    return context
