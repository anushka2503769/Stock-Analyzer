"""
report_generator.py — Assembles the full PDF report using ReportLab.
"""

import os
import io
import tempfile
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, HRFlowable, KeepTogether
)
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF

import charts as ch

# ─── COLOUR PALETTE ──────────────────────────────────────────────────────────
C_BG        = colors.HexColor("#0D1117")
C_PANEL     = colors.HexColor("#161B22")
C_PANEL2    = colors.HexColor("#1C2128")
C_BORDER    = colors.HexColor("#21262D")
C_ACCENT1   = colors.HexColor("#00D4FF")
C_ACCENT2   = colors.HexColor("#7B61FF")
C_ACCENT3   = colors.HexColor("#00E676")
C_ACCENT4   = colors.HexColor("#FF6B6B")
C_ACCENT5   = colors.HexColor("#FFD600")
C_WHITE     = colors.HexColor("#E6EDF3")
C_DIM       = colors.HexColor("#8B949E")
C_HEADER_BG = colors.HexColor("#0D1117")

PW, PH = A4
MARGIN = 15 * mm


def _safe(val, fmt="{:.2f}", default="N/A", multiply=1):
    if val is None:
        return default
    try:
        return fmt.format(val * multiply)
    except Exception:
        return default


def _color_val(val, good_above=None, bad_below=None):
    """Return green/red/yellow hex based on thresholds."""
    if val is None:
        return "#8B949E"
    if good_above is not None and val >= good_above:
        return "#00E676"
    if bad_below is not None and val <= bad_below:
        return "#FF6B6B"
    return "#FFD600"


# ─── PAGE CANVAS (header / footer) ───────────────────────────────────────────

class PageCanvas:
    def __init__(self, ticker, company):
        self.ticker  = ticker
        self.company = company

    def __call__(self, canv, doc):
        canv.saveState()
        w, h = A4

        # Top bar
        canv.setFillColor(C_PANEL)
        canv.rect(0, h - 22*mm, w, 22*mm, fill=1, stroke=0)

        canv.setFillColor(C_ACCENT1)
        canv.rect(0, h - 22*mm, 3*mm, 22*mm, fill=1, stroke=0)

        canv.setFont("Helvetica-Bold", 11)
        canv.setFillColor(C_WHITE)
        canv.drawString(MARGIN + 4*mm, h - 12*mm, f"{self.ticker}  ·  {self.company}")

        canv.setFont("Helvetica", 8)
        canv.setFillColor(C_DIM)
        canv.drawRightString(w - MARGIN, h - 9*mm, "Fundamental Analysis Report")
        canv.drawRightString(w - MARGIN, h - 14*mm, datetime.now().strftime("%d %b %Y"))

        # Bottom bar
        canv.setFillColor(C_PANEL)
        canv.rect(0, 0, w, 10*mm, fill=1, stroke=0)

        canv.setFillColor(C_ACCENT2)
        canv.rect(0, 0, 3*mm, 10*mm, fill=1, stroke=0)

        canv.setFont("Helvetica", 7)
        canv.setFillColor(C_DIM)
        canv.drawString(MARGIN + 4*mm, 3.5*mm,
            "For informational purposes only. Not financial advice. Data sourced from Yahoo Finance.")
        canv.drawRightString(w - MARGIN, 3.5*mm, f"Page {doc.page}")

        canv.restoreState()


# ─── STYLES ───────────────────────────────────────────────────────────────────

def _make_styles():
    base = getSampleStyleSheet()
    s = {}

    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    s["title"] = ps("rtitle",
        fontSize=26, fontName="Helvetica-Bold",
        textColor=C_WHITE, spaceAfter=4, alignment=TA_LEFT)

    s["subtitle"] = ps("rsubtitle",
        fontSize=13, fontName="Helvetica",
        textColor=C_ACCENT1, spaceAfter=8, alignment=TA_LEFT)

    s["section"] = ps("rsection",
        fontSize=13, fontName="Helvetica-Bold",
        textColor=C_ACCENT1, spaceBefore=14, spaceAfter=6,
        borderPad=4, backColor=C_PANEL,
        borderColor=C_ACCENT1, borderWidth=0, borderRadius=4,
        leftIndent=6)

    s["body"] = ps("rbody",
        fontSize=9, fontName="Helvetica",
        textColor=C_WHITE, spaceAfter=4,
        leading=14, alignment=TA_JUSTIFY)

    s["label"] = ps("rlabel",
        fontSize=8, fontName="Helvetica",
        textColor=C_DIM, spaceAfter=1)

    s["kv_key"] = ps("rkv_key",
        fontSize=8.5, fontName="Helvetica",
        textColor=C_DIM)

    s["kv_val"] = ps("rkv_val",
        fontSize=9.5, fontName="Helvetica-Bold",
        textColor=C_WHITE)

    s["conclusion"] = ps("rconcl",
        fontSize=10, fontName="Helvetica",
        textColor=C_WHITE, spaceAfter=6,
        leading=16, alignment=TA_JUSTIFY,
        backColor=C_PANEL2,
        borderPad=10, borderColor=C_ACCENT2,
        borderWidth=1, borderRadius=6,
        leftIndent=8, rightIndent=8)

    s["news_title"] = ps("rnews",
        fontSize=8, fontName="Helvetica",
        textColor=C_WHITE, spaceAfter=2, leading=11)

    s["news_meta"] = ps("rnewsmeta",
        fontSize=7, fontName="Helvetica",
        textColor=C_DIM, spaceAfter=4)

    s["warn"] = ps("rwarn",
        fontSize=8, fontName="Helvetica-Oblique",
        textColor=C_DIM, spaceAfter=3, alignment=TA_CENTER)

    return s


