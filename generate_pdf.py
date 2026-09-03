#!/usr/bin/env python3
"""Generate the Thesium Desk Installation Guide PDF."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, Flowable, Preformatted
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

PAGE_W, PAGE_H = A4
MARGIN_LEFT = 25 * mm
MARGIN_RIGHT = 25 * mm
MARGIN_TOP = 30 * mm
MARGIN_BOTTOM = 25 * mm


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


class StepIndicator(Flowable):
    """A teal circle with step number inside."""
    def __init__(self, step_number, size=20):
        Flowable.__init__(self)
        self.step_number = step_number
        self.size = size

    def wrap(self, availWidth, availHeight):
        return (self.size + 4, self.size + 4)

    def draw(self):
        r = self.size / 2
        cx, cy = r + 2, r + 2
        self.canv.setFillColor(TEAL_PRIMARY)
        self.canv.circle(cx, cy, r, fill=1, stroke=0)
        self.canv.setFillColor(white)
        self.canv.setFont("Helvetica-Bold", 10)
        self.canv.drawCentredString(cx, cy - 3.5, str(self.step_number))


class CheckBox(Flowable):
    """An empty checkbox indicator."""
    def __init__(self, size=10):
        Flowable.__init__(self)
        self.size = size

    def wrap(self, availWidth, availHeight):
        return (self.size + 4, self.size + 4)

    def draw(self):
        self.canv.setStrokeColor(TEAL_PRIMARY)
        self.canv.setLineWidth(1.5)
        self.canv.rect(1, 1, self.size, self.size, fill=0, stroke=1)


# ─── Styles ──────────────────────────────────────────────────────────────────

def get_styles():
    styles = getSampleStyleSheet()

    # Cover styles
    styles.add(ParagraphStyle(
        'CoverTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=30,
        leading=36,
        textColor=TEAL_DARK,
        alignment=TA_LEFT,
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=16,
        leading=22,
        textColor=TEAL_PRIMARY,
        alignment=TA_LEFT,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        'CoverBrand',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=DEEP_TEAL,
        alignment=TA_LEFT,
    ))

    # Section headers
    styles.add(ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=26,
        textColor=TEAL_DARK,
        spaceBefore=24,
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        'SubSection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=TEAL_PRIMARY,
        spaceBefore=16,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        'SubSubSection',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=DEEP_TEAL,
        spaceBefore=12,
        spaceAfter=6,
    ))

    # Body
    styles.add(ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=TEAL_DARK,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=TEAL_DARK,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        'BulletItem',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=TEAL_DARK,
        leftIndent=20,
        bulletIndent=8,
        spaceAfter=4,
        bulletFontName='Helvetica',
        bulletFontSize=10,
    ))
    styles.add(ParagraphStyle(
        'CodeInline',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=9,
        leading=12,
        textColor=TEAL_DARK,
        backColor=PAPER_WHITE,
        leftIndent=6,
        rightIndent=6,
    ))
    styles.add(ParagraphStyle(
        'Note',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=13,
        textColor=DEEP_TEAL,
        leftIndent=12,
        spaceBefore=4,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        'StepTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=TEAL_DARK,
        spaceBefore=4,
        spaceAfter=4,
    ))

    # Footer
    styles.add(ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=HexColor("#999999"),
        alignment=TA_CENTER,
    ))

    return styles


# ─── Code Block Builder ──────────────────────────────────────────────────────

def code_block(code_text, available_width=None):
    """Create a styled code block as a table with gray background."""
    if available_width is None:
        available_width = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT - 10

    style = ParagraphStyle(
        'CodeBlock',
        fontName='Courier',
        fontSize=8.5,
        leading=12,
        textColor=TEAL_DARK,
        leftIndent=6,
        rightIndent=6,
        spaceBefore=0,
        spaceAfter=0,
    )

    # Escape XML
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
    available_width = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT

    if col_widths is None:
        n = len(headers)
        col_widths = [available_width / n] * n

    header_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=white,
        alignment=TA_LEFT,
    )
    cell_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=TEAL_DARK,
        alignment=TA_LEFT,
    )
    cell_code_style = ParagraphStyle(
        'TableCellCode',
        fontName='Courier',
        fontSize=8,
        leading=11,
        textColor=TEAL_DARK,
        alignment=TA_LEFT,
    )

    formatted_data = []
    for i, row in enumerate(data):
        formatted_row = []
        for cell in row:
            if i == 0:
                formatted_row.append(Paragraph(str(cell), header_style))
            else:
                # If cell looks like a command, use code style
                cell_str = str(cell)
                if cell_str.startswith("curl") or cell_str.startswith("python") or cell_str.startswith("pip") or cell_str.startswith("{") or cell_str.startswith("POST") or cell_str.startswith("http"):
                    formatted_row.append(Paragraph(cell_str, cell_code_style))
                else:
                    formatted_row.append(Paragraph(cell_str, cell_style))
        formatted_data.append(formatted_row)

    t = Table(formatted_data, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), TEAL_PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),

        # Alternating rows
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, PAPER_WHITE]),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, WARM_BEIGE),
        ('BOX', (0, 0), (-1, -1), 1, TEAL_PRIMARY),

        # Padding
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),

        # Alignment
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]
    t.setStyle(TableStyle(style_cmds))
    return t


def step_header(step_num, title, styles):
    """Create a step with number indicator and title."""
    indicator = StepIndicator(step_num)
    title_para = Paragraph(
        f"<b>\u00c9tape {step_num} : {title}</b>",
        styles['StepTitle']
    )

    t = Table(
        [[indicator, title_para]],
        colWidths=[30, PAGE_W - MARGIN_LEFT - MARGIN_RIGHT - 40]
    )
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('LEFTPADDING', (1, 0), (1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


# ─── Page Templates ──────────────────────────────────────────────────────────

def draw_cover_page(canvas_obj, doc):
    """Draw cover page background and decorations."""
    canvas_obj.saveState()

    # Background
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
    canvas_obj.drawString(MARGIN_LEFT, 6 * mm, "Document confidentiel — Thesium.finance — Mars 2026")

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
    canvas_obj.drawString(MARGIN_LEFT, PAGE_H - 13 * mm, "Guide d'Installation — Thesium Desk")
    canvas_obj.drawRightString(PAGE_W - MARGIN_RIGHT, PAGE_H - 13 * mm, "Thesium.finance")

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
    canvas_obj.drawString(MARGIN_LEFT, 12 * mm, "Version 1.0 — Mars 2026")
    canvas_obj.drawRightString(PAGE_W - MARGIN_RIGHT, 12 * mm, "Thesium.finance")

    canvas_obj.restoreState()


# ─── Build Document ──────────────────────────────────────────────────────────

def build_pdf(output_path):
    styles = get_styles()
    story = []
    available_width = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT

    # ═══════════════════════════════════════════════════════════════════
    # COVER PAGE
    # ═══════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 60 * mm))

    # Title block
    story.append(Paragraph("Guide d'Installation", styles['CoverTitle']))
    story.append(Spacer(1, 3 * mm))

    # Teal accent line
    story.append(HorizontalRule(available_width, TEAL_PRIMARY, 3))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("Thesium Desk", styles['CoverTitle']))
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph("Version 1.0 — Mars 2026", styles['CoverSubtitle']))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Thesium.finance", styles['CoverBrand']))

    story.append(Spacer(1, 30 * mm))

    # Description block
    story.append(Paragraph(
        "Ce document d\u00e9crit la proc\u00e9dure compl\u00e8te d\u2019installation et de configuration "
        "de l\u2019application Thesium Desk, plateforme de gestion de portefeuille propri\u00e9taire "
        "avec moteur de risque int\u00e9gr\u00e9 et agents de recherche IA.",
        styles['Body']
    ))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "Architecture : Backend FastAPI (Python) + Frontend Vanilla JS + Base SQLite",
        styles['Body']
    ))
    story.append(Spacer(1, 15 * mm))

    # Meta info
    meta_data = [
        ["Auteur", "R\u00e9dacteur technique"],
        ["Date de cr\u00e9ation", "Mars 2026"],
        ["Derni\u00e8re mise \u00e0 jour", "4 mars 2026"],
        ["Statut", "Version 1.0 — Finale"],
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

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # TABLE OF CONTENTS
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("Table des mati\u00e8res", styles['SectionTitle']))
    story.append(HorizontalRule(available_width, TEAL_PRIMARY, 1.5))
    story.append(Spacer(1, 8 * mm))

    toc_items = [
        ("1.", "Introduction"),
        ("2.", "Pr\u00e9requis Syst\u00e8me"),
        ("3.", "Structure du Projet"),
        ("4.", "Installation Pas \u00e0 Pas"),
        ("5.", "Configuration"),
        ("6.", "D\u00e9ploiement en Production"),
        ("7.", "Migration vers PostgreSQL (optionnel)"),
        ("8.", "V\u00e9rification Post-Installation"),
        ("9.", "D\u00e9pannage"),
    ]

    toc_style = ParagraphStyle(
        'TOCItem',
        fontName='Helvetica',
        fontSize=12,
        leading=22,
        textColor=TEAL_DARK,
        leftIndent=10,
    )
    toc_num_style = ParagraphStyle(
        'TOCNum',
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=22,
        textColor=TEAL_PRIMARY,
    )

    for num, title in toc_items:
        t = Table(
            [[Paragraph(num, toc_num_style), Paragraph(title, toc_style)]],
            colWidths=[12 * mm, available_width - 12 * mm]
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
    story.append(Paragraph("1. Introduction", styles['SectionTitle']))
    story.append(HorizontalRule(available_width, TEAL_PRIMARY, 1.5))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("1.1 Pr\u00e9sentation du projet", styles['SubSection']))
    story.append(Paragraph(
        "<b>Thesium Desk</b> est une plateforme de gestion de portefeuille propri\u00e9taire con\u00e7ue "
        "pour les \u00e9quipes d\u2019investissement. Elle int\u00e8gre un <b>moteur de risque</b> "
        "(Value at Risk param\u00e9trique), des <b>agents de recherche IA</b> sp\u00e9cialis\u00e9s, "
        "et un <b>cycle de d\u00e9cision automatis\u00e9</b> (paper broker) permettant de simuler "
        "des op\u00e9rations de march\u00e9.",
        styles['Body']
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "L\u2019application est construite autour d\u2019une architecture l\u00e9g\u00e8re et modulaire, "
        "id\u00e9ale pour un MVP :",
        styles['Body']
    ))
    story.append(Spacer(1, 2 * mm))

    story.append(Paragraph("1.2 Architecture technique", styles['SubSection']))

    arch_items = [
        "\u2022  <b>Backend</b> : FastAPI (Python) — API RESTful performante et asynchrone",
        "\u2022  <b>Frontend</b> : Vanilla JavaScript — SPA l\u00e9g\u00e8re sans d\u00e9pendance framework",
        "\u2022  <b>Base de donn\u00e9es</b> : SQLite — z\u00e9ro configuration, 12 tables relationnelles",
        "\u2022  <b>Donn\u00e9es de march\u00e9</b> : Yahoo Finance (ingestion automatique)",
        "\u2022  <b>Agents IA</b> : 4 agents sp\u00e9cialis\u00e9s (Macro, Fondamental, Technique, Sentiment)",
    ]
    for item in arch_items:
        story.append(Paragraph(item, styles['BulletItem']))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("1.3 Port\u00e9e de ce guide", styles['SubSection']))
    story.append(Paragraph(
        "Ce guide couvre l\u2019installation locale compl\u00e8te, la configuration initiale, "
        "et les options de d\u00e9ploiement en production. Il est destin\u00e9 aux d\u00e9veloppeurs "
        "ayant une connaissance de base de Python et de la ligne de commande.",
        styles['Body']
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # 2. PRÉREQUIS SYSTÈME
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("2. Pr\u00e9requis Syst\u00e8me", styles['SectionTitle']))
    story.append(HorizontalRule(available_width, TEAL_PRIMARY, 1.5))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        "Avant de commencer l\u2019installation, v\u00e9rifiez que votre environnement satisfait "
        "les conditions suivantes :",
        styles['Body']
    ))
    story.append(Spacer(1, 3 * mm))

    prereq_headers = ["Composant", "Version minimum", "Notes"]
    prereq_rows = [
        ["Python", "3.10+", "Recommand\u00e9 3.11+"],
        ["pip", "21+", "Gestionnaire de paquets Python"],
        ["Navigateur", "Chrome, Firefox, Edge", "Derni\u00e8re version"],
        ["Syst\u00e8me", "Linux, macOS, Windows", "WSL recommand\u00e9 sous Windows"],
        ["RAM", "2 Go minimum", "4 Go recommand\u00e9"],
        ["Disque", "500 Mo", "Code, base et donn\u00e9es"],
        ["R\u00e9seau", "Acc\u00e8s internet", "Pour Yahoo Finance (optionnel)"],
    ]
    story.append(make_table(prereq_headers, prereq_rows,
                            col_widths=[40 * mm, 40 * mm, available_width - 80 * mm]))

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(
        "<i>Note : Pour le MVP, aucune cl\u00e9 API externe n\u2019est requise. L\u2019application "
        "fonctionne enti\u00e8rement avec des donn\u00e9es synth\u00e9tiques pr\u00e9-g\u00e9n\u00e9r\u00e9es.</i>",
        styles['Note']
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # 3. STRUCTURE DU PROJET
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("3. Structure du Projet", styles['SectionTitle']))
    story.append(HorizontalRule(available_width, TEAL_PRIMARY, 1.5))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        "Le projet est organis\u00e9 dans un r\u00e9pertoire unique contenant l\u2019ensemble "
        "des fichiers n\u00e9cessaires au fonctionnement de l\u2019application :",
        styles['Body']
    ))
    story.append(Spacer(1, 3 * mm))

    tree_text = """thesium-desk/
