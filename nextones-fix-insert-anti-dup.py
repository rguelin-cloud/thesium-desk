# -*- coding: utf-8 -*-
"""
[FIX_INSERT_ANTI_DUP_V1]
Patche universe_expansion_agent.py:insert_candidates() pour ne pas inserer
de doublons : si un candidat pending sur le meme ticker existe deja, on le
marque 'superseded' AVANT d'inserer la nouvelle entree.

Avantages :
  - plus de doublons en pending
  - historique conserve (status='superseded')
  - le dedupe manuel n'est plus necessaire

Idempotent via marker [ANTI_DUP_V1].
"""
import re
import shutil
import datetime
import ast
import py_compile
from pathlib import Path

AGENT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\universe_expansion_agent.py")
MARK = "# [ANTI_DUP_V1]"

# Snippet a injecter au debut de la boucle for f in features :
SUPERSEDE_LINE = (
    "        conn.execute("
    "\"UPDATE universe_candidates SET status='superseded' "
    "WHERE ticker=? AND status='pending';\", "
    "(f.ticker,))  " + MARK
)


def main():
    if not AGENT.exists():
        print(f"[ERR] {AGENT} introuvable")
        return

    raw = AGENT.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    txt = raw.decode("utf-8", errors="replace")

    if MARK in txt:
        print(f"[SKIP] {MARK} deja present")
        return

    # On cherche la ligne "for f in features:" dans insert_candidates
    # et on insere notre UPDATE juste apres.
    # On veut la PREMIERE occurrence apres "def insert_candidates"
    m_func = re.search(r"def\s+insert_candidates\s*\(", txt)
    if not m_func:
        print("[ERR] def insert_candidates introuvable")
        return

    after_func = txt[m_func.end():]
    m_for = re.search(r"^(\s+)for\s+f\s+in\s+features\s*:\s*\n", after_func, re.MULTILINE)
    if not m_for:
        print("[ERR] 'for f in features:' introuvable apres def insert_candidates")
        return

    abs_pos = m_func.end() + m_for.end()  # juste apres la ligne 'for f in features:\n'
    # On verifie qu'on n'est pas au-dela d'un autre def (securite)
    next_def = re.search(r"^def\s+\w", after_func[m_for.end():], re.MULTILINE)
    if next_def and next_def.start() < 0:
        print("[ERR] limite fonction depassee")
        return

    new_txt = txt[:abs_pos] + SUPERSEDE_LINE + "\n" + txt[abs_pos:]

    # Validation
    try:
        ast.parse(new_txt)
        print("[OK] ast.parse OK")
    except SyntaxError as e:
        print(f"[ERR SYNTAX] {e}")
        bad = AGENT.with_suffix(".py.bad-anti-dup")
        bad.write_text(new_txt, encoding="utf-8")
        print(f"[ERR] dump dans {bad.name}")
        return

    # Backup + ecriture
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = AGENT.with_suffix(f".py.bak-{ts}-pre-anti-dup")
    shutil.copy2(AGENT, bak)
    print(f"[BAK] {bak.name}")

    AGENT.write_bytes(new_txt.encode("utf-8"))

    try:
        py_compile.compile(str(AGENT), doraise=True)
        print("[OK] py_compile OK")
    except py_compile.PyCompileError as e:
        print(f"[ERR py_compile] {e}")
        return

    # Affiche le bloc patche
    print()
    print("=" * 60)
    print("Bloc insert_candidates apres patch :")
    print("=" * 60)
    final_lines = new_txt.split("\n")
    # Retrouver la ligne for f in features
    for i, line in enumerate(final_lines, 1):
        if "for f in features" in line and "insert_candidates" in "\n".join(final_lines[max(0, i - 20):i]):
            for j in range(i - 1, min(len(final_lines), i + 4)):
                print(f"  {j + 1:4d}: {final_lines[j]}")
            break

    print()
    print("Patch applique. Au prochain scan, plus aucun doublon pending.")


if __name__ == "__main__":
    main()
