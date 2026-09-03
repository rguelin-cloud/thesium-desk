# -*- coding: utf-8 -*-
# Diag pour Option 2 :
# 1) Endpoint /api/orders/pending_approval (filtre SQL a changer)
# 2) Endpoint /api/orders/pending-validation (ancien)
# 3) Card UI "Ordres en attente de validation" dans index.html + app.js
import os, sys

API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server_with_static.py"
HTML = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html"
JS = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"

def read_text(path):
    with open(path, "rb") as f:
        return f.read().decode("utf-8-sig", errors="replace")

def main():
    # 1) API endpoints
    print("=== API : pending_approval + pending-validation ===")
    if os.path.exists(API):
        text = read_text(API)
        lines = text.splitlines()
        for i, ln in enumerate(lines):
            if "pending_approval" in ln or "pending-validation" in ln or "pending_validation" in ln:
                print("L%d: %s" % (i+1, ln.strip()[:160]))
        print()
        # Dump body autour de /api/orders/pending_approval
        for i, ln in enumerate(lines):
            if "/api/orders/pending_approval" in ln:
                start = max(0, i-1)
                end = min(len(lines), i+45)
                print("=== Body L%d-L%d (pending_approval) ===" % (start+1, end))
                for j in range(start, end):
                    print("%4d| %s" % (j+1, lines[j]))
                print()
        # Dump body autour de /api/orders/pending-validation
        for i, ln in enumerate(lines):
            if "/api/orders/pending-validation" in ln:
                start = max(0, i-1)
                end = min(len(lines), i+45)
                print("=== Body L%d-L%d (pending-validation) ===" % (start+1, end))
                for j in range(start, end):
                    print("%4d| %s" % (j+1, lines[j]))
                print()

    # 2) HTML : recherche card "Ordres en attente de validation"
    print("=== HTML : 'Ordres en attente' / pending-validation ===")
    if os.path.exists(HTML):
        text = read_text(HTML)
        lines = text.splitlines()
        for i, ln in enumerate(lines):
            low = ln.lower()
            if "ordres en attente" in low or "pending-validation" in low or "pending_validation" in low or "tout valider" in low or "tout rejeter" in low:
                print("L%d: %s" % (i+1, ln.strip()[:180]))

    # 3) JS : recherche fetch pending-validation + renderers
    print()
    print("=== JS : pending-validation / pending_approval / Ordres en attente ===")
    if os.path.exists(JS):
        text = read_text(JS)
        lines = text.splitlines()
        for i, ln in enumerate(lines):
            low = ln.lower()
            if ("pending-validation" in ln or "pending_validation" in ln
                or "pending_approval" in ln
                or "ordres en attente" in low or "tout valider" in low or "tout rejeter" in low):
                print("L%d: %s" % (i+1, ln.strip()[:180]))

if __name__ == "__main__":
    main()
