"""
PDF 리포트 생성 도구 (ReportLab 사용)
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from app.config import REPORT_DIR
from app.db.models import generate_uuid

logger = logging.getLogger(__name__)


def make_pdf(
    calc_result: Dict[str, Any],
    evaluation: Dict[str, Any],
    corp_name: str,
    comparison_table: Optional[str] = None
) -> str:
    """
    법인세 계산 결과 PDF 생성

    Args:
        calc_result: 계산 결과
        evaluation: 평가 결과
        corp_name: 기업명
        comparison_table: 비교표 텍스트 (옵션)

    Returns:
        생성된 PDF 파일 경로
    """
    logger.info(f"PDF 생성 시작: {corp_name}")

    try:
        # 파일명 생성
        filename = f"{generate_uuid()}.pdf"
        filepath = REPORT_DIR / filename

        # PDF 문서 생성
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        # 스토리 (PDF 콘텐츠)
        story = []
        styles = getSampleStyleSheet()

        # 커스텀 스타일 (한글 폰트 없이 기본 폰트 사용)
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#333333'),
            spaceAfter=12
        )

        # 제목
        story.append(Paragraph(f"Corporate Tax Report", title_style))
        story.append(Paragraph(f"{corp_name}", title_style))
        story.append(Spacer(1, 0.5*cm))

        # 생성 일시
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        story.append(Paragraph(f"Generated: {timestamp}", styles['Normal']))
        story.append(Spacer(1, 1*cm))

        # 1. 요약 정보
        story.append(Paragraph("1. Summary", heading_style))
        summary_data = [
            ["Item", "Value"],
            ["Company", corp_name],
            ["Taxable Income", f"{calc_result.get('taxable_income', 0):,.0f} KRW"],
            ["Corporate Tax", f"{calc_result.get('corp_tax', 0):,.0f} KRW"],
            ["Surtax", f"{calc_result.get('surtax', 0):,.0f} KRW"],
            ["Total Tax", f"{calc_result.get('total_tax', 0):,.0f} KRW"],
            ["Effective Rate", f"{calc_result.get('effective_rate', 0)*100:.2f}%"],
        ]

        summary_table = Table(summary_data, colWidths=[8*cm, 8*cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 1*cm))

        # 2. 구간별 세율 적용 내역
        story.append(Paragraph("2. Tax Bracket Details", heading_style))
        bracket_details = calc_result.get("bracket_details", [])

        if bracket_details:
            bracket_data = [["Bracket", "Rate", "Taxable Amount", "Tax Amount"]]
            for detail in bracket_details:
                bracket_data.append([
                    detail.get("description", ""),
                    f"{detail.get('rate', 0)*100:.0f}%",
                    f"{detail.get('taxable_amount', 0):,.0f}",
                    f"{detail.get('tax_amount', 0):,.0f}"
                ])

            bracket_table = Table(bracket_data, colWidths=[6*cm, 3*cm, 4*cm, 4*cm])
            bracket_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(bracket_table)
        else:
            story.append(Paragraph("No bracket details available.", styles['Normal']))

        story.append(Spacer(1, 1*cm))

        # 3. 평가 결과
        story.append(Paragraph("3. Evaluation", heading_style))
        confidence = evaluation.get("confidence_score", 0)
        story.append(Paragraph(f"Confidence Score: {confidence*100:.0f}%", styles['Normal']))
        story.append(Paragraph(f"Recommendation: {evaluation.get('recommendation', 'N/A')}", styles['Normal']))

        warnings = evaluation.get("warnings", [])
        if warnings:
            story.append(Spacer(1, 0.5*cm))
            story.append(Paragraph("Warnings:", styles['Normal']))
            for warning in warnings:
                story.append(Paragraph(f"- {warning}", styles['Normal']))

        story.append(Spacer(1, 1*cm))

        # 4. 비교표 (옵션)
        if comparison_table:
            story.append(Paragraph("4. Comparison with Past Results", heading_style))
            # 비교표를 텍스트로 출력 (간단하게)
            for line in comparison_table.split("\n"):
                if line.strip():
                    story.append(Paragraph(line.replace(" ", "&nbsp;"), styles['Code']))
            story.append(Spacer(1, 1*cm))

        # 5. 면책 사항
        story.append(PageBreak())
        story.append(Paragraph("Disclaimer", heading_style))
        disclaimer_text = """
        <b>WARNING:</b><br/>
        This report is generated for research and simulation purposes only.<br/>
        <b>DO NOT use this report for actual tax filing or tax advisory purposes.</b><br/><br/>
        The calculations are approximate and may not reflect actual tax obligations.<br/>
        Tax parameters used are temporary templates and may differ from actual tax laws.<br/>
        Please consult with a certified tax professional for official tax matters.<br/><br/>
        Generated by Corporate Tax Agent - Local Research Version
        """
        story.append(Paragraph(disclaimer_text.replace('\n', ' '), styles['Normal']))

        # PDF 빌드
        doc.build(story)

        logger.info(f"PDF 생성 완료: {filepath}")
        return str(filepath)

    except Exception as e:
        logger.error(f"PDF 생성 실패: {e}", exc_info=True)
        raise


def get_pdf_download_url(pdf_path: str, report_id: str) -> str:
    """
    PDF 다운로드 URL 생성

    Args:
        pdf_path: PDF 파일 경로
        report_id: 리포트 ID

    Returns:
        다운로드 URL
    """
    # 프론트엔드에서 접근 가능한 URL 형식
    return f"/report/{report_id}"