|-- api_server.py          # Serveur FastAPI principal (port 8000)
|-- models.py              # Schema SQLite (12 tables)
|-- agents.py              # 4 agents IA de recherche
|-- risk_engine.py         # Moteur de risque (VaR parametrique)
|-- execution_engine.py    # Paper broker + cycle de decision
|-- memo_generator.py      # Generateur de memos IC
|-- data_ingestion.py      # Ingestion Yahoo Finance
|-- seed_data.py           # Donnees de demonstration
|-- requirements.txt       # Dependances Python
|-- thesium.db             # Base SQLite (creee au demarrage)
|-- index.html             # Frontend SPA
|-- base.css               # Styles de base
|-- style.css              # Styles applicatifs
|-- app.js                 # Logique frontend (vanilla JS)
`-- RUNBOOK.md             # Documentation operationnelle"""

    story.append(code_block(tree_text, available_width))

    story.append(Spacer(1, 5 * mm))

    # Description of key files
    story.append(Paragraph("Fichiers cl\u00e9s :", styles['SubSection']))

    file_desc = [
        ("\u2022  <b>api_server.py</b>", "Point d\u2019entr\u00e9e principal. D\u00e9marre le serveur FastAPI sur le port 8000 et expose tous les endpoints REST."),
        ("\u2022  <b>models.py</b>", "D\u00e9finit le sch\u00e9ma de la base de donn\u00e9es SQLite avec 12 tables relationnelles (instruments, positions, ordres, th\u00e8ses, etc.)."),
        ("\u2022  <b>agents.py</b>", "Impl\u00e9mente les 4 agents de recherche IA : Macro, Fondamental, Technique et Sentiment."),
        ("\u2022  <b>risk_engine.py</b>", "Moteur de calcul de risque int\u00e9gr\u00e9 (VaR param\u00e9trique, corr\u00e9lations, limites)."),
        ("\u2022  <b>seed_data.py</b>", "G\u00e9n\u00e8re les donn\u00e9es de d\u00e9monstration (instruments, prix, positions, th\u00e8ses)."),
    ]
    for title, desc in file_desc:
        story.append(Paragraph(f"{title} \u2014 {desc}", styles['Bullet']))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # 4. INSTALLATION PAS À PAS
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("4. Installation Pas \u00e0 Pas", styles['SectionTitle']))
    story.append(HorizontalRule(available_width, TEAL_PRIMARY, 1.5))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        "Suivez ces \u00e9tapes dans l\u2019ordre pour installer Thesium Desk sur votre machine locale.",
        styles['Body']
    ))
    story.append(Spacer(1, 4 * mm))

    # ── Étape 1 ──
    story.append(step_header(1, "Cloner ou copier le projet", styles))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Placez tous les fichiers du projet dans un r\u00e9pertoire d\u00e9di\u00e9. "
        "Par exemple :",
        styles['Body']
    ))
    story.append(code_block("mkdir ~/thesium-desk\ncd ~/thesium-desk\n# Copier tous les fichiers du projet ici", available_width))
    story.append(Spacer(1, 5 * mm))

    # ── Étape 2 ──
    story.append(step_header(2, "Cr\u00e9er un environnement virtuel (recommand\u00e9)", styles))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "L\u2019utilisation d\u2019un environnement virtuel Python est fortement recommand\u00e9e "
        "pour isoler les d\u00e9pendances du projet :",
        styles['Body']
    ))
    story.append(code_block(
        "cd thesium-desk\npython -m venv venv\nsource venv/bin/activate   # Linux/macOS\n# ou: venv\\Scripts\\activate  # Windows",
        available_width
    ))
    story.append(Spacer(1, 5 * mm))

    # ── Étape 3 ──
    story.append(step_header(3, "Installer les d\u00e9pendances", styles))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Installez toutes les d\u00e9pendances Python n\u00e9cessaires via pip :",
        styles['Body']
    ))
    story.append(code_block("pip install -r requirements.txt", available_width))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "<i>D\u00e9pendances principales : fastapi, uvicorn (et leurs sous-d\u00e9pendances automatiques).</i>",
        styles['Note']
    ))
    story.append(Spacer(1, 5 * mm))

    # ── Étape 4 ──
    story.append(step_header(4, "Initialiser la base de donn\u00e9es et les donn\u00e9es de d\u00e9mo", styles))
    story.append(Spacer(1, 2 * mm))
    story.append(code_block("python seed_data.py", available_width))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Cette commande cr\u00e9e le fichier <font face='Courier' size='9'>thesium.db</font> et le remplit avec :",
        styles['Body']
    ))
    seed_items = [
        "\u2022  <b>14 instruments</b> : AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META, JPM, BAC, XOM, JNJ, UNH, SPY, QQQ",
        "\u2022  <b>30 jours d\u2019historique</b> de prix par instrument",
        "\u2022  <b>Portefeuille initial</b> : ~$1.16M AUM, $587K cash, 6 positions",
        "\u2022  <b>Th\u00e8ses actives</b> de chaque agent de recherche",
        "\u2022  <b>3-4 m\u00e9mos IC</b> historiques",
        "\u2022  <b>Journal d\u2019\u00e9v\u00e9nements</b> complet",
    ]
    for item in seed_items:
        story.append(Paragraph(item, styles['BulletItem']))
    story.append(Spacer(1, 5 * mm))

    # ── Étape 5 ──
    story.append(step_header(5, "D\u00e9marrer le serveur", styles))
    story.append(Spacer(1, 2 * mm))
    story.append(code_block("python api_server.py", available_width))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Le serveur d\u00e9marre sur <font face='Courier' size='9'>http://0.0.0.0:8000</font>",
        styles['Body']
    ))
    story.append(Paragraph(
        "<i>Note : Au d\u00e9marrage, le serveur initialise automatiquement la base de donn\u00e9es "
        "et ex\u00e9cute le seed si n\u00e9cessaire.</i>",
        styles['Note']
    ))
    story.append(Spacer(1, 5 * mm))

    # ── Étape 6 ──
    story.append(step_header(6, "V\u00e9rifier le fonctionnement", styles))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Testez l\u2019\u00e9tat de sant\u00e9 de l\u2019API :", styles['Body']))
    story.append(code_block("curl http://localhost:8000/api/health", available_width))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("R\u00e9ponse attendue :", styles['Body']))
    story.append(code_block('{"status": "healthy", "timestamp": "...", "service": "Thesium.finance API"}', available_width))
    story.append(Spacer(1, 5 * mm))

    # ── Étape 7 ──
    story.append(step_header(7, "Acc\u00e9der au frontend", styles))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Deux options pour acc\u00e9der \u00e0 l\u2019interface utilisateur :",
        styles['Body']
    ))
    story.append(Paragraph(
        "\u2022  <b>En local</b> : Ouvrir directement <font face='Courier' size='9'>index.html</font> dans un navigateur",
        styles['Bullet']
    ))
    story.append(Paragraph(
        "\u2022  <b>\u00c0 distance</b> : Configurer le placeholder <font face='Courier' size='9'>API_BASE</font> "
        "dans <font face='Courier' size='9'>app.js</font> pour pointer vers l\u2019URL du backend",
        styles['Bullet']
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # 5. CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("5. Configuration", styles['SectionTitle']))
    story.append(HorizontalRule(available_width, TEAL_PRIMARY, 1.5))
    story.append(Spacer(1, 4 * mm))

    # 5.1
    story.append(Paragraph("5.1 Variables d\u2019environnement (MVP)", styles['SubSection']))
    story.append(Paragraph(
        "Dans sa version MVP, Thesium Desk ne n\u00e9cessite <b>aucune cl\u00e9 API</b>. "
        "L\u2019application utilise des donn\u00e9es synth\u00e9tiques g\u00e9n\u00e9r\u00e9es par "
        "<font face='Courier' size='9'>seed_data.py</font>. SQLite fonctionne en mode "
        "z\u00e9ro-configuration.",
        styles['Body']
    ))
    story.append(Spacer(1, 4 * mm))

    # 5.2
    story.append(Paragraph("5.2 Pour la production (futures int\u00e9grations)", styles['SubSection']))
    story.append(Paragraph(
        "Les variables suivantes seront n\u00e9cessaires pour les int\u00e9grations futures :",
        styles['Body']
    ))
    story.append(Spacer(1, 2 * mm))

    env_headers = ["Variable", "Description", "Exemple"]
    env_rows = [
        ["POLYGON_API_KEY", "Donn\u00e9es temps r\u00e9el polygon.io", "pk_xxxxx"],
        ["ALPHA_VANTAGE_KEY", "Source alternative de donn\u00e9es", "xxxxxx"],
        ["IBKR_ACCOUNT", "Compte Interactive Brokers", "DU12345"],
        ["IBKR_HOST", "H\u00f4te TWS", "127.0.0.1"],
        ["IBKR_PORT", "Port TWS", "7497"],
        ["DATABASE_URL", "PostgreSQL (migration)", "postgresql://..."],
        ["LIVE_TRADING", "Activer le trading r\u00e9el", "true/false"],
    ]
    story.append(make_table(env_headers, env_rows,
                            col_widths=[45 * mm, 55 * mm, available_width - 100 * mm]))
    story.append(Spacer(1, 5 * mm))

    # 5.3
    story.append(Paragraph("5.3 Configuration du port", styles['SubSection']))
    story.append(Paragraph(
        "Le port par d\u00e9faut est <b>8000</b>. Pour le modifier, changez la derni\u00e8re ligne du "
        "fichier <font face='Courier' size='9'>api_server.py</font> :",
        styles['Body']
    ))
    story.append(code_block(
        '# Dernière ligne de api_server.py\nuvicorn.run(app, host="0.0.0.0", port=8000)  # Modifier le port ici',
        available_width
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # 6. DÉPLOIEMENT EN PRODUCTION
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("6. D\u00e9ploiement en Production", styles['SectionTitle']))
    story.append(HorizontalRule(available_width, TEAL_PRIMARY, 1.5))
    story.append(Spacer(1, 4 * mm))

    # 6.1
    story.append(Paragraph("6.1 Avec Uvicorn (simple)", styles['SubSection']))
    story.append(code_block(
        'uvicorn api_server:app --host 0.0.0.0 --port 8000 --workers 1',
        available_width
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "<i>Note : SQLite ne supporte qu\u2019un seul worker. Pour du multi-worker, "
        "migrez vers PostgreSQL (voir section 7).</i>",
        styles['Note']
    ))
    story.append(Spacer(1, 5 * mm))

    # 6.2
    story.append(Paragraph("6.2 Avec systemd (Linux)", styles['SubSection']))
    story.append(Paragraph(
        "Cr\u00e9ez un fichier de service systemd pour g\u00e9rer le d\u00e9marrage automatique :",
        styles['Body']
    ))
    story.append(Spacer(1, 2 * mm))

    systemd_code = """[Unit]
Description=Thesium Desk API
After=network.target

[Service]
User=thesium
WorkingDirectory=/opt/thesium-desk
ExecStart=/opt/thesium-desk/venv/bin/uvicorn api_server:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target"""

    story.append(code_block(systemd_code, available_width))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Commandes d\u2019activation :",
        styles['Body']
    ))
    story.append(code_block(
        "sudo cp thesium-desk.service /etc/systemd/system/\nsudo systemctl daemon-reload\nsudo systemctl enable thesium-desk\nsudo systemctl start thesium-desk",
        available_width
    ))
    story.append(Spacer(1, 5 * mm))

    # 6.3
    story.append(Paragraph("6.3 Avec Docker (optionnel)", styles['SubSection']))
    story.append(Paragraph(
        "Exemple de Dockerfile pour conteneuriser l\u2019application :",
        styles['Body']
    ))
    story.append(Spacer(1, 2 * mm))

    docker_code = """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python seed_data.py
EXPOSE 8000
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]"""

    story.append(code_block(docker_code, available_width))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("Construction et lancement :", styles['Body']))
    story.append(code_block(
        "docker build -t thesium-desk .\ndocker run -d -p 8000:8000 --name thesium thesium-desk",
        available_width
    ))
    story.append(Spacer(1, 5 * mm))

    # 6.4
    story.append(Paragraph("6.4 Servir le frontend", styles['SubSection']))
    story.append(Paragraph(
        "Plusieurs options pour servir les fichiers statiques du frontend :",
        styles['Body']
    ))
    frontend_options = [
        "\u2022  <b>Option A</b> : Utiliser un serveur web statique (nginx, Caddy) pointant vers les fichiers HTML/CSS/JS",
        "\u2022  <b>Option B</b> : Modifier <font face='Courier' size='9'>API_BASE</font> dans <font face='Courier' size='9'>app.js</font> pour pointer vers l\u2019URL du backend",
    ]
    for opt in frontend_options:
        story.append(Paragraph(opt, styles['Bullet']))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "<i>Important : Le placeholder <font face='Courier' size='9'>__PORT_8000__</font> doit \u00eatre "
        "remplac\u00e9 par l\u2019URL r\u00e9elle du backend "
        "(ex: https://api.thesium.finance).</i>",
        styles['Note']
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # 7. MIGRATION POSTGRESQL
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("7. Migration vers PostgreSQL (optionnel)", styles['SectionTitle']))
    story.append(HorizontalRule(available_width, TEAL_PRIMARY, 1.5))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        "Le sch\u00e9ma SQLite utilis\u00e9 par Thesium Desk est compatible avec PostgreSQL "
        "moyennant quelques ajustements mineurs. Cette migration est recommand\u00e9e pour "
        "un d\u00e9ploiement en production multi-utilisateur.",
        styles['Body']
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Proc\u00e9dure de migration :", styles['SubSection']))
    migration_steps = [
        "\u2022  Installer PostgreSQL et cr\u00e9er une base de donn\u00e9es d\u00e9di\u00e9e",
        "\u2022  Installer le driver Python : <font face='Courier' size='9'>pip install psycopg2-binary</font> ou <font face='Courier' size='9'>pip install asyncpg</font>",
        "\u2022  Modifier <font face='Courier' size='9'>DB_PATH</font> dans <font face='Courier' size='9'>models.py</font> pour utiliser la cha\u00eene de connexion PostgreSQL",
        "\u2022  Recr\u00e9er les tables (le sch\u00e9ma est compatible avec des ajustements mineurs sur les types)",
        "\u2022  Migrer les donn\u00e9es existantes ou relancer <font face='Courier' size='9'>seed_data.py</font>",
        "\u2022  Configurer la variable <font face='Courier' size='9'>DATABASE_URL</font> (voir section 5.2)",
    ]
    for step in migration_steps:
        story.append(Paragraph(step, styles['Bullet']))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "<i>Avantages de PostgreSQL : support multi-worker, transactions concurrentes, "
        "meilleure performance en \u00e9criture, sauvegardes incr\u00e9mentales.</i>",
        styles['Note']
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # 8. VÉRIFICATION POST-INSTALLATION
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("8. V\u00e9rification Post-Installation", styles['SectionTitle']))
    story.append(HorizontalRule(available_width, TEAL_PRIMARY, 1.5))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        "Apr\u00e8s l\u2019installation, utilisez la checklist suivante pour v\u00e9rifier que "
        "l\u2019ensemble des composants fonctionne correctement :",
        styles['Body']
    ))
    story.append(Spacer(1, 3 * mm))

    check_headers = ["Test", "Commande", "R\u00e9sultat attendu"]
    check_rows = [
        ["Sant\u00e9 API", "curl /api/health", '{"status": "healthy"}'],
        ["Dashboard", "curl /api/dashboard", "JSON avec portfolio, positions"],
        ["Th\u00e8ses", "curl /api/theses", "Liste de th\u00e8ses actives"],
        ["Instruments", "curl /api/instruments", "14 instruments"],
        ["Cycle d\u00e9cision", "curl -X POST /api/orders/execute-cycle", '{"success": true}'],
        ["Frontend", "Ouvrir index.html", "4 onglets, donn\u00e9es affich\u00e9es"],
    ]
    story.append(make_table(check_headers, check_rows,
                            col_widths=[35 * mm, 55 * mm, available_width - 90 * mm]))

    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("Proc\u00e9dure de v\u00e9rification compl\u00e8te :", styles['SubSection']))
    story.append(Spacer(1, 2 * mm))

    verify_code = """# 1. Vérifier la santé de l'API
curl http://localhost:8000/api/health

# 2. Vérifier le dashboard
curl http://localhost:8000/api/dashboard | python -m json.tool

# 3. Vérifier les instruments
curl http://localhost:8000/api/instruments | python -m json.tool

# 4. Vérifier les thèses actives
curl http://localhost:8000/api/theses | python -m json.tool

# 5. Exécuter un cycle de décision
curl -X POST http://localhost:8000/api/orders/execute-cycle

# 6. Vérifier les mémos IC
curl http://localhost:8000/api/memos | python -m json.tool"""

    story.append(code_block(verify_code, available_width))

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(
        "<i>Si tous les tests retournent les r\u00e9sultats attendus, l\u2019installation est "
        "termin\u00e9e avec succ\u00e8s.</i>",
        styles['Note']
    ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════
    # 9. DÉPANNAGE
    # ═══════════════════════════════════════════════════════════════════
    story.append(Paragraph("9. D\u00e9pannage", styles['SectionTitle']))
    story.append(HorizontalRule(available_width, TEAL_PRIMARY, 1.5))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        "Cette section r\u00e9pertorie les probl\u00e8mes les plus fr\u00e9quemment rencontr\u00e9s "
        "et leurs solutions :",
        styles['Body']
    ))
    story.append(Spacer(1, 3 * mm))

    trouble_headers = ["Probl\u00e8me", "Cause possible", "Solution"]
    trouble_rows = [
        ["ModuleNotFoundError: fastapi", "D\u00e9pendances non install\u00e9es", "pip install -r requirements.txt"],
        ["Port 8000 d\u00e9j\u00e0 utilis\u00e9", "Autre service sur ce port", "Changer le port ou arr\u00eater le service"],
        ["Base de donn\u00e9es vide", "seed_data.py non ex\u00e9cut\u00e9", "python seed_data.py"],
        ["Erreur CORS frontend", "Frontend sur un domaine diff\u00e9rent", 'CORS configur\u00e9 allow_origins=["*"]'],
        ["Donn\u00e9es de prix obsolètes", "Pas d\u2019ingestion r\u00e9cente", "POST /api/run-ingestion"],
        ["thesium.db verrouill\u00e9", "Acc\u00e8s concurrent", "Red\u00e9marrer le serveur"],
    ]
    story.append(make_table(trouble_headers, trouble_rows,
                            col_widths=[45 * mm, 45 * mm, available_width - 90 * mm]))

    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Commandes utiles de diagnostic :", styles['SubSection']))
    story.append(Spacer(1, 2 * mm))

    diag_code = """# Vérifier la version de Python
python --version

# Vérifier que les dépendances sont installées
pip list | grep -E "fastapi|uvicorn"

# Vérifier que le port 8000 est libre
lsof -i :8000          # Linux/macOS
netstat -an | find "8000"  # Windows

# Vérifier la taille de la base de données
ls -lh thesium.db

# Relancer le seed (réinitialise toutes les données)
rm thesium.db && python seed_data.py

# Lancer le serveur en mode debug
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload"""

    story.append(code_block(diag_code, available_width))

    story.append(Spacer(1, 10 * mm))

    # ── Final note ──
    story.append(HorizontalRule(available_width, TEAL_PRIMARY, 2))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Pour toute question suppl\u00e9mentaire, consultez le fichier "
        "<font face='Courier' size='9'>RUNBOOK.md</font> inclus dans le projet ou contactez "
        "l\u2019\u00e9quipe technique Thesium.finance.",
        styles['Body']
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "<b>Thesium.finance</b> — Plateforme de gestion de portefeuille propri\u00e9taire",
        ParagraphStyle(
            'FinalBrand',
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=14,
            textColor=TEAL_PRIMARY,
            alignment=TA_CENTER,
        )
    ))
    story.append(Paragraph(
        "Version 1.0 — Mars 2026",
        ParagraphStyle(
            'FinalVersion',
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=DEEP_TEAL,
            alignment=TA_CENTER,
        )
    ))

    # ─── Build ────────────────────────────────────────────────────────────────

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        title="Guide d'Installation — Thesium Desk",
        author="Perplexity Computer",
        leftMargin=MARGIN_LEFT,
        rightMargin=MARGIN_RIGHT,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
    )

    # We use different page templates for cover vs content
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

    # Insert template switch after cover
    from reportlab.platypus import NextPageTemplate
    story.insert(story.index([e for e in story if isinstance(e, PageBreak)][0]), NextPageTemplate('Content'))

    # Build
    doc.build(story)
    print(f"PDF generated: {output_path}")


if __name__ == "__main__":
    output = "/home/user/workspace/thesium-desk/Guide_Installation_Thesium_Desk.pdf"
    build_pdf(output)
