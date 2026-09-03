# -*- coding: utf-8 -*-
"""
Liste les orders pending_validation regroupes par cycle (created_at).
Permet d'identifier les doublons issus de plusieurs Run Decision Cycle successifs.
"""
import sqlite3

c = sqlite3.connect('thesium.db')
c.row_factory = sqlite3.Row

print('=== Orders pending_validation par cycle ===')
rows = c.execute("""
    SELECT id, instrument_id, thesis_id, side, quantity, status, created_at
    FROM orders
    WHERE status = 'pending_validation'
    ORDER BY created_at DESC, id DESC
""").fetchall()

print(f'Total pending: {len(rows)}')
print()

prev_ts = None
cycle_count = 0
for r in rows:
    ts = r['created_at'][:19]
    if ts != prev_ts:
        cycle_count += 1
        print(f'--- Cycle #{cycle_count} ({ts}) ---')
        prev_ts = ts
    oid = r['id']
    tid = r['thesis_id']
    inst = r['instrument_id']
    side = r['side']
    qty = r['quantity']
    print(f'  #{oid:>4} thesis=#{tid:>4} inst={inst:>3} {side:<4} qty={qty}')

print()
print(f'=== Resume : {cycle_count} cycles distincts, {len(rows)} orders pending ===')

# Identifier le cycle le plus recent (a garder)
if rows:
    latest_ts = rows[0]['created_at'][:19]
    latest_ids = [r['id'] for r in rows if r['created_at'][:19] == latest_ts]
    older_ids = [r['id'] for r in rows if r['created_at'][:19] != latest_ts]
    print()
    print(f'>>> Cycle le plus recent : {latest_ts}')
    print(f'>>> A GARDER  : {len(latest_ids)} ordres (ids: {latest_ids})')
    print(f'>>> A REJETER : {len(older_ids)} ordres (doublons anciens cycles)')
