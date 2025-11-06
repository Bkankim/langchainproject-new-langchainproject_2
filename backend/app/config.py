"""
설정 파일 - 환경 변수 로드 및 관리
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# OpenAI 설정
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
OPENAI_EMBED_MODEL = os.getenv('OPENAI_EMBED_MODEL', 'text-embedding-3-small')


# DART API 설정
DART_API_KEY = os.getenv('DART_API_KEY', '')

# Naver DataLab API 설정 (트렌드 분석용)
NAVER_CLIENT_ID = os.getenv('NAVER_DATALAB_CLIENT_ID', '')
NAVER_CLIENT_SECRET = os.getenv('NAVER_DATALAB_CLIENT_SECRET', '')
NAVER_DATALAB_URL = os.getenv(
    'NAVER_DATALAB_URL', 'https://openapi.naver.com/v1/datalab/search')

# Naver Shopping API 설정 (경쟁사 분석용)
NAVER_SHOPPING_CLIENT_ID = os.getenv('NAVER_SHOPPING_CLIENT_ID', '')
NAVER_SHOPPING_CLIENT_SECRET = os.getenv('NAVER_SHOPPING_CLIENT_SECRET', '')

# 데이터베이스 설정
DB_URL = os.getenv('DB_URL', 'sqlite:///./corp_tax_agent.db')

# 리포트 디렉토리 설정
REPORT_DIR = Path(os.getenv('REPORT_DIR', './reports'))

# 디렉토리 생성
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# 보안: API 키 검증 (개발 모드에서는 경고만)


def validate_config():
    """설정 유효성 검사"""
    warnings = []

    if not OPENAI_API_KEY or OPENAI_API_KEY == 'YOUR_OPENAI_KEY':
        warnings.append("⚠️ OPENAI_API_KEY가 설정되지 않았습니다.")

    if not DART_API_KEY or DART_API_KEY == 'YOUR_DART_KEY':
        warnings.append(
            "⚠️ DART_API_KEY가 설정되지 않았습니다. DART 조회 시 모의 데이터를 사용합니다.")

    return warnings
