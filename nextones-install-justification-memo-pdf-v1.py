"""
Patch 5b/6 - Memo IC PDF : enrichit _build_proposed_changes_section
====================================================================

Modifie memo_generator.py (L147-188) :

1) SELECT : ajoute o.justification
2) Table markdown : ajoute colonne "Justification"
3) Row : affiche justification (truncated 80 chars) ou tiret cadratin

Marker : # [JUSTIFICATION_MEMO_V1]
Idempotent (skip si marker present)
Backup memo_generator.py.bak.<TS>
"""
import os
import re
import shutil
import sys
import time

F = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\memo_generator.py"
MARK = "# [JUSTIFICATION_MEMO_V1]"
TS = time.strftime("%Y%m%d_%H%M%S")


# ---------- Ancien bloc (L149-188 exact) ----------
OLD_BLOCK = '''    orders = conn.execute(
        """SELECT o.id, o.side, o.quantity, o.status, o.risk_check_result,
                  i.ticker, i.name,
                  f.fill_price, f.slippage, f.fees
           FROM orders o
           JOIN instruments i ON i.id = o.instrument_id
           LEFT JOIN fills f ON f.order_id = o.id
           ORDER BY o.created_at DESC
           LIMIT 10"""
    ).fetchall()

    if not orders:
        return "## Proposed Changes & Executions\\n\\n*No orders in this cycle.*\\n\\n"

    lines = [
        "## Proposed Changes & Executions",
        "",
        "| Order ID | Ticker | Side | Qty | Status | Fill Price | Slippage | Risk Notes |",
        "|----------|--------|------|-----|--------|------------|----------|------------|",
    ]

    for o in orders:
        risk_check = {}
        try:
            risk_check = json.loads(o["risk_check_result"]) if o["risk_check_result"] else {}
        except Exception:
            pass

        risk_notes = risk_check.get("action", "N/A")
        fill_str = f"${o['fill_price']:.2f}" if o["fill_price"] else "\u2013"
        slip_str = f"${o['slippage']:.2f}" if o["slippage"] else "\u2013"

        lines.append(
            f"| #{o['id']} | {o['ticker']} | {o['side'].upper()} | "
            f"{int(o['quantity'])} | {o['status']} | "
            f"{fill_str} | {slip_str} | {risk_notes} |"
        )

    lines.append("")
    return "\\n".join(lines) + "\\n"'''


NEW_BLOCK = '''    # [JUSTIFICATION_MEMO_V1] ajoute colonne justification au tableau
    orders = conn.execute(
        """SELECT o.id, o.side, o.quantity, o.status, o.risk_check_result,
                  o.justification,
                  i.ticker, i.name,
                  f.fill_price, f.slippage, f.fees
           FROM orders o
           JOIN instruments i ON i.id = o.instrument_id
           LEFT JOIN fills f ON f.order_id = o.id
           ORDER BY o.created_at DESC
           LIMIT 10"""
    ).fetchall()

    if not orders:
        return "## Proposed Changes & Executions\\n\\n*No orders in this cycle.*\\n\\n"

    lines = [
        "## Proposed Changes & Executions",
        "",
        "| Order ID | Ticker | Side | Qty | Status | Fill Price | Slippage | Risk Notes | Justification |",
        "|----------|--------|------|-----|--------|------------|----------|------------|---------------|",
    ]

    for o in orders:
        risk_check = {}
        try:
            risk_check = json.loads(o["risk_check_result"]) if o["risk_check_result"] else {}
        except Exception:
            pass

        risk_notes = risk_check.get("action", "N/A")
        fill_str = f"${o['fill_price']:.2f}" if o["fill_price"] else "\u2013"
        slip_str = f"${o['slippage']:.2f}" if o["slippage"] else "\u2013"

        # [JUSTIFICATION_MEMO_V1] extraction + truncate + escape pipes markdown
        _just_raw = o["justification"] if "justification" in o.keys() else None
        if _just_raw:
            _just_clean = str(_just_raw).replace("|", "/").replace("\\n", " ").strip()
            if len(_just_clean) > 100:
                _just_clean = _just_clean[:97] + "..."
        else:
            _just_clean = "\u2014"

        lines.append(
            f"| #{o['id']} | {o['ticker']} | {o['side'].upper()} | "
            f"{int(o['quantity'])} | {o['status']} | "
            f"{fill_str} | {slip_str} | {risk_notes} | {_just_clean} |"
        )

    lines.append("")
    return "\\n".join(lines) + "\\n"'''


def main():
    if not os.path.exists(F):
        print("[ERR] file not found:", F)
        return 2

    with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
        src = fh.read()

    if MARK in src:
        print("[SKIP] memo PDF patch already applied (marker present)")
        return 0

    if OLD_BLOCK not in src:
        print("[ERR] OLD_BLOCK not found verbatim")
        # dump 5 premieres lignes attendues
        print("[DEBUG] premieres lignes attendues :")
        for i, ln in enumerate(OLD_BLOCK.splitlines()[:8]):
            print(f"  OLD[{i}]: {ln!r}")
        # cherche fonction
        m = re.search(r"def _build_proposed_changes_section", src)
        if m:
            ln = src[:m.start()].count("\n") + 1
            print(f"[HINT] fonction trouvee L{ln}, mais body diverge du modele")
            # dump 45 lignes
            lines_src = src.splitlines()
            for k in range(ln, min(len(lines_src), ln + 45)):
                print(f"  L{k+1}: {lines_src[k][:220]!r}")
        return 3

    print("[OK] OLD_BLOCK found verbatim")

    new_src = src.replace(OLD_BLOCK, NEW_BLOCK, 1)

    if new_src == src:
        print("[ERR] no change produced")
        return 4

    # Validation syntaxique
    try:
        compile(new_src, F, "exec")
        print("[OK] compile() passes on patched source")
    except SyntaxError as e:
        print(f"[ERR] SyntaxError post-patch: {e}")
        return 5

    # Backup + write
    bak = F + ".bak." + TS
    shutil.copy2(F, bak)
    print("[BAK]", bak)

    with open(F, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_src)
    print("[OK] written:", F)

    # Sanity checks
    with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
        check = fh.read()

    checks = [
        ("[JUSTIFICATION_MEMO_V1]", "marker present"),
        ("o.justification,", "SELECT enrichi"),
        ("| Justification |", "col header table"),
        ("|---------------|", "col separator table"),
        ("_just_clean", "variable truncate"),
    ]
    print()
    print("[POST-WRITE CHECKS]")
    for needle, label in checks:
        n = check.count(needle)
        tag = "OK" if n > 0 else "MISSING"
        print(f"  [{tag}] {label}: {n} occurrences")

    print()
    print("[NEXT] Restart uvicorn (memo_generator est charge en memoire)")
    print("[NEXT] Puis regenere un memo IC (cycle nouveau OU force via endpoint)")
    print("[DONE] Jalon 10 complet apres validation visuelle")
    return 0


if __name__ == "__main__":
    sys.exit(main())
