"""
법인세 계산기 (근사 계산)

⚠️ 면책 사항 ⚠️
본 계산기는 연구 및 시뮬레이션 목적의 근사 계산을 수행합니다.
실제 세무 신고, 세무 자문 용도로 사용할 수 없습니다.
"""
from typing import Dict, Any
import logging
from datetime import datetime

from app.tools.tax_rules import calculate_tax_by_bracket, apply_surtax

logger = logging.getLogger(__name__)


def estimate_taxable_income(financials: Dict[str, Any]) -> float:
    """
    과세표준 근사 계산
    실제로는 복잡한 조정이 필요하지만, 간단히 영업이익 기반으로 근사

    Args:
        financials: 재무 데이터

    Returns:
        근사 과세표준
    """
    # 영업이익 또는 순이익 사용
    operating_income = financials.get("operating_income", 0)
    net_income = financials.get("net_income", 0)

    # 영업이익이 있으면 우선 사용, 없으면 순이익
    base_income = operating_income if operating_income > 0 else net_income

    # 간단한 조정 (실제로는 세무조정이 필요)
    # 여기서는 단순히 80% 정도로 근사 (과세표준이 일반적으로 회계이익보다 낮음)
    estimated_taxable = base_income * 0.8

    logger.info(f"과세표준 근사: {estimated_taxable:,.0f}원 (기준: {base_income:,.0f}원)")

    return max(0, estimated_taxable)  # 음수 방지


