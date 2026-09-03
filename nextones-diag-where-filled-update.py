# -*- coding: utf-8 -*-
# Trouve toutes les sources d'UPDATE orders SET status='filled' dans le projet
import os, sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

PATTERNS = [
    "status='filled'",
    'status="filled"',
    "status = 'filled'",
    'status = "filled"',
    "'filled',",
    '"filled",',
]

def scan(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
        text = data.decode("utf-8-sig", errors="replace")
    except Exception:
        return []
    hits = []
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        for p in PATTERNS:
            if p in ln:
                hits.append((i+1, p, ln.strip()[:160]))
                break
    return hits

def main():
    print("=== Scan complet ===")
    for dirpath, dirs, files in os.walk(ROOT):
        # Skip noise
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules", "venv", ".venv")]
        for fn in files:
            if not (fn.endswith(".py") or fn.endswith(".js")):
                continue
            fp = os.path.join(dirpath, fn)
            hits = scan(fp)
            if hits:
                rel = os.path.relpath(fp, ROOT)
                print()
                print("--- %s ---" % rel)
                for lno, p, ln in hits:
                    print("  L%d [%s]: %s" % (lno, p, ln))

if __name__ == "__main__":
    main()
