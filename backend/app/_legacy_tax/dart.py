"""
DART (Open DART) API 도구
전자공시시스템 API를 통한 기업 재무 정보 조회

참고: https://opendart.fss.or.kr/
"""
import requests
import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime

from app.config import DART_API_KEY
from app.db.session import get_db
from app.db.crud import save_dart_cache, get_dart_cache

logger = logging.getLogger(__name__)

DART_BASE_URL = "https://opendart.fss.or.kr/api"


def _check_api_key() -> bool:
    """API 키 유효성 확인"""
    if not DART_API_KEY or DART_API_KEY == 'YOUR_DART_KEY':
        logger.warning("DART API KEY가 설정되지 않았습니다. 모의 데이터를 사용합니다.")
        return False
    return True


def get_corp_code_by_name(corp_name: str) -> Optional[str]:
    """
    기업명으로 기업 코드 조회

    Args:
        corp_name: 기업명 (예: "삼성전자")

    Returns:
        기업 코드 (예: "00126380") 또는 None
    """
    logger.info(f"기업 코드 조회: {corp_name}")

    # 1. 캐시 확인
    with get_db() as db:
        cache = get_dart_cache(db, None, key=f"corp_code_{corp_name}")
        if cache:
            logger.info(f"캐시에서 기업 코드 조회: {cache.value}")
            return cache.value

    # 2. API 키 확인
    if not _check_api_key():
        # 모의 데이터 반환
        logger.info("모의 데이터 사용: 기업 코드 반환")
        mock_code = _get_mock_corp_code(corp_name)

        # 캐시 저장
        with get_db() as db:
            save_dart_cache(
                db,
                corp_name=corp_name,
                corp_code=mock_code,
                period=None,
                key=f"corp_code_{corp_name}",
                value=mock_code,
                raw_source="mock"
            )

        return mock_code

    # 3. DART API 호출 (기업 검색)
    try:
        # DART에서 기업 코드 검색은 corpCode.xml 다운로드 필요
        # 여기서는 간단히 API 키만 체크하고 모의 데이터 사용
        # 실제 구현 시 corpCode.xml을 다운로드하여 검색
        logger.warning("DART 기업 코드 검색은 corpCode.xml 다운로드가 필요합니다. 모의 데이터 사용.")
        mock_code = _get_mock_corp_code(corp_name)

        # 캐시 저장
        with get_db() as db:
            save_dart_cache(
                db,
                corp_name=corp_name,
                corp_code=mock_code,
                period=None,
                key=f"corp_code_{corp_name}",
                value=mock_code,
                raw_source="mock"
            )

        return mock_code

    except Exception as e:
        logger.error(f"DART API 호출 실패: {e}")
        return None


