# -*- coding: utf-8 -*-
# [FIX_UI_PNL_6_CARDS_V3]
# Patch app.js : remplace le template kpiGrid.innerHTML dans renderKPIs (L1070+)
# par le bon template 6 cards : PV | Unrealized P&L | Total Return | Cash | Daily | VaR
#
# V2 avait deja ajoute les variables (unrealizedPnl, totalReturn, ...) au-dessus du template
# mais avait OUBLIE de remplacer le HTML lui-meme. V3 corrige uniquement le HTML.
#
# Idempotent : skip si marker V3 present.

import re
import sys
import time
from pathlib import Path

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
TARGET = BASE / "app.js"
MARKER = "/* [FIX_UI_PNL_6_CARDS_V3] */"

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")

def write_text(p, s):
    with open(p, "wb") as f:
        f.write(s.encode("utf-8"))

def main():
    src = read_text(TARGET)

    if MARKER in src:
        print("SKIP : marker V3 present")
        return 0

    # Cherche le bloc dans renderKPIs : doit etre apres "const kpiGrid = document.getElementById('kpiGrid');"
    # qui suit immediatement les declarations totalReturnPct (marker V2 actif)
    # Cible : "kpiGrid.innerHTML = `\n<...5 cards anciennes...>\n`;"
    # Strategie : trouve la fonction renderKPIs (declaration "function renderKPIs("),
    # puis remplace le seul "kpiGrid.innerHTML = `...`;" qui suit.

    # Localiser renderKPIs
    m_func = re.search(r"function\s+renderKPIs\s*\(", src)
    if not m_func:
        print("ERREUR : renderKPIs introuvable")
        return 1

    func_start = m_func.start()
    # Cherche dans la fonction (apres func_start) le pattern "kpiGrid.innerHTML = `"
    rest = src[func_start:]
    m_inner = re.search(r"kpiGrid\.innerHTML\s*=\s*`", rest)
    if not m_inner:
        print("ERREUR : kpiGrid.innerHTML introuvable dans renderKPIs")
        return 1

    # Trouve le backtick de fermeture (apres "`;")
    tmpl_start_abs = func_start + m_inner.end()  # juste apres le ` ouvrant
    # Cherche "`;" depuis tmpl_start_abs
    # On suppose pas de backtick imbrique dans le template (template literal simple)
    close_idx = src.find("`;", tmpl_start_abs)
    if close_idx == -1:
        print("ERREUR : backtick de fermeture introuvable")
        return 1

    # Bloc complet a remplacer : depuis "kpiGrid.innerHTML = `" jusqu'a "`;"
    block_start = func_start + m_inner.start()
    block_end = close_idx + 2  # inclus "`;"

    old_block = src[block_start:block_end]
    print("Bloc a remplacer : " + str(len(old_block)) + " chars")
    print("  start L=" + str(src[:block_start].count(chr(10)) + 1))
    print("  end   L=" + str(src[:block_end].count(chr(10)) + 1))

    # Nouveau template 6 cards
    new_block = (
        "kpiGrid.innerHTML = `\n"
        "    " + MARKER + "\n"
        "    <div class=\"kpi-card\">\n"
        "      <div class=\"kpi-label\">Portfolio Value</div>\n"
        "      <div class=\"kpi-value mono\">${fmtUSDCompact(pv)}</div>\n"
        "      <div class=\"kpi-delta neutral\">AUM</div>\n"
        "    </div>\n"
        "    <div class=\"kpi-card\">\n"
        "      <div class=\"kpi-label\">Unrealized P&amp;L</div>\n"
        "      <div class=\"kpi-value mono ${colorClass(unrealizedPnl)}\">${fmtUSD(unrealizedPnl)}</div>\n"
        "      <div class=\"kpi-delta ${unrealizedPnlPct > 0 ? 'positive' : unrealizedPnlPct < 0 ? 'negative' : 'neutral'}\">\n"
        "        ${unrealizedPnlPct > 0 ? '\\u25B2' : unrealizedPnlPct < 0 ? '\\u25BC' : ''}\n"
        "        ${fmtPct(unrealizedPnlPct)}\n"
        "      </div>\n"
        "    </div>\n"
        "    <div class=\"kpi-card\">\n"
        "      <div class=\"kpi-label\">Total Return</div>\n"
        "      <div class=\"kpi-value mono ${colorClass(totalReturn)}\">${fmtUSD(totalReturn)}</div>\n"
        "      <div class=\"kpi-delta ${totalReturnPct > 0 ? 'positive' : totalReturnPct < 0 ? 'negative' : 'neutral'}\">\n"
        "        ${totalReturnPct > 0 ? '\\u25B2' : totalReturnPct < 0 ? '\\u25BC' : ''}\n"
        "        ${fmtPct(totalReturnPct)}\n"
        "      </div>\n"
        "    </div>\n"
        "    <div class=\"kpi-card\">\n"
        "      <div class=\"kpi-label\">Cash Available</div>\n"
        "      <div class=\"kpi-value mono\">${fmtUSDCompact(cash)}</div>\n"
        "      <div class=\"kpi-delta neutral\">\n"
        "        ${cash != null && pv != null ? fmtPct((cash / pv) * 100) + ' of NAV' : ''}\n"
        "      </div>\n"
        "    </div>\n"
        "    <div class=\"kpi-card\">\n"
        "      <div class=\"kpi-label\">Daily P&amp;L</div>\n"
        "      <div class=\"kpi-value mono ${colorClass(pnl)}\">${fmtUSD(pnl)}</div>\n"
        "      <div class=\"kpi-delta ${pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : 'neutral'}\">\n"
        "        ${pnl > 0 ? '\\u25B2' : pnl < 0 ? '\\u25BC' : ''}\n"
        "        ${pnl != null && pv != null ? fmtPct((pnl / pv) * 100) : ''}\n"
        "      </div>\n"
        "    </div>\n"
        "    <div class=\"kpi-card\">\n"
        "      <div class=\"kpi-label\">VaR (95%)</div>\n"
        "      <div class=\"kpi-value mono text-negative\">${fmtPct(var95)}</div>\n"
        "      <div class=\"kpi-delta neutral\">${var95 != null && pv != null ? fmtUSDCompact(pv * var95 / 100) + ' at risk' : ''}</div>\n"
        "    </div>\n"
        "  `;"
    )

    src2 = src[:block_start] + new_block + src[block_end:]

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = TARGET.with_suffix(".js.bak." + ts)
    write_text(bak, src)
    print("BACKUP : " + str(bak))

    write_text(TARGET, src2)
    print("OK : app.js patche (6 cards : PV | Unrealized | Total Return | Cash | Daily | VaR)")
    print("  - Ancien template L1085-1121 (5 cards) remplace")
    print("  - Marker V3 ajoute")
    return 0

if __name__ == "__main__":
    sys.exit(main())
