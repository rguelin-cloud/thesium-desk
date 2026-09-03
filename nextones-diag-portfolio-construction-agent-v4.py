"""
[DIAG_PORTFOLIO_CONSTRUCTION_AGENT_V4]
v4 - fix encoding : force stdout en UTF-8 et echappe les non-ASCII a l'output.
"""

import os
import re
import sys
import io

# Force stdout en UTF-8 (compatible PowerShell qui pipe en cp1252)
try:
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="backslashreplace"
    )
except Exception:
    pass

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
PRIMARY = os.path.join(ROOT, "portfolio_construction_agent.py")


def safe_str(s):
    """Convertit tout en ASCII-safe via backslashreplace."""
    if s is None:
        return ""
    return s.encode("ascii", "backslashreplace").decode("ascii")


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
                block.append(
                    "    %s L%-5d %s" % (marker, k + 1, safe_str(lines[k]))
                )
            out.append("--- L%d ---\n%s" % (i + 1, "\n".join(block)))
            if len(out) >= limit:
                break
    return out


def head_dump(txt, n=150):
    lines = txt.splitlines()
    out = []
    for i, ln in enumerate(lines[:n], 1):
        out.append("    L%-5d %s" % (i, safe_str(ln)))
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

    print("")
    print("HEAD (150 lignes) :")
    print("-" * 78)
    print(head_dump(txt, 150))

    print("")
    print("=" * 78)
    print("CLASSES :")
    print("=" * 78)
    for blk in grep(
        txt, re.compile(r"^\s*class\s+\w+"), context=0, limit=20
    ):
        print(blk)

    print("")
    print("=" * 78)
    print("FUNCTIONS top-level (indent 0) :")
    print("=" * 78)
    for blk in grep(txt, re.compile(r"^def\s+\w+"), context=0, limit=40):
        print(blk)

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

    print("")
    print("=" * 78)
    print("target_weight :")
    print("=" * 78)
    for blk in grep(
        txt,
        re.compile(r"target_weight(_pct)?\b"),
        context=4,
        limit=12,
    ):
        print(blk)

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

    print("")
    print("=" * 78)
    print("agent_type :")
    print("=" * 78)
    for blk in grep(
        txt, re.compile(r"agent_type"), context=4, limit=10
    ):
        print(blk)

    print("")
    print("=" * 78)
    print("DONE")
    print("=" * 78)


if __name__ == "__main__":
    main()
