"""
종합 보고서 생성 도구
여러 태스크 결과를 종합하여 마케팅 전략 보고서 생성
"""
import logging
import json
import os
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.config import OPENAI_API_KEY, OPENAI_MODEL
from openai import OpenAI

import matplotlib
matplotlib.use('Agg')  # GUI 없이 사용
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib import rc
import seaborn as sns
import numpy as np
import pandas as pd

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT

logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# 한글 폰트 및 Seaborn 스타일 설정
try:
    font_path = "C:/Windows/Fonts/malgun.ttf"
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('Malgun', font_path))
        # matplotlib 한글 폰트 설정
        plt.rcParams['font.family'] = 'Malgun Gothic'
        plt.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지

        # Seaborn 스타일 설정 (더 예쁜 차트)
        sns.set_theme(style="whitegrid")
        sns.set_palette("husl")  # 밝고 선명한 색상 팔레트

        logger.info("한글 폰트 및 Seaborn 스타일 설정 완료")
    else:
        logger.warning("한글 폰트를 찾을 수 없습니다. 기본 폰트를 사용합니다.")
except Exception as e:
    logger.warning(f"폰트 설정 실패: {e}")


def _fix_bold_tags(text: str) -> str:
    """
    마크다운 ** 기호를 올바르게 <b></b> 태그로 변환

    Args:
        text: 원본 텍스트

    Returns:
        HTML 태그로 변환된 텍스트
    """
    # ** 기호가 없으면 그대로 반환
    if '**' not in text:
        return text

    # ** 기호를 모두 찾아서 순서대로 <b>, </b>로 교체
    result = []
    parts = text.split('**')

    for i, part in enumerate(parts):
        if i == 0:
            # 첫 번째 부분은 그대로
            result.append(part)
        elif i % 2 == 1:
            # 홀수 번째: 볼드 시작
            result.append(f"<b>{part}")
        else:
            # 짝수 번째: 볼드 끝
            result.append(f"</b>{part}")

    # 마지막에 닫히지 않은 <b> 태그가 있으면 닫기
    final_text = ''.join(result)
    open_count = final_text.count('<b>')
    close_count = final_text.count('</b>')

    if open_count > close_count:
        final_text += '</b>' * (open_count - close_count)

    return final_text


def estimate_tokens(task_data_list: List[Dict[str, Any]]) -> int:
    """태스크 결과의 토큰 수 추정"""
    total = 0
    for task_data in task_data_list:
        json_str = json.dumps(task_data['result_data'], ensure_ascii=False)
        # 한글 기준: 3글자 ≈ 1토큰
        total += len(json_str) // 3
    return total


