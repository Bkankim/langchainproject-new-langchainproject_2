"""
소비 트렌드 분석 에이전트
Google Trends, Naver DataLab 등을 활용한 트렌드 분석
"""
import logging
import os
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.db.session import get_db
from app.db.crud import append_message, create_session, get_session, save_task_result
from app.tools.trend_tools import (
    extract_trend_keyword,
    resolve_time_window,
    get_naver_datalab_trends,
    analyze_trend_data,
)
from app.tools.pdf_generator import (
    create_trend_report_pdf,
    get_pdf_download_url,
)

logger = logging.getLogger(__name__)


class TrendAgentContext:
    """트렌드 분석 에이전트 컨텍스트"""

    def __init__(self, session_id: str, user_message: str):
        self.session_id = session_id
        self.user_message = user_message
        self.keyword: Optional[str] = None
        self.start_date: Optional[str] = None
        self.end_date: Optional[str] = None
        self.time_unit: str = "week"
        self.window_days: Optional[int] = None
        self.trend_data: Optional[Dict[str, Any]] = None
        self.analysis_result: Optional[Dict[str, Any]] = None
        self.pdf_path: Optional[str] = None
        self.errors: List[str] = []


class TrendAgent:
    """트렌드 분석 에이전트"""

    def __init__(self):
        self.name = "TrendAgent"

    def run(self, session_id: str, user_message: str) -> Dict[str, Any]:
        logger.info("트렌드 분석 에이전트 시작 (세션: %s)", session_id)

        context = TrendAgentContext(session_id, user_message)

        try:
            with get_db() as db:
                if not session_id:
                    session = create_session(db)
                    context.session_id = session.id
                else:
                    session = get_session(db, session_id)
                    if not session:
                        session = create_session(db)
                        context.session_id = session.id

                append_message(db, context.session_id, "system", "--- 트렌드 분석 시작 ---")
                append_message(db, context.session_id, "user", context.user_message)

            logger.info("Step 1: 키워드 추출")
            context.keyword = extract_trend_keyword(context.user_message)

            if not context.keyword:
                logger.warning("키워드 추출 실패: %s", context.user_message)
                context.errors.append("키워드를 추출하지 못했습니다.")
                reply_text = (
                    "분석할 키워드를 찾지 못했습니다. "
                    "예: \"스마트워치 트렌드 알려줘\"처럼 제품이나 주제를 포함해 다시 요청해주세요."
                )
                with get_db() as db:
                    append_message(db, context.session_id, "assistant", reply_text)
                return {
                    "success": False,
                    "session_id": context.session_id,
                    "reply_text": reply_text,
                    "result_data": None,
                    "errors": context.errors,
                }

            time_window = resolve_time_window(context.user_message)
            context.start_date = time_window["start_date"]
            context.end_date = time_window["end_date"]
            context.time_unit = time_window["time_unit"]
            context.window_days = time_window.get("days")

            logger.info(
                "Step 2: 트렌드 데이터 수집 (keyword=%s, period=%s~%s)",
                context.keyword,
                context.start_date,
                context.end_date,
            )
            naver_data = get_naver_datalab_trends(
                [context.keyword],
                context.start_date,
                context.end_date,
                time_unit=context.time_unit,
            )

            context.trend_data = {
                "keyword": context.keyword,
                "start_date": context.start_date,
                "end_date": context.end_date,
                "naver": naver_data,
                "time_unit": context.time_unit,
                "window_days": context.window_days,
                "fetched_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

            logger.info("Step 3: 트렌드 데이터 분석")
            analysis = analyze_trend_data(context.trend_data)
            context.analysis_result = analysis
            context.trend_data["analysis"] = analysis

            try:
                context.pdf_path = create_trend_report_pdf(
                    context.keyword,
                    context.trend_data,
                    analysis,
                )
            except Exception as pdf_error:  # pragma: no cover - ReportLab 오류는 런타임 확인
                logger.error("트렌드 리포트 PDF 생성 실패: %s", pdf_error, exc_info=True)
                context.errors.append("트렌드 리포트 PDF 생성에 실패했습니다.")
                context.pdf_path = None

            reply_text = self._generate_final_response(context, analysis)

            with get_db() as db:
                append_message(db, context.session_id, "assistant", reply_text)

            # 종합 보고서용 결과 데이터 구조화
            result_data = {
                "keyword": context.keyword,
                "period": {
                    "start": context.start_date,
                    "end": context.end_date
                },
                "time_unit": context.time_unit,
                "trend_series": [
                    {"date": item.get("period"), "value": item.get("ratio")}
                    for item in context.trend_data.get("naver", {}).get("results", [{}])[0].get("data", [])
                ] if context.trend_data else [],
                "metrics": {
                    "average": naver.get("average") if (naver := analysis.get("naver", {})) else None,
                    "latest_value": naver.get("latest_value") if naver else None,
                    "growth_pct": naver.get("growth_pct") if naver else None,
                    "momentum_pct": naver.get("momentum_pct") if naver else None,
                    "momentum_label": naver.get("momentum_label") if naver else None,
                    "peak_date": naver.get("peak", {}).get("date") if naver else None,
                    "peak_value": naver.get("peak", {}).get("value") if naver else None,
                },
                "summary": analysis.get("summary"),
                "insight": analysis.get("insight"),
                "signal": analysis.get("signal"),
                "clusters": analysis.get("clusters", []),
            }

            # DB에 태스크 결과 저장
            with get_db() as db:
                save_task_result(
                    db,
                    session_id=context.session_id,
                    task_type="trend",
                    result_data=result_data,
                    product_name=context.keyword,
                    pdf_path=context.pdf_path
                )

            pdf_filename = os.path.basename(context.pdf_path) if context.pdf_path else None
            download_url = get_pdf_download_url(context.pdf_path) if context.pdf_path else None

            return {
                "success": True,
                "session_id": context.session_id,
                "reply_text": reply_text,
                "result_data": result_data,
                "report_id": pdf_filename,
                "download_url": download_url,
                "errors": context.errors,
            }

        except Exception as exc:  # pragma: no cover - 전체 파이프라인 오류는 런타임 확인
            logger.error("트렌드 분석 실패: %s", exc, exc_info=True)
            return {
                "success": False,
                "session_id": context.session_id,
                "reply_text": f"트렌드 분석 중 오류가 발생했습니다: {str(exc)}",
                "result_data": None,
                "errors": context.errors + [str(exc)],
            }

    def _generate_final_response(self, context: TrendAgentContext, analysis: Dict[str, Any]) -> str:
        def fmt_pct(value: Optional[float]) -> str:
            return f"{value:+.1f}%" if isinstance(value, (int, float)) else "N/A"

        def fmt_avg(value: Optional[float]) -> str:
            return f"{value:.1f}" if isinstance(value, (int, float)) else "N/A"

        def fmt_index(value: Optional[float]) -> str:
            return f"{value:.0f}" if isinstance(value, (int, float)) else "N/A"

        lines: List[str] = []
        keyword = context.keyword or analysis.get("keyword", "")
        lines.append(f"📈 **'{keyword}' 트렌드 분석 요약**")
        lines.append("")

        if analysis.get("start_date") and analysis.get("end_date"):
            lines.append(
                f"- 분석 기간: {analysis['start_date']} ~ {analysis['end_date']} "
                f"(단위: {analysis.get('time_unit', '주간')})"
            )
        if analysis.get("confidence"):
            lines.append(f"- 데이터 신뢰도: {analysis['confidence']}")
        if analysis.get("signal"):
            lines.append(f"- 추세 해석: {analysis['signal']}")
        lines.append("")

        summary = analysis.get("summary")
        if summary:
            for summary_line in _split_lines(summary):
                lines.append(summary_line)
            lines.append("")

        naver = analysis.get("naver", {})
        if naver.get("has_data"):
            lines.append("**Naver DataLab**")
            lines.append(f"- 평균 지수: {fmt_avg(naver.get('average'))}")
            lines.append(f"- 최신 지수: {fmt_index(naver.get('latest_value'))}")
            lines.append(
                f"- 최근 모멘텀: {naver.get('momentum_label')} "
                f"({fmt_pct(naver.get('momentum_pct'))})"
            )
            lines.append(f"- 첫 시점 대비 변화: {fmt_pct(naver.get('growth_pct'))}")
            peak = naver.get("peak")
            if peak and peak.get("date"):
                lines.append(
                    f"- 최고 지점: {peak['date']} (지수 {fmt_index(peak.get('value'))})"
                )
            lines.append("")
        else:
            lines.append("Naver DataLab 데이터가 충분하지 않습니다.")
            lines.append("")

        insight = analysis.get("insight")
        if insight:
            lines.append("**추천 인사이트**")
            for insight_line in _split_lines(insight):
                lines.append(insight_line)
            lines.append("")

        clusters = analysis.get("clusters") or []
        if clusters:
            lines.append("**연관 키워드 클러스터**")
            for cluster in clusters:
                cluster_name = cluster.get("name", "클러스터")
                change_text = fmt_pct(cluster.get("change_pct"))
                trend_label = cluster.get("trend_label", "N/A")
                keywords_text = ", ".join(cluster.get("keywords", [])[:4])
                bullet = f"- {cluster_name}: {trend_label} ({change_text})"
                if keywords_text:
                    bullet += f" | 키워드: {keywords_text}"
                insight_text = cluster.get("insight")
                if insight_text:
                    bullet += f" — {insight_text}"
                lines.append(_strip_markdown(bullet))
            lines.append("")

        sources = []
        if naver.get("has_data"):
            naver_source = "Naver DataLab"
            if naver.get("is_mock"):
                naver_source += " (모의)"
            sources.append(naver_source)
        else:
            sources.append("Naver DataLab (데이터 없음)")

        lines.append(f"🔗 데이터 출처: {', '.join(sources)}")
        lines.append("⚠️ 공개 데이터 기반 추정치이므로 의사결정 시 추가 검증이 필요합니다.")

        if context.pdf_path:
            filename = os.path.basename(context.pdf_path)
            lines.append("")
            lines.append("📄 **트렌드 리포트 PDF가 생성되었습니다.**")
            lines.append(f"파일명: `{filename}` (다운로드 메뉴에서 확인하세요)")

        return "\n".join(lines)


agent = TrendAgent()


def run_agent(session_id: str, user_message: str) -> Dict[str, Any]:
    if not session_id:
        with get_db() as db:
            session = create_session(db)
            session_id = session.id
    return agent.run(session_id, user_message)


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
