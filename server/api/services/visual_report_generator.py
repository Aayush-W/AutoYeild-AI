import base64
import io
from datetime import datetime
from html import escape as html_escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, Line, String
from reportlab.graphics import renderPDF, renderSVG
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

APP_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = APP_ROOT / "api" / "templates"
REPORTS_DIR = APP_ROOT / "reports"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def _get_severity_color(severity: str) -> str:
    s = _safe_str(severity).lower()
    if s in {"low", "minimal", "safe"}:
        return "green"
    if s in {"medium", "moderate"}:
        return "orange"
    return "red"


def _tone_to_color(tone: str) -> colors.Color:
    palette = {
        "green": colors.HexColor("#28a745"),
        "orange": colors.HexColor("#fd7e14"),
        "red": colors.HexColor("#dc3545"),
        "blue": colors.HexColor("#1f77b4"),
        "gray": colors.HexColor("#6c757d"),
    }
    return palette.get(tone, palette["gray"])


def _decode_image(value: Any) -> bytes | None:
    if not value:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if raw == "[base64 omitted]":
            return None
        if raw.startswith("data:"):
            try:
                _, b64 = raw.split(",", 1)
                return base64.b64decode(b64)
            except ValueError:
                return None
        path = Path(raw)
        if path.exists():
            try:
                return path.read_bytes()
            except OSError:
                return None
        try:
            return base64.b64decode(raw)
        except (ValueError, base64.binascii.Error):
            return None
    return None


def _image_src_for_html(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, str) and value.strip().startswith("data:"):
        return value.strip()
    img_bytes = _decode_image(value)
    if not img_bytes:
        return ""
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _drawing_to_svg_data_uri(drawing: Drawing) -> str:
    svg_data = renderSVG.drawToString(drawing)
    if isinstance(svg_data, str):
        svg_bytes = svg_data.encode("utf-8")
    else:
        svg_bytes = svg_data
    b64 = base64.b64encode(svg_bytes).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64}"


def _flatten_metrics(data: Any, prefix: str = "") -> List[Tuple[str, str]]:
    items: List[Tuple[str, str]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
            items.extend(_flatten_metrics(value, full_key))
    elif isinstance(data, list):
        if all(isinstance(item, (str, int, float, bool)) for item in data):
            items.append((prefix, ", ".join(_safe_str(x) for x in data)))
        else:
            items.append((prefix, f"{len(data)} items"))
    elif isinstance(data, (str, int, float, bool)):
        items.append((prefix, _safe_str(data)))
    return items


def _build_bar_chart(labels: List[str], values: List[float], width: int, height: int, tone: str) -> Drawing:
    drawing = Drawing(width, height)
    chart = VerticalBarChart()
    chart.x = 45
    chart.y = 25
    chart.width = max(100, width - 70)
    chart.height = max(60, height - 50)
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(max(values), 1.0) * 1.1
    chart.valueAxis.valueStep = max(chart.valueAxis.valueMax / 4, 0.1)
    chart.bars[0].fillColor = _tone_to_color(tone)
    chart.bars[0].strokeColor = colors.white
    drawing.add(chart)
    return drawing


def _build_line_chart(labels: List[str], values: List[float], width: int, height: int, threshold: float | None = None) -> Drawing:
    drawing = Drawing(width, height)
    chart = HorizontalLineChart()
    chart.x = 45
    chart.y = 25
    chart.width = max(100, width - 70)
    chart.height = max(60, height - 50)
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.valueAxis.valueMin = 0
    max_val = max(max(values), threshold or 0.0, 1.0) * 1.05
    chart.valueAxis.valueMax = max_val
    chart.valueAxis.valueStep = max(max_val / 4, 0.1)
    chart.lines[0].strokeColor = colors.HexColor("#ff7f0e")
    chart.lines[0].strokeWidth = 2
    drawing.add(chart)
    if threshold is not None:
        y_pos = chart.y + ((threshold - chart.valueAxis.valueMin) / (chart.valueAxis.valueMax - chart.valueAxis.valueMin)) * chart.height
        drawing.add(Line(chart.x, y_pos, chart.x + chart.width, y_pos, strokeColor=colors.HexColor("#dc3545"), strokeDashArray=[4, 3]))
        drawing.add(String(chart.x + chart.width - 120, y_pos + 4, f"Drift threshold {threshold:.2f}", fontSize=7, fillColor=colors.HexColor("#dc3545")))
    return drawing


def _build_pie_chart(labels: List[str], values: List[float], width: int, height: int) -> Drawing:
    drawing = Drawing(width, height)
    pie = Pie()
    pie.x = width / 2
    pie.y = height / 2 - 10
    pie.width = max(100, width - 40)
    pie.height = max(100, height - 40)
    pie.data = values
    pie.labels = labels
    pie.slices.strokeColor = colors.white
    drawing.add(pie)
    return drawing


def _wrap_text(text: str, font_name: str, font_size: int, max_width: float) -> List[str]:
    words = _safe_str(text).split()
    if not words:
        return [""]
    lines: List[str] = []
    current: List[str] = []
    for word in words:
        test = " ".join(current + [word])
        if pdfmetrics.stringWidth(test, font_name, font_size) > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def _draw_wrapped_text(c: canvas.Canvas, text: str, x: float, y: float, max_width: float, font_name: str, font_size: int, leading: float) -> float:
    c.setFont(font_name, font_size)
    for line in _wrap_text(text, font_name, font_size, max_width):
        c.drawString(x, y, line)
        y -= leading
    return y


def _draw_section_title(c: canvas.Canvas, title: str, x: float, y: float) -> float:
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.HexColor("#2c3e50"))
    c.drawString(x, y, title)
    c.setStrokeColor(colors.HexColor("#e0e0e0"))
    c.line(x, y - 4, x + 520, y - 4)
    return y - 16


