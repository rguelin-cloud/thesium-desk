"""
Diag : dump complet du bloc smoothing dans jalon2 (L1020-L1095).
Pour preparer le patch [SMOOTHING_FORCED_EXIT_BYPASS_V1].

ASCII pur.
"""
JALON2 = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent_jalon2.py"

with open(JALON2, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()

# Bloc autour de apply_convergence_sizing (L595) - signature + return
print("=== Signature et fin de apply_convergence_sizing (L595-L700) ===")
for i in range(595, min(700, len(lines)) + 1):
    print("  L{}: {}".format(i, lines[i-1].rstrip()))

print("\n\n=== Bloc smoothing dans run_construction_agent (L1010-L1095) ===")
for i in range(1010, min(1095, len(lines)) + 1):
    print("  L{}: {}".format(i, lines[i-1].rstrip()))

# Localiser raw_alloc et scaled_alloc + smoothing
print("\n\n=== Toutes les occurrences de scaled_alloc, raw_alloc, smoothed ===")
for i, l in enumerate(lines, 1):
    if any(k in l for k in ["scaled_alloc", "raw_alloc", "smoothed", "delta_max", "max_delta"]):
        print("  L{}: {}".format(i, l.rstrip()[:140]))

# Localiser conv_log et son schema
print("\n\n=== Occurrences conv_log et multiplier_log ===")
for i, l in enumerate(lines, 1):
    if "conv_log" in l or "multiplier_log" in l:
        print("  L{}: {}".format(i, l.rstrip()[:140]))
