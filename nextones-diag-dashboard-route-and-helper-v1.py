# -*- coding: utf-8 -*-
# [DIAG_DASHBOARD_ROUTE_AND_HELPER_V1]
# Dump api_server.py L404-490 (route /api/dashboard complete)
# pour voir exactement comment portfolio_state est lu et serialise.

from pathlib import Path

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")

api_lines = read_text(BASE / "api_server.py").splitlines()

print("=" * 70)
print("Route /api/dashboard : L404-490")
print("=" * 70)
for i in range(403, min(490, len(api_lines))):
    print("  L" + str(i+1) + ": " + api_lines[i][:170])

print()
print("DONE")