def _draw_footer(c: canvas.Canvas, page_num: int) -> None:
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#666666"))
    c.drawString(40, 25, "AutoYield AI inspection report")
    c.drawRightString(555, 25, f"Page {page_num}")


def _build_report_data(inspection_data: Dict[str, Any]) -> Dict[str, Any]:
    inspection = inspection_data.get("inspection", {}) or {}
    triage = inspection.get("triage") or inspection_data.get("explainability", {}).get("triage", {}) or {}
    reasoning = inspection.get("reasoning") or inspection_data.get("explainability", {}).get("reasoning", {}) or {}
    impact = inspection_data.get("impact", {}).get("current_result", {}) or {}
    dashboard = inspection_data.get("dashboard", {}) or {}
    explainability = inspection_data.get("explainability", {}) or {}

    inspection_id = inspection.get("inspection_id", inspection_data.get("inspection_id", "Unknown"))
    defect_class = inspection.get("defect_class", "Unknown")
    confidence_score = _safe_float(inspection.get("confidence", 0.0))
    severity_level = reasoning.get("severity_assessment", inspection.get("severity", "Medium"))
    drift_status = "Detected" if inspection.get("drift_detected") else "Clear"
    inference_time = f"{int(_safe_float(inspection.get('inference_time_ms', 0)))} ms"

    wafer_image = inspection.get("input_image") or ""
    heatmap_overlay = inspection.get("heatmap_image") or explainability.get("heatmap_image") or ""

    hotspots_detected = triage.get("num_hotspots", 0)
    activation_spread = round(_safe_float(triage.get("spread_score", 0.0)), 3)
    dominant_region = triage.get("dominant_region", "Unknown")

    top_predictions = inspection.get("top_predictions", []) or []
    confidence_trend = dashboard.get("confidence_trend", []) or []
    recent_inspections = dashboard.get("recent_inspections", []) or []

    labels = [item.get("label", "Unknown") for item in top_predictions]
    values = [_safe_float(item.get("prob", 0.0)) for item in top_predictions]
    if not labels:
        labels = ["Center", "Local", "Random"]
        values = [0.74, 0.11, 0.07]

    drift_labels = [str(item.get("inspection_id", f"INS-{i+1}")) for i, item in enumerate(confidence_trend)]
    drift_values = [_safe_float(item.get("confidence", 0.0)) for item in confidence_trend]
    if not drift_labels:
        drift_labels = ["INS-1", "INS-2"]
        drift_values = [0.8, 0.82]

    counts: Dict[str, int] = {}
    for item in recent_inspections:
        cls = item.get("defect_class", "Unknown")
        counts[cls] = counts.get(cls, 0) + 1
    if not counts:
        counts = {"Unknown": 1}

    impact_labels = ["Yield Improvement", "Energy Saved", "CO2 Saved"]
    impact_values = [
        _safe_float(impact.get("yieldUpliftPp")),
        _safe_float(impact.get("energySavedKwh")),
        _safe_float(impact.get("carbonPreventedKgco2e")),
    ]

    confidence_chart = _build_bar_chart(labels, values, 480, 220, "blue")
    drift_chart = _build_line_chart(drift_labels, drift_values, 480, 220, threshold=0.6)
    defect_pie = _build_pie_chart(list(counts.keys()), list(counts.values()), 320, 220)
    impact_chart = _build_bar_chart(impact_labels, impact_values, 480, 220, "green")

    root_causes = [
        f"Dominant activation region: {dominant_region}",
        f"Hotspots detected: {hotspots_detected}" if hotspots_detected else None,
        reasoning.get("cause_summary"),
        "Drift pattern observed in inspection tool" if inspection.get("drift_detected") else None,
    ]
    root_causes = [item for item in root_causes if item]
    if not root_causes:
        root_causes = ["No specific root causes identified."]

    actions = [
        reasoning.get("recommended_action"),
        "Inspect wafer heatmap activation",
        "Verify center-zone temperature uniformity",
        "Review chamber pressure logs",
    ]
    actions = [item for item in actions if item]

    ai_raw = explainability.get("ai_insight", "")
    if isinstance(ai_raw, dict):
        ai_insight_text = ai_raw.get("explanation", ai_raw.get("insight", str(ai_raw)))
    else:
        ai_insight_text = _safe_str(ai_raw, "No AI insight available.")

    insights = [
        f"Dominant region: {dominant_region}",
        f"Activation spread score: {activation_spread}",
        f"Hotspots detected: {hotspots_detected}",
    ]

    history_rows = []
    for item in recent_inspections[:10]:
        history_rows.append({
            "inspection_id": _safe_str(item.get("inspection_id", "Unknown")),
            "timestamp": _safe_str(item.get("timestamp", "")),
            "defect_class": _safe_str(item.get("defect_class", "Unknown")),
            "confidence": _safe_float(item.get("confidence", 0.0)),
        })

    metrics_blocks = []
    for label, block in [
        ("dashboard.summary", dashboard.get("summary")),
        ("dashboard.model_metrics", dashboard.get("model_metrics")),
        ("drift.dashboard_summary", inspection_data.get("drift", {}).get("dashboard_summary")),
        ("impact.session_summary", inspection_data.get("impact", {}).get("session_summary")),
        ("impact.current_result", impact),
    ]:
        metrics_blocks.extend(_flatten_metrics(block, label))

    metrics_blocks = metrics_blocks[:24]

    return {
        "inspection_id": inspection_id,
        "generated_at": inspection_data.get("generated_at") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "defect_class": defect_class,
        "confidence_score": confidence_score,
        "severity_level": severity_level,
        "drift_status": drift_status,
        "inference_time": inference_time,
        "wafer_image": wafer_image,
        "heatmap_overlay": heatmap_overlay,
        "hotspots_detected": hotspots_detected,
        "activation_spread": activation_spread,
        "dominant_region": dominant_region,
        "ai_insight_text": ai_insight_text,
        "insights": insights,
        "root_causes": root_causes,
        "actions": actions,
        "history_rows": history_rows,
        "metrics_blocks": metrics_blocks,
        "charts": {
            "confidence": confidence_chart,
            "drift": drift_chart,
            "defect_pie": defect_pie,
            "impact": impact_chart,
        },
    }


