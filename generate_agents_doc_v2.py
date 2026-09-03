"""
Generate PDF: Architecture & Agents — Nextones Desk
Comprehensive French-language documentation covering all agents, risk engine,
execution, backtest, auth/RBAC, geopolitical risk, data ingestion, DB schema, and API reference.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import os

# ── Perplexity / Nextones Brand Colors ──
DARK_NAVY    = HexColor("#091717")
DARK_TEAL    = HexColor("#13343B")
DEEP_TEAL    = HexColor("#115058")
MED_TEAL     = HexColor("#2E565D")
MUTED_TEAL   = HexColor("#20808D")
LIGHT_TEAL   = HexColor("#D6F5FA")
OFF_WHITE    = HexColor("#FCFAF6")
PAPER_WHITE  = HexColor("#F3F3EE")
WARM_BEIGE   = HexColor("#E5E3D4")
TERRA        = HexColor("#A84B2F")
MAUVE        = HexColor("#944454")
GOLD         = HexColor("#FFC553")
OLIVE        = HexColor("#848456")

AGENT_COLORS = [MUTED_TEAL, TERRA, DEEP_TEAL, MAUVE, GOLD]

PAGE_W, PAGE_H = A4
LEFT_MARGIN = 20*mm
RIGHT_MARGIN = 20*mm
TOP_MARGIN = 25*mm
BOT_MARGIN = 25*mm
CONTENT_W = PAGE_W - LEFT_MARGIN - RIGHT_MARGIN

# ── Styles ──
styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "DocTitle", parent=styles["Title"],
    fontName="Helvetica-Bold", fontSize=26, leading=32,
    textColor=DARK_TEAL, alignment=TA_LEFT, spaceAfter=6*mm
)

subtitle_style = ParagraphStyle(
    "DocSubtitle", parent=styles["Normal"],
    fontName="Helvetica", fontSize=13, leading=17,
    textColor=MED_TEAL, alignment=TA_LEFT, spaceAfter=10*mm
)

h1_style = ParagraphStyle(
    "H1", parent=styles["Heading1"],
    fontName="Helvetica-Bold", fontSize=16, leading=20,
    textColor=DARK_TEAL, spaceBefore=5*mm, spaceAfter=2.5*mm
)

h2_style = ParagraphStyle(
    "H2", parent=styles["Heading2"],
    fontName="Helvetica-Bold", fontSize=12, leading=15,
    textColor=DEEP_TEAL, spaceBefore=3*mm, spaceAfter=1.5*mm
)

h3_style = ParagraphStyle(
    "H3", parent=styles["Heading3"],
    fontName="Helvetica-Bold", fontSize=10.5, leading=14,
    textColor=MED_TEAL, spaceBefore=3*mm, spaceAfter=1.5*mm
)

body_style = ParagraphStyle(
    "Body", parent=styles["Normal"],
    fontName="Helvetica", fontSize=9.5, leading=12.5,
    textColor=DARK_TEAL, alignment=TA_JUSTIFY, spaceAfter=2*mm
)

body_bold = ParagraphStyle(
    "BodyBold", parent=body_style,
    fontName="Helvetica-Bold"
)

bullet_style = ParagraphStyle(
    "Bullet", parent=body_style,
    leftIndent=10*mm, bulletIndent=5*mm,
    spaceBefore=0.3*mm, spaceAfter=0.3*mm
)

caption_style = ParagraphStyle(
    "Caption", parent=styles["Normal"],
    fontName="Helvetica-Oblique", fontSize=8, leading=11,
    textColor=MED_TEAL, alignment=TA_CENTER, spaceBefore=2*mm, spaceAfter=4*mm
)

footer_style = ParagraphStyle(
    "Footer", parent=styles["Normal"],
    fontName="Helvetica", fontSize=7, leading=9,
    textColor=MED_TEAL, alignment=TA_CENTER
)

toc_style = ParagraphStyle(
    "TOC", parent=body_style,
    fontSize=10, leading=15, leftIndent=5*mm,
    textColor=DEEP_TEAL
)

toc_sub_style = ParagraphStyle(
    "TOCSub", parent=body_style,
    fontSize=9.5, leading=14, leftIndent=12*mm,
    textColor=MED_TEAL
)

code_style = ParagraphStyle(
    "Code", parent=body_style,
    fontName="Courier", fontSize=8.5, leading=12,
    textColor=DARK_TEAL, leftIndent=5*mm
)

# ── Page template functions ──
def cover_page(canvas, doc):
    canvas.saveState()
    # Top band
    canvas.setFillColor(DARK_TEAL)
    canvas.rect(0, PAGE_H - 65*mm, PAGE_W, 65*mm, fill=1, stroke=0)
    # Accent line
    canvas.setFillColor(MUTED_TEAL)
    canvas.rect(0, PAGE_H - 67*mm, PAGE_W, 2*mm, fill=1, stroke=0)
    # Title block
    canvas.setFillColor(white)
    canvas.setFont("Helvetica-Bold", 28)
    canvas.drawString(LEFT_MARGIN, PAGE_H - 32*mm, "Architecture & Agents")
    canvas.setFont("Helvetica", 16)
    canvas.drawString(LEFT_MARGIN, PAGE_H - 45*mm, "Nextones Desk — Documentation Technique")
    canvas.setFont("Helvetica", 11)
    canvas.drawString(LEFT_MARGIN, PAGE_H - 57*mm, f"Version 2.0 — {datetime.now().strftime('%d/%m/%Y')}")
    # Bottom accent
    canvas.setFillColor(MUTED_TEAL)
    canvas.rect(0, 0, PAGE_W, 12*mm, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(PAGE_W/2, 4.5*mm, "NEXTONES.FINANCE  •  Document confidentiel  •  Perplexity Computer")
    canvas.restoreState()


def later_pages(canvas, doc):
    canvas.saveState()
    # Header band
    canvas.setFillColor(DARK_TEAL)
    canvas.rect(0, PAGE_H - 14*mm, PAGE_W, 14*mm, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(LEFT_MARGIN, PAGE_H - 10*mm, "NEXTONES.FINANCE — Architecture & Agents")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(PAGE_W - RIGHT_MARGIN, PAGE_H - 10*mm, f"Page {doc.page}")
    # Footer
    canvas.setFillColor(MUTED_TEAL)
    canvas.rect(0, 0, PAGE_W, 8*mm, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Helvetica", 7)
    canvas.drawCentredString(PAGE_W/2, 2.5*mm, f"NEXTONES.FINANCE  •  {datetime.now().strftime('%d/%m/%Y')}  •  Perplexity Computer")
    canvas.restoreState()


# ── Helper functions ──
def make_info_table(rows_data, header_color=MUTED_TEAL):
    """Key/value info table."""
    data = []
    for key, val in rows_data:
        data.append([
            Paragraph(f"<b>{key}</b>", ParagraphStyle("K", parent=body_style, fontSize=9, textColor=white)),
            Paragraph(val, ParagraphStyle("V", parent=body_style, fontSize=9))
        ])
    t = Table(data, colWidths=[45*mm, CONTENT_W - 45*mm])
    style_cmds = [
        ("BACKGROUND", (0, 0), (0, -1), header_color),
        ("BACKGROUND", (1, 0), (1, -1), PAPER_WHITE),
        ("TOPPADDING", (0, 0), (-1, -1), 3*mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3*mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 3*mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3*mm),
        ("GRID", (0, 0), (-1, -1), 0.5, WARM_BEIGE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    t.setStyle(TableStyle(style_cmds))
    return t


def make_data_table(headers, rows, col_widths=None, header_color=DARK_TEAL):
    """Generic data table with header row."""
    hdr_style = ParagraphStyle("TH", parent=body_style, fontSize=8.5, textColor=white, fontName="Helvetica-Bold", alignment=TA_CENTER)
    cell_style = ParagraphStyle("TD", parent=body_style, fontSize=8.5, leading=11, alignment=TA_LEFT)
    cell_center = ParagraphStyle("TDC", parent=body_style, fontSize=8.5, leading=11, alignment=TA_CENTER)

    data = [[Paragraph(f"<b>{h}</b>", hdr_style) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), cell_center if i == 0 else cell_style) for i, c in enumerate(row)])

    if col_widths is None:
        col_widths = [CONTENT_W / len(headers)] * len(headers)

    t = Table(data, colWidths=col_widths)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5*mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5*mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 2*mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2*mm),
        ("GRID", (0, 0), (-1, -1), 0.5, WARM_BEIGE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    # Alternate row colors
    for i in range(1, len(data)):
        bg = PAPER_WHITE if i % 2 == 1 else OFF_WHITE
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
    t.setStyle(TableStyle(style_cmds))
    return t


def hr():
    return HRFlowable(width="100%", thickness=0.5, color=WARM_BEIGE, spaceBefore=2*mm, spaceAfter=2*mm)


def bullet(text):
    return Paragraph(text, bullet_style, bulletText="\u25b8")


# ══════════════════════════════════════════════════════════════════════
# DOCUMENT CONTENT
# ══════════════════════════════════════════════════════════════════════

story = []

# ── COVER PAGE ──
story.append(Spacer(1, 55*mm))

story.append(Paragraph(
    "Ce document presente l'architecture complete de <b>Nextones Desk</b>, "
    "un systeme de gestion de portefeuille intelligent propulse par l'IA. "
    "Il couvre le pipeline de decision multi-agents, les moteurs de risque et d'execution, "
    "le backtester, l'authentification RBAC, l'ingestion de donnees, le schema de base de donnees "
    "et la reference complete de l'API.",
    ParagraphStyle("CoverBody", parent=body_style, fontSize=12, leading=17, textColor=DARK_TEAL, spaceAfter=8*mm)
))

cover_info = [
    ("Projet", "Nextones Desk (nextones.finance)"),
    ("Version", "2.0"),
    ("Date", datetime.now().strftime("%d/%m/%Y")),
    ("Auteur", "Perplexity Computer"),
    ("Agents IA", "5 (Macro, Factor, Microstructure, AltData, Crypto)"),
    ("Stack", "Python 3.11 / FastAPI / SQLite / Vanilla JS"),
    ("Sections", "15 chapitres — Architecture, Agents, Risk, Execution, Backtest, RBAC, API"),
]
story.append(make_info_table(cover_info, header_color=DEEP_TEAL))
story.append(PageBreak())

# ── TABLE OF CONTENTS ──
story.append(Paragraph("Table des matieres", h1_style))
story.append(Spacer(1, 4*mm))

toc_entries = [
    ("1.", "Vue d'ensemble de l'architecture", toc_style),
    ("2.", "Pipeline de decision", toc_style),
    ("3.", "MacroAgent — Analyse macro-economique", toc_style),
    ("4.", "FactorAgent — Analyse factorielle", toc_style),
    ("5.", "MicrostructureAgent — Microstructure de marche", toc_style),
    ("6.", "CryptoAgent — Analyse crypto-actifs", toc_style),
    ("7.", "AltDataAgent — Donnees alternatives", toc_style),
    ("8.", "Moteur de risque", toc_style),
    ("9.", "Moteur d'execution", toc_style),
    ("10.", "Backtest Engine", toc_style),
    ("11.", "Authentification et RBAC", toc_style),
    ("12.", "Risque geopolitique", toc_style),
    ("13.", "Ingestion des donnees", toc_style),
    ("14.", "Base de donnees", toc_style),
    ("15.", "API Reference", toc_style),
]
for num, text, style in toc_entries:
    story.append(Paragraph(f"<b>{num}</b> {text}", style))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 1: Vue d'ensemble de l'architecture
# ═══════════════════════════════════════════════════════

story.append(Paragraph("1. Vue d'ensemble de l'architecture", h1_style))
story.append(hr())

story.append(Paragraph(
    "Nextones Desk est construit sur une architecture <b>modulaire</b> organisee en quatre couches principales : "
    "la couche d'<b>ingestion de donnees</b>, la couche d'<b>analyse multi-agents</b>, la couche de "
    "<b>decision et risque</b>, et la couche de <b>presentation</b>.",
    body_style
))

story.append(Paragraph("1.1 Composants principaux", h2_style))

arch_items = [
    "<b>Backend FastAPI</b> : Serveur Python (port 8000) exposant une API REST complete. "
    "Gere l'orchestration des agents, le risk engine, l'execution paper trading et l'authentification JWT.",
    "<b>Base de donnees SQLite</b> : Stockage local unique (nextones.db) regroupant prix, theses, ordres, "
    "positions, evenements, configurations de risque et utilisateurs.",
    "<b>5 Agents IA</b> : MacroAgent, FactorAgent, MicrostructureAgent, CryptoAgent et AltDataAgent. "
    "Chacun produit des theses d'investissement avec un score de conviction (0-10).",
    "<b>Risk Engine</b> : Verification VaR 95%, limites de position (20% max), limites sectorielles (35% max), "
    "monitoring drawdown (15% max), verification pre-trade systematique.",
    "<b>Execution Engine</b> : Paper trading avec simulation de fills, slippage, et gestion du cycle order-fill-position.",
    "<b>Frontend Vanilla JS</b> : Interface web single-page avec onglets (Dashboard, Theses, Orders, Market Intel, "
    "Macro US, IC Memos, Backtest, Administration), Chart.js pour les graphiques.",
]
for item in arch_items:
    story.append(bullet(item))

story.append(Paragraph("1.2 Schema global", h2_style))

story.append(Paragraph(
    "Le diagramme conceptuel ci-dessous illustre le flux de donnees principal :",
    body_style
))

# ASCII-style architecture diagram as a table
arch_flow = [
    ["Sources Externes", "\u2192", "Ingestion Layer", "\u2192", "SQLite DB"],
    ["(Yahoo, CoinGecko,", "", "(yfinance, requests,", "", "(prices, instruments,"],
    ["FRED, Finviz, GDELT)", "", "APIs scheduled)", "", "events, theses...)"],
    ["", "", "", "", ""],
    ["", "", "5 Agents IA", "\u2192", "Theses + Convictions"],
    ["", "", "(Macro, Factor, Micro,", "", "(score 0-10, horizon,"],
    ["", "", "Crypto, AltData)", "", "drivers, action)"],
    ["", "", "", "", ""],
    ["", "", "Risk Engine", "\u2192", "VaR Check + Limites"],
    ["", "", "(pre-trade check)", "", "(position, secteur, DD)"],
    ["", "", "", "", ""],
    ["", "", "Execution Engine", "\u2192", "Orders + Fills"],
    ["", "", "(paper trading)", "", "(simulation slippage)"],
]
arch_cell = ParagraphStyle("ArchCell", parent=body_style, fontSize=8, leading=10, alignment=TA_CENTER, textColor=DARK_TEAL)
arch_data = [[Paragraph(c, arch_cell) for c in row] for row in arch_flow]
arch_table = Table(arch_data, colWidths=[35*mm, 10*mm, 40*mm, 10*mm, 40*mm])
arch_table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (0, 2), LIGHT_TEAL),
    ("BACKGROUND", (2, 0), (2, 2), LIGHT_TEAL),
    ("BACKGROUND", (4, 0), (4, 2), LIGHT_TEAL),
    ("BACKGROUND", (2, 4), (2, 6), HexColor("#E0F2F1")),
    ("BACKGROUND", (4, 4), (4, 6), HexColor("#E0F2F1")),
    ("BACKGROUND", (2, 8), (2, 9), HexColor("#FBE9E7")),
    ("BACKGROUND", (4, 8), (4, 9), HexColor("#FBE9E7")),
    ("BACKGROUND", (2, 11), (2, 12), HexColor("#E8F5E9")),
    ("BACKGROUND", (4, 11), (4, 12), HexColor("#E8F5E9")),
    ("TOPPADDING", (0, 0), (-1, -1), 1*mm),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 1*mm),
    ("GRID", (0, 0), (-1, -1), 0, white),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
]))
story.append(arch_table)
story.append(Paragraph("Figure 1 — Flux de donnees Nextones Desk", caption_style))

story.append(Paragraph("1.3 Stack technique", h2_style))

stack_data = [
    ("Backend", "Python 3.11+, FastAPI, uvicorn, SQLite3"),
    ("Librairies", "yfinance, numpy, pandas, requests, reportlab"),
    ("Auth", "passlib[bcrypt] 4.0.1, python-jose, bcrypt 4.0.1"),
    ("Frontend", "HTML5, CSS3, Vanilla JS, Chart.js CDN"),
    ("Deploiement", "Port 8000, fichiers statiques servis par FastAPI"),
]
story.append(make_info_table(stack_data, header_color=MUTED_TEAL))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 2: Pipeline de decision
# ═══════════════════════════════════════════════════════

story.append(Paragraph("2. Pipeline de decision", h1_style))
story.append(hr())

story.append(Paragraph(
    "Le pipeline de decision de Nextones Desk suit un flux sequentiel en quatre etapes : "
    "<b>Agents \u2192 Risk Check \u2192 Execution \u2192 IC Memo</b>. Chaque etape enrichit la precedente "
    "et peut bloquer le flux si les conditions de risque ne sont pas remplies.",
    body_style
))

story.append(Paragraph("2.1 Etape 1 — Cycle d'agents", h2_style))
story.append(Paragraph(
    "La fonction <font face='Courier' size=9>run_all_agents()</font> orchestre l'execution sequentielle "
    "des cinq agents. Chaque agent recoit les donnees de prix depuis SQLite, applique ses indicateurs "
    "proprietaires et produit une ou plusieurs theses structurees (texte, conviction, horizon, action proposee, drivers cles). "
    "Les theses sont persistees dans la table <font face='Courier' size=9>theses</font> avec un timestamp "
    "et un statut <font face='Courier' size=9>pending</font>.",
    body_style
))

story.append(Paragraph("2.2 Etape 2 — Risk Check", h2_style))
story.append(Paragraph(
    "Avant toute execution, le moteur de risque verifie systematiquement : "
    "la VaR 95% du portefeuille, les limites de position (20% max par instrument), "
    "les limites sectorielles (35% max), et le drawdown cumule (15% max). "
    "Si une these implique un trade qui violerait une contrainte, elle est marquee "
    "<font face='Courier' size=9>rejected</font> avec le motif de rejet.",
    body_style
))

story.append(Paragraph("2.3 Etape 3 — Execution", h2_style))
story.append(Paragraph(
    "Les theses approuvees par le risk check sont converties en ordres paper trading. "
    "Le moteur d'execution simule le fill au prix courant avec un slippage configurable, "
    "met a jour les positions et l'equity du portefeuille, puis journalise le fill dans la table "
    "<font face='Courier' size=9>fills</font>.",
    body_style
))

story.append(Paragraph("2.4 Etape 4 — IC Memo", h2_style))
story.append(Paragraph(
    "Un memo de comite d'investissement (IC Memo) est genere automatiquement a la fin du cycle. "
    "Il synthetise les theses du cycle, le regime macro, les positions prises, les verifications de risque, "
    "et les metriques de portefeuille. Le memo est exportable en PDF et Markdown depuis l'interface.",
    body_style
))

story.append(Spacer(1, 4*mm))

# Pipeline summary table
pipeline_headers = ["Etape", "Composant", "Entree", "Sortie", "Persistance"]
pipeline_rows = [
    ["1", "5 Agents IA", "Donnees OHLCV (SQLite)", "Theses + conviction", "Table theses"],
    ["2", "Risk Engine", "Theses pending", "Approved / Rejected", "Table events"],
    ["3", "Execution Engine", "Theses approved", "Orders + Fills", "Tables orders, fills"],
    ["4", "IC Memo Generator", "Theses + positions + risk", "Memo PDF/Markdown", "Table memos"],
]
story.append(make_data_table(pipeline_headers, pipeline_rows,
    col_widths=[14*mm, 28*mm, 38*mm, 38*mm, 30*mm]))
story.append(Paragraph("Tableau 1 — Pipeline de decision Nextones Desk", caption_style))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 3: MacroAgent
# ═══════════════════════════════════════════════════════

story.append(Paragraph("3. MacroAgent — Analyse macro-economique", h1_style))
story.append(hr())

macro_info = [
    ("Role", "Determine le regime macro global et le score de vulnerabilite economique"),
    ("Sources", "FRED API (Federal Reserve Economic Data) : Fed Funds Rate, CPI YoY, Unemployment, "
     "10Y-2Y Spread, VIX, GDP Growth"),
    ("Indicateurs", "Score de vulnerabilite composite (0-100), SMA 50/200 sur ETFs (SPY, QQQ, DIA), RSI(14), momentum 20j"),
    ("Sortie", "Stance macro (risk-on / risk-off / neutral) + score de vulnerabilite"),
    ("Horizon", "Moyen terme (medium) en tendance claire, court terme (short) en zone neutre"),
    ("Conviction", "Echelle 5-9 selon la force des signaux agreges"),
]
story.append(make_info_table(macro_info, header_color=AGENT_COLORS[0]))
story.append(Spacer(1, 4*mm))

story.append(Paragraph("3.1 Sources FRED API", h2_style))
story.append(Paragraph(
    "Le MacroAgent integre les donnees de la Federal Reserve via l'API FRED pour construire "
    "un <b>tableau de bord de vulnerabilite</b> macro-economique. Les indicateurs suivis sont :",
    body_style
))

fred_indicators = [
    "<b>Fed Funds Rate (FEDFUNDS)</b> : Taux directeur de la Fed. Un niveau eleve (>5%) indique une politique restrictive.",
    "<b>CPI Year-over-Year (CPIAUCSL)</b> : Inflation annuelle. Au-dessus de 3%, contribue a un score de vulnerabilite eleve.",
    "<b>Unemployment Rate (UNRATE)</b> : Taux de chomage. Au-dessus de 5%, signal de faiblesse economique.",
    "<b>10Y-2Y Treasury Spread (T10Y2Y)</b> : Courbe des taux. Une inversion (spread negatif) est un precurseur historique de recession.",
    "<b>VIX (VIXCLS)</b> : Indice de volatilite. Au-dessus de 25, signal de stress sur les marches.",
    "<b>GDP Growth (A191RL1Q225SBEA)</b> : Croissance du PIB trimestrielle. Sous 1%, signal de ralentissement.",
]
for item in fred_indicators:
    story.append(bullet(item))

story.append(Paragraph("3.2 Scoring de vulnerabilite", h2_style))
story.append(Paragraph(
    "Chaque indicateur FRED est mappe sur une echelle 0-100 selon des seuils pre-definis. "
    "Le score composite est la moyenne ponderee de ces sous-scores. Un score > 60 correspond "
    "a un regime <b>risk-off</b> (prudence), un score < 40 a un regime <b>risk-on</b> (confiance), "
    "et entre 40-60 a un regime <b>neutral</b>. Le score est affiche dans le dashboard Macro US.",
    body_style
))

story.append(Paragraph("3.3 Analyse technique ETFs", h2_style))
story.append(Paragraph(
    "En complement du scoring FRED, le MacroAgent analyse trois ETFs de reference (SPY, QQQ, DIA) "
    "avec les indicateurs techniques classiques :",
    body_style
))

macro_tech = [
    "<b>Golden/Death Cross</b> : SMA50 vs SMA200. Vote majoritaire (2/3) determine la tendance.",
    "<b>RSI(14)</b> : Filtre surachat (>65) / survente (<35). Tempere la conviction haussiere.",
    "<b>Momentum 20 jours</b> : Rendement moyen sur 20j des 3 ETFs. Quantifie la force de tendance.",
    "<b>Volatilite annualisee</b> : Calculee sur 20j, annualisee (x racine de 252). Regime de vol actuel.",
]
for item in macro_tech:
    story.append(bullet(item))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 4: FactorAgent
# ═══════════════════════════════════════════════════════

story.append(Paragraph("4. FactorAgent — Analyse factorielle", h1_style))
story.append(hr())

factor_info = [
    ("Role", "Classement relatif des actions par exposition factorielle composite"),
    ("Perimetre", "Tous les instruments de classe 'equity' (exclut ETFs de reference et crypto)"),
    ("Facteurs", "Momentum 12-1 mois (50%), Qualite/inverse vol (30%), RSI contrariant (20%)"),
    ("Score", "Composite 0-10 : >= 7 overweight, <= 3 underweight, entre 3-7 neutral"),
    ("Horizon", "Moyen terme (medium)"),
    ("Sortie", "Liste triee des actions avec tilt (overweight / neutral / underweight)"),
]
story.append(make_info_table(factor_info, header_color=AGENT_COLORS[1]))
story.append(Spacer(1, 4*mm))

story.append(Paragraph("4.1 Signaux momentum / value / quality", h2_style))

story.append(Paragraph(
    "Le FactorAgent s'appuie sur le <b>factor investing</b>, valide par la recherche academique "
    "(Fama-French, Carhart). Il decompose l'attractivite de chaque action en trois facteurs mesurables :",
    body_style
))

factor_details = [
    "<b>Momentum (poids 50%)</b> : Rendement sur 12 mois excluant le dernier mois (convention \"12-1\" "
    "pour eviter l'effet de reversal a court terme). Mappe lineairement de [-30%, +30%] vers [0, 10]. "
    "Le poids dominant reflete la persistance historique du momentum comme source d'alpha.",
    "<b>Qualite (poids 30%)</b> : En l'absence de donnees fondamentales (ROE, marges), la volatilite "
    "annualisee sur 20 jours sert de proxy inverse : faible volatilite = meilleure \"qualite\". "
    "Score = 10 - (volatilite x 20), borne entre 0 et 10.",
    "<b>RSI inverse (poids 20%)</b> : Complement du RSI(14) normalise (10 - RSI/10). Penalise les "
    "actions en zone de surachat et favorise celles en zone de survente, ajoutant un element contrariant.",
]
for item in factor_details:
    story.append(bullet(item))

story.append(Spacer(1, 3*mm))
story.append(Paragraph(
    "<b>Classification :</b> Score composite >= 7 \u2192 overweight (surponderer). Score <= 3 \u2192 underweight "
    "(sous-ponderer). Entre 3 et 7 \u2192 neutral. La conviction est proportionnelle a l'ecart du score "
    "par rapport a 5 (le centre neutre), variant de 4 a 9.",
    body_style
))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 5: MicrostructureAgent
# ═══════════════════════════════════════════════════════

story.append(Paragraph("5. MicrostructureAgent — Microstructure de marche", h1_style))
story.append(hr())

micro_info = [
    ("Role", "Analyse technique fine : timing d'entree/sortie, stop loss dynamique, niveaux S/R"),
    ("Sources", "Finviz (stock signals, analyst ratings, target prices, sector performance)"),
    ("Indicateurs", "Bollinger Bands (20p, 2 sigma), RSI(14), SMA crossovers, ratio volume 5j/20j, ATR(14), S/R 10j"),
    ("Signaux", "buy/add, sell/take_profit, accumulate, reduce, hold"),
    ("Horizon", "Court terme (short) pour signaux forts, moyen terme (medium) sinon"),
    ("Sortie", "Signal de trading par instrument avec stop ATR(14) x2"),
]
story.append(make_info_table(micro_info, header_color=AGENT_COLORS[2]))
story.append(Spacer(1, 4*mm))

story.append(Paragraph("5.1 Finviz Data Integration", h2_style))
story.append(Paragraph(
    "Le MicrostructureAgent enrichit son analyse technique avec des donnees issues de <b>Finviz</b> : "
    "signaux stock screener (oversold, overbought, top gainers/losers), analyst ratings et target prices, "
    "performance sectorielle, et RSI pre-calcule. Ces donnees sont ingerees via le pipeline Finviz "
    "et stockees dans la table <font face='Courier' size=9>finviz_signals</font>.",
    body_style
))

story.append(Paragraph("5.2 RSI, SMA crossovers, Bollinger Bands", h2_style))

micro_details = [
    "<b>Bandes de Bollinger (20p, 2 sigma)</b> : Le prix est positionne en percentile dans la bande "
    "(0% = bande inf., 100% = bande sup.). Percentile > 95% + volume eleve = exces haussier. "
    "Percentile < 5% + volume faible = capitulation (signal d'achat).",
    "<b>RSI(14)</b> : Surachat > 70 declenche 'reduce', survente < 30 declenche 'accumulate'. "
    "Filtre secondaire apres les signaux Bollinger.",
    "<b>SMA crossovers</b> : Croisements SMA courtes (10/20) confirment les changements de tendance intraday.",
    "<b>Ratio volume (5j/20j)</b> : > 1.2x = participation elevee (confirmation). < 0.9x = essoufflement.",
    "<b>ATR(14)</b> : Average True Range pour calibrer le stop loss a 2x ATR sous le prix courant.",
    "<b>Support/Resistance 10j</b> : Extremes des 10 derniers jours comme bornes techniques immediates.",
    "<b>Analyst Ratings (Finviz)</b> : Consensus des analystes (Strong Buy/Buy/Hold/Sell) comme filtre supplementaire de validation.",
]
for item in micro_details:
    story.append(bullet(item))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 6: CryptoAgent
# ═══════════════════════════════════════════════════════

story.append(Paragraph("6. CryptoAgent — Analyse crypto-actifs", h1_style))
story.append(hr())

crypto_info = [
    ("Role", "Analyse specialisee des crypto-actifs avec indicateurs adaptes a leur volatilite"),
    ("Sources", "CoinGecko API — TOP 25 cryptomonnaies par capitalisation"),
    ("Perimetre", "BTC, ETH, LINK et TOP 25 CoinGecko (prix, market cap, volume 24h, variation)"),
    ("Indicateurs", "SMA 7/21, RSI(14) seuils 75/25, momentum 7j, vol annualisee, Bollinger 20p, ratio vol 5j/20j"),
    ("Score", "Composite 0-10 : momentum 35%, tendance 30%, RSI 20%, volume 15%"),
    ("Signaux", "strong_buy, buy, sell, take_profit, accumulate, hold"),
    ("Sortie", "Signal par crypto avec score composite + stop ATR x2.5"),
]
story.append(make_info_table(crypto_info, header_color=AGENT_COLORS[4]))
story.append(Spacer(1, 4*mm))

story.append(Paragraph("6.1 TOP 25 CoinGecko", h2_style))
story.append(Paragraph(
    "Le CryptoAgent s'appuie sur les donnees <b>CoinGecko</b> pour le suivi en temps reel des 25 "
    "principales cryptomonnaies par capitalisation boursiere. Le pipeline d'ingestion recupere : "
    "prix courant, market cap, volume 24h, variation 24h, et rang. Ces donnees alimentent le "
    "tableau <b>Crypto TOP 25</b> du Market Intel et sont stockees dans la table "
    "<font face='Courier' size=9>crypto_prices</font>.",
    body_style
))

story.append(Paragraph("6.2 Analyse technique adaptee", h2_style))
story.append(Paragraph(
    "Les indicateurs du CryptoAgent sont specifiquement calibres pour la volatilite crypto :",
    body_style
))

crypto_diffs = [
    "<b>SMA 7/21 (vs 50/200 equity)</b> : Periodes courtes adaptees aux cycles crypto rapides.",
    "<b>Momentum 7 jours, plage [-50%, +50%]</b> : Amplitude elargie vs [-30%, +30%] pour les actions.",
    "<b>RSI seuils 75/25 (vs 70/30)</b> : Les cryptos restent en conditions extremes plus longtemps.",
    "<b>Volatilite : haute > 80%, basse < 40%</b> : Seuils adaptes (vs ~25% pour equities).",
    "<b>Stop ATR x2.5 (vs x2 equity)</b> : Plus large pour absorber le bruit intraday crypto.",
]
for item in crypto_diffs:
    story.append(bullet(item))

story.append(Paragraph("6.3 Theses crypto", h2_style))
story.append(Paragraph(
    "Le CryptoAgent genere des theses d'investissement specifiques a chaque crypto-actif, "
    "integrant le score composite, la tendance SMA, le regime de volatilite, et les niveaux de stop. "
    "Les theses sont enrichies par les donnees CoinGecko (market cap, dominance BTC, volume global) "
    "pour contextualiser la recommandation dans l'etat general du marche crypto.",
    body_style
))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 7: AltDataAgent
# ═══════════════════════════════════════════════════════

story.append(Paragraph("7. AltDataAgent — Donnees alternatives", h1_style))
story.append(hr())

alt_info = [
    ("Role", "Detection d'anomalies, signaux geopolitiques et analyse de sentiment proxy"),
    ("Sources", "GDELT GKG API (evenements geopolitiques), USGS Earthquakes (risques naturels), donnees prix-volume"),
    ("Indicateurs", "Divergence prix-volume (5j), consistance tendance (SMA20), z-score rendements, score geopolitique"),
    ("Sentiments", "strong_bullish, weak_bullish, capitulation, weak_bearish, neutral"),
    ("Horizon", "Court terme pour signaux forts, moyen terme sinon"),
    ("Sortie", "Sentiment par action avec conviction ajustee + alertes geopolitiques"),
]
story.append(make_info_table(alt_info, header_color=AGENT_COLORS[3]))
story.append(Spacer(1, 4*mm))

story.append(Paragraph("7.1 Signaux geopolitiques (GDELT, USGS)", h2_style))
story.append(Paragraph(
    "L'AltDataAgent integre des <b>sources de donnees alternatives</b> pour detecter les risques "
    "geopolitiques et naturels pouvant impacter les marches. Les deux sources principales sont :",
    body_style
))

alt_geo = [
    "<b>GDELT GKG API</b> : Analyse en temps reel de la couverture mediatique mondiale. "
    "L'agent extrait le tone moyen (sentiment) et le volume d'articles sur les themes de risque "
    "(conflits, sanctions, instabilite politique). Un tone negatif eleve correle avec des periodes de stress.",
    "<b>USGS Earthquakes API</b> : Suivi des seismes majeurs (magnitude > 5.0) pouvant impacter "
    "les chokepoints logistiques (Detroit d'Hormuz, Canal de Suez, Panama) ou les zones de production industrielle.",
]
for item in alt_geo:
    story.append(bullet(item))

story.append(Paragraph("7.2 Analyse prix-volume", h2_style))

alt_details = [
    "<b>Divergence prix-volume</b> : Croisement variation prix 5j / variation volume 5j. "
    "Quatre regimes : (1) hausse prix + hausse vol = rally sain, (2) hausse prix + baisse vol = distribution, "
    "(3) baisse prix + hausse vol = capitulation, (4) baisse prix + baisse vol = tendance molle.",
    "<b>Consistance de tendance</b> : Ratio jours au-dessus de SMA20 sur les 10 derniers jours. "
    "> 60% renforce un signal haussier. Ajuste la conviction dynamiquement.",
    "<b>Detection d'anomalies (z-score)</b> : Rendement normalise par moyenne et ecart-type recents. "
    "z-score > 2 ou < -2 = mouvement inhabituel (potentiel evenement).",
]
for item in alt_details:
    story.append(bullet(item))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 8: Moteur de risque
# ═══════════════════════════════════════════════════════

story.append(Paragraph("8. Moteur de risque", h1_style))
story.append(hr())

story.append(Paragraph(
    "Le moteur de risque est le <b>gardien du portefeuille</b>. Il intervient systematiquement avant "
    "toute execution d'ordre pour verifier que le trade propose ne viole aucune contrainte de risque. "
    "Sa configuration est modifiable par les administrateurs via l'endpoint "
    "<font face='Courier' size=9>PUT /api/risk-config</font>.",
    body_style
))

story.append(Paragraph("8.1 VaR 95%", h2_style))
story.append(Paragraph(
    "La Value-at-Risk a 95% est calculee par la methode historique sur les 60 derniers jours "
    "de rendements du portefeuille. Elle represente la perte maximale attendue sur un jour avec "
    "95% de confiance. Si l'ajout d'une position fait depasser le seuil VaR configure, le trade est rejete.",
    body_style
))

story.append(Paragraph("8.2 Limites de position et secteur", h2_style))

risk_params = [
    "<b>Limite de position (20%)</b> : Aucun instrument ne peut representer plus de 20% de la valeur "
    "totale du portefeuille. Empeche la concentration excessive sur un seul actif.",
    "<b>Limite sectorielle (35%)</b> : Aucun secteur ne peut representer plus de 35% du portefeuille. "
    "Assure la diversification sectorielle minimale.",
    "<b>Drawdown max (15%)</b> : Si le drawdown cumule depuis le dernier pic depasse 15%, "
    "tout nouvel achat est bloque. Seules les ventes de reduction d'exposition sont autorisees.",
]
for item in risk_params:
    story.append(bullet(item))

story.append(Paragraph("8.3 Drawdown monitoring", h2_style))
story.append(Paragraph(
    "Le monitoring de drawdown est continu : a chaque mise a jour des prix, le systeme recalcule "
    "le peak-to-trough du portefeuille. Trois seuils de severite sont definis : "
    "<b>warning (10%)</b> journalise un evenement d'alerte, "
    "<b>critical (12.5%)</b> bloque les nouvelles positions longues, "
    "<b>halt (15%)</b> bloque toute execution et genere une alerte IC Memo urgente.",
    body_style
))

story.append(Spacer(1, 4*mm))

# Risk parameters table
risk_headers = ["Parametre", "Valeur", "Type", "Description"]
risk_rows = [
    ["VaR Seuil", "2.5%", "Pre-trade", "Perte max journaliere a 95% de confiance"],
    ["Position Max", "20%", "Pre-trade", "Poids max d'un instrument dans le portefeuille"],
    ["Secteur Max", "35%", "Pre-trade", "Poids max d'un secteur dans le portefeuille"],
    ["Drawdown Warning", "10%", "Monitoring", "Alerte journalisee dans events"],
    ["Drawdown Critical", "12.5%", "Monitoring", "Blocage nouvelles positions longues"],
    ["Drawdown Halt", "15%", "Monitoring", "Blocage total d'execution"],
    ["Lookback VaR", "60 jours", "Calcul", "Fenetre historique pour VaR"],
]
story.append(make_data_table(risk_headers, risk_rows,
    col_widths=[32*mm, 18*mm, 22*mm, 78*mm]))
story.append(Paragraph("Tableau 2 — Parametres du moteur de risque", caption_style))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 9: Moteur d'execution
# ═══════════════════════════════════════════════════════

story.append(Paragraph("9. Moteur d'execution", h1_style))
story.append(hr())

story.append(Paragraph(
    "Le moteur d'execution gere le <b>paper trading</b> : simulation realiste du cycle de vie "
    "d'un ordre, de la soumission au fill, avec prise en compte du slippage et du prix de marche courant.",
    body_style
))

story.append(Paragraph("9.1 Paper trading", h2_style))
story.append(Paragraph(
    "Nextones Desk fonctionne exclusivement en mode <b>paper trading</b> (simulation). Aucun ordre "
    "n'est envoye a un broker reel. Le portefeuille demarre avec un capital fictif configurable "
    "(par defaut 1 000 000 USD) et evolue selon les fills simules. Ce mode permet de valider la "
    "strategie sans risque financier reel.",
    body_style
))

story.append(Paragraph("9.2 Order flow et fills", h2_style))

exec_flow = [
    "<b>Soumission</b> : Un ordre est cree avec ticker, side (buy/sell), quantite, et prix limite optionnel. "
    "Statut initial : <font face='Courier' size=9>pending</font>.",
    "<b>Risk Check</b> : Le moteur de risque verifie les contraintes. Si violation, l'ordre passe en "
    "<font face='Courier' size=9>rejected</font> avec motif.",
    "<b>Fill Simulation</b> : L'ordre approuve est rempli au prix courant +/- slippage. "
    "Statut : <font face='Courier' size=9>filled</font>. Un enregistrement fill est cree.",
    "<b>Position Update</b> : La position sur l'instrument est mise a jour (quantite, prix moyen, P&amp;L). "
    "Le cash du portefeuille est ajuste.",
    "<b>Event Logging</b> : Un evenement <font face='Courier' size=9>order_filled</font> est journalise "
    "avec tous les details du trade.",
]
for item in exec_flow:
    story.append(bullet(item))

story.append(Paragraph("9.3 Slippage simulation", h2_style))
story.append(Paragraph(
    "Le slippage est simule avec un modele simple : le prix d'execution est ajuste de +/- 0.05% "
    "par rapport au prix de marche pour les ordres market. Pour les ordres limites, le fill n'intervient "
    "que si le prix de marche atteint la limite. Ce modele realiste permet de mesurer l'impact "
    "du slippage sur la performance globale du portefeuille.",
    body_style
))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 10: Backtest Engine (NEW)
# ═══════════════════════════════════════════════════════

story.append(Paragraph("10. Backtest Engine", h1_style))
story.append(hr())

story.append(Paragraph(
    "Le moteur de backtesting permet de tester des strategies d'allocation sur des donnees historiques "
    "reelles issues de <b>Yahoo Finance</b>. Il genere une courbe d'equity, des statistiques de "
    "performance, et un journal de trading exportable en CSV.",
    body_style
))

story.append(Paragraph("10.1 Yahoo Finance data", h2_style))
story.append(Paragraph(
    "Les donnees historiques sont recuperees via la librairie <font face='Courier' size=9>yfinance</font> "
    "pour chaque ticker du portefeuille de backtest. Les prix OHLCV ajustes (splits, dividendes) "
    "sont telecharges sur la periode demandee (par defaut : 1 an). La frequence est journaliere.",
    body_style
))

story.append(Paragraph("10.2 Ponderations : equal / custom weight", h2_style))
story.append(Paragraph(
    "Deux modes de ponderation sont disponibles :",
    body_style
))

bt_weights = [
    "<b>Equal Weight</b> : Le capital est reparti equitablement entre tous les tickers selectionnes. "
    "Mode par defaut, ideal pour evaluer la contribution relative de chaque actif.",
    "<b>Custom Weight</b> : L'utilisateur definit manuellement le poids de chaque ticker "
    "(somme = 100%). Permet de tester des allocations specifiques issues des theses des agents.",
]
for item in bt_weights:
    story.append(bullet(item))

story.append(Paragraph("10.3 Stats computation", h2_style))

bt_stats = [
    "<b>Rendement total (%)</b> : Performance cumulative du portefeuille sur la periode.",
    "<b>Rendement annualise (%)</b> : Rendement total ramene sur une base annuelle (252 jours de trading).",
    "<b>Volatilite annualisee (%)</b> : Ecart-type des rendements journaliers x racine de 252.",
    "<b>Ratio de Sharpe</b> : (Rendement annualise - Taux sans risque) / Volatilite. Taux sans risque par defaut : 4%.",
    "<b>Max Drawdown (%)</b> : Perte maximale peak-to-trough sur la periode.",
    "<b>Comparaison benchmark</b> : Les memes statistiques sont calculees pour un benchmark (SPY par defaut) "
    "et affichees cote a cote pour evaluation relative.",
]
for item in bt_stats:
    story.append(bullet(item))

story.append(Paragraph("10.4 Export CSV du journal de trading", h2_style))
story.append(Paragraph(
    "Le journal de trading est exportable en CSV depuis le bouton <b>\"Exporter CSV\"</b> dans les "
    "resultats du backtest. La generation s'effectue cote client (Blob download) avec un fallback "
    "serveur via <font face='Courier' size=9>POST /api/backtest/export-csv</font>.",
    body_style
))

csv_headers = ["Colonne", "Description", "Exemple"]
csv_rows = [
    ["Date", "Date du jour de trading", "2025-12-15"],
    ["Ticker", "Symbole de l'instrument", "AAPL"],
    ["Poids (%)", "Ponderation dans le portefeuille", "10.00"],
    ["Prix", "Prix de cloture ajuste", "198.50"],
    ["Rendement Jour (%)", "Variation journaliere", "+1.23"],
    ["Rendement Cumul (%)", "Performance cumulee depuis le debut", "+15.40"],
    ["Valeur Position", "Valeur en USD de la position", "19 850.00"],
]
story.append(make_data_table(csv_headers, csv_rows,
    col_widths=[35*mm, 70*mm, 45*mm]))
story.append(Paragraph("Tableau 3 — Colonnes du CSV de backtest", caption_style))

story.append(Paragraph(
    "Le fichier utilise le <b>separateur point-virgule (;)</b> pour compatibilite avec Excel en francais, "
    "et inclut un BOM UTF-8 pour le bon rendu des caracteres accentues. Une section de synthese "
    "avec les statistiques du portefeuille est ajoutee en fin de fichier.",
    body_style
))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 11: Authentification et RBAC (NEW)
# ═══════════════════════════════════════════════════════

story.append(Paragraph("11. Systeme d'authentification et RBAC", h1_style))
story.append(hr())

story.append(Paragraph(
    "Nextones Desk implemente un systeme d'authentification complet base sur <b>JWT</b> (JSON Web Tokens) "
    "avec hachage des mots de passe par <b>bcrypt</b> et un controle d'acces base sur les roles (RBAC).",
    body_style
))

story.append(Paragraph("11.1 JWT et bcrypt", h2_style))

auth_details = [
    "<b>JWT Tokens</b> : Chaque connexion reussie genere un token JWT signe (algorithme HS256) avec une "
    "duree de validite de 24 heures. Le token contient le username, le role et l'heure d'expiration.",
    "<b>bcrypt Password Hashing</b> : Les mots de passe sont haches avec bcrypt (librairie passlib, "
    "version bcrypt 4.0.1) avant stockage en base. Le salt est genere automatiquement. "
    "Aucun mot de passe en clair n'est stocke.",
    "<b>Middleware d'authentification</b> : Chaque requete API protegee passe par un middleware qui "
    "extrait le token du header Authorization (Bearer scheme), le verifie et injecte l'utilisateur "
    "courant dans le contexte de la requete.",
]
for item in auth_details:
    story.append(bullet(item))

story.append(Paragraph("11.2 Les 4 roles", h2_style))

role_headers = ["Role", "Niveau", "Permissions", "Acces typique"]
role_rows = [
    ["Viewer", "0", "Lecture seule", "Dashboards, rapports, consultation des theses"],
    ["Analyst", "1", "Viewer + propositions", "Proposer des theses, lancer des backtests, exporter CSV"],
    ["Manager", "2", "Analyst + validation", "Valider les theses, lancer cycles d'execution et d'ingestion"],
    ["Admin", "3", "Acces total", "Gestion utilisateurs, configuration du risk engine, acces complet"],
]
story.append(make_data_table(role_headers, role_rows,
    col_widths=[22*mm, 18*mm, 50*mm, 60*mm]))
story.append(Paragraph("Tableau 4 — Roles et permissions RBAC", caption_style))

story.append(Paragraph("11.3 Middleware require_role", h2_style))
story.append(Paragraph(
    "Le decorateur <font face='Courier' size=9>require_role(min_level)</font> protege les endpoints "
    "en verifiant que le role de l'utilisateur authentifie a un niveau >= au niveau requis. "
    "La hierarchie est lineaire : Viewer (0) < Analyst (1) < Manager (2) < Admin (3). "
    "Un Manager peut acceder a tout ce qu'un Analyst peut faire, et ainsi de suite.",
    body_style
))

story.append(Paragraph("11.4 Hierarchie et endpoints proteges", h2_style))

protected_headers = ["Endpoint", "Methode", "Role min.", "Description"]
protected_rows = [
    ["/api/orders/execute-cycle", "POST", "Manager", "Lancer un cycle d'execution complet"],
    ["/api/run-agents", "POST", "Manager", "Lancer le cycle des 5 agents"],
    ["/api/run-ingestion", "POST", "Manager", "Declencher l'ingestion de donnees"],
    ["/api/risk-config", "PUT", "Admin", "Modifier la configuration du risk engine"],
    ["/api/admin/*", "ALL", "Admin", "Administration des utilisateurs"],
    ["/api/backtest", "POST", "Analyst", "Lancer un backtest"],
    ["/api/theses", "GET", "Viewer", "Consulter les theses (lecture seule)"],
]
story.append(make_data_table(protected_headers, protected_rows,
    col_widths=[45*mm, 18*mm, 22*mm, 65*mm]))
story.append(Paragraph("Tableau 5 — Endpoints proteges par role", caption_style))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 12: Risque geopolitique (NEW)
# ═══════════════════════════════════════════════════════

story.append(Paragraph("12. Risque geopolitique", h1_style))
story.append(hr())

story.append(Paragraph(
    "Le module de risque geopolitique integre des sources de donnees en temps reel pour detecter "
    "et scorer les evenements mondiaux pouvant impacter les marches financiers. Il est affiche "
    "dans l'onglet <b>Macro US</b> du dashboard.",
    body_style
))

story.append(Paragraph("12.1 GDELT GKG API", h2_style))
story.append(Paragraph(
    "Le <b>GDELT Global Knowledge Graph</b> (GKG) est une base de donnees ouverte indexant "
    "la couverture mediatique mondiale en temps reel. Nextones Desk interroge l'API GKG pour "
    "extraire le <b>tone moyen</b> (sentiment positif/negatif) et le <b>volume d'articles</b> "
    "sur les themes de risque geopolitique (conflits armes, sanctions economiques, instabilite politique, "
    "crises energetiques).",
    body_style
))

story.append(Paragraph("12.2 USGS Earthquakes API", h2_style))
story.append(Paragraph(
    "L'API <b>USGS Earthquake Hazards</b> fournit les donnees sismiques en temps reel a l'echelle mondiale. "
    "Le systeme filtre les seismes de magnitude > 5.0 et evalue leur proximite avec les "
    "<b>chokepoints logistiques</b> critiques et les zones industrielles majeures.",
    body_style
))

story.append(Paragraph("12.3 Composite score et chokepoints", h2_style))
story.append(Paragraph(
    "Un score composite de risque geopolitique (0-100) est calcule a partir de trois composantes :",
    body_style
))

geo_score = [
    "<b>GDELT Tone Score (40%)</b> : Tone moyen normalise des articles recents. Tone negatif eleve = risque.",
    "<b>GDELT Volume Score (30%)</b> : Volume d'articles sur les themes de risque, normalise par la moyenne mobile 30j.",
    "<b>USGS Seismic Score (30%)</b> : Nombre et magnitude des seismes recents pres des chokepoints.",
]
for item in geo_score:
    story.append(bullet(item))

story.append(Spacer(1, 3*mm))

# Chokepoints table
choke_headers = ["Chokepoint", "Localisation", "Impact marche", "Rayon surveillance"]
choke_rows = [
    ["Detroit d'Hormuz", "26.5N, 56.2E", "Petrole, gaz (20% trafic mondial)", "500 km"],
    ["Canal de Suez", "30.5N, 32.3E", "Commerce mondial (12% du trafic)", "300 km"],
    ["Canal de Panama", "9.0N, 79.7W", "Commerce Ameriques-Asie", "200 km"],
    ["Detroit de Malacca", "2.5N, 101.0E", "Commerce Asie (25% trafic maritime)", "400 km"],
    ["Bosphore", "41.0N, 29.0E", "Petrole russe, cereales Ukraine", "200 km"],
]
story.append(make_data_table(choke_headers, choke_rows,
    col_widths=[35*mm, 28*mm, 52*mm, 35*mm]))
story.append(Paragraph("Tableau 6 — Chokepoints logistiques surveilles", caption_style))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 13: Ingestion des donnees
# ═══════════════════════════════════════════════════════

story.append(Paragraph("13. Ingestion des donnees", h1_style))
story.append(hr())

story.append(Paragraph(
    "La couche d'ingestion centralise la collecte de donnees depuis cinq sources externes. "
    "Chaque pipeline est independant et peut etre declenche individuellement ou globalement "
    "via <font face='Courier' size=9>POST /api/run-ingestion</font> (role Manager+).",
    body_style
))

story.append(Paragraph("13.1 Yahoo Finance", h2_style))
story.append(Paragraph(
    "La librairie <font face='Courier' size=9>yfinance</font> est utilisee pour recuperer les prix "
    "OHLCV historiques et en temps reel de tous les instruments equity et ETF. Les donnees sont "
    "stockees dans la table <font face='Courier' size=9>prices</font> avec deduplication sur "
    "(ticker, date). Le pipeline gere les splits et dividendes via les prix ajustes.",
    body_style
))

story.append(Paragraph("13.2 CoinGecko", h2_style))
story.append(Paragraph(
    "L'API CoinGecko (gratuite, sans cle) fournit les donnees des TOP 25 crypto par market cap : "
    "prix courant (USD), market cap, volume 24h, variation 24h et 7j, et rang. Les donnees alimentent "
    "la table <font face='Courier' size=9>crypto_prices</font> et le tableau Crypto TOP 25 du Market Intel.",
    body_style
))

story.append(Paragraph("13.3 FRED API", h2_style))
story.append(Paragraph(
    "La Federal Reserve Economic Data (FRED) fournit les series macro-economiques via une API REST "
    "avec cle d'authentification. Les series suivies : FEDFUNDS, CPIAUCSL, UNRATE, T10Y2Y, VIXCLS, "
    "A191RL1Q225SBEA. Les donnees sont stockees dans la table <font face='Courier' size=9>macro_data</font>.",
    body_style
))

story.append(Paragraph("13.4 Finviz", h2_style))
story.append(Paragraph(
    "Le pipeline Finviz collecte les signaux stock screener (oversold, overbought, new highs/lows), "
    "les analyst ratings (consensus, target price), et la performance sectorielle. Les donnees sont "
    "stockees dans <font face='Courier' size=9>finviz_signals</font> et "
    "<font face='Courier' size=9>sector_performance</font>.",
    body_style
))

story.append(Paragraph("13.5 GDELT + USGS", h2_style))
story.append(Paragraph(
    "Les pipelines geopolitiques interrogent l'API GDELT GKG (tone et volume d'articles) et "
    "l'API USGS Earthquake Hazards (seismes > 5.0 magnitude). Les resultats sont agreges en "
    "un score composite stocke dans <font face='Courier' size=9>geopolitical_risk</font>.",
    body_style
))

story.append(Spacer(1, 4*mm))

# Ingestion summary table
ingest_headers = ["Source", "API / Librairie", "Frequence", "Table(s) SQLite", "Auth"]
ingest_rows = [
    ["Yahoo Finance", "yfinance (Python)", "Quotidien", "prices", "Aucune"],
    ["CoinGecko", "REST API", "Toutes les 15 min", "crypto_prices", "Aucune"],
    ["FRED", "REST API", "Quotidien", "macro_data", "API Key"],
    ["Finviz", "Web + REST", "Quotidien", "finviz_signals, sector_perf", "Aucune"],
    ["GDELT", "REST API (GKG)", "Toutes les heures", "geopolitical_risk", "Aucune"],
    ["USGS", "REST API", "Toutes les heures", "geopolitical_risk", "Aucune"],
]
story.append(make_data_table(ingest_headers, ingest_rows,
    col_widths=[28*mm, 32*mm, 30*mm, 38*mm, 22*mm]))
story.append(Paragraph("Tableau 7 — Sources de donnees et pipelines d'ingestion", caption_style))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 14: Base de donnees
# ═══════════════════════════════════════════════════════

story.append(Paragraph("14. Base de donnees", h1_style))
story.append(hr())

story.append(Paragraph(
    "Nextones Desk utilise <b>SQLite</b> comme base de donnees unique (fichier "
    "<font face='Courier' size=9>nextones.db</font>). Le schema comprend les tables suivantes, "
    "couvrant toutes les entites du systeme.",
    body_style
))

story.append(Paragraph("14.1 Schema principal", h2_style))

db_headers = ["Table", "Description", "Colonnes principales", "Relations"]
db_rows = [
    ["instruments", "Catalogue des actifs suivis", "ticker, name, asset_class, sector, is_active", "FK vers prices, theses"],
    ["prices", "Prix OHLCV historiques", "ticker, date, open, high, low, close, volume", "FK instruments.ticker"],
    ["theses", "Theses d'investissement des agents", "id, ticker, agent, text, conviction, status, horizon, action", "FK instruments.ticker"],
    ["orders", "Ordres de paper trading", "id, ticker, side, qty, price, status, created_at", "FK instruments.ticker"],
    ["fills", "Executions (fills) des ordres", "id, order_id, fill_price, qty, slippage, filled_at", "FK orders.id"],
    ["positions", "Positions courantes", "ticker, qty, avg_price, current_value, pnl", "FK instruments.ticker"],
    ["events", "Journal d'evenements systeme", "id, type, payload, timestamp", "—"],
    ["users", "Utilisateurs et credentials", "id, username, email, hashed_pw, role, is_active", "—"],
    ["risk_config", "Configuration du risk engine", "key, value, updated_at, updated_by", "FK users.id"],
    ["crypto_prices", "Prix crypto (CoinGecko)", "coin_id, price_usd, market_cap, vol_24h, rank", "—"],
    ["macro_data", "Series macro (FRED)", "series_id, date, value", "—"],
    ["finviz_signals", "Signaux Finviz", "ticker, signal_type, analyst_rating, target_price", "FK instruments.ticker"],
    ["geopolitical_risk", "Score risque geopolitique", "date, gdelt_tone, gdelt_volume, usgs_score, composite", "—"],
    ["memos", "IC Memos generes", "id, content, format, created_at, cycle_id", "—"],
]
story.append(make_data_table(db_headers, db_rows,
    col_widths=[30*mm, 32*mm, 48*mm, 40*mm]))
story.append(Paragraph("Tableau 8 — Schema de la base de donnees SQLite", caption_style))

story.append(Paragraph("14.2 Conventions de nommage", h2_style))

naming_items = [
    "<b>Tables</b> : snake_case pluriel (instruments, prices, theses).",
    "<b>Colonnes</b> : snake_case (created_at, asset_class, hashed_pw).",
    "<b>Cles primaires</b> : 'id' INTEGER AUTOINCREMENT pour les tables a identifiant unique, "
    "ou cle composite (ticker, date) pour les tables de donnees temporelles.",
    "<b>Foreign keys</b> : Nommees selon la convention table_colonne (instruments.ticker, orders.id).",
    "<b>Timestamps</b> : Format ISO 8601 (YYYY-MM-DDTHH:MM:SS) stocke en TEXT.",
    "<b>Statuts</b> : Chaines descriptives (pending, approved, rejected, filled, active, inactive).",
]
for item in naming_items:
    story.append(bullet(item))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 15: API Reference
# ═══════════════════════════════════════════════════════

story.append(Paragraph("15. API Reference", h1_style))
story.append(hr())

story.append(Paragraph(
    "L'API REST de Nextones Desk est exposee sur le port 8000 via FastAPI. "
    "Tous les endpoints retournent du JSON. L'authentification est requise pour la plupart des endpoints "
    "via un header <font face='Courier' size=9>Authorization: Bearer &lt;token&gt;</font>.",
    body_style
))

story.append(Paragraph("15.1 Authentification", h2_style))

api_auth_headers = ["Endpoint", "Methode", "Auth", "Description"]
api_auth_rows = [
    ["/api/auth/login", "POST", "Non", "Connexion — retourne JWT token (24h)"],
    ["/api/auth/me", "GET", "Oui", "Profil de l'utilisateur connecte"],
    ["/api/auth/change-password", "POST", "Oui", "Changement de mot de passe"],
]
story.append(make_data_table(api_auth_headers, api_auth_rows,
    col_widths=[45*mm, 18*mm, 14*mm, 73*mm]))
story.append(Spacer(1, 3*mm))

story.append(Paragraph("15.2 Agents et Theses", h2_style))

api_agents_headers = ["Endpoint", "Methode", "Auth", "Role min.", "Description"]
api_agents_rows = [
    ["/api/run-agents", "POST", "Oui", "Manager", "Lancer le cycle complet des 5 agents"],
    ["/api/theses", "GET", "Oui", "Viewer", "Liste des theses (filtre par agent, status)"],
    ["/api/theses/{id}", "GET", "Oui", "Viewer", "Detail d'une these"],
    ["/api/theses/{id}/approve", "POST", "Oui", "Manager", "Approuver une these"],
    ["/api/theses/{id}/reject", "POST", "Oui", "Manager", "Rejeter une these"],
]
story.append(make_data_table(api_agents_headers, api_agents_rows,
    col_widths=[38*mm, 16*mm, 12*mm, 20*mm, 64*mm]))
story.append(Spacer(1, 3*mm))

story.append(Paragraph("15.3 Execution et Ordres", h2_style))

api_exec_headers = ["Endpoint", "Methode", "Auth", "Role min.", "Description"]
api_exec_rows = [
    ["/api/orders", "GET", "Oui", "Viewer", "Liste des ordres (filtre par status)"],
    ["/api/orders/execute-cycle", "POST", "Oui", "Manager", "Lancer un cycle d'execution"],
    ["/api/fills", "GET", "Oui", "Viewer", "Historique des fills"],
    ["/api/positions", "GET", "Oui", "Viewer", "Positions courantes du portefeuille"],
    ["/api/portfolio/summary", "GET", "Oui", "Viewer", "Resume portefeuille (equity, P&amp;L, allocation)"],
]
story.append(make_data_table(api_exec_headers, api_exec_rows,
    col_widths=[42*mm, 16*mm, 12*mm, 20*mm, 60*mm]))
story.append(Spacer(1, 3*mm))

story.append(Paragraph("15.4 Market Intel et Donnees", h2_style))

api_data_headers = ["Endpoint", "Methode", "Auth", "Description"]
api_data_rows = [
    ["/api/run-ingestion", "POST", "Oui (Manager)", "Declencher l'ingestion de toutes les sources"],
    ["/api/crypto/top25", "GET", "Oui", "TOP 25 crypto CoinGecko (prix, market cap, vol)"],
    ["/api/macro/vulnerability", "GET", "Oui", "Score de vulnerabilite macro (FRED)"],
    ["/api/macro/geopolitical", "GET", "Oui", "Score risque geopolitique (GDELT + USGS)"],
    ["/api/finviz/signals", "GET", "Oui", "Signaux Finviz (stock screener)"],
    ["/api/finviz/sectors", "GET", "Oui", "Performance sectorielle Finviz"],
    ["/api/prices/{ticker}", "GET", "Oui", "Historique des prix d'un instrument"],
    ["/api/instruments", "GET", "Oui", "Catalogue des instruments"],
]
story.append(make_data_table(api_data_headers, api_data_rows,
    col_widths=[42*mm, 20*mm, 25*mm, 63*mm]))
story.append(Spacer(1, 3*mm))

story.append(Paragraph("15.5 Backtest", h2_style))

api_bt_headers = ["Endpoint", "Methode", "Auth", "Role min.", "Description"]
api_bt_rows = [
    ["/api/backtest", "POST", "Oui", "Analyst", "Lancer un backtest (tickers, poids, periode)"],
    ["/api/backtest/export-csv", "POST", "Oui", "Analyst", "Exporter le journal de trading en CSV"],
]
story.append(make_data_table(api_bt_headers, api_bt_rows,
    col_widths=[42*mm, 16*mm, 12*mm, 20*mm, 60*mm]))
story.append(Spacer(1, 3*mm))

story.append(Paragraph("15.6 Risk Engine", h2_style))

api_risk_headers = ["Endpoint", "Methode", "Auth", "Role min.", "Description"]
api_risk_rows = [
    ["/api/risk-config", "GET", "Oui", "Viewer", "Configuration actuelle du risk engine"],
    ["/api/risk-config", "PUT", "Oui", "Admin", "Modifier parametres de risque (VaR, limites)"],
    ["/api/risk/status", "GET", "Oui", "Viewer", "Etat actuel : VaR, drawdown, violations"],
]
story.append(make_data_table(api_risk_headers, api_risk_rows,
    col_widths=[38*mm, 16*mm, 12*mm, 20*mm, 64*mm]))
story.append(Spacer(1, 3*mm))

story.append(Paragraph("15.7 Administration", h2_style))

api_admin_headers = ["Endpoint", "Methode", "Auth", "Description"]
api_admin_rows = [
    ["/api/admin/users", "GET", "Admin", "Liste de tous les utilisateurs (status, role, last login)"],
    ["/api/admin/users", "POST", "Admin", "Creer un nouvel utilisateur (username, email, password, role)"],
    ["/api/admin/users/{id}", "PUT", "Admin", "Modifier role, status, nom d'un utilisateur"],
    ["/api/admin/users/{id}/reset-password", "POST", "Admin", "Reinitialiser le mot de passe"],
    ["/api/admin/users/{id}", "DELETE", "Admin", "Desactiver un utilisateur (soft delete)"],
    ["/api/admin/roles", "GET", "Admin", "Liste des roles et permissions"],
]
story.append(make_data_table(api_admin_headers, api_admin_rows,
    col_widths=[50*mm, 16*mm, 16*mm, 68*mm]))
story.append(Paragraph("Tableau 9 — Reference complete de l'API Nextones Desk", caption_style))

story.append(Spacer(1, 3*mm))

story.append(Paragraph("15.8 IC Memos", h2_style))

api_memo_headers = ["Endpoint", "Methode", "Auth", "Role min.", "Description"]
api_memo_rows = [
    ["/api/memos", "GET", "Oui", "Viewer", "Liste des IC Memos generes"],
    ["/api/memos/{id}", "GET", "Oui", "Viewer", "Detail d'un memo (contenu complet)"],
    ["/api/memos/{id}/export", "GET", "Oui", "Analyst", "Exporter un memo en PDF ou Markdown"],
    ["/api/memos/generate", "POST", "Oui", "Manager", "Generer un IC Memo pour le cycle courant"],
]
story.append(make_data_table(api_memo_headers, api_memo_rows,
    col_widths=[40*mm, 16*mm, 12*mm, 20*mm, 62*mm]))

story.append(Spacer(1, 6*mm))

# ── Agents comparison summary table ──
story.append(Paragraph("Annexe — Comparatif des 5 agents", h1_style))
story.append(hr())

comp_header_style = ParagraphStyle("CompH", parent=body_style, fontSize=8, textColor=white, fontName="Helvetica-Bold", alignment=TA_CENTER)
comp_cell_style = ParagraphStyle("CompC", parent=body_style, fontSize=8, leading=10, alignment=TA_CENTER)
comp_cell_left = ParagraphStyle("CompCL", parent=body_style, fontSize=8, leading=10)

col_widths = [25*mm, 28*mm, 40*mm, 22*mm, 35*mm]

comp_data = [
    [Paragraph("<b>Agent</b>", comp_header_style),
     Paragraph("<b>Perimetre</b>", comp_header_style),
     Paragraph("<b>Indicateurs cles</b>", comp_header_style),
     Paragraph("<b>Horizon</b>", comp_header_style),
     Paragraph("<b>Type de signal</b>", comp_header_style)],

    [Paragraph("MacroAgent", comp_cell_style),
     Paragraph("SPY, QQQ, DIA + FRED", comp_cell_style),
     Paragraph("SMA 50/200, RSI(14), FRED Vulnerability Score", comp_cell_left),
     Paragraph("Moyen terme", comp_cell_style),
     Paragraph("Stance macro + score vulnerabilite", comp_cell_left)],

    [Paragraph("FactorAgent", comp_cell_style),
     Paragraph("Actions (equity)", comp_cell_style),
     Paragraph("Momentum 12-1m, Qualite (vol), RSI inverse", comp_cell_left),
     Paragraph("Moyen terme", comp_cell_style),
     Paragraph("Tilt (over / under / neutral)", comp_cell_left)],

    [Paragraph("Microstructure", comp_cell_style),
     Paragraph("Tous + Finviz", comp_cell_style),
     Paragraph("Bollinger, Volume, ATR, S/R, Analyst Ratings", comp_cell_left),
     Paragraph("Court terme", comp_cell_style),
     Paragraph("Signal trading (buy/sell/hold)", comp_cell_left)],

    [Paragraph("AltDataAgent", comp_cell_style),
     Paragraph("Equity + GDELT/USGS", comp_cell_style),
     Paragraph("Div. prix-vol, Tendance, Z-score, Geopolitique", comp_cell_left),
     Paragraph("Court/moyen", comp_cell_style),
     Paragraph("Sentiment + score geopolitique", comp_cell_left)],

    [Paragraph("CryptoAgent", comp_cell_style),
     Paragraph("TOP 25 CoinGecko", comp_cell_style),
     Paragraph("SMA 7/21, Mom. 7j, Vol regime, RSI 75/25", comp_cell_left),
     Paragraph("Court terme", comp_cell_style),
     Paragraph("Signal crypto (strong_buy/sell)", comp_cell_left)],
]

comp_table = Table(comp_data, colWidths=col_widths)
comp_table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), DARK_TEAL),
    ("BACKGROUND", (0, 1), (-1, 1), PAPER_WHITE),
    ("BACKGROUND", (0, 2), (-1, 2), OFF_WHITE),
    ("BACKGROUND", (0, 3), (-1, 3), PAPER_WHITE),
    ("BACKGROUND", (0, 4), (-1, 4), OFF_WHITE),
    ("BACKGROUND", (0, 5), (-1, 5), PAPER_WHITE),
    ("TOPPADDING", (0, 0), (-1, -1), 3*mm),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3*mm),
    ("LEFTPADDING", (0, 0), (-1, -1), 2*mm),
    ("RIGHTPADDING", (0, 0), (-1, -1), 2*mm),
    ("GRID", (0, 0), (-1, -1), 0.5, WARM_BEIGE),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
]))
story.append(comp_table)
story.append(Paragraph("Tableau 10 — Comparatif des cinq agents Nextones Desk", caption_style))

story.append(Spacer(1, 8*mm))
story.append(hr())
story.append(Paragraph(
    "<i>Document genere automatiquement par Perplexity Computer pour Nextones Desk (nextones.finance). "
    "Version 2.0 — Mars 2026. Ce document couvre l'architecture complete du systeme incluant "
    "les 5 agents IA, le moteur de risque, le moteur d'execution, le backtester, l'authentification RBAC, "
    "le risque geopolitique, l'ingestion de donnees, le schema de base de donnees et la reference API.</i>",
    ParagraphStyle("Disclaimer", parent=body_style, fontSize=8, textColor=MED_TEAL, alignment=TA_CENTER)
))


# ══════════════════════════════════════════════════════════
# BUILD
# ══════════════════════════════════════════════════════════

output_path = "/home/user/workspace/thesium-desk/Nextones_Architecture_Agents.pdf"

doc = SimpleDocTemplate(
    output_path,
    pagesize=A4,
    leftMargin=LEFT_MARGIN,
    rightMargin=RIGHT_MARGIN,
    topMargin=TOP_MARGIN,
    bottomMargin=BOT_MARGIN,
    title="Architecture & Agents — Nextones Desk",
    author="Perplexity Computer",
)

doc.build(story, onFirstPage=cover_page, onLaterPages=later_pages)
print(f"PDF generated: {output_path}")
print(f"Pages: {doc.page}")
