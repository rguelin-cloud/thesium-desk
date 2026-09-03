"""
[DIAG_PORTFOLIO_CONSTRUCTION_AGENT_V2]
v2 - corrige v1 :
  - Exclut les fichiers de diag/install (nextones-* + diag_* + _backups*)
  - Cible directement portfolio_construction_agent.py et variantes
  - Etend la detection au-dela de "class X" : aussi les usages reels
"""

import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

EXCLUDE_DIRS = {
    ".git", "__pycache__", "node_modules", "venv", "env",
    ".venv", "dist", "build", ".pytest_cache",
}

# Exclut les fichiers de diag/scripts utilitaires + backups
EXCLUDE_FILE_PREFIXES = (
    "nextones-", "diag_", "_diag", "_show", "_promote", "_verify",
    "diag-",
)
EXCLUDE_DIR_FRAGMENTS = ("_backups", "_backup")

CLASS_PATTERN = re.compile(r"^\s*class\s+PortfolioConstructionAgent\b")
TARGET_INSERT = re.compile(
    r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+(portfolio_targets\w*|theses)\b",
    re.IGNORECASE,
)
TARGET_WEIGHT = re.compile(r"target_weight(_pct)?\b")
CALLER_PATTERN = re.compile(
    r"PortfolioConstructionAgent\s*\(|"
    r"from\s+portfolio_construction_agent\b|"
    r"import\s+portfolio_construction_agent\b"
)


def should_skip(path):
    rel = os.path.relpath(path, ROOT)
    parts = rel.split(os.sep)
    for p in parts[:-1]:
        for frag in EXCLUDE_DIR_FRAGMENTS:
            if frag in p:
                return True
    fn = parts[-1].lower()
    for pref in EXCLUDE_FILE_PREFIXES:
        if fn.startswith(pref):
            return True
    return False


def iter_py_files(root, allow_diag_scripts=False):
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d not in EXCLUDE_DIRS
                 and not d.startswith(".")]
        for fn in fns:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dp, fn)
            if not allow_diag_scripts and should_skip(full):
                continue
            yield full


def read_text(path):
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return None


def find_class_files(root):
    defs = []
    refs = []
    for path in iter_py_files(root):
        txt = read_text(path)
        if not txt:
            continue
        # Detecte la classe via regex en MULTILINE
        has_class = bool(
            re.search(
                r"^\s*class\s+PortfolioConstructionAgent\b",
                txt,
                re.MULTILINE,
            )
        )
        if has_class:
            defs.append(path)
        elif "PortfolioConstructionAgent" in txt:
            refs.append(path)
    return defs, refs


def locate_class_block(text):
    lines = text.splitlines()
    start = None
    class_indent = None
    for i, ln in enumerate(lines, 1):
        if CLASS_PATTERN.match(ln):
            start = i
            class_indent = len(ln) - len(ln.lstrip())
            break
    if start is None:
        return None
    for j in range(start, len(lines)):
        ln = lines[j]
        if j + 1 == start:
            continue
        stripped = ln.strip()
        if not stripped:
            continue
        cur_indent = len(ln) - len(ln.lstrip())
        if cur_indent <= class_indent and (
            stripped.startswith("class ")
            or stripped.startswith("def ")
            or stripped.startswith("@")
        ):
            return (start, j)
    return (start, len(lines))


def list_methods(text, start, end):
    methods = []
    lines = text.splitlines()
    for i in range(start, end):
        ln = lines[i]
        m = re.match(r"^(\s+)def\s+(\w+)\s*\(", ln)
        if m:
            methods.append((i + 1, m.group(2), m.group(1)))
    return methods


def grep_lines(text, pattern, context=3):
    out = []
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if pattern.search(ln):
            lo = max(0, i - context)
            hi = min(len(lines), i + context + 1)
            block = []
            for k in range(lo, hi):
                marker = ">>>" if k == i else "   "
                block.append("    %s L%-5d %s" % (marker, k + 1, lines[k]))
            out.append((i + 1, "\n".join(block)))
    return out


