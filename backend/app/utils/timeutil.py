"""
시간 유틸리티 함수
"""
from datetime import datetime, timezone


def get_current_timestamp() -> datetime:
    """현재 UTC 타임스탬프 반환"""
    return datetime.now(timezone.utc)


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """datetime을 문자열로 포맷팅"""
    return dt.strftime(fmt)


def get_current_date_str() -> str:
    """현재 날짜를 YYYY-MM-DD 형식으로 반환"""
    return datetime.now().strftime("%Y-%m-%d")