def _render_html(report_data: Dict[str, Any]) -> str:
    template_path = TEMPLATE_DIR / "inspection_report.html"
    css_path = TEMPLATE_DIR / "report_styles.css"
    template_str = template_path.read_text(encoding="utf-8")
    styles_str = css_path.read_text(encoding="utf-8")

    confidence_chart_src = _drawing_to_svg_data_uri(report_data["charts"]["confidence"])
    drift_chart_src = _drawing_to_svg_data_uri(report_data["charts"]["drift"])
    defect_pie_src = _drawing_to_svg_data_uri(report_data["charts"]["defect_pie"])
    impact_chart_src = _drawing_to_svg_data_uri(report_data["charts"]["impact"])

    root_cause_html = "".join(f"<li>{html_escape(item)}</li>" for item in report_data["root_causes"])
    recommended_actions_html = "".join(f"<li>{html_escape(item)}</li>" for item in report_data["actions"])

    history_rows_html = "".join(
        f"<tr><td>{html_escape(row['inspection_id'])}</td>"
        f"<td>{html_escape(row['timestamp'])}</td>"
        f"<td>{html_escape(row['defect_class'])}</td>"
        f"<td>{row['confidence'] * 100:.1f}%</td></tr>"
        for row in report_data["history_rows"]
    ) or "<tr><td colspan='4'>No recent inspections available.</td></tr>"

    metrics_rows_html = ""
    if report_data["metrics_blocks"]:
        metrics_rows_html = "".join(
            f"<p><strong>{html_escape(k)}:</strong> {html_escape(v)}</p>"
            for k, v in report_data["metrics_blocks"]
        )
    manufacturing_metrics_html = metrics_rows_html or "<p><em>No manufacturing analytics data available.</em></p>"

    html_content = template_str.replace("/* __INJECT_STYLES_HERE__ */", styles_str)
    html_content = html_content.replace("{{ inspection_id }}", html_escape(_safe_str(report_data["inspection_id"])))
    html_content = html_content.replace("{{ generated_at }}", html_escape(_safe_str(report_data["generated_at"])))
    html_content = html_content.replace("{{ defect_class }}", html_escape(_safe_str(report_data["defect_class"]).upper()))
    html_content = html_content.replace("{{ confidence_score }}", f"{report_data['confidence_score'] * 100:.1f}%")
    html_content = html_content.replace("{{ severity_level }}", html_escape(_safe_str(report_data["severity_level"]).upper()))
    html_content = html_content.replace("{{ severity_color }}", _get_severity_color(report_data["severity_level"]))
    html_content = html_content.replace("{{ drift_status }}", html_escape(_safe_str(report_data["drift_status"]).upper()))
    html_content = html_content.replace("{{ inference_time }}", html_escape(_safe_str(report_data["inference_time"])))

    html_content = html_content.replace("{{ confidence_chart }}", confidence_chart_src)
    html_content = html_content.replace("{{ drift_chart }}", drift_chart_src)
    html_content = html_content.replace("{{ defect_pie }}", defect_pie_src)
    html_content = html_content.replace("{{ impact_chart }}", impact_chart_src)

    html_content = html_content.replace("{{ wafer_image }}", _image_src_for_html(report_data["wafer_image"]))
    html_content = html_content.replace("{{ heatmap_overlay }}", _image_src_for_html(report_data["heatmap_overlay"]))
    html_content = html_content.replace("{{ hotspots_detected }}", html_escape(_safe_str(report_data["hotspots_detected"])))
    html_content = html_content.replace("{{ activation_spread }}", html_escape(_safe_str(report_data["activation_spread"])))
    html_content = html_content.replace("{{ dominant_region }}", html_escape(_safe_str(report_data["dominant_region"])))
    html_content = html_content.replace("{{ ai_insight_text }}", html_escape(_safe_str(report_data["ai_insight_text"])))
    html_content = html_content.replace("{{ root_cause_html }}", root_cause_html)
    html_content = html_content.replace("{{ recommended_actions_html }}", recommended_actions_html)
    html_content = html_content.replace("{{ manufacturing_metrics_html }}", manufacturing_metrics_html)
    html_content = html_content.replace("{{ history_table_html }}", history_rows_html)
    return html_content


