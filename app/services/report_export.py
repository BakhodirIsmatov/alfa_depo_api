from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

import reportlab
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.report import (
    DailyStockReportResponse,
    ProductReportFilters,
    ProductReportItem,
    ProductReportSummary,
    ReportFormat,
    ReportLanguage,
)

A4_LANDSCAPE_WIDTH_MM, A4_LANDSCAPE_HEIGHT_MM = 297, 210
PNG_DPI = 150
MM_PER_INCH = 25.4
PNG_PAGE_WIDTH = int(A4_LANDSCAPE_WIDTH_MM / MM_PER_INCH * PNG_DPI)
PNG_PAGE_HEIGHT = int(A4_LANDSCAPE_HEIGHT_MM / MM_PER_INCH * PNG_DPI)
PNG_MARGIN = 32
PNG_HEADER_HEIGHT = 88
PNG_HEADER_HORIZONTAL_PADDING = 32
PNG_HEADER_VERTICAL_PADDING = 14
PNG_HEADER_TEXT_GAP = 6
PNG_SUMMARY_HEIGHT = 52
PNG_SUMMARY_TOP_PADDING = 18
PNG_TABLE_HEADER_HEIGHT = 32
PNG_TABLE_ROW_HEIGHT = 26
PNG_TABLE_BOTTOM_PADDING = 32
PNG_CELL_HORIZONTAL_PADDING = 8
PNG_MIN_COLUMN_WIDTH = 48
PNG_COLUMN_UNIT = 8


@dataclass(frozen=True)
class ExportColumn:
    key: str
    title: str
    width: int  # Maximum width in character-based export units.


@dataclass(frozen=True)
class ReportDocument:
    title: str
    subtitle: str
    columns: list[ExportColumn]
    rows: list[dict[str, Any]]
    summary: list[tuple[str, Any]]
    filename: str


@dataclass(frozen=True)
class ExportArtifact:
    content: bytes
    media_type: str
    filename: str


TRANSLATIONS = {
    ReportLanguage.TURKISH: {
        "product_report": "Ürün Raporu",
        "daily_report": "Günlük Stok Hareket Raporu",
        "generated": "Oluşturulma",
        "code": "Ürün Kodu",
        "name": "Ürün Adı",
        "brand": "Marka",
        "color": "Renk",
        "lot": "Lot",
        "current": "Mevcut (kg)",
        "status": "Durum",
        "created": "Oluşturuldu",
        "total_products": "Toplam ürün",
        "total_stock": "Toplam stok (kg)",
        "low": "Düşük stok",
        "out": "Stokta yok",
        "date": "Tarih",
        "opening": "Başlangıç (kg)",
        "closing": "Kapanış (kg)",
        "stock_in": "Giriş (kg)",
        "stock_out": "Çıkış (kg)",
        "adjustment_in": "Pozitif düzeltme",
        "adjustment_out": "Negatif düzeltme",
        "net": "Net değişim",
        "transactions": "İşlem",
        "affected": "Etkilenen ürün",
        "normal": "Normal",
        "movement_type": "Hareket türü",
        "movement_all": "Tümü",
        "movement_in": "Giriş",
        "movement_out": "Çıkış",
    },
    ReportLanguage.ENGLISH: {
        "product_report": "Product Report",
        "daily_report": "Daily Stock Movement Report",
        "generated": "Generated",
        "code": "Product Code",
        "name": "Product Name",
        "brand": "Brand",
        "color": "Color",
        "lot": "Lot",
        "current": "Current (kg)",
        "status": "Status",
        "created": "Created",
        "total_products": "Total products",
        "total_stock": "Total stock (kg)",
        "low": "Low stock",
        "out": "Out of stock",
        "date": "Date",
        "opening": "Opening (kg)",
        "closing": "Closing (kg)",
        "stock_in": "Stock in (kg)",
        "stock_out": "Stock out (kg)",
        "adjustment_in": "Positive adjustment",
        "adjustment_out": "Negative adjustment",
        "net": "Net change",
        "transactions": "Transactions",
        "affected": "Affected products",
        "normal": "Normal",
        "movement_type": "Movement type",
        "movement_all": "All",
        "movement_in": "Stock in",
        "movement_out": "Stock out",
    },
    ReportLanguage.UZBEK: {
        "product_report": "Mahsulotlar hisoboti",
        "daily_report": "Kunlik ombor harakatlari hisoboti",
        "generated": "Yaratilgan vaqt",
        "code": "Mahsulot kodi",
        "name": "Mahsulot nomi",
        "brand": "Marka",
        "color": "Rang",
        "lot": "Lot",
        "current": "Mavjud (kg)",
        "status": "Holat",
        "created": "Yaratilgan",
        "total_products": "Jami mahsulot",
        "total_stock": "Jami stok (kg)",
        "low": "Kam qolgan",
        "out": "Tugagan",
        "date": "Sana",
        "opening": "Boshlang‘ich (kg)",
        "closing": "Yakuniy (kg)",
        "stock_in": "Kirim (kg)",
        "stock_out": "Chiqim (kg)",
        "adjustment_in": "Musbat tuzatish",
        "adjustment_out": "Manfiy tuzatish",
        "net": "Sof o‘zgarish",
        "transactions": "Operatsiyalar",
        "affected": "Ta’sirlangan mahsulot",
        "normal": "Normal",
        "movement_type": "Harakat turi",
        "movement_all": "Barchasi",
        "movement_in": "Kirim",
        "movement_out": "Chiqim",
    },
}


