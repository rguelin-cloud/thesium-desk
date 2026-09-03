#!/usr/bin/env python3
"""Generate the Nextones Desk Installation Guide PDF (v2 — March 2026)."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, Flowable,
)
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate, Frame
import os, datetime

# ─── Brand Colors ────────────────────────────────────────────────────────────
DARK_NAVY = HexColor("#091717")
TEAL_DARK = HexColor("#13343B")
DEEP_TEAL = HexColor("#115058")
MEDIUM_TEAL = HexColor("#2E565D")
TEAL_PRIMARY = HexColor("#20808D")
LIGHT_TEAL = HexColor("#D6F5FA")
OFF_WHITE = HexColor("#FCFAF6")
PAPER_WHITE = HexColor("#F3F3EE")
WARM_BEIGE = HexColor("#E5E3D4")

PAGE_W, PAGE_H = A4
ML = 25 * mm
MR = 25 * mm
MT = 32 * mm
MB = 25 * mm
CONTENT_W = PAGE_W - ML - MR


# ═════════════════════════════════════════════════════════════════════════════
# Custom Flowables
# ═════════════════════════════════════════════════════════════════════════════

class HorizontalRule(Flowable):
    def __init__(self, color=TEAL_PRIMARY, thickness=1):
        Flowable.__init__(self)
        self.color = color
        self.thickness = thickness

    def wrap(self, aw, ah):
        return (aw, self.thickness + 4)

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 2, self.width, 2)


class SectionNumber(Flowable):
    """A teal circle with section number."""
    def __init__(self, number, size=22):
        Flowable.__init__(self)
        self.number = number
        self.size = size

    def wrap(self, aw, ah):
        return (self.size + 4, self.size + 4)

    def draw(self):
        r = self.size / 2
        cx, cy = r + 2, r + 2
        self.canv.setFillColor(TEAL_PRIMARY)
        self.canv.circle(cx, cy, r, fill=1, stroke=0)
        self.canv.setFillColor(white)
        self.canv.setFont("Helvetica-Bold", 11)
        self.canv.drawCentredString(cx, cy - 3.5, str(self.number))


class WarningBox(Flowable):
    """Colored warning/info box."""
    def __init__(self, text, bg_color=LIGHT_TEAL, border_color=TEAL_PRIMARY, width=None):
        Flowable.__init__(self)
        self.text = text
        self.bg_color = bg_color
        self.border_color = border_color
        self._width = width or CONTENT_W

    def wrap(self, aw, ah):
        self._width = aw
        return (aw, 40)

    def draw(self):
        self.canv.setFillColor(self.bg_color)
        self.canv.setStrokeColor(self.border_color)
        self.canv.setLineWidth(1.5)
        self.canv.roundRect(0, 0, self._width, 36, 4, fill=1, stroke=1)
        self.canv.setFillColor(DARK_NAVY)
        self.canv.setFont("Helvetica", 9)
        self.canv.drawString(10, 14, self.text)


# ═════════════════════════════════════════════════════════════════════════════
# Styles
# ═════════════════════════════════════════════════════════════════════════════

def get_styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle('CoverTitle', parent=s['Title'],
        fontName='Helvetica-Bold', fontSize=30, leading=36,
        textColor=TEAL_DARK, alignment=TA_LEFT, spaceAfter=10))
    s.add(ParagraphStyle('CoverSubtitle', parent=s['Normal'],
        fontName='Helvetica', fontSize=16, leading=22,
        textColor=TEAL_PRIMARY, alignment=TA_LEFT, spaceAfter=6))
    s.add(ParagraphStyle('CoverBrand', parent=s['Normal'],
        fontName='Helvetica-Bold', fontSize=14, leading=18,
        textColor=DEEP_TEAL, alignment=TA_LEFT))
    s.add(ParagraphStyle('CoverMeta', parent=s['Normal'],
        fontName='Helvetica', fontSize=10, leading=14,
        textColor=MEDIUM_TEAL, alignment=TA_LEFT, spaceAfter=3))
    s.add(ParagraphStyle('SectionTitle', parent=s['Heading1'],
        fontName='Helvetica-Bold', fontSize=20, leading=26,
        textColor=TEAL_DARK, spaceBefore=24, spaceAfter=12))
    s.add(ParagraphStyle('SubSection', parent=s['Heading2'],
        fontName='Helvetica-Bold', fontSize=14, leading=18,
        textColor=TEAL_PRIMARY, spaceBefore=16, spaceAfter=8))
    s.add(ParagraphStyle('SubSub', parent=s['Heading3'],
        fontName='Helvetica-Bold', fontSize=12, leading=15,
        textColor=DEEP_TEAL, spaceBefore=12, spaceAfter=6))
    s.add(ParagraphStyle('Body', parent=s['Normal'],
        fontName='Helvetica', fontSize=10, leading=14,
        textColor=DARK_NAVY, alignment=TA_JUSTIFY, spaceAfter=6))
    s.add(ParagraphStyle('BodyBold', parent=s['Normal'],
        fontName='Helvetica-Bold', fontSize=10, leading=14,
        textColor=DARK_NAVY, spaceAfter=6))
    s.add(ParagraphStyle('BulletItem', parent=s['Normal'],
        fontName='Helvetica', fontSize=10, leading=14,
        textColor=DARK_NAVY, leftIndent=20, bulletIndent=8,
        spaceAfter=3, bulletFontName='Helvetica', bulletFontSize=10))
    s.add(ParagraphStyle('BulletBold', parent=s['Normal'],
        fontName='Helvetica-Bold', fontSize=10, leading=14,
        textColor=DARK_NAVY, leftIndent=20, bulletIndent=8,
        spaceAfter=3))
    s.add(ParagraphStyle('Note', parent=s['Normal'],
        fontName='Helvetica-Oblique', fontSize=9, leading=13,
        textColor=DEEP_TEAL, leftIndent=12, spaceBefore=4, spaceAfter=8))
    s.add(ParagraphStyle('StepTitle', parent=s['Normal'],
        fontName='Helvetica-Bold', fontSize=12, leading=16,
        textColor=TEAL_DARK, spaceBefore=4, spaceAfter=4))
    s.add(ParagraphStyle('TOCItem', parent=s['Normal'],
        fontName='Helvetica', fontSize=11, leading=18,
        textColor=DARK_NAVY, leftIndent=10, spaceAfter=2))
    s.add(ParagraphStyle('TOCHead', parent=s['Normal'],
        fontName='Helvetica-Bold', fontSize=11, leading=18,
        textColor=TEAL_DARK, leftIndent=10, spaceAfter=2))
    s.add(ParagraphStyle('Footer', parent=s['Normal'],
        fontName='Helvetica', fontSize=8, leading=10,
        textColor=HexColor("#999999"), alignment=TA_CENTER))
    return s


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def esc(text):
    """Escape XML entities."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def code_block(code_text):
    """Create a styled code block with gray background."""
    style = ParagraphStyle('CB', fontName='Courier', fontSize=8.5,
        leading=12, textColor=DARK_NAVY, leftIndent=6, rightIndent=6)
    escaped = esc(code_text)
    formatted = "<br/>".join(escaped.split("\n"))
    para = Paragraph(formatted, style)
    t = Table([[para]], colWidths=[CONTENT_W])
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
    header_style = ParagraphStyle('TH', fontName='Helvetica-Bold',
        fontSize=9, leading=12, textColor=white, alignment=TA_CENTER)
    cell_style = ParagraphStyle('TD', fontName='Helvetica',
        fontSize=9, leading=12, textColor=DARK_NAVY)

    data = [[Paragraph(h, header_style) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), cell_style) for c in row])

    if col_widths is None:
        n = len(headers)
        col_widths = [CONTENT_W / n] * n

    t = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), TEAL_PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, WARM_BEIGE),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    for i in range(1, len(data)):
        bg = PAPER_WHITE if i % 2 == 0 else OFF_WHITE
        style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))
    t.setStyle(TableStyle(style_cmds))
    return t


