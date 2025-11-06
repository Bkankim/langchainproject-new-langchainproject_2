"""
PDF 리포트 생성 도구
ReportLab을 사용한 세그먼트 분석 리포트 생성 (한글 지원)
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import uuid
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT

logger = logging.getLogger(__name__)

# 한글 폰트 전역 변수
_FONT_REGISTERED = False


def register_korean_font():
    """한글 폰트 등록 (윈도우 맑은 고딕 사용)"""
    global _FONT_REGISTERED

    if _FONT_REGISTERED:
        return

    try:
        # 윈도우 기본 폰트 경로
        font_paths = [
            r"C:\Windows\Fonts\malgun.ttf",  # 맑은 고딕 Regular
            r"C:\Windows\Fonts\malgunbd.ttf",  # 맑은 고딕 Bold
        ]

        # Regular 폰트 등록
        if os.path.exists(font_paths[0]):
            pdfmetrics.registerFont(TTFont('MalgunGothic', font_paths[0]))
            logger.info("한글 폰트 등록 성공: 맑은 고딕 Regular")
        else:
            logger.warning(f"맑은 고딕 Regular 폰트를 찾을 수 없습니다: {font_paths[0]}")

        # Bold 폰트 등록
        if os.path.exists(font_paths[1]):
            pdfmetrics.registerFont(TTFont('MalgunGothic-Bold', font_paths[1]))
            logger.info("한글 폰트 등록 성공: 맑은 고딕 Bold")
        else:
            logger.warning(f"맑은 고딕 Bold 폰트를 찾을 수 없습니다: {font_paths[1]}")

        _FONT_REGISTERED = True

    except Exception as e:
        logger.error(f"한글 폰트 등록 실패: {e}")
        raise


def create_segment_report_pdf(segments: Dict[str, Any], product_name: str) -> str:
    """
    세그먼트 분석 PDF 리포트 생성 (한글 지원)

    Args:
        segments: 세그먼트 분석 결과
        product_name: 제품명

    Returns:
        생성된 PDF 파일 경로
    """
    logger.info(f"PDF 생성 시작: {product_name}")

    # 한글 폰트 등록
    register_korean_font()

    # reports 폴더 확인/생성
    reports_dir = "reports"
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
        logger.info(f"리포트 폴더 생성: {reports_dir}")

    # 파일명 생성
    file_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"segment_report_{timestamp}_{file_id}.pdf"
    filepath = os.path.join(reports_dir, filename)

    # PDF 문서 생성
    doc = SimpleDocTemplate(filepath, pagesize=A4)
    story = []

    # 스타일 정의 (한글 폰트 적용)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName='MalgunGothic-Bold',
        fontSize=24,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontName='MalgunGothic-Bold',
        fontSize=16,
        textColor=colors.HexColor('#34495E'),
        spaceAfter=12
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontName='MalgunGothic',
        fontSize=10,
        leading=16
    )

    segment_title_style = ParagraphStyle(
        'SegmentTitle',
        parent=styles['Heading3'],
        fontName='MalgunGothic-Bold',
        fontSize=14,
        textColor=colors.HexColor('#3498DB'),
        spaceAfter=10
    )

    # 표지
    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph(f"고객 세그먼트 분석 리포트", title_style))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(f"제품: {product_name}", heading_style))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"생성일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}", body_style))
    story.append(PageBreak())

    # 개요 섹션
    story.append(Paragraph("요약", heading_style))
    story.append(Spacer(1, 0.3 * cm))

    overview_text = f"총 세그먼트 수: {segments.get('total_segments', 0)}<br/><br/>"
    overview_text += f"전체 인사이트: {segments.get('overall_insights', 'N/A')}"
    story.append(Paragraph(overview_text, body_style))
    story.append(Spacer(1, 1 * cm))

    # 세그먼트별 상세 분석
    story.append(Paragraph("세그먼트 상세 분석", heading_style))
    story.append(Spacer(1, 0.5 * cm))

    for i, segment in enumerate(segments.get('segments', []), 1):
        # 세그먼트 제목
        segment_title = f"{i}. {segment.get('name', f'세그먼트 {i}')} ({segment.get('percentage', 0)}%)"
        story.append(Paragraph(segment_title, segment_title_style))

        # 세그먼트 정보 테이블
        segment_data = [
            ["특성", segment.get('characteristics', 'N/A')],
            ["인구통계", segment.get('demographics', 'N/A')],
            ["니즈", segment.get('needs', 'N/A')],
            ["마케팅 전략", segment.get('marketing_strategy', 'N/A')]
        ]

        segment_table = Table(segment_data, colWidths=[4 * cm, 13 * cm])
        segment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ECF0F1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'MalgunGothic-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'MalgunGothic'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (1, 0), (1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        story.append(segment_table)
        story.append(Spacer(1, 0.8 * cm))

    # 페이지 나누기
    story.append(PageBreak())

    # 요약 테이블
    story.append(Paragraph("세그먼트 요약 테이블", heading_style))
    story.append(Spacer(1, 0.5 * cm))

    summary_data = [["세그먼트", "비율", "주요 특성"]]
    for segment in segments.get('segments', []):
        characteristics = segment.get('characteristics', 'N/A')
        # 긴 텍스트 줄이기
        if len(characteristics) > 60:
            characteristics = characteristics[:60] + "..."

        summary_data.append([
            segment.get('name', 'N/A'),
            f"{segment.get('percentage', 0)}%",
            characteristics
        ])

    summary_table = Table(summary_data, colWidths=[5 * cm, 3 * cm, 9 * cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'MalgunGothic-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'MalgunGothic'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')])
    ]))

    story.append(summary_table)
    story.append(Spacer(1, 1 * cm))

    # 면책 문구
    story.append(Spacer(1, 2 * cm))
    disclaimer = """
    <b>면책 조항</b><br/>
    본 리포트는 온라인 리뷰 데이터 분석을 기반으로 AI/ML 기술을 사용하여 생성되었습니다.
    제공된 인사이트와 권장사항은 참고용이며, 실제 마케팅 전략 수립 전에
    시장 조사 및 검증을 권장합니다.
    """
    story.append(Paragraph(disclaimer, ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontName='MalgunGothic',
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER,
        leading=12
    )))

    # PDF 빌드
    try:
        doc.build(story)
        logger.info(f"PDF 생성 완료: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"PDF 빌드 실패: {e}", exc_info=True)
        raise


def get_pdf_download_url(pdf_path: str) -> Optional[str]:
    """
    PDF 다운로드 URL 생성

    Args:
        pdf_path: PDF 파일 경로

    Returns:
        다운로드 URL
    """
    if not pdf_path:
        return None

    # 파일명만 추출
    filename = os.path.basename(pdf_path)
    return f"/report/{filename}"


def create_trend_report_pdf(keyword: str, trend_data: Dict[str, Any], analysis: Dict[str, Any]) -> str:
    """트렌드 분석 PDF 리포트 생성"""
    logger.info("트렌드 리포트 PDF 생성 시작: %s", keyword)

    register_korean_font()

    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)

    safe_keyword = re.sub(r"[^0-9A-Za-z가-힣]+", "_", keyword).strip("_") or "trend"
    file_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"trend_report_{safe_keyword[:20]}_{timestamp}_{file_id}.pdf"
    filepath = os.path.join(reports_dir, filename)

    doc = SimpleDocTemplate(filepath, pagesize=A4)
    story: List[Any] = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TrendTitle",
        parent=styles["Heading1"],
        fontName="MalgunGothic-Bold",
        fontSize=24,
        textColor=colors.HexColor("#1B4F72"),
        spaceAfter=24,
        alignment=TA_CENTER,
    )
    heading_style = ParagraphStyle(
        "TrendHeading",
        parent=styles["Heading2"],
        fontName="MalgunGothic-Bold",
        fontSize=16,
        textColor=colors.HexColor("#2E86C1"),
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "TrendBody",
        parent=styles["BodyText"],
        fontName="MalgunGothic",
        fontSize=10,
        leading=16,
    )

    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph("트렌드 분석 리포트", title_style))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(f"키워드: {keyword}", heading_style))
    period_text = f"분석 기간: {analysis.get('start_date', 'N/A')} ~ {analysis.get('end_date', 'N/A')}"
    if analysis.get("time_unit"):
        period_text += f" (단위: {analysis.get('time_unit')})"
    story.append(Paragraph(period_text, body_style))
    story.append(Paragraph(f"생성일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}", body_style))
    story.append(PageBreak())

    story.append(Paragraph("요약", heading_style))
    story.append(Spacer(1, 0.2 * cm))

    summary_lines: List[str] = []
    if analysis.get("signal"):
        summary_lines.append(f"• 추세 해석: {analysis['signal']}")
    if analysis.get("confidence"):
        summary_lines.append(f"• 데이터 신뢰도: {analysis['confidence']}")

    summary_body = analysis.get("summary")
    if summary_body:
        summary_lines.append("• 핵심 요약:")
        for sub_line in _split_lines(summary_body):
            bullet_text = sub_line.lstrip("• ").strip()
            summary_lines.append(f"   • {bullet_text}")

    if summary_lines:
        for line in summary_lines:
            story.append(Paragraph(_strip_markdown(line), body_style))
        story.append(Spacer(1, 0.3 * cm))
    else:
        story.append(Paragraph("요약 정보를 생성할 수 없습니다.", body_style))

    if analysis.get("insight"):
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph("추천 인사이트", heading_style))
        for line in _split_lines(analysis["insight"]):
            story.append(Paragraph(line, body_style))

    story.append(PageBreak())

    story.append(Paragraph("핵심 지표", heading_style))
    story.append(Spacer(1, 0.2 * cm))
    naver_metrics = analysis.get("naver", {}) or {}
    metrics_data = [
        [Paragraph("<b>지표</b>", body_style), Paragraph("<b>값</b>", body_style)],
        [Paragraph("평균 지수", body_style), Paragraph(_format_metric(naver_metrics.get("average")), body_style)],
        [Paragraph("최신 지수", body_style), Paragraph(_format_metric(naver_metrics.get("latest_value"), integer=True), body_style)],
        [Paragraph("최근 모멘텀", body_style), Paragraph(_format_percentage(naver_metrics.get("momentum_pct"), naver_metrics.get("momentum_label")), body_style)],
        [Paragraph("첫 시점 대비 변화", body_style), Paragraph(_format_percentage(naver_metrics.get("growth_pct")), body_style)],
    ]

    peak = naver_metrics.get("peak")
    if peak:
        metrics_data.append(
            [
                Paragraph("검색 피크", body_style),
                Paragraph(
                    f"{peak.get('date', 'N/A')} / {_format_metric(peak.get('value'), integer=True)}",
                    body_style,
                ),
            ]
        )

    metrics_table = Table(metrics_data, colWidths=[5 * cm, 11 * cm])
    metrics_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E86C1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "MalgunGothic-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 1), (-1, -1), "MalgunGothic"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8F9F9")),
            ]
        )
    )
    story.append(metrics_table)

    clusters = analysis.get("clusters") or []
    if clusters:
        story.append(Spacer(1, 0.6 * cm))
        story.append(Paragraph("연관 키워드 클러스터", heading_style))
        story.append(Spacer(1, 0.2 * cm))

        cluster_headers = [
            Paragraph("<b>클러스터</b>", body_style),
            Paragraph("<b>대표 키워드</b>", body_style),
            Paragraph("<b>추세</b>", body_style),
            Paragraph("<b>변화율</b>", body_style),
            Paragraph("<b>인사이트</b>", body_style),
        ]

        cluster_rows: List[List[Any]] = [cluster_headers]
        for cluster in clusters:
            keywords = cluster.get("keywords", [])[:6]
            keywords_text = ", ".join(keywords)
            change_text = _format_percentage(cluster.get("change_pct"))
            insight_text = _strip_markdown(cluster.get("insight", "")).replace("\n", " ")
            if len(insight_text) > 220:
                insight_text = insight_text[:220] + "..."

            cluster_rows.append(
                [
                    Paragraph(_strip_markdown(cluster.get("name", "클러스터")), body_style),
                    Paragraph(_strip_markdown(keywords_text or "-"), body_style),
                    Paragraph(_strip_markdown(cluster.get("trend_label", "N/A")), body_style),
                    Paragraph(change_text, body_style),
                    Paragraph(insight_text, body_style),
                ]
            )

        cluster_table = Table(cluster_rows, colWidths=[3.5 * cm, 4.5 * cm, 2.2 * cm, 2.2 * cm, 5.6 * cm])
        cluster_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5B2C6F")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "MalgunGothic-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "MalgunGothic"),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("ALIGN", (0, 1), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("FONTSIZE", (0, 1), (-1, -1), 8.5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4ECF7")]),
                ]
            )
        )
        story.append(cluster_table)

    story.append(PageBreak())

    story.append(Paragraph("최근 검색 추이", heading_style))
    story.append(Spacer(1, 0.2 * cm))
    recent_rows = [["날짜", "검색 지수"]]
    tail_series = naver_metrics.get("series_tail") or []
    if tail_series:
        for point in tail_series:
            recent_rows.append([point.get("date", "N/A"), _format_metric(point.get("value"), integer=True)])
    else:
        recent_rows.append(["데이터 없음", "-"])

    recent_table = Table(recent_rows, colWidths=[8 * cm, 8 * cm])
    recent_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1ABC9C")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "MalgunGothic-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "MalgunGothic"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F6F7")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(recent_table)

    detailed_rows = _build_detailed_series_rows(trend_data.get("naver"), keyword)
    if detailed_rows:
        story.append(PageBreak())
        story.append(Paragraph("상세 시계열 데이터", heading_style))
        story.append(Spacer(1, 0.2 * cm))
        detail_table = Table(detailed_rows, colWidths=[5.5 * cm, 5.5 * cm, 5 * cm])
        detail_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7D3C98")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "MalgunGothic-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "MalgunGothic"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9EBEA")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(detail_table)

    story.append(Spacer(1, 1.5 * cm))
    disclaimer = (
        "<b>면책 조항</b><br/>"
        "본 리포트는 Naver DataLab 공개 데이터를 기반으로 AI가 생성한 분석 자료입니다.<br/>"
        "전략 수립 시 추가적인 시장 조사 및 검증을 병행하시기를 권장드립니다."
    )
    story.append(
        Paragraph(
            disclaimer,
            ParagraphStyle(
                "TrendDisclaimer",
                parent=styles["Normal"],
                fontName="MalgunGothic",
                fontSize=8,
                textColor=colors.grey,
                alignment=TA_CENTER,
                leading=12,
            ),
        )
    )

    try:
        doc.build(story)
        logger.info("트렌드 리포트 PDF 생성 완료: %s", filepath)
        return filepath
    except Exception as exc:  # pragma: no cover - ReportLab 내부 오류는 런타임 확인
        logger.error("트렌드 리포트 PDF 생성 실패: %s", exc, exc_info=True)
        raise


def _format_metric(value: Optional[float], integer: bool = False) -> str:
    if value is None:
        return "N/A"
    try:
        if integer:
            return f"{float(value):.0f}"
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return str(value)


def _format_percentage(value: Optional[float], label: Optional[str] = None) -> str:
    if value is None:
        return "N/A"
    try:
        pct_text = f"{float(value):+.1f}%"
    except (TypeError, ValueError):
        pct_text = str(value)
    if label:
        return f"{label} ({pct_text})"
    return pct_text


def _build_detailed_series_rows(naver_data: Optional[Dict[str, Any]], keyword: str) -> List[List[str]]:
    if not naver_data:
        return []

    rows: List[List[str]] = [["그룹", "날짜", "지수"]]
    if "results" in naver_data:
        for entry in naver_data.get("results", []):
            group = entry.get("group") or entry.get("title") or entry.get("keywords", [""])[0]
            for point in entry.get("series", [])[:60]:
                rows.append(
                    [
                        group,
                        point.get("date", "N/A"),
                        _format_metric(point.get("value"), integer=True),
                    ]
                )
    elif "data" in naver_data:
        for item in naver_data.get("data", [])[:60]:
            rows.append(
                [
                    keyword,
                    item.get("period", "N/A"),
                    _format_metric(item.get("ratio"), integer=True),
                ]
            )

    return rows if len(rows) > 1 else []


def _strip_markdown(text: Optional[str]) -> str:
    if not text:
        return ""

    cleaned = str(text).replace("\r\n", "\n")
    cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"_(.*?)_", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)
    cleaned = re.sub(r"^-\s+", "• ", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^>\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+(\n)", r"\1", cleaned)
    return cleaned.strip()


def _split_lines(text: Optional[str]) -> List[str]:
    cleaned = _strip_markdown(text)
    return [line.strip() for line in cleaned.split("\n") if line.strip()]


def create_review_report_pdf(sentiment_result: Dict[str, Any], topics: List[str], summary: Optional[str], improvements_area: List[str], product_name: Optional[str]) -> str:
    """
    리뷰 분석 PDF 리포트 생성 (한글 지원)

    Args:
        sentiment_result: 감성 분석 결과
        topics: 주요 토픽 리스트
        summary: 리뷰 요약 텍스트
        improvements_area: 개선점 리스트
        product_name: 제품명

    Returns:
        생성된 PDF 파일 경로
    """

    logger.info("리뷰 분석 PDF 리포트 생성 시작")

    # 한글 폰트 등록
    register_korean_font()

    # reports 폴더 확인/생성
    reports_dir = "reports"
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
        logger.info(f"리포트 폴더 생성: {reports_dir}")

    # 파일명 생성
    pdf_file_name = f"review_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_file_path = os.path.join(reports_dir, pdf_file_name)

    # PDF 문서 생성
    doc = SimpleDocTemplate(pdf_file_path, pagesize=A4)
    story = []

    # 스타일 정의 (한글 폰트 적용)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName='MalgunGothic-Bold',
        fontSize=24,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontName='MalgunGothic-Bold',
        fontSize=16,
        textColor=colors.HexColor('#34495E'),
        spaceAfter=12
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontName='MalgunGothic',
        fontSize=10,
        leading=16
    )

    # 표지
    story.append(Spacer(1, 2 * cm))
    story.append(Paragraph(f"리뷰 분석 리포트", title_style))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(f"제품: {product_name or 'N/A'}", heading_style))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"생성일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}", body_style))
    story.append(PageBreak())

    # 감성 분석 섹션
    story.append(Paragraph("감성 분석 결과", heading_style))
    story.append(Spacer(1, 0.3 * cm))
    sentiment_text = f"총 리뷰 수: {sentiment_result.get('total_reviews', 0)}<br/><br/>"
    sentiment_text += f"긍정: {sentiment_result.get('sentiment_distribution', {}).get('positive', 0)}개<br/>"
    sentiment_text += f"부정: {sentiment_result.get('sentiment_distribution', {}).get('negative', 0)}개<br/>"
    sentiment_text += f"중립: {sentiment_result.get('sentiment_distribution', {}).get('neutral', 0)}개<br/><br/>"
    sentiment_text += f"평균 점수: {sentiment_result.get('average_score', 0):.2f}"
    story.append(Paragraph(sentiment_text, body_style))
    story.append(Spacer(1, 1 * cm))

    # 주요 토픽 섹션
    story.append(Paragraph("주요 토픽", heading_style))
    story.append(Spacer(1, 0.3 * cm))
    for i, topic in enumerate(topics, 1):
        story.append(Paragraph(f"{i}. {topic}", body_style))
        story.append(Spacer(1, 0.2 * cm))
    story.append(Spacer(1, 1 * cm))

    # 리뷰 요약 섹션
    if summary:
        story.append(Paragraph("리뷰 요약", heading_style))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(summary, body_style))
        story.append(Spacer(1, 1 * cm))

    # 개선점 섹션
    story.append(Paragraph("개선점", heading_style))
    story.append(Spacer(1, 0.3 * cm))
    for i, area in enumerate(improvements_area, 1):
        story.append(Paragraph(f"{i}. {area}", body_style))
        story.append(Spacer(1, 0.2 * cm))
    story.append(Spacer(1, 1 * cm))

    # PDF 빌드
    try:
        doc.build(story)
        logger.info(f"리뷰 분석 PDF 리포트 생성 성공: {pdf_file_path}")
        return pdf_file_path
    except Exception as e:
        logger.error(f"리뷰 분석 PDF 빌드 실패: {e}", exc_info=True)
        raise