def _decimal(value: Decimal | int | str) -> str:
    result = f"{Decimal(value):,.3f}"
    return result.rstrip("0").rstrip(".")


def _status(value: str, labels: dict[str, str]) -> str:
    return labels.get(value, value)


def product_report_document(
    items: list[ProductReportItem],
    summary: ProductReportSummary,
    filters: ProductReportFilters,
    language: ReportLanguage,
    generated_at: datetime,
) -> ReportDocument:
    labels = TRANSLATIONS[language]
    filter_parts = [
        value
        for value in (
            filters.search and f"search={filters.search}",
            filters.brand and f"brand={filters.brand}",
            filters.color and f"color={filters.color}",
            filters.lot_number and f"lot={filters.lot_number}",
            filters.stock_status.value != "all" and f"status={filters.stock_status.value}",
            filters.created_from and f"from={filters.created_from.isoformat()}",
            filters.created_to and f"to={filters.created_to.isoformat()}",
        )
        if value
    ]
    subtitle = f"{labels['generated']}: {generated_at:%Y-%m-%d %H:%M}"
    if filter_parts:
        subtitle += " | " + ", ".join(filter_parts)
    rows = [
        {
            "code": item.product_code,
            "name": item.name,
            "brand": item.brand or "—",
            "color": item.color or "—",
            "lot": item.lot_number,
            "current": _decimal(item.current_stock),
            "status": _status(item.stock_status, labels),
            "created": item.created_at.strftime("%Y-%m-%d"),
        }
        for item in items
    ]
    return ReportDocument(
        title=f"ALFATEKS — {labels['product_report']}",
        subtitle=subtitle,
        columns=[
            ExportColumn("code", labels["code"], 15),
            ExportColumn("name", labels["name"], 28),
            ExportColumn("brand", labels["brand"], 18),
            ExportColumn("color", labels["color"], 14),
            ExportColumn("lot", labels["lot"], 18),
            ExportColumn("current", labels["current"], 14),
            ExportColumn("status", labels["status"], 14),
            ExportColumn("created", labels["created"], 14),
        ],
        rows=rows,
        summary=[
            (labels["total_products"], summary.total_products),
            (labels["total_stock"], _decimal(summary.total_current_stock)),
            (labels["low"], summary.low_stock_products),
            (labels["out"], summary.out_of_stock_products),
        ],
        filename=f"alfateks-products-{generated_at:%Y%m%d-%H%M}",
    )