def bullet(text, styles):
    return Paragraph(f"<bullet>&bull;</bullet> {text}", styles['BulletItem'])


def bullet_bold(label, text, styles):
    return Paragraph(f"<bullet>&bull;</bullet> <b>{esc(label)}</b> {text}", styles['BulletItem'])


def info_box(text):
    """Light-teal info box."""
    style = ParagraphStyle('InfoBox', fontName='Helvetica', fontSize=9,
        leading=13, textColor=DEEP_TEAL, leftIndent=8, rightIndent=8)
    para = Paragraph(text, style)
    t = Table([[para]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_TEAL),
        ('BOX', (0, 0), (-1, -1), 1, TEAL_PRIMARY),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    return t


def warning_box(text):
    """Amber warning box."""
    style = ParagraphStyle('WarnBox', fontName='Helvetica-Bold', fontSize=9,
        leading=13, textColor=HexColor("#7A4500"), leftIndent=8, rightIndent=8)
    para = Paragraph(text, style)
    t = Table([[para]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor("#FFF3CD")),
        ('BOX', (0, 0), (-1, -1), 1, HexColor("#D4A017")),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    return t


# ═════════════════════════════════════════════════════════════════════════════
# Document Template with Header/Footer
# ═════════════════════════════════════════════════════════════════════════════

class InstallGuideTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        BaseDocTemplate.__init__(self, filename, **kwargs)
        frame = Frame(ML, MB, CONTENT_W, PAGE_H - MT - MB, id='main')
        self.addPageTemplates([
            PageTemplate(id='cover', frames=[frame], onPage=self._cover_page),
            PageTemplate(id='content', frames=[frame], onPage=self._content_page),
        ])

    def _cover_page(self, canvas, doc):
        canvas.saveState()
        # Dark navy header bar
        canvas.setFillColor(DARK_NAVY)
        canvas.rect(0, PAGE_H - 8 * mm, PAGE_W, 8 * mm, fill=1, stroke=0)
        # Teal accent line
        canvas.setStrokeColor(TEAL_PRIMARY)
        canvas.setLineWidth(2)
        canvas.line(0, PAGE_H - 8 * mm, PAGE_W, PAGE_H - 8 * mm)
        # Brand in header
        canvas.setFillColor(white)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(ML, PAGE_H - 5.5 * mm, "NEXTONES.FINANCE")
        canvas.restoreState()

    def _content_page(self, canvas, doc):
        canvas.saveState()
        # Header bar
        canvas.setFillColor(DARK_NAVY)
        canvas.rect(0, PAGE_H - 8 * mm, PAGE_W, 8 * mm, fill=1, stroke=0)
        canvas.setStrokeColor(TEAL_PRIMARY)
        canvas.setLineWidth(2)
        canvas.line(0, PAGE_H - 8 * mm, PAGE_W, PAGE_H - 8 * mm)
        canvas.setFillColor(white)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(ML, PAGE_H - 5.5 * mm, "NEXTONES.FINANCE")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(PAGE_W - MR, PAGE_H - 5.5 * mm,
            "Guide d'Installation — Nextones Desk")
        # Footer
        canvas.setStrokeColor(WARM_BEIGE)
        canvas.setLineWidth(0.5)
        canvas.line(ML, MB - 8 * mm, PAGE_W - MR, MB - 8 * mm)
        canvas.setFillColor(HexColor("#999999"))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(ML, MB - 14 * mm,
            "NEXTONES.FINANCE — Guide d'Installation")
        canvas.drawRightString(PAGE_W - MR, MB - 14 * mm,
            f"Page {doc.page}")
        canvas.restoreState()


# ═════════════════════════════════════════════════════════════════════════════
# Content Builder
# ═════════════════════════════════════════════════════════════════════════════

def build_story(styles):
    S = styles
    story = []

    # ── COVER PAGE ────────────────────────────────────────────────────────
    story.append(Spacer(1, 60))
    story.append(Paragraph("Guide d'Installation", S['CoverTitle']))
    story.append(Paragraph("Nextones Desk", S['CoverTitle']))
    story.append(Spacer(1, 12))
    story.append(HorizontalRule(color=TEAL_PRIMARY, thickness=2))
    story.append(Spacer(1, 16))
    story.append(Paragraph("Plateforme de gestion de portefeuille", S['CoverSubtitle']))
    story.append(Paragraph("et d'analyse quantitative", S['CoverSubtitle']))
    story.append(Spacer(1, 30))
    story.append(Paragraph("NEXTONES.FINANCE", S['CoverBrand']))
    story.append(Spacer(1, 16))
    today = datetime.date.today().strftime("%d/%m/%Y")
    story.append(Paragraph(f"Version 2.0 — Mars 2026", S['CoverMeta']))
    story.append(Paragraph(f"Date : {today}", S['CoverMeta']))
    story.append(Paragraph("Classification : Interne", S['CoverMeta']))

    # ── TABLE OF CONTENTS ─────────────────────────────────────────────────
    story.append(PageBreak())

    toc_items = [
        ("1.", "Prerequis systeme"),
        ("2.", "Installation des dependances"),
        ("3.", "Configuration"),
        ("4.", "Structure des fichiers"),
        ("5.", "Demarrage de l'application"),
        ("6.", "Creation du premier administrateur"),
        ("7.", "Configuration des roles (RBAC)"),
        ("8.", "Deploiement en production"),
        ("9.", "Configuration Docker"),
        ("10.", "Variables d'environnement"),
        ("11.", "Depannage"),
        ("12.", "Mise a jour et migration"),
    ]

    story.append(Paragraph("Table des matieres", S['SectionTitle']))
    story.append(HorizontalRule(color=TEAL_PRIMARY, thickness=1))
    story.append(Spacer(1, 12))
    for num, title in toc_items:
        story.append(Paragraph(
            f"<b>{num}</b>&nbsp;&nbsp;&nbsp;{title}", S['TOCItem']))
    story.append(Spacer(1, 20))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 1 — Prerequis
    # ══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("1. Prerequis systeme", S['SectionTitle']))
    story.append(HorizontalRule())
    story.append(Spacer(1, 8))

    story.append(Paragraph("Avant de commencer l'installation de Nextones Desk, "
        "assurez-vous que votre environnement remplit les conditions suivantes.", S['Body']))

    story.append(Paragraph("Systeme d'exploitation", S['SubSection']))
    story.append(make_table(
        ["OS", "Version minimale", "Statut"],
        [
            ["Linux (Ubuntu/Debian)", "20.04 LTS / 11+", "Recommande"],
            ["macOS", "12 Monterey+", "Supporte"],
            ["Windows", "10/11 (avec WSL2)", "Supporte"],
        ],
        [CONTENT_W * 0.35, CONTENT_W * 0.35, CONTENT_W * 0.30]
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Logiciels requis", S['SubSection']))
    story.append(make_table(
        ["Composant", "Version", "Notes"],
        [
            ["Python", "3.11+", "3.12 supporte, 3.13 non teste"],
            ["pip", "23.0+", "Mis a jour automatiquement"],
            ["Git", "2.30+", "Pour cloner le depot"],
            ["SQLite", "3.35+", "Inclus dans Python"],
        ],
        [CONTENT_W * 0.30, CONTENT_W * 0.25, CONTENT_W * 0.45]
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Verification de Python :", S['BodyBold']))
    story.append(code_block("python3 --version\n# Python 3.11.x ou superieur requis\n\npip3 --version"))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Ressources materielles", S['SubSection']))
    story.append(bullet("RAM : 1 Go minimum (2 Go recommande)", S))
    story.append(bullet("Disque : 500 Mo d'espace libre", S))
    story.append(bullet("CPU : 1 vCPU minimum", S))
    story.append(bullet("Reseau : acces Internet pour les API externes (FRED, Yahoo Finance, CoinGecko)", S))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 2 — Installation des dependances
    # ══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("2. Installation des dependances", S['SectionTitle']))
    story.append(HorizontalRule())
    story.append(Spacer(1, 8))

    story.append(Paragraph("Clonez le depot et installez les paquets Python :", S['Body']))
    story.append(code_block(
        "# 1. Cloner le depot\n"
        "git clone https://github.com/nextones/desk.git\n"
        "cd desk\n\n"
        "# 2. Creer un environnement virtuel (recommande)\n"
        "python3 -m venv .venv\n"
        "source .venv/bin/activate  # Linux/macOS\n"
        '# .venv\\Scripts\\activate   # Windows\n\n'
        "# 3. Installer les dependances\n"
        "pip install fastapi \\\n"
        '    "uvicorn[standard]" \\\n'
        '    "passlib[bcrypt]" \\\n'
        '    "python-jose[cryptography]" \\\n'
        "    bcrypt==4.0.1 \\\n"
        "    yfinance numpy pandas requests \\\n"
        "    reportlab pdfplumber"
    ))
    story.append(Spacer(1, 8))

    story.append(warning_box(
        "IMPORTANT : La version bcrypt==4.0.1 est OBLIGATOIRE. "
        "Les versions 4.1+ introduisent des changements d'API qui cassent "
        "la compatibilite avec passlib. Ne pas mettre a jour bcrypt."
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Vous pouvez egalement utiliser le fichier requirements.txt :", S['Body']))
    story.append(code_block(
        "# requirements.txt\n"
        "fastapi>=0.109.0\n"
        "uvicorn[standard]>=0.27.0\n"
        "passlib[bcrypt]>=1.7.4\n"
        "python-jose[cryptography]>=3.3.0\n"
        "bcrypt==4.0.1\n"
        "yfinance>=0.2.36\n"
        "numpy>=1.26.0\n"
        "pandas>=2.2.0\n"
        "requests>=2.31.0\n"
        "reportlab>=4.0\n"
        "pdfplumber>=0.10.0"
    ))
    story.append(Spacer(1, 6))
    story.append(code_block("pip install -r requirements.txt"))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Verification de l'installation :", S['BodyBold']))
    story.append(code_block(
        "python3 -c \"import fastapi, uvicorn, passlib, jose, bcrypt; "
        "print('OK — toutes les dependances sont installees')\""
    ))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 3 — Configuration
    # ══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("3. Configuration", S['SectionTitle']))
    story.append(HorizontalRule())
    story.append(Spacer(1, 8))

    story.append(Paragraph("Cle API FRED", S['SubSection']))
    story.append(Paragraph(
        "Le module Macro US necessite une cle API FRED (Federal Reserve Economic Data) "
        "pour recuperer les indicateurs economiques americains.", S['Body']))
    story.append(code_block(
        "# Option 1 : Variable d'environnement (recommande)\n"
        "export FRED_API_KEY=8d8ef4b05a6d63cec4d7abb7a6031d84\n\n"
        "# Option 2 : Fichier .env\n"
        "echo 'FRED_API_KEY=8d8ef4b05a6d63cec4d7abb7a6031d84' > .env\n\n"
        "# Option 3 : Directement dans data_macro.py (non recommande en production)"
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Secret JWT", S['SubSection']))
    story.append(Paragraph(
        "Un secret JWT est utilise pour signer les tokens d'authentification. "
        "Par defaut, une cle aleatoire est generee automatiquement au premier "
        "demarrage et sauvegardee dans le fichier <font face='Courier'>.jwt_secret</font>.", S['Body']))
    story.append(code_block(
        "# Pour specifier votre propre secret :\n"
        "export JWT_SECRET=votre_secret_personnalise_ici\n\n"
        "# Si non defini, le serveur genere un secret aleatoire\n"
        "# et le sauvegarde dans .jwt_secret"
    ))
    story.append(Spacer(1, 8))

    story.append(info_box(
        "Le secret JWT est crucial pour la securite. En production, "
        "utilisez toujours une variable d'environnement et ne commitez "
        "jamais le fichier .jwt_secret dans votre depot."
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Base de donnees SQLite", S['SubSection']))
    story.append(Paragraph(
        "La base de donnees SQLite (<font face='Courier'>thesium.db</font>) "
        "est creee automatiquement au premier demarrage du serveur. "
        "Elle contient les tables utilisateurs, positions, ordres, theses et configurations.", S['Body']))
    story.append(bullet("Aucune configuration manuelle requise", S))
    story.append(bullet("Fichier cree dans le repertoire de l'application", S))
    story.append(bullet("Sauvegardez regulierement ce fichier (voir section 12)", S))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4 — Structure des fichiers
    # ══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("4. Structure des fichiers", S['SectionTitle']))
    story.append(HorizontalRule())
    story.append(Spacer(1, 8))

    story.append(Paragraph("Arborescence du projet", S['SubSection']))
    story.append(code_block(
        "nextones-desk/\n"
        "|\n"
        "|-- api_server.py          # Serveur FastAPI principal (port 8000)\n"
        "|-- auth.py                # Authentification JWT + bcrypt + RBAC\n"
        "|-- models.py              # Modeles de donnees SQLAlchemy\n"
        "|-- seed_data.py           # Donnees initiales (positions, theses)\n"
        "|\n"
        "|-- agents.py              # Agents IA (Macro, Factor, Micro, Crypto, AltData)\n"
        "|-- risk_engine.py         # Moteur de risque (VaR 95%, limites)\n"
        "|-- execution_engine.py    # Moteur d'execution paper trading\n"
        "|-- memo_generator.py      # Generateur de memos IC\n"
        "|-- backtest_engine.py     # Backtester (Yahoo Finance)\n"
        "|\n"
        "|-- data_ingestion.py      # Orchestrateur d'ingestion\n"
        "|-- data_finviz.py         # Signaux boursiers (Finviz)\n"
        "|-- data_crypto.py         # Donnees crypto (CoinGecko)\n"
        "|-- data_macro.py          # Indicateurs macro (FRED)\n"
        "|-- data_geopolitical.py   # Risque geopolitique (GDELT + USGS)\n"
        "|\n"
        "|-- index.html             # Interface utilisateur\n"
        "|-- app.js                 # Logique frontend JavaScript\n"
        "|-- base.css               # Styles de base\n"
        "|-- style.css              # Styles specifiques\n"
        "|-- mock_data.js           # Donnees de demonstration\n"
        "|\n"
        "|-- thesium.db             # Base de donnees SQLite (auto-creee)\n"
        "|-- .jwt_secret            # Secret JWT (auto-genere)\n"
        "|-- requirements.txt       # Dependances Python\n"
        "|-- .env                   # Variables d'environnement (optionnel)\n"
        "|-- Dockerfile             # Image Docker (optionnel)\n"
        "|-- docker-compose.yml     # Orchestration Docker (optionnel)"
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Description des modules", S['SubSection']))
    story.append(make_table(
        ["Fichier", "Role", "Port / API"],
        [
            ["api_server.py", "Point d'entree FastAPI, routes REST, middleware CORS", "8000"],
            ["auth.py", "JWT tokens, hachage bcrypt, middleware RBAC", "—"],
            ["agents.py", "5 agents IA generant des theses d'investissement", "—"],
            ["risk_engine.py", "VaR 95%, limites de position/secteur, drawdown", "—"],
            ["execution_engine.py", "Paper trading, generation d'ordres", "—"],
            ["backtest_engine.py", "Backtester multi-actifs via Yahoo Finance", "—"],
            ["data_macro.py", "Indicateurs FRED (PIB, chomage, inflation...)", "FRED API"],
            ["data_crypto.py", "Top 25 crypto via CoinGecko", "CoinGecko"],
            ["data_finviz.py", "Signaux boursiers, dynamique sectorielle", "Finviz"],
            ["data_geopolitical.py", "Risque geopolitique (GDELT + USGS)", "GDELT/USGS"],
        ],
        [CONTENT_W * 0.28, CONTENT_W * 0.50, CONTENT_W * 0.22]
    ))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 5 — Demarrage
    # ══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("5. Demarrage de l'application", S['SectionTitle']))
    story.append(HorizontalRule())
    story.append(Spacer(1, 8))

    story.append(Paragraph("Lancez le serveur avec la commande suivante :", S['Body']))
    story.append(code_block(
        "# Demarrage du serveur\n"
        "python api_server.py\n\n"
        "# Le serveur demarre sur le port 8000\n"
        "# Sortie attendue :\n"
        "# INFO:     Uvicorn running on http://0.0.0.0:8000\n"
        "# INFO:     Application startup complete."
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Acces a l'application :", S['BodyBold']))
    story.append(make_table(
        ["Service", "URL", "Description"],
        [
            ["Interface web", "http://localhost:8000", "Application complete"],
            ["API REST", "http://localhost:8000/api/", "Endpoints FastAPI"],
            ["Documentation API", "http://localhost:8000/docs", "Swagger UI auto-generee"],
        ],
        [CONTENT_W * 0.25, CONTENT_W * 0.35, CONTENT_W * 0.40]
    ))
    story.append(Spacer(1, 8))

    story.append(info_box(
        "Le serveur sert a la fois l'API REST et les fichiers statiques "
        "(HTML/CSS/JS). Aucun serveur web supplementaire n'est necessaire "
        "pour le developpement."
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Demarrage avec options :", S['SubSection']))
    story.append(code_block(
        "# Specifier un port different\n"
        "PORT=9000 python api_server.py\n\n"
        "# Specifier l'hote (pour acces reseau)\n"
        "HOST=0.0.0.0 PORT=8000 python api_server.py\n\n"
        "# Mode developpement avec rechargement automatique\n"
        "uvicorn api_server:app --reload --host 0.0.0.0 --port 8000"
    ))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 6 — Premier administrateur
    # ══════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 16))
    story.append(Paragraph("6. Creation du premier administrateur", S['SectionTitle']))
    story.append(HorizontalRule())
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        "Lors du premier demarrage, aucun utilisateur n'existe. "
        "Creez le compte administrateur via l'API :", S['Body']))
    story.append(code_block(
        'curl -X POST http://localhost:8000/api/auth/register \\\n'
        '  -H "Content-Type: application/json" \\\n'
        '  -d \'{\n'
        '    "username": "admin",\n'
        '    "email": "admin@nextones.finance",\n'
        '    "password": "VotreMotDePasse!2026",\n'
        '    "full_name": "Administrateur",\n'
        '    "role": "admin"\n'
        '  }\''
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Connexion et obtention du token :", S['BodyBold']))
    story.append(code_block(
        '# Obtenir un token JWT\n'
        'curl -X POST http://localhost:8000/api/auth/login \\\n'
        '  -H "Content-Type: application/json" \\\n'
        '  -d \'{"username": "admin", "password": "VotreMotDePasse!2026"}\'\n\n'
        '# Reponse :\n'
        '# {"access_token": "eyJhbG...", "token_type": "bearer", "role": "admin"}'
    ))
    story.append(Spacer(1, 8))

    story.append(warning_box(
        "SECURITE : Changez immediatement le mot de passe par defaut "
        "apres la premiere connexion. Utilisez un mot de passe fort "
        "(min. 12 caracteres, majuscules, chiffres, symboles)."
    ))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 7 — Configuration des roles
    # ══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("7. Configuration des roles (RBAC)", S['SectionTitle']))
    story.append(HorizontalRule())
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        "Nextones Desk utilise un systeme de controle d'acces base sur les roles "
        "(RBAC) avec 4 niveaux hierarchiques.", S['Body']))
    story.append(Spacer(1, 6))

    story.append(make_table(
        ["Role", "Niveau", "Permissions"],
        [
            ["Viewer", "0", "Lecture seule : dashboards, rapports, consultation des donnees"],
            ["Analyst", "1", "Viewer + propositions de theses, backtests, export CSV"],
            ["Manager", "2", "Analyst + validation des theses, lancement des cycles d'execution et d'ingestion"],
            ["Admin", "3", "Acces total + gestion des utilisateurs, configuration du risk engine"],
        ],
        [CONTENT_W * 0.15, CONTENT_W * 0.12, CONTENT_W * 0.73]
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Endpoints proteges par role :", S['SubSection']))
    story.append(make_table(
        ["Endpoint", "Methode", "Role minimum"],
        [
            ["/api/orders/execute-cycle", "POST", "Manager"],
            ["/api/run-agents", "POST", "Manager"],
            ["/api/run-ingestion", "POST", "Manager"],
            ["/api/risk-config", "PUT", "Admin"],
            ["/api/admin/*", "ALL", "Admin"],
        ],
        [CONTENT_W * 0.42, CONTENT_W * 0.18, CONTENT_W * 0.40]
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Attribution des roles via l'onglet Admin", S['SubSection']))
    story.append(Paragraph(
        "L'onglet Administration (visible uniquement pour les utilisateurs admin) "
        "permet de gerer les comptes :", S['Body']))
    story.append(bullet("Lister tous les utilisateurs avec statut, role et derniere connexion", S))
    story.append(bullet("Creer un nouvel utilisateur (nom, email, mot de passe, role)", S))
    story.append(bullet("Modifier le role via un menu deroulant", S))
    story.append(bullet("Activer/desactiver un compte (suppression logique)", S))
    story.append(bullet("Reinitialiser le mot de passe d'un utilisateur", S))
    story.append(Spacer(1, 8))

    story.append(Paragraph("API d'administration :", S['SubSection']))
    story.append(make_table(
        ["Endpoint", "Methode", "Description"],
        [
            ["/api/admin/users", "GET", "Lister tous les utilisateurs"],
            ["/api/admin/users", "POST", "Creer un utilisateur"],
            ["/api/admin/users/{id}", "PUT", "Modifier role/statut/nom"],
            ["/api/admin/users/{id}/reset-password", "POST", "Reinitialiser le mot de passe"],
            ["/api/admin/users/{id}", "DELETE", "Desactiver un utilisateur"],
            ["/api/admin/roles", "GET", "Lister les roles et permissions"],
        ],
        [CONTENT_W * 0.40, CONTENT_W * 0.15, CONTENT_W * 0.45]
    ))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 8 — Deploiement en production
    # ══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("8. Deploiement en production", S['SectionTitle']))
    story.append(HorizontalRule())
    story.append(Spacer(1, 8))

    story.append(Paragraph("Hebergement VPS", S['SubSection']))
    story.append(Paragraph(
        "Nextones Desk peut etre deploye sur n'importe quel VPS Linux. "
        "Voici les fournisseurs recommandes :", S['Body']))
    story.append(make_table(
        ["Fournisseur", "Plan minimum", "Prix indicatif"],
        [
            ["OVH", "VPS Starter (1 vCPU, 2 Go RAM)", "~4 EUR/mois"],
            ["Scaleway", "DEV1-S (2 vCPU, 2 Go RAM)", "~4 EUR/mois"],
            ["Hetzner", "CX22 (2 vCPU, 4 Go RAM)", "~4 EUR/mois"],
        ],
        [CONTENT_W * 0.30, CONTENT_W * 0.40, CONTENT_W * 0.30]
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Reverse proxy Nginx", S['SubSection']))
    story.append(Paragraph(
        "En production, utilisez Nginx comme reverse proxy devant Uvicorn :", S['Body']))
    story.append(code_block(
        "# /etc/nginx/sites-available/nextones\n"
        "server {\n"
        "    listen 80;\n"
        "    server_name desk.nextones.finance;\n\n"
        "    location / {\n"
        "        proxy_pass http://127.0.0.1:8000;\n"
        "        proxy_set_header Host $host;\n"
        "        proxy_set_header X-Real-IP $remote_addr;\n"
        "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
        "        proxy_set_header X-Forwarded-Proto $scheme;\n"
        "    }\n"
        "}"
    ))
    story.append(Spacer(1, 8))

    story.append(code_block(
        "# Activer le site\n"
        "sudo ln -s /etc/nginx/sites-available/nextones /etc/nginx/sites-enabled/\n"
        "sudo nginx -t\n"
        "sudo systemctl reload nginx"
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("HTTPS avec Let's Encrypt", S['SubSection']))
    story.append(code_block(
        "# Installer Certbot\n"
        "sudo apt install certbot python3-certbot-nginx\n\n"
        "# Obtenir un certificat SSL\n"
        "sudo certbot --nginx -d desk.nextones.finance\n\n"
        "# Renouvellement automatique (cron)\n"
        "sudo certbot renew --dry-run"
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Service systemd", S['SubSection']))
    story.append(Paragraph(
        "Creez un service systemd pour un demarrage automatique :", S['Body']))
    story.append(code_block(
        "# /etc/systemd/system/nextones-desk.service\n"
        "[Unit]\n"
        "Description=Nextones Desk API Server\n"
        "After=network.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        "User=nextones\n"
        "WorkingDirectory=/opt/nextones-desk\n"
        "Environment=FRED_API_KEY=8d8ef4b05a6d63cec4d7abb7a6031d84\n"
        "Environment=JWT_SECRET=votre_secret_production\n"
        "ExecStart=/opt/nextones-desk/.venv/bin/python api_server.py\n"
        "Restart=always\n"
        "RestartSec=5\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target"
    ))
    story.append(Spacer(1, 6))
    story.append(code_block(
        "sudo systemctl daemon-reload\n"
        "sudo systemctl enable nextones-desk\n"
        "sudo systemctl start nextones-desk\n"
        "sudo systemctl status nextones-desk"
    ))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 9 — Configuration Docker
    # ══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("9. Configuration Docker", S['SectionTitle']))
    story.append(HorizontalRule())
    story.append(Spacer(1, 8))

    story.append(Paragraph("Dockerfile", S['SubSection']))
    story.append(code_block(
        "FROM python:3.11-slim\n\n"
        "WORKDIR /app\n\n"
        "# Dependances systeme\n"
        "RUN apt-get update && apt-get install -y --no-install-recommends \\\n"
        "    gcc libffi-dev && \\\n"
        "    rm -rf /var/lib/apt/lists/*\n\n"
        "# Dependances Python\n"
        "COPY requirements.txt .\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n\n"
        "# Code applicatif\n"
        "COPY . .\n\n"
        "# Port expose\n"
        "EXPOSE 8000\n\n"
        "# Volume pour la base de donnees\n"
        "VOLUME /app/data\n\n"
        '# Demarrage\n'
        'CMD ["python", "api_server.py"]'
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("docker-compose.yml", S['SubSection']))
    story.append(code_block(
        'version: "3.8"\n\n'
        "services:\n"
        "  nextones-desk:\n"
        "    build: .\n"
        "    container_name: nextones-desk\n"
        "    ports:\n"
        '      - "8000:8000"\n'
        "    environment:\n"
        "      - FRED_API_KEY=8d8ef4b05a6d63cec4d7abb7a6031d84\n"
        "      - JWT_SECRET=${JWT_SECRET:-auto}\n"
        "      - HOST=0.0.0.0\n"
        "      - PORT=8000\n"
        "    volumes:\n"
        "      - nextones-data:/app/data\n"
        "    restart: unless-stopped\n"
        "    healthcheck:\n"
        "      test: [\"CMD\", \"curl\", \"-f\", \"http://localhost:8000/api/health\"]\n"
        "      interval: 30s\n"
        "      timeout: 10s\n"
        "      retries: 3\n\n"
        "volumes:\n"
        "  nextones-data:\n"
        "    driver: local"
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Commandes Docker :", S['SubSection']))
    story.append(code_block(
        "# Construire et demarrer\n"
        "docker-compose up -d --build\n\n"
        "# Voir les logs\n"
        "docker-compose logs -f nextones-desk\n\n"
        "# Arreter\n"
        "docker-compose down\n\n"
        "# Redemarrer\n"
        "docker-compose restart"
    ))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 10 — Variables d'environnement
    # ══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("10. Variables d'environnement", S['SectionTitle']))
    story.append(HorizontalRule())
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        "Nextones Desk peut etre configure via des variables d'environnement. "
        "Toutes sont optionnelles sauf FRED_API_KEY pour le module Macro US.", S['Body']))
    story.append(Spacer(1, 6))

    story.append(make_table(
        ["Variable", "Obligatoire", "Defaut", "Description"],
        [
            ["FRED_API_KEY", "Oui*", "—", "Cle API FRED pour les donnees macro US"],
            ["JWT_SECRET", "Non", "Auto-genere", "Secret pour la signature des tokens JWT"],
            ["HOST", "Non", "0.0.0.0", "Adresse d'ecoute du serveur"],
            ["PORT", "Non", "8000", "Port d'ecoute du serveur"],
        ],
        [CONTENT_W * 0.23, CONTENT_W * 0.15, CONTENT_W * 0.20, CONTENT_W * 0.42]
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<i>* Obligatoire uniquement si le module Macro US est utilise.</i>", S['Note']))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Exemple de fichier .env :", S['BodyBold']))
    story.append(code_block(
        "# .env — Variables d'environnement Nextones Desk\n"
        "FRED_API_KEY=8d8ef4b05a6d63cec4d7abb7a6031d84\n"
        "JWT_SECRET=mon_secret_super_securise_ici\n"
        "HOST=0.0.0.0\n"
        "PORT=8000"
    ))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 11 — Depannage
    # ══════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 16))
    story.append(Paragraph("11. Depannage", S['SectionTitle']))
    story.append(HorizontalRule())
    story.append(Spacer(1, 8))

    story.append(Paragraph("Erreur bcrypt / passlib", S['SubSection']))
    story.append(Paragraph(
        "Symptome : <font face='Courier'>AttributeError: module 'bcrypt' has no "
        "attribute '__about__'</font> ou erreur similaire lors de la connexion.", S['Body']))
    story.append(Paragraph("Solution :", S['BodyBold']))
    story.append(code_block(
        "pip uninstall bcrypt -y\n"
        "pip install bcrypt==4.0.1\n\n"
        "# Verifier la version\n"
        "python -c \"import bcrypt; print(bcrypt.__version__)\"\n"
        "# Doit afficher : 4.0.1"
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Port deja utilise", S['SubSection']))
    story.append(Paragraph(
        "Symptome : <font face='Courier'>OSError: [Errno 98] Address already in use</font>", S['Body']))
    story.append(Paragraph("Solution :", S['BodyBold']))
    story.append(code_block(
        "# Identifier le processus utilisant le port\n"
        "lsof -i :8000    # Linux/macOS\n"
        "netstat -ano | findstr :8000    # Windows\n\n"
        "# Tuer le processus\n"
        "kill -9 <PID>\n\n"
        "# Ou utiliser un port different\n"
        "PORT=9000 python api_server.py"
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Erreur CORS", S['SubSection']))
    story.append(Paragraph(
        "Symptome : Requetes bloquees depuis un autre domaine "
        "(<font face='Courier'>Access-Control-Allow-Origin</font>).", S['Body']))
    story.append(Paragraph(
        "Le serveur FastAPI inclut un middleware CORS configure par defaut "
        "pour accepter toutes les origines en developpement. En production, "
        "restreignez les origines dans <font face='Courier'>api_server.py</font> :", S['Body']))
    story.append(code_block(
        "# Dans api_server.py, modifier :\n"
        "app.add_middleware(\n"
        "    CORSMiddleware,\n"
        '    allow_origins=["https://desk.nextones.finance"],\n'
        "    allow_credentials=True,\n"
        '    allow_methods=["*"],\n'
        '    allow_headers=["*"],\n'
        ")"
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Timeout API FRED", S['SubSection']))
    story.append(Paragraph(
        "Symptome : Les donnees macro ne se chargent pas, timeout apres 30 secondes.", S['Body']))
    story.append(Paragraph("Solutions :", S['BodyBold']))
    story.append(bullet("Verifiez que la cle API FRED est valide", S))
    story.append(bullet("Verifiez la connectivite reseau vers api.stlouisfed.org", S))
    story.append(bullet("L'API FRED a un rate limit de 120 requetes/minute", S))
    story.append(bullet("En cas de panne FRED, les donnees en cache sont utilisees", S))
    story.append(code_block(
        "# Tester la connectivite FRED\n"
        "curl -s \"https://api.stlouisfed.org/fred/series?series_id=GDP\\\n"
        "&api_key=8d8ef4b05a6d63cec4d7abb7a6031d84&file_type=json\" | head -c 200"
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Erreur d'import Python", S['SubSection']))
    story.append(Paragraph(
        "Symptome : <font face='Courier'>ModuleNotFoundError</font> au demarrage.", S['Body']))
    story.append(code_block(
        "# Verifiez que l'environnement virtuel est active\n"
        "which python    # Doit pointer vers .venv/bin/python\n\n"
        "# Reinstallez les dependances\n"
        "pip install -r requirements.txt"
    ))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 12 — Mise a jour et migration
    # ══════════════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("12. Mise a jour et migration", S['SectionTitle']))
    story.append(HorizontalRule())
    story.append(Spacer(1, 8))

    story.append(Paragraph("Processus de mise a jour", S['SubSection']))
    story.append(Paragraph(
        "Suivez ces etapes pour mettre a jour Nextones Desk vers une nouvelle version :", S['Body']))

    steps = [
        ("Sauvegarder la base de donnees",
         "cp thesium.db thesium.db.backup.$(date +%Y%m%d)"),
        ("Sauvegarder la configuration",
         "cp .env .env.backup\ncp .jwt_secret .jwt_secret.backup"),
        ("Recuperer la nouvelle version",
         "git pull origin main"),
        ("Mettre a jour les dependances",
         "pip install -r requirements.txt"),
        ("Redemarrer le serveur",
         "# Systemd\nsudo systemctl restart nextones-desk\n\n"
         "# Docker\ndocker-compose down && docker-compose up -d --build"),
    ]
    for i, (title, cmd) in enumerate(steps, 1):
        story.append(Paragraph(f"Etape {i} : {title}", S['SubSub']))
        story.append(code_block(cmd))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Sauvegarde automatique", S['SubSection']))
    story.append(Paragraph(
        "Configurez une sauvegarde automatique quotidienne de la base de donnees :", S['Body']))
    story.append(code_block(
        "# Ajouter au crontab (crontab -e)\n"
        "0 2 * * * cp /opt/nextones-desk/thesium.db \\\n"
        "  /opt/nextones-desk/backups/thesium.db.$(date +\\%Y\\%m\\%d)"
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Migration de la base", S['SubSection']))
    story.append(Paragraph(
        "En cas de changement de schema de base de donnees entre versions, "
        "un script de migration est fourni :", S['Body']))
    story.append(code_block(
        "# Verifier la version actuelle du schema\n"
        "sqlite3 thesium.db \"PRAGMA user_version;\"\n\n"
        "# Appliquer les migrations\n"
        "python migrate.py\n\n"
        "# En cas de probleme, restaurer le backup\n"
        "cp thesium.db.backup.YYYYMMDD thesium.db"
    ))
    story.append(Spacer(1, 8))

    story.append(warning_box(
        "ATTENTION : Sauvegardez TOUJOURS la base de donnees avant une "
        "mise a jour. Les migrations ne sont pas reversibles automatiquement."
    ))

    story.append(Spacer(1, 20))
    story.append(HorizontalRule(color=TEAL_PRIMARY, thickness=2))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Pour toute question ou assistance, contactez l'equipe Nextones :", S['Body']))
    story.append(bullet("Email : support@nextones.finance", S))
    story.append(bullet("Site : https://nextones.finance", S))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<i>Document genere automatiquement — Mars 2026</i>", S['Note']))

    return story


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def main():
    output = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "Guide_Installation_Nextones_Desk.pdf")

    doc = InstallGuideTemplate(
        output,
        pagesize=A4,
        title="Guide Installation — Nextones Desk",
        author="Perplexity Computer",
        leftMargin=ML,
        rightMargin=MR,
        topMargin=MT,
        bottomMargin=MB,
    )

    styles = get_styles()
    story = build_story(styles)

    doc.build(story)
    print(f"PDF genere : {output}")
    print(f"Taille : {os.path.getsize(output) / 1024:.1f} Ko")


if __name__ == "__main__":
    main()