# ─── HELPER FLOWABLES ─────────────────────────────────────────────────────────

def _section_header(text, styles):
    return [
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=2),
        Paragraph(f"▌  {text}", styles["section"]),
        Spacer(1, 2*mm),
    ]


def _kv_table(rows, styles, col_widths=None):
    """rows = [(key, value, value_color), ...]"""
    col_widths = col_widths or [(PW - 2*MARGIN) / len(rows[0])] * len(rows[0])
    data = []
    for row in rows:
        r = []
        for i, cell in enumerate(row):
            if i % 2 == 0:  # key
                r.append(Paragraph(str(cell), styles["kv_key"]))
            else:           # value
                color = cell[1] if isinstance(cell, tuple) else "#E6EDF3"
                text  = cell[0] if isinstance(cell, tuple) else str(cell)
                r.append(Paragraph(f'<font color="{color}"><b>{text}</b></font>', styles["kv_val"]))
        data.append(r)

    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_PANEL),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_PANEL, C_PANEL2]),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, C_BORDER),
        ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _img(path, width, height=None):
    if not path or not os.path.exists(path):
        return Spacer(1, 1)
    img = Image(path, width=width, height=height or width * 0.55)
    img.hAlign = "CENTER"
    return img


def _verdict_badge(text, bg_color):
    badge_text = f'<font color="#0D1117"><b>  {text.upper()}  </b></font>'
    style = ParagraphStyle("badge",
        fontSize=11, fontName="Helvetica-Bold",
        backColor=bg_color, textColor=colors.HexColor("#0D1117"),
        borderPad=6, borderRadius=4,
        alignment=TA_CENTER)
    return Paragraph(badge_text, style)


def _get_verdict_color(recommendation):
    r = (recommendation or "").lower()
    if r in ["strong_buy", "buy"]:
        return C_ACCENT3, "BUY"
    elif r in ["strong_sell", "sell"]:
        return C_ACCENT4, "SELL"
    elif r in ["hold", "neutral"]:
        return C_ACCENT5, "HOLD"
    else:
        return C_DIM, recommendation.upper() if recommendation else "N/A"


# ─── MAIN REPORT CLASS ────────────────────────────────────────────────────────

