# -*- coding: utf-8 -*-
"""
nextones-test-runscan-cli.py
Appelle directement run_scan(top_n=10, dry_run=True) HORS API
pour capturer l'erreur exacte du patch [TOP_N_PER_CLASS_V1].
"""

import sys, os, traceback, json

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

print("=" * 70)
print("Test direct run_scan(top_n=10, dry_run=True)")
print("=" * 70)

try:
    import universe_expansion_agent as uea
    print(f"  Module charge : {uea.__file__}")
    
    # Verifie que le patch est present dans le module charge
    src = open(uea.__file__, "r", encoding="utf-8-sig").read()
    print(f"  [TOP_N_PER_CLASS_V1] present dans fichier : {'[TOP_N_PER_CLASS_V1]' in src}")
    
    # Verifie via inspect que la fonction utilise le nouveau code
    import inspect
    src_func = inspect.getsource(uea.run_scan)
    print(f"  [TOP_N_PER_CLASS_V1] present dans run_scan() : {'[TOP_N_PER_CLASS_V1]' in src_func}")
    print(f"  'by_class' present dans run_scan() : {'by_class' in src_func}")
    
    print("\n  --- Appel run_scan(top_n=10, dry_run=True) ---")
    res = uea.run_scan(top_n=10, dry_run=True)
    print("  --- Fin appel ---\n")
    
    print("  Resultat brut :")
    print(json.dumps(res, indent=2, ensure_ascii=False))
    
except Exception as e:
    print(f"\n  [EXCEPTION] {type(e).__name__}: {e}")
    print("\n  Traceback complet :")
    traceback.print_exc()