def daily_report_document(
    report: DailyStockReportResponse, language: ReportLanguage
) -> ReportDocument:
    labels = TRANSLATIONS[language]
    movement_label = labels[f"movement_{report.movement_type.value}"]
    rows = [
        {
            "code": item.product_code,
            "name": item.product_name,
            "opening": _decimal(item.opening_stock),
            "stock_in": _decimal(item.stock_in),
            "stock_out": _decimal(item.stock_out),
            "adjustment_in": _decimal(item.adjustment_in),
            "adjustment_out": _decimal(item.adjustment_out),
            "closing": _decimal(item.closing_stock),
            "net": _decimal(item.net_change),
            "transactions": item.transaction_count,
        }
        for item in report.products
    ]
    return ReportDocument(
        title=f"ALFATEKS — {labels['daily_report']}",
        subtitle=(
            f"{labels['date']}: {report.report_date.isoformat()} | "
            f"{labels['movement_type']}: {movement_label} | "
            f"{labels['generated']}: {report.generated_at:%Y-%m-%d %H:%M} | "
            f"TZ: {report.timezone}"
        ),
        columns=[
            ExportColumn("code", labels["code"], 15),
            ExportColumn("name", labels["name"], 25),
            ExportColumn("opening", labels["opening"], 14),
            ExportColumn("stock_in", labels["stock_in"], 14),
            ExportColumn("stock_out", labels["stock_out"], 14),
            ExportColumn("adjustment_in", labels["adjustment_in"], 16),
            ExportColumn("adjustment_out", labels["adjustment_out"], 16),
            ExportColumn("closing", labels["closing"], 14),
            ExportColumn("net", labels["net"], 14),
            ExportColumn("transactions", labels["transactions"], 12),
        ],
        rows=rows,
        summary=[
            (labels["stock_in"], _decimal(report.summary.stock_in)),
            (labels["stock_out"], _decimal(report.summary.stock_out)),
            (labels["adjustment_in"], _decimal(report.summary.adjustment_in)),
            (labels["adjustment_out"], _decimal(report.summary.adjustment_out)),
            (labels["net"], _decimal(report.summary.net_change)),
            (labels["transactions"], report.summary.transaction_count),
            (labels["affected"], report.summary.affected_products),
        ],
        filename=f"alfateks-daily-stock-{report.report_date:%Y%m%d}",
    )


def export_document(document: ReportDocument, report_format: ReportFormat) -> ExportArtifact:
    normalized = report_format.normalized
    if normalized == ReportFormat.PDF:
        return ExportArtifact(_pdf(document), "application/pdf", f"{document.filename}.pdf")
    if normalized == ReportFormat.PNG:
        return ExportArtifact(_png(document), "image/png", f"{document.filename}.png")
    return ExportArtifact(
        _xlsx(document),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        f"{document.filename}.xlsx",
    )


def _register_pdf_fonts() -> tuple[str, str]:
    regular_name = "AlfateksVera"
    bold_name = "AlfateksVeraBold"
    if regular_name not in pdfmetrics.getRegisteredFontNames():
        fonts = Path(reportlab.__file__).resolve().parent / "fonts"
        pdfmetrics.registerFont(TTFont(regular_name, str(fonts / "Vera.ttf")))
        pdfmetrics.registerFont(TTFont(bold_name, str(fonts / "VeraBd.ttf")))
    return regular_name, bold_name


