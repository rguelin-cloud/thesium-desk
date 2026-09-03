#!/usr/bin/env python3
"""Generate the Nextones Desk Administrator Guide PDF."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, Flowable, NextPageTemplate
)
from reportlab.pdfgen import canvas
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate, Frame
from reportlab.lib import colors
import os

# ─── Brand Colors ────────────────────────────────────────────────────────────
TEAL_PRIMARY = HexColor("#20808D")
TEAL_DARK = HexColor("#13343B")
OFF_WHITE = HexColor("#FCFAF6")
PAPER_WHITE = HexColor("#F3F3EE")
WARM_BEIGE = HexColor("#E5E3D4")
DARK_NAVY = HexColor("#091717")
DEEP_TEAL = HexColor("#115058")
LIGHT_TEAL = HexColor("#D6F5FA")
MEDIUM_TEAL = HexColor("#2E565D")

PAGE_W, PAGE_H = A4
MARGIN_LEFT = 25 * mm
MARGIN_RIGHT = 25 * mm
MARGIN_TOP = 30 * mm
MARGIN_BOTTOM = 25 * mm
AVAILABLE_WIDTH = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT


# ─── Custom Flowables ────────────────────────────────────────────────────────

class HorizontalRule(Flowable):
    """A colored horizontal rule."""
    def __init__(self, width, color=TEAL_PRIMARY, thickness=1):
        Flowable.__init__(self)
        self.width = width
        self.color = color
        self.thickness = thickness

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return (availWidth, self.thickness + 4)

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 2, self.width, 2)


class SectionNumber(Flowable):
    """A teal circle with section number inside."""
    def __init__(self, number, size=22):
        Flowable.__init__(self)
        self.number = number
        self.size = size

    def wrap(self, availWidth, availHeight):
        return (self.size + 4, self.size + 4)

    def draw(self):
        r = self.size / 2
        cx, cy = r + 2, r + 2
        self.canv.setFillColor(TEAL_PRIMARY)
        self.canv.circle(cx, cy, r, fill=1, stroke=0)
        self.canv.setFillColor(white)
        self.canv.setFont("Helvetica-Bold", 11)
        self.canv.drawCentredString(cx, cy - 3.5, str(self.number))


# ─── Styles ──────────────────────────────────────────────────────────────────

def get_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'CoverTitle', parent=styles['Title'],
        fontName='Helvetica-Bold', fontSize=30, leading=36,
        textColor=TEAL_DARK, alignment=TA_LEFT, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        'CoverSubtitle', parent=styles['Normal'],
        fontName='Helvetica', fontSize=16, leading=22,
        textColor=TEAL_PRIMARY, alignment=TA_LEFT, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        'CoverBrand', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=14, leading=18,
        textColor=DEEP_TEAL, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        'SectionTitle', parent=styles['Heading1'],
        fontName='Helvetica-Bold', fontSize=20, leading=26,
        textColor=TEAL_DARK, spaceBefore=24, spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        'SubSection', parent=styles['Heading2'],
        fontName='Helvetica-Bold', fontSize=14, leading=18,
        textColor=TEAL_PRIMARY, spaceBefore=16, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        'SubSubSection', parent=styles['Heading3'],
        fontName='Helvetica-Bold', fontSize=12, leading=15,
        textColor=DEEP_TEAL, spaceBefore=12, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        'Body', parent=styles['Normal'],
        fontName='Helvetica', fontSize=10, leading=14,
        textColor=TEAL_DARK, alignment=TA_JUSTIFY, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        'BodyBold', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10, leading=14,
        textColor=TEAL_DARK, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        'BulletItem', parent=styles['Normal'],
        fontName='Helvetica', fontSize=10, leading=14,
        textColor=TEAL_DARK, leftIndent=20, bulletIndent=8,
        spaceAfter=4, bulletFontName='Helvetica', bulletFontSize=10,
    ))
    styles.add(ParagraphStyle(
        'CodeInline', parent=styles['Normal'],
        fontName='Courier', fontSize=9, leading=12,
        textColor=TEAL_DARK, backColor=PAPER_WHITE,
        leftIndent=6, rightIndent=6,
    ))
    styles.add(ParagraphStyle(
        'Note', parent=styles['Normal'],
        fontName='Helvetica-Oblique', fontSize=9, leading=13,
        textColor=DEEP_TEAL, leftIndent=12, spaceBefore=4, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8, leading=10,
        textColor=HexColor("#999999"), alignment=TA_CENTER,
    ))
    return styles


# ─── Reusable Builders ───────────────────────────────────────────────────────

def code_block(code_text, available_width=None):
    """Create a styled code block as a table with gray background."""
    if available_width is None:
        available_width = AVAILABLE_WIDTH - 10

    style = ParagraphStyle(
        'CodeBlock', fontName='Courier', fontSize=8.5, leading=12,
        textColor=TEAL_DARK, leftIndent=6, rightIndent=6,
        spaceBefore=0, spaceAfter=0,
    )
    escaped = code_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    lines = escaped.split("\n")
    formatted = "<br/>".join(lines)
    para = Paragraph(formatted, style)

    t = Table([[para]], colWidths=[available_width])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PAPER_WHITE),
        ('BOX', (0, 0), (-1, -1), 0.5, WARM_BEIGE),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    return t


def make_table(headers, rows, col_widths=None):
    """Create a branded table with teal header."""
    data = [headers] + rows
    if col_widths is None:
        n = len(headers)
        col_widths = [AVAILABLE_WIDTH / n] * n

    header_style = ParagraphStyle(
        'TableHeader', fontName='Helvetica-Bold', fontSize=9, leading=12,
        textColor=white, alignment=TA_LEFT,
    )
    cell_style = ParagraphStyle(
        'TableCell', fontName='Helvetica', fontSize=9, leading=12,
        textColor=TEAL_DARK, alignment=TA_LEFT,
    )
    cell_code_style = ParagraphStyle(
        'TableCellCode', fontName='Courier', fontSize=8, leading=11,
        textColor=TEAL_DARK, alignment=TA_LEFT,
    )

    formatted_data = []
    for i, row in enumerate(data):
        formatted_row = []
        for cell in row:
            cell_str = str(cell)
            if i == 0:
                formatted_row.append(Paragraph(cell_str, header_style))
            else:
                if any(cell_str.startswith(prefix) for prefix in
                       ["curl", "python", "pip", "{", "POST", "GET", "PUT", "DELETE", "http", "/"]):
                    formatted_row.append(Paragraph(cell_str, cell_code_style))
                else:
                    formatted_row.append(Paragraph(cell_str, cell_style))
        formatted_data.append(formatted_row)

    t = Table(formatted_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TEAL_PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, PAPER_WHITE]),
        ('GRID', (0, 0), (-1, -1), 0.5, WARM_BEIGE),
        ('BOX', (0, 0), (-1, -1), 1, TEAL_PRIMARY),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return t


def info_box(text, styles):
    """Create a highlighted info/note box."""
    para = Paragraph(text, styles['Note'])
    t = Table([[para]], colWidths=[AVAILABLE_WIDTH - 10])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_TEAL),
        ('BOX', (0, 0), (-1, -1), 1, TEAL_PRIMARY),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    return t


def section_header(number, title, styles, story):
    """Add a section header with number and horizontal rule."""
    story.append(Paragraph(f"{number}. {title}", styles['SectionTitle']))
    story.append(HorizontalRule(AVAILABLE_WIDTH, TEAL_PRIMARY, 1.5))
    story.append(Spacer(1, 4 * mm))


# ─── Page Templates ──────────────────────────────────────────────────────────

def draw_cover_page(canvas_obj, doc):
    """Draw cover page background and decorations."""
    canvas_obj.saveState()
    canvas_obj.setFillColor(OFF_WHITE)
    canvas_obj.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Top teal bar
    canvas_obj.setFillColor(TEAL_PRIMARY)
    canvas_obj.rect(0, PAGE_H - 8 * mm, PAGE_W, 8 * mm, fill=1, stroke=0)

    # Left accent strip
    canvas_obj.setFillColor(TEAL_PRIMARY)
    canvas_obj.rect(0, 0, 6 * mm, PAGE_H - 8 * mm, fill=1, stroke=0)

    # Bottom bar
    canvas_obj.setFillColor(TEAL_DARK)
    canvas_obj.rect(0, 0, PAGE_W, 15 * mm, fill=1, stroke=0)

    # Bottom text
    canvas_obj.setFillColor(white)
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawString(MARGIN_LEFT, 6 * mm, "Document confidentiel — NEXTONES.FINANCE — Mars 2026")

    canvas_obj.restoreState()


def draw_content_page(canvas_obj, doc):
    """Draw header/footer for content pages."""
    canvas_obj.saveState()

    # Background
    canvas_obj.setFillColor(OFF_WHITE)
    canvas_obj.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Top header line
    canvas_obj.setStrokeColor(TEAL_PRIMARY)
    canvas_obj.setLineWidth(2)
    canvas_obj.line(MARGIN_LEFT, PAGE_H - 15 * mm, PAGE_W - MARGIN_RIGHT, PAGE_H - 15 * mm)

    # Header text
    canvas_obj.setFillColor(TEAL_PRIMARY)
    canvas_obj.setFont("Helvetica-Bold", 8)
    canvas_obj.drawString(MARGIN_LEFT, PAGE_H - 13 * mm, "Guide Administrateur — Nextones Desk")
    canvas_obj.drawRightString(PAGE_W - MARGIN_RIGHT, PAGE_H - 13 * mm, "NEXTONES.FINANCE")

    # Footer line
    canvas_obj.setStrokeColor(WARM_BEIGE)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(MARGIN_LEFT, 18 * mm, PAGE_W - MARGIN_RIGHT, 18 * mm)

    # Page number
    canvas_obj.setFillColor(TEAL_PRIMARY)
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawCentredString(PAGE_W / 2, 12 * mm, f"— {doc.page} —")

    # Footer text
    canvas_obj.setFillColor(HexColor("#999999"))
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.drawString(MARGIN_LEFT, 12 * mm, "Version 2.0 — Mars 2026")
    canvas_obj.drawRightString(PAGE_W - MARGIN_RIGHT, 12 * mm, "NEXTONES.FINANCE")

    canvas_obj.restoreState()


# ─── Build Document ──────────────────────────────────────────────────────────

def build_pdf(output_path):
    styles = get_styles()
    story = []
    aw = AVAILABLE_WIDTH

    # ═══════════════════════════════════════════════════════════════════
    # COVER PAGE
    # ═══════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 55 * mm))
    story.append(Paragraph("Guide Administrateur", styles['CoverTitle']))
    story.append(Spacer(1, 2 * mm))
    story.append(HorizontalRule(aw, TEAL_PRIMARY, 3))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Nextones Desk", styles['CoverTitle']))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Version 2.0 — Mars 2026", styles['CoverSubtitle']))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("NEXTONES.FINANCE", styles['CoverBrand']))
    story.append(Spacer(1, 18 * mm))

    story.append(Paragraph(
        "Ce document est le guide complet de l\u2019administrateur de la plateforme "
        "<b>Nextones Desk</b>. Il couvre l\u2019architecture technique, la gestion des utilisateurs "
        "et des r\u00f4les, la configuration du moteur de risque et des agents IA, "
        "la gestion des donn\u00e9es, le backtest, la base de donn\u00e9es, le monitoring, "
        "la sauvegarde et la s\u00e9curit\u00e9.",
        styles['Body']
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Architecture : Backend FastAPI (Python) + Frontend Vanilla JS + Base SQLite + Agents IA",
        styles['Body']
    ))
    story.append(Spacer(1, 10 * mm))

    meta_data = [
        ["Auteur", "Perplexity Computer"],
        ["Destinataires", "Administrateurs Nextones Desk"],
        ["Date de cr\u00e9ation", "Mars 2026"],
        ["Derni\u00e8re mise \u00e0 jour", "5 mars 2026"],
        ["Statut", "Version 2.0 — Finale"],
    ]
    meta_table = Table(meta_data, colWidths=[50 * mm, 100 * mm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), TEAL_DARK),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, WARM_BEIGE),
    ]))
    story.append(meta_table)

    # Switch to content template before first page break
    story.append(NextPageTemplate('Content'))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # TABLE OF CONTENTS
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("Table des mati\u00e8res", styles['SectionTitle']))
    story.append(HorizontalRule(aw, TEAL_PRIMARY, 1.5))
    story.append(Spacer(1, 8 * mm))

    toc_items = [
        ("1.", "Introduction"),
        ("2.", "Architecture technique"),
        ("3.", "Gestion des utilisateurs"),
        ("4.", "Syst\u00e8me de r\u00f4les et permissions"),
        ("5.", "Configuration du moteur de risque"),
        ("6.", "Configuration des agents IA"),
        ("7.", "Gestion des donn\u00e9es"),
        ("8.", "Backtest et export CSV"),
        ("9.", "Base de donn\u00e9es"),
        ("10.", "Monitoring et logs"),
        ("11.", "Sauvegarde et maintenance"),
        ("12.", "S\u00e9curit\u00e9"),
    ]

    toc_style = ParagraphStyle(
        'TOCItem', fontName='Helvetica', fontSize=12, leading=22,
        textColor=TEAL_DARK, leftIndent=10,
    )
    toc_num_style = ParagraphStyle(
        'TOCNum', fontName='Helvetica-Bold', fontSize=12, leading=22,
        textColor=TEAL_PRIMARY,
    )

    for num, title in toc_items:
        t = Table(
            [[Paragraph(num, toc_num_style), Paragraph(title, toc_style)]],
            colWidths=[14 * mm, aw - 14 * mm]
        )
        t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('LINEBELOW', (0, 0), (-1, -1), 0.3, WARM_BEIGE),
        ]))
        story.append(t)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # 1. INTRODUCTION
    # ═══════════════════════════════════════════════════════════════════
    section_header(1, "Introduction", styles, story)

    story.append(Paragraph("1.1 R\u00f4le de l\u2019administrateur", styles['SubSection']))
    story.append(Paragraph(
        "L\u2019administrateur <b>Nextones Desk</b> est responsable du bon fonctionnement "
        "de la plateforme. Ses responsabilit\u00e9s incluent :",
        styles['Body']
    ))
    admin_duties = [
        "\u2022  <b>Gestion des utilisateurs</b> : cr\u00e9ation de comptes, attribution des r\u00f4les, activation/d\u00e9sactivation",
        "\u2022  <b>Configuration du moteur de risque</b> : param\u00e9trage VaR, limites de position et secteur",
        "\u2022  <b>Configuration des agents IA</b> : activation et param\u00e9trage des agents de recherche",
        "\u2022  <b>Gestion des donn\u00e9es</b> : supervision de l\u2019ingestion de donn\u00e9es march\u00e9 et macro\u00e9conomiques",
        "\u2022  <b>Maintenance</b> : sauvegarde de la base de donn\u00e9es, rotation des logs, monitoring",
        "\u2022  <b>S\u00e9curit\u00e9</b> : gestion des tokens JWT, politique de mots de passe, configuration CORS",
    ]
    for item in admin_duties:
        story.append(Paragraph(item, styles['BulletItem']))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("1.2 Pr\u00e9sentation de Nextones Desk", styles['SubSection']))
    story.append(Paragraph(
        "<b>Nextones Desk</b> est une plateforme de gestion de portefeuille propri\u00e9taire "
        "con\u00e7ue pour les \u00e9quipes d\u2019investissement. Elle int\u00e8gre un moteur de risque "
        "(Value at Risk param\u00e9trique), des agents de recherche IA sp\u00e9cialis\u00e9s, "
        "et un cycle de d\u00e9cision automatis\u00e9 (paper broker) permettant de simuler "
        "des op\u00e9rations de march\u00e9.",
        styles['Body']
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Les modules principaux sont :", styles['Body']))
    features = [
        "\u2022  <b>Dashboard Today</b> \u2014 R\u00e9sum\u00e9 portefeuille, positions, courbe d\u2019\u00e9quit\u00e9, flux d\u2019\u00e9v\u00e9nements",
        "\u2022  <b>Theses</b> \u2014 Th\u00e8ses d\u2019investissement g\u00e9n\u00e9r\u00e9es par IA, scores de conviction, workflow d\u2019approbation",
        "\u2022  <b>Orders &amp; Executions</b> \u2014 Flux d\u2019ordres paper trading, remplissages, historique",
        "\u2022  <b>Market Intel</b> \u2014 Stock Signals (Finviz), Dynamique Sectorielle, Crypto TOP 25 (CoinGecko)",
        "\u2022  <b>Macro US</b> \u2014 Dashboard vuln\u00e9rabilit\u00e9 (FRED), calendrier \u00e9conomique, risque g\u00e9opolitique",
        "\u2022  <b>IC Memos</b> \u2014 M\u00e9mos comit\u00e9 d\u2019investissement auto-g\u00e9n\u00e9r\u00e9s, export PDF/Markdown",
        "\u2022  <b>Backtest</b> \u2014 Backtester de portefeuille, courbe d\u2019\u00e9quit\u00e9, export CSV du journal",
        "\u2022  <b>Administration</b> \u2014 Gestion des utilisateurs (CRUD), 4 r\u00f4les, RBAC",
    ]
    for f in features:
        story.append(Paragraph(f, styles['BulletItem']))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # 2. ARCHITECTURE TECHNIQUE
    # ═══════════════════════════════════════════════════════════════════
    section_header(2, "Architecture technique", styles, story)

    story.append(Paragraph("2.1 Vue d\u2019ensemble", styles['SubSection']))
    story.append(Paragraph(
        "Nextones Desk repose sur une architecture l\u00e9g\u00e8re et modulaire, "
        "id\u00e9ale pour un d\u00e9ploiement rapide :",
        styles['Body']
    ))

    arch_headers = ["Composant", "Technologie", "Description"]
    arch_rows = [
        ["Backend", "FastAPI (Python 3.11+)", "API RESTful asynchrone, port 8000"],
        ["Frontend", "Vanilla JS, Chart.js", "SPA statique HTML/CSS/JS, sans framework"],
        ["Base de donn\u00e9es", "SQLite3", "Base fichier, z\u00e9ro configuration"],
        ["Authentification", "JWT + bcrypt", "Tokens 24h, hachage bcrypt"],
        ["Agents IA", "Python (4+1 agents)", "Macro, Factor, Microstructure, Crypto, AltData"],
        ["Moteur de risque", "NumPy / Pandas", "VaR 95%, limites position/secteur"],
        ["Serveur ASGI", "Uvicorn", "Serveur ASGI performant"],
    ]
    story.append(make_table(arch_headers, arch_rows,
                            col_widths=[35 * mm, 45 * mm, aw - 80 * mm]))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("2.2 Structure des fichiers", styles['SubSection']))
    tree = """nextones-desk/
