"""
nextones-install-risk-v2-wired.py
[RISK_V2_WIRED] - Cable le gate dans create_and_execute_order + section IC Memo.

Mode hybride :
  - concentration  -> BLOCK dur (status=rejected, rejection_reason explicite)
  - var_budget     -> WARNING (ordre passe)
  - var_marginal   -> WARNING (ordre passe)
  - correlation    -> WARNING (ordre passe)

Tout est trace dans risk_check_result.risk_v2 et dans la table risk_pretrade_log.

Roles :
  1. Backup horodate de execution_engine.py + memo_generator.py
  2. Patch execution_engine.create_and_execute_order : appel risk_v2_gate + merge JSON
  3. Patch memo_generator.py : ajoute _build_risk_v2_section + l'insere dans generate_ic_memo
  4. Idempotent (marker [RISK_V2_WIRED]) - validation tags before/after

Usage :
  py -3.13 nextones-install-risk-v2-wired.py

ASCII only.
"""
from __future__ import annotations
import shutil
import sys
import datetime as _dt
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
TS = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / f"_backups_risk_v2_wired_{TS}"

MARKER = "[RISK_V2_WIRED]"

# ============================================================
# Patches
# ============================================================

# 1) execution_engine.py - juste apres `risk_result = check_order(...)`
# On ajoute un bloc qui appelle le gate v2 et merge dans risk_result.
EXEC_HOOK_BEFORE = "risk_result = check_order(conn, instrument_id, thesis_id, side, quantity, effective_price)"

EXEC_HOOK_INSERT = '''
    # [RISK_V2_WIRED] gate hybride - Concentration (block) / VaR + Correlation (warn)
    try:
        # Resolve ticker pour le module risk_pretrade (qui attend ticker, pas instrument_id)
        _rv2_ticker_row = conn.execute(
            "SELECT ticker FROM instruments WHERE id = ?", (instrument_id,)
        ).fetchone()
        _rv2_ticker = _rv2_ticker_row[0] if _rv2_ticker_row else None
        if _rv2_ticker:
            from risk_pretrade import run_pretrade_checks as _rv2_run
            _rv2 = _rv2_run(_rv2_ticker, quantity, effective_price, side)
            # Inject dans le risk_result existant
            if isinstance(risk_result, dict):
                risk_result.setdefault("warnings", [])
                risk_result["risk_v2"] = _rv2
                _rv2_blocked = _rv2.get("blocked_by")
                if _rv2_blocked == "concentration":
                    # BLOCK DUR concentration
                    risk_result["approved"] = False
                    risk_result["action"] = "rejected_concentration_v2"
                    risk_result.setdefault("reasons", []).append(
                        f"[RISK_V2] BLOCK concentration: new_pct={_rv2.get('details',{}).get('concentration',{}).get('new_pct')} cap=15%"
                    )
                elif _rv2_blocked in ("var_budget", "var_marginal", "correlation"):
                    # WARNING (mode hybride - ordre passe)
                    risk_result["warnings"].append({
                        "source": "[RISK_V2]",
                        "code": _rv2_blocked,
                        "details": _rv2.get("details", {}).get(
                            "correlation" if _rv2_blocked == "correlation" else "var", {}
                        ),
                    })
    except Exception as _rv2_err:
        # Fail-safe : ne bloque pas la prod si le module risk_pretrade plante
        if isinstance(risk_result, dict):
            risk_result.setdefault("warnings", []).append({
                "source": "[RISK_V2]",
                "code": "risk_v2_error",
                "message": str(_rv2_err)[:160],
            })
'''