def _pdf(document: ReportDocument) -> bytes:
    regular, bold = _register_pdf_fonts()
    output = BytesIO()
    pdf = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=document.title,
        author="Alfateks Warehouse",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName=bold,
        fontSize=17,
        textColor=colors.HexColor("#16332A"),
        alignment=TA_CENTER,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontName=regular,
        fontSize=7.3,
        leading=9,
    )
    header_style = ParagraphStyle(
        "ReportHeader",
        parent=body_style,
        fontName=bold,
        textColor=colors.white,
    )
    story = [
        Paragraph(escape(document.title), title_style),
        Paragraph(escape(document.subtitle), body_style),
        Spacer(1, 5 * mm),
        Paragraph(
            " &nbsp; | &nbsp; ".join(
                f"<b>{escape(str(label))}:</b> {escape(str(value))}"
                for label, value in document.summary
            ),
            body_style,
        ),
        Spacer(1, 4 * mm),
    ]
    table_rows = [[Paragraph(escape(column.title), header_style) for column in document.columns]]
    for row in document.rows:
        table_rows.append(
            [
                Paragraph(escape(str(row.get(column.key, ""))), body_style)
                for column in document.columns
            ]
        )
    available_width = landscape(A4)[0] - 20 * mm
    column_widths = _pdf_column_widths(document, regular, bold, available_width)
    table = Table(table_rows, colWidths=column_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#176B54")),
                ("FONTNAME", (0, 0), (-1, 0), bold),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)

    def page_number(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont(regular, 7)
        canvas.drawRightString(landscape(A4)[0] - 10 * mm, 6 * mm, f"{doc.page}")
        canvas.restoreState()

    pdf.build(story, onFirstPage=page_number, onLaterPages=page_number)
    return output.getvalue()


def _excel_safe(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _visible_character_width(value: Any) -> int:
    """Approximate an Excel character width without stretching short columns."""
    return sum(2 if ord(character) > 0xFF else 1 for character in str(value))


def _excel_column_widths(document: ReportDocument) -> list[float]:
    widths: list[float] = []
    for column in document.columns:
        header_width = max(
            (_visible_character_width(part) for part in column.title.split()),
            default=0,
        )
        content_width = max(
            (_visible_character_width(row.get(column.key, "")) for row in document.rows),
            default=0,
        )
        widths.append(float(min(column.width, max(6, header_width + 2, content_width + 2))))
    return widths


def _xlsx(document: ReportDocument) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Alfateks Report"
    last_column = get_column_letter(len(document.columns))
    sheet.merge_cells(f"A1:{last_column}1")
    sheet["A1"] = document.title
    sheet["A1"].font = Font(size=16, bold=True, color="176B54")
    sheet["A1"].alignment = Alignment(horizontal="center")
    sheet.merge_cells(f"A2:{last_column}2")
    sheet["A2"] = document.subtitle
    sheet["A2"].alignment = Alignment(horizontal="center")
    sheet.merge_cells(f"A4:{last_column}4")
    sheet["A4"] = " | ".join(f"{label}: {value}" for label, value in document.summary)
    sheet["A4"].font = Font(bold=True, color="334155")

    header_row = 6
    column_widths = _excel_column_widths(document)
    sheet.row_dimensions[header_row].height = 28
    for index, (column, column_width) in enumerate(
        zip(document.columns, column_widths, strict=True), start=1
    ):
        cell = sheet.cell(header_row, index, column.title)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="176B54")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        sheet.column_dimensions[get_column_letter(index)].width = column_width
    for row_index, row in enumerate(document.rows, start=header_row + 1):
        for column_index, column in enumerate(document.columns, start=1):
            cell = sheet.cell(row_index, column_index, _excel_safe(row.get(column.key, "")))
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if row_index % 2 == 0:
                cell.fill = PatternFill("solid", fgColor="F8FAFC")
    last_row = max(header_row, header_row + len(document.rows))
    sheet.auto_filter.ref = f"A{header_row}:{last_column}{last_row}"
    sheet.freeze_panes = f"A{header_row + 1}"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.print_title_rows = f"{header_row}:{header_row}"
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _load_png_font(size: int, *, bold: bool = False):
    candidates = (
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
        (
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/dejavu/DejaVuSans.ttf"
        ),
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_widths(preferred: list[float], minimum: list[float], available: float) -> list[float]:
    if sum(preferred) <= available:
        return preferred

    minimum_total = sum(minimum)
    if minimum_total >= available:
        scale = available / minimum_total
        return [width * scale for width in minimum]

    available_slack = available - minimum_total
    preferred_slack = sum(
        preferred_width - minimum_width
        for preferred_width, minimum_width in zip(preferred, minimum, strict=True)
    )
    return [
        minimum_width
        + (preferred_width - minimum_width) * available_slack / preferred_slack
        for preferred_width, minimum_width in zip(preferred, minimum, strict=True)
    ]


def _pdf_column_widths(
    document: ReportDocument,
    regular_font: str,
    bold_font: str,
    available_width: float,
) -> list[float]:
    horizontal_padding = 8.0
    preferred: list[float] = []
    minimum: list[float] = []
    for column in document.columns:
        header_width = pdfmetrics.stringWidth(column.title, bold_font, 7.3)
        content_width = max(
            (
                pdfmetrics.stringWidth(str(row.get(column.key, "")), regular_font, 7.3)
                for row in document.rows
            ),
            default=0.0,
        )
        maximum_width = column.width * 5.2
        preferred.append(
            min(maximum_width, max(30.0, header_width + horizontal_padding, content_width + 8.0))
        )
        minimum.append(30.0)
    return _fit_widths(preferred, minimum, available_width)


def _text_width(draw: ImageDraw.ImageDraw, value: Any, font: Any) -> float:
    return float(draw.textlength(str(value), font=font))


def _fit_text(draw: ImageDraw.ImageDraw, value: Any, font: Any, max_width: float) -> str:
    text = str(value)
    if _text_width(draw, text, font) <= max_width:
        return text

    ellipsis = "…"
    ellipsis_width = _text_width(draw, ellipsis, font)
    if max_width <= ellipsis_width:
        return ""

    low = 0
    high = len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if _text_width(draw, f"{text[:middle]}{ellipsis}", font) <= max_width:
            low = middle
        else:
            high = middle - 1
    return f"{text[:low]}{ellipsis}"


def _png_column_widths(
    draw: ImageDraw.ImageDraw,
    document: ReportDocument,
    header_font: Any,
    body_font: Any,
    available_width: int,
) -> list[int]:
    preferred: list[float] = []
    minimum: list[float] = []
    padding = PNG_CELL_HORIZONTAL_PADDING * 2
    for column in document.columns:
        header_width = _text_width(draw, column.title, header_font)
        content_width = max(
            (_text_width(draw, row.get(column.key, ""), body_font) for row in document.rows),
            default=0.0,
        )
        maximum_width = column.width * PNG_COLUMN_UNIT + padding
        preferred.append(
            min(
                maximum_width,
                max(PNG_MIN_COLUMN_WIDTH, header_width + padding, content_width + padding),
            )
        )
        minimum.append(float(PNG_MIN_COLUMN_WIDTH))

    fitted = _fit_widths(preferred, minimum, float(available_width))
    widths = [max(1, round(width)) for width in fitted]
    overflow = sum(widths) - available_width
    for index in range(len(widths) - 1, -1, -1):
        if overflow <= 0:
            break
        reduction = min(overflow, widths[index] - 1)
        widths[index] -= reduction
        overflow -= reduction
    return widths


def _draw_vertically_centered_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    height: float,
    text: str,
    *,
    font: Any,
    fill: str,
) -> None:
    bounds = draw.textbbox((0, 0), text, font=font)
    text_height = bounds[3] - bounds[1]
    draw.text((xy[0], xy[1] + (height - text_height) / 2 - bounds[1]), text, font=font, fill=fill)


def _png(document: ReportDocument) -> bytes:
    rows = max(1, len(document.rows))
    required_height = (
        PNG_HEADER_HEIGHT
        + PNG_SUMMARY_HEIGHT
        + PNG_TABLE_HEADER_HEIGHT
        + rows * PNG_TABLE_ROW_HEIGHT
        + PNG_TABLE_BOTTOM_PADDING
    )
    if required_height > PNG_PAGE_HEIGHT:
        raise ValueError(f"PNG export exceeds A4 landscape height with {len(document.rows)} rows")

    image = Image.new("RGB", (PNG_PAGE_WIDTH, PNG_PAGE_HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    title_font = _load_png_font(30, bold=True)
    subtitle_font = _load_png_font(14)
    header_font = _load_png_font(13, bold=True)
    body_font = _load_png_font(13)
    header_text_width = PNG_PAGE_WIDTH - PNG_HEADER_HORIZONTAL_PADDING * 2
    title = _fit_text(draw, document.title, title_font, header_text_width)
    subtitle = _fit_text(draw, document.subtitle, subtitle_font, header_text_width)
    title_line_height = 36
    subtitle_line_height = 20
    draw.rectangle((0, 0, PNG_PAGE_WIDTH, PNG_HEADER_HEIGHT - 1), fill="#16332A")
    draw.rectangle(
        (0, PNG_HEADER_HEIGHT - 3, PNG_PAGE_WIDTH, PNG_HEADER_HEIGHT - 1),
        fill="#2F9E7D",
    )
    _draw_vertically_centered_text(
        draw,
        (PNG_HEADER_HORIZONTAL_PADDING, PNG_HEADER_VERTICAL_PADDING),
        title_line_height,
        title,
        font=title_font,
        fill="white",
    )
    _draw_vertically_centered_text(
        draw,
        (
            PNG_HEADER_HORIZONTAL_PADDING,
            PNG_HEADER_VERTICAL_PADDING + title_line_height + PNG_HEADER_TEXT_GAP,
        ),
        subtitle_line_height,
        subtitle,
        font=subtitle_font,
        fill="#D8E7E2",
    )
    summary = "  |  ".join(f"{label}: {value}" for label, value in document.summary)
    summary = _fit_text(draw, summary, body_font, PNG_PAGE_WIDTH - PNG_MARGIN * 2)
    _draw_vertically_centered_text(
        draw,
        (PNG_MARGIN, PNG_HEADER_HEIGHT + PNG_SUMMARY_TOP_PADDING),
        PNG_SUMMARY_HEIGHT - PNG_SUMMARY_TOP_PADDING,
        summary,
        font=body_font,
        fill="#475569",
    )

    table_top = PNG_HEADER_HEIGHT + PNG_SUMMARY_HEIGHT
    available_width = PNG_PAGE_WIDTH - PNG_MARGIN * 2
    widths = _png_column_widths(draw, document, header_font, body_font, available_width)
    table_width = sum(widths)
    table_right = PNG_MARGIN + table_width
    draw.rectangle(
        (PNG_MARGIN, table_top, table_right, table_top + PNG_TABLE_HEADER_HEIGHT),
        fill="#176B54",
    )
    x = PNG_MARGIN
    for column, width in zip(document.columns, widths, strict=True):
        header_text = _fit_text(
            draw,
            column.title,
            header_font,
            width - PNG_CELL_HORIZONTAL_PADDING * 2,
        )
        _draw_vertically_centered_text(
            draw,
            (x + PNG_CELL_HORIZONTAL_PADDING, table_top),
            PNG_TABLE_HEADER_HEIGHT,
            header_text,
            font=header_font,
            fill="white",
        )
        x += width
    for row_index in range(rows):
        y = table_top + PNG_TABLE_HEADER_HEIGHT + row_index * PNG_TABLE_ROW_HEIGHT
        if row_index % 2:
            draw.rectangle(
                (PNG_MARGIN, y, table_right, y + PNG_TABLE_ROW_HEIGHT),
                fill="#F1F5F9",
            )
        x = PNG_MARGIN
        row = document.rows[row_index] if row_index < len(document.rows) else {}
        for column, width in zip(document.columns, widths, strict=True):
            cell_text = _fit_text(
                draw,
                row.get(column.key, ""),
                body_font,
                width - PNG_CELL_HORIZONTAL_PADDING * 2,
            )
            _draw_vertically_centered_text(
                draw,
                (x + PNG_CELL_HORIZONTAL_PADDING, y),
                PNG_TABLE_ROW_HEIGHT,
                cell_text,
                font=body_font,
                fill="#172033",
            )
            x += width
        draw.line(
            (
                PNG_MARGIN,
                y + PNG_TABLE_ROW_HEIGHT,
                table_right,
                y + PNG_TABLE_ROW_HEIGHT,
            ),
            fill="#CBD5E1",
        )
    table_bottom = table_top + PNG_TABLE_HEADER_HEIGHT + rows * PNG_TABLE_ROW_HEIGHT
    x = PNG_MARGIN
    for width in widths[:-1]:
        x += width
        draw.line((x, table_top, x, table_bottom), fill="#CBD5E1")
    draw.rectangle((PNG_MARGIN, table_top, table_right, table_bottom), outline="#B8C5D1", width=1)
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()