|-- api_server.py          # Serveur FastAPI (port 8000)
|-- models.py              # Schema SQLite (tables)
|-- agents.py              # Agents IA de recherche
|-- risk_engine.py         # Moteur de risque (VaR)
|-- execution_engine.py    # Paper broker + cycle de decision
|-- memo_generator.py      # Generateur de memos IC
|-- data_ingestion.py      # Ingestion Yahoo Finance, FRED, etc.
|-- seed_data.py           # Donnees de demonstration
|-- requirements.txt       # Dependances Python
|-- nextones.db            # Base SQLite (creee au demarrage)
|-- index.html             # Frontend SPA
|-- base.css / style.css   # Styles
|-- app.js                 # Logique frontend (vanilla JS)
`-- RUNBOOK.md             # Documentation operationnelle"""
    story.append(code_block(tree, aw))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("2.3 D\u00e9pendances Python", styles['SubSection']))
    story.append(Paragraph(
        "Les d\u00e9pendances principales sont d\u00e9finies dans "
        "<font face='Courier' size='9'>requirements.txt</font> :",
        styles['Body']
    ))
    deps_code = """fastapi, uvicorn[standard]
passlib[bcrypt]==4.0.1, python-jose[cryptography], bcrypt==4.0.1
yfinance, numpy, pandas, requests
reportlab (generation PDF)"""
    story.append(code_block(deps_code, aw))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "<i>Installation : </i><font face='Courier' size='9'>pip install -r requirements.txt</font>",
        styles['Note']
    ))

    story.append(Spacer(1, 6 * mm))

    # ═══════════════════════════════════════════════════════════════════
    # 3. GESTION DES UTILISATEURS
    # ═══════════════════════════════════════════════════════════════════
    section_header(3, "Gestion des utilisateurs", styles, story)

    story.append(Paragraph(
        "Le panneau d\u2019administration (onglet <b>Administration</b>, visible uniquement pour "
        "le r\u00f4le admin) permet la gestion compl\u00e8te des utilisateurs de la plateforme.",
        styles['Body']
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("3.1 Cr\u00e9er un utilisateur", styles['SubSection']))
    story.append(Paragraph(
        "Pour cr\u00e9er un nouvel utilisateur, acc\u00e9dez au panneau Administration et cliquez "
        "sur <b>Nouvel utilisateur</b>. Les champs requis sont :",
        styles['Body']
    ))
    user_fields = [
        "\u2022  <b>username</b> \u2014 Identifiant unique de connexion (alphanum\u00e9rique, sans espace)",
        "\u2022  <b>email</b> \u2014 Adresse e-mail valide de l\u2019utilisateur",
        "\u2022  <b>password</b> \u2014 Mot de passe initial (minimum 8 caract\u00e8res recommand\u00e9)",
        "\u2022  <b>full_name</b> \u2014 Nom complet affich\u00e9 dans l\u2019interface",
        "\u2022  <b>role</b> \u2014 R\u00f4le attribu\u00e9 : viewer, analyst, manager ou admin",
    ]
    for f in user_fields:
        story.append(Paragraph(f, styles['BulletItem']))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Appel API correspondant :", styles['BodyBold']))
    story.append(code_block(
        'POST /api/admin/users\nContent-Type: application/json\nAuthorization: Bearer <token_admin>\n\n{\n  "username": "jdupont",\n  "email": "j.dupont@nextones.finance",\n  "password": "SecurePass2026!",\n  "full_name": "Jean Dupont",\n  "role": "analyst"\n}',
        aw
    ))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("3.2 Modifier le r\u00f4le d\u2019un utilisateur", styles['SubSection']))
    story.append(Paragraph(
        "Dans le panneau Administration, chaque utilisateur dispose d\u2019un menu d\u00e9roulant "
        "permettant de changer son r\u00f4le. La modification est imm\u00e9diate.",
        styles['Body']
    ))
    story.append(code_block(
        'PUT /api/admin/users/{id}\nAuthorization: Bearer <token_admin>\n\n{\n  "role": "manager"\n}',
        aw
    ))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("3.3 Activer / D\u00e9sactiver un utilisateur", styles['SubSection']))
    story.append(Paragraph(
        "La d\u00e9sactivation d\u2019un utilisateur est un <b>soft delete</b> : le compte est "
        "marqu\u00e9 comme inactif mais n\u2019est pas supprim\u00e9 de la base. L\u2019utilisateur ne peut plus "
        "se connecter tant que son compte n\u2019est pas r\u00e9activ\u00e9.",
        styles['Body']
    ))
    story.append(Paragraph(
        "Pour d\u00e9sactiver un utilisateur via l\u2019API :",
        styles['Body']
    ))
    story.append(code_block(
        'DELETE /api/admin/users/{id}\nAuthorization: Bearer <token_admin>\n\n# Reponse : {"success": true, "message": "Utilisateur desactive"}',
        aw
    ))
    story.append(Paragraph(
        "Pour r\u00e9activer, utilisez l\u2019endpoint PUT avec le statut :",
        styles['Body']
    ))
    story.append(code_block(
        'PUT /api/admin/users/{id}\nAuthorization: Bearer <token_admin>\n\n{\n  "is_active": true\n}',
        aw
    ))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("3.4 R\u00e9initialiser un mot de passe", styles['SubSection']))
    story.append(Paragraph(
        "L\u2019administrateur peut forcer la r\u00e9initialisation du mot de passe d\u2019un utilisateur. "
        "Le nouveau mot de passe doit \u00eatre communiqu\u00e9 \u00e0 l\u2019utilisateur de mani\u00e8re s\u00e9curis\u00e9e.",
        styles['Body']
    ))
    story.append(code_block(
        'POST /api/admin/users/{id}/reset-password\nAuthorization: Bearer <token_admin>\n\n{\n  "new_password": "NouveauPass2026!"\n}',
        aw
    ))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("3.5 Endpoints API Administration", styles['SubSection']))
    api_headers = ["M\u00e9thode", "Endpoint", "Description"]
    api_rows = [
        ["GET", "/api/admin/users", "Lister tous les utilisateurs"],
        ["POST", "/api/admin/users", "Cr\u00e9er un utilisateur"],
        ["PUT", "/api/admin/users/{id}", "Modifier r\u00f4le / statut / nom"],
        ["POST", "/api/admin/users/{id}/reset-password", "R\u00e9initialiser le mot de passe"],
        ["DELETE", "/api/admin/users/{id}", "D\u00e9sactiver un utilisateur"],
        ["GET", "/api/admin/roles", "Lister les r\u00f4les et permissions"],
    ]
    story.append(make_table(api_headers, api_rows,
                            col_widths=[20 * mm, 65 * mm, aw - 85 * mm]))
    story.append(Spacer(1, 3 * mm))
    story.append(info_box(
        "<b>Note :</b> Tous les endpoints <font face='Courier' size='9'>/api/admin/*</font> "
        "sont r\u00e9serv\u00e9s au r\u00f4le <b>admin</b>. Toute tentative d\u2019acc\u00e8s par un r\u00f4le inf\u00e9rieur "
        "retourne une erreur HTTP 403 Forbidden.",
        styles
    ))

    story.append(Spacer(1, 6 * mm))

    # ═══════════════════════════════════════════════════════════════════
    # 4. SYSTÈME DE RÔLES ET PERMISSIONS
    # ═══════════════════════════════════════════════════════════════════
    section_header(4, "Syst\u00e8me de r\u00f4les et permissions", styles, story)

    story.append(Paragraph(
        "Nextones Desk impl\u00e9mente un syst\u00e8me RBAC (Role-Based Access Control) "
        "avec 4 r\u00f4les hi\u00e9rarchiques. Chaque r\u00f4le h\u00e9rite des permissions du r\u00f4le inf\u00e9rieur.",
        styles['Body']
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("4.1 Hi\u00e9rarchie des r\u00f4les", styles['SubSection']))

    roles_headers = ["R\u00f4le", "Niv.", "Description", "Permissions"]
    roles_rows = [
        ["Viewer", "0", "Lecture seule",
         "Consultation dashboards, rapports, th\u00e8ses, m\u00e9mos"],
        ["Analyst", "1", "Viewer + analyse",
         "Propositions de th\u00e8ses, backtests, export CSV"],
        ["Manager", "2", "Analyst + gestion",
         "Validation th\u00e8ses, lancement cycles d\u2019ex\u00e9cution et d\u2019ingestion"],
        ["Admin", "3", "Acc\u00e8s total",
         "Gestion utilisateurs, configuration risk, acc\u00e8s complet"],
    ]
    story.append(make_table(roles_headers, roles_rows,
                            col_widths=[22 * mm, 14 * mm, 35 * mm, aw - 71 * mm]))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("4.2 Matrice des permissions d\u00e9taill\u00e9e", styles['SubSection']))

    perm_headers = ["Action", "Viewer", "Analyst", "Manager", "Admin"]
    perm_rows = [
        ["Consulter le dashboard", "\u2713", "\u2713", "\u2713", "\u2713"],
        ["Consulter les th\u00e8ses", "\u2713", "\u2713", "\u2713", "\u2713"],
        ["Consulter les m\u00e9mos IC", "\u2713", "\u2713", "\u2713", "\u2713"],
        ["Consulter Market Intel", "\u2713", "\u2713", "\u2713", "\u2713"],
        ["Proposer une th\u00e8se", "\u2717", "\u2713", "\u2713", "\u2713"],
        ["Lancer un backtest", "\u2717", "\u2713", "\u2713", "\u2713"],
        ["Exporter en CSV", "\u2717", "\u2713", "\u2713", "\u2713"],
        ["Valider une th\u00e8se", "\u2717", "\u2717", "\u2713", "\u2713"],
        ["Lancer un cycle d\u2019ex\u00e9cution", "\u2717", "\u2717", "\u2713", "\u2713"],
        ["Lancer l\u2019ingestion", "\u2717", "\u2717", "\u2713", "\u2713"],
        ["Lancer les agents IA", "\u2717", "\u2717", "\u2713", "\u2713"],
        ["G\u00e9rer les utilisateurs", "\u2717", "\u2717", "\u2717", "\u2713"],
        ["Configurer le risk engine", "\u2717", "\u2717", "\u2717", "\u2713"],
    ]
    story.append(make_table(perm_headers, perm_rows,
                            col_widths=[50 * mm, 20 * mm, 20 * mm, 22 * mm, 20 * mm]))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("4.3 Endpoints prot\u00e9g\u00e9s par r\u00f4le", styles['SubSection']))

    prot_headers = ["Endpoint", "M\u00e9thode", "R\u00f4le minimum"]
    prot_rows = [
        ["/api/orders/execute-cycle", "POST", "Manager"],
        ["/api/run-agents", "POST", "Manager"],
        ["/api/run-ingestion", "POST", "Manager"],
        ["/api/risk-config", "PUT", "Admin"],
        ["/api/admin/users", "GET/POST", "Admin"],
        ["/api/admin/users/{id}", "PUT/DELETE", "Admin"],
        ["/api/admin/users/{id}/reset-password", "POST", "Admin"],
        ["/api/admin/roles", "GET", "Admin"],
    ]
    story.append(make_table(prot_headers, prot_rows,
                            col_widths=[60 * mm, 25 * mm, aw - 85 * mm]))
    story.append(Spacer(1, 3 * mm))
    story.append(info_box(
        "<b>Important :</b> Le middleware d\u2019authentification v\u00e9rifie le token JWT puis "
        "le r\u00f4le de l\u2019utilisateur avant chaque requ\u00eate. Un token expir\u00e9 retourne "
        "HTTP 401, un r\u00f4le insuffisant retourne HTTP 403.",
        styles
    ))

    story.append(Spacer(1, 6 * mm))

    # ═══════════════════════════════════════════════════════════════════
    # 5. CONFIGURATION DU MOTEUR DE RISQUE
    # ═══════════════════════════════════════════════════════════════════
    section_header(5, "Configuration du moteur de risque", styles, story)

    story.append(Paragraph(
        "Le moteur de risque int\u00e9gr\u00e9 calcule en temps r\u00e9el la Value at Risk (VaR) "
        "du portefeuille et applique un ensemble de limites configur\u00e9es par l\u2019administrateur.",
        styles['Body']
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("5.1 Param\u00e8tres VaR", styles['SubSection']))
    var_headers = ["Param\u00e8tre", "Valeur par d\u00e9faut", "Description"]
    var_rows = [
        ["Niveau de confiance", "95%", "VaR param\u00e9trique \u00e0 1 jour"],
        ["Horizon", "1 jour", "P\u00e9riode de calcul du risque"],
        ["Fen\u00eatre historique", "252 jours", "Historique de prix utilis\u00e9 pour les corr\u00e9lations"],
        ["M\u00e9thode", "Param\u00e9trique", "Bas\u00e9e sur matrice de variance-covariance"],
    ]
    story.append(make_table(var_headers, var_rows,
                            col_widths=[40 * mm, 35 * mm, aw - 75 * mm]))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("5.2 Limites de position", styles['SubSection']))
    story.append(Paragraph(
        "Les limites de position contr\u00f4lent la concentration maximale du portefeuille "
        "sur un instrument ou un secteur donn\u00e9 :",
        styles['Body']
    ))
    limits_items = [
        "\u2022  <b>Position individuelle max</b> : pourcentage maximum de l\u2019AUM allou\u00e9 \u00e0 un seul instrument",
        "\u2022  <b>Limite sectorielle</b> : pourcentage maximum de l\u2019AUM allou\u00e9 \u00e0 un secteur",
        "\u2022  <b>Drawdown max</b> : seuil de drawdown d\u00e9clenchant une alerte ou un gel des ordres",
    ]
    for item in limits_items:
        story.append(Paragraph(item, styles['BulletItem']))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("5.3 Modifier la configuration via API", styles['SubSection']))
    story.append(Paragraph(
        "Seul un administrateur peut modifier la configuration du moteur de risque :",
        styles['Body']
    ))
    story.append(code_block(
        'PUT /api/risk-config\nAuthorization: Bearer <token_admin>\nContent-Type: application/json\n\n{\n  "var_confidence": 0.95,\n  "max_position_pct": 15.0,\n  "max_sector_pct": 30.0,\n  "max_drawdown_pct": 10.0\n}',
        aw
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(info_box(
        "<b>Attention :</b> La modification de la configuration du moteur de risque prend "
        "effet imm\u00e9diatement. V\u00e9rifiez les param\u00e8tres avant de valider. Les limites trop "
        "restrictives peuvent bloquer le cycle d\u2019ex\u00e9cution.",
        styles
    ))

    story.append(Spacer(1, 6 * mm))

    # ═══════════════════════════════════════════════════════════════════
    # 6. CONFIGURATION DES AGENTS IA
    # ═══════════════════════════════════════════════════════════════════
    section_header(6, "Configuration des agents IA", styles, story)

    story.append(Paragraph(
        "Nextones Desk dispose de 5 agents de recherche IA sp\u00e9cialis\u00e9s. Chaque agent "
        "analyse un aspect diff\u00e9rent du march\u00e9 et g\u00e9n\u00e8re des th\u00e8ses d\u2019investissement "
        "avec un score de conviction.",
        styles['Body']
    ))
    story.append(Spacer(1, 4 * mm))

    agents_headers = ["Agent", "Sp\u00e9cialit\u00e9", "Sources de donn\u00e9es"]
    agents_rows = [
        ["MacroAgent", "Analyse macro\u00e9conomique US (taux, inflation, emploi)",
         "FRED API, GDELT, USGS"],
        ["FactorAgent", "Analyse factorielle (value, momentum, qualit\u00e9)",
         "Yahoo Finance, calculs internes"],
        ["MicrostructureAgent", "Signaux techniques, flux d\u2019ordres, volatil. implicite",
         "Finviz, Yahoo Finance"],
        ["CryptoAgent", "Analyse march\u00e9 crypto (TOP 25), corr\u00e9lations",
         "CoinGecko API"],
        ["AltDataAgent", "Donn\u00e9es alternatives, sentiment, g\u00e9opolitique",
         "GDELT, Finviz, signaux sentiment"],
    ]
    story.append(make_table(agents_headers, agents_rows,
                            col_widths=[38 * mm, 52 * mm, aw - 90 * mm]))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("6.1 Lancer les agents", styles['SubSection']))
    story.append(Paragraph(
        "Le lancement des agents n\u00e9cessite le r\u00f4le <b>Manager</b> ou sup\u00e9rieur. "
        "Les agents analysent les donn\u00e9es disponibles et g\u00e9n\u00e8rent de nouvelles th\u00e8ses :",
        styles['Body']
    ))
    story.append(code_block(
        'POST /api/run-agents\nAuthorization: Bearer <token_manager_ou_admin>\n\n# Reponse :\n# {"success": true, "theses_generated": 12, "agents_run": 5}',
        aw
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("6.2 Cycle de d\u00e9cision", styles['SubSection']))
    story.append(Paragraph(
        "Le cycle de d\u00e9cision collecte les th\u00e8ses des agents, les \u00e9value via le moteur "
        "de risque, et g\u00e9n\u00e8re des ordres (paper trading). Il est d\u00e9clench\u00e9 manuellement "
        "ou peut \u00eatre automatis\u00e9 :",
        styles['Body']
    ))
    story.append(code_block(
        'POST /api/orders/execute-cycle\nAuthorization: Bearer <token_manager_ou_admin>\n\n# Reponse :\n# {"success": true, "orders_created": 4, "orders_filled": 3}',
        aw
    ))

    story.append(Spacer(1, 6 * mm))

    # ═══════════════════════════════════════════════════════════════════
    # 7. GESTION DES DONNÉES
    # ═══════════════════════════════════════════════════════════════════
    section_header(7, "Gestion des donn\u00e9es", styles, story)

    story.append(Paragraph(
        "Nextones Desk ing\u00e8re des donn\u00e9es de march\u00e9 depuis plusieurs sources externes. "
        "L\u2019administrateur peut d\u00e9clencher l\u2019ingestion manuellement ou la planifier.",
        styles['Body']
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("7.1 Sources de donn\u00e9es", styles['SubSection']))
    data_headers = ["Source", "Type de donn\u00e9es", "Fr\u00e9quence", "Cl\u00e9 API"]
    data_rows = [
        ["Yahoo Finance", "Prix historiques, actions", "Quotidien", "Non requise"],
        ["CoinGecko", "Crypto TOP 25, prix live", "Temps r\u00e9el", "Non requise"],
        ["FRED", "Macro US (taux, inflation, emploi)", "Hebdomadaire", "Cl\u00e9 API gratuite"],
        ["GDELT", "Risque g\u00e9opolitique mondial", "Quotidien", "Non requise"],
        ["Finviz", "Signaux techniques actions", "Quotidien", "Non requise"],
    ]
    story.append(make_table(data_headers, data_rows,
                            col_widths=[30 * mm, 40 * mm, 28 * mm, aw - 98 * mm]))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("7.2 Lancer l\u2019ingestion", styles['SubSection']))
    story.append(Paragraph(
        "L\u2019ingestion met \u00e0 jour les prix, les donn\u00e9es macro et les signaux dans la base "
        "de donn\u00e9es. Elle n\u00e9cessite le r\u00f4le Manager ou Admin :",
        styles['Body']
    ))
    story.append(code_block(
        'POST /api/run-ingestion\nAuthorization: Bearer <token_manager_ou_admin>\n\n# Reponse :\n# {"success": true, "instruments_updated": 14, "macro_updated": true}',
        aw
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("7.3 Configuration de la cl\u00e9 FRED", styles['SubSection']))
    story.append(Paragraph(
        "La cl\u00e9 API FRED est n\u00e9cessaire pour les donn\u00e9es macro\u00e9conomiques. "
        "Elle peut \u00eatre d\u00e9finie comme variable d\u2019environnement ou dans le fichier de configuration :",
        styles['Body']
    ))
    story.append(code_block(
        '# Variable d\'environnement\nexport FRED_API_KEY="votre_cle_fred_ici"\n\n# Ou dans api_server.py\nFRED_API_KEY = "votre_cle_fred_ici"',
        aw
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(info_box(
        "<b>Note :</b> Les cl\u00e9s API FRED sont gratuites et disponibles sur "
        "https://fred.stlouisfed.org/docs/api/api_key.html. "
        "Les autres sources (Yahoo Finance, CoinGecko, GDELT, Finviz) ne requi\u00e8rent pas de cl\u00e9.",
        styles
    ))

    story.append(Spacer(1, 6 * mm))

    # ═══════════════════════════════════════════════════════════════════
    # 8. BACKTEST ET EXPORT CSV
    # ═══════════════════════════════════════════════════════════════════
    section_header(8, "Backtest et export CSV", styles, story)

    story.append(Paragraph(
        "Le module de backtest permet de tester une strat\u00e9gie sur des donn\u00e9es historiques "
        "Yahoo Finance. Il g\u00e9n\u00e8re une courbe d\u2019\u00e9quit\u00e9, des statistiques de performance "
        "et un journal de trading exportable en CSV.",
        styles['Body']
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("8.1 Configuration du backtest", styles['SubSection']))
    bt_items = [
        "\u2022  <b>P\u00e9riode</b> : s\u00e9lection des dates de d\u00e9but et de fin",
        "\u2022  <b>Univers d\u2019investissement</b> : s\u00e9lection des instruments \u00e0 inclure",
        "\u2022  <b>Benchmark</b> : comparaison avec SPY ou QQQ",
        "\u2022  <b>Capital initial</b> : montant de d\u00e9part du portefeuille simul\u00e9",
        "\u2022  <b>R\u00e9\u00e9quilibrage</b> : fr\u00e9quence de rebalancement (quotidien, hebdomadaire, mensuel)",
    ]
    for item in bt_items:
        story.append(Paragraph(item, styles['BulletItem']))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("8.2 R\u00e9sultats du backtest", styles['SubSection']))
    story.append(Paragraph(
        "Apr\u00e8s ex\u00e9cution, le backtest affiche :",
        styles['Body']
    ))
    results_items = [
        "\u2022  <b>Courbe d\u2019\u00e9quit\u00e9</b> : \u00e9volution de la valeur du portefeuille vs benchmark",
        "\u2022  <b>Statistiques</b> : rendement total, rendement annualis\u00e9, Sharpe ratio, max drawdown",
        "\u2022  <b>Performance par actif</b> : contribution de chaque instrument",
        "\u2022  <b>Journal de trading</b> : d\u00e9tail quotidien de chaque position",
    ]
    for item in results_items:
        story.append(Paragraph(item, styles['BulletItem']))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("8.3 Export CSV du journal de trading", styles['SubSection']))
    story.append(Paragraph(
        "Le bouton <b>Exporter CSV</b> g\u00e9n\u00e8re un fichier CSV t\u00e9l\u00e9chargeable contenant "
        "le journal complet du backtest. Le format est optimis\u00e9 pour Excel fran\u00e7ais.",
        styles['Body']
    ))
    story.append(Spacer(1, 2 * mm))

    csv_headers = ["Colonne", "Description", "Exemple"]
    csv_rows = [
        ["Date", "Date de la ligne", "2025-12-15"],
        ["Ticker", "Symbole de l\u2019instrument", "AAPL"],
        ["Poids (%)", "Poids dans le portefeuille", "12.5"],
        ["Prix", "Prix de cl\u00f4ture", "198.50"],
        ["Rendement Jour (%)", "Rendement quotidien", "0.85"],
        ["Rendement Cumul (%)", "Rendement cumul\u00e9", "14.32"],
        ["Valeur Position", "Valeur en USD", "24,812.50"],
    ]
    story.append(make_table(csv_headers, csv_rows,
                            col_widths=[35 * mm, 50 * mm, aw - 85 * mm]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "<i>Format : s\u00e9parateur point-virgule (;), encodage UTF-8 BOM, compatible Excel FR. "
        "L\u2019export peut \u00eatre r\u00e9alis\u00e9 c\u00f4t\u00e9 client (Blob download) ou via "
        "l\u2019endpoint serveur <font face='Courier' size='8'>POST /api/backtest/export-csv</font>.</i>",
        styles['Note']
    ))

    story.append(Spacer(1, 6 * mm))

    # ═══════════════════════════════════════════════════════════════════
    # 9. BASE DE DONNÉES
    # ═══════════════════════════════════════════════════════════════════
    section_header(9, "Base de donn\u00e9es", styles, story)

    story.append(Paragraph(
        "Nextones Desk utilise <b>SQLite3</b> comme base de donn\u00e9es. Le fichier "
        "<font face='Courier' size='9'>nextones.db</font> est cr\u00e9\u00e9 automatiquement "
        "au premier d\u00e9marrage du serveur.",
        styles['Body']
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("9.1 Tables principales", styles['SubSection']))

    db_headers = ["Table", "Description", "Colonnes cl\u00e9s"]
    db_rows = [
        ["users", "Utilisateurs et authentification",
         "id, username, email, hashed_password, full_name, role, is_active, last_login"],
        ["instruments", "Univers d\u2019instruments",
         "id, ticker, name, sector, asset_class"],
        ["prices", "Historique de prix",
         "id, instrument_id, date, open, high, low, close, volume"],
        ["positions", "Positions du portefeuille",
         "id, instrument_id, quantity, avg_price, current_value"],
        ["theses", "Th\u00e8ses d\u2019investissement IA",
         "id, agent, ticker, direction, conviction, rationale, status"],
        ["orders", "Ordres de trading (paper)",
         "id, instrument_id, side, quantity, price, status, created_at"],
        ["fills", "Ex\u00e9cutions d\u2019ordres",
         "id, order_id, fill_price, fill_quantity, filled_at"],
        ["ic_memos", "M\u00e9mos comit\u00e9 d\u2019investissement",
         "id, title, content, created_at"],
        ["events", "Journal d\u2019\u00e9v\u00e9nements",
         "id, event_type, description, timestamp"],
        ["risk_snapshots", "Snapshots risque portefeuille",
         "id, var_95, total_exposure, timestamp"],
        ["portfolio", "M\u00e9ta-donn\u00e9es portefeuille",
         "id, aum, cash, equity_curve_data"],
        ["macro_data", "Donn\u00e9es macro\u00e9conomiques",
         "id, indicator, value, date, source"],
    ]
    story.append(make_table(db_headers, db_rows,
                            col_widths=[28 * mm, 42 * mm, aw - 70 * mm]))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("9.2 Acc\u00e8s direct \u00e0 la base", styles['SubSection']))
    story.append(Paragraph(
        "Pour inspecter la base de donn\u00e9es directement (diagnostic ou d\u00e9bogage) :",
        styles['Body']
    ))
    story.append(code_block(
        '# Ouvrir la base SQLite en ligne de commande\nsqlite3 nextones.db\n\n# Lister les tables\n.tables\n\n# Voir le schema d\'une table\n.schema users\n\n# Compter les utilisateurs\nSELECT COUNT(*) FROM users;\n\n# Voir les derniers evenements\nSELECT * FROM events ORDER BY timestamp DESC LIMIT 10;',
        aw
    ))

    story.append(Spacer(1, 6 * mm))

    # ═══════════════════════════════════════════════════════════════════
    # 10. MONITORING ET LOGS
    # ═══════════════════════════════════════════════════════════════════
    section_header(10, "Monitoring et logs", styles, story)

    story.append(Paragraph("10.1 Event log", styles['SubSection']))
    story.append(Paragraph(
        "Tous les \u00e9v\u00e9nements significatifs de la plateforme sont enregistr\u00e9s dans "
        "la table <font face='Courier' size='9'>events</font> de la base de donn\u00e9es. "
        "Le flux d\u2019\u00e9v\u00e9nements est visible sur le Dashboard Today.",
        styles['Body']
    ))
    story.append(Spacer(1, 2 * mm))
    event_types = [
        "\u2022  <b>INGESTION</b> \u2014 Mise \u00e0 jour des donn\u00e9es de march\u00e9",
        "\u2022  <b>AGENT_RUN</b> \u2014 Ex\u00e9cution d\u2019un agent IA",
        "\u2022  <b>ORDER_CREATED</b> \u2014 Cr\u00e9ation d\u2019un ordre",
        "\u2022  <b>ORDER_FILLED</b> \u2014 Ex\u00e9cution d\u2019un ordre",
        "\u2022  <b>RISK_ALERT</b> \u2014 D\u00e9passement d\u2019une limite de risque",
        "\u2022  <b>USER_LOGIN</b> \u2014 Connexion d\u2019un utilisateur",
        "\u2022  <b>USER_CREATED</b> \u2014 Cr\u00e9ation d\u2019un nouveau compte",
        "\u2022  <b>CONFIG_CHANGE</b> \u2014 Modification de la configuration",
    ]
    for item in event_types:
        story.append(Paragraph(item, styles['BulletItem']))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("10.2 Health check", styles['SubSection']))
    story.append(Paragraph(
        "L\u2019endpoint de sant\u00e9 permet de v\u00e9rifier que le serveur est op\u00e9rationnel :",
        styles['Body']
    ))
    story.append(code_block(
        'GET /api/health\n\n# Reponse :\n{\n  "status": "healthy",\n  "timestamp": "2026-03-05T10:30:00Z",\n  "service": "Nextones.finance API",\n  "db_status": "connected",\n  "uptime_seconds": 86400\n}',
        aw
    ))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("10.3 Logs serveur", styles['SubSection']))
    story.append(Paragraph(
        "Les logs du serveur FastAPI/Uvicorn sont \u00e9mis sur la sortie standard (stdout). "
        "En production, redirigez les logs vers un fichier :",
        styles['Body']
    ))
    story.append(code_block(
        '# Rediriger les logs en production\nuvicorn api_server:app --host 0.0.0.0 --port 8000 \\\n  --log-level info \\\n  --access-log \\\n  2>&1 | tee -a /var/log/nextones-desk.log\n\n# Ou via systemd (logs automatiques via journalctl)\njournalctl -u nextones-desk -f',
        aw
    ))

    story.append(Spacer(1, 6 * mm))

    # ═══════════════════════════════════════════════════════════════════
    # 11. SAUVEGARDE ET MAINTENANCE
    # ═══════════════════════════════════════════════════════════════════
    section_header(11, "Sauvegarde et maintenance", styles, story)

    story.append(Paragraph("11.1 Sauvegarde de la base SQLite", styles['SubSection']))
    story.append(Paragraph(
        "La base de donn\u00e9es SQLite est un fichier unique, ce qui simplifie consid\u00e9rablement "
        "la proc\u00e9dure de sauvegarde. Il est recommand\u00e9 de sauvegarder quotidiennement.",
        styles['Body']
    ))
    story.append(Spacer(1, 2 * mm))

    story.append(Paragraph("Sauvegarde manuelle :", styles['BodyBold']))
    story.append(code_block(
        '# Copie simple du fichier (arreter le serveur si possible)\ncp nextones.db nextones_backup_$(date +%Y%m%d).db\n\n# Sauvegarde en ligne avec sqlite3 (sans arret du serveur)\nsqlite3 nextones.db ".backup nextones_backup.db"',
        aw
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Script de sauvegarde automatique (cron) :", styles['BodyBold']))
    story.append(code_block(
        '#!/bin/bash\n# /opt/nextones-desk/backup.sh\nBACKUP_DIR="/opt/nextones-desk/backups"\nDB_PATH="/opt/nextones-desk/nextones.db"\nDATE=$(date +%Y%m%d_%H%M%S)\n\nmkdir -p $BACKUP_DIR\nsqlite3 $DB_PATH ".backup $BACKUP_DIR/nextones_$DATE.db"\n\n# Supprimer les sauvegardes de plus de 30 jours\nfind $BACKUP_DIR -name "nextones_*.db" -mtime +30 -delete\n\necho "Backup completed: nextones_$DATE.db"',
        aw
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Ajouter au crontab :", styles['BodyBold']))
    story.append(code_block(
        '# Sauvegarde quotidienne a 2h00\n0 2 * * * /opt/nextones-desk/backup.sh >> /var/log/nextones-backup.log 2>&1',
        aw
    ))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("11.2 Rotation des logs", styles['SubSection']))
    story.append(Paragraph(
        "Configurez logrotate pour \u00e9viter que les fichiers de log ne saturent le disque :",
        styles['Body']
    ))
    story.append(code_block(
        '# /etc/logrotate.d/nextones-desk\n/var/log/nextones-desk.log {\n    daily\n    rotate 14\n    compress\n    delaycompress\n    missingok\n    notifempty\n    create 0640 nextones nextones\n}',
        aw
    ))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("11.3 Maintenance p\u00e9riodique", styles['SubSection']))
    maint_headers = ["T\u00e2che", "Fr\u00e9quence", "Commande / Action"]
    maint_rows = [
        ["Sauvegarde base", "Quotidienne", "backup.sh (cron)"],
        ["Rotation logs", "Quotidienne", "logrotate (automatique)"],
        ["Mise \u00e0 jour d\u00e9pendances", "Mensuelle", "pip install --upgrade -r requirements.txt"],
        ["V\u00e9rification int\u00e9grit\u00e9 base", "Hebdomadaire", "sqlite3 nextones.db \"PRAGMA integrity_check;\""],
        ["Nettoyage \u00e9v\u00e9nements anciens", "Mensuelle", "DELETE FROM events WHERE timestamp < ..."],
        ["Red\u00e9marrage serveur", "Si n\u00e9cessaire", "systemctl restart nextones-desk"],
    ]
    story.append(make_table(maint_headers, maint_rows,
                            col_widths=[38 * mm, 30 * mm, aw - 68 * mm]))

    story.append(Spacer(1, 6 * mm))

    # ═══════════════════════════════════════════════════════════════════
    # 12. SÉCURITÉ
    # ═══════════════════════════════════════════════════════════════════
    section_header(12, "S\u00e9curit\u00e9", styles, story)

    story.append(Paragraph("12.1 Authentification JWT", styles['SubSection']))
    story.append(Paragraph(
        "L\u2019authentification repose sur des <b>JSON Web Tokens (JWT)</b> g\u00e9n\u00e9r\u00e9s lors de la connexion. "
        "Chaque requ\u00eate vers un endpoint prot\u00e9g\u00e9 doit inclure le token dans l\u2019en-t\u00eate "
        "<font face='Courier' size='9'>Authorization: Bearer &lt;token&gt;</font>.",
        styles['Body']
    ))
    jwt_items = [
        "\u2022  <b>Dur\u00e9e de vie</b> : 24 heures (configurable dans api_server.py)",
        "\u2022  <b>Algorithme</b> : HS256 (HMAC-SHA256)",
        "\u2022  <b>Payload</b> : user_id, username, role, exp (expiration)",
        "\u2022  <b>Biblioth\u00e8que</b> : python-jose[cryptography]",
    ]
    for item in jwt_items:
        story.append(Paragraph(item, styles['BulletItem']))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("12.2 Hachage des mots de passe", styles['SubSection']))
    story.append(Paragraph(
        "Les mots de passe sont hach\u00e9s avec <b>bcrypt</b> avant stockage en base. "
        "Le mot de passe en clair n\u2019est jamais stock\u00e9.",
        styles['Body']
    ))
    story.append(code_block(
        '# Utilisation interne (passlib)\nfrom passlib.context import CryptContext\npwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")\nhashed = pwd_context.hash("MonMotDePasse")\nvalid = pwd_context.verify("MonMotDePasse", hashed)',
        aw
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("12.3 Configuration CORS", styles['SubSection']))
    story.append(Paragraph(
        "La configuration CORS (Cross-Origin Resource Sharing) contr\u00f4le les domaines "
        "autoris\u00e9s \u00e0 communiquer avec l\u2019API. En production, restreignez les origines :",
        styles['Body']
    ))
    story.append(code_block(
        '# Configuration actuelle (developpement)\napp.add_middleware(\n    CORSMiddleware,\n    allow_origins=["*"],  # A restreindre en production !\n    allow_credentials=True,\n    allow_methods=["*"],\n    allow_headers=["*"],\n)\n\n# Configuration recommandee en production\napp.add_middleware(\n    CORSMiddleware,\n    allow_origins=["https://nextones.finance"],\n    allow_credentials=True,\n    allow_methods=["GET", "POST", "PUT", "DELETE"],\n    allow_headers=["Authorization", "Content-Type"],\n)',
        aw
    ))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("12.4 Bonnes pratiques de s\u00e9curit\u00e9", styles['SubSection']))
    bp_items = [
        "\u2022  <b>Secret JWT</b> : utilisez une cl\u00e9 secr\u00e8te forte et unique en production (variable d\u2019environnement)",
        "\u2022  <b>HTTPS</b> : d\u00e9ployez toujours derri\u00e8re un reverse proxy TLS (nginx, Caddy)",
        "\u2022  <b>Mots de passe</b> : imposez des mots de passe complexes (8+ caract\u00e8res, majuscules, chiffres)",
        "\u2022  <b>Compte admin par d\u00e9faut</b> : changez le mot de passe du compte admin initial (rguelin / Thesium2026!)",
        "\u2022  <b>Rotation des tokens</b> : r\u00e9duisez la dur\u00e9e de vie JWT en environnement sensible",
        "\u2022  <b>Audit</b> : surveillez la table events pour d\u00e9tecter les activit\u00e9s suspectes",
        "\u2022  <b>Backup chiffr\u00e9</b> : chiffrez les sauvegardes de la base contenant les hash de mots de passe",
        "\u2022  <b>Mises \u00e0 jour</b> : maintenez les d\u00e9pendances Python \u00e0 jour (failles de s\u00e9curit\u00e9)",
    ]
    for item in bp_items:
        story.append(Paragraph(item, styles['BulletItem']))

    story.append(Spacer(1, 5 * mm))
    story.append(info_box(
        "<b>Rappel :</b> Le compte administrateur par d\u00e9faut est cr\u00e9\u00e9 au premier d\u00e9marrage "
        "avec les identifiants <font face='Courier' size='9'>rguelin / Thesium2026!</font>. "
        "Il est <b>imp\u00e9ratif</b> de changer ce mot de passe imm\u00e9diatement apr\u00e8s la premi\u00e8re connexion.",
        styles
    ))

    story.append(Spacer(1, 10 * mm))

    # ── Final note ──
    story.append(HorizontalRule(aw, TEAL_PRIMARY, 2))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Pour toute question suppl\u00e9mentaire, consultez le fichier "
        "<font face='Courier' size='9'>RUNBOOK.md</font> inclus dans le projet ou contactez "
        "l\u2019\u00e9quipe technique NEXTONES.FINANCE.",
        styles['Body']
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "<b>NEXTONES.FINANCE</b> — Plateforme de gestion de portefeuille propri\u00e9taire",
        ParagraphStyle(
            'FinalBrand', fontName='Helvetica-Bold', fontSize=10, leading=14,
            textColor=TEAL_PRIMARY, alignment=TA_CENTER,
        )
    ))
    story.append(Paragraph(
        "Version 2.0 — Mars 2026",
        ParagraphStyle(
            'FinalVersion', fontName='Helvetica', fontSize=9, leading=12,
            textColor=DEEP_TEAL, alignment=TA_CENTER,
        )
    ))

    # ─── Build ────────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        title="Guide Administrateur — Nextones Desk",
        author="Perplexity Computer",
        leftMargin=MARGIN_LEFT,
        rightMargin=MARGIN_RIGHT,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
    )

    cover_frame = Frame(
        MARGIN_LEFT, MARGIN_BOTTOM,
        PAGE_W - MARGIN_LEFT - MARGIN_RIGHT,
        PAGE_H - MARGIN_TOP - MARGIN_BOTTOM,
        id='cover'
    )
    content_frame = Frame(
        MARGIN_LEFT, MARGIN_BOTTOM + 5 * mm,
        PAGE_W - MARGIN_LEFT - MARGIN_RIGHT,
        PAGE_H - MARGIN_TOP - MARGIN_BOTTOM - 10 * mm,
        id='content'
    )

    cover_template = PageTemplate(id='Cover', frames=cover_frame, onPage=draw_cover_page)
    content_template = PageTemplate(id='Content', frames=content_frame, onPage=draw_content_page)

    doc.addPageTemplates([cover_template, content_template])

    doc.build(story)
    print(f"PDF generated: {output_path}")


if __name__ == "__main__":
    output = "/home/user/workspace/thesium-desk/Guide_Administrateur_Nextones_Desk.pdf"
    build_pdf(output)