def synthesize_marketing_strategy(task_data_list: List[Dict[str, Any]]) -> str:
    """
    모든 태스크 결과를 종합하여 마케팅 전략 생성

    Args:
        task_data_list: 태스크 데이터 딕셔너리 리스트

    Returns:
        종합 마케팅 전략 텍스트
    """
    if not client:
        return "OpenAI API 키가 설정되지 않아 종합 보고서를 생성할 수 없습니다."

    # 태스크별 데이터 추출
    task_data_map = {}
    for task_data in task_data_list:
        task_data_map[task_data['task_type']] = task_data['result_data']

    # 프롬프트 구성
    prompt = f"""당신은 경험이 풍부한 마케팅 전략 컨설턴트입니다.
다음 분석 결과들을 종합하여 실행 가능한 통합 마케팅 전략 보고서를 작성하세요.

# 입력 데이터

## 1. 트렌드 분석
{json.dumps(task_data_map.get('trend', {}), ensure_ascii=False, indent=2)}

## 2. 광고 문구
{json.dumps(task_data_map.get('ad_copy', {}), ensure_ascii=False, indent=2)}

## 3. 세그먼트 분류
{json.dumps(task_data_map.get('segment', {}), ensure_ascii=False, indent=2)}

## 4. 리뷰 감성 분석
{json.dumps(task_data_map.get('review', {}), ensure_ascii=False, indent=2)}

## 5. 경쟁사 분석
{json.dumps(task_data_map.get('competitor', {}), ensure_ascii=False, indent=2)}

# 작성 지침

1. 데이터를 심층적으로 분석하고 인사이트를 도출하세요
2. 각 섹션을 구체적이고 실행 가능한 내용으로 작성하세요
3. 수치와 데이터를 적극 활용하세요
4. 각 세그먼트별 맞춤 전략을 제시하세요
5. 실행 계획은 구체적인 기간과 KPI를 포함하세요

# 출력 형식

## 📊 Executive Summary
제품의 시장 포지션, 핵심 발견사항, 주요 기회와 위협을 5-7문장으로 명확하게 요약하세요.

## 🌐 시장 환경 분석

### 트렌드 현황
- 검색 트렌드 변화 분석 (구체적 수치 포함)
- 연관 검색어 분석
- 시즌성 및 주요 이벤트 영향

### 경쟁 환경
- SWOT 분석 요약 (각 항목별 2-3개)
- 경쟁사 대비 강점과 약점
- 시장 내 포지셔닝

### 기회와 위협
- 시장 기회 요인 (최소 3개)
- 위협 요인 및 대응 방안 (최소 3개)

## 👥 고객 인사이트

### 세그먼트별 특성
각 고객 세그먼트에 대해:
- 주요 특징 및 니즈
- 구매 동기와 의사결정 요인
- 선호하는 커뮤니케이션 방식

### 고객 감성 분석
- 긍정적 요인 (구체적 수치)
- 부정적 요인 및 개선점
- 중립 고객의 전환 전략

## 🎯 마케팅 전략 제안

### 세그먼트별 전략
각 세그먼트를 위한 맞춤 전략:
- 타겟 메시지 (광고 문구 활용)
- 채널 전략
- 프로모션 방안

### 콘텐츠 마케팅
- 블로그/SNS 콘텐츠 주제
- 인플루언서 협업 방안
- SEO 최적화 키워드

### 리텐션 전략
- 기존 고객 유지 방안
- 재구매 유도 전략
- 로열티 프로그램

## 📅 실행 계획

### 단기 (1-3개월)
- 구체적 액션 아이템 (최소 5개)
- 담당 부서 제안
- 예상 예산 범위
- KPI 지표

### 중기 (3-6개월)
- 구체적 액션 아이템 (최소 5개)
- 담당 부서 제안
- 예상 예산 범위
- KPI 지표

### 장기 (6-12개월)
- 구체적 액션 아이템 (최소 3개)
- 담당 부서 제안
- 예상 예산 범위
- KPI 지표

각 섹션을 풍부하고 구체적으로 작성하세요. 단순한 요약이 아니라, 실제 마케팅 팀이 바로 실행할 수 있는 수준의 상세함을 유지하세요.
"""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "당신은 경험이 풍부한 마케팅 전략 컨설턴트입니다. 데이터 기반의 구체적이고 실행 가능한 전략을 제시합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=8000  # 더 상세한 보고서를 위해 증가
        )

        result_text = response.choices[0].message.content
        logger.info("종합 마케팅 전략 생성 완료")
        return result_text

    except Exception as e:
        logger.error(f"LLM 종합 분석 실패: {e}", exc_info=True)
        return f"종합 분석 중 오류가 발생했습니다: {str(e)}"


def execute_chart_codes(chart_codes: List[str], output_dir: str = "reports") -> List[str]:
    """
    LLM이 생성한 차트 코드를 안전하게 실행

    Args:
        chart_codes: Python 코드 문자열 리스트
        output_dir: 차트 저장 디렉토리

    Returns:
        생성된 차트 파일 경로 리스트
    """
    os.makedirs(output_dir, exist_ok=True)
    generated_charts = []

    for i, code in enumerate(chart_codes, 1):
        try:
            logger.info(f"차트 코드 {i}/{len(chart_codes)} 실행 중...")

            # 안전한 실행 환경 설정
            safe_globals = {
                "__builtins__": __builtins__,
                "matplotlib": matplotlib,
                "plt": plt,
                "sns": sns,
                "np": np,
                "pd": pd,
                "os": os,
            }

            # 코드 실행
            exec(code, safe_globals)
            logger.info(f"차트 코드 {i} 실행 완료")

            # 생성된 파일 확인 (synthesis_chart_N.png 패턴)
            expected_path = os.path.join(output_dir, f"synthesis_chart_{i}.png")
            if os.path.exists(expected_path):
                generated_charts.append(expected_path)
                logger.info(f"차트 파일 생성 확인: {expected_path}")
            else:
                logger.warning(f"예상 경로에 차트 파일이 없음: {expected_path}")

        except Exception as e:
            logger.error(f"차트 코드 {i} 실행 실패: {e}", exc_info=True)
            continue

    logger.info(f"총 {len(generated_charts)}개 차트 생성 완료")
    return generated_charts


