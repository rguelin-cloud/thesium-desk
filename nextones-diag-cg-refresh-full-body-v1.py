"""
Dump complet refresh_crypto_prices_to_db() L177-L245 pour visualiser tous les {{...}}
avant patch groupe.
"""
F = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_crypto.py"

with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
    lines = fh.read().splitlines()

print(f"[DUMP] data_crypto.py L177-L245")
print("-" * 78)
for i in range(176, min(245, len(lines))):
    marker = " >>> " if "{{" in lines[i] or "}}" in lines[i] else "     "
    print(f"L{i+1:5d}{marker}{lines[i][:200]}")

# Verifie aussi ETF_MAP + fetch_crypto_signals context
print()
print(f"[DUMP] data_crypto.py L45-L145 (ETF_MAP + fetch_crypto_signals)")
print("-" * 78)
for i in range(44, min(145, len(lines))):
    print(f"L{i+1:5d}  {lines[i][:200]}")
