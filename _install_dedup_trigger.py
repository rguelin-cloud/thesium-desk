# -*- coding: utf-8 -*-
"""
Pose un trigger SQLite BEFORE INSERT sur la table orders pour bloquer
les doublons (meme instrument_id + side en pending_validation < 10 min).
"""
import sqlite3
import sys

DRY_RUN = "--apply" not in sys.argv

c = sqlite3.connect('thesium.db')

# Verifier si le trigger existe deja
existing = c.execute("""
    SELECT name FROM sqlite_master
    WHERE type='trigger' AND name='trg_orders_dedup'
""").fetchone()

if existing:
    print('[trigger] trg_orders_dedup existe deja.')
    if DRY_RUN:
        print('[trigger] DRY-RUN : pour le recreer, relancer avec --apply')
        sys.exit(0)
    c.execute('DROP TRIGGER trg_orders_dedup')
    print('[trigger] Ancien trigger supprime.')

trigger_sql = """
CREATE TRIGGER trg_orders_dedup
BEFORE INSERT ON orders
FOR EACH ROW
WHEN NEW.status = 'pending_validation'
 AND EXISTS (
    SELECT 1 FROM orders
    WHERE instrument_id = NEW.instrument_id
      AND side = NEW.side
      AND status = 'pending_validation'
      AND datetime(created_at) > datetime('now', '-10 minutes')
 )
BEGIN
  SELECT RAISE(IGNORE);
END;
"""

if DRY_RUN:
    print('[trigger] DRY-RUN. SQL a installer :')
    print(trigger_sql)
    print('[trigger] Pour appliquer : py -3.13 _install_dedup_trigger.py --apply')
    sys.exit(0)

c.execute(trigger_sql)
c.commit()
print('[trigger] OK : trg_orders_dedup installe.')
print('[trigger] Regle : INSERT ignore si meme (instrument_id, side) deja pending < 10 min.')

# Test rapide
print()
print('[trigger] Verification :')
for r in c.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' AND name='trg_orders_dedup'"):
    print(f'  Trigger {r[0]} present.')