def dump_method(text, method_line, method_indent):
    """Dump le corps complet d'une methode."""
    lines = text.splitlines()
    start = method_line  # 1-based
    body_indent = len(method_indent) + 4  # heuristique: indent + 4
    end = len(lines)
    for j in range(start, len(lines)):
        ln = lines[j]
        stripped = ln.strip()
        if not stripped:
            continue
        cur_indent = len(ln) - len(ln.lstrip())
        if cur_indent <= len(method_indent) and j + 1 > start:
            end = j
            break
    return start, end, "\n".join(
        "    L%-5d %s" % (k + 1, lines[k]) for k in range(start - 1, end)
    )


def main():
    if not os.path.isdir(ROOT):
        print("ERROR: ROOT not found")
        return

    print("=" * 78)
    print("ROOT : %s (exclu : nextones-* / _backups* / diag-*)" % ROOT)
    print("=" * 78)

    defs, refs = find_class_files(ROOT)
    print("")
    print("Files DEFINING class PortfolioConstructionAgent : %d" % len(defs))
    for p in defs:
        print("  DEF  %s" % p)
    print("")
    print("Files REFERENCING (sans definir) : %d" % len(refs))
    for p in refs:
        print("  REF  %s" % p)

    if not defs:
        print("ERROR: aucun fichier ne definit la classe")
        return

    # Selectionne le fichier production (le plus court chemin sans suffix)
    primary = None
    for p in defs:
        fn = os.path.basename(p).lower()
        if fn == "portfolio_construction_agent.py":
            primary = p
            break
    if not primary:
        primary = defs[0]

    print("")
    print("=" * 78)
    print("PRIMARY FILE : %s" % primary)
    print("=" * 78)

    txt = read_text(primary)
    if not txt:
        print("ERROR: read failed")
        return

    total_lines = len(txt.splitlines())
    print("Total lines : %d" % total_lines)

    block = locate_class_block(txt)
    if not block:
        print("ERROR: bloc class introuvable")
        return
    cls_start, cls_end = block
    print("Class block : L%d - L%d (%d lignes)"
          % (cls_start, cls_end, cls_end - cls_start))

    methods = list_methods(txt, cls_start, cls_end)
    print("")
    print("Methods (%d) :" % len(methods))
    for line_no, name, indent in methods:
        print("  L%-5d %sdef %s()" % (line_no, " " * len(indent), name))

    # INSERT INTO theses / portfolio_targets dans tout le fichier
    print("")
    print("-" * 78)
    print("INSERT INTO portfolio_targets / theses (file-wide) :")
    print("-" * 78)
    hits = grep_lines(txt, TARGET_INSERT, context=4)
    if not hits:
        print("  (aucun)")
    else:
        for line_no, blk in hits[:12]:
            print("--- L%d ---" % line_no)
            print(blk)

    # target_weight dans tout le fichier
    print("")
    print("-" * 78)
    print("target_weight references (file-wide) :")
    print("-" * 78)
    hits2 = grep_lines(txt, TARGET_WEIGHT, context=4)
    if not hits2:
        print("  (aucun)")
    else:
        for line_no, blk in hits2[:15]:
            print("--- L%d ---" % line_no)
            print(blk)

    # Dump bref des methodes principales (run, build, construct, propose)
    print("")
    print("-" * 78)
    print("Method bodies (run / build / construct / propose / generate) :")
    print("-" * 78)
    for line_no, name, indent in methods:
        if name.lower() in (
            "run", "execute", "build", "construct", "propose",
            "generate", "compute", "calculate"
        ):
            s, e, body = dump_method(txt, line_no, indent)
            print("")
            print("=== def %s() : L%d - L%d ===" % (name, s, e))
            # Limite a 80 lignes pour eviter inondation
            lines = body.split("\n")
            if len(lines) > 80:
                print("\n".join(lines[:80]))
                print("    ... (tronque, %d lignes total)" % len(lines))
            else:
                print(body)

    # Callers
    print("")
    print("=" * 78)
    print("CALLERS")
    print("=" * 78)
    for path in iter_py_files(ROOT):
        if path == primary:
            continue
        txt2 = read_text(path)
        if not txt2:
            continue
        hits = grep_lines(txt2, CALLER_PATTERN, context=2)
        if hits:
            print("")
            print("FILE : %s" % path)
            for line_no, blk in hits[:5]:
                print("--- L%d ---" % line_no)
                print(blk)

    print("")
    print("=" * 78)
    print("DONE")
    print("=" * 78)


if __name__ == "__main__":
    main()