# 2) memo_generator.py - nouvelle section
MEMO_SECTION_FN = '''

# [RISK_V2_WIRED] Pre-trade controls section
def _build_risk_v2_section(conn: sqlite3.Connection) -> str:
    """Render the pre-trade [RISK_V2] controls table for the current cycle's orders."""
    orders = conn.execute(
        """SELECT o.id, o.side, o.quantity, o.status, o.risk_check_result, i.ticker
           FROM orders o JOIN instruments i ON i.id = o.instrument_id
           ORDER BY o.created_at DESC LIMIT 10"""
    ).fetchall()
    if not orders:
        return ""

    rows_seen = 0
    body = []
    for o in orders:
        try:
            rc = json.loads(o["risk_check_result"]) if o["risk_check_result"] else {}
        except Exception:
            rc = {}
        v2 = rc.get("risk_v2")
        if not v2:
            continue
        rows_seen += 1
        d = v2.get("details", {})
        c = d.get("concentration", {}) or {}
        v = d.get("var", {}) or {}
        cor = d.get("correlation", {}) or {}

        blocked = v2.get("blocked_by")
        passed = v2.get("passed", True)
        verdict = "PASS" if passed else f"BLOCK ({blocked})"

        new_pct = c.get("new_pct")
        new_pct_str = f"{(new_pct*100):.2f}%" if isinstance(new_pct, (int, float)) else "n/a"

        var_dm = v.get("delta_marginal_pct")
        var_dm_str = f"{(var_dm*100):.3f}%" if isinstance(var_dm, (int, float)) else (v.get("note", "n/a"))

        cor_max = cor.get("max_correl_value")
        cor_sym = cor.get("max_correl_symbol", "")
        cor_str = (f"{cor_max:.2f} vs {cor_sym}" if isinstance(cor_max, (int, float))
                   else (cor.get("note", "n/a")))

        body.append(
            f"| #{o['id']} | {o['ticker']} | {o['side'].upper()} | "
            f"{int(o['quantity'])} | {verdict} | {new_pct_str} | {var_dm_str} | {cor_str} |"
        )

    if rows_seen == 0:
        return ""

    head = [
        "## Pre-trade Controls [RISK_V2]",
        "",
        "Controls: Concentration 15% per name (BLOCK), VaR historical 99%/1d budget+marginal (WARN), Pearson correlation 60d (WARN).",
        "",
        "| Order | Ticker | Side | Qty | Verdict | Concentration | Delta VaR | Max Correlation |",
        "|-------|--------|------|-----|---------|---------------|-----------|------------------|",
    ]
    return "\\n".join(head + body) + "\\n\\n"
'''


# Insertion sous _build_proposed_changes_section : on ajoute la nouvelle section
# dans la liste `sections = [...]` de generate_ic_memo, juste apres
# _build_proposed_changes_section(conn).
MEMO_LIST_BEFORE = "_build_proposed_changes_section(conn),"
MEMO_LIST_INSERT = "_build_proposed_changes_section(conn),\n        _build_risk_v2_section(conn),  # [RISK_V2_WIRED]"


# ============================================================
# Helpers
# ============================================================
def info(m): print(f"[INFO] {m}")
def ok(m): print(f"[OK]   {m}")
def warn(m): print(f"[WARN] {m}")
def fatal(m):
    print(f"[FATAL] {m}")
    sys.exit(1)


