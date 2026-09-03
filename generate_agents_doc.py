"""
Generate PDF: Architecture des Agents Thesium.finance
French document with agent rationale, descriptions, and SWOT analysis.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import os

# ── Perplexity Brand Colors ──
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

# Chart sequence for agents (5 agents)
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
    fontName="Helvetica-Bold", fontSize=18, leading=24,
    textColor=DARK_TEAL, spaceBefore=10*mm, spaceAfter=5*mm
)

h2_style = ParagraphStyle(
    "H2", parent=styles["Heading2"],
    fontName="Helvetica-Bold", fontSize=14, leading=18,
    textColor=DEEP_TEAL, spaceBefore=6*mm, spaceAfter=3*mm
)

h3_style = ParagraphStyle(
    "H3", parent=styles["Heading3"],
    fontName="Helvetica-Bold", fontSize=11, leading=15,
    textColor=MED_TEAL, spaceBefore=4*mm, spaceAfter=2*mm
)

body_style = ParagraphStyle(
    "Body", parent=styles["Normal"],
    fontName="Helvetica", fontSize=10, leading=14,
    textColor=DARK_TEAL, alignment=TA_JUSTIFY, spaceAfter=3*mm
)

body_bold = ParagraphStyle(
    "BodyBold", parent=body_style,
    fontName="Helvetica-Bold"
)

bullet_style = ParagraphStyle(
    "Bullet", parent=body_style,
    leftIndent=10*mm, bulletIndent=5*mm,
    spaceBefore=1*mm, spaceAfter=1*mm
)

swot_header_style = ParagraphStyle(
    "SwotHeader", parent=styles["Normal"],
    fontName="Helvetica-Bold", fontSize=10, leading=13,
    textColor=white, alignment=TA_CENTER, spaceAfter=0
)

swot_cell_style = ParagraphStyle(
    "SwotCell", parent=styles["Normal"],
    fontName="Helvetica", fontSize=9, leading=12,
    textColor=DARK_TEAL, alignment=TA_LEFT, spaceAfter=0
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
    fontSize=11, leading=18, leftIndent=5*mm,
    textColor=DEEP_TEAL
)

toc_sub_style = ParagraphStyle(
    "TOCSub", parent=body_style,
    fontSize=10, leading=16, leftIndent=12*mm,
    textColor=MED_TEAL
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
    canvas.setFont("Helvetica-Bold", 30)
    canvas.drawString(LEFT_MARGIN, PAGE_H - 35*mm, "Architecture des 5 Agents")
    canvas.setFont("Helvetica", 16)
    canvas.drawString(LEFT_MARGIN, PAGE_H - 47*mm, "Thesium.finance — Documentation Technique")
    canvas.setFont("Helvetica", 11)
    canvas.drawString(LEFT_MARGIN, PAGE_H - 57*mm, f"Version 1.0 — {datetime.now().strftime('%d/%m/%Y')}")
    # Bottom accent
    canvas.setFillColor(MUTED_TEAL)
    canvas.rect(0, 0, PAGE_W, 12*mm, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(PAGE_W/2, 4.5*mm, "Thesium.finance • Document confidentiel • Perplexity Computer")
    canvas.restoreState()


def later_pages(canvas, doc):
    canvas.saveState()
    # Header band
    canvas.setFillColor(DARK_TEAL)
    canvas.rect(0, PAGE_H - 14*mm, PAGE_W, 14*mm, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(LEFT_MARGIN, PAGE_H - 10*mm, "Thesium.finance — Architecture des Agents")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(PAGE_W - RIGHT_MARGIN, PAGE_H - 10*mm, f"Page {doc.page}")
    # Footer
    canvas.setFillColor(MUTED_TEAL)
    canvas.rect(0, 0, PAGE_W, 8*mm, fill=1, stroke=0)
    canvas.setFillColor(white)
    canvas.setFont("Helvetica", 7)
    canvas.drawCentredString(PAGE_W/2, 2.5*mm, f"Thesium.finance • {datetime.now().strftime('%d/%m/%Y')} • Perplexity Computer")
    canvas.restoreState()


def make_swot_table(strengths, weaknesses, opportunities, threats, agent_color):
    """Create a styled SWOT table."""
    s_items = "<br/>".join([f"• {s}" for s in strengths])
    w_items = "<br/>".join([f"• {w}" for w in weaknesses])
    o_items = "<br/>".join([f"• {o}" for o in opportunities])
    t_items = "<br/>".join([f"• {t}" for t in threats])

    col_w = CONTENT_W / 2

    data = [
        [Paragraph("FORCES (S)", swot_header_style),
         Paragraph("FAIBLESSES (W)", swot_header_style)],
        [Paragraph(s_items, swot_cell_style),
         Paragraph(w_items, swot_cell_style)],
        [Paragraph("OPPORTUNITES (O)", swot_header_style),
         Paragraph("MENACES (T)", swot_header_style)],
        [Paragraph(o_items, swot_cell_style),
         Paragraph(t_items, swot_cell_style)],
    ]

    # Colors
    s_color = HexColor("#1B7A3C")  # green
    w_color = HexColor("#A84B2F")  # terra/red
    o_color = HexColor("#20808D")  # teal
    t_color = HexColor("#944454")  # mauve

    t = Table(data, colWidths=[col_w, col_w])
    t.setStyle(TableStyle([
        # Header rows
        ("BACKGROUND", (0, 0), (0, 0), s_color),
        ("BACKGROUND", (1, 0), (1, 0), w_color),
        ("BACKGROUND", (0, 2), (0, 2), o_color),
        ("BACKGROUND", (1, 2), (1, 2), t_color),
        # Content cells
        ("BACKGROUND", (0, 1), (0, 1), HexColor("#E8F5E9")),
        ("BACKGROUND", (1, 1), (1, 1), HexColor("#FBE9E7")),
        ("BACKGROUND", (0, 3), (0, 3), HexColor("#E0F2F1")),
        ("BACKGROUND", (1, 3), (1, 3), HexColor("#FCE4EC")),
        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), 4*mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4*mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 4*mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4*mm),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, WARM_BEIGE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


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


def hr():
    return HRFlowable(width="100%", thickness=0.5, color=WARM_BEIGE, spaceBefore=3*mm, spaceAfter=3*mm)


# ══════════════════════════════════════════════════════════════════════
# DOCUMENT CONTENT
# ══════════════════════════════════════════════════════════════════════

story = []

# ── COVER PAGE (content below band) ──
story.append(Spacer(1, 55*mm))  # push below cover header band

story.append(Paragraph(
    "Ce document presente l'architecture multi-agents de Thesium.finance, "
    "un systeme de gestion de portefeuille intelligent propulse par l'IA. "
    "Il decrit la logique de conception, le fonctionnement detaille de chaque agent (5 agents), "
    "et fournit une analyse SWOT individuelle.",
    ParagraphStyle("CoverBody", parent=body_style, fontSize=12, leading=17, textColor=DARK_TEAL, spaceAfter=8*mm)
))

# Info block on cover
cover_info = [
    ("Projet", "Thesium.finance — MVP (Fund OS)"),
    ("Version", "1.0"),
    ("Date", datetime.now().strftime("%d/%m/%Y")),
    ("Auteur", "Perplexity Computer"),
    ("Nombre d'agents", "5 (Macro, Factor, Microstructure, AltData, Crypto)"),
    ("Langages", "Python 3.11 / SQLite / FastAPI"),
]
story.append(make_info_table(cover_info, header_color=DEEP_TEAL))
story.append(PageBreak())

# ── TABLE OF CONTENTS ──
story.append(Paragraph("Table des matieres", h1_style))
story.append(Spacer(1, 4*mm))

toc_entries = [
    ("1.", "Philosophie et choix de l'architecture multi-agents", toc_style),
    ("", "1.1 Pourquoi cinq agents specialises ?", toc_sub_style),
    ("", "1.2 Principe de fonctionnement global", toc_sub_style),
    ("", "1.3 L'orchestrateur", toc_sub_style),
    ("2.", "MacroAgent — Analyse macro-economique", toc_style),
    ("", "2.1 Description et fonctionnement", toc_sub_style),
    ("", "2.2 Analyse SWOT", toc_sub_style),
    ("3.", "FactorAgent — Analyse factorielle", toc_style),
    ("", "3.1 Description et fonctionnement", toc_sub_style),
    ("", "3.2 Analyse SWOT", toc_sub_style),
    ("4.", "MicrostructureAgent — Microstructure de marche", toc_style),
    ("", "4.1 Description et fonctionnement", toc_sub_style),
    ("", "4.2 Analyse SWOT", toc_sub_style),
    ("5.", "AltDataAgent — Donnees alternatives", toc_style),
    ("", "5.1 Description et fonctionnement", toc_sub_style),
    ("", "5.2 Analyse SWOT", toc_sub_style),
    ("6.", "CryptoAgent — Analyse crypto-actifs", toc_style),
    ("", "6.1 Description et fonctionnement", toc_sub_style),
    ("", "6.2 Analyse SWOT", toc_sub_style),
    ("7.", "Synthese comparative et conclusion", toc_style),
]
for num, text, style in toc_entries:
    if num:
        story.append(Paragraph(f"<b>{num}</b> {text}", style))
    else:
        story.append(Paragraph(text, style))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 1: Philosophy & Architecture Choice
# ═══════════════════════════════════════════════════════

story.append(Paragraph("1. Philosophie et choix de l'architecture multi-agents", h1_style))
story.append(hr())

story.append(Paragraph("1.1 Pourquoi cinq agents specialises ?", h2_style))

story.append(Paragraph(
    "L'architecture de Thesium.finance repose sur un principe fondamental issu de la gestion "
    "de fonds institutionnelle : la <b>separation des preoccupations analytiques</b>. Plutot qu'un "
    "algorithme unique tentant de capturer tous les signaux du marche, nous avons opte pour "
    "cinq agents specialises, chacun maitrisant un domaine d'analyse distinct.",
    body_style
))

story.append(Paragraph(
    "Ce choix s'inspire directement de l'organisation d'un desk de trading professionnel ou "
    "differents analystes couvrent chacun un angle specifique :",
    body_style
))

rationale_items = [
    "<b>MacroAgent</b> : Le stratege macro, equivalent d'un chief investment strategist qui definit le regime de marche global (risk-on / risk-off / neutral).",
    "<b>FactorAgent</b> : L'analyste quantitatif, specialise dans les facteurs systematiques (momentum, qualite, valorisation) pour classer les actifs par attractivite relative.",
    "<b>MicrostructureAgent</b> : Le trader technique, expert en lecture de l'action des prix, des volumes et des niveaux techniques pour determiner le timing optimal.",
    "<b>AltDataAgent</b> : L'analyste de donnees alternatives, detectant les anomalies de marche et les divergences prix-volume comme proxy de sentiment.",
    "<b>CryptoAgent</b> : Le specialiste crypto-actifs, analysant BTC, ETH et LINK avec des indicateurs adaptes a la volatilite et aux cycles propres aux cryptomonnaies.",
]
for item in rationale_items:
    story.append(Paragraph(item, bullet_style, bulletText="▸"))

story.append(Spacer(1, 3*mm))
story.append(Paragraph(
    "Cette separation offre plusieurs avantages decisifs : <b>independance des analyses</b> (un biais "
    "dans un agent ne contamine pas les autres), <b>maintenabilite</b> (chaque agent peut etre ameliore "
    "isolement), <b>transparence</b> (les theses sont clairement attribuees a leur source), et "
    "<b>scalabilite</b> (de nouveaux agents peuvent etre ajoutes sans refactoring majeur).",
    body_style
))

story.append(Paragraph("1.2 Principe de fonctionnement global", h2_style))

story.append(Paragraph(
    "Chaque agent suit un cycle d'analyse identique en quatre etapes :",
    body_style
))

cycle_steps = [
    "<b>Collecte</b> : Extraction des donnees historiques de prix (OHLCV) depuis la base SQLite pour les instruments de son perimetre.",
    "<b>Calcul</b> : Application d'indicateurs techniques deterministes (SMA, RSI, Bandes de Bollinger, ATR, etc.) sur les series de prix.",
    "<b>Decision</b> : Generation d'un signal (stance, tilt, signal de trading, sentiment) accompagne d'un score de conviction de 0 a 10.",
    "<b>Persistance</b> : Sauvegarde d'une these structuree (texte, drivers cles, action proposee, horizon) dans la table <font face='Courier' size=9>theses</font> et journalisation dans la table <font face='Courier' size=9>events</font>.",
]
for step in cycle_steps:
    story.append(Paragraph(step, bullet_style, bulletText="▸"))

story.append(Spacer(1, 3*mm))
story.append(Paragraph(
    "Toutes les analyses sont <b>100% deterministes</b> : a donnees identiques, les signaux produits "
    "sont strictement reproductibles. Il n'y a aucune composante aleatoire dans le moteur d'agents, "
    "ce qui garantit l'auditabilite complete des decisions.",
    body_style
))

story.append(Paragraph("1.3 L'orchestrateur", h2_style))

story.append(Paragraph(
    "La fonction <font face='Courier' size=9>run_all_agents()</font> joue le role d'orchestrateur : "
    "elle execute sequentiellement les cinq agents, collecte leurs resultats, et journalise un evenement "
    "<font face='Courier' size=9>agent_cycle_complete</font> avec les statistiques du cycle "
    "(conviction macro, nombre de theses par agent). Ce design permet au front-end de declencher "
    "un cycle complet via l'endpoint <font face='Courier' size=9>POST /api/agents/run</font> et d'afficher "
    "les theses resultantes dans l'onglet dedie.",
    body_style
))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 2: MacroAgent
# ═══════════════════════════════════════════════════════

story.append(Paragraph("2. MacroAgent — Analyse macro-economique", h1_style))
story.append(hr())

# Info card
macro_info = [
    ("Role", "Determine le regime macro global : risk-on, risk-off ou neutral"),
    ("Perimetre", "ETFs de reference : SPY (S&P 500), QQQ (Nasdaq 100), DIA (Dow Jones 30)"),
    ("Indicateurs", "SMA 50/200 (golden/death cross), RSI(14), momentum 20 jours, volatilite annualisee"),
    ("Horizon", "Moyen terme (medium) en configuration claire, court terme (short) en neutre"),
    ("Conviction", "Echelle 5-9 selon la force des signaux agreges"),
    ("Sortie", "Une these unique avec stance macro et recommendation d'allocation"),
]
story.append(make_info_table(macro_info, header_color=AGENT_COLORS[0]))
story.append(Spacer(1, 4*mm))

story.append(Paragraph("2.1 Description et fonctionnement", h2_style))

story.append(Paragraph(
    "Le MacroAgent constitue la <b>premiere ligne de defense</b> du systeme. Avant toute analyse "
    "instrument par instrument, il etablit le regime macro en examinant trois ETFs representatifs "
    "des principaux marches actions americains.",
    body_style
))

story.append(Paragraph("<b>Logique de decision detaillee :</b>", body_style))

macro_logic = [
    "<b>Golden/Death Cross</b> : Pour chaque ETF, l'agent calcule les moyennes mobiles simples a 50 et 200 jours. Si SMA50 > SMA200, c'est un \"golden cross\" (signal haussier). Si SMA50 < SMA200, c'est un \"death cross\" (signal baissier). Le vote majoritaire (2 sur 3 ou plus) determine la stance.",
    "<b>RSI(14)</b> : Le Relative Strength Index sur 14 periodes detecte les conditions de surachat (RSI > 65) ou de survente (RSI < 35). Les conditions de surachat viennent temperer un signal haussier.",
    "<b>Momentum 20 jours</b> : Le rendement sur 20 jours est calcule pour chaque ETF et moyennise. Ce chiffre quantifie la force de la tendance recente.",
    "<b>Volatilite annualisee</b> : Calculee sur 20 jours et annualisee (x racine de 252), elle mesure le regime de volatilite actuel.",
]
for item in macro_logic:
    story.append(Paragraph(item, bullet_style, bulletText="▸"))

story.append(Spacer(1, 3*mm))
story.append(Paragraph(
    "<b>Matrice de decision :</b> Si 2+ ETFs en golden cross → risk-on (conviction 7-9). Si 2+ en death cross "
    "→ risk-off (conviction 7-9). Sinon → neutral (conviction 5). La conviction est ajustee a la baisse "
    "si des signaux de surachat RSI sont detectes, refletant une prudence accrue.",
    body_style
))

story.append(Spacer(1, 4*mm))
story.append(Paragraph("2.2 Analyse SWOT", h2_style))

story.append(make_swot_table(
    strengths=[
        "Approche top-down classique et eprouvee en gestion institutionnelle",
        "Golden/Death cross : indicateur fiable de tendance longue",
        "Perimetre restreint (3 ETFs) = robustesse et vitesse d'execution",
        "Vote majoritaire elimine le bruit d'un seul indice",
        "Faible risque d'overfitting grace a des regles simples",
    ],
    weaknesses=[
        "Indicateur retarde : SMA 200 reagit lentement aux retournements",
        "Pas de donnees fondamentales (taux, inflation, PIB, spreads credit)",
        "Limite aux marches US (pas d'analyse internationale)",
        "RSI seul comme filtre de timing est basique",
        "Pas de prise en compte de la courbe des taux ou du VIX",
    ],
    opportunities=[
        "Integrer des donnees macro reelles (Fed Funds, CPI, PMI) via API",
        "Ajouter des ETFs internationaux (EFA, EEM) pour couverture globale",
        "Incorporer le VIX comme indicateur complementaire de regime",
        "Appliquer un modele de regime switching (Hidden Markov)",
        "Connecter aux calendriers economiques pour anticiper les evenements",
    ],
    threats=[
        "Whipsaw : faux signaux en marche sans tendance (range-bound)",
        "Les flash crashes peuvent generer des signaux errones temporaires",
        "Changements structurels de marche (correlation entre actifs)",
        "Dependance aux donnees historiques qui peuvent ne pas refleter le futur",
        "Retard de detection peut causer des pertes lors de corrections rapides",
    ],
    agent_color=AGENT_COLORS[0]
))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 3: FactorAgent
# ═══════════════════════════════════════════════════════

story.append(Paragraph("3. FactorAgent — Analyse factorielle", h1_style))
story.append(hr())

factor_info = [
    ("Role", "Classement relatif des actions par exposition factorielle composite"),
    ("Perimetre", "Tous les instruments de classe 'equity' (exclut ETFs de reference et crypto)"),
    ("Indicateurs", "Momentum 12-1 mois, qualite (inverse volatilite), RSI(14)"),
    ("Score", "Composite 0-10 pondere : momentum (50%), qualite (30%), RSI inverse (20%)"),
    ("Horizon", "Moyen terme (medium)"),
    ("Sortie", "Liste triee des actions avec tilt (overweight / neutral / underweight)"),
]
story.append(make_info_table(factor_info, header_color=AGENT_COLORS[1]))
story.append(Spacer(1, 4*mm))

story.append(Paragraph("3.1 Description et fonctionnement", h2_style))

story.append(Paragraph(
    "Le FactorAgent s'inspire du <b>factor investing</b>, une approche quantitative validee par la "
    "recherche academique (Fama-French, Carhart). Il decompose l'attractivite de chaque action en "
    "trois facteurs mesurables et les combine en un score unique.",
    body_style
))

story.append(Paragraph("<b>Les trois facteurs :</b>", body_style))

factor_details = [
    "<b>Momentum (poids 50%)</b> : Calcul du rendement sur 12 mois en excluant le dernier mois (convention \"12-1\" pour eviter l'effet de reversal a court terme). Le rendement est mappe lineairement de [-30%, +30%] vers une echelle [0, 10]. Avec des donnees limitees, l'agent s'adapte en utilisant le maximum de jours disponibles (jusqu'a 21 jours).",
    "<b>Qualite (poids 30%)</b> : En l'absence de donnees fondamentales (ROE, marges), la volatilite annualisee sur 20 jours sert de proxy inverse : une faible volatilite indique une action de meilleure \"qualite\". Score = 10 - (volatilite x 20), borne entre 0 et 10.",
    "<b>RSI inverse (poids 20%)</b> : Le complement du RSI(14) normalise (10 - RSI/10) penalise les actions en zone de surachat et favorise celles en zone de survente, ajoutant un element contrariant au modele.",
]
for item in factor_details:
    story.append(Paragraph(item, bullet_style, bulletText="▸"))

story.append(Spacer(1, 3*mm))
story.append(Paragraph(
    "<b>Classification :</b> Score composite >= 7 → overweight (surponderer). Score <= 3 → underweight "
    "(sous-ponderer). Entre 3 et 7 → neutral. La conviction est proportionnelle a l'ecart du score "
    "par rapport a 5 (le centre neutre), variant de 4 a 9.",
    body_style
))

story.append(Spacer(1, 4*mm))
story.append(Paragraph("3.2 Analyse SWOT", h2_style))

story.append(make_swot_table(
    strengths=[
        "Fondement academique solide (Fama-French, Carhart four-factor model)",
        "Score composite multi-facteurs reduit la dependance a un seul signal",
        "Ponderation explicite et transparente des facteurs",
        "Classement relatif ideal pour l'allocation intra-portefeuille",
        "Adaptabilite automatique a la profondeur de donnees disponible",
    ],
    weaknesses=[
        "Proxy qualite (inverse-vol) simplifie vs metriques fondamentales reelles",
        "Pas de facteur Value (P/E, P/B) faute de donnees fondamentales",
        "Momentum peut amplifier les bulles et les drawdowns",
        "Ponderation fixe (50/30/20) sans optimisation dynamique",
        "Ne traite pas les cryptos ni les ETFs de reference",
    ],
    opportunities=[
        "Integrer des donnees fondamentales via API (P/E, ROE, dette/EBITDA)",
        "Ajouter le facteur Value et Size pour un modele five-factor complet",
        "Optimiser les ponderations par backtesting historique",
        "Etendre aux cryptos avec des facteurs adaptes (NVT, hashrate)",
        "Implementer un regime-switch des ponderations selon le cycle macro",
    ],
    threats=[
        "Factor crowding : quand trop d'acteurs suivent le momentum, les reversals sont brutaux",
        "Periodes prolongees de sous-performance des facteurs momentum",
        "Correlations entre facteurs en periode de stress (tout baisse)",
        "Le proxy qualite (vol) peut classer en \"haute qualite\" des actions simplement illiquides",
        "Absence de donnees sur 12 mois complets degrade la fiabilite du momentum",
    ],
    agent_color=AGENT_COLORS[1]
))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 4: MicrostructureAgent
# ═══════════════════════════════════════════════════════

story.append(Paragraph("4. MicrostructureAgent — Microstructure de marche", h1_style))
story.append(hr())

micro_info = [
    ("Role", "Analyse technique fine : timing d'entree/sortie, niveaux de stop, support/resistance"),
    ("Perimetre", "Tous les instruments (actions, ETFs et cryptos)"),
    ("Indicateurs", "Bandes de Bollinger (20p, 2σ), RSI(14), ratio volume 5j/20j, ATR(14), support/resistance 10j"),
    ("Signaux", "buy/add, sell/take profit, accumulate, reduce, hold"),
    ("Horizon", "Court terme (short) pour signaux forts, moyen terme (medium) sinon"),
    ("Sortie", "Signal de trading par instrument avec niveaux de stop ATR"),
]
story.append(make_info_table(micro_info, header_color=AGENT_COLORS[2]))
story.append(Spacer(1, 4*mm))

story.append(Paragraph("4.1 Description et fonctionnement", h2_style))

story.append(Paragraph(
    "Le MicrostructureAgent est le <b>bras executif</b> du systeme. Tandis que les autres agents "
    "determinent quoi et combien, celui-ci repond a la question <b>quand</b>. Il analyse la "
    "microstructure de chaque instrument pour identifier les points d'entree et de sortie optimaux.",
    body_style
))

story.append(Paragraph("<b>Arsenal d'indicateurs :</b>", body_style))

micro_details = [
    "<b>Bandes de Bollinger (20 periodes, 2 ecarts-types)</b> : Le prix est positionne en percentile dans la bande (0% = bande inferieure, 100% = bande superieure). Un percentile > 95% avec volume eleve signale un exces haussier (vente). Un percentile < 5% avec volume faible signale une capitulation (achat).",
    "<b>Ratio de volume (5j/20j)</b> : Compare l'activite recente a la moyenne. Un ratio > 1.2x indique une participation elevee (confirmation de mouvement). Un ratio < 0.9x suggere un essoufflement.",
    "<b>ATR (Average True Range, 14 periodes)</b> : Mesure la volatilite moyenne reelle pour calibrer les stops. Le stop est place a 2x ATR sous le prix courant, offrant un coussin adapte a la volatilite de l'instrument.",
    "<b>Support/Resistance</b> : Les extremes des 10 derniers jours definissent les bornes techniques immediates.",
    "<b>RSI(14)</b> : Filtre secondaire — surachat > 70 declenche un signal 'reduce', survente < 30 declenche 'accumulate'.",
]
for item in micro_details:
    story.append(Paragraph(item, bullet_style, bulletText="▸"))

story.append(Spacer(1, 3*mm))
story.append(Paragraph(
    "<b>Hierarchie de decision :</b> La priorite est donnee aux signaux Bollinger+Volume (conviction 7.5), "
    "puis aux extremes RSI (conviction 6.5), puis au signal neutre 'hold' (conviction 5.0). "
    "Chaque signal inclut un niveau de stop loss calcule dynamiquement.",
    body_style
))

story.append(Spacer(1, 4*mm))
story.append(Paragraph("4.2 Analyse SWOT", h2_style))

story.append(make_swot_table(
    strengths=[
        "Couverture universelle : analyse tous les instruments (actions + crypto)",
        "Combinaison Bollinger + Volume offre des signaux contextuels riches",
        "Stops dynamiques via ATR s'adaptent a la volatilite de chaque actif",
        "Signaux actionnables (buy/sell) avec niveaux de prix concrets",
        "Hierarchie de decision claire et previsible",
    ],
    weaknesses=[
        "Bollinger Bands peu fiables en marche fortement directionnel (trending)",
        "Support/resistance sur 10 jours est une fenetre tres courte",
        "Pas de prise en compte du carnet d'ordres (orderbook) reel",
        "Conviction fixe par categorie (7.5 / 6.5 / 5.0) manque de granularite",
        "Ne distingue pas les regimes de volatilite (VIX eleve vs faible)",
    ],
    opportunities=[
        "Integrer des donnees de carnet d'ordres (Level 2) pour les crypto",
        "Ajouter VWAP intraday pour un meilleur benchmark d'execution",
        "Implementer des patterns de chandelier (doji, engulfing, hammer)",
        "Adapter les seuils de Bollinger selon le regime de volatilite",
        "Ajouter un scoring de confluence multi-indicateurs gradue",
    ],
    threats=[
        "Faux signaux frequents en periodes de faible volatilite (squeeze)",
        "Les stops ATR peuvent etre declenches par le bruit intraday",
        "Dependance aux donnees journalieres (pas d'intraday)",
        "Latence entre le signal et l'execution en paper-trading",
        "Les niveaux S/R sur 10 jours peuvent ne pas refleter les niveaux cles historiques",
    ],
    agent_color=AGENT_COLORS[2]
))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 5: AltDataAgent
# ═══════════════════════════════════════════════════════

story.append(Paragraph("5. AltDataAgent — Donnees alternatives", h1_style))
story.append(hr())

alt_info = [
    ("Role", "Detection d'anomalies et analyse de sentiment proxy via prix-volume"),
    ("Perimetre", "Instruments de classe 'equity' uniquement"),
    ("Indicateurs", "Divergence prix-volume (5j), consistance de tendance (jours > SMA20), z-score des rendements"),
    ("Sentiments", "strong_bullish, weak_bullish, capitulation, weak_bearish, neutral"),
    ("Horizon", "Court terme pour signaux forts, moyen terme sinon"),
    ("Sortie", "Sentiment par action avec conviction ajustee par consistance de tendance"),
]
story.append(make_info_table(alt_info, header_color=AGENT_COLORS[3]))
story.append(Spacer(1, 4*mm))

story.append(Paragraph("5.1 Description et fonctionnement", h2_style))

story.append(Paragraph(
    "L'AltDataAgent represente une approche <b>innovante et differenciante</b>. En l'absence "
    "de flux de donnees alternatives reels (reseaux sociaux, images satellite, donnees de "
    "transaction), il construit des <b>proxies de sentiment</b> a partir de la dynamique "
    "prix-volume, detectant les configurations qui, historiquement, precedent des mouvements significatifs.",
    body_style
))

story.append(Paragraph("<b>Les trois piliers analytiques :</b>", body_style))

alt_details = [
    "<b>Divergence prix-volume</b> : L'agent croise la variation de prix sur 5 jours avec la variation de volume sur la meme periode. Quatre configurations sont identifiees : (1) Prix hausse + volume hausse = rally sain (strong_bullish), (2) Prix hausse + volume baisse = distribution (weak_bullish, risque de retournement), (3) Prix baisse + volume hausse = capitulation (signal d'achat potentiel), (4) Prix baisse + volume baisse = tendance baissiere sans conviction (weak_bearish).",
    "<b>Consistance de tendance</b> : Le ratio de jours ou le prix est au-dessus de la SMA20 sur les 10 derniers jours mesure la solidite de la tendance. Un ratio > 60% renforce un signal haussier. Ce mecanisme ajuste la conviction a la hausse ou a la baisse.",
    "<b>Detection d'anomalies (z-score)</b> : Le rendement du dernier jour est normalise par la moyenne et l'ecart-type des rendements recents. Un z-score > 2 ou < -2 signale un mouvement inhabituel, potentiellement lie a un evenement (news, earnings, etc.).",
]
for item in alt_details:
    story.append(Paragraph(item, bullet_style, bulletText="▸"))

story.append(Spacer(1, 3*mm))
story.append(Paragraph(
    "<b>Ajustement de conviction :</b> La conviction de base depend du sentiment (strong_bullish = 8.0, "
    "capitulation = 7.5, weak_bearish = 6.0, weak_bullish = 5.5, neutral = 5.0). Elle est ensuite "
    "modulee par la consistance de tendance : une tendance consistante renforce les signaux haussiers "
    "et attenue les signaux baissiers, et inversement. Le score final est borne entre 3 et 9.5.",
    body_style
))

story.append(Spacer(1, 4*mm))
story.append(Paragraph("5.2 Analyse SWOT", h2_style))

story.append(make_swot_table(
    strengths=[
        "Approche originale : construit du sentiment a partir de donnees pures de marche",
        "Combinaison de trois signaux orthogonaux (divergence, tendance, anomalie)",
        "Detection de capitulation est un signal contrarian puissant",
        "Conviction dynamique ajustee par la consistance de tendance",
        "Z-score permet de flagger les evenements inhabituels",
    ],
    weaknesses=[
        "Proxy de sentiment seulement — pas de donnees alternatives reelles",
        "Seuils de divergence (2% prix, 20% volume) sont fixes et arbitraires",
        "Ne couvre pas les cryptos (limite aux equities)",
        "Fenetre de 5 jours pour la divergence est courte et sensible au bruit",
        "Pas de distinction entre types d'anomalies (earnings vs. news vs. technique)",
    ],
    opportunities=[
        "Integrer des flux de sentiment reels (Twitter/X, Reddit, news NLP)",
        "Ajouter l'analyse Finviz (signaux, secteurs) deja integree a la plateforme",
        "Incorporer des donnees on-chain pour les cryptomonnaies",
        "Utiliser un LLM pour analyser les earnings calls et press releases",
        "Backtester les seuils de divergence pour optimiser les parametres",
    ],
    threats=[
        "Les proxies de sentiment peuvent generer des faux positifs en periode d'expiration options",
        "Volume peut etre deforme par des operations institutionnelles (block trades)",
        "Z-score inefficace si la distribution des rendements n'est pas gaussienne",
        "Signaux de capitulation rares — risque de sur-reaction quand ils apparaissent",
        "Concurrence croissante dans l'alt-data reduit l'alpha des signaux simples",
    ],
    agent_color=AGENT_COLORS[3]
))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 6: CryptoAgent
# ═══════════════════════════════════════════════════════

story.append(Paragraph("6. CryptoAgent \u2014 Analyse crypto-actifs", h1_style))
story.append(hr())

crypto_info = [
    ("Role", "Analyse specialisee des cryptomonnaies avec indicateurs adaptes a leur volatilite"),
    ("Perimetre", "Instruments de classe 'crypto' : BTC (Bitcoin), ETH (Ethereum), LINK (Chainlink)"),
    ("Indicateurs", "SMA 7/21 (tendance rapide), RSI(14), momentum 7j, volatilite annualisee, Bollinger 20p, ratio volume 5j/20j"),
    ("Score", "Composite 0-10 pondere : momentum (35%), tendance (30%), RSI contrariant (20%), volume (15%)"),
    ("Signaux", "strong_buy, buy, sell, take_profit, accumulate, hold"),
    ("Horizon", "Court terme (short) pour signaux forts, moyen terme (medium) sinon"),
    ("Sortie", "Signal de trading par crypto avec score composite et stop ATR (2.5x)"),
]
story.append(make_info_table(crypto_info, header_color=AGENT_COLORS[4]))
story.append(Spacer(1, 4*mm))

story.append(Paragraph("6.1 Description et fonctionnement", h2_style))

story.append(Paragraph(
    "Le CryptoAgent est le dernier-ne de l'architecture. Il repond au besoin d'une analyse "
    "<b>specifiquement calibree pour les crypto-actifs</b>, dont la dynamique differe fondamentalement "
    "des actions : volatilite 3 a 5 fois superieure, cycles plus courts, volumes et liquidite variables, "
    "et absence de donnees fondamentales traditionnelles (P/E, dividendes).",
    body_style
))

story.append(Paragraph("<b>Differences cles avec les agents equity :</b>", body_style))

crypto_diffs = [
    "<b>Moyennes mobiles rapides (SMA 7/21)</b> : Contrairement au MacroAgent (SMA 50/200), le CryptoAgent utilise des periodes courtes adaptees aux cycles crypto. Le croisement SMA7/SMA21 detecte les changements de tendance en quelques jours plutot qu'en plusieurs mois.",
    "<b>Momentum 7 jours</b> : Plage elargie de [-50%, +50%] contre [-30%, +30%] pour les equities, refletant l'amplitude normale des mouvements crypto.",
    "<b>Seuils de volatilite adaptes</b> : Le regime de volatilite est juge 'eleve' au-dessus de 80% annualise (vs. ~25% pour les equities), 'faible' sous 40%. Cela evite de generer des alertes de volatilite perpetuelles.",
    "<b>Stop loss ATR x2.5</b> : Plus large que le x2 des equities pour absorber le bruit intraday des crypto sans declencher des stops prematures.",
    "<b>RSI seuils elargis (75/25)</b> : Les seuils de surachat/survente sont plus extremes (75/25 vs 70/30) car les cryptos restent souvent en conditions extremes plus longtemps.",
]
for item in crypto_diffs:
    story.append(Paragraph(item, bullet_style, bulletText="\u25b8"))

story.append(Spacer(1, 3*mm))
story.append(Paragraph("<b>Score composite et ponderation :</b>", body_style))
story.append(Paragraph(
    "Le score composite (0-10) combine quatre composantes : <b>momentum 7j (35%)</b> capte la dynamique "
    "de prix recente, <b>tendance SMA7/21 (30%)</b> confirme la direction, <b>RSI contrariant (20%)</b> "
    "penalise les exces, et <b>volume (15%)</b> valide la participation du marche. "
    "La ponderation lourde sur le momentum reflete la nature trend-following des marches crypto.",
    body_style
))

story.append(Spacer(1, 2*mm))
story.append(Paragraph(
    "<b>Hierarchie de decision :</b> Composite >= 7.5 + tendance haussiere + volume eleve \u2192 strong_buy "
    "(conviction 7-9). Composite >= 6.0 + tendance haussiere \u2192 buy (conviction 6-8). "
    "Composite <= 3.0 + tendance baissiere \u2192 sell (conviction 6-8.5). "
    "RSI > 75 \u2192 take_profit (conviction 7). RSI < 25 \u2192 accumulate (conviction 7). "
    "Sinon \u2192 hold (conviction 5).",
    body_style
))

story.append(Spacer(1, 4*mm))
story.append(Paragraph("6.2 Analyse SWOT", h2_style))

story.append(make_swot_table(
    strengths=[
        "Indicateurs specifiquement calibres pour la volatilite crypto",
        "SMA courtes (7/21) detectent les retournements rapidement",
        "Score composite multi-facteurs equilibre tendance et contrarian",
        "Stops ATR elargis (2.5x) evitent les declenchements prematures",
        "Couverture des 3 principales crypto (BTC, ETH, LINK)",
    ],
    weaknesses=[
        "Perimetre limite a 3 actifs (pas de SOL, AVAX, etc.)",
        "Pas de donnees on-chain (hashrate, adresses actives, flows)",
        "Volume simule — pas de donnees de volume reel des exchanges",
        "Indicateurs purement techniques, pas de sentiment social (Twitter, Reddit)",
        "Seuils fixes (75/25 RSI, 80%/40% vol) non optimises par backtesting",
    ],
    opportunities=[
        "Integrer des donnees on-chain via APIs (Glassnode, IntoTheBlock)",
        "Ajouter un sentiment social crypto (Crypto Fear &amp; Greed Index)",
        "Etendre a d'autres actifs (SOL, AVAX, DOT, stablecoins)",
        "Integrer les flux d'ETFs crypto (IBIT, ETHA) deja presents dans la plateforme",
        "Ajouter la correlation BTC/alts comme indicateur de regime crypto",
    ],
    threats=[
        "Volatilite extreme peut rendre les signaux techniques obsoletes en heures",
        "Evenements regulatoires imprevisibles (interdictions, reglementations)",
        "Manipulation de marche (wash trading, pump &amp; dump) fausse les volumes",
        "Forks, hacks d'exchanges, ou defaillances de protocole non detectables",
        "Correlation croissante crypto/actions reduit le benefice de diversification",
    ],
    agent_color=AGENT_COLORS[4]
))

story.append(PageBreak())

# ═══════════════════════════════════════════════════════
# SECTION 7: Synthese Comparative
# ═══════════════════════════════════════════════════════

story.append(Paragraph("7. Synthese comparative et conclusion", h1_style))
story.append(hr())

story.append(Paragraph(
    "Le tableau ci-dessous resume les caracteristiques cles de chaque agent pour une comparaison rapide :",
    body_style
))

# Comparison table
comp_header_style = ParagraphStyle("CompH", parent=body_style, fontSize=8.5, textColor=white, fontName="Helvetica-Bold", alignment=TA_CENTER)
comp_cell_style = ParagraphStyle("CompC", parent=body_style, fontSize=8.5, leading=11, alignment=TA_CENTER)
comp_cell_left = ParagraphStyle("CompCL", parent=body_style, fontSize=8.5, leading=11)

col_widths = [28*mm, 38*mm, 38*mm, 28*mm, 38*mm]

comp_data = [
    [Paragraph("<b>Agent</b>", comp_header_style),
     Paragraph("<b>Perimetre</b>", comp_header_style),
     Paragraph("<b>Indicateurs cles</b>", comp_header_style),
     Paragraph("<b>Horizon</b>", comp_header_style),
     Paragraph("<b>Type de signal</b>", comp_header_style)],

    [Paragraph("MacroAgent", comp_cell_style),
     Paragraph("SPY, QQQ, DIA", comp_cell_style),
     Paragraph("SMA 50/200, RSI(14), Mom. 20j", comp_cell_left),
     Paragraph("Moyen terme", comp_cell_style),
     Paragraph("Stance macro (risk-on / off / neutral)", comp_cell_left)],

    [Paragraph("FactorAgent", comp_cell_style),
     Paragraph("Actions (equity)", comp_cell_style),
     Paragraph("Momentum 12-1m, Qualite (vol), RSI", comp_cell_left),
     Paragraph("Moyen terme", comp_cell_style),
     Paragraph("Tilt (over / under / neutral)", comp_cell_left)],

    [Paragraph("Microstructure", comp_cell_style),
     Paragraph("Tous instruments", comp_cell_style),
     Paragraph("Bollinger, Volume, ATR, S/R", comp_cell_left),
     Paragraph("Court terme", comp_cell_style),
     Paragraph("Signal trading (buy/sell/hold...)", comp_cell_left)],

    [Paragraph("AltDataAgent", comp_cell_style),
     Paragraph("Actions (equity)", comp_cell_style),
     Paragraph("Div. prix-vol, Tendance, Z-score", comp_cell_left),
     Paragraph("Court/moyen", comp_cell_style),
     Paragraph("Sentiment (bullish/bearish/...)", comp_cell_left)],

    [Paragraph("CryptoAgent", comp_cell_style),
     Paragraph("BTC, ETH, LINK", comp_cell_style),
     Paragraph("SMA 7/21, Mom. 7j, Vol regime", comp_cell_left),
     Paragraph("Court terme", comp_cell_style),
     Paragraph("Signal crypto (strong_buy/buy/sell/hold)", comp_cell_left)],
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
story.append(Paragraph("Tableau 1 — Comparatif des cinq agents Thesium.finance", caption_style))

story.append(Spacer(1, 6*mm))

story.append(Paragraph("<b>Complementarite des agents</b>", h3_style))
story.append(Paragraph(
    "La force de l'architecture reside dans la <b>complementarite</b> des cinq agents. Le MacroAgent "
    "definit le cadre (faut-il prendre du risque ?), le FactorAgent identifie les meilleurs candidats "
    "(dans quoi investir ?), le MicrostructureAgent optimise le timing (quand entrer/sortir ?), "
    "l'AltDataAgent apporte un regard contrarian (y a-t-il des signaux caches ?), "
    "et le CryptoAgent couvre la classe d'actifs numeriques avec des indicateurs adaptes a leur volatilite.",
    body_style
))

story.append(Paragraph(
    "Ensemble, ils couvrent les cinq dimensions essentielles de la decision d'investissement : "
    "le <b>regime</b>, la <b>selection</b>, le <b>timing</b>, le <b>sentiment</b> et la <b>couverture crypto</b>. "
    "Cette separation permet au comite d'investissement (IC) de ponderer les avis selon le contexte : en marche "
    "fortement tendanciel, le MacroAgent domine ; en range, le MicrostructureAgent et l'AltDataAgent "
    "prennent le relais ; sur les cryptomonnaies, le CryptoAgent fournit des signaux calibres "
    "pour leur volatilite specifique.",
    body_style
))

story.append(Spacer(1, 4*mm))
story.append(Paragraph("<b>Axes d'evolution prioritaires</b>", h3_style))

evolution_items = [
    "<b>Donnees fondamentales</b> : L'integration de ratios financiers (P/E, ROE, dette) enrichirait considerablement le FactorAgent avec un veritable facteur Value.",
    "<b>Donnees alternatives reelles</b> : Flux de sentiment (NLP sur news, reseaux sociaux), donnees on-chain crypto, et signaux Finviz sectoriels transformeraient l'AltDataAgent en veritable moteur d'alpha.",
    "<b>Machine Learning</b> : Des modeles de regime-switching (HMM) pour le MacroAgent et d'optimisation des ponderations factorielles amelioreraient l'adaptabilite du systeme.",
    "<b>Backtesting systematique</b> : Valider les parametres (seuils RSI, periodes SMA, ponderations) sur des donnees historiques longues pour confirmer la robustesse statistique.",
    "<b>Agent de consensus</b> : Un MetaAgent pourrait synthetiser les signaux des cinq agents en une recommandation unifiee avec gestion de conflits et allocation cross-asset (equity + crypto).",
]
for item in evolution_items:
    story.append(Paragraph(item, bullet_style, bulletText="▸"))

story.append(Spacer(1, 6*mm))
story.append(hr())
story.append(Paragraph(
    "<i>Document genere automatiquement par Perplexity Computer pour Thesium.finance. "
    "Les analyses SWOT sont basees sur l'examen du code source (agents.py, 629 lignes) "
    "et les pratiques etablies en gestion quantitative.</i>",
    ParagraphStyle("Disclaimer", parent=body_style, fontSize=8, textColor=MED_TEAL, alignment=TA_CENTER)
))


# ══════════════════════════════════════════════════════════
# BUILD
# ══════════════════════════════════════════════════════════

output_path = "/home/user/workspace/thesium-desk/Thesium_Architecture_Agents.pdf"

doc = SimpleDocTemplate(
    output_path,
    pagesize=A4,
    leftMargin=LEFT_MARGIN,
    rightMargin=RIGHT_MARGIN,
    topMargin=TOP_MARGIN,
    bottomMargin=BOT_MARGIN,
    title="Thesium.finance — Architecture des Agents",
    author="Perplexity Computer",
)

doc.build(story, onFirstPage=cover_page, onLaterPages=later_pages)
print(f"PDF generated: {output_path}")
