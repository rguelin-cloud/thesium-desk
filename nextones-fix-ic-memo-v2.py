# -*- coding: ascii -*-
# [MARKER] nextones-fix-ic-memo-v2
#
# Fix v2 export PDF IC Memo - remplace integralement la fonction get_memo_pdf
# dans api_server.py par une version corrigee.
#
# Bugs corriges :
#   B1 corps vide IC-Memo-49      -> pre-trait md : "\\n" -> "\n", XML escape robuste
#   B2 double ligne header page 1 -> 1 seule ligne header
#   B3 mojibake /!\ (!) (OK) etc. -> enregistre DejaVuSans (fallback Arial Unicode
#                                    -> fallback Helvetica) + substitution glyphes
#   B4 titre placeholder          -> "Comite d'Investissement -- {date} -- N ordres"
#
# Strategie :
#   - Detecter bornes de get_memo_pdf via regex sur la route
#   - Backup automatique horodate
#   - Idempotent : si marker [ICMEMO_PDF_V2] deja present, skip
#   - Validation py_compile sur api_server.py apres ecriture
#
# Usage :
#   py -3.13 .\nextones-fix-ic-memo-v2.py
#   # Puis redemarrer uvicorn et retelecharger IC-Memo-49 et IC-Memo-49 (dernier id)

import io
import os
import py_compile
import re
import shutil
import sys
import time

API_FILE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
MARKER   = "[ICMEMO_PDF_V2]"

# ---------- I/O helpers ----------

def read_utf8(p):
    with open(p, "rb") as f:
        b = f.read()
    if b.startswith(b"\xef\xbb\xbf"):
        b = b[3:]
    return b.decode("utf-8")

def write_utf8(p, s):
    with open(p, "wb") as f:
        f.write(s.encode("utf-8"))

def banner(t):
    print("")
    print("=" * 72)
    print("== " + t)
    print("=" * 72)

# ---------- Nouveau code de la fonction (sans la ligne de route) ----------
# Important : seules de l'indentation 0 sur les lignes pour pouvoir prefixer
# par "" lors de l'insertion. La route @app.get(...) est ajoutee separement.

