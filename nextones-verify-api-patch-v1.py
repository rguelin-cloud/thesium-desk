"""
Verifie que le patch 4 est correctement en place :
- Endpoint /api/orders/pending_approval enrichi (SELECT contient o.justification)
- Nouveau endpoint POST /api/orders/{order_id}/memo present
- compile() OK
"""
import os

F = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server_with_static.py"

with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
    src = fh.read()

print("[INFO] file size:", os.path.getsize(F))
print()

# Compile check
try:
    compile(src, F, "exec")
    print("[OK] compile() passes")
except SyntaxError as e:
    print(f"[ERR] SyntaxError: {e}")

# Markers
print()
print("[MARKERS]")
print(f"  '# [JUSTIFICATION_API_V1]' : {src.count('# [JUSTIFICATION_API_V1]')} occurrences")

# Elements attendus
checks = [
    ("o.justification,", "SELECT enrichi contient justification"),
    ("has_memo", "SELECT enrichi contient has_memo"),
    ("POST /api/orders/{order_id}/memo", "route memo commentee"),
    ('@app.post("/api/orders/{order_id}/memo")', "route memo decoree"),
    ("_api_order_memo_v1", "fonction memo definie"),
    ("import pplx_client", "import pplx_client"),
    ("justification_memo", "acces colonne DB"),
]
print()
print("[CONTENT CHECKS]")
for needle, label in checks:
    ok = needle in src
    tag = "OK" if ok else "MISSING"
    print(f"  [{tag}] {label}: {needle[:60]!r}")

# Liste toutes les routes /api/orders/
print()
print("[ROUTES /api/orders/ dans le fichier]")
import re
for m in re.finditer(r'@app\.(get|post|put|delete|patch)\("(/api/orders/[^"]+)"', src):
    print(f"  {m.group(1).upper():6s} {m.group(2)}")
