import sqlite3
c = sqlite3.connect('thesium.db')
c.row_factory = sqlite3.Row

# Voir si quantity_pct est stocke quelque part visible
# Peut-etre dans risk_check_result ou dans event_log
print('=== event_log cycle 20260524-204616 META (instr_id=7) ===')
try:
    for r in c.execute("""
        SELECT * FROM event_log
        WHERE created_at LIKE '2026-05-24 20:46%'
        ORDER BY id DESC LIMIT 20
    """):
        d = dict(r)
        # only show lines mentioning META or instr 7
        s = str(d)
        if 'META' in s or 'instrument_id\': 7' in s or '"instrument_id": 7' in s:
            print(d)
except Exception as e:
    print(f'event_log error: {e}')