def create_synthesis_charts(task_data_map: Dict[str, Any], output_dir: str = "reports") -> Dict[str, str]:
    """
    종합 보고서용 차트 생성 (레거시 함수 - 더 이상 사용하지 않음)

    Returns:
        생성된 차트 파일 경로 딕셔너리
    """
    os.makedirs(output_dir, exist_ok=True)
    chart_paths = {}

    logger.info(f"차트 생성 시작. 태스크 데이터 맵 키: {list(task_data_map.keys())}")

    try:
        # 1. 트렌드 시계열 차트
        if 'trend' in task_data_map:
            trend_data = task_data_map['trend']
            trend_series = trend_data.get('trend_series', [])

            if trend_series:
                logger.info(f"트렌드 차트 생성 시작: {len(trend_series)}개 데이터 포인트")
                fig, ax = plt.subplots(figsize=(10, 5))
                dates = [item['date'] for item in trend_series[:30]]  # 최근 30개
                values = [item['value'] for item in trend_series[:30]]

                ax.plot(dates, values, marker='o', linewidth=2, markersize=4, color='#1976D2')
                ax.set_title(f'{trend_data.get("keyword", "제품")} 검색 트렌드', fontsize=14, pad=15)
                ax.set_xlabel('기간', fontsize=11)
                ax.set_ylabel('검색 지수', fontsize=11)
                ax.grid(True, alpha=0.3)
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()

                chart_path = os.path.join(output_dir, f"synthesis_trend_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
                plt.savefig(chart_path, dpi=150, bbox_inches='tight')
                plt.close()
                chart_paths['trend'] = chart_path
                logger.info(f"트렌드 차트 생성 완료: {chart_path}")
            else:
                logger.warning("트렌드 데이터가 비어있어 차트를 생성하지 못했습니다.")

        # 2. 세그먼트 분포 파이 차트
        if 'segment' in task_data_map:
            segment_data = task_data_map['segment']
            segments = segment_data.get('segments', [])

            if segments and isinstance(segments, list):
                try:
                    logger.info(f"세그먼트 차트 생성 시작: {len(segments)}개 세그먼트")
                    fig, ax = plt.subplots(figsize=(8, 8))

                    # 세그먼트가 dict인지 확인
                    labels = []
                    sizes = []
                    for i, seg in enumerate(segments):
                        if isinstance(seg, dict):
                            labels.append(seg.get('segment_name', f'세그먼트 {i+1}'))
                            sizes.append(seg.get('percentage', 0))
                        else:
                            logger.warning(f"세그먼트 항목이 dict가 아님: {type(seg)}")
                            labels.append(f'세그먼트 {i+1}')
                            sizes.append(100 / len(segments))

                    colors_list = plt.cm.Set3(range(len(segments)))
                    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors_list)
                    ax.set_title('고객 세그먼트 분포', fontsize=14, pad=20)

                    chart_path = os.path.join(output_dir, f"synthesis_segments_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
                    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
                    plt.close()
                    chart_paths['segments'] = chart_path
                    logger.info(f"세그먼트 차트 생성 완료: {chart_path}")
                except Exception as e:
                    logger.error(f"세그먼트 차트 생성 실패: {e}")

        # 3. 리뷰 감성 분포 바 차트 (Seaborn 스타일)
        if 'review' in task_data_map:
            review_data = task_data_map['review']
            sentiment_dist = review_data.get('sentiment_distribution', {})

            if sentiment_dist:
                fig, ax = plt.subplots(figsize=(10, 6))
                sentiments = list(sentiment_dist.keys())
                counts = list(sentiment_dist.values())

                # Seaborn 바 차트
                sentiment_names_kr = {
                    'positive': '긍정',
                    'neutral': '중립',
                    'negative': '부정'
                }
                sentiments_kr = [sentiment_names_kr.get(s, s) for s in sentiments]
                colors_map = {'positive': '#4CAF50', 'neutral': '#FFC107', 'negative': '#F44336'}
                bar_colors = [colors_map.get(s, '#2196F3') for s in sentiments]

                bars = sns.barplot(x=sentiments_kr, y=counts, palette=bar_colors, ax=ax, alpha=0.85)

                # 값 표시
                for i, (sentiment, count) in enumerate(zip(sentiments_kr, counts)):
                    ax.text(i, count, f'{count}개', ha='center', va='bottom', fontsize=10, fontweight='bold')

                ax.set_title('리뷰 감성 분포', fontsize=16, fontweight='bold', pad=20)
                ax.set_xlabel('감성 분류', fontsize=12)
                ax.set_ylabel('리뷰 수', fontsize=12)
                sns.despine()  # 불필요한 테두리 제거

                chart_path = os.path.join(output_dir, f"synthesis_sentiment_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
                plt.savefig(chart_path, dpi=150, bbox_inches='tight')
                plt.close()
                chart_paths['sentiment'] = chart_path
                logger.info(f"감성 분석 차트 생성: {chart_path}")

        # 4. 경쟁사 SWOT 요약 차트 (Seaborn 스타일)
        if 'competitor' in task_data_map:
            competitor_data = task_data_map['competitor']
            swot = competitor_data.get('swot', {})

            if swot:
                fig, ax = plt.subplots(figsize=(10, 6))
                categories = ['강점(S)', '약점(W)', '기회(O)', '위협(T)']
                counts = [
                    len(swot.get('strengths', [])),
                    len(swot.get('weaknesses', [])),
                    len(swot.get('opportunities', [])),
                    len(swot.get('threats', []))
                ]
                colors_list = ['#4CAF50', '#FF9800', '#2196F3', '#F44336']

                # Seaborn 수평 바 차트
                bars = sns.barh(y=categories, width=counts, palette=colors_list, ax=ax, alpha=0.85)

                # 값 표시
                for i, (category, count) in enumerate(zip(categories, counts)):
                    ax.text(count, i, f'  {count}개', va='center', fontsize=10, fontweight='bold')

                ax.set_title('SWOT 분석 항목 수', fontsize=16, fontweight='bold', pad=20)
                ax.set_xlabel('항목 수', fontsize=12)
                ax.set_ylabel('SWOT 분류', fontsize=12)
                sns.despine()

                chart_path = os.path.join(output_dir, f"synthesis_swot_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
                plt.savefig(chart_path, dpi=150, bbox_inches='tight')
                plt.close()
                chart_paths['swot'] = chart_path
                logger.info(f"SWOT 차트 생성: {chart_path}")

    except Exception as e:
        logger.error(f"차트 생성 실패: {e}", exc_info=True)

    return chart_paths


def generate_synthesis_pdf(
    task_data_list: List[Dict[str, Any]],
    synthesis_text: str,
    product_name: str = "제품"
) -> Optional[str]:
    """
    종합 마케팅 전략 PDF 보고서 생성

    Args:
        task_data_list: 태스크 데이터 리스트
        synthesis_text: 종합 마케팅 전략 텍스트
        product_name: 제품명

    Returns:
        생성된 PDF 파일 경로
    """
    try:
        # 출력 디렉토리 생성
        output_dir = "reports"
        os.makedirs(output_dir, exist_ok=True)

        # PDF 파일명
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        pdf_filename = f"synthesis_report_{timestamp}.pdf"
        pdf_path = os.path.join(output_dir, pdf_filename)

        # PDF 문서 생성
        doc = SimpleDocTemplate(pdf_path, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []

        # 스타일 정의
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName='Malgun',
            fontSize=20,
            textColor=colors.HexColor('#1976D2'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontName='Malgun',
            fontSize=14,
            textColor=colors.HexColor('#424242'),
            spaceAfter=12,
            spaceBefore=20
        )
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontName='Malgun',
            fontSize=10,
            leading=16,
            spaceAfter=10
        )

        # 제목
        story.append(Paragraph(f"{product_name} 마케팅 전략 종합 보고서", title_style))
        story.append(Paragraph(f"생성일: {datetime.now().strftime('%Y년 %m월 %d일')}", body_style))
        story.append(Spacer(1, 0.3*inch))

        # 태스크 요약 테이블
        story.append(Paragraph("분석 태스크 요약", heading_style))
        task_summary_data = [['태스크', '제품명', '상태']]
        task_names = {
            'trend': '소비 트렌드 분석',
            'ad_copy': '광고 문구 생성',
            'segment': '사용자 세그먼트 분류',
            'review': '리뷰 감성 분석',
            'competitor': '경쟁사 분석'
        }
        for task_data in task_data_list:
            task_summary_data.append([
                task_names.get(task_data['task_type'], task_data['task_type']),
                task_data.get('product_name', 'N/A'),
                '✅ 완료'
            ])

        task_table = Table(task_summary_data, colWidths=[2.5*inch, 2*inch, 1.5*inch])
        task_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E3F2FD')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1976D2')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Malgun'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        story.append(task_table)
        story.append(Spacer(1, 0.3*inch))

        # LLM 생성 전략 텍스트
        story.append(PageBreak())
        story.append(Paragraph("마케팅 전략 분석", heading_style))
        story.append(Spacer(1, 0.1*inch))

        # synthesis_text를 섹션별로 분리하여 표시
        for line in synthesis_text.split('\n'):
            line = line.strip()
            if not line:
                continue

            # 마크다운 기호 처리
            if line.startswith('###'):
                # 소제목 (H3)
                clean_text = line.replace('###', '').strip()
                # 이모지 제거
                for emoji in ['📊', '🌐', '👥', '🎯', '📅', '✅', '🚀', '💡', '📈', '🔍']:
                    clean_text = clean_text.replace(emoji, '')
                clean_text = clean_text.strip()
                subheading_style = ParagraphStyle(
                    'SubHeading',
                    parent=body_style,
                    fontSize=12,
                    textColor=colors.HexColor('#1976D2'),
                    spaceBefore=10,
                    spaceAfter=8,
                    fontName='Malgun'
                )
                story.append(Paragraph(f"<b>{clean_text}</b>", subheading_style))
            elif line.startswith('##'):
                # 제목 (H2)
                clean_text = line.replace('##', '').strip()
                # 이모지 제거
                for emoji in ['📊', '🌐', '👥', '🎯', '📅', '✅', '🚀', '💡', '📈', '🔍']:
                    clean_text = clean_text.replace(emoji, '')
                clean_text = clean_text.strip()
                story.append(Spacer(1, 0.2*inch))
                story.append(Paragraph(f"<b>{clean_text}</b>", heading_style))
                story.append(Spacer(1, 0.1*inch))
            elif line.startswith('-') or line.startswith('•') or line.startswith('*'):
                # 리스트 항목
                clean_text = line.lstrip('-•* ').strip()
                # 볼드 처리 (**text**) - 올바르게 짝 맞춰서 변환
                clean_text = _fix_bold_tags(clean_text)
                bullet_style = ParagraphStyle(
                    'Bullet',
                    parent=body_style,
                    leftIndent=20,
                    bulletIndent=10
                )
                story.append(Paragraph(f"• {clean_text}", bullet_style))
            else:
                # 일반 텍스트
                # 볼드 처리
                clean_text = _fix_bold_tags(line)
                story.append(Paragraph(clean_text, body_style))

        # PDF 생성
        doc.build(story)
        logger.info(f"종합 보고서 PDF 생성 완료: {pdf_path}")

        return pdf_path

    except Exception as e:
        logger.error(f"PDF 생성 실패: {e}", exc_info=True)
        return None
