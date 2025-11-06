"""
법인세 파라미터 템플릿 (하드코딩)

⚠️ 중요 면책 사항 ⚠️
===========================================
본 파일의 세율 및 파라미터는 연구/시뮬레이션 목적의 임시 템플릿입니다.
실제 세무 신고, 세무 자문, 또는 공식 계산 용도로 사용할 수 없습니다.

정식 법령 API 승인 후 실제 세율/구간/공제 항목으로 업데이트될 예정입니다.
현재 값은 예시 목적이며 실제 법인세법과 다를 수 있습니다.
===========================================
"""
from typing import Dict, Any
from datetime import datetime
import logging

from app.db.session import get_db
from app.db.crud import save_law_param_snapshot, get_latest_law_param_snapshot

logger = logging.getLogger(__name__)

# 하드코딩 법인세 파라미터 템플릿 (임시)
LAW_PARAMS = {
    "version": "v0.1-local-template",
    "effective_date": "2024-01-01",
    "description": "임시 연구용 템플릿 - 실제 세무 목적 사용 불가",
    "corp_tax": {
        "brackets": [
            {
                "threshold": 200000000,  # 2억 이하
                "rate": 0.10,  # 10%
                "description": "과세표준 2억 이하"
            },
            {
                "threshold": 20000000000,  # 200억 이하
                "rate": 0.20,  # 20%
                "description": "과세표준 2억 초과 200억 이하"
            },
            {
                "threshold": 300000000000,  # 3000억 이하
                "rate": 0.22,  # 22%
                "description": "과세표준 200억 초과 3000억 이하"
            },
            {
                "threshold": float('inf'),  # 3000억 초과
                "rate": 0.25,  # 25%
                "description": "과세표준 3000억 초과"
            }
        ],
        "surtax_rate": 0.10,  # 지방소득세 10% (법인세의 10%)
        "credits": [
            {
                "name": "R&D 세액공제",
                "rate": 0.0,  # 임시 0% (실제는 복잡한 계산)
                "cap": None,
                "description": "연구개발 세액공제 (간략화)"
            },
            {
                "name": "고용증대 세액공제",
                "rate": 0.0,
                "cap": None,
                "description": "고용증대 세액공제 (간략화)"
            }
        ],
        "deductions": {
            "basic_deduction": 0,  # 기본 공제 (임시 0)
            "description": "각종 소득공제 (간략화)"
        }
    },
    "notes": [
        "이 템플릿은 임시 연구용입니다.",
        "실제 세무 신고에 사용할 수 없습니다.",
        "법령 API 승인 후 정식 파라미터로 업데이트 예정입니다.",
        "구간별 세율은 예시이며 실제 법인세법과 다를 수 있습니다."
    ]
}


def get_current_law_params() -> Dict[str, Any]:
    """
    현재 법령 파라미터 조회
    - DB에 최신 스냅샷이 있으면 반환
    - 없으면 LAW_PARAMS를 DB에 저장 후 반환
    """
    with get_db() as db:
        # 최신 스냅샷 조회
        snapshot = get_latest_law_param_snapshot(db)

        if snapshot:
            logger.info(f"기존 법령 파라미터 사용: {snapshot.version}")
            return snapshot.json_blob

        # 없으면 템플릿 저장
        logger.info("법령 파라미터 템플릿 최초 저장")
        snapshot = save_law_param_snapshot(
            db,
            version=LAW_PARAMS["version"],
            params=LAW_PARAMS
        )
        return snapshot.json_blob


def calculate_tax_by_bracket(taxable_income: float, brackets: list) -> Dict[str, Any]:
    """
    구간별 세율 적용 계산

    Args:
        taxable_income: 과세표준
        brackets: 세율 구간 리스트

    Returns:
        계산 상세 결과
    """
    if taxable_income <= 0:
        return {
            "taxable_income": taxable_income,
            "total_tax": 0,
            "bracket_details": [],
            "effective_rate": 0
        }

    total_tax = 0
    bracket_details = []
    prev_threshold = 0

    # 구간별 세액 계산
    for i, bracket in enumerate(brackets):
        threshold = bracket["threshold"]
        rate = bracket["rate"]

        # 현재 구간에서 과세되는 금액
        if taxable_income > threshold:
            # 전체 구간 과세
            taxable_in_bracket = threshold - prev_threshold
        else:
            # 일부 구간만 과세
            taxable_in_bracket = taxable_income - prev_threshold

        if taxable_in_bracket > 0:
            tax_in_bracket = taxable_in_bracket * rate
            total_tax += tax_in_bracket

            bracket_details.append({
                "bracket_index": i,
                "threshold": threshold,
                "rate": rate,
                "taxable_amount": taxable_in_bracket,
                "tax_amount": tax_in_bracket,
                "description": bracket.get("description", "")
            })

        prev_threshold = threshold

        # 마지막 구간이거나 과세표준이 현재 구간 이하면 종료
        if taxable_income <= threshold:
            break

    effective_rate = total_tax / taxable_income if taxable_income > 0 else 0

    return {
        "taxable_income": taxable_income,
        "total_tax": total_tax,
        "bracket_details": bracket_details,
        "effective_rate": effective_rate
    }


def apply_surtax(corp_tax: float, surtax_rate: float) -> float:
    """지방소득세 계산 (법인세의 일정 비율)"""
    return corp_tax * surtax_rate


def format_law_params_summary(params: Dict[str, Any]) -> str:
    """법령 파라미터 요약 텍스트 생성"""
    version = params.get("version", "unknown")
    effective_date = params.get("effective_date", "unknown")
    corp_tax = params.get("corp_tax", {})
    brackets = corp_tax.get("brackets", [])
    surtax_rate = corp_tax.get("surtax_rate", 0)

    summary = f"법령 파라미터 버전: {version}\n"
    summary += f"적용 기준일: {effective_date}\n"
    summary += f"지방소득세율: {surtax_rate * 100}%\n\n"
    summary += "구간별 세율:\n"

    for i, bracket in enumerate(brackets):
        threshold = bracket.get("threshold")
        rate = bracket.get("rate")
        desc = bracket.get("description", "")

        if threshold == float('inf'):
            summary += f"  {i+1}. {desc}: {rate * 100}%\n"
        else:
            summary += f"  {i+1}. {desc}: {rate * 100}%\n"

    summary += "\n⚠️ 본 파라미터는 연구용 임시 템플릿이며 실제 세무 신고에 사용할 수 없습니다.\n"

    return summary
