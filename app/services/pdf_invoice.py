"""PDF invoice rendering with reportlab.

Pure functions: ORM/Pydantic data in, PDF bytes out. No DB writes.
"""

import io
import os
from typing import Iterable, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.invoice import Invoice
from app.schemas.billing import TariffRead

BRAND = colors.HexColor("#0f172a")       # slate-900 header band
BRAND_ACCENT = colors.HexColor("#f59e0b")  # amber-500
AMBER_LIGHT = colors.HexColor("#fef3c7")
ROW_ALT = colors.HexColor("#f8fafc")
GRID_LINE = colors.HexColor("#e2e8f0")
TEXT_MUTED = colors.HexColor("#64748b")
GREEN = colors.HexColor("#059669")

_RUPEE = "\u20b9"

# reportlab's built-in Helvetica uses WinAnsi encoding, which has no glyph for
# the rupee sign (it renders as a black box). Prefer a system Unicode TTF when
# one is available; otherwise fall back to Helvetica + the ASCII "Rs." prefix.
_FONT_CANDIDATES = [
    # Windows
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
    # Debian/Ubuntu (python:*-slim images)
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    # macOS
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
]


def _register_unicode_font() -> Optional[tuple]:
    """Register a regular+bold Unicode font pair that can render ₹.

    Returns (regular_name, bold_name) or None when no suitable font exists
    (caller then falls back to Helvetica + 'Rs.')."""
    for idx, (regular_path, bold_path) in enumerate(_FONT_CANDIDATES):
        if not (os.path.exists(regular_path) and os.path.exists(bold_path)):
            continue
        reg_name, bold_name = f"_solar_reg_{idx}", f"_solar_bold_{idx}"
        try:
            pdfmetrics.registerFont(TTFont(reg_name, regular_path))
            pdfmetrics.registerFont(TTFont(bold_name, bold_path))
        except Exception:
            continue
        # Verify the rupee glyph actually exists in this font
        # (charToGlyph is keyed by int codepoint).
        face = pdfmetrics.getFont(reg_name).face
        if not face.charToGlyph.get(ord(_RUPEE), 0):
            continue
        # Lets reportlab resolve <b>/<i> markup inside Paragraphs.
        pdfmetrics.registerFontFamily(
            reg_name, normal=reg_name, bold=bold_name, italic=reg_name, boldItalic=bold_name,
        )
        return reg_name, bold_name
    return None


_FONT_PAIR = _register_unicode_font()
FONT_REGULAR = _FONT_PAIR[0] if _FONT_PAIR else "Helvetica"
FONT_BOLD = _FONT_PAIR[1] if _FONT_PAIR else "Helvetica-Bold"
CURRENCY = _RUPEE if _FONT_PAIR else "Rs."

FOOTER_NOTE = (
    "Prototype demo invoice — figures are generated from SolarShare's simulated "
    "Tamil Nadu ToU billing model and are not an official utility bill. "
    "SolarShare internal prototype business assumption, not an official tariff."
)


def _inr(value: float) -> str:
    return f"{CURRENCY}{value:,.2f}"


def _kwh(value: float) -> str:
    return f"{value:,.2f} kWh"


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "brand": ParagraphStyle(
            "brand", parent=base["Heading1"], fontName=FONT_BOLD,
            fontSize=18, textColor=colors.white, leading=22,
        ),
        "brand_sub": ParagraphStyle(
            "brand_sub", parent=base["Normal"], fontName=FONT_REGULAR,
            fontSize=9, textColor=colors.HexColor("#cbd5e1"), leading=12,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName=FONT_BOLD,
            fontSize=11, textColor=BRAND, spaceBefore=10, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName=FONT_REGULAR,
            fontSize=9, textColor=colors.black, leading=12,
        ),
        "muted": ParagraphStyle(
            "muted", parent=base["Normal"], fontName=FONT_REGULAR,
            fontSize=8, textColor=TEXT_MUTED, leading=11,
        ),
        "label": ParagraphStyle(
            "label", parent=base["Normal"], fontName=FONT_BOLD,
            fontSize=8, textColor=TEXT_MUTED, leading=11,
        ),
        "right": ParagraphStyle(
            "right", parent=base["Normal"], fontName=FONT_REGULAR,
            fontSize=9, alignment=TA_RIGHT, leading=12,
        ),
        # Table header cells: white text on the dark header band (table-level
        # TEXTCOLOR does not recolor Paragraph cells, so it must be set here).
        "th": ParagraphStyle(
            "th", parent=base["Normal"], fontName=FONT_BOLD,
            fontSize=8.5, textColor=colors.white, leading=11,
        ),
        "th_right": ParagraphStyle(
            "th_right", parent=base["Normal"], fontName=FONT_BOLD,
            fontSize=8.5, textColor=colors.white, leading=11, alignment=TA_RIGHT,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"], fontName=FONT_REGULAR,
            fontSize=7, textColor=TEXT_MUTED, leading=9,
        ),
    }


