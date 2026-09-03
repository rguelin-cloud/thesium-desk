"""
[DIAG_PORTFOLIO_CONSTRUCTION_AGENT_V3]
v3 - on cherche la VRAIE definition (pas forcement une classe).
PortfolioConstructionAgent peut etre :
  - une classe
  - une fonction
  - une variable / instance
  - un alias d'import

Strategie : dump tete + grep precis dans portfolio_construction_agent.py
"""

import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

PRIMARY = os.path.join(ROOT, "portfolio_construction_agent.py")

PATTERNS = {
    "class def": re.compile(r"^\s*class\s+\w+"),
    "function def": re.compile(r"^\s*def\s+\w+"),
    "PortfolioConstructionAgent literal": re.compile(
        r"PortfolioConstructionAgent"
    ),
    "INSERT INTO": re.compile(
        r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+\w+", re.IGNORECASE
    ),
    "target_weight": re.compile(r"target_weight(_pct)?\b"),
    "conviction": re.compile(r"\bconviction\b", re.IGNORECASE),
    "agent_type": re.compile(r"agent_type\s*=\s*['\"]"),
    "import portfolio": re.compile(
        r"(from|import)\s+\S*portfolio_construction"
    ),
}


def read_text(path):
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return None


def grep(text, pattern, context=2, limit=20):
    lines = text.splitlines()
    out = []
    for i, ln in enumerate(lines):
        if pattern.search(ln):
            lo = max(0, i - context)
            hi = min(len(lines), i + context + 1)
            block = []
            for k in range(lo, hi):
                marker = ">>>" if k == i else "   "
                block.append("    %s L%-5d %s" % (marker, k + 1, lines[k]))
            out.append("--- L%d ---\n%s" % (i + 1, "\n".join(block)))
            if len(out) >= limit:
                break
    return out


def head_dump(path, n=120):
    txt = read_text(path)
    if not txt:
        return "(read failed)"
    lines = txt.splitlines()
    out = []
    for i, ln in enumerate(lines[:n], 1):
        out.append("    L%-5d %s" % (i, ln))
    if len(lines) > n:
        out.append("    ... (%d lignes total)" % len(lines))
    return "\n".join(out)


def main():
    if not os.path.exists(PRIMARY):
        print("ERROR: PRIMARY not found at %s" % PRIMARY)
        return

    txt = read_text(PRIMARY)
    if not txt:
        print("ERROR: read failed")
        return

    total = len(txt.splitlines())
    print("=" * 78)
    print("FILE : %s (%d lignes)" % (PRIMARY, total))
    print("=" * 78)

    # 1. Head dump (premieres 120 lignes pour voir imports + structure)
    print("")
    print("HEAD (120 lignes) :")
    print("-" * 78)
    print(head_dump(PRIMARY, 120))

    # 2. Toutes les classes
    print("")
    print("=" * 78)
    print("CLASSES dans ce fichier :")
    print("=" * 78)
    for blk in grep(txt, re.compile(r"^\s*class\s+\w+"), context=0, limit=20):
        print(blk)

    # 3. Toutes les fonctions de top-level (indent 0)
    print("")
    print("=" * 78)
    print("FUNCTIONS top-level :")
    print("=" * 78)
    for blk in grep(txt, re.compile(r"^def\s+\w+"), context=0, limit=30):
        print(blk)

    # 4. Toutes les occurrences "PortfolioConstructionAgent"
    print("")
    print("=" * 78)
    print("Occurrences PortfolioConstructionAgent :")
    print("=" * 78)
    for blk in grep(
        txt,
        re.compile(r"PortfolioConstructionAgent"),
        context=3,
        limit=15,
    ):
        print(blk)

    # 5. INSERT INTO
    print("")
    print("=" * 78)
    print("INSERT INTO :")
    print("=" * 78)
    for blk in grep(
        txt,
        re.compile(
            r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+\w+", re.IGNORECASE
        ),
        context=4,
        limit=10,
    ):
        print(blk)

    # 6. target_weight
    print("")
    print("=" * 78)
    print("target_weight :")
    print("=" * 78)
    for blk in grep(
        txt,
        re.compile(r"target_weight(_pct)?\b"),
        context=4,
        limit=10,
    ):
        print(blk)

    # 7. conviction (formule sizing)
    print("")
    print("=" * 78)
    print("conviction (top 10) :")
    print("=" * 78)
    for blk in grep(
        txt,
        re.compile(r"\bconviction\b", re.IGNORECASE),
        context=2,
        limit=10,
    ):
        print(blk)

    # 8. agent_type='PortfolioConstructionAgent' (signature INSERT theses)
    print("")
    print("=" * 78)
    print("agent_type assignments :")
    print("=" * 78)
    for blk in grep(
        txt,
        re.compile(r"agent_type"),
        context=4,
        limit=10,
    ):
        print(blk)

    print("")
    print("=" * 78)
    print("DONE")
    print("=" * 78)


if __name__ == "__main__":
    main()