NEW_FUNC = r'''@app.get("/api/memos/{memo_id}/pdf")  # [ICMEMO_PDF_V2]
def get_memo_pdf(memo_id: int):
    """Generate and return a styled PDF export of an IC memo. [ICMEMO_PDF_V2]"""
    conn = db()
    try:
        row = conn.execute("SELECT * FROM ic_memos WHERE id = ?", (memo_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Memo not found")
        memo = row_to_dict(row)
    finally:
        conn.close()

    import io as _io
    import json as _json
    import os as _os
    import re as _re
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether,
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # -- Brand colors --
    DARK_NAVY   = HexColor("#091717")
    OFFBLACK    = HexColor("#13343B")
    DEEP_TEAL   = HexColor("#115058")
    MUTED_TEAL  = HexColor("#20808D")
    OFF_WHITE   = HexColor("#FCFAF6")
    PAPER_WHITE = HexColor("#F3F3EE")
    WARM_BEIGE  = HexColor("#E5E3D4")
    TERRA       = HexColor("#A84B2F")
    GREEN_OK    = HexColor("#70AD47")

    W, H = A4
    buf = _io.BytesIO()

    # -- Police Unicode : DejaVu si dispo, sinon Arial Unicode, sinon Helvetica --
    FONT_REG  = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"
    _font_candidates = [
        ("DejaVuSans",      "DejaVuSans-Bold",
         r"C:\Windows\Fonts\DejaVuSans.ttf",
         r"C:\Windows\Fonts\DejaVuSans-Bold.ttf"),
        ("ArialUnicode",    "ArialUnicodeBold",
         r"C:\Windows\Fonts\ARIALUNI.TTF",
         r"C:\Windows\Fonts\ARIALUNI.TTF"),
    ]
    for fr_name, fb_name, fr_path, fb_path in _font_candidates:
        if _os.path.exists(fr_path):
            try:
                pdfmetrics.registerFont(TTFont(fr_name, fr_path))
                if _os.path.exists(fb_path) and fb_path != fr_path:
                    pdfmetrics.registerFont(TTFont(fb_name, fb_path))
                    FONT_REG  = fr_name
                    FONT_BOLD = fb_name
                else:
                    FONT_REG  = fr_name
                    FONT_BOLD = fr_name
                break
            except Exception as _fe:
                print(f"[ICMEMO_PDF_V2] font registration failed for {fr_name}: {_fe}")

    # -- Substitution glyphes safe : pre-traite le markdown avant rendu --
    def _normalize_glyphes(text):
        if text is None:
            return ""
        if isinstance(text, bytes):
            try:
                text = text.decode("utf-8")
            except Exception:
                text = text.decode("latin-1", errors="replace")
        # Si on a une vraie police Unicode, on prefere les vrais symboles
        if FONT_REG != "Helvetica":
            sub = {
                "/!\\":   "\u26a0",  # warning sign
                "(!)":    "\u25b2",  # black up-pointing triangle
                "(OK)":   "\u2713",  # check mark
                "[WARN]": "\u26a0",
                "[OK]":   "\u2713",
                "[X]":    "\u2717",
                "[!]":    "\u26a0",
            }
        else:
            # Helvetica : pas de glyphes etendus, on garde ASCII propre
            sub = {
                "/!\\":   "[!]",
                "(!)":    "[!]",
                "(OK)":   "[OK]",
                "[WARN]": "[!]",
            }
        for k, v in sub.items():
            text = text.replace(k, v)
        return text

    # -- Calcul du titre significatif (B4) --
    raw_date = memo.get("date", "") or ""
    raw_title = memo.get("title", "") or ""
    proposed_raw = memo.get("proposed_changes")
    proposed_list = []
    if isinstance(proposed_raw, str):
        try:
            proposed_list = _json.loads(proposed_raw)
        except Exception:
            proposed_list = []
    elif isinstance(proposed_raw, list):
        proposed_list = proposed_raw
    n_ords  = len(proposed_list) if isinstance(proposed_list, list) else 0
    n_buys  = sum(1 for p in proposed_list
                  if str(p.get("side", "")).lower() == "buy") if proposed_list else 0
    n_sells = sum(1 for p in proposed_list
                  if str(p.get("side", "")).lower() == "sell") if proposed_list else 0

    if n_ords > 0:
        pdf_title = f"Comite d'Investissement -- {raw_date} -- {n_ords} propositions ({n_buys} achats / {n_sells} ventes)"
    elif raw_title:
        # nettoie tout mojibake potentiel du title DB
        clean = raw_title.replace("\u00fb", "--").replace("\u00f9", "--")
        pdf_title = clean
    else:
        pdf_title = f"IC Memo -- {raw_date}"

    # -- Header / footer : 1 SEULE ligne haute pour eviter le doublon visuel (B2) --
    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(DARK_NAVY)
        canvas.rect(0, H - 18*mm, W, 18*mm, fill=1, stroke=0)
        canvas.setFillColor(MUTED_TEAL)
        canvas.setFont(FONT_BOLD, 11)
        canvas.drawString(15*mm, H - 12*mm, "NEXTONES.FINANCE")
        canvas.setFillColor(white)
        canvas.setFont(FONT_REG, 8)
        canvas.drawRightString(W - 15*mm, H - 12*mm,
                               f"IC Memo -- {raw_date}  |  Paper Trading")
        canvas.setStrokeColor(MUTED_TEAL)
        canvas.setLineWidth(1.2)
        canvas.line(15*mm, H - 18*mm, W - 15*mm, H - 18*mm)
        # Footer bas
        canvas.setFillColor(OFFBLACK)
        canvas.setFont(FONT_REG, 7)
        canvas.drawString(15*mm, 10*mm, "Nextones Desk -- AI-native fund operating system")
        canvas.drawRightString(W - 15*mm, 10*mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        title=pdf_title,
        author="Nextones.finance",
        subject=f"IC Memo {raw_date}",
        topMargin=24*mm,
        bottomMargin=20*mm,
        leftMargin=15*mm,
        rightMargin=15*mm,
    )

    styles = getSampleStyleSheet()
    sH1 = ParagraphStyle("MemoH1", parent=styles["Heading1"],
        fontSize=16, leading=20, textColor=OFFBLACK,
        spaceAfter=6, spaceBefore=12, fontName=FONT_BOLD)
    sH2 = ParagraphStyle("MemoH2", parent=styles["Heading2"],
        fontSize=12, leading=15, textColor=DEEP_TEAL,
        spaceAfter=4, spaceBefore=10, fontName=FONT_BOLD)
    sBody = ParagraphStyle("MemoBody", parent=styles["Normal"],
        fontSize=9.5, leading=13, textColor=OFFBLACK,
        spaceAfter=4, fontName=FONT_REG)
    sBullet = ParagraphStyle("MemoBullet", parent=sBody,
        leftIndent=12, bulletIndent=4, spaceBefore=1, spaceAfter=1)
    sSmall = ParagraphStyle("MemoSmall", parent=sBody,
        fontSize=8, leading=10, textColor=HexColor("#5a7a7e"))

    story = []
    # Cover bloc : titre significatif en tete de premiere page
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(_normalize_glyphes(pdf_title), sH1))
    if n_ords > 0:
        story.append(Paragraph(
            f"<i>{n_ords} ordres proposes &middot; {n_buys} achats &middot; {n_sells} ventes</i>",
            sSmall))
    story.append(HRFlowable(width="100%", thickness=0.8,
                            color=WARM_BEIGE, spaceAfter=6, spaceBefore=6))

    # -- Parse markdown : B1 fix --
    md = memo.get("full_markdown") or ""
    if not md:
        md = f"# {pdf_title}\\n\\nAucun contenu structure pour ce memo."
    # B1 : si la DB contient des "\\n" echappes au lieu de vrais retours ligne
    if "\\n" in md and md.count("\n") < 3:
        md = md.replace("\\n", "\n")
    md = _normalize_glyphes(md)
    lines = md.split("\n")

    def _xml_escape(s):
        return (s.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;"))

    def flush_md_table(table_rows, separator_idx):
        if not table_rows:
            return []
        header = [c.strip() for c in table_rows[0].strip("|").split("|")]
        body_rows = []
        start = separator_idx if separator_idx is not None else 1
        for row_str in table_rows[start:]:
            cells = [c.strip() for c in row_str.strip("|").split("|")]
            body_rows.append(cells)
        col_count = len(header)
        if col_count == 0:
            return []
        available_width = W - 30*mm
        col_w = available_width / col_count
        col_widths = [col_w] * col_count
        sTH = ParagraphStyle("TH", parent=sBody, fontSize=7.5, leading=9.5,
            textColor=white, fontName=FONT_BOLD)
        sTC = ParagraphStyle("TC", parent=sBody, fontSize=7.5, leading=9.5,
            fontName=FONT_REG)
        data = [[Paragraph(_re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', _xml_escape(h)), sTH)
                 for h in header]]
        for r in body_rows:
            row = []
            for c in r:
                c2 = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', _xml_escape(c))
                row.append(Paragraph(c2, sTC))
            data.append(row)
        for row in data:
            while len(row) < col_count:
                row.append(Paragraph("", sTC))
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DEEP_TEAL),
            ("TEXTCOLOR",  (0, 0), (-1, 0), white),
            ("FONTNAME",   (0, 0), (-1, 0), FONT_BOLD),
            ("FONTSIZE",   (0, 0), (-1, -1), 7.5),
            ("LEADING",    (0, 0), (-1, -1), 9.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER_WHITE, OFF_WHITE]),
            ("GRID",       (0, 0), (-1, -1), 0.4, WARM_BEIGE),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",  (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        return [KeepTogether([t])]

    pending_table_rows = []
    pending_table_sep = None
    body_paragraphs_count = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            if _re.match(r"^\|[\s\-:]+\|", stripped) and "---" in stripped:
                pending_table_sep = len(pending_table_rows)
            else:
                pending_table_rows.append(stripped)
            continue
        else:
            if pending_table_rows:
                story.extend(flush_md_table(pending_table_rows, pending_table_sep))
                body_paragraphs_count += 1
                pending_table_rows = []
                pending_table_sep = None
        if not stripped:
            story.append(Spacer(1, 3))
            continue
        # Skip premiere ligne H1 si elle reprend juste le titre (eviter doublon avec cover)
        if stripped.startswith("# "):
            txt = _xml_escape(stripped[2:].strip())
            if body_paragraphs_count == 0 and ("ic memo" in txt.lower() or "nextones" in txt.lower()):
                continue
            story.append(Paragraph(txt, sH1))
            body_paragraphs_count += 1
            continue
        if stripped.startswith("## "):
            txt = _xml_escape(stripped[3:].strip())
            story.append(Paragraph(txt, sH2))
            body_paragraphs_count += 1
            continue
        if stripped.startswith("### "):
            txt = _xml_escape(stripped[4:].strip())
            txt = _re.sub(r'\*\*(.+?)\*\*', r'\1', txt)
            story.append(Paragraph(f"<b>{txt}</b>", sBody))
            body_paragraphs_count += 1
            continue
        if stripped.startswith("---"):
            story.append(HRFlowable(width="100%", thickness=0.6,
                                    color=WARM_BEIGE, spaceAfter=4, spaceBefore=4))
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            txt = _xml_escape(stripped[2:].strip())
            txt = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', txt)
            story.append(Paragraph(f"\u2022  {txt}", sBullet))
            body_paragraphs_count += 1
            continue
        # Bold de ligne entiere
        bold_match = _re.match(r"^\*\*(.+?)\*\*(.*)$", stripped)
        if bold_match:
            btxt = _xml_escape(bold_match.group(1))
            rest = _xml_escape(bold_match.group(2).strip())
            txt = f"<b>{btxt}</b>"
            if rest:
                rest = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', rest)
                txt += f" {rest}"
            story.append(Paragraph(txt, sBody))
            body_paragraphs_count += 1
            continue
        # Italic ligne entiere
        if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("**"):
            txt = _xml_escape(stripped.strip("*"))
            story.append(Paragraph(f"<i>{txt}</i>", sSmall))
            body_paragraphs_count += 1
            continue
        # Paragraphe normal
        txt = _xml_escape(stripped)
        txt = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', txt)
        story.append(Paragraph(txt, sBody))
        body_paragraphs_count += 1

    if pending_table_rows:
        story.extend(flush_md_table(pending_table_rows, pending_table_sep))
        body_paragraphs_count += 1

    # B1 garde-fou : si rien n'a ete genere depuis le markdown, ecrit le brut
    if body_paragraphs_count == 0:
        story.append(Paragraph("<i>Contenu markdown non parsable - affichage brut :</i>", sSmall))
        story.append(Spacer(1, 3))
        for chunk in (md or "").split("\n"):
            if chunk.strip():
                story.append(Paragraph(_xml_escape(chunk), sBody))

    # -- Sections structurees (factor_tilts / thesis_summaries / proposed_changes) --
    factor_tilts     = memo.get("factor_tilts")
    thesis_summaries = memo.get("thesis_summaries")
    proposed_changes = memo.get("proposed_changes")
    if factor_tilts and isinstance(factor_tilts, str):
        try: factor_tilts = _json.loads(factor_tilts)
        except Exception: factor_tilts = None
    if thesis_summaries and isinstance(thesis_summaries, str):
        try: thesis_summaries = _json.loads(thesis_summaries)
        except Exception: thesis_summaries = None
    if proposed_changes and isinstance(proposed_changes, str):
        try: proposed_changes = _json.loads(proposed_changes)
        except Exception: proposed_changes = None

    if thesis_summaries and isinstance(thesis_summaries, list) and len(thesis_summaries) > 0:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Thesis Summaries", sH2))
        table_data = [["Ticker", "Agent", "Conviction", "Action"]]
        for ts in thesis_summaries:
            table_data.append([
                Paragraph(f"<b>{_xml_escape(str(ts.get('ticker', '--')))}</b>", sBody),
                Paragraph(_xml_escape(str(ts.get("agent", "--"))), sSmall),
                Paragraph(f"{ts.get('conviction', '--')}/10", sBody),
                Paragraph(_xml_escape(str(ts.get("action", "--"))), sBody),
            ])
        t = Table(table_data, colWidths=[55, 85, 55, None])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DEEP_TEAL),
            ("TEXTCOLOR",  (0, 0), (-1, 0), white),
            ("FONTNAME",   (0, 0), (-1, 0), FONT_BOLD),
            ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
            ("LEADING",    (0, 0), (-1, -1), 11),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER_WHITE, OFF_WHITE]),
            ("GRID",       (0, 0), (-1, -1), 0.4, WARM_BEIGE),
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)

    if proposed_changes and isinstance(proposed_changes, list) and len(proposed_changes) > 0:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Proposed Changes", sH2))
        table_data = [["Ticker", "Side", "Qty", "Status"]]
        for pc in proposed_changes:
            side_str = str(pc.get("side", "--")).upper()
            side_color = GREEN_OK if side_str == "BUY" else TERRA
            table_data.append([
                Paragraph(f"<b>{_xml_escape(str(pc.get('ticker', '--')))}</b>", sBody),
                Paragraph(f'<font color="{side_color}">{side_str}</font>', sBody),
                Paragraph(_xml_escape(str(pc.get("quantity", "--"))), sBody),
                Paragraph(_xml_escape(str(pc.get("status", "--"))).upper(), sSmall),
            ])
        t = Table(table_data, colWidths=[70, 60, 60, None])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DEEP_TEAL),
            ("TEXTCOLOR",  (0, 0), (-1, 0), white),
            ("FONTNAME",   (0, 0), (-1, 0), FONT_BOLD),
            ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
            ("LEADING",    (0, 0), (-1, -1), 11),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER_WHITE, OFF_WHITE]),
            ("GRID",       (0, 0), (-1, -1), 0.4, WARM_BEIGE),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    buf.seek(0)
    from starlette.responses import Response
    safe_date = (raw_date or "memo").replace("/", "-")
    return Response(
        content=buf.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="ic-memo-{memo_id}-{safe_date}.pdf"'},
    )
# === END [ICMEMO_PDF_V2] ===
'''

