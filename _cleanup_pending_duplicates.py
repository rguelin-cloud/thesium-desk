# -*- coding: utf-8 -*-
"""
Rejette les orders pending_validation antérieurs au dernier cycle.
Mode DRY_RUN par défaut. Lancer avec --apply pour exécuter réellement.
"""
import sqlite3
import sys
from datetime import datetime

APPLY = "--apply" in sys.argv

c = sqlite3.connect('thesium.db')
c.row_factory = sqlite3.Row

rows = c.execute("""
    SELECT id, created_at FROM orders
    WHERE status = 'pending_validation'
    ORDER BY created_at DESC, id DESC
""").fetchall()

if not rows:
    print('[cleanup] Aucun order pending. Rien a faire.')
    sys.exit(0)

latest_ts = rows[0]['created_at'][:19]
to_keep = [r['id'] for r in rows if r['created_at'][:19] == latest_ts]
to_reject = [r['id'] for r in rows if r['created_at'][:19] != latest_ts]

print(f'[cleanup] Cycle le plus recent : {latest_ts}')
print(f'[cleanup] A GARDER  : {len(to_keep)} orders {to_keep}')
print(f'[cleanup] A REJETER : {len(to_reject)} orders {to_reject}')
print()

if not to_reject:
    print('[cleanup] Aucun doublon a nettoyer.')
    sys.exit(0)

if not APPLY:
    print('[cleanup] DRY-RUN (aucune modification). Pour appliquer :')
    print('         py -3.13 _cleanup_pending_duplicates.py --apply')
    sys.exit(0)

# Application reelle
now = datetime.now().isoformat(timespec='seconds')
reason = f'duplicate_cycle_cleanup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'

placeholders = ",".join("?" * len(to_reject))
c.execute(f"""
    UPDATE orders
    SET status = 'rejected',
        rejection_reason = ?,
        validated_at = ?,
        validated_by = 'system_cleanup'
    WHERE id IN ({placeholders})
""", [reason, now] + to_reject)
c.commit()

print(f'[cleanup] OK : {len(to_reject)} orders rejetes (reason={reason})')
print(f'[cleanup] {len(to_keep)} orders conserves en pending_validation.')