def read_utf8(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig")


def write_utf8(p: Path, content: str) -> None:
    p.write_text(content, encoding="utf-8", newline="\n")


def count(s: str, sub: str) -> int:
    return s.count(sub)


# ============================================================
# Steps
# ============================================================
def step_backup():
    BACKUP.mkdir(parents=True, exist_ok=True)
    for fname in ("execution_engine.py", "memo_generator.py"):
        src = ROOT / fname
        if src.exists():
            shutil.copy2(src, BACKUP / fname)
            ok(f"backup : {fname}")
        else:
            fatal(f"absent : {fname}")
    info(f"dossier backup : {BACKUP}")


def step_patch_execution_engine():
    p = ROOT / "execution_engine.py"
    src = read_utf8(p)

    if MARKER in src:
        info(f"marker {MARKER} deja present dans execution_engine.py - skip patch.")
        return

    if EXEC_HOOK_BEFORE not in src:
        fatal("Ligne d'ancrage 'risk_result = check_order(...)' introuvable.")

    n_before = count(src, EXEC_HOOK_BEFORE)
    if n_before != 1:
        fatal(f"Ligne d'ancrage trouvee {n_before} fois (attendu 1). Abort.")

    # Insertion juste apres la ligne d'ancrage (avant l'INSERT INTO orders)
    new_src = src.replace(
        EXEC_HOOK_BEFORE,
        EXEC_HOOK_BEFORE + "\n" + EXEC_HOOK_INSERT,
        1
    )

    # Verifs avant ecriture
    after_marker = count(new_src, MARKER)
    if after_marker < 1:
        fatal("Patch execution_engine : marker non present apres remplacement.")
    if count(new_src, "INSERT INTO orders") != count(src, "INSERT INTO orders"):
        fatal("Patch execution_engine : nombre d'INSERT INTO orders change. Abort.")

    write_utf8(p, new_src)
    ok(f"execution_engine.py patche - markers {MARKER} : {after_marker}")


def step_patch_memo_generator():
    p = ROOT / "memo_generator.py"
    src = read_utf8(p)

    if MARKER in src:
        info(f"marker {MARKER} deja present dans memo_generator.py - skip patch.")
        return

    # 1. Ajout de la fonction _build_risk_v2_section juste avant generate_ic_memo
    anchor_fn = "def generate_ic_memo(conn: sqlite3.Connection"
    if anchor_fn not in src:
        fatal("Ancre 'def generate_ic_memo' introuvable dans memo_generator.py.")

    new_src = src.replace(anchor_fn, MEMO_SECTION_FN + "\n\n" + anchor_fn, 1)

    # 2. Insertion dans la liste sections =
    if MEMO_LIST_BEFORE not in new_src:
        fatal("Ancre '_build_proposed_changes_section(conn),' introuvable.")
    n = count(new_src, MEMO_LIST_BEFORE)
    if n != 1:
        fatal(f"Ancre _build_proposed_changes_section trouvee {n} fois (attendu 1).")

    new_src = new_src.replace(MEMO_LIST_BEFORE, MEMO_LIST_INSERT, 1)

    after_marker = count(new_src, MARKER)
    if after_marker < 2:
        fatal("Patch memo_generator : markers insuffisants apres remplacement.")

    write_utf8(p, new_src)
    ok(f"memo_generator.py patche - markers {MARKER} : {after_marker}")


def step_validate():
    for fname, expected_min in (("execution_engine.py", 1), ("memo_generator.py", 2)):
        p = ROOT / fname
        src = read_utf8(p)
        n = count(src, MARKER)
        if n < expected_min:
            warn(f"{fname} : {n} markers {MARKER} (attendu >= {expected_min})")
        else:
            ok(f"{fname} : {n} markers {MARKER}")


def step_summary():
    print("")
    print("=" * 60)
    print(f" {MARKER} installation terminee - mode hybride")
    print("=" * 60)
    print("")
    print("Comportement attendu :")
    print("  - Concentration > 15%   -> BLOCK dur (status=rejected)")
    print("  - VaR budget/marginal   -> WARNING trace")
    print("  - Correlation > 0.85    -> WARNING trace")
    print("  - risk_pretrade plante  -> fail-safe (ordre passe, warning)")
    print("")
    print("Test recommande - relance un cycle de decision :")
    print("  py -3.13 -c \"from models import get_db; from execution_engine import run_decision_cycle; "
          "c=get_db(); print(run_decision_cycle(c)); c.commit(); c.close()\"")
    print("")
    print("Inspection apres cycle :")
    print("  py -3.13 -c \"import sqlite3,json; "
          "c=sqlite3.connect(r'C:\\\\Users\\\\RichardGUELIN\\\\Prod\\\\ThesiumDesk\\\\thesium.db'); "
          "c.row_factory=sqlite3.Row; "
          "rows=c.execute('SELECT id,risk_check_result FROM orders ORDER BY id DESC LIMIT 3').fetchall(); "
          "[print('order',r['id'],'->',json.dumps(json.loads(r['risk_check_result']).get('risk_v2',{}).get('blocked_by'),ensure_ascii=False)) for r in rows]\"")
    print("")
    print("Verification IC Memo (regarder full_markdown du dernier memo) :")
    print("  py -3.13 -c \"import sqlite3; "
          "c=sqlite3.connect(r'C:\\\\Users\\\\RichardGUELIN\\\\Prod\\\\ThesiumDesk\\\\thesium.db'); "
          "row=c.execute('SELECT full_markdown FROM ic_memos ORDER BY id DESC LIMIT 1').fetchone(); "
          "md=row[0] if row else ''; "
          "print('PRESENT' if '[RISK_V2]' in md else 'ABSENT')\"")
    print("")


def main():
    if not ROOT.exists():
        fatal(f"ROOT introuvable : {ROOT}")
    print("=" * 60)
    print(f" {MARKER} installer - cablage execution_engine + memo")
    print("=" * 60)
    step_backup()
    step_patch_execution_engine()
    step_patch_memo_generator()
    step_validate()
    step_summary()


if __name__ == "__main__":
    main()
