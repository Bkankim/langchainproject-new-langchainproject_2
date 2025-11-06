"""
RAG 저장 및 검색 도구 (FTS5 기반)
"""
import logging
from typing import List, Dict, Any, Optional
import json

from app.db.session import get_db
from app.db.crud import upsert_rag_doc, search_rag_fts
from app.db.models import RagDoc

logger = logging.getLogger(__name__)


def add_calc_result_to_rag(
    calc_result: Dict[str, Any],
    corp_name: str,
    corp_code: Optional[str] = None
) -> bool:
    """
    계산 결과를 RAG 저장소에 색인

    Args:
        calc_result: 계산 결과 딕셔너리
        corp_name: 기업명
        corp_code: 기업 코드 (옵션)

    Returns:
        성공 여부
    """
    try:
        logger.info(f"RAG 저장: {corp_name} 계산 결과")

        # 검색 가능한 콘텐츠 구성
        title = f"{corp_name} 법인세 계산 결과"
        content = _build_searchable_content(calc_result, corp_name)

        # 메타데이터 구성
        meta = {
            "corp_name": corp_name,
            "corp_code": corp_code,
            "calc_date": calc_result.get("timestamp", ""),
            "law_version": calc_result.get("law_param_version", ""),
            "taxable_income": calc_result.get("taxable_income", 0),
            "total_tax": calc_result.get("total_tax", 0),
            "effective_rate": calc_result.get("effective_rate", 0)
        }

        # RAG 문서로 저장
        with get_db() as db:
            upsert_rag_doc(
                db,
                doc_type="calc_result",
                title=title,
                content=content,
                meta_json=meta
            )

        logger.info(f"RAG 저장 완료: {corp_name}")
        return True

    except Exception as e:
        logger.error(f"RAG 저장 실패: {e}")
        return False


def search_rag(query: str, k: int = 5, corp_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    RAG 검색 (FTS5 기반)

    Args:
        query: 검색 쿼리
        k: 반환할 결과 수
        corp_name: 특정 기업으로 필터링 (옵션)

    Returns:
        검색 결과 리스트
    """
    try:
        logger.info(f"RAG 검색: '{query}' (상위 {k}개)")

        with get_db() as db:
            # FTS5 검색
            docs = search_rag_fts(db, query, k=k * 2)  # 필터링을 고려해 더 많이 조회

            # 기업명 필터링 (옵션)
            if corp_name:
                docs = [
                    doc for doc in docs
                    if doc.meta_json and doc.meta_json.get("corp_name") == corp_name
                ]

            # 상위 k개만 반환
            docs = docs[:k]

            # 결과 포맷팅
            results = []
            for doc in docs:
                results.append({
                    "id": doc.id,
                    "title": doc.title,
                    "content": doc.content,
                    "meta": doc.meta_json or {},
                    "created_at": doc.created_at.isoformat() if doc.created_at else None
                })

            logger.info(f"RAG 검색 완료: {len(results)}개 결과 반환")
            return results

    except Exception as e:
        logger.error(f"RAG 검색 실패: {e}")
        return []


def build_comparison_table(
    current_result: Dict[str, Any],
    past_results: List[Dict[str, Any]]
) -> str:
    """
    현재 결과와 과거 결과를 비교하는 표 생성

    Args:
        current_result: 현재 계산 결과
        past_results: 과거 계산 결과 리스트 (RAG 검색 결과)

    Returns:
        비교표 텍스트
    """
    if not past_results:
        return "No past calculation results found."

    table = "\n" + "=" * 80 + "\n"
    table += "Comparison with Past Results\n"
    table += "=" * 80 + "\n\n"

    # Header (English only for PDF compatibility)
    table += f"{'Date':<20} {'Taxable Income':<25} {'Total Tax':<25} {'Rate':<10}\n"
    table += "-" * 80 + "\n"

    # Past results
    for result in past_results[:5]:
        meta = result.get("meta", {})
        calc_date = meta.get("calc_date", "unknown")[:10]
        taxable = meta.get("taxable_income", 0)
        total_tax = meta.get("total_tax", 0)
        rate = meta.get("effective_rate", 0)

        table += f"{calc_date:<20} {taxable:>23,.0f} KRW {total_tax:>23,.0f} KRW {rate*100:>8.2f}%\n"

    # Current result
    table += "-" * 80 + "\n"
    current_date = current_result.get("timestamp", "")[:10]
    current_taxable = current_result.get("taxable_income", 0)
    current_tax = current_result.get("total_tax", 0)
    current_rate = current_result.get("effective_rate", 0)

    table += f"{'Current (New)':<20} {current_taxable:>23,.0f} KRW {current_tax:>23,.0f} KRW {current_rate*100:>8.2f}%\n"
    table += "=" * 80 + "\n"

    # Change analysis
    if past_results:
        latest_past = past_results[0].get("meta", {})
        past_tax = latest_past.get("total_tax", 0)
        past_taxable = latest_past.get("taxable_income", 0)

        if past_tax > 0:
            tax_change = ((current_tax - past_tax) / past_tax) * 100
            table += f"\nTax change vs latest: {tax_change:+.2f}%\n"

        if past_taxable > 0:
            taxable_change = ((current_taxable - past_taxable) / past_taxable) * 100
            table += f"Taxable income change vs latest: {taxable_change:+.2f}%\n"

    return table


def _build_searchable_content(calc_result: Dict[str, Any], corp_name: str) -> str:
    """
    검색 가능한 콘텐츠 텍스트 생성

    Args:
        calc_result: 계산 결과
        corp_name: 기업명

    Returns:
        검색용 텍스트
    """
    content = f"기업명: {corp_name}\n"
    content += f"계산 일시: {calc_result.get('timestamp', 'unknown')}\n"
    content += f"법령 버전: {calc_result.get('law_param_version', 'unknown')}\n\n"

    # 재무 요약
    financials = calc_result.get("financials_summary", {})
    content += "재무 정보:\n"
    content += f"  매출: {financials.get('revenue', 0):,.0f}원\n"
    content += f"  영업이익: {financials.get('operating_income', 0):,.0f}원\n"
    content += f"  순이익: {financials.get('net_income', 0):,.0f}원\n\n"

    # 계산 결과
    content += "법인세 계산 결과:\n"
    content += f"  과세표준: {calc_result.get('taxable_income', 0):,.0f}원\n"
    content += f"  법인세: {calc_result.get('corp_tax', 0):,.0f}원\n"
    content += f"  지방소득세: {calc_result.get('surtax', 0):,.0f}원\n"
    content += f"  총 세액: {calc_result.get('total_tax', 0):,.0f}원\n"
    content += f"  실효세율: {calc_result.get('effective_rate', 0)*100:.2f}%\n\n"

    # 주요 키워드 (검색 향상)
    content += f"키워드: 법인세 계산 {corp_name} 세액 과세표준 실효세율\n"

    return content


def search_past_results_by_corp(corp_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    특정 기업의 과거 계산 결과 검색

    Args:
        corp_name: 기업명
        limit: 반환할 결과 수

    Returns:
        과거 결과 리스트
    """
    # 기업명으로 검색
    query = f"{corp_name} 법인세 계산"
    return search_rag(query, k=limit, corp_name=corp_name)