# ---------- Locate function bounds and patch ----------

def main():
    print("nextones-fix-ic-memo-v2  -  31/05/2026")
    print("FILE : " + API_FILE)
    if not os.path.exists(API_FILE):
        print("[FATAL] api_server.py introuvable")
        sys.exit(1)

    src = read_utf8(API_FILE)
    if MARKER in src:
        print("[SKIP] Marker " + MARKER + " deja present. Patch deja applique.")
        print("       Pour reappliquer : supprimer le bloc entre la route et")
        print("       '# === END [ICMEMO_PDF_V2] ===', puis relancer.")
        return 0

    # Localisation : route + def + corps jusqu'a la prochaine route ou EOF
    route_re = re.compile(r'^@app\.get\("/api/memos/\{memo_id\}/pdf"\)\s*$', re.MULTILINE)
    m = route_re.search(src)
    if not m:
        print("[FATAL] Route @app.get('/api/memos/{memo_id}/pdf') introuvable")
        sys.exit(2)
    start = m.start()

    # Fin = prochaine ligne commencant par '@app.' ou '# [' (autre marker) ou
    # 'def ' a indentation 0 apres le bloc
    rest = src[m.end():]
    end_re = re.compile(
        r'^(?:@app\.(?:get|post|put|delete|patch)|@router\.|# \[|def [A-Za-z_]|class [A-Za-z_])',
        re.MULTILINE
    )
    em = end_re.search(rest)
    if not em:
        print("[FATAL] Fin du bloc get_memo_pdf introuvable")
        sys.exit(3)
    end = m.end() + em.start()

    old_block = src[start:end]
    print("  bornes : L%d -> L%d (len=%d)" %
          (src.count("\n", 0, start) + 1,
           src.count("\n", 0, end) + 1,
           len(old_block)))

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bk = API_FILE + ".bak_icmemo_v2_" + ts
    shutil.copy2(API_FILE, bk)
    print("  backup : " + bk)

    # Sauvegarde du vieux bloc pour reference
    old_bk = os.path.join(os.path.dirname(API_FILE),
                          "_backup_get_memo_pdf_OLD_" + ts + ".py")
    with open(old_bk, "wb") as f:
        f.write(old_block.encode("utf-8"))
    print("  ancien bloc sauve : " + old_bk)

    new_src = src[:start] + NEW_FUNC.rstrip() + "\n\n" + src[end:]
    write_utf8(API_FILE, new_src)
    print("  ecrit  : %d bytes" % len(new_src.encode("utf-8")))

    # Validation py_compile
    try:
        py_compile.compile(API_FILE, doraise=True)
        print("  py_compile : OK")
    except py_compile.PyCompileError as pce:
        print("[FAIL] py_compile : " + str(pce))
        # rollback
        shutil.copy2(bk, API_FILE)
        print("  ROLLBACK depuis " + bk)
        sys.exit(4)

    banner("DONE")
    print("Patch applique. Prochaines etapes :")
    print("  1) Redemarrer l'API : kill uvicorn puis :")
    print("     py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print("  2) Retelecharger 2 PDFs temoins :")
    print("     http://localhost:8000/api/memos/1/pdf")
    print("     http://localhost:8000/api/memos/49/pdf")
    print("  3) Verifier les 4 bugs :")
    print("     B1 corps : doit etre rempli (>1 page de contenu)")
    print("     B2 header: 1 SEULE ligne en haut (titre + date + Paper Trading)")
    print("     B3 glyph : warning -> [!] ou symbole Unicode si DejaVu detecte")
    print("     B4 titre : 'Comite d'Investissement -- 2026-05-31 -- N propositions'")
    return 0

if __name__ == "__main__":
    sys.exit(main())