def _header_band(title: str, subtitle: str) -> Table:
    st = _styles()
    left = [
        Paragraph("SolarShare", st["brand"]),
        Paragraph("Shared Solar Energy for MSME Industrial Estates", st["brand_sub"]),
    ]
    right = [
        Paragraph(f"<b>{title}</b>", ParagraphStyle(
            "ht", parent=st["brand"], fontSize=13, alignment=TA_RIGHT)),
        Paragraph(subtitle, ParagraphStyle(
            "hs", parent=st["brand_sub"], alignment=TA_RIGHT)),
    ]
    t = Table([[left, right]], colWidths=[105 * mm, 75 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LINEBELOW", (0, 0), (-1, -1), 3, BRAND_ACCENT),
    ]))
    return t


def _kv_table(pairs: list, col1: float = 30 * mm) -> Table:
    st = _styles()
    data = [
        [Paragraph(k, st["label"]), Paragraph(str(v), st["body"])]
        for k, v in pairs
    ]
    t = Table(data, colWidths=[col1, 60 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(GRID_LINE)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 18 * mm, A4[0] - doc.rightMargin, 18 * mm)
    canvas.setFont("Helvetica-Oblique", 7)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(doc.leftMargin, 14 * mm, "SolarShare prototype — not an official utility bill.")
    canvas.drawRightString(A4[0] - doc.rightMargin, 14 * mm, f"Page {doc.page}")
    canvas.restoreState()


def render_invoice_pdf(
    invoice: Invoice,
    *,
    tenant_name: str,
    estate_name: str,
    tariff: Optional[TariffRead] = None,
) -> bytes:
    """Render a single tenant invoice to PDF bytes."""
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=12 * mm, bottomMargin=24 * mm,
        title=f"Invoice {invoice.invoice_number}",
        author="SolarShare",
    )
    story = []

    story.append(_header_band("INVOICE", f"Invoice {invoice.invoice_number}"))
    story.append(Spacer(1, 6 * mm))

    # Meta + Bill To side by side
    meta = _kv_table([
        ("Invoice No.", invoice.invoice_number),
        ("Billing Period", invoice.billing_period),
        ("Issue Date", invoice.issue_date.strftime("%d %b %Y") if invoice.issue_date else "-"),
        ("Due Date", invoice.due_date.strftime("%d %b %Y") if invoice.due_date else "-"),
        ("Status", invoice.status),
    ])
    bill_to = _kv_table([
        ("Bill To", tenant_name),
        ("Estate", estate_name),
        ("Tenant ID", str(invoice.tenant_id)),
    ])
    side = Table([[meta, bill_to]], colWidths=[95 * mm, 85 * mm])
    side.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
    ]))
    story.append(side)
    story.append(Spacer(1, 5 * mm))

    # Line items
    story.append(Paragraph("Charges", st["h2"]))
    header = [
        Paragraph("Description", st["th"]),
        Paragraph("Quantity", st["th_right"]),
        Paragraph(f"Rate ({CURRENCY}/kWh)", st["th_right"]),
        Paragraph(f"Amount ({CURRENCY})", st["th_right"]),
    ]
    data = [header]
    for li in invoice.line_items:
        if li.category == "NOTE":
            data.append([
                Paragraph(f"<i>{li.description}: {_inr(li.amount_inr)}</i>", st["muted"]),
                "", "", "",
            ])
        elif li.category == "TOTAL":
            data.append([
                Paragraph(f"<b>{li.description}</b>", st["body"]),
                Paragraph(f"<b>{_kwh(li.quantity_kwh)}</b>", st["right"]),
                Paragraph(f"<b>{li.rate_inr_per_kwh:,.4f}</b>", st["right"]),
                Paragraph(f"<b>{_inr(li.amount_inr)}</b>", st["right"]),
            ])
        else:
            data.append([
                Paragraph(li.description, st["body"]),
                _kwh(li.quantity_kwh) if li.quantity_kwh else "-",
                f"{li.rate_inr_per_kwh:,.4f}" if li.category != "TAX" else f"{li.rate_inr_per_kwh:.1f}%",
                _inr(li.amount_inr),
            ])

    col_w = [78 * mm, 32 * mm, 32 * mm, 38 * mm]
    t = Table(data, colWidths=col_w, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("FONTNAME", (0, 0), (-1, -1), FONT_REGULAR),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID_LINE),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT]),
    ]
    # Highlight TOTAL row
    for i, li in enumerate(invoice.line_items, start=1):
        if li.category == "TOTAL":
            style_cmds += [
                ("BACKGROUND", (0, i), (-1, i), AMBER_LIGHT),
                ("LINEABOVE", (0, i), (-1, i), 1, BRAND_ACCENT),
            ]
        if li.category == "NOTE":
            style_cmds += [("BACKGROUND", (0, i), (-1, i), colors.white)]
    t.setStyle(TableStyle(style_cmds))
    story.append(t)
    story.append(Spacer(1, 5 * mm))

    # Summary block
    summary_rows = [
        ("Total consumption", _kwh(invoice.total_consumption_kwh)),
        ("Solar consumed", _kwh(invoice.solar_consumed_kwh)),
        ("Grid consumed", _kwh(invoice.grid_consumed_kwh)),
        ("Solar charge", _inr(invoice.solar_cost_inr)),
        ("Grid charge (ToU)", _inr(invoice.grid_cost_inr)),
    ]
    sub = _kv_table(summary_rows, col1=45 * mm)

    total_tbl = Table([
        [Paragraph("Total bill", ParagraphStyle("tb", parent=st["body"], fontName=FONT_BOLD, fontSize=11)),
         Paragraph(_inr(invoice.total_bill_inr),
                   ParagraphStyle("tv", parent=st["body"], fontName=FONT_BOLD,
                                  fontSize=13, alignment=TA_RIGHT, textColor=BRAND))],
        [Paragraph("Savings vs 100% grid", ParagraphStyle(
            "sb", parent=st["body"], fontSize=9, textColor=GREEN)),
         Paragraph(_inr(invoice.savings_inr),
                   ParagraphStyle("sv", parent=st["body"], fontName=FONT_BOLD,
                                  fontSize=11, alignment=TA_RIGHT, textColor=GREEN))],
    ], colWidths=[60 * mm, 55 * mm])
    total_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AMBER_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, BRAND_ACCENT),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, BRAND_ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    two = Table([[sub, total_tbl]], colWidths=[90 * mm, 90 * mm])
    two.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(two)

    # Tariff reference
    if tariff is not None:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("Tariff reference", st["h2"]))
        story.append(Paragraph(
            f"{tariff.name} — {tariff.source} ({tariff.source_reference}). {tariff.label}",
            st["muted"],
        ))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(FOOTER_NOTE, st["footer"]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def render_estate_summary_pdf(
    month: str,
    invoices: Iterable[Invoice],
    *,
    estate_name: str,
    tenant_names: Optional[dict] = None,
) -> bytes:
    """Render a consolidated estate-wide summary PDF for a billing month."""
    st = _styles()
    invoices = list(invoices)
    tenant_names = tenant_names or {}

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=12 * mm, bottomMargin=24 * mm,
        title=f"Estate Billing Summary {month}",
        author="SolarShare",
    )
    story = []

    story.append(_header_band("ESTATE BILLING SUMMARY", f"Period {month}"))
    story.append(Spacer(1, 6 * mm))
    story.append(_kv_table([
        ("Estate", estate_name),
        ("Billing Period", month),
        ("Invoices", str(len(invoices))),
    ]))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("Per-tenant breakdown", st["h2"]))
    head_left = ["Invoice No.", "Tenant"]
    head_right = ["kWh", f"Solar {CURRENCY}", f"Grid {CURRENCY}", f"Total {CURRENCY}", f"Savings {CURRENCY}"]
    data = [[Paragraph(h, st["th"]) for h in head_left] + [Paragraph(h, st["th_right"]) for h in head_right]]

    tot_kwh = tot_solar = tot_grid = tot_bill = tot_save = 0.0
    for inv in invoices:
        data.append([
            inv.invoice_number,
            Paragraph(tenant_names.get(inv.tenant_id, f"Tenant #{inv.tenant_id}"), st["body"]),
            f"{inv.total_consumption_kwh:,.0f}",
            f"{inv.solar_cost_inr:,.0f}",
            f"{inv.grid_cost_inr:,.0f}",
            f"{inv.total_bill_inr:,.0f}",
            f"{inv.savings_inr:,.0f}",
        ])
        tot_kwh += inv.total_consumption_kwh
        tot_solar += inv.solar_cost_inr
        tot_grid += inv.grid_cost_inr
        tot_bill += inv.total_bill_inr
        tot_save += inv.savings_inr

    data.append([
        Paragraph("<b>TOTAL</b>", st["body"]), "",
        Paragraph(f"<b>{tot_kwh:,.0f}</b>", st["right"]),
        Paragraph(f"<b>{tot_solar:,.0f}</b>", st["right"]),
        Paragraph(f"<b>{tot_grid:,.0f}</b>", st["right"]),
        Paragraph(f"<b>{tot_bill:,.0f}</b>", st["right"]),
        Paragraph(f"<b>{tot_save:,.0f}</b>", st["right"]),
    ])

    col_w = [34 * mm, 40 * mm, 22 * mm, 22 * mm, 22 * mm, 24 * mm, 24 * mm]
    t = Table(data, colWidths=col_w, repeatRows=1)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("FONTNAME", (0, 0), (-1, -1), FONT_REGULAR),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, GRID_LINE),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, ROW_ALT]),
        ("BACKGROUND", (0, -1), (-1, -1), AMBER_LIGHT),
        ("LINEABOVE", (0, -1), (-1, -1), 1, BRAND_ACCENT),
    ]
    t.setStyle(TableStyle(cmds))
    story.append(t)

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        f"Estate total bill: <b>{_inr(tot_bill)}</b> — total savings: "
        f"<b>{_inr(tot_save)}</b> versus a 100% grid supply for the same load.",
        st["body"],
    ))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(FOOTER_NOTE, st["footer"]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()