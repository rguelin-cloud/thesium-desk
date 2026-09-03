#!/usr/bin/env python3
"""Generate the Nextones Desk User Guide PDF in French — v2 (12-15 pages)."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    HRFlowable, NextPageTemplate, PageTemplate, Frame, KeepTogether
)
from reportlab.platypus.doctemplate import BaseDocTemplate
from reportlab.pdfgen import canvas
import os

# ─── Brand Colors ───────────────────────────────────────────────────
TEAL_PRIMARY  = HexColor("#20808D")
TEAL_DARK     = HexColor("#13343B")
TEAL_DEEP     = HexColor("#115058")
TEAL_MEDIUM   = HexColor("#2E565D")
OFF_WHITE     = HexColor("#FCFAF6")
PAPER_WHITE   = HexColor("#F3F3EE")
WARM_BEIGE    = HexColor("#E5E3D4")
DARK_NAVY     = HexColor("#091717")
LIGHT_TEAL    = HexColor("#D6F5FA")

PAGE_W, PAGE_H = A4
MARGIN_LEFT   = 2.0 * cm
MARGIN_RIGHT  = 2.0 * cm
MARGIN_TOP    = 2.2 * cm
MARGIN_BOTTOM = 2.2 * cm
AVAIL_W       = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT

OUTPUT_PATH = "/home/user/workspace/thesium-desk/Guide_Utilisateur_Nextones_Desk.pdf"

# ─── Styles ─────────────────────────────────────────────────────────
styles = {
    "h1": ParagraphStyle(
        "H1", fontName="Helvetica-Bold", fontSize=18, leading=23,
        textColor=TEAL_DARK, spaceBefore=14, spaceAfter=4,
    ),
    "h2": ParagraphStyle(
        "H2", fontName="Helvetica-Bold", fontSize=12.5, leading=16,
        textColor=TEAL_PRIMARY, spaceBefore=10, spaceAfter=4,
    ),
    "h3": ParagraphStyle(
        "H3", fontName="Helvetica-Bold", fontSize=10.5, leading=13,
        textColor=TEAL_DEEP, spaceBefore=8, spaceAfter=3,
    ),
    "body": ParagraphStyle(
        "Body", fontName="Helvetica", fontSize=9.5, leading=13,
        textColor=TEAL_DARK, alignment=TA_JUSTIFY, spaceAfter=5,
    ),
    "bullet": ParagraphStyle(
        "Bullet", fontName="Helvetica", fontSize=9.5, leading=13,
        textColor=TEAL_DARK, alignment=TA_LEFT, spaceAfter=2,
        leftIndent=16, bulletIndent=4,
    ),
    "table_header": ParagraphStyle(
        "TableHeader", fontName="Helvetica-Bold", fontSize=8.5, leading=11,
        textColor=white, alignment=TA_LEFT,
    ),
    "table_cell": ParagraphStyle(
        "TableCell", fontName="Helvetica", fontSize=8.5, leading=11,
        textColor=TEAL_DARK, alignment=TA_LEFT,
    ),
    "table_cell_bold": ParagraphStyle(
        "TableCellBold", fontName="Helvetica-Bold", fontSize=8.5, leading=11,
        textColor=TEAL_DARK, alignment=TA_LEFT,
    ),
    "note": ParagraphStyle(
        "Note", fontName="Helvetica-Oblique", fontSize=8.5, leading=11,
        textColor=TEAL_MEDIUM, alignment=TA_LEFT, spaceAfter=5,
        leftIndent=10, rightIndent=10,
        borderColor=TEAL_PRIMARY, borderWidth=0.5,
        borderPadding=6, backColor=PAPER_WHITE,
    ),
    "toc_entry": ParagraphStyle(
        "TOCEntry", fontName="Helvetica", fontSize=10.5, leading=16,
        textColor=TEAL_DARK, spaceAfter=1,
    ),
}


# ─── Helpers ────────────────────────────────────────────────────────
def teal_divider():
    return HRFlowable(width="100%", thickness=1.2, color=TEAL_PRIMARY, spaceAfter=6, spaceBefore=2)

def make_table(headers, rows, col_widths=None):
    header_cells = [Paragraph(h, styles["table_header"]) for h in headers]
    data = [header_cells]
    for row in rows:
        data.append([Paragraph(str(c), styles["table_cell"]) for c in row])
    if col_widths is None:
        n = len(headers)
        col_widths = [AVAIL_W / n] * n
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.3, WARM_BEIGE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [OFF_WHITE, white]),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t

def B(text):
    return Paragraph(f"\u2022  {text}", styles["bullet"])

def P(text):
    return Paragraph(text, styles["body"])

def N(text):
    return Paragraph(text, styles["note"])

def H1(text):
    return Paragraph(text, styles["h1"])

def H2(text):
    return Paragraph(text, styles["h2"])

def H3(text):
    return Paragraph(text, styles["h3"])

def SP(h=4):
    return Spacer(1, h)


# ─── Custom Doc with Cover ──────────────────────────────────────────
def draw_cover(canvas_obj, doc):
    """Draw the cover page background and text."""
    c = canvas_obj
    c.saveState()
    # Full dark background
    c.setFillColor(DARK_NAVY)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Accent bar
    c.setFillColor(TEAL_PRIMARY)
    bar_y = PAGE_H * 0.50
    c.rect(0, bar_y, PAGE_W, 3, fill=1, stroke=0)

    # Title
    y_base = PAGE_H * 0.62
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 32)
    c.drawString(MARGIN_LEFT + 0.5*cm, y_base, "Guide Utilisateur")
    c.drawString(MARGIN_LEFT + 0.5*cm, y_base - 42, "Nextones Desk")

    # Subtitle
    c.setFillColor(LIGHT_TEAL)
    c.setFont("Helvetica", 13)
    c.drawString(MARGIN_LEFT + 0.5*cm, y_base - 80, "Version 2.0 \u2014 Mars 2026")

    # Description
    c.setFillColor(HexColor("#8FBFC6"))
    c.setFont("Helvetica", 10.5)
    c.drawString(MARGIN_LEFT + 0.5*cm, y_base - 106,
                 "Fund OS pilot\u00e9 par IA pour la gestion d\u2019investissements")

    # Bottom branding
    by = 3 * cm
    c.setFillColor(TEAL_PRIMARY)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(MARGIN_LEFT + 0.5*cm, by, "NEXTONES.FINANCE")
    c.setFillColor(HexColor("#8FBFC6"))
    c.setFont("Helvetica", 8)
    c.drawString(MARGIN_LEFT + 0.5*cm, by - 14,
                 "Document g\u00e9n\u00e9r\u00e9 par Perplexity Computer")

    # Decorative
    c.setStrokeColor(TEAL_PRIMARY)
    c.setLineWidth(1)
    cx = PAGE_W - MARGIN_RIGHT - 1.5*cm
    c.circle(cx, by + 8, 0.35*cm, fill=0, stroke=1)
    c.setFillColor(TEAL_PRIMARY)
    c.circle(cx - 1.5*cm, by - 2, 0.15*cm, fill=1, stroke=0)

    c.restoreState()


def draw_normal_header_footer(canvas_obj, doc):
    """Draw header/footer on content pages."""
    c = canvas_obj
    page_num = doc.page  # 1-based, cover=1, TOC starts at 2
    content_page = page_num - 1  # subtract cover

    c.saveState()
    # Header
    c.setStrokeColor(TEAL_PRIMARY)
    c.setLineWidth(0.6)
    yh = PAGE_H - 1.4*cm
    c.line(MARGIN_LEFT, yh, PAGE_W - MARGIN_RIGHT, yh)
    c.setFont("Helvetica", 7)
    c.setFillColor(TEAL_MEDIUM)
    c.drawString(MARGIN_LEFT, yh + 3, "Guide Utilisateur \u2014 Nextones Desk")
    c.drawRightString(PAGE_W - MARGIN_RIGHT, yh + 3, "NEXTONES.FINANCE")

    # Footer
    yf = 1.4*cm
    c.setStrokeColor(WARM_BEIGE)
    c.setLineWidth(0.4)
    c.line(MARGIN_LEFT, yf, PAGE_W - MARGIN_RIGHT, yf)
    c.setFont("Helvetica", 7)
    c.setFillColor(TEAL_MEDIUM)
    c.drawString(MARGIN_LEFT, yf - 10, "Version 2.0 \u2014 Mars 2026")
    c.drawCentredString(PAGE_W / 2, yf - 10, "\u00a9 NEXTONES.FINANCE")
    c.drawRightString(PAGE_W - MARGIN_RIGHT, yf - 10,
                      f"Page {content_page}")

    c.restoreState()


# ─── Build story ────────────────────────────────────────────────────
def build_story():
    s = []

    # Cover page is handled by the template callback
    s.append(Spacer(1, 1))
    s.append(NextPageTemplate("normal"))
    s.append(PageBreak())

    # ── TABLE OF CONTENTS ──
    s.append(H1("Table des mati\u00e8res"))
    s.append(teal_divider())
    toc = [
        "1.   Introduction",
        "2.   Connexion et authentification",
        "3.   Dashboard Today",
        "4.   Th\u00e8ses d\u2019investissement",
        "5.   Orders &amp; Executions",
        "6.   Market Intel",
        "7.   Macro US",
        "8.   IC Memos",
        "9.   Backtest",
        "10. Administration",
        "11. FAQ et d\u00e9pannage",
    ]
    for item in toc:
        parts = item.split("  ", 1)
        if len(parts) == 2:
            s.append(Paragraph(f'<b>{parts[0]}</b> {parts[1]}', styles["toc_entry"]))
        else:
            s.append(Paragraph(f'<b>{item}</b>', styles["toc_entry"]))
    s.append(SP(8))
    s.append(N(
        "<b>Convention typographique\u202f:</b> les \u00e9l\u00e9ments d\u2019interface "
        "apparaissent <b>en gras</b>, les termes techniques en <i>italique</i>. "
        "Les raccourcis clavier sont indiqu\u00e9s entre crochets [Ctrl+R]."
    ))
    s.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    #  1. INTRODUCTION
    # ═══════════════════════════════════════════════════════════════
    s.append(H1("1. Introduction"))
    s.append(teal_divider())

    s.append(H2("1.1 Pr\u00e9sentation de Nextones Desk"))
    s.append(P(
        "Nextones Desk est un <b>Fund OS</b> (syst\u00e8me d\u2019exploitation pour fonds "
        "d\u2019investissement) pilot\u00e9 par intelligence artificielle. La plateforme "
        "automatise la cha\u00eene de recherche\u202f: cinq agents IA sp\u00e9cialis\u00e9s "
        "(MacroAgent, FactorAgent, MicrostructureAgent, CryptoAgent, AltDataAgent) "
        "analysent en continu les donn\u00e9es de march\u00e9, g\u00e9n\u00e8rent des "
        "<i>th\u00e8ses d\u2019investissement</i> et proposent des ordres, le tout "
        "supervis\u00e9 par les \u00e9quipes humaines via l\u2019interface web."
    ))
    s.append(P(
        "L\u2019objectif est de fournir un processus de d\u00e9cision rigoureux, "
        "tra\u00e7able et r\u00e9p\u00e9table\u202f: chaque th\u00e8se g\u00e9n\u00e9r\u00e9e est document\u00e9e, "
        "chaque ordre passe par un contr\u00f4le de risque automatique (VaR 95\u202f%, limites de position, "
        "limites sectorielles, surveillance du drawdown), et chaque "
        "cycle de d\u00e9cision produit un m\u00e9mo d\u2019audit \u00e0 destination du "
        "comit\u00e9 d\u2019investissement."
    ))

    s.append(H2("1.2 Architecture technique"))
    s.append(P(
        "Nextones Desk repose sur un <b>backend FastAPI</b> (Python 3.11+) "
        "servi par uvicorn, avec une base de donn\u00e9es SQLite. Le frontend est "
        "construit en HTML5/CSS3 avec JavaScript vanilla et Chart.js pour les graphiques. "
        "L\u2019authentification utilise des <i>tokens JWT</i> (expiration 24h) "
        "et le hachage bcrypt pour les mots de passe."
    ))
    s.append(P(
        "Les API externes utilis\u00e9es incluent\u202f: Yahoo Finance (backtest), "
        "CoinGecko (crypto live), FRED (donn\u00e9es macro), GDELT et USGS (risque g\u00e9opolitique), "
        "et Finviz (signaux actions). Toutes les donn\u00e9es sont agr\u00e9g\u00e9es c\u00f4t\u00e9 serveur "
        "avant d\u2019\u00eatre expos\u00e9es via des endpoints REST."
    ))

    s.append(H2("1.3 Public cible"))
    s.append(P("Ce guide s\u2019adresse aux\u202f:"))
    s.append(B("<b>Gestionnaires de portefeuille</b> \u2014 pilotage quotidien des positions et validation des ordres"))
    s.append(B("<b>Analystes</b> \u2014 revue des th\u00e8ses IA, backtests, export de donn\u00e9es"))
    s.append(B("<b>Superviseurs / Compliance</b> \u2014 consultation des m\u00e9mos IC pour l\u2019audit r\u00e9glementaire"))
    s.append(B("<b>Administrateurs</b> \u2014 gestion des utilisateurs, configuration de l\u2019instance, int\u00e9gration API"))
    s.append(SP(4))
    s.append(N(
        "<b>Pr\u00e9requis\u202f:</b> un navigateur web r\u00e9cent (Chrome, Firefox, Edge) "
        "et un acc\u00e8s r\u00e9seau \u00e0 l\u2019instance Nextones Desk de votre organisation."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  2. CONNEXION ET AUTHENTIFICATION
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("2. Connexion et authentification"))
    s.append(teal_divider())

    s.append(H2("2.1 Premi\u00e8re connexion"))
    s.append(P(
        "Ouvrez votre navigateur et acc\u00e9dez \u00e0 l\u2019URL fournie par votre "
        "administrateur (par exemple\u202f: <b>https://desk.nextones.finance</b>). "
        "Saisissez votre <b>nom d\u2019utilisateur</b> et votre <b>mot de passe</b> "
        "dans le formulaire de connexion. Apr\u00e8s authentification r\u00e9ussie, "
        "vous arrivez directement sur l\u2019onglet <b>Today</b>."
    ))
    s.append(P(
        "Lors de la premi\u00e8re utilisation de l\u2019instance, un compte administrateur "
        "par d\u00e9faut est cr\u00e9\u00e9 automatiquement. Il est fortement recommand\u00e9 de "
        "modifier le mot de passe par d\u00e9faut imm\u00e9diatement apr\u00e8s la premi\u00e8re connexion."
    ))

    s.append(H2("2.2 Jetons JWT"))
    s.append(P(
        "L\u2019authentification repose sur des <b>jetons JWT</b> (<i>JSON Web Tokens</i>). "
        "Apr\u00e8s connexion r\u00e9ussie, le serveur d\u00e9livre un jeton sign\u00e9 avec une "
        "<b>dur\u00e9e de validit\u00e9 de 24 heures</b>. Ce jeton est stock\u00e9 localement "
        "dans le navigateur et envoy\u00e9 automatiquement avec chaque requ\u00eate API."
    ))
    s.append(P(
        "Si le jeton expire, l\u2019interface redirige automatiquement vers la page "
        "de connexion. Les mots de passe sont hach\u00e9s avec <b>bcrypt</b> c\u00f4t\u00e9 serveur "
        "\u2014 ils ne sont jamais stock\u00e9s en clair."
    ))

    s.append(H2("2.3 R\u00f4les et permissions (RBAC)"))
    s.append(P(
        "Nextones Desk impl\u00e9mente un syst\u00e8me de <b>contr\u00f4le d\u2019acc\u00e8s bas\u00e9 sur les r\u00f4les</b> "
        "(RBAC) avec une hi\u00e9rarchie \u00e0 quatre niveaux\u202f:"
    ))
    s.append(make_table(
        ["R\u00f4le", "Niveau", "Droits"],
        [
            ["Viewer", "0", "Lecture seule \u2014 dashboards, rapports, consultation des donn\u00e9es"],
            ["Analyst", "1", "Viewer + propositions de th\u00e8ses, backtests, export CSV"],
            ["Manager", "2", "Analyst + validation des th\u00e8ses, lancement de cycles d\u2019ex\u00e9cution/ingestion"],
            ["Admin", "3", "Acc\u00e8s total + gestion utilisateurs, configuration risk, administration"],
        ],
        col_widths=[2.2*cm, 1.5*cm, AVAIL_W - 3.7*cm],
    ))

    s.append(H2("2.4 Endpoints prot\u00e9g\u00e9s"))
    s.append(P("Les endpoints suivants sont soumis \u00e0 des restrictions de r\u00f4le\u202f:"))
    s.append(make_table(
        ["Endpoint", "M\u00e9thode", "R\u00f4le minimum"],
        [
            ["/api/orders/execute-cycle", "POST", "Manager"],
            ["/api/run-agents", "POST", "Manager"],
            ["/api/run-ingestion", "POST", "Manager"],
            ["/api/risk-config", "PUT", "Admin"],
            ["/api/admin/*", "GET/POST/PUT/DELETE", "Admin"],
        ],
        col_widths=[5.5*cm, 3.5*cm, AVAIL_W - 9.0*cm],
    ))
    s.append(SP(3))
    s.append(N(
        "<b>S\u00e9curit\u00e9\u202f:</b> toutes les actions sont journalis\u00e9es. "
        "L\u2019historique des connexions et des op\u00e9rations est consultable "
        "par les administrateurs dans le panneau d\u2019administration."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  3. DASHBOARD TODAY
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("3. Dashboard Today"))
    s.append(teal_divider())

    s.append(P(
        "L\u2019onglet <b>Today</b> est votre point d\u2019entr\u00e9e quotidien. "
        "Il pr\u00e9sente une vue consolid\u00e9e de l\u2019\u00e9tat du portefeuille, "
        "des m\u00e9triques de risque et de l\u2019activit\u00e9 r\u00e9cente du syst\u00e8me."
    ))

    s.append(H2("3.1 R\u00e9sum\u00e9 du portefeuille"))
    s.append(P("La section sup\u00e9rieure affiche quatre indicateurs cl\u00e9s\u202f:"))
    s.append(B("<b>Total Value</b> \u2014 Valeur totale du portefeuille (positions + cash), mise \u00e0 jour en temps r\u00e9el"))
    s.append(B("<b>Cash disponible</b> \u2014 Liquidit\u00e9s non investies, disponibles pour de nouvelles positions"))
    s.append(B("<b>P&amp;L total</b> \u2014 Gain ou perte cumul\u00e9(e) depuis l\u2019ouverture du portefeuille"))
    s.append(B("<b>P&amp;L journalier</b> \u2014 Variation de valeur sur la s\u00e9ance en cours"))
    s.append(SP(3))
    s.append(P(
        "Les valeurs positives sont affich\u00e9es en <b>vert</b>, les valeurs n\u00e9gatives "
        "en <b>rouge</b>. Trois compteurs synth\u00e9tiques compl\u00e8tent la vue\u202f: "
        "th\u00e8ses actives, ordres en attente et nombre de positions."
    ))

    s.append(H2("3.2 Tableau des positions"))
    s.append(P("Le tableau central liste l\u2019ensemble des positions ouvertes\u202f:"))
    s.append(make_table(
        ["Colonne", "Description"],
        [
            ["Ticker", "Code de l\u2019instrument (ex.\u202f: AAPL, MSFT)"],
            ["Quantit\u00e9", "Nombre de titres d\u00e9tenus"],
            ["Prix moyen d\u2019achat", "Co\u00fbt moyen pond\u00e9r\u00e9 d\u2019acquisition"],
            ["Prix actuel", "Dernier cours disponible"],
            ["P&amp;L non r\u00e9alis\u00e9 (%)", "Gain/perte latent(e) en pourcentage"],
            ["Poids", "Poids de la position dans le portefeuille"],
        ],
        col_widths=[4*cm, AVAIL_W - 4*cm],
    ))

    s.append(H2("3.3 Courbe d\u2019\u00e9quit\u00e9 et m\u00e9triques de risque"))
    s.append(P(
        "Le graphique Chart.js affiche l\u2019\u00e9volution de la valeur totale du portefeuille "
        "sur les <b>30 derniers jours</b>. Survolez la courbe pour afficher la valeur "
        "exacte \u00e0 une date donn\u00e9e. Deux m\u00e9triques de risque sont affich\u00e9es en permanence\u202f:"
    ))
    s.append(B(
        "<b>VaR 95\u202f% (1 jour)</b> \u2014 <i>Value at Risk</i>\u202f: estimation de la perte maximale "
        "probable sur une journ\u00e9e avec un niveau de confiance de 95\u202f%."
    ))
    s.append(B(
        "<b>Drawdown maximum</b> \u2014 Perte maximale observ\u00e9e entre un pic et un creux de la "
        "courbe d\u2019\u00e9quit\u00e9, exprim\u00e9e en pourcentage."
    ))

    s.append(H2("3.4 Fil d\u2019\u00e9v\u00e9nements"))
    s.append(P(
        "Le panneau d\u2019activit\u00e9 affiche les <b>20 derniers \u00e9v\u00e9nements</b>\u202f: "
        "th\u00e8ses g\u00e9n\u00e9r\u00e9es, ordres cr\u00e9\u00e9s, ex\u00e9cutions confirm\u00e9es, alertes de risque. "
        "Les \u00e9v\u00e9nements sont cod\u00e9s par couleur\u202f: <b>turquoise</b> pour les th\u00e8ses, "
        "<b>bleu</b> pour les ordres, <b>vert</b> pour les ex\u00e9cutions r\u00e9ussies, "
        "<b>orange</b> pour les alertes, <b>rouge</b> pour les rejets."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  4. THESES
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("4. Th\u00e8ses d\u2019investissement"))
    s.append(teal_divider())

    s.append(P(
        "Cet onglet centralise l\u2019ensemble des <b>th\u00e8ses d\u2019investissement</b> "
        "g\u00e9n\u00e9r\u00e9es par les cinq agents IA. Chaque th\u00e8se repr\u00e9sente une "
        "recommandation argument\u00e9e pour acheter, vendre ou conserver un titre."
    ))

    s.append(H2("4.1 Liste et colonnes"))
    s.append(make_table(
        ["Colonne", "Description"],
        [
            ["Ticker", "Instrument concern\u00e9"],
            ["Agent", "Agent IA auteur (MacroAgent, FactorAgent, MicrostructureAgent, CryptoAgent, AltDataAgent)"],
            ["Classe d\u2019actifs", "Actions, Crypto, ETF, etc."],
            ["Score de conviction", "Note de 1 \u00e0 10 refl\u00e9tant la confiance de l\u2019agent"],
            ["Horizon", "Court terme (<\u202f5j), moyen terme (5-20j), long terme (>\u202f20j)"],
            ["Action propos\u00e9e", "Buy, Sell ou Hold"],
            ["Statut", "Active, Approuv\u00e9e, Archiv\u00e9e"],
        ],
        col_widths=[3.8*cm, AVAIL_W - 3.8*cm],
    ))

    s.append(H2("4.2 Filtres"))
    s.append(P("Utilisez la barre de filtres pour affiner la vue\u202f:"))
    s.append(B("<b>Par agent</b> \u2014 s\u00e9lectionnez un ou plusieurs agents"))
    s.append(B("<b>Par classe d\u2019actifs</b> \u2014 actions, crypto, ETF"))
    s.append(B("<b>Par statut</b> \u2014 active, approuv\u00e9e, archiv\u00e9e"))
    s.append(B("<b>Par ticker</b> \u2014 recherche libre par code instrument"))
    s.append(B("<b>Par score</b> \u2014 seuil minimum de conviction (curseur de 1 \u00e0 10)"))

    s.append(H2("4.3 Workflow d\u2019approbation"))
    s.append(P(
        "Pour qu\u2019une th\u00e8se d\u00e9clenche la cr\u00e9ation d\u2019un ordre, elle doit \u00eatre "
        "approuv\u00e9e par un utilisateur disposant du r\u00f4le <b>Manager</b> ou <b>Admin</b>. "
        "Cliquez sur le bouton <b>Approve</b> dans le d\u00e9tail de la th\u00e8se. "
        "Cette action est irr\u00e9versible\u202f: une th\u00e8se approuv\u00e9e sera prise en compte "
        "lors du prochain cycle de d\u00e9cision."
    ))
    s.append(N(
        "<b>Important\u202f:</b> seules les th\u00e8ses avec un score de conviction "
        "\u2265\u202f7 sont automatiquement propos\u00e9es \u00e0 l\u2019approbation. "
        "Les th\u00e8ses \u00e0 score inf\u00e9rieur restent visibles mais n\u00e9cessitent "
        "une approbation manuelle explicite."
    ))

    s.append(H2("4.4 Convergence entre agents"))
    s.append(P(
        "Lorsque plusieurs agents convergent sur un m\u00eame titre avec une m\u00eame "
        "direction (achat ou vente), la th\u00e8se est signal\u00e9e par un badge "
        "<b>Multi-Agent</b>. Inversement, une <b>divergence</b> est signal\u00e9e "
        "par un badge <b>Conflit</b>, invitant le gestionnaire "
        "\u00e0 examiner les analyses contradictoires avant de prendre une d\u00e9cision."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  5. ORDERS & EXECUTIONS
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("5. Orders &amp; Executions"))
    s.append(teal_divider())

    s.append(H2("5.1 Flux d\u2019ordres"))
    s.append(P(
        "Chaque ordre suit un parcours lin\u00e9aire pass\u00e9 par le <b>moteur de risque</b> "
        "avant ex\u00e9cution\u202f:"
    ))
    flow_data = [[
        Paragraph("<b>Pending</b>", styles["table_cell_bold"]),
        Paragraph("\u2192", styles["table_cell"]),
        Paragraph("<b>Approved</b>", styles["table_cell_bold"]),
        Paragraph("\u2192", styles["table_cell"]),
        Paragraph("<b>Filled</b>", styles["table_cell_bold"]),
    ]]
    flow_t = Table(flow_data, colWidths=[3*cm, 0.8*cm, 3*cm, 0.8*cm, 3*cm])
    flow_t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (0, 0), LIGHT_TEAL),
        ("BACKGROUND", (2, 0), (2, 0), LIGHT_TEAL),
        ("BACKGROUND", (4, 0), (4, 0), LIGHT_TEAL),
        ("BOX", (0, 0), (0, 0), 0.5, TEAL_PRIMARY),
        ("BOX", (2, 0), (2, 0), 0.5, TEAL_PRIMARY),
        ("BOX", (4, 0), (4, 0), 0.5, TEAL_PRIMARY),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    s.append(flow_t)
    s.append(SP(3))
    s.append(P(
        "Un ordre peut \u00e9galement \u00eatre <b>Rejected</b> (rejet\u00e9 par le contr\u00f4le de risque) "
        "ou <b>Cancelled</b> (annul\u00e9 manuellement par un Manager ou Admin)."
    ))

    s.append(H2("5.2 Tableau des ordres"))
    s.append(make_table(
        ["Colonne", "Description"],
        [
            ["ID", "Identifiant unique de l\u2019ordre"],
            ["Ticker", "Instrument concern\u00e9"],
            ["C\u00f4t\u00e9", "Buy (achat) ou Sell (vente)"],
            ["Quantit\u00e9", "Nombre de titres \u00e0 n\u00e9gocier"],
            ["Type", "Market (au march\u00e9) ou Limit (prix limite)"],
            ["Statut", "Pending, Approved, Filled, Rejected, Cancelled"],
            ["Th\u00e8se source", "Lien vers la th\u00e8se ayant g\u00e9n\u00e9r\u00e9 cet ordre"],
        ],
        col_widths=[3.2*cm, AVAIL_W - 3.2*cm],
    ))

    s.append(H2("5.3 Contr\u00f4le de risque"))
    s.append(P("Les v\u00e9rifications effectu\u00e9es par le moteur de risque incluent\u202f:"))
    s.append(B("<b>Exposition maximale</b> \u2014 v\u00e9rifie que la valeur totale du portefeuille ne d\u00e9passe pas le plafond autoris\u00e9"))
    s.append(B("<b>Concentration</b> \u2014 aucune position individuelle ne doit exc\u00e9der le seuil (par d\u00e9faut\u202f: 15\u202f%)"))
    s.append(B("<b>VaR marginal</b> \u2014 l\u2019ajout de la position ne doit pas augmenter la VaR au-del\u00e0 du budget de risque"))
    s.append(B("<b>Limites sectorielles</b> \u2014 diversification entre secteurs"))
    s.append(B("<b>Drawdown monitoring</b> \u2014 surveillance continue du drawdown maximal"))

    s.append(H2("5.4 Ex\u00e9cutions (Fills)"))
    s.append(P("Une fois un ordre ex\u00e9cut\u00e9, les d\u00e9tails apparaissent dans le tableau des fills\u202f:"))
    s.append(make_table(
        ["Colonne", "Description"],
        [
            ["Prix d\u2019ex\u00e9cution", "Prix auquel la transaction a \u00e9t\u00e9 r\u00e9alis\u00e9e"],
            ["Quantit\u00e9", "Nombre de titres effectivement n\u00e9goci\u00e9s"],
            ["Slippage", "\u00c9cart entre le prix demand\u00e9 et le prix obtenu (0,1\u202f% en paper trading)"],
            ["Horodatage", "Date et heure pr\u00e9cises de l\u2019ex\u00e9cution"],
        ],
        col_widths=[3.5*cm, AVAIL_W - 3.5*cm],
    ))
    s.append(SP(3))
    s.append(N(
        "<b>Paper Trading\u202f:</b> par d\u00e9faut, Nextones Desk fonctionne en mode simulation. "
        "Toutes les ex\u00e9cutions appliquent un slippage r\u00e9aliste de 0,1\u202f%. "
        "Aucun ordre r\u00e9el n\u2019est envoy\u00e9 aux march\u00e9s."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  6. MARKET INTEL
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("6. Market Intel"))
    s.append(teal_divider())

    s.append(P(
        "L\u2019onglet <b>Market Intel</b> fournit une veille march\u00e9 en temps r\u00e9el, "
        "organis\u00e9e en trois sous-sections compl\u00e9mentaires."
    ))

    s.append(H2("6.1 Stock Signals (Finviz)"))
    s.append(P(
        "Cette section affiche les <b>signaux techniques</b> d\u00e9tect\u00e9s sur les actions "
        "am\u00e9ricaines via Finviz. Les signaux couvrent les screeners les plus courants\u202f: "
        "surachat/survente RSI, cassures de moyennes mobiles, volumes anormaux, etc. "
        "Chaque signal est accompagn\u00e9 du ticker, du type de signal et de l\u2019horodatage."
    ))

    s.append(H2("6.2 Dynamique Sectorielle"))
    s.append(P(
        "Vue d\u2019ensemble de la performance des <b>11 secteurs GICS</b> sur plusieurs horizons "
        "(1j, 5j, 1 mois, 3 mois). Un code couleur indique la force relative de chaque secteur. "
        "Cette vue aide \u00e0 identifier les rotations sectorielles en cours et \u00e0 calibrer "
        "l\u2019exposition sectorielle du portefeuille."
    ))

    s.append(H2("6.3 Crypto TOP 25"))
    s.append(P(
        "Tableau des <b>25 premi\u00e8res cryptomonnaies</b> par capitalisation, "
        "aliment\u00e9 en temps r\u00e9el par l\u2019API CoinGecko. Pour chaque actif, "
        "sont affich\u00e9s\u202f: prix actuel, variation 24h, variation 7j, volume 24h, "
        "et capitalisation de march\u00e9. Le CryptoAgent utilise ces donn\u00e9es "
        "pour g\u00e9n\u00e9rer ses th\u00e8ses sur les actifs num\u00e9riques."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  7. MACRO US
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("7. Macro US"))
    s.append(teal_divider())

    s.append(P(
        "L\u2019onglet <b>Macro US</b> centralise les indicateurs macro\u00e9conomiques "
        "am\u00e9ricains et les risques g\u00e9opolitiques, utilis\u00e9s par le MacroAgent "
        "pour d\u00e9terminer sa stance (Risk-On / Risk-Off / Neutre)."
    ))

    s.append(H2("7.1 Dashboard Vuln\u00e9rabilit\u00e9"))
    s.append(P(
        "Ce tableau de bord agr\u00e8ge les donn\u00e9es de la <b>Federal Reserve Economic Data (FRED)</b> "
        "pour \u00e9valuer la vuln\u00e9rabilit\u00e9 macro\u00e9conomique. Les indicateurs suivis incluent\u202f: "
        "taux directeurs, courbe de taux (2Y-10Y spread), inflation (CPI/PCE), "
        "emploi non-agricole (NFP), et indice de confiance des consommateurs."
    ))
    s.append(P(
        "Un <b>score de vuln\u00e9rabilit\u00e9 composite</b> (0-100) est calcul\u00e9 et affich\u00e9 "
        "avec un code couleur\u202f: vert (faible risque), orange (mod\u00e9r\u00e9), rouge (\u00e9lev\u00e9). "
        "Ce score influence directement le dimensionnement des positions propos\u00e9es par les agents."
    ))

    s.append(H2("7.2 Calendrier \u00e9conomique"))
    s.append(P(
        "Liste des <b>publications \u00e9conomiques majeures</b> \u00e0 venir (Fed, BLS, ISM, etc.) "
        "avec leur date, heure et impact attendu. Les \u00e9v\u00e9nements \u00e0 fort impact sont "
        "mis en surbrillance. Le syst\u00e8me peut r\u00e9duire automatiquement l\u2019exposition "
        "avant une publication majeure."
    ))

    s.append(H2("7.3 Risque g\u00e9opolitique"))
    s.append(P(
        "Section aliment\u00e9e par les API <b>GDELT</b> (Global Database of Events, "
        "Language and Tone) et <b>USGS</b> (U.S. Geological Survey). "
        "Elle surveille les tensions g\u00e9opolitiques, les catastrophes naturelles "
        "et les \u00e9v\u00e9nements susceptibles d\u2019impacter les march\u00e9s financiers. "
        "Un indice de risque g\u00e9opolitique est calcul\u00e9 et int\u00e9gr\u00e9 dans "
        "l\u2019analyse du MacroAgent."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  8. IC MEMOS
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("8. IC Memos"))
    s.append(teal_divider())

    s.append(P(
        "\u00c0 chaque cycle de d\u00e9cision, Nextones Desk g\u00e9n\u00e8re automatiquement "
        "un <b>m\u00e9mo du comit\u00e9 d\u2019investissement</b> (IC Memo). Ces documents "
        "constituent la trace d\u2019audit r\u00e9glementaire de chaque d\u00e9cision."
    ))

    s.append(H2("8.1 Contenu d\u2019un m\u00e9mo"))
    s.append(P("Chaque m\u00e9mo contient les sections suivantes\u202f:"))
    s.append(B("<b>R\u00e9sum\u00e9 macro</b> \u2014 vue d\u2019ensemble des conditions de march\u00e9 selon le MacroAgent"))
    s.append(B("<b>Tilts factoriels</b> \u2014 positionnement momentum/qualit\u00e9/RSI issu du FactorAgent"))
    s.append(B("<b>R\u00e9sum\u00e9s des th\u00e8ses</b> \u2014 synth\u00e8se de chaque th\u00e8se retenue lors du cycle"))
    s.append(B("<b>Changements propos\u00e9s</b> \u2014 ordres g\u00e9n\u00e9r\u00e9s, avec justification et r\u00e9sultat du contr\u00f4le de risque"))
    s.append(B("<b>R\u00e9sum\u00e9 des positions</b> \u2014 \u00e9tat du portefeuille avant et apr\u00e8s les modifications"))

    s.append(H2("8.2 Export"))
    s.append(P(
        "Chaque m\u00e9mo peut \u00eatre export\u00e9 en deux formats\u202f: "
        "<b>PDF</b> pour l\u2019archivage formel et la distribution, "
        "ou <b>Markdown</b> pour l\u2019int\u00e9gration dans les outils de documentation. "
        "Le bouton d\u2019export est situ\u00e9 en haut \u00e0 droite de chaque m\u00e9mo."
    ))

    s.append(H2("8.3 R\u00f4le r\u00e9glementaire"))
    s.append(P(
        "Les m\u00e9mos IC servent de <b>trace d\u2019audit</b> pour les r\u00e9gulateurs. "
        "Ils documentent le raisonnement complet ayant conduit \u00e0 chaque d\u00e9cision "
        "d\u2019investissement\u202f: donn\u00e9es d\u2019entr\u00e9e, analyse des agents, r\u00e9sultat "
        "du contr\u00f4le de risque et ex\u00e9cution finale. Cette tra\u00e7abilit\u00e9 compl\u00e8te est un atout "
        "majeur pour la conformit\u00e9 MiFID\u202fII et AIFMD."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  9. BACKTEST
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("9. Backtest"))
    s.append(teal_divider())

    s.append(P(
        "Le module de <b>backtest</b> permet de tester des strat\u00e9gies d\u2019investissement "
        "sur des donn\u00e9es historiques fournies par Yahoo Finance. Il est accessible "
        "aux utilisateurs disposant du r\u00f4le <b>Analyst</b> ou sup\u00e9rieur."
    ))

    s.append(H2("9.1 Configuration"))
    s.append(P("Param\u00e9trez votre backtest via le panneau de configuration\u202f:"))
    s.append(make_table(
        ["Param\u00e8tre", "Description", "Exemple"],
        [
            ["Presets", "Strat\u00e9gies pr\u00e9configur\u00e9es (All Weather, Tech Growth, etc.)", "All Weather"],
            ["Dur\u00e9e", "P\u00e9riode de backtest (6 mois, 1 an, 3 ans, 5 ans)", "1 an"],
            ["Capital initial", "Montant de d\u00e9part en euros", "100\u202f000 \u20ac"],
            ["Benchmark", "Indice de r\u00e9f\u00e9rence pour comparaison", "SPY (S&amp;P 500)"],
            ["Tickers", "Liste des instruments \u00e0 inclure", "AAPL, MSFT, GOOG"],
            ["Pond\u00e9rations", "R\u00e9partition du capital entre les instruments", "33%, 33%, 34%"],
        ],
        col_widths=[3*cm, AVAIL_W - 5.5*cm, 2.5*cm],
    ))

    s.append(H2("9.2 KPIs et r\u00e9sultats"))
    s.append(P("Apr\u00e8s ex\u00e9cution, le backtest affiche les indicateurs cl\u00e9s\u202f:"))
    s.append(B("<b>Rendement total</b> \u2014 performance cumul\u00e9e sur la p\u00e9riode"))
    s.append(B("<b>Rendement annualis\u00e9</b> \u2014 performance normalis\u00e9e sur un an"))
    s.append(B("<b>Volatilit\u00e9 annualis\u00e9e</b> \u2014 \u00e9cart-type des rendements"))
    s.append(B("<b>Ratio de Sharpe</b> \u2014 rendement ajust\u00e9 du risque"))
    s.append(B("<b>Drawdown maximum</b> \u2014 perte maximale entre pic et creux"))
    s.append(B("<b>Performance par actif</b> \u2014 contribution individuelle de chaque position"))

    s.append(H2("9.3 Courbe d\u2019\u00e9quit\u00e9 et comparaison"))
    s.append(P(
        "Un graphique interactif superpose la <b>courbe d\u2019\u00e9quit\u00e9 du portefeuille</b> "
        "et celle du <b>benchmark</b> choisi. La zone entre les deux courbes est color\u00e9e "
        "en vert (surperformance) ou en rouge (sous-performance). "
        "Survolez pour afficher les valeurs exactes \u00e0 chaque date."
    ))

    s.append(H2("9.4 Export CSV du journal de trading"))
    s.append(P(
        "Le bouton <b>Exporter CSV</b> permet de t\u00e9l\u00e9charger le journal de trading "
        "complet du backtest. L\u2019export est g\u00e9n\u00e9r\u00e9 c\u00f4t\u00e9 client (Blob download) "
        "avec un endpoint serveur <b>POST /api/backtest/export-csv</b> en fallback."
    ))
    s.append(P("Le fichier CSV contient les colonnes suivantes\u202f:"))
    s.append(make_table(
        ["Colonne CSV", "Description"],
        [
            ["Date", "Date de la ligne"],
            ["Ticker", "Code instrument"],
            ["Poids (%)", "Pond\u00e9ration de la position"],
            ["Prix", "Prix de cl\u00f4ture"],
            ["Rendement Jour (%)", "Performance journali\u00e8re"],
            ["Rendement Cumul (%)", "Performance cumul\u00e9e"],
            ["Valeur Position", "Valeur en euros de la position"],
        ],
        col_widths=[3.5*cm, AVAIL_W - 3.5*cm],
    ))
    s.append(SP(3))
    s.append(N(
        "<b>Format CSV\u202f:</b> s\u00e9parateur point-virgule (;) pour compatibilit\u00e9 "
        "avec Excel en configuration fran\u00e7aise, encodage UTF-8 avec BOM. "
        "Une section r\u00e9capitulative avec les statistiques du portefeuille "
        "est ajout\u00e9e en fin de fichier."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  10. ADMINISTRATION
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("10. Administration"))
    s.append(teal_divider())

    s.append(P(
        "L\u2019onglet <b>Administration</b> est <b>visible uniquement pour les utilisateurs "
        "disposant du r\u00f4le Admin</b> (niveau 3). Il permet la gestion compl\u00e8te "
        "des utilisateurs et des permissions de la plateforme."
    ))

    s.append(H2("10.1 Liste des utilisateurs"))
    s.append(P(
        "Le tableau principal affiche tous les comptes utilisateurs avec les informations "
        "suivantes\u202f: nom d\u2019utilisateur, email, nom complet, r\u00f4le actuel, "
        "statut (actif/inactif) et date de derni\u00e8re connexion."
    ))

    s.append(H2("10.2 Cr\u00e9ation d\u2019un utilisateur"))
    s.append(P("Pour cr\u00e9er un nouveau compte, renseignez les champs suivants\u202f:"))
    s.append(make_table(
        ["Champ", "Obligatoire", "Description"],
        [
            ["Nom d\u2019utilisateur", "Oui", "Identifiant unique de connexion"],
            ["Email", "Oui", "Adresse email de l\u2019utilisateur"],
            ["Mot de passe", "Oui", "Mot de passe initial (sera hach\u00e9 en bcrypt)"],
            ["Nom complet", "Non", "Nom affich\u00e9 dans l\u2019interface"],
            ["R\u00f4le", "Oui", "Viewer, Analyst, Manager ou Admin"],
        ],
        col_widths=[3.5*cm, 2.5*cm, AVAIL_W - 6*cm],
    ))

    s.append(H2("10.3 Modification et d\u00e9sactivation"))
    s.append(P(
        "Depuis la liste des utilisateurs, l\u2019administrateur peut\u202f:"
    ))
    s.append(B("<b>Changer le r\u00f4le</b> \u2014 via un menu d\u00e9roulant dans la ligne de l\u2019utilisateur"))
    s.append(B("<b>Modifier les informations</b> \u2014 nom complet, email"))
    s.append(B("<b>R\u00e9initialiser le mot de passe</b> \u2014 g\u00e9n\u00e8re un nouveau mot de passe temporaire"))
    s.append(B("<b>D\u00e9sactiver un compte</b> \u2014 <i>soft delete</i>, le compte reste en base mais l\u2019acc\u00e8s est bloqu\u00e9"))
    s.append(B("<b>R\u00e9activer un compte</b> \u2014 restauration d\u2019un compte pr\u00e9c\u00e9demment d\u00e9sactiv\u00e9"))

    s.append(H2("10.4 Endpoints d\u2019administration"))
    s.append(P("L\u2019API d\u2019administration expose les endpoints suivants (r\u00f4le Admin requis)\u202f:"))
    s.append(make_table(
        ["Endpoint", "M\u00e9thode", "Description"],
        [
            ["/api/admin/users", "GET", "Lister tous les utilisateurs"],
            ["/api/admin/users", "POST", "Cr\u00e9er un utilisateur"],
            ["/api/admin/users/{id}", "PUT", "Modifier r\u00f4le/statut/nom"],
            ["/api/admin/users/{id}/reset-password", "POST", "R\u00e9initialiser le mot de passe"],
            ["/api/admin/users/{id}", "DELETE", "D\u00e9sactiver un utilisateur"],
            ["/api/admin/roles", "GET", "Lister les r\u00f4les et permissions"],
        ],
        col_widths=[5.5*cm, 2*cm, AVAIL_W - 7.5*cm],
    ))

    # ═══════════════════════════════════════════════════════════════
    #  11. FAQ ET DEPANNAGE
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("11. FAQ et d\u00e9pannage"))
    s.append(teal_divider())

    faq = [
        ("Je ne peux pas me connecter.",
         "V\u00e9rifiez vos identifiants. Si le probl\u00e8me persiste, demandez \u00e0 un administrateur de r\u00e9initialiser votre mot de passe via le panneau d\u2019administration. V\u00e9rifiez \u00e9galement que votre compte n\u2019a pas \u00e9t\u00e9 d\u00e9sactiv\u00e9."),
        ("Mon jeton JWT a expir\u00e9.",
         "Les jetons ont une dur\u00e9e de validit\u00e9 de 24 heures. L\u2019interface vous redirige automatiquement vers la page de connexion. Reconnectez-vous simplement."),
        ("Je ne vois pas l\u2019onglet Administration.",
         "Cet onglet est r\u00e9serv\u00e9 aux utilisateurs disposant du r\u00f4le <b>Admin</b>. Contactez votre administrateur si vous avez besoin d\u2019un acc\u00e8s \u00e9lev\u00e9."),
        ("Le bouton \u00ab\u202fRun Decision Cycle\u202f\u00bb est gris\u00e9.",
         "Seuls les r\u00f4les <b>Manager</b> et <b>Admin</b> peuvent lancer un cycle. V\u00e9rifiez votre r\u00f4le dans le panneau utilisateur."),
        ("Le backtest ne se lance pas.",
         "V\u00e9rifiez que vous avez s\u00e9lectionn\u00e9 au moins un ticker et que les pond\u00e9rations totalisent 100\u202f%. Le r\u00f4le <b>Analyst</b> minimum est requis."),
        ("L\u2019export CSV du backtest est vide.",
         "Assurez-vous qu\u2019un backtest a \u00e9t\u00e9 ex\u00e9cut\u00e9 avec succ\u00e8s avant de tenter l\u2019export. V\u00e9rifiez la console navigateur pour d\u2019\u00e9ventuelles erreurs."),
        ("Les donn\u00e9es Crypto ne se chargent pas.",
         "Les donn\u00e9es proviennent de l\u2019API CoinGecko. V\u00e9rifiez votre connexion r\u00e9seau. L\u2019API peut \u00eatre temporairement indisponible en cas de surcharge."),
        ("Les donn\u00e9es macro sont manquantes.",
         "V\u00e9rifiez que la cl\u00e9 API FRED est correctement configur\u00e9e sur le serveur. Sans cette cl\u00e9, le dashboard de vuln\u00e9rabilit\u00e9 ne peut pas r\u00e9cup\u00e9rer les indicateurs."),
        ("Comment changer le benchmark du backtest\u202f?",
         "Dans le panneau de configuration du backtest, utilisez le champ <b>Benchmark</b> pour saisir le ticker de l\u2019indice souhait\u00e9 (ex.\u202f: SPY, QQQ, DIA)."),
        ("Comment exporter un m\u00e9mo IC en PDF\u202f?",
         "Ouvrez le m\u00e9mo souhait\u00e9, puis cliquez sur le bouton <b>Export PDF</b> en haut \u00e0 droite. Le fichier sera t\u00e9l\u00e9charg\u00e9 automatiquement."),
    ]

    for i, (q, a) in enumerate(faq):
        s.append(H3(f"Q{i+1}\u202f: {q}"))
        s.append(P(a))
        if i < len(faq) - 1:
            s.append(SP(2))

    # ── KEYBOARD SHORTCUTS ──
    s.append(SP(6))
    s.append(H2("Raccourcis clavier"))
    s.append(make_table(
        ["Raccourci", "Action"],
        [
            ["[Ctrl+R]", "Rafra\u00eechir les donn\u00e9es du tableau de bord"],
            ["[Ctrl+E]", "Exporter la vue courante"],
            ["[Ctrl+F]", "Rechercher dans la page active"],
            ["[Esc]", "Fermer la fen\u00eatre modale / panneau de d\u00e9tail"],
            ["[Tab]", "Naviguer entre les onglets principaux"],
        ],
        col_widths=[3*cm, AVAIL_W - 3*cm],
    ))

    # ── END ──
    s.append(SP(30))
    s.append(HRFlowable(width="100%", thickness=0.4, color=WARM_BEIGE, spaceAfter=10, spaceBefore=4))
    s.append(SP(10))
    end_center = ParagraphStyle("EC", fontName="Helvetica-Bold", fontSize=14,
                                leading=18, textColor=TEAL_DARK, alignment=TA_CENTER)
    end_sub = ParagraphStyle("ES", fontName="Helvetica", fontSize=9.5,
                             leading=13, textColor=TEAL_MEDIUM, alignment=TA_CENTER)
    end_brand = ParagraphStyle("EB", fontName="Helvetica-Bold", fontSize=9.5,
                               leading=13, textColor=TEAL_PRIMARY, alignment=TA_CENTER)
    end_credit = ParagraphStyle("ECR", fontName="Helvetica", fontSize=7.5,
                                leading=10, textColor=TEAL_MEDIUM, alignment=TA_CENTER)

    s.append(Paragraph("Fin du Guide Utilisateur", end_center))
    s.append(SP(10))
    s.append(Paragraph(
        "Pour toute question, contactez votre \u00e9quipe support ou consultez "
        "la documentation en ligne sur <b>docs.nextones.finance</b>.",
        end_sub,
    ))
    s.append(SP(14))
    s.append(Paragraph("NEXTONES.FINANCE \u2014 Version 2.0 \u2014 Mars 2026", end_brand))
    s.append(Paragraph("Document g\u00e9n\u00e9r\u00e9 par Perplexity Computer", end_credit))

    return s


# ─── Main ───────────────────────────────────────────────────────────
def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # Define frames
    content_frame = Frame(
        MARGIN_LEFT, MARGIN_BOTTOM,
        AVAIL_W, PAGE_H - MARGIN_TOP - MARGIN_BOTTOM,
        id="content",
    )
    cover_frame = Frame(
        0, 0, PAGE_W, PAGE_H,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        id="cover",
    )

    # Templates
    cover_template = PageTemplate(id="cover", frames=[cover_frame], onPage=draw_cover)
    normal_template = PageTemplate(id="normal", frames=[content_frame], onPage=draw_normal_header_footer)

    doc = BaseDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        title="Guide Utilisateur \u2014 Nextones Desk",
        author="Perplexity Computer",
        leftMargin=MARGIN_LEFT,
        rightMargin=MARGIN_RIGHT,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        pageTemplates=[cover_template, normal_template],
    )

    story = build_story()
    doc.build(story)
    print(f"PDF generated: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
