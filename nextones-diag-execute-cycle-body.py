# -*- coding: utf-8 -*-
# Affiche le corps complet de execute_cycle (L716 -> ~L770)
# pour verifier ou le hook a ete pose et s'il est au bon endroit.

API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"

with open(API, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()

# Affiche L710 a L770
start, end = 710, 770
for i in range(start - 1, min(end, len(lines))):
    line = lines[i].rstrip("\n")
    # Marqueur visuel des markers
    tag = ""
    if "[HISTORY_SNAPSHOT_V1]" in line:
        tag = "  <-- HOOK"
    elif "[EXECUTE_CYCLE_TRACE_V1]" in line:
        tag = "  <-- TRACE"
    elif line.strip().startswith("return"):
        tag = "  <-- RETURN"
    print(f"L{i+1:4d}  {line}{tag}")