def _render_pdf(report_data: Dict[str, Any], output_path: Path) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4
    margin = 1.5 * cm
    usable_width = page_width - 2 * margin

    def draw_header() -> float:
        y = page_height - margin
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(colors.HexColor("#1f2d3d"))
        c.drawString(margin, y, "AutoYield AI - Visual Wafer Inspection Report")
        y -= 18
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor("#555555"))
        c.drawString(margin, y, f"Inspection ID: {report_data['inspection_id']}")
        c.drawRightString(page_width - margin, y, f"Generated: {report_data['generated_at']}")
        return y - 16

    def draw_small_header() -> float:
        y = page_height - margin
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#1f2d3d"))
        c.drawString(margin, y, "AutoYield AI Inspection Report")
        y -= 14
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.HexColor("#555555"))
        c.drawString(margin, y, f"Inspection ID: {report_data['inspection_id']}")
        return y - 12

    def ensure_space(y: float, needed: float) -> float:
        nonlocal page_num
        if y - needed < margin + 30:
            _draw_footer(c, page_num)
            c.showPage()
            page_num += 1
            y = draw_small_header()
        return y

    def draw_kpis(y: float) -> float:
        gap = 8
        card_width = (usable_width - 2 * gap) / 3
        card_height = 42
        kpis = [
            ("Defect Class", _safe_str(report_data["defect_class"]).upper(), _get_severity_color(report_data["severity_level"])),
            ("Confidence Score", f"{report_data['confidence_score'] * 100:.1f}%", "blue"),
            ("Severity Level", _safe_str(report_data["severity_level"]).upper(), _get_severity_color(report_data["severity_level"])),
            ("Drift Status", _safe_str(report_data["drift_status"]).upper(), "red" if report_data["drift_status"] == "Detected" else "green"),
            ("Inference Time", _safe_str(report_data["inference_time"]), "gray"),
            ("Yield Risk", _safe_str(report_data["severity_level"]).upper(), _get_severity_color(report_data["severity_level"])),
        ]

        def draw_row(start_y: float, items: Iterable[Tuple[str, str, str]]) -> float:
            x = margin
            for label, value, tone in items:
                c.setFillColor(colors.HexColor("#f5f7fa"))
                c.roundRect(x, start_y - card_height, card_width, card_height, 6, fill=1, stroke=0)
                c.setStrokeColor(_tone_to_color(tone))
                c.setLineWidth(3)
                c.line(x, start_y - card_height, x, start_y)
                c.setFillColor(colors.HexColor("#666666"))
                c.setFont("Helvetica", 8)
                c.drawString(x + 8, start_y - 14, label.upper())
                c.setFillColor(colors.HexColor("#111111"))
                c.setFont("Helvetica-Bold", 12)
                c.drawString(x + 8, start_y - 30, value)
                x += card_width + gap
            return start_y - card_height - 10

        y = draw_row(y, kpis[:3])
        y = draw_row(y, kpis[3:])
        return y

    def draw_chart_section(title: str, drawing: Drawing, y: float) -> float:
        y = ensure_space(y, drawing.height + 40)
        y = _draw_section_title(c, title, margin, y)
        chart_height = drawing.height
        renderPDF.draw(drawing, c, margin, y - chart_height)
        return y - chart_height - 16

    def draw_explainability(y: float) -> float:
        y = ensure_space(y, 260)
        y = _draw_section_title(c, "Explainability Visualization & AI Insight", margin, y)
        img_height = 120
        img_width = (usable_width - 10) / 2
        img_y = y - img_height
        img_x1 = margin
        img_x2 = margin + img_width + 10

        wafer_bytes = _decode_image(report_data["wafer_image"])
        heat_bytes = _decode_image(report_data["heatmap_overlay"])

        def draw_image_or_placeholder(img_bytes: bytes | None, x: float):
            c.setStrokeColor(colors.HexColor("#dddddd"))
            c.setFillColor(colors.HexColor("#f8f9fa"))
            c.rect(x, img_y, img_width, img_height, fill=1, stroke=1)
            if img_bytes:
                try:
                    c.drawImage(ImageReader(io.BytesIO(img_bytes)), x + 4, img_y + 4, img_width - 8, img_height - 8, preserveAspectRatio=True, anchor="c")
                except Exception:
                    c.setFillColor(colors.HexColor("#999999"))
                    c.setFont("Helvetica", 9)
                    c.drawCentredString(x + img_width / 2, img_y + img_height / 2, "Image unavailable")
            else:
                c.setFillColor(colors.HexColor("#999999"))
                c.setFont("Helvetica", 9)
                c.drawCentredString(x + img_width / 2, img_y + img_height / 2, "Image missing")

        draw_image_or_placeholder(wafer_bytes, img_x1)
        draw_image_or_placeholder(heat_bytes, img_x2)

        y = img_y - 12
        c.setFillColor(colors.HexColor("#333333"))
        c.setFont("Helvetica", 9)
        c.drawString(margin, y, f"Hotspots detected: {report_data['hotspots_detected']}")
        y -= 12
        c.drawString(margin, y, f"Activation spread: {report_data['activation_spread']}")
        y -= 12
        c.drawString(margin, y, f"Dominant region: {report_data['dominant_region']}")
        y -= 16

        c.setFillColor(colors.HexColor("#f0f7ff"))
        c.setStrokeColor(colors.HexColor("#007bff"))
        box_height = 60
        c.roundRect(margin, y - box_height, usable_width, box_height, 4, fill=1, stroke=1)
        c.setFillColor(colors.HexColor("#0056b3"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(margin + 8, y - 14, "Generative AI Insight")
        c.setFillColor(colors.HexColor("#333333"))
        c.setFont("Helvetica", 9)
        text_y = y - 28
        text_y = _draw_wrapped_text(c, report_data["ai_insight_text"], margin + 8, text_y, usable_width - 16, "Helvetica", 9, 11)
        return text_y - 10

    def draw_root_causes(y: float) -> float:
        y = ensure_space(y, 80 + len(report_data["root_causes"]) * 12)
        y = _draw_section_title(c, "Root Cause Evidence", margin, y)
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor("#333333"))
        for item in report_data["root_causes"]:
            y = _draw_wrapped_text(c, f"- {item}", margin, y, usable_width, "Helvetica", 10, 12)
        return y - 6

    def draw_actions(y: float) -> float:
        y = ensure_space(y, 80 + len(report_data["actions"]) * 12)
        y = _draw_section_title(c, "Recommended Actions Checklist", margin, y)
        c.setFont("Helvetica", 10)
        c.setFillColor(colors.HexColor("#333333"))
        for item in report_data["actions"]:
            y = _draw_wrapped_text(c, f"[ ] {item}", margin, y, usable_width, "Helvetica", 10, 12)
        return y - 6

    def draw_metrics(y: float) -> float:
        y = ensure_space(y, 40 + len(report_data["metrics_blocks"]) * 12)
        y = _draw_section_title(c, "Technical Metrics Snapshot", margin, y)
        if not report_data["metrics_blocks"]:
            c.setFont("Helvetica", 10)
            c.drawString(margin, y, "No metrics available.")
            return y - 14
        col_split = margin + usable_width * 0.55
        row_height = 12
        for key, value in report_data["metrics_blocks"]:
            c.setFont("Helvetica", 9)
            c.setFillColor(colors.HexColor("#666666"))
            c.drawString(margin, y, key)
            c.setFillColor(colors.HexColor("#111111"))
            c.drawString(col_split, y, value[:60])
            y -= row_height
        return y - 4

    def draw_history_table(y: float) -> float:
        y = ensure_space(y, 40 + len(report_data["history_rows"]) * 14)
        y = _draw_section_title(c, "Recent Inspection History (Last 10)", margin, y)
        if not report_data["history_rows"]:
            c.setFont("Helvetica", 10)
            c.drawString(margin, y, "No recent inspections available.")
            return y - 14
        headers = ["Inspection ID", "Timestamp", "Defect Class", "Confidence"]
        col_widths = [0.25, 0.35, 0.2, 0.2]
        col_positions = [margin]
        for width in col_widths[:-1]:
            col_positions.append(col_positions[-1] + usable_width * width)
        row_height = 14
        c.setFillColor(colors.HexColor("#f8f9fa"))
        c.rect(margin, y - row_height + 2, usable_width, row_height, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#333333"))
        c.setFont("Helvetica-Bold", 9)
        for header, x in zip(headers, col_positions):
            c.drawString(x + 2, y - 9, header)
        y -= row_height
        c.setFont("Helvetica", 9)
        for row in report_data["history_rows"]:
            c.setFillColor(colors.HexColor("#333333"))
            c.drawString(col_positions[0] + 2, y - 9, row["inspection_id"][:20])
            c.drawString(col_positions[1] + 2, y - 9, row["timestamp"][:24])
            c.drawString(col_positions[2] + 2, y - 9, row["defect_class"][:14])
            c.drawRightString(margin + usable_width - 4, y - 9, f"{row['confidence'] * 100:.1f}%")
            y -= row_height
        return y - 6

    page_num = 1
    y = draw_header()
    y = draw_kpis(y)
    y = draw_chart_section("Prediction Confidence Distribution", report_data["charts"]["confidence"], y)
    y = draw_explainability(y)
    _draw_footer(c, page_num)
    c.showPage()

    page_num += 1
    y = draw_small_header()
    y = _draw_section_title(c, "Drift Monitoring Graph", margin, y)
    renderPDF.draw(report_data["charts"]["drift"], c, margin, y - report_data["charts"]["drift"].height)
    y = y - report_data["charts"]["drift"].height - 16
    y = draw_chart_section("Defect Distribution", report_data["charts"]["defect_pie"], y)
    y = draw_root_causes(y)
    _draw_footer(c, page_num)
    c.showPage()

    page_num += 1
    y = draw_small_header()
    y = draw_chart_section("Operational Impact", report_data["charts"]["impact"], y)
    y = draw_actions(y)
    y = draw_metrics(y)
    y = draw_history_table(y)
    _draw_footer(c, page_num)

    c.save()
    pdf_bytes = buffer.getvalue()
    output_path.write_bytes(pdf_bytes)
    return pdf_bytes


def generate_visual_report(inspection_data: Dict[str, Any]) -> Dict[str, Any]:
    report_data = _build_report_data(inspection_data)
    html_content = _render_html(report_data)
    out_html = REPORTS_DIR / "inspection_report.html"
    out_html.write_text(html_content, encoding="utf-8")

    safe_id = "".join(c if c.isalnum() or c in "_-" else "_" for c in _safe_str(report_data["inspection_id"]))
    pdf_filename = f"AutoYield_AI_Inspection_Report_{safe_id}.pdf"
    pdf_path = REPORTS_DIR / pdf_filename

    pdf_bytes = _render_pdf(report_data, pdf_path)

    return {
        "filename": pdf_filename,
        "pdf_bytes": pdf_bytes,
        "mime_type": "application/pdf",
        "html_path": str(out_html),
        "pdf_path": str(pdf_path),
    }


def generate_pdf_report(inspection_data: Dict[str, Any]) -> Dict[str, Any]:
    return generate_visual_report(inspection_data)


__all__ = ["generate_visual_report", "generate_pdf_report"]