def get_basic_financials(corp_code: str, corp_name: str = "") -> Dict[str, Any]:
    """
    기업의 기본 재무 정보 조회 (간이)

    Args:
        corp_code: 기업 코드
        corp_name: 기업명 (로깅용)

    Returns:
        재무 정보 딕셔너리
    """
    logger.info(f"재무 정보 조회: {corp_name} ({corp_code})")

    # 1. 캐시 확인
    with get_db() as db:
        cache = get_dart_cache(db, corp_code, key="basic_financials")
        if cache:
            logger.info("캐시에서 재무 정보 조회")
            try:
                return json.loads(cache.value)
            except:
                pass

    # 2. API 키 확인
    if not _check_api_key():
        logger.info("모의 데이터 사용: 재무 정보 반환")
        mock_data = _get_mock_financials(corp_name)

        # 캐시 저장
        with get_db() as db:
            save_dart_cache(
                db,
                corp_name=corp_name,
                corp_code=corp_code,
                period=None,
                key="basic_financials",
                value=json.dumps(mock_data, ensure_ascii=False),
                raw_source="mock"
            )

        return mock_data

    # 3. DART API 호출 (재무제표)
    try:
        # 단일회사 전체 재무제표 API
        url = f"{DART_BASE_URL}/fnlttSinglAcntAll.json"
        params = {
            "crtfc_key": DART_API_KEY,
            "corp_code": corp_code,
            "bsns_year": datetime.now().year - 1,  # 전년도
            "reprt_code": "11011",  # 사업보고서
            "fs_div": "CFS"  # 연결재무제표
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "000":
            logger.warning(f"DART API 응답 오류: {data.get('message')}")
            return _get_mock_financials(corp_name)

        # 재무제표 파싱 (간략화)
        financials = _parse_dart_financials(data, corp_name)

        # 캐시 저장
        with get_db() as db:
            save_dart_cache(
                db,
                corp_name=corp_name,
                corp_code=corp_code,
                period=f"{params['bsns_year']}",
                key="basic_financials",
                value=json.dumps(financials, ensure_ascii=False),
                raw_source=json.dumps(data, ensure_ascii=False)
            )

        logger.info(f"DART 재무 정보 조회 성공")
        return financials

    except Exception as e:
        logger.error(f"DART API 호출 실패: {e}")
        logger.info("폴백: 모의 데이터 사용")
        return _get_mock_financials(corp_name)


def _parse_dart_financials(data: Dict[str, Any], corp_name: str) -> Dict[str, Any]:
    """
    DART API 응답을 파싱하여 재무 정보 추출 (간략화)
    """
    # 실제 구현은 복잡한 파싱이 필요 (계정과목 매칭 등)
    # 여기서는 간략히 처리

    items = data.get("list", [])

    financials = {
        "corp_name": corp_name,
        "year": data.get("bsns_year", "unknown"),
        "revenue": 0,
        "operating_income": 0,
        "net_income": 0,
        "total_assets": 0,
        "total_equity": 0,
        "source": "DART API"
    }

    # 주요 계정과목 매칭 (간략화)
    account_map = {
        "매출액": "revenue",
        "영업이익": "operating_income",
        "당기순이익": "net_income",
        "자산총계": "total_assets",
        "자본총계": "total_equity"
    }

    for item in items:
        account_nm = item.get("account_nm", "")
        thstrm_amount = item.get("thstrm_amount", "0")

        for key, field in account_map.items():
            if key in account_nm:
                try:
                    # 금액 파싱 (쉼표 제거)
                    amount = float(thstrm_amount.replace(",", ""))
                    financials[field] = amount * 1000000  # 백만원 -> 원
                except:
                    pass

    return financials


def _get_mock_corp_code(corp_name: str) -> str:
    """모의 기업 코드 반환"""
    mock_codes = {
        "삼성전자": "00126380",
        "SK하이닉스": "00164779",
        "현대자동차": "00164742",
        "LG전자": "00401731",
        "네이버": "00282659",
        "카카오": "00334624"
    }
    return mock_codes.get(corp_name, "00000000")


def _get_mock_financials(corp_name: str) -> Dict[str, Any]:
    """
    모의 재무 데이터 반환

    ⚠️ 주의: 실제 데이터가 아닙니다. 테스트 및 시연 목적으로만 사용하세요.
    """
    mock_data = {
        "삼성전자": {
            "corp_name": "삼성전자",
            "year": "2023",
            "revenue": 258_000_000_000_000,  # 258조
            "operating_income": 35_000_000_000_000,  # 35조
            "net_income": 25_000_000_000_000,  # 25조
            "total_assets": 448_000_000_000_000,  # 448조
            "total_equity": 300_000_000_000_000,  # 300조
            "source": "mock_data"
        },
        "SK하이닉스": {
            "corp_name": "SK하이닉스",
            "year": "2023",
            "revenue": 55_000_000_000_000,  # 55조
            "operating_income": 5_000_000_000_000,  # 5조
            "net_income": 3_000_000_000_000,  # 3조
            "total_assets": 100_000_000_000_000,  # 100조
            "total_equity": 60_000_000_000_000,  # 60조
            "source": "mock_data"
        }
    }

    if corp_name in mock_data:
        return mock_data[corp_name]

    # 기본 모의 데이터
    return {
        "corp_name": corp_name,
        "year": "2023",
        "revenue": 1_000_000_000_000,  # 1조
        "operating_income": 100_000_000_000,  # 1000억
        "net_income": 80_000_000_000,  # 800억
        "total_assets": 2_000_000_000_000,  # 2조
        "total_equity": 1_000_000_000_000,  # 1조
        "source": "mock_data"
    }
