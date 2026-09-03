"""
Diag renderPendingApprovals dans app.js :
- Trouve la fonction
- Dump son body (jusqu'a la fin de la fonction)
- Identifie ou inserer la col Justification + bouton Memo IA
"""
import os
import re

F = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"

with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
    src = fh.read()

print("[INFO] app.js size:", len(src))
print()

# Trouve la fonction
patterns = [
    r"function\s+renderPendingApprovals",
    r"renderPendingApprovals\s*=\s*function",
    r"renderPendingApprovals\s*:\s*function",
    r"async\s+function\s+renderPendingApprovals",
    r"const\s+renderPendingApprovals\s*=",
    r"let\s+renderPendingApprovals\s*=",
]

start_line = None
for pat in patterns:
    m = re.search(pat, src)
    if m:
        # Trouve numero de ligne
        start_line = src[:m.start()].count("\n") + 1
        print(f"[FOUND] pattern {pat!r} at line {start_line}")
        break

if start_line is None:
    print("[NOT FOUND] renderPendingApprovals - cherche variantes...")
    # Fallback : cherche toute reference
    for m in re.finditer(r"renderPendingApprovals", src):
        ln = src[:m.start()].count("\n") + 1
        # extrait la ligne complete
        line_start = src.rfind("\n", 0, m.start()) + 1
        line_end = src.find("\n", m.end())
        print(f"  L{ln}: {src[line_start:line_end][:120]}")
    # cherche aussi variantes camelCase
    for needle in ["PendingApproval", "pending_approval", "pendingApprovals"]:
        n = src.count(needle)
        print(f"  count('{needle}') = {n}")
else:
    # Dump 100 lignes autour du start
    lines = src.splitlines()
    print()
    print(f"[DUMP] lignes {start_line} a {start_line + 100} :")
    print("-" * 80)
    for i in range(start_line - 1, min(len(lines), start_line + 100)):
        print(f"L{i+1:5d}: {lines[i][:200]}")

# Cherche aussi les endpoints appeles depuis app.js
print()
print("[FETCH CALLS a /api/orders/pending_approval]")
for m in re.finditer(r"['\"](/api/orders/pending[_-]approval[^'\"]*)['\"]", src):
    ln = src[:m.start()].count("\n") + 1
    print(f"  L{ln}: {m.group(1)}")

# Cherche modals existants pour trouver le pattern reutilisable
print()
print("[MODAL PATTERNS existants]")
for m in re.finditer(r"showModal|openModal|createModal|Modal\(", src):
    ln = src[:m.start()].count("\n") + 1
    if ln > 0:
        # dump la ligne
        line_start = src.rfind("\n", 0, m.start()) + 1
        line_end = src.find("\n", m.end())
        snippet = src[line_start:line_end].strip()[:150]
        print(f"  L{ln}: {snippet}")
