#!/usr/bin/env python3
"""Generate the Thesium Desk User Guide PDF in French — expanded version (12-15 pages)."""

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

OUTPUT_PATH = "/home/user/workspace/thesium-desk/Guide_Utilisateur_Thesium_Desk.pdf"

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
    c.drawString(MARGIN_LEFT + 0.5*cm, y_base - 42, "Thesium Desk")

    # Subtitle
    c.setFillColor(LIGHT_TEAL)
    c.setFont("Helvetica", 13)
    c.drawString(MARGIN_LEFT + 0.5*cm, y_base - 80, "Version 1.0 \u2014 Mars 2026")

    # Description
    c.setFillColor(HexColor("#8FBFC6"))
    c.setFont("Helvetica", 10.5)
    c.drawString(MARGIN_LEFT + 0.5*cm, y_base - 106,
                 "Fund OS pilot\u00e9 par IA pour la gestion d\u2019investissements")

    # Bottom branding
    by = 3 * cm
    c.setFillColor(TEAL_PRIMARY)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(MARGIN_LEFT + 0.5*cm, by, "Thesium.finance")
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
    c.drawString(MARGIN_LEFT, yh + 3, "Guide Utilisateur \u2014 Thesium Desk")
    c.drawRightString(PAGE_W - MARGIN_RIGHT, yh + 3, "Thesium.finance")

    # Footer
    yf = 1.4*cm
    c.setStrokeColor(WARM_BEIGE)
    c.setLineWidth(0.4)
    c.line(MARGIN_LEFT, yf, PAGE_W - MARGIN_RIGHT, yf)
    c.setFont("Helvetica", 7)
    c.setFillColor(TEAL_MEDIUM)
    c.drawString(MARGIN_LEFT, yf - 10, "Version 1.0 \u2014 Mars 2026")
    c.drawCentredString(PAGE_W / 2, yf - 10, "\u00a9 Thesium.finance")
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
        "1.  Introduction",
        "2.  Prise en main",
        "3.  Onglet \u00ab\u202fToday\u202f\u00bb \u2014 Tableau de bord",
        "4.  Onglet \u00ab\u202fTheses\u202f\u00bb \u2014 Th\u00e8ses d\u2019investissement",
        "5.  Onglet \u00ab\u202fOrders &amp; Fills\u202f\u00bb \u2014 Ordres et Ex\u00e9cutions",
        "6.  Onglet \u00ab\u202fIC Memos\u202f\u00bb \u2014 M\u00e9mos du Comit\u00e9 d\u2019Investissement",
        "7.  Le Cycle de D\u00e9cision",
        "8.  Les 4 Agents de Recherche IA",
        "9.  Glossaire",
    ]
    for item in toc:
        parts = item.split("  ", 1)
        s.append(Paragraph(f'<b>{parts[0]}</b> {parts[1]}', styles["toc_entry"]))
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

    s.append(H2("1.1 Pr\u00e9sentation de Thesium Desk"))
    s.append(P(
        "Thesium Desk est un <b>Fund OS</b> (syst\u00e8me d\u2019exploitation pour fonds "
        "d\u2019investissement) pilot\u00e9 par intelligence artificielle. La plateforme "
        "automatise la cha\u00eene de recherche\u202f: quatre agents IA sp\u00e9cialis\u00e9s "
        "analysent en continu les donn\u00e9es de march\u00e9, g\u00e9n\u00e8rent des "
        "<i>th\u00e8ses d\u2019investissement</i> et proposent des ordres, le tout "
        "supervis\u00e9 par les \u00e9quipes humaines via l\u2019interface Thesium Desk."
    ))
    s.append(P(
        "L\u2019objectif est de fournir un processus de d\u00e9cision rigoureux, "
        "tra\u00e7able et r\u00e9p\u00e9table\u202f: chaque th\u00e8se g\u00e9n\u00e9r\u00e9e est document\u00e9e, "
        "chaque ordre passe par un contr\u00f4le de risque automatique, et chaque "
        "cycle de d\u00e9cision produit un m\u00e9mo d\u2019audit \u00e0 destination du "
        "comit\u00e9 d\u2019investissement."
    ))

    s.append(H2("1.2 Philosophie du produit"))
    s.append(P(
        "Thesium Desk repose sur le principe de la <b>supervision humaine augment\u00e9e</b> "
        "(<i>human-in-the-loop</i>). L\u2019intelligence artificielle ne remplace pas le "
        "gestionnaire\u202f: elle acc\u00e9l\u00e8re l\u2019analyse, d\u00e9tecte les signaux faibles et "
        "structure l\u2019information. Chaque d\u00e9cision finale reste sous la responsabilit\u00e9 "
        "de l\u2019\u00e9quipe d\u2019investissement."
    ))
    s.append(P(
        "Le syst\u00e8me est con\u00e7u pour \u00eatre <b>transparent</b> et <b>auditable</b>. "
        "Toutes les recommandations sont accompagn\u00e9es de leur raisonnement complet\u202f: "
        "donn\u00e9es utilis\u00e9es, indicateurs calcul\u00e9s, seuils appliqu\u00e9s et r\u00e9sultat "
        "du contr\u00f4le de risque. Cette tra\u00e7abilit\u00e9 facilite les audits internes "
        "et la conformit\u00e9 r\u00e9glementaire."
    ))

    s.append(H2("1.3 Public cible"))
    s.append(P("Ce guide s\u2019adresse aux\u202f:"))
    s.append(B("<b>Gestionnaires de portefeuille</b> \u2014 pilotage quotidien des positions et validation des ordres"))
    s.append(B("<b>Analystes</b> \u2014 revue des th\u00e8ses IA, ajustement des param\u00e8tres"))
    s.append(B("<b>Superviseurs / Compliance</b> \u2014 consultation des m\u00e9mos IC pour l\u2019audit r\u00e9glementaire"))
    s.append(B("<b>Administrateurs techniques</b> \u2014 configuration de l\u2019instance, gestion des acc\u00e8s et int\u00e9gration API"))
    s.append(SP(4))
    s.append(N(
        "<b>Pr\u00e9requis\u202f:</b> un navigateur web r\u00e9cent (Chrome, Firefox, Edge) "
        "et un acc\u00e8s r\u00e9seau \u00e0 l\u2019instance Thesium Desk de votre organisation."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  2. PRISE EN MAIN
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("2. Prise en main"))
    s.append(teal_divider())

    s.append(H2("2.1 Acc\u00e8s \u00e0 l\u2019application"))
    s.append(P(
        "Ouvrez votre navigateur et acc\u00e9dez \u00e0 l\u2019URL fournie par votre "
        "administrateur (par exemple\u202f: <b>https://desk.thesium.finance</b>). "
        "Authentifiez-vous avec vos identifiants d\u2019entreprise. Apr\u00e8s connexion, "
        "vous arrivez directement sur l\u2019onglet <b>Today</b>."
    ))
    s.append(P(
        "Si votre organisation utilise l\u2019authentification unique (<i>SSO</i>), "
        "cliquez sur le bouton <b>Connexion SSO</b> et suivez la proc\u00e9dure standard "
        "de votre fournisseur d\u2019identit\u00e9. En cas de difficult\u00e9, contactez votre "
        "administrateur syst\u00e8me."
    ))

    s.append(H2("2.2 Interface et th\u00e8me visuel"))
    s.append(P(
        "L\u2019interface adopte un <b>th\u00e8me sombre</b> (<i>dark mode</i>) par d\u00e9faut, "
        "avec une palette <i>Nexus Teal</i> con\u00e7ue pour r\u00e9duire la fatigue visuelle "
        "lors d\u2019un usage prolong\u00e9. Les \u00e9l\u00e9ments interactifs (boutons, liens) "
        "utilisent la couleur turquoise primaire pour une identification imm\u00e9diate."
    ))
    s.append(P(
        "L\u2019interface est enti\u00e8rement <b>responsive</b>\u202f: elle s\u2019adapte aux \u00e9crans "
        "larges (double moniteur recommand\u00e9) comme aux tablettes. Les tableaux "
        "sont redimensionnables et les panneaux lat\u00e9raux peuvent \u00eatre r\u00e9duits "
        "pour maximiser l\u2019espace de travail."
    ))

    s.append(H2("2.3 Navigation"))
    s.append(P("La barre lat\u00e9rale gauche contient quatre onglets principaux\u202f:"))
    s.append(make_table(
        ["Onglet", "Ic\u00f4ne", "Description"],
        [
            ["Today", "\u2302", "Tableau de bord synth\u00e9tique du portefeuille"],
            ["Theses", "\u2261", "Liste et d\u00e9tail des th\u00e8ses d\u2019investissement IA"],
            ["Orders &amp; Fills", "\u2194", "Suivi des ordres et de leurs ex\u00e9cutions"],
            ["IC Memos", "\u2709", "M\u00e9mos du comit\u00e9 d\u2019investissement"],
        ],
        col_widths=[3.2*cm, 1.2*cm, AVAIL_W - 4.4*cm],
    ))
    s.append(SP(3))
    s.append(P(
        "Cliquez sur un onglet pour y acc\u00e9der. L\u2019onglet actif est mis en "
        "surbrillance. En haut \u00e0 droite, vous trouverez le bouton "
        "<b>Run Decision Cycle</b> ainsi que les indicateurs de connexion."
    ))

    s.append(H2("2.4 R\u00f4les et permissions"))
    s.append(P(
        "Thesium Desk g\u00e8re trois niveaux de permissions. Votre administrateur "
        "attribue un r\u00f4le \u00e0 chaque utilisateur lors de la cr\u00e9ation du compte\u202f:"
    ))
    s.append(make_table(
        ["R\u00f4le", "Consultation", "Approbation", "Lancement cycle", "Configuration"],
        [
            ["Viewer", "\u2713", "\u2014", "\u2014", "\u2014"],
            ["Analyst", "\u2713", "\u2713", "\u2014", "\u2014"],
            ["Manager", "\u2713", "\u2713", "\u2713", "\u2014"],
            ["Admin", "\u2713", "\u2713", "\u2713", "\u2713"],
        ],
        col_widths=[2.5*cm, 2.5*cm, 2.5*cm, 2.8*cm, AVAIL_W - 10.3*cm],
    ))
    s.append(SP(3))
    s.append(N(
        "<b>S\u00e9curit\u00e9\u202f:</b> toutes les actions sont journalis\u00e9es. "
        "L\u2019historique des connexions et des op\u00e9rations est consultable "
        "par les administrateurs dans le panneau <b>Settings > Audit Log</b>."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  3. ONGLET TODAY
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("3. Onglet \u00ab\u202fToday\u202f\u00bb \u2014 Tableau de bord"))
    s.append(teal_divider())

    s.append(P(
        "L\u2019onglet <b>Today</b> est votre point d\u2019entr\u00e9e quotidien. "
        "Il pr\u00e9sente une vue consolid\u00e9e de l\u2019\u00e9tat du portefeuille, "
        "des m\u00e9triques de risque et de l\u2019activit\u00e9 r\u00e9cente du syst\u00e8me."
    ))

    s.append(H2("3.1 Vue d\u2019ensemble du portefeuille"))
    s.append(P("La section sup\u00e9rieure affiche quatre indicateurs cl\u00e9s\u202f:"))
    s.append(B("<b>Total Value</b> \u2014 Valeur totale du portefeuille (positions + cash), mise \u00e0 jour en temps r\u00e9el"))
    s.append(B("<b>Cash disponible</b> \u2014 Liquidit\u00e9s non investies, disponibles pour de nouvelles positions"))
    s.append(B("<b>P&amp;L total</b> \u2014 Gain ou perte cumul\u00e9(e) depuis l\u2019ouverture du portefeuille"))
    s.append(B("<b>P&amp;L journalier</b> \u2014 Variation de valeur sur la s\u00e9ance en cours"))
    s.append(SP(3))
    s.append(P(
        "Les valeurs positives sont affich\u00e9es en <b>vert</b>, les valeurs n\u00e9gatives "
        "en <b>rouge</b>. Un code couleur identique est appliqu\u00e9 dans l\u2019ensemble "
        "de l\u2019interface pour garantir une lecture rapide."
    ))

    s.append(H2("3.2 M\u00e9triques de risque"))
    s.append(P("Deux m\u00e9triques de risque sont affich\u00e9es en permanence\u202f:"))
    s.append(B(
        "<b>VaR 95\u202f% (1 jour)</b> \u2014 <i>Value at Risk</i>\u202f: estimation de la perte maximale "
        "probable sur une journ\u00e9e avec un niveau de confiance de 95\u202f%. Par exemple, "
        "une VaR de 12\u202f000\u202f\u20ac signifie que la perte journali\u00e8re ne d\u00e9passera pas "
        "ce montant dans 95\u202f% des sc\u00e9narios."
    ))
    s.append(B(
        "<b>Drawdown maximum</b> \u2014 Perte maximale observ\u00e9e entre un pic et un creux de la "
        "courbe d\u2019\u00e9quit\u00e9, exprim\u00e9e en pourcentage."
    ))
    s.append(SP(3))
    s.append(N(
        "<b>Rappel\u202f:</b> ces m\u00e9triques sont recalcul\u00e9es en temps r\u00e9el \u00e0 chaque "
        "mise \u00e0 jour des cours. En mode paper trading, elles refl\u00e8tent les "
        "positions simul\u00e9es."
    ))

    s.append(H2("3.3 Tableau des positions"))
    s.append(P("Le tableau central liste l\u2019ensemble des positions ouvertes\u202f:"))
    s.append(make_table(
        ["Colonne", "Description"],
        [
            ["Ticker", "Code de l\u2019instrument (ex.\u202f: AAPL, MSFT)"],
            ["Nom", "Nom complet de l\u2019instrument"],
            ["Quantit\u00e9", "Nombre de titres d\u00e9tenus"],
            ["Prix moyen d\u2019achat", "Co\u00fbt moyen pond\u00e9r\u00e9 d\u2019acquisition"],
            ["Prix actuel", "Dernier cours disponible"],
            ["P&amp;L non r\u00e9alis\u00e9 (\u20ac)", "Gain/perte latent(e) en euros"],
            ["P&amp;L non r\u00e9alis\u00e9 (%)", "Gain/perte latent(e) en pourcentage"],
            ["Poids", "Poids de la position dans le portefeuille"],
        ],
        col_widths=[4*cm, AVAIL_W - 4*cm],
    ))
    s.append(SP(3))
    s.append(N(
        "<b>Astuce\u202f:</b> cliquez sur un en-t\u00eate de colonne pour trier le tableau. "
        "Un second clic inverse l\u2019ordre de tri. Maintenez <b>Shift</b> enfonc\u00e9 "
        "pour ajouter un crit\u00e8re de tri secondaire."
    ))

    s.append(H2("3.4 Courbe d\u2019\u00e9quit\u00e9 (<i>Equity Curve</i>)"))
    s.append(P(
        "Le graphique Chart.js en bas \u00e0 gauche affiche l\u2019\u00e9volution de la valeur "
        "totale du portefeuille sur les <b>30 derniers jours</b>. L\u2019axe horizontal "
        "repr\u00e9sente le temps, l\u2019axe vertical la valeur en euros. Survolez la courbe "
        "pour afficher la valeur exacte \u00e0 une date donn\u00e9e."
    ))
    s.append(P(
        "La zone sous la courbe est color\u00e9e en gradient turquoise. Un deuxi\u00e8me "
        "trac\u00e9 en pointill\u00e9s indique la valeur de r\u00e9f\u00e9rence (benchmark) si "
        "celui-ci est configur\u00e9 dans les param\u00e8tres."
    ))

    s.append(H2("3.5 Fil d\u2019activit\u00e9 (<i>Activity Feed</i>)"))
    s.append(P(
        "Le panneau de droite affiche les <b>20 derniers \u00e9v\u00e9nements</b> du syst\u00e8me "
        "en ordre chronologique invers\u00e9\u202f: th\u00e8ses g\u00e9n\u00e9r\u00e9es, ordres cr\u00e9\u00e9s, "
        "ex\u00e9cutions confirm\u00e9es, alertes de risque. Chaque entr\u00e9e indique "
        "l\u2019horodatage, le type d\u2019\u00e9v\u00e9nement et un r\u00e9sum\u00e9 succinct."
    ))
    s.append(P(
        "Les \u00e9v\u00e9nements sont cod\u00e9s par couleur\u202f: <b>turquoise</b> pour les th\u00e8ses, "
        "<b>bleu</b> pour les ordres, <b>vert</b> pour les ex\u00e9cutions r\u00e9ussies, "
        "<b>orange</b> pour les alertes, <b>rouge</b> pour les rejets."
    ))

    s.append(H2("3.6 Compteurs"))
    s.append(P("Trois compteurs synth\u00e9tiques sont visibles en haut du tableau de bord\u202f:"))
    s.append(B("<b>Th\u00e8ses actives</b> \u2014 nombre de th\u00e8ses en cours d\u2019\u00e9valuation"))
    s.append(B("<b>Ordres en attente</b> \u2014 ordres au statut <i>pending</i> ou <i>approved</i>"))
    s.append(B("<b>Positions</b> \u2014 nombre total de lignes en portefeuille"))

    # ═══════════════════════════════════════════════════════════════
    #  4. ONGLET THESES
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("4. Onglet \u00ab\u202fTheses\u202f\u00bb \u2014 Th\u00e8ses d\u2019investissement"))
    s.append(teal_divider())

    s.append(P(
        "Cet onglet centralise l\u2019ensemble des <b>th\u00e8ses d\u2019investissement</b> "
        "g\u00e9n\u00e9r\u00e9es par les quatre agents IA. Chaque th\u00e8se repr\u00e9sente une "
        "recommandation argument\u00e9e pour acheter, vendre ou conserver un titre."
    ))

    s.append(H2("4.1 Liste des th\u00e8ses"))
    s.append(P("Le tableau principal pr\u00e9sente les colonnes suivantes\u202f:"))
    s.append(make_table(
        ["Colonne", "Description"],
        [
            ["Ticker", "Instrument concern\u00e9"],
            ["Agent", "Agent IA auteur (MacroAgent, FactorAgent, MicrostructureAgent, AltDataAgent)"],
            ["Score de conviction", "Note de 1 \u00e0 10 refl\u00e9tant la confiance de l\u2019agent"],
            ["Horizon", "Court terme (&lt;\u202f5j), moyen terme (5-20j), long terme (&gt;\u202f20j)"],
            ["Action propos\u00e9e", "Buy, Sell ou Hold"],
            ["Facteurs cl\u00e9s", "R\u00e9sum\u00e9 des signaux ayant conduit \u00e0 la recommandation"],
        ],
        col_widths=[3.8*cm, AVAIL_W - 3.8*cm],
    ))

    s.append(H2("4.2 Filtres disponibles"))
    s.append(P("Utilisez la barre de filtres pour affiner la vue\u202f:"))
    s.append(B("<b>Par agent</b> \u2014 s\u00e9lectionnez un ou plusieurs agents"))
    s.append(B("<b>Par statut</b> \u2014 active, approuv\u00e9e, archiv\u00e9e"))
    s.append(B("<b>Par ticker</b> \u2014 recherche libre par code instrument"))
    s.append(B("<b>Par horizon</b> \u2014 filtrage par dur\u00e9e de la recommandation"))
    s.append(B("<b>Par score</b> \u2014 seuil minimum de conviction (curseur de 1 \u00e0 10)"))

    s.append(H2("4.3 D\u00e9tail d\u2019une th\u00e8se"))
    s.append(P("Cliquez sur une ligne pour ouvrir le d\u00e9tail. Celui-ci affiche\u202f:"))
    s.append(B("<b>Texte complet</b> \u2014 analyse r\u00e9dig\u00e9e en markdown par l\u2019agent"))
    s.append(B("<b>Facteurs cl\u00e9s d\u00e9taill\u00e9s</b> \u2014 indicateurs techniques et fondamentaux utilis\u00e9s"))
    s.append(B("<b>Ordres li\u00e9s</b> \u2014 liste des ordres g\u00e9n\u00e9r\u00e9s \u00e0 partir de cette th\u00e8se"))
    s.append(B("<b>Historique</b> \u2014 horodatage de cr\u00e9ation, de modification et d\u2019approbation"))

    s.append(H2("4.4 Approbation d\u2019une th\u00e8se"))
    s.append(P(
        "Pour qu\u2019une th\u00e8se d\u00e9clenche la cr\u00e9ation d\u2019un ordre, elle doit \u00eatre "
        "approuv\u00e9e. Cliquez sur le bouton <b>Approve</b> dans le d\u00e9tail de la th\u00e8se. "
        "Cette action est irr\u00e9versible\u202f: une th\u00e8se approuv\u00e9e sera prise en compte "
        "lors du prochain cycle de d\u00e9cision."
    ))
    s.append(N(
        "<b>Important\u202f:</b> seules les th\u00e8ses avec un score de conviction "
        "\u2265\u202f7 sont automatiquement propos\u00e9es \u00e0 l\u2019approbation. "
        "Les th\u00e8ses \u00e0 score inf\u00e9rieur restent visibles mais n\u00e9cessitent "
        "une approbation manuelle explicite."
    ))

    s.append(H2("4.5 Convergence entre agents"))
    s.append(P(
        "Lorsque plusieurs agents convergent sur un m\u00eame titre avec une m\u00eame "
        "direction (achat ou vente), la th\u00e8se est signal\u00e9e par un badge "
        "<b>Multi-Agent</b>. Cette convergence renforce la conviction globale et "
        "constitue souvent un signal de qualit\u00e9 sup\u00e9rieure."
    ))
    s.append(P(
        "Inversement, une <b>divergence</b> entre agents sur un m\u00eame titre "
        "est signal\u00e9e par un badge <b>Conflit</b>, invitant le gestionnaire "
        "\u00e0 examiner les analyses contradictoires avant de prendre une d\u00e9cision."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  5. ONGLET ORDERS & FILLS
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("5. Onglet \u00ab\u202fOrders &amp; Fills\u202f\u00bb \u2014 Ordres et Ex\u00e9cutions"))
    s.append(teal_divider())

    s.append(H2("5.1 Tableau des ordres"))
    s.append(P("Ce tableau r\u00e9capitule tous les ordres g\u00e9n\u00e9r\u00e9s par le syst\u00e8me\u202f:"))
    s.append(make_table(
        ["Colonne", "Description"],
        [
            ["ID", "Identifiant unique de l\u2019ordre"],
            ["Ticker", "Instrument concern\u00e9"],
            ["C\u00f4t\u00e9", "Buy (achat) ou Sell (vente)"],
            ["Quantit\u00e9", "Nombre de titres \u00e0 n\u00e9gocier"],
            ["Type", "Market (au march\u00e9) ou Limit (prix limite)"],
            ["Prix limite", "Prix limite pour les ordres de type Limit"],
            ["Statut", "Pending, Approved, Filled, Rejected, Cancelled"],
            ["Th\u00e8se source", "Lien vers la th\u00e8se ayant g\u00e9n\u00e9r\u00e9 cet ordre"],
        ],
        col_widths=[3.2*cm, AVAIL_W - 3.2*cm],
    ))

    s.append(H2("5.2 Contr\u00f4le de risque"))
    s.append(P(
        "Chaque ordre passe par le <b>moteur de risque</b> avant ex\u00e9cution. "
        "Le r\u00e9sultat est visible dans la colonne d\u00e9di\u00e9e\u202f: "
        "un indicateur vert signifie que l\u2019ordre respecte toutes les limites "
        "(exposition maximale, concentration, VaR marginal), un indicateur rouge "
        "indique un rejet avec le motif d\u00e9taill\u00e9."
    ))
    s.append(P("Les v\u00e9rifications effectu\u00e9es par le moteur de risque incluent\u202f:"))
    s.append(B("<b>Exposition maximale</b> \u2014 v\u00e9rifie que la valeur totale du portefeuille ne d\u00e9passe pas le plafond autoris\u00e9"))
    s.append(B("<b>Concentration</b> \u2014 aucune position individuelle ne doit exc\u00e9der le seuil de concentration (par d\u00e9faut\u202f: 15\u202f% du portefeuille)"))
    s.append(B("<b>VaR marginal</b> \u2014 l\u2019ajout de la position ne doit pas augmenter la VaR au-del\u00e0 du budget de risque"))
    s.append(B("<b>Corr\u00e9lation</b> \u2014 v\u00e9rification de la diversification globale du portefeuille"))

    s.append(H2("5.3 Tableau des ex\u00e9cutions (<i>Fills</i>)"))
    s.append(P("Une fois un ordre ex\u00e9cut\u00e9, les d\u00e9tails apparaissent dans le tableau des fills\u202f:"))
    s.append(make_table(
        ["Colonne", "Description"],
        [
            ["Prix d\u2019ex\u00e9cution", "Prix auquel la transaction a \u00e9t\u00e9 r\u00e9alis\u00e9e"],
            ["Quantit\u00e9", "Nombre de titres effectivement n\u00e9goci\u00e9s"],
            ["Slippage", "\u00c9cart entre le prix demand\u00e9 et le prix obtenu"],
            ["Frais", "Commissions et frais de transaction"],
            ["Horodatage", "Date et heure pr\u00e9cises de l\u2019ex\u00e9cution"],
        ],
        col_widths=[3.5*cm, AVAIL_W - 3.5*cm],
    ))

    s.append(H2("5.4 Cycle de vie d\u2019un ordre"))
    s.append(P("Chaque ordre suit un parcours lin\u00e9aire\u202f:"))
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
        "ou <b>Cancelled</b> (annul\u00e9 manuellement par un utilisateur disposant des droits n\u00e9cessaires)."
    ))
    s.append(SP(3))
    s.append(N(
        "<b>Bonnes pratiques\u202f:</b> consultez r\u00e9guli\u00e8rement les ordres rejet\u00e9s. "
        "Un nombre \u00e9lev\u00e9 de rejets peut indiquer que les param\u00e8tres de risque "
        "doivent \u00eatre ajust\u00e9s ou que les agents produisent des recommandations "
        "trop agressives pour le profil du fonds."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  6. ONGLET IC MEMOS
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("6. Onglet \u00ab\u202fIC Memos\u202f\u00bb \u2014 M\u00e9mos du Comit\u00e9 d\u2019Investissement"))
    s.append(teal_divider())

    s.append(P(
        "\u00c0 chaque cycle de d\u00e9cision, Thesium Desk g\u00e9n\u00e8re automatiquement "
        "un <b>m\u00e9mo du comit\u00e9 d\u2019investissement</b> (IC Memo). Ces documents "
        "constituent la trace d\u2019audit r\u00e9glementaire de chaque d\u00e9cision."
    ))

    s.append(H2("6.1 Liste des m\u00e9mos"))
    s.append(P(
        "L\u2019onglet affiche la liste compl\u00e8te des m\u00e9mos, class\u00e9s du plus "
        "r\u00e9cent au plus ancien. Chaque entr\u00e9e indique la date, l\u2019heure du cycle "
        "et un r\u00e9sum\u00e9 en une ligne. Le nombre total de m\u00e9mos est affich\u00e9 "
        "en haut de la page."
    ))

    s.append(H2("6.2 Contenu d\u2019un m\u00e9mo"))
    s.append(P("Cliquez sur un m\u00e9mo pour afficher son contenu d\u00e9taill\u00e9\u202f:"))
    s.append(B("<b>R\u00e9sum\u00e9 macro</b> \u2014 vue d\u2019ensemble des conditions de march\u00e9 selon le MacroAgent"))
    s.append(B("<b>Tilts factoriels</b> \u2014 positionnement momentum/qualit\u00e9/RSI issu du FactorAgent"))
    s.append(B("<b>R\u00e9sum\u00e9s des th\u00e8ses</b> \u2014 synth\u00e8se de chaque th\u00e8se retenue lors du cycle"))
    s.append(B("<b>Changements propos\u00e9s</b> \u2014 ordres g\u00e9n\u00e9r\u00e9s, avec justification et r\u00e9sultat du contr\u00f4le de risque"))
    s.append(B("<b>R\u00e9sum\u00e9 des positions</b> \u2014 \u00e9tat du portefeuille avant et apr\u00e8s les modifications"))

    s.append(H2("6.3 Export"))
    s.append(P(
        "Chaque m\u00e9mo peut \u00eatre export\u00e9 au format <b>Markdown</b> via le bouton "
        "d\u2019export en haut \u00e0 droite. Ce format est compatible avec la plupart "
        "des outils de documentation et de conformit\u00e9. Un export <b>PDF</b> "
        "est \u00e9galement disponible pour l\u2019archivage formel."
    ))

    s.append(H2("6.4 R\u00f4le r\u00e9glementaire"))
    s.append(P(
        "Les m\u00e9mos IC servent de <b>trace d\u2019audit</b> pour les r\u00e9gulateurs. "
        "Ils documentent le raisonnement complet ayant conduit \u00e0 chaque d\u00e9cision "
        "d\u2019investissement\u202f: donn\u00e9es d\u2019entr\u00e9e, analyse des agents, r\u00e9sultat "
        "du contr\u00f4le de risque et ex\u00e9cution finale. Conservez ces m\u00e9mos "
        "conform\u00e9ment \u00e0 votre politique de r\u00e9tention documentaire."
    ))
    s.append(P(
        "En cas d\u2019audit, les m\u00e9mos IC permettent de reconstituer l\u2019int\u00e9gralit\u00e9 "
        "du processus d\u00e9cisionnel\u202f: de l\u2019analyse initiale des agents \u00e0 "
        "l\u2019ex\u00e9cution finale de l\u2019ordre, en passant par les \u00e9tapes de validation "
        "et de contr\u00f4le de risque. Cette tra\u00e7abilit\u00e9 compl\u00e8te est un atout "
        "majeur pour la conformit\u00e9 MiFID\u202fII et AIFMD."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  7. LE CYCLE DE DECISION
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("7. Le Cycle de D\u00e9cision"))
    s.append(teal_divider())

    s.append(P(
        "Le cycle de d\u00e9cision est le processus central de Thesium Desk. "
        "Il orchestre l\u2019analyse des agents IA, le filtrage des th\u00e8ses, "
        "le contr\u00f4le de risque et l\u2019ex\u00e9cution des ordres en une s\u00e9quence automatique."
    ))

    s.append(H2("7.1 D\u00e9clenchement"))
    s.append(P("Le cycle peut \u00eatre d\u00e9clench\u00e9 de deux mani\u00e8res\u202f:"))
    s.append(B("<b>Interface</b> \u2014 cliquez sur le bouton <b>Run Decision Cycle</b> en haut \u00e0 droite"))
    s.append(B("<b>API</b> \u2014 envoyez une requ\u00eate <b>POST /api/orders/execute-cycle</b>"))
    s.append(SP(3))
    s.append(P(
        "Un cycle ne peut \u00eatre lanc\u00e9 que par un utilisateur disposant du r\u00f4le "
        "<b>Manager</b> ou <b>Admin</b>. Une confirmation est demand\u00e9e avant le "
        "lancement pour \u00e9viter les d\u00e9clenchements accidentels."
    ))

    s.append(H2("7.2 \u00c9tapes du cycle"))
    s.append(P("Le cycle se d\u00e9roule en cinq \u00e9tapes s\u00e9quentielles\u202f:"))
    s.append(make_table(
        ["\u00c9tape", "Description", "Dur\u00e9e typ."],
        [
            ["1. Analyse", "Les 4 agents IA analysent les donn\u00e9es de march\u00e9 en parall\u00e8le\u202f: cours, volumes, indicateurs techniques, signaux alternatifs", "15-30s"],
            ["2. Filtrage", "Les th\u00e8ses \u00e0 haute conviction (score \u2265\u202f7) sont s\u00e9lectionn\u00e9es et transform\u00e9es en propositions d\u2019ordres", "2-5s"],
            ["3. Contr\u00f4le risque", "Le moteur de risque \u00e9value chaque proposition\u202f: exposition, concentration, VaR marginal, corr\u00e9lation", "1-3s"],
            ["4. Ex\u00e9cution", "Les ordres approuv\u00e9s sont ex\u00e9cut\u00e9s en mode <i>paper trading</i> (simulation)", "1-2s"],
            ["5. M\u00e9mo IC", "Un m\u00e9mo du comit\u00e9 d\u2019investissement est g\u00e9n\u00e9r\u00e9 automatiquement", "3-5s"],
        ],
        col_widths=[3*cm, AVAIL_W - 4.8*cm, 1.8*cm],
    ))

    s.append(H2("7.3 Suivi en temps r\u00e9el"))
    s.append(P(
        "Pendant l\u2019ex\u00e9cution du cycle, une barre de progression s\u2019affiche en "
        "haut de l\u2019\u00e9cran, indiquant l\u2019\u00e9tape en cours. L\u2019ensemble du cycle "
        "dure g\u00e9n\u00e9ralement entre <b>20 et 45 secondes</b> selon le nombre de "
        "titres en portefeuille et la complexit\u00e9 des analyses. Une notification "
        "est envoy\u00e9e \u00e0 la fin du cycle."
    ))

    s.append(H2("7.4 Mode Paper Trading"))
    s.append(P(
        "Par d\u00e9faut, Thesium Desk fonctionne en <b>paper trading</b>\u202f: toutes les "
        "ex\u00e9cutions sont <b>simul\u00e9es</b>. Le syst\u00e8me applique un slippage r\u00e9aliste "
        "de <b>0,1\u202f%</b> sur chaque transaction pour refl\u00e9ter les conditions de march\u00e9. "
        "Aucun ordre r\u00e9el n\u2019est envoy\u00e9 aux march\u00e9s."
    ))
    s.append(P(
        "Le paper trading permet de valider la strat\u00e9gie, d\u2019\u00e9valuer la performance "
        "des agents et de calibrer les param\u00e8tres de risque avant tout passage en production. "
        "Les r\u00e9sultats simul\u00e9s sont enregistr\u00e9s avec le m\u00eame niveau de d\u00e9tail que "
        "des ex\u00e9cutions r\u00e9elles."
    ))
    s.append(N(
        "<b>Attention\u202f:</b> le passage en mode <i>live trading</i> n\u00e9cessite "
        "une configuration sp\u00e9cifique par l\u2019administrateur et des autorisations "
        "r\u00e9glementaires. Contactez votre \u00e9quipe technique pour activer ce mode."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  8. LES 4 AGENTS IA
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("8. Les 4 Agents de Recherche IA"))
    s.append(teal_divider())

    s.append(P(
        "Thesium Desk int\u00e8gre quatre agents de recherche sp\u00e9cialis\u00e9s, chacun "
        "analysant les donn\u00e9es de march\u00e9 sous un angle diff\u00e9rent. Leurs th\u00e8ses "
        "sont compl\u00e9mentaires et peuvent converger ou diverger sur un m\u00eame titre."
    ))
    s.append(P(
        "Chaque agent fonctionne de mani\u00e8re ind\u00e9pendante et produit ses analyses "
        "en parall\u00e8le lors du cycle de d\u00e9cision. L\u2019agr\u00e9gation des signaux "
        "multi-agents constitue la force diff\u00e9renciante de Thesium Desk\u202f: "
        "elle r\u00e9duit le risque li\u00e9 \u00e0 la d\u00e9pendance envers un seul mod\u00e8le."
    ))

    # MacroAgent
    s.append(H2("8.1 MacroAgent"))
    s.append(P(
        "Le MacroAgent se concentre sur l\u2019analyse <b>macro\u00e9conomique et technique</b> "
        "des grands indices am\u00e9ricains\u202f: <b>SPY</b> (S&amp;P 500), <b>QQQ</b> (Nasdaq 100) "
        "et <b>DIA</b> (Dow Jones)."
    ))
    s.append(H3("Indicateurs analys\u00e9s"))
    s.append(B("<b>Croisements SMA 50/200</b> \u2014 d\u00e9tection des <i>Golden Cross</i> (haussier) et <i>Death Cross</i> (baissier)"))
    s.append(B("<b>RSI</b> \u2014 identification des zones de surachat (&gt;\u202f70) et de survente (&lt;\u202f30)"))
    s.append(B("<b>Momentum</b> \u2014 mesure de la force directionnelle du march\u00e9"))
    s.append(H3("Signal de sortie"))
    s.append(P(
        "Stance globale\u202f: <b>Risk-On</b> (favorable aux actifs risqu\u00e9s), "
        "<b>Risk-Off</b> (d\u00e9fensif) ou <b>Neutre</b>. Ce signal influence "
        "le dimensionnement global des positions propos\u00e9es par les autres agents."
    ))

    # FactorAgent
    s.append(H2("8.2 FactorAgent"))
    s.append(P(
        "Le FactorAgent applique une approche d\u2019investissement <b>factoriel</b>, "
        "\u00e9valuant chaque titre selon trois dimensions."
    ))
    s.append(H3("Facteurs analys\u00e9s"))
    s.append(B("<b>Momentum (12-1 mois)</b> \u2014 rendement sur 12 mois hors dernier mois, capturant la tendance \u00e0 moyen terme"))
    s.append(B("<b>Qualit\u00e9 (volatilit\u00e9 inverse)</b> \u2014 les titres \u00e0 faible volatilit\u00e9 sont consid\u00e9r\u00e9s de meilleure qualit\u00e9"))
    s.append(B("<b>RSI</b> \u2014 signal de timing pour affiner les entr\u00e9es/sorties"))
    s.append(H3("Signal de sortie"))
    s.append(P(
        "Score composite <b>0\u201310</b> et recommandation\u202f: "
        "<b>Surpond\u00e9rer</b>, <b>Sous-pond\u00e9rer</b> ou <b>Neutre</b>."
    ))

    # MicrostructureAgent
    s.append(H2("8.3 MicrostructureAgent"))
    s.append(P(
        "Le MicrostructureAgent analyse la <b>microstructure de march\u00e9</b>\u202f: "
        "patterns de prix, volumes et volatilit\u00e9 \u00e0 court terme."
    ))
    s.append(H3("Indicateurs analys\u00e9s"))
    s.append(B("<b>Bandes de Bollinger</b> \u2014 cassures de volatilit\u00e9 (prix hors bandes \u00e0 \u00b12\u03c3)"))
    s.append(B("<b>Ratio volume</b> \u2014 volume actuel vs. moyenne pour d\u00e9tecter les anomalies"))
    s.append(B("<b>RSI</b> \u2014 confirmation des signaux de surachat/survente"))
    s.append(B("<b>Support/R\u00e9sistance</b> \u2014 niveaux de prix cl\u00e9s historiques"))
    s.append(B("<b>ATR</b> (<i>Average True Range</i>) \u2014 volatilit\u00e9 r\u00e9cente pour le dimensionnement"))
    s.append(H3("Signal de sortie"))
    s.append(P("Signaux directionnels\u202f: <b>Buy</b>, <b>Sell</b> ou <b>Hold</b>."))

    # AltDataAgent
    s.append(H2("8.4 AltDataAgent"))
    s.append(P(
        "L\u2019AltDataAgent exploite des <b>donn\u00e9es alternatives</b> et des indicateurs "
        "statistiques avanc\u00e9s pour compl\u00e9ter les analyses techniques classiques."
    ))
    s.append(H3("Indicateurs analys\u00e9s"))
    s.append(B("<b>Divergence prix-volume</b> \u2014 signal pr\u00e9coce de retournement"))
    s.append(B("<b>Consistance de tendance</b> \u2014 r\u00e9gularit\u00e9 sur plusieurs horizons temporels"))
    s.append(B("<b>Z-score des rendements</b> \u2014 \u00e9cart normalis\u00e9 vs. distribution historique"))
    s.append(H3("Signal de sortie"))
    s.append(P("Sentiment\u202f: <b>Haussier</b>, <b>Baissier</b> ou <b>Neutre</b>."))

    # Summary table
    s.append(SP(6))
    s.append(H2("8.5 Tableau r\u00e9capitulatif"))
    s.append(make_table(
        ["Agent", "Approche", "Indicateurs cl\u00e9s", "Signal"],
        [
            ["MacroAgent", "Macro / Technique", "SMA 50/200, RSI, Momentum", "Risk-On / Off / Neutre"],
            ["FactorAgent", "Factoriel", "Momentum 12-1, Vol. inv., RSI", "Sur-/Sous-pond. / Neutre"],
            ["MicrostructureAgent", "Microstructure", "Bollinger, Volume, ATR, S/R", "Buy / Sell / Hold"],
            ["AltDataAgent", "Donn\u00e9es alt.", "Div. prix-vol., Tendance, Z-score", "Haussier / Baissier / Neutre"],
        ],
        col_widths=[3.2*cm, 2.8*cm, 4.8*cm, AVAIL_W - 10.8*cm],
    ))
    s.append(SP(4))
    s.append(N(
        "<b>Personnalisation\u202f:</b> les param\u00e8tres de chaque agent (seuils, horizons, "
        "p\u00e9riodes de calcul) peuvent \u00eatre ajust\u00e9s par un administrateur via "
        "le panneau <b>Settings > Agent Configuration</b>. Toute modification est "
        "trac\u00e9e dans le journal d\u2019audit."
    ))

    # ═══════════════════════════════════════════════════════════════
    #  9. GLOSSAIRE
    # ═══════════════════════════════════════════════════════════════
    s.append(PageBreak())
    s.append(H1("9. Glossaire"))
    s.append(teal_divider())

    s.append(P(
        "Ce glossaire d\u00e9finit les termes techniques utilis\u00e9s dans "
        "Thesium Desk et dans ce guide."
    ))

    glossary = [
        ["AIFMD", "<i>Alternative Investment Fund Managers Directive</i>. Directive europ\u00e9enne encadrant les gestionnaires de fonds d\u2019investissement alternatifs."],
        ["ATR", "<i>Average True Range</i>. Indicateur de volatilit\u00e9 mesurant l\u2019amplitude moyenne des variations de prix sur une p\u00e9riode donn\u00e9e (g\u00e9n\u00e9ralement 14\u202fjours)."],
        ["Bandes de Bollinger", "Enveloppe de prix\u202f: moyenne mobile centrale \u00b1\u202f2 \u00e9carts-types. Une cassure au-del\u00e0 des bandes signale un exc\u00e8s de volatilit\u00e9."],
        ["Benchmark", "Indice ou portefeuille de r\u00e9f\u00e9rence utilis\u00e9 pour \u00e9valuer la performance relative du fonds."],
        ["Conviction Score", "Note de 1 \u00e0 10 attribu\u00e9e par un agent IA. Plus le score est \u00e9lev\u00e9, plus l\u2019agent est confiant dans sa recommandation."],
        ["Death Cross", "Croisement baissier\u202f: la SMA 50j passe <b>sous</b> la SMA 200j, signalant un potentiel retournement \u00e0 la baisse."],
        ["Drawdown", "Perte maximale observ\u00e9e entre un pic et un creux de la courbe d\u2019\u00e9quit\u00e9, exprim\u00e9e en pourcentage."],
        ["EMA", "<i>Exponential Moving Average</i>. Moyenne mobile exponentielle, donnant plus de poids aux donn\u00e9es r\u00e9centes."],
        ["Golden Cross", "Croisement haussier\u202f: la SMA 50j passe <b>au-dessus</b> de la SMA 200j, signal haussier."],
        ["IC Memo", "M\u00e9mo du Comit\u00e9 d\u2019Investissement. Document g\u00e9n\u00e9r\u00e9 automatiquement servant de trace d\u2019audit."],
        ["MiFID\u202fII", "Directive europ\u00e9enne sur les march\u00e9s d\u2019instruments financiers, imposant des obligations de transparence et de best execution."],
        ["Paper Trading", "Mode de simulation\u202f: les ordres sont ex\u00e9cut\u00e9s virtuellement sans impact sur les march\u00e9s r\u00e9els."],
        ["RSI", "<i>Relative Strength Index</i>. Oscillateur 0\u2013100. Au-dessus de 70\u202f: surachat\u202f; en dessous de 30\u202f: survente."],
        ["Slippage", "\u00c9cart entre le prix attendu et le prix obtenu. En paper trading\u202f: 0,1\u202f% simul\u00e9."],
        ["SMA", "<i>Simple Moving Average</i>. Moyenne arithm\u00e9tique des cours de cl\u00f4ture sur N jours."],
        ["Stop-Loss", "Ordre automatique de vente d\u00e9clench\u00e9 sous un seuil pr\u00e9d\u00e9fini, limitant la perte."],
        ["Th\u00e8se", "Recommandation d\u2019investissement argument\u00e9e g\u00e9n\u00e9r\u00e9e par un agent IA."],
        ["VaR", "<i>Value at Risk</i>. Perte maximale probable sur un horizon donn\u00e9 (95\u202f% dans Thesium Desk)."],
    ]

    g_header = [Paragraph("Terme", styles["table_header"]),
                Paragraph("D\u00e9finition", styles["table_header"])]
    g_data = [g_header]
    for term, defn in glossary:
        g_data.append([
            Paragraph(f"<b>{term}</b>", styles["table_cell_bold"]),
            Paragraph(defn, styles["table_cell"]),
        ])
    g_table = Table(g_data, colWidths=[3.5*cm, AVAIL_W - 3.5*cm], repeatRows=1)
    g_table.setStyle(TableStyle([
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
    s.append(g_table)

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
        "la documentation en ligne sur <b>docs.thesium.finance</b>.",
        end_sub,
    ))
    s.append(SP(14))
    s.append(Paragraph("Thesium.finance \u2014 Version 1.0 \u2014 Mars 2026", end_brand))
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
        title="Guide Utilisateur \u2014 Thesium Desk",
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