def estimate_tax(financials: Dict[str, Any], law_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    법인세 근사 계산

    Args:
        financials: 재무 데이터
        law_params: 법령 파라미터

    Returns:
        계산 결과 상세
    """
    logger.info("법인세 계산 시작")

    # 1. 과세표준 근사
    taxable_income = estimate_taxable_income(financials)

    if taxable_income <= 0:
        logger.warning("과세표준이 0 이하입니다. 세액 0으로 계산")
        return {
            "success": True,
            "taxable_income": taxable_income,
            "corp_tax": 0,
            "surtax": 0,
            "total_tax": 0,
            "effective_rate": 0,
            "bracket_details": [],
            "credits_applied": 0,
            "warnings": ["과세표준이 0 이하입니다."],
            "notes": ["실제 세무 신고에 사용할 수 없습니다."]
        }

    # 2. 구간별 세율 적용
    corp_tax_params = law_params.get("corp_tax", {})
    brackets = corp_tax_params.get("brackets", [])
    surtax_rate = corp_tax_params.get("surtax_rate", 0.10)

    bracket_result = calculate_tax_by_bracket(taxable_income, brackets)
    corp_tax = bracket_result["total_tax"]

    # 3. 세액공제 (간략화: 여기서는 0으로 가정)
    credits = corp_tax_params.get("credits", [])
    credits_applied = 0  # 실제로는 복잡한 계산 필요

    corp_tax_after_credits = max(0, corp_tax - credits_applied)

    # 4. 지방소득세
    surtax = apply_surtax(corp_tax_after_credits, surtax_rate)

    # 5. 총 세액
    total_tax = corp_tax_after_credits + surtax

    # 6. 실효세율
    effective_rate = total_tax / taxable_income if taxable_income > 0 else 0

    result = {
        "success": True,
        "timestamp": datetime.utcnow().isoformat(),
        "law_param_version": law_params.get("version", "unknown"),
        "financials_summary": {
            "revenue": financials.get("revenue", 0),
            "operating_income": financials.get("operating_income", 0),
            "net_income": financials.get("net_income", 0)
        },
        "taxable_income": taxable_income,
        "corp_tax_before_credits": corp_tax,
        "credits_applied": credits_applied,
        "corp_tax": corp_tax_after_credits,
        "surtax": surtax,
        "surtax_rate": surtax_rate,
        "total_tax": total_tax,
        "effective_rate": effective_rate,
        "bracket_details": bracket_result["bracket_details"],
        "warnings": [],
        "notes": [
            "본 결과는 연구/시뮬레이션 목적의 근사치입니다.",
            "실제 세무 신고, 세무 자문 용도로 사용할 수 없습니다.",
            "과세표준은 회계이익 기반 간이 추정치입니다.",
            "세액공제 및 세무조정 사항이 반영되지 않았습니다."
        ]
    }

    logger.info(f"법인세 계산 완료: 총 세액 {total_tax:,.0f}원 (실효세율 {effective_rate*100:.2f}%)")

    return result


def evaluate_result(result: Dict[str, Any], financials: Dict[str, Any]) -> Dict[str, Any]:
    """
    계산 결과 평가 및 검증

    Args:
        result: 계산 결과
        financials: 재무 데이터

    Returns:
        평가 결과
    """
    logger.info("계산 결과 평가 시작")

    warnings = []
    confidence_score = 1.0

    # 1. Sanity check: 세액이 음수인지
    total_tax = result.get("total_tax", 0)
    if total_tax < 0:
        warnings.append("⚠️ 계산된 세액이 음수입니다. 계산 오류 가능성.")
        confidence_score *= 0.5

    # 2. Sanity check: 과세표준이 비정상적으로 큰지
    taxable_income = result.get("taxable_income", 0)
    revenue = financials.get("revenue", 1)
    if taxable_income > revenue * 2:
        warnings.append("⚠️ 과세표준이 매출의 2배를 초과합니다. 데이터 확인 필요.")
        confidence_score *= 0.7

    # 3. 실효세율 체크 (일반적으로 10~30% 사이)
    effective_rate = result.get("effective_rate", 0)
    if effective_rate < 0.05:
        warnings.append("실효세율이 5% 미만입니다. 세액공제가 많거나 과세표준이 낮을 수 있습니다.")
        confidence_score *= 0.9
    elif effective_rate > 0.35:
        warnings.append("실효세율이 35%를 초과합니다. 계산 확인 필요.")
        confidence_score *= 0.8

    # 4. 영업이익 대비 세액 비율 체크
    operating_income = financials.get("operating_income", 0)
    if operating_income > 0:
        tax_to_income_ratio = total_tax / operating_income
        if tax_to_income_ratio > 0.5:
            warnings.append("세액이 영업이익의 50%를 초과합니다. 검토 필요.")
            confidence_score *= 0.8

    evaluation = {
        "confidence_score": max(0.0, min(1.0, confidence_score)),
        "warnings": warnings,
        "passed_checks": len(warnings) == 0,
        "recommendation": "재계산 필요" if confidence_score < 0.7 else "결과 사용 가능 (연구 목적)",
        "notes": [
            "본 평가는 간단한 검증만 수행합니다.",
            "실제 세무 검증은 전문가의 확인이 필요합니다."
        ]
    }

    logger.info(f"평가 완료: 신뢰도 {confidence_score:.2f}, 경고 {len(warnings)}개")

    return evaluation


def format_calc_result_summary(result: Dict[str, Any], evaluation: Dict[str, Any]) -> str:
    """
    계산 결과를 요약 텍스트로 포맷팅

    Args:
        result: 계산 결과
        evaluation: 평가 결과

    Returns:
        요약 텍스트
    """
    taxable_income = result.get("taxable_income", 0)
    corp_tax = result.get("corp_tax", 0)
    surtax = result.get("surtax", 0)
    total_tax = result.get("total_tax", 0)
    effective_rate = result.get("effective_rate", 0)
    confidence = evaluation.get("confidence_score", 0)

    summary = "=" * 50 + "\n"
    summary += "법인세 계산 결과 요약\n"
    summary += "=" * 50 + "\n\n"

    summary += f"과세표준: {taxable_income:,.0f}원\n"
    summary += f"법인세: {corp_tax:,.0f}원\n"
    summary += f"지방소득세: {surtax:,.0f}원\n"
    summary += f"총 세액: {total_tax:,.0f}원\n"
    summary += f"실효세율: {effective_rate*100:.2f}%\n\n"

    summary += f"신뢰도: {confidence*100:.0f}%\n"
    summary += f"평가: {evaluation.get('recommendation', 'N/A')}\n\n"

    if evaluation.get("warnings"):
        summary += "경고:\n"
        for warning in evaluation["warnings"]:
            summary += f"  - {warning}\n"
        summary += "\n"

    summary += "⚠️ 본 결과는 연구/시뮬레이션 목적의 근사치이며\n"
    summary += "   실제 세무 신고/자문 용도로 사용할 수 없습니다.\n"

    return summary
