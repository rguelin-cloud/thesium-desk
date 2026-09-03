"""Dump du bloc final de execute_cycle (L880-L905) pour planifier patch SHADOW_HOOK."""
import os
FPATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
with open(FPATH, "rb") as f:
    data = f.read().decode("utf-8-sig", errors="replace")
lines = data.split("\n")
print(f"Total lines : {len(lines)}")
print("\n=== L880-L915 (bloc final execute_cycle) ===")
for i in range(879, min(915, len(lines))):
    print(f"  L{i+1:4d}: {lines[i]}")