class ReportGenerator:
    def __init__(self, data, output_dir):
        self.data       = data
        self.output_dir = output_dir
        self.ticker     = data["ticker"]
        self.info       = data["info"]
        self.val        = data["valuation"]
        self.h          = data["health"]
        self.g          = data["growth"]
        self.pd_        = data["price_data"]
        self.sent       = data["sentiment"]
        self.dcf_       = data["dcf"]
        self.styles     = _make_styles()
        self.chart_dir  = os.path.join(output_dir, "_charts", self.ticker)
        os.makedirs(self.chart_dir, exist_ok=True)

    # ── Master build ──────────────────────────
    def build(self):
        # Generate charts
        print(f"    Generating charts...")
        self.charts = ch.generate_all_charts(self.data, self.chart_dir)

        # Generate conclusion
        print(f"    Writing AI conclusion...")
        from conclusion import build_conclusion
        self.conclusion_text = build_conclusion(self.data)

        # Build PDF
        fname = os.path.join(self.output_dir, f"{self.ticker}_analysis.pdf")
        page_cb = PageCanvas(self.ticker,
                             self.info.get("longName", self.ticker))

        doc = SimpleDocTemplate(
            fname, pagesize=A4,
            leftMargin=MARGIN, rightMargin=MARGIN,
            topMargin=26*mm, bottomMargin=14*mm,
            title=f"{self.ticker} — Fundamental Analysis",
            author="Stock Analysis Engine",
        )

        story = []
        story += self._cover_page()
        story += self._company_overview()
        story += self._price_technicals()
        story += self._valuation_section()
        story += self._financial_health_section()
        story += self._growth_profitability_section()
        story += self._dcf_analyst_section()
        story += self._sentiment_section()
        story += self._conclusion_section()
        story += self._risk_disclaimer()

        doc.build(story, onFirstPage=page_cb, onLaterPages=page_cb)
        return fname

    # ── 0. COVER PAGE ─────────────────────────
    def _cover_page(self):
        S = self.styles
        info = self.info
        val  = self.val

        company  = info.get("longName", self.ticker)
        sector   = info.get("sector",   "—")
        industry = info.get("industry", "—")
        exchange = info.get("exchange", "—")
        currency = info.get("currency", "USD")

        price   = val.get("current_price")
        mktcap  = info.get("marketCap")
        rec     = self.dcf_.get("recommendation", "")
        v_color, v_label = _get_verdict_color(rec)

        story = []
        story.append(Spacer(1, 12*mm))

        # Big ticker
        story.append(Paragraph(
            f'<font color="#00D4FF"><b>{self.ticker}</b></font>',
            ParagraphStyle("bigtick", fontSize=42, fontName="Helvetica-Bold",
                           textColor=C_ACCENT1, spaceAfter=0)))
        story.append(Paragraph(company, S["subtitle"]))
        story.append(Spacer(1, 3*mm))

        # Meta row
        meta_data = [
            [Paragraph("<b>Sector</b>",   S["kv_key"]),
             Paragraph(sector,             S["kv_val"]),
             Paragraph("<b>Industry</b>", S["kv_key"]),
             Paragraph(industry,           S["kv_val"])],
            [Paragraph("<b>Exchange</b>", S["kv_key"]),
             Paragraph(exchange,           S["kv_val"]),
             Paragraph("<b>Currency</b>", S["kv_key"]),
             Paragraph(currency,           S["kv_val"])],
        ]
        cw = (PW - 2*MARGIN) / 4
        t = Table(meta_data, colWidths=[cw]*4)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), C_PANEL),
            ("INNERGRID", (0,0), (-1,-1), 0.3, C_BORDER),
            ("BOX", (0,0), (-1,-1), 0.5, C_BORDER),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
        ]))
        story.append(t)
        story.append(Spacer(1, 5*mm))

        # Key metrics strip
        def _fmt_price(p):
            return f"${p:,.2f}" if p else "N/A"
        def _fmt_mktcap(m):
            if not m: return "N/A"
            if m >= 1e12: return f"${m/1e12:.2f}T"
            if m >= 1e9:  return f"${m/1e9:.1f}B"
            return f"${m/1e6:.0f}M"

        strip_data = [[
            Paragraph('<font color="#8B949E">Current Price</font>', S["kv_key"]),
            Paragraph('<font color="#8B949E">Market Cap</font>', S["kv_key"]),
            Paragraph('<font color="#8B949E">52W High</font>', S["kv_key"]),
            Paragraph('<font color="#8B949E">52W Low</font>', S["kv_key"]),
            Paragraph('<font color="#8B949E">Report Date</font>', S["kv_key"]),
        ],[
            Paragraph(f'<font color="#00D4FF"><b>{_fmt_price(price)}</b></font>', S["kv_val"]),
            Paragraph(f'<b>{_fmt_mktcap(mktcap)}</b>', S["kv_val"]),
            Paragraph(f'<font color="#00E676"><b>{_fmt_price(self.pd_.get("52w_high"))}</b></font>', S["kv_val"]),
            Paragraph(f'<font color="#FF6B6B"><b>{_fmt_price(self.pd_.get("52w_low"))}</b></font>', S["kv_val"]),
            Paragraph(f'<b>{self.data["generated_at"]}</b>', S["kv_val"]),
        ]]
        cw2 = (PW - 2*MARGIN) / 5
        t2 = Table(strip_data, colWidths=[cw2]*5)
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), C_PANEL2),
            ("INNERGRID", (0,0), (-1,-1), 0.3, C_BORDER),
            ("BOX", (0,0), (-1,-1), 1, C_ACCENT1),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
        ]))
        story.append(t2)
        story.append(Spacer(1, 5*mm))

        # Analyst verdict badge
        story.append(_verdict_badge(f"Analyst Consensus: {v_label}", v_color))
        story.append(Spacer(1, 6*mm))

        # 5Y chart on cover
        if self.charts.get("5y_price"):
            story.append(_img(self.charts["5y_price"], PW - 2*MARGIN, (PW - 2*MARGIN) * 0.38))

        story.append(PageBreak())
        return story

    # ── 1. COMPANY OVERVIEW ───────────────────
    def _company_overview(self):
        S = self.styles
        info = self.info
        story = []

        story += _section_header("COMPANY OVERVIEW", S)

        desc = info.get("longBusinessSummary", "No description available.")
        story.append(Paragraph(desc, S["body"]))
        story.append(Spacer(1, 4*mm))

        # Key info grid
        emp = info.get("fullTimeEmployees")
        emp_str = f"{emp:,}" if emp else "N/A"

        rows = [
            ["CEO / Leadership",
             (info.get("companyOfficers", [{}])[0].get("name", "N/A") if info.get("companyOfficers") else "N/A"),
             "Employees", emp_str],
            ["Website",  info.get("website", "N/A"), "Country", info.get("country", "N/A")],
            ["Headquarters", info.get("city", "") + (", " + info.get("state","") if info.get("state") else ""), "IPO / Founded", info.get("ipoExpectedDate", "—")],
        ]

        cw = (PW - 2*MARGIN) / 4
        t = _kv_table([[r[0], r[1], r[2], r[3]] for r in rows],
                      S, col_widths=[cw*1.1, cw*1.4, cw*0.9, cw*0.6])
        story.append(t)
        return story

    # ── 2. PRICE & TECHNICALS ─────────────────
    def _price_technicals(self):
        S = self.styles
        story = []
        story.append(PageBreak())
        story += _section_header("PRICE & TECHNICAL ANALYSIS", S)

        # Returns summary
        pd_ = self.pd_
        returns_rows = [[
            "1W Return", (_safe(pd_.get("return_1w"), "{:+.2f}%"), _color_val(pd_.get("return_1w"), 0, 0)),
            "1M Return", (_safe(pd_.get("return_1m"), "{:+.2f}%"), _color_val(pd_.get("return_1m"), 0, 0)),
            "6M Return", (_safe(pd_.get("return_6m"), "{:+.2f}%"), _color_val(pd_.get("return_6m"), 0, 0)),
            "1Y Return", (_safe(pd_.get("return_1y"), "{:+.2f}%"), _color_val(pd_.get("return_1y"), 0, 0)),
        ]]
        cw = (PW - 2*MARGIN) / 8
        story.append(_kv_table(returns_rows, S, col_widths=[cw]*8))
        story.append(Spacer(1, 3*mm))

        tech_rows = [[
            "RSI (14)",
            (_safe(pd_.get("rsi", None) if not hasattr(pd_.get("rsi"), "iloc") else pd_.get("rsi").iloc[-1] if pd_.get("rsi") is not None and len(pd_.get("rsi")) > 0 else None, "{:.1f}"),
             _color_val(pd_.get("rsi").iloc[-1] if hasattr(pd_.get("rsi"), "iloc") and len(pd_.get("rsi")) > 0 else None, good_above=None, bad_below=None) if True else "#8B949E"),
            "Annualised Vol",
            (_safe(pd_.get("annualised_vol"), "{:.1f}%"), _color_val(pd_.get("annualised_vol"), good_above=None, bad_below=None)),
            "Sharpe Ratio",
            (_safe(pd_.get("sharpe"), "{:.2f}"), _color_val(pd_.get("sharpe"), 1, 0)),
            "Max Drawdown",
            (_safe(pd_.get("max_drawdown"), "{:.1f}%"), _color_val(pd_.get("max_drawdown"), good_above=None, bad_below=-30)),
        ]]
        story.append(_kv_table(tech_rows, S, col_widths=[cw]*8))
        story.append(Spacer(1, 3*mm))

        if self.charts.get("price_technicals"):
            story.append(_img(self.charts["price_technicals"], PW - 2*MARGIN, (PW - 2*MARGIN)*0.72))

        if self.charts.get("returns"):
            story.append(Spacer(1, 3*mm))
            story.append(_img(self.charts["returns"], PW - 2*MARGIN, (PW - 2*MARGIN)*0.34))

        return story

    # ── 3. VALUATION ──────────────────────────
    def _valuation_section(self):
        S = self.styles
        val = self.val
        story = []
        story.append(PageBreak())
        story += _section_header("VALUATION METRICS", S)

        cw = (PW - 2*MARGIN) / 6

        rows1 = [[
            "Trailing P/E",
            (_safe(val.get("trailingPE"), "{:.2f}x"), _color_val(val.get("trailingPE"), bad_below=None, good_above=None)),
            "Forward P/E",
            (_safe(val.get("forwardPE"), "{:.2f}x"), _color_val(val.get("forwardPE"), bad_below=None, good_above=None)),
            "PEG Ratio",
            (_safe(val.get("pegRatio"), "{:.2f}"), _color_val(val.get("pegRatio"), good_above=None, bad_below=None)),
        ]]
        rows2 = [[
            "Price/Book",
            (_safe(val.get("priceToBook"), "{:.2f}x"), "#E6EDF3"),
            "Price/Sales",
            (_safe(val.get("priceToSalesTrailing12Months"), "{:.2f}x"), "#E6EDF3"),
            "EV/EBITDA",
            (_safe(val.get("enterpriseToEbitda"), "{:.2f}x"), "#E6EDF3"),
        ]]
        rows3 = [[
            "EV/Revenue",
            (_safe(val.get("enterpriseToRevenue"), "{:.2f}x"), "#E6EDF3"),
            "EV/FCF",
            (_safe(val.get("ev_fcf"), "{:.2f}x"), _color_val(val.get("ev_fcf"), bad_below=None, good_above=None)),
            "Price/FCF",
            (_safe(val.get("price_fcf"), "{:.2f}x"), "#E6EDF3"),
        ]]
        rows4 = [[
            "Trailing EPS",
            (_safe(val.get("trailingEps"), "${:.2f}"), _color_val(val.get("trailingEps"), 0, 0)),
            "Forward EPS",
            (_safe(val.get("forwardEps"), "${:.2f}"), _color_val(val.get("forwardEps"), 0, 0)),
            "Book Value/Share",
            (_safe(val.get("bookValue"), "${:.2f}"), "#E6EDF3"),
        ]]
        rows5 = [[
            "Dividend Yield",
            (_safe(val.get("dividendYield"), "{:.2f}%", multiply=100), _color_val((val.get("dividendYield") or 0)*100, 2, 0)),
            "Payout Ratio",
            (_safe(val.get("payoutRatio"), "{:.1f}%", multiply=100), "#E6EDF3"),
            "5Y Avg Div Yield",
            (_safe(val.get("fiveYearAvgDividendYield"), "{:.2f}%"), "#E6EDF3"),
        ]]

        for row in [rows1, rows2, rows3, rows4, rows5]:
            story.append(_kv_table(row, S, col_widths=[cw]*6))
            story.append(Spacer(1, 1.5*mm))

        # Graham & DCF preview
        g_num = val.get("graham_number")
        price = val.get("current_price")
        g_color = "#00E676" if (g_num and price and g_num > price) else "#FF6B6B"

        story.append(Spacer(1, 2*mm))
        graham_row = [[
            "Graham Number",
            (f'${g_num:.2f}' if g_num else "N/A", g_color),
            "Current Price",
            (f'${price:.2f}' if price else "N/A", "#00D4FF"),
            "Discount / Premium",
            (f'{(g_num/price - 1)*100:+.1f}%' if (g_num and price) else "N/A",
             g_color if g_num and price else "#8B949E"),
        ]]
        story.append(_kv_table(graham_row, S, col_widths=[cw]*6))

        if self.charts.get("valuation_radar"):
            story.append(Spacer(1, 4*mm))
            iw = (PW - 2*MARGIN) * 0.55
            img = _img(self.charts["valuation_radar"], iw, iw)
            img.hAlign = "CENTER"
            story.append(img)

        return story

    # ── 4. FINANCIAL HEALTH ───────────────────
    def _financial_health_section(self):
        S = self.styles
        h  = self.h
        info = self.info
        story = []
        story.append(PageBreak())
        story += _section_header("FINANCIAL HEALTH & BALANCE SHEET", S)

        cw = (PW - 2*MARGIN) / 6

        def _b(val_):
            if val_ is None: return "N/A"
            if abs(val_) >= 1e12: return f"${val_/1e12:.2f}T"
            if abs(val_) >= 1e9:  return f"${val_/1e9:.2f}B"
            if abs(val_) >= 1e6:  return f"${val_/1e6:.2f}M"
            return f"${val_:,.0f}"

        rows = [
            ["Current Ratio",   (_safe(h.get("currentRatio"), "{:.2f}x"), _color_val(h.get("currentRatio"), 1.5, 1.0)),
             "Quick Ratio",     (_safe(h.get("quickRatio"),   "{:.2f}x"), _color_val(h.get("quickRatio"),   1.0, 0.5)),
             "Cash & Equiv.",   (_b(h.get("totalCash")),                  "#E6EDF3")],
            ["Total Debt",      (_b(h.get("totalDebt")),                  "#FF6B6B" if (h.get("totalDebt") or 0) > 0 else "#00E676"),
             "Net Debt",        (_b(h.get("net_debt")),                   "#FF6B6B" if (h.get("net_debt") or 0) > 0 else "#00E676"),
             "Debt/Equity",     (_safe(h.get("debtToEquity"), "{:.1f}%"), _color_val((h.get("debtToEquity") or 0)/100, bad_below=None, good_above=None))],
            ["Debt/EBITDA",     (_safe(h.get("debt_ebitda"), "{:.2f}x"), _color_val(h.get("debt_ebitda"), good_above=None, bad_below=None)),
             "Interest Cov.",   (_safe(h.get("interest_coverage"), "{:.2f}x"), _color_val(h.get("interest_coverage"), 3, 1.5)),
             "Operating CF",    (_b(h.get("operatingCashflow")),          _color_val(h.get("operatingCashflow"), 0, 0))],
            ["Free Cash Flow",  (_b(h.get("freeCashflow")),               _color_val(h.get("freeCashflow"), 0, 0)),
             "Net Income",      (_b(h.get("netIncomeToCommon")),          _color_val(h.get("netIncomeToCommon"), 0, 0)),
             "Total Revenue",   (_b(h.get("totalRevenue")),               "#E6EDF3")],
            ["ROE",             (_safe(info.get("returnOnEquity"), "{:.1f}%", multiply=100), _color_val((info.get("returnOnEquity") or 0)*100, 15, 5)),
             "ROA",             (_safe(info.get("returnOnAssets"), "{:.1f}%", multiply=100), _color_val((info.get("returnOnAssets") or 0)*100, 5,  2)),
             "EBITDA",          (_b(h.get("ebitda")),                     "#E6EDF3")],
        ]

        for row in rows:
            t_data = [[row[0], row[1], row[2], row[3], row[4], row[5]]]
            story.append(_kv_table(t_data, S, col_widths=[cw]*6))
            story.append(Spacer(1, 1.5*mm))

        # Solvency scores
        az = h.get("altman_z")
        pf = h.get("piotroski")
        az_color = "#00E676" if az and az > 2.99 else "#FF6B6B" if az and az < 1.81 else "#FFD600"
        pf_color = "#00E676" if pf and pf >= 7 else "#FF6B6B" if pf and pf <= 3 else "#FFD600"

        story.append(Spacer(1, 2*mm))
        solvency_row = [[
            "Altman Z-Score",
            (f'{az:.2f}' if az else "N/A", az_color),
            "Z Interpretation",
            (("Safe Zone (>2.99)" if az and az > 2.99 else "Distress Zone (<1.81)" if az and az < 1.81 else "Grey Zone (1.81–2.99)") if az else "N/A",
             az_color),
            "Piotroski F-Score",
            (f'{pf}/9' if pf else "N/A", pf_color),
        ]]
        story.append(_kv_table(solvency_row, S, col_widths=[cw]*6))

        # Explanation of scores
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            "Altman Z-Score: >2.99 = financially safe, 1.81–2.99 = grey zone, <1.81 = distress. "
            "Piotroski F-Score (0–9): 8–9 = strong, 6–7 = good, 0–3 = weak fundamentals.",
            S["warn"]))

        if self.charts.get("financial_health"):
            story.append(Spacer(1, 4*mm))
            story.append(_img(self.charts["financial_health"], PW - 2*MARGIN, (PW - 2*MARGIN) * 0.34))

        return story

    # ── 5. GROWTH & PROFITABILITY ─────────────
    def _growth_profitability_section(self):
        S = self.styles
        info = self.info
        g    = self.g
        story = []
        story.append(PageBreak())
        story += _section_header("GROWTH & PROFITABILITY", S)

        cw = (PW - 2*MARGIN) / 6
        rows = [
            ["Gross Margin",     (_safe(info.get("grossMargins"),    "{:.1f}%", multiply=100), _color_val((info.get("grossMargins") or 0)*100,    30, 10)),
             "Operating Margin", (_safe(info.get("operatingMargins"),"{:.1f}%", multiply=100), _color_val((info.get("operatingMargins") or 0)*100, 15, 5)),
             "Net Margin",       (_safe(info.get("profitMargins"),   "{:.1f}%", multiply=100), _color_val((info.get("profitMargins") or 0)*100,    10, 3))],
            ["EBITDA Margin",    (_safe(info.get("ebitdaMargins"),   "{:.1f}%", multiply=100), _color_val((info.get("ebitdaMargins") or 0)*100, 20, 8)),
             "Revenue Growth",   (_safe(g.get("revenueGrowth"),      "{:+.1f}%", multiply=100), _color_val((g.get("revenueGrowth") or 0)*100, 10, 3)),
             "Earnings Growth",  (_safe(g.get("earningsGrowth"),     "{:+.1f}%", multiply=100), _color_val((g.get("earningsGrowth") or 0)*100, 10, 0))],
            ["Rev. CAGR 3Y",     (_safe(g.get("revenue_cagr_3y"), "{:+.1f}%"), "#E6EDF3"),
             "Rev YoY (Y1)",     (_safe(g.get("revenue_yoy_1"), "{:+.1f}%"), "#E6EDF3"),
             "Rev YoY (Y2)",     (_safe(g.get("revenue_yoy_2"), "{:+.1f}%"), "#E6EDF3")],
            ["Qtrly Earn Growth",(_safe(g.get("earningsQuarterlyGrowth"), "{:+.1f}%", multiply=100), "#E6EDF3"),
             "Rev/Share",        (_safe(info.get("revenuePerShare"), "${:.2f}"), "#E6EDF3"),
             "FCF/Share",        (_safe((self.h.get("freeCashflow") or 0) / (info.get("sharesOutstanding") or 1), "${:.2f}"), "#E6EDF3")],
        ]

        for row in rows:
            t_data = [[row[0], row[1], row[2], row[3], row[4], row[5]]]
            story.append(_kv_table(t_data, S, col_widths=[cw]*6))
            story.append(Spacer(1, 1.5*mm))

        if self.charts.get("revenue_earnings"):
            story.append(Spacer(1, 4*mm))
            story.append(_img(self.charts["revenue_earnings"], PW - 2*MARGIN, (PW - 2*MARGIN) * 0.34))

        if self.charts.get("scorecard"):
            story.append(Spacer(1, 4*mm))
            story += _section_header("METRIC SCORECARD", S)
            story.append(_img(self.charts["scorecard"], PW - 2*MARGIN, (PW - 2*MARGIN) * 0.55))

        return story

    # ── 6. DCF & ANALYST TARGETS ──────────────
    def _dcf_analyst_section(self):
        S  = self.styles
        dcf = self.dcf_
        val = self.val
        story = []
        story.append(PageBreak())
        story += _section_header("DCF VALUATION & ANALYST ESTIMATES", S)

        cw = (PW - 2*MARGIN) / 6
        price = val.get("current_price")

        # DCF
        dcf_intro = ("The Discounted Cash Flow (DCF) model below projects future free cash flows "
                     "using near-term revenue growth as the base rate, applies a 9% WACC, "
                     "and assumes 3% terminal growth over a 5-year horizon.")
        story.append(Paragraph(dcf_intro, S["body"]))
        story.append(Spacer(1, 3*mm))

        dcf_row1 = [[
            "DCF Intrinsic Value", (f'${dcf.get("dcf_intrinsic"):.2f}' if dcf.get("dcf_intrinsic") else "N/A",
                                    _color_val(dcf.get("dcf_margin_safety"), 0, 0)),
            "Current Price",       (f'${price:.2f}' if price else "N/A", "#00D4FF"),
            "Margin of Safety",    (f'{dcf.get("dcf_margin_safety"):.1f}%' if dcf.get("dcf_margin_safety") else "N/A",
                                    _color_val(dcf.get("dcf_margin_safety"), 15, -15)),
        ]]
        story.append(_kv_table(dcf_row1, S, col_widths=[cw]*6))
        story.append(Spacer(1, 1.5*mm))

        dcf_row2 = [[
            "Growth Rate (g1)",    (f'{(dcf.get("dcf_g1") or 0)*100:.1f}%', "#E6EDF3"),
            "Terminal Growth (g2)",(f'{(dcf.get("dcf_g2") or 0)*100:.1f}%', "#E6EDF3"),
            "WACC",                (f'{(dcf.get("dcf_wacc") or 0)*100:.1f}%', "#E6EDF3"),
        ]]
        story.append(_kv_table(dcf_row2, S, col_widths=[cw]*6))
        story.append(Spacer(1, 5*mm))

        # Analyst targets
        story += _section_header("ANALYST CONSENSUS & PRICE TARGETS", S)

        n = dcf.get("analyst_count", 0) or 0
        rec = dcf.get("recommendation", "N/A")
        vc, vl = _get_verdict_color(rec)

        analyst_row1 = [[
            "Consensus",     (vl, str(vc)),
            "# of Analysts", (str(n), "#E6EDF3"),
            "Upside (Mean)", (f'{dcf.get("upside_mean"):+.1f}%' if dcf.get("upside_mean") else "N/A",
                              _color_val(dcf.get("upside_mean"), 0, 0)),
        ]]
        story.append(_kv_table(analyst_row1, S, col_widths=[cw]*6))
        story.append(Spacer(1, 1.5*mm))

        analyst_row2 = [[
            "Target Low",    (f'${dcf.get("target_low"):.2f}'    if dcf.get("target_low")    else "N/A", "#8B949E"),
            "Target Median", (f'${dcf.get("target_median"):.2f}' if dcf.get("target_median") else "N/A", "#FFD600"),
            "Target High",   (f'${dcf.get("target_high"):.2f}'   if dcf.get("target_high")   else "N/A", "#00E676"),
        ]]
        story.append(_kv_table(analyst_row2, S, col_widths=[cw]*6))

        if self.charts.get("price_targets"):
            story.append(Spacer(1, 4*mm))
            story.append(_img(self.charts["price_targets"], PW - 2*MARGIN, (PW - 2*MARGIN)*0.4))

        return story

    # ── 7. SENTIMENT ──────────────────────────
    def _sentiment_section(self):
        S    = self.styles
        sent = self.sent
        story = []
        story.append(PageBreak())
        story += _section_header("NEWS SENTIMENT ANALYSIS", S)

        cw = (PW - 2*MARGIN) / 6

        overall = sent.get("overall", "Neutral")
        avg     = sent.get("avg_compound", 0)
        ovr_color = "#00E676" if "Positive" in overall else "#FF6B6B" if "Negative" in overall else "#FFD600"

        sent_row = [[
            "Overall Sentiment", (overall, ovr_color),
            "Avg Compound Score",(f'{avg:.3f}', ovr_color),
            "Articles Analysed", (str(len(sent.get("articles", []))), "#E6EDF3"),
        ]]
        story.append(_kv_table(sent_row, S, col_widths=[cw]*6))
        story.append(Spacer(1, 1.5*mm))

        pct_row = [[
            "% Positive", (f'{sent.get("positive_pct", 0):.0f}%', "#00E676"),
            "% Neutral",  (f'{sent.get("neutral_pct",  0):.0f}%', "#FFD600"),
            "% Negative", (f'{sent.get("negative_pct", 0):.0f}%', "#FF6B6B"),
        ]]
        story.append(_kv_table(pct_row, S, col_widths=[cw]*6))
        story.append(Spacer(1, 3*mm))

        # Accuracy commentary
        story.append(Paragraph(
            f'<b>Sentiment Accuracy Note:</b> {sent.get("accuracy_note", "")}', S["body"]))
        story.append(Spacer(1, 3*mm))

        if self.charts.get("sentiment"):
            story.append(_img(self.charts["sentiment"], PW - 2*MARGIN, (PW - 2*MARGIN)*0.36))

        # Recent headlines table
        articles = sent.get("articles", [])
        if articles:
            story.append(Spacer(1, 4*mm))
            story += _section_header("RECENT HEADLINES", S)

            h_data = [
                [Paragraph("<b>Headline</b>", S["kv_key"]),
                 Paragraph("<b>Source</b>", S["kv_key"]),
                 Paragraph("<b>Sentiment</b>", S["kv_key"]),
                 Paragraph("<b>Score</b>", S["kv_key"])]
            ]
            for a in articles[:15]:
                sc = a["compound"]
                sc_color = "#00E676" if sc >= 0.05 else "#FF6B6B" if sc <= -0.05 else "#FFD600"
                h_data.append([
                    Paragraph(a["title"][:90] + ("…" if len(a["title"]) > 90 else ""), S["news_title"]),
                    Paragraph(a.get("source", ""), S["news_meta"]),
                    Paragraph(f'<font color="{sc_color}"><b>{a["label"]}</b></font>', S["kv_val"]),
                    Paragraph(f'<font color="{sc_color}"><b>{sc:.3f}</b></font>', S["kv_val"]),
                ])

            tw = PW - 2*MARGIN
            t = Table(h_data, colWidths=[tw*0.57, tw*0.15, tw*0.15, tw*0.13])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0),  C_ACCENT2),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_PANEL, C_PANEL2]),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, C_BORDER),
                ("BOX", (0, 0), (-1, -1), 0.5, C_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(t)

        return story

    # ── 8. CONCLUSION ─────────────────────────
    def _conclusion_section(self):
        S = self.styles
        story = []
        story.append(PageBreak())
        story += _section_header("INVESTMENT CONCLUSION", S)

        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(self.conclusion_text, S["conclusion"]))
        story.append(Spacer(1, 5*mm))

        # Final scorecard image
        if self.charts.get("scorecard"):
            story.append(Spacer(1, 4*mm))
            story.append(_img(self.charts["scorecard"], PW - 2*MARGIN, (PW - 2*MARGIN)*0.55))

        return story

    # ── 9. DISCLAIMER ─────────────────────────
    def _risk_disclaimer(self):
        S = self.styles
        story = [PageBreak()]
        story += _section_header("RISK FACTORS & DISCLAIMER", S)

        disclaimer = (
            "This report has been generated automatically using publicly available financial data sourced from Yahoo Finance. "
            "It is intended purely for informational and educational purposes and does not constitute financial, investment, "
            "legal, or tax advice. The analysis presented herein is based on historical and publicly reported data which may "
            "be incomplete, delayed, or subject to revision. Past performance is not indicative of future results. "
            "Stock prices are volatile and can fall as well as rise; you may get back less than you invest. "
            "The DCF valuation model relies on assumptions about growth rates, discount rates, and terminal values which "
            "are inherently uncertain and subjective. News sentiment scores are computed algorithmically and do not reflect "
            "nuanced qualitative judgement. Before making any investment decision, you should conduct your own due diligence, "
            "consult a licensed financial adviser, and consider your own risk tolerance, investment horizon, and financial situation. "
            "The authors and operators of this tool assume no liability for any investment decisions made on the basis of this report."
        )
        story.append(Paragraph(disclaimer, S["body"]))
        return story
