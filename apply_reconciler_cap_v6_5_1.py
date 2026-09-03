# -*- coding: utf-8 -*-
"""
Patch Reconciler v6.5.1 : Cap BUY au delta target.
Empeche les overshoots quand plusieurs agents proposent BUY sur le meme ticker
au-dela du gap reel position-vs-target.

Insere un bloc de cap entre la ligne 581 (delta_target_pct = ...) et la ligne 583
(FILTRE 1 bruit). Rescale qty_net et total_pct pour ne jamais depasser
|delta_target_pct| * CAP_FACTOR.
"""
import re
import shutil
from pathlib import Path
from datetime import datetime

TARGET_FILES = ['execution_engine.py', 'execution_engine_v6_5.py']
CAP_FACTOR = 1.10   # tolerance +10% au-dela du delta cible (cohesion avec ceiling regime)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_dir = Path(f'_backups_reconciler_cap_{timestamp}')
backup_dir.mkdir(exist_ok=True)

# Bloc a inserer (apres calcul delta_target_pct)
PATCH_BLOCK = '''
        # --- CAP v6.5.1 : ne jamais depasser le delta target (anti-overshoot) ---
        # Empeche les agents aggreges (ex: ExitAgent + AltDataAgent) de surdimensionner
        # un BUY/SELL au-dela du gap reel position-vs-target.
        # Applique seulement si le ticker a une target connue ET un gap significatif.
        if ticker in self.target_weights and abs(delta_target_pct) > self.DRIFT_TOLERANCE_PCT:
            max_allowed_pct = abs(delta_target_pct) * 1.10  # tolerance +10%
            if abs(delta_signal_pct) > max_allowed_pct and price > 0:
                old_qty = qty_net
                old_pct = total_pct
                # Rescale au cap
                capped_value = max_allowed_pct / 100 * self.nav
                qty_net = max(1, int(capped_value / price))
                total_pct = max_allowed_pct
                signal_value = qty_net * price
                delta_signal_pct = (signal_value / self.nav * 100) * (1 if side == "buy" else -1)
                self._log(cycle_id, ticker, "CAPPED",
                          f"Reduit qty={old_qty}->{qty_net} (signal {old_pct:.2f}%->"
                          f"{total_pct:.2f}% NAV, cap=delta_target x 1.10)",
                          len(group), qty_net, side.upper(), conv_max,
                          delta_signal_pct, delta_target_pct)
'''

# Marqueur d'insertion : on cherche la ligne avec "delta_target_pct = target_weight_pct - current_weight_pct"
MARKER = 'delta_target_pct = target_weight_pct - current_weight_pct'

for fname in TARGET_FILES:
    fpath = Path(fname)
    if not fpath.exists():
        print(f'[patch] {fname} not found, skip')
        continue

    # Backup
    shutil.copy(fpath, backup_dir / fname)
    content = fpath.read_text(encoding='utf-8')

    # Check si deja patche
    if 'CAP v6.5.1' in content:
        print(f'[patch] {fname} deja patche (CAP v6.5.1 present), skip')
        continue

    if MARKER not in content:
        print(f'[patch] {fname} : marqueur introuvable, ABORT')
        continue

    # Inserer le bloc juste apres la ligne marqueur
    new_content = content.replace(
        MARKER,
        MARKER + PATCH_BLOCK,
        1  # une seule occurrence
    )

    fpath.write_text(new_content, encoding='utf-8')
    print(f'[patch] {fname} : CAP v6.5.1 insere')

# Compile check
print()
import py_compile
for fname in TARGET_FILES:
    if Path(fname).exists():
        try:
            py_compile.compile(fname, doraise=True)
            print(f'[compile] {fname} OK')
        except Exception as e:
            print(f'[compile] {fname} ERROR: {e}')

print()
print('============================================================')
print(' PATCH v6.5.1 applique. Pour activer :')
print('   1. Arreter le serveur (Ctrl+C dans la fenetre uvicorn)')
print('   2. Relancer : py -3.13 -m uvicorn api_server_with_static:app --host 127.0.0.1 --port 8000')
print('   3. Cliquer Run Decision Cycle dans l UI')
print('   4. Verifier : aucun ordre META BUY > 16 actions')
print('============================================================')
