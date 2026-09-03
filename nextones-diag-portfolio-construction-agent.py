"""
[DIAG_PORTFOLIO_CONSTRUCTION_AGENT_V1]
Localise PortfolioConstructionAgent + sa logique de sizing actuelle
pour preparer le patch d'integration du Convergence Engine.

Output ASCII :
  1. Fichier(s) qui definissent PortfolioConstructionAgent
  2. Methode principale + lignes
  3. Appelants (callers) de la classe ou methode
  4. Sites INSERT theses + portfolio_targets
  5. Formule actuelle de target_weight_pct (bloc autour de l'INSERT)
"""

import os
import re
import sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

EXCLUDE_DIRS = {
    ".git", "__pycache__", "node_modules", "venv", "env",
    ".venv", "dist", "build", ".pytest_cache",
}

CLASS_PATTERN = re.compile(r"class\s+PortfolioConstructionAgent\b")
RUN_METHODS = re.compile(
    r"^\s*def\s+(run|execute|build|construct|propose|generate)\b"
)
TARGET_INSERT = re.compile(
    r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+(portfolio_targets\w*|theses)\b",
    re.IGNORECASE,
)
TARGET_WEIGHT = re.compile(r"target_weight(_pct)?\b")
SIZING_KEYWORDS = re.compile(
    r"(conviction|weighted|average|mean|sum|sizing|multiplier|"
    r"target_weight|portfolio_targets)",
    re.IGNORECASE,
)


def iter_py_files(root):
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d not in EXCLUDE_DIRS
                 and not d.startswith(".")]
        for fn in fns:
            if fn.endswith(".py"):
                yield os.path.join(dp, fn)


def read_text(path):
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return None


def find_class_files(root):
    """Fichiers qui definissent ou referencent PortfolioConstructionAgent."""
    defs = []
    refs = []
    for path in iter_py_files(root):
        txt = read_text(path)
        if not txt:
            continue
        if CLASS_PATTERN.search(txt):
            defs.append(path)
        elif "PortfolioConstructionAgent" in txt:
            refs.append(path)
    return defs, refs


def locate_class_block(text):
    """Retourne (start_line, end_line) du bloc class PortfolioConstructionAgent."""
    lines = text.splitlines()
    start = None
    indent = None
    for i, ln in enumerate(lines, 1):
        if CLASS_PATTERN.search(ln):
            start = i
            indent = len(ln) - len(ln.lstrip())
            break
    if start is None:
        return None
    # Fin = prochaine ligne avec indent <= indent de la class
    for j in range(start, len(lines)):
        ln = lines[j]
        if j + 1 == start:
            continue
        stripped = ln.strip()
        if not stripped:
            continue
        cur_indent = len(ln) - len(ln.lstrip())
        # nouvelle declaration au meme niveau (class/def hors classe)
        if cur_indent <= indent and (
            stripped.startswith("class ")
            or stripped.startswith("def ")
            or stripped.startswith("@")
        ):
            return (start, j)
    return (start, len(lines))


def list_methods(text, start, end):
    """Methodes definies dans le bloc class."""
    methods = []
    lines = text.splitlines()
    for i in range(start, end):
        ln = lines[i]
        m = re.match(r"^(\s+)def\s+(\w+)\s*\(", ln)
        if m:
            methods.append((i + 1, m.group(2)))
    return methods


def grep_lines(text, pattern, context=2):
    out = []
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if pattern.search(ln):
            lo = max(0, i - context)
            hi = min(len(lines), i + context + 1)
            block = []
            for k in range(lo, hi):
                marker = ">>>" if k == i else "   "
                block.append("  %s L%d: %s" % (marker, k + 1, lines[k]))
            out.append((i + 1, "\n".join(block)))
    return out


def main():
    if not os.path.isdir(ROOT):
        print("ERROR: ROOT not found at %s" % ROOT)
        return

    print("=" * 78)
    print("ROOT : %s" % ROOT)
    print("=" * 78)

    defs, refs = find_class_files(ROOT)
    print("")
    print("Files DEFINING PortfolioConstructionAgent : %d" % len(defs))
    for p in defs:
        print("  DEF  %s" % p)
    print("")
    print("Files REFERENCING PortfolioConstructionAgent : %d" % len(refs))
    for p in refs:
        print("  REF  %s" % p)

    if not defs:
        print("")
        print("ERROR: classe non trouvee - tentative grep nom alternatif")
        return

    for def_path in defs:
        txt = read_text(def_path)
        if not txt:
            continue

        print("")
        print("=" * 78)
        print("FILE : %s" % def_path)
        print("=" * 78)

        block = locate_class_block(txt)
        if not block:
            print("  ERROR: bloc class introuvable")
            continue
        start, end = block
        print("  class block : lines %d - %d (%d lignes)"
              % (start, end, end - start))

        methods = list_methods(txt, start, end)
        print("")
        print("  methods (%d) :" % len(methods))
        for line_no, name in methods:
            print("    L%-5d %s()" % (line_no, name))

        # INSERT sites dans tout le fichier
        print("")
        print("  INSERT INTO portfolio_targets/theses :")
        hits = grep_lines(txt, TARGET_INSERT, context=3)
        if not hits:
            print("    (aucun)")
        else:
            for line_no, blk in hits[:10]:
                print("    --- L%d ---" % line_no)
                print(blk)

        # target_weight references dans le bloc class
        print("")
        print("  target_weight references (dans le bloc class) :")
        # On extrait la sous-portion class et on grep
        class_text = "\n".join(txt.splitlines()[start - 1:end])
        hits2 = grep_lines(class_text, TARGET_WEIGHT, context=3)
        if not hits2:
            print("    (aucun)")
        else:
            for offset, blk in hits2[:8]:
                # Reajuste les numeros de ligne
                lines = blk.split("\n")
                fixed = []
                for ln in lines:
                    m = re.match(r"(  ...) L(\d+):(.*)", ln)
                    if m:
                        fixed.append(
                            "%s L%d:%s"
                            % (m.group(1), int(m.group(2)) + start - 1,
                               m.group(3))
                        )
                    else:
                        fixed.append(ln)
                print("    --- L%d (in class) ---" % (offset + start - 1))
                print("\n".join(fixed))

    # Callers : qui instancie PortfolioConstructionAgent ?
    print("")
    print("=" * 78)
    print("CALLERS : instanciation ou appel")
    print("=" * 78)
    call_pat = re.compile(
        r"PortfolioConstructionAgent\s*\(|"
        r"from\s+\w+\s+import\s+.*PortfolioConstructionAgent|"
        r"import\s+.*PortfolioConstructionAgent"
    )
    for path in iter_py_files(ROOT):
        txt = read_text(path)
        if not txt:
            continue
        hits = grep_lines(txt, call_pat, context=1)
        if hits:
            print("")
            print("  FILE : %s" % path)
            for line_no, blk in hits[:5]:
                print("    --- L%d ---" % line_no)
                print(blk)

    print("")
    print("=" * 78)
    print("DONE")
    print("=" * 78)


if __name__ == "__main__":
    main()
