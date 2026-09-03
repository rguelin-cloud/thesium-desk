# -*- coding: utf-8 -*-
"""
[RISK_CONTROLS_UI_V1] Carte 'Controles pre-trade' dans index.html.
- Inseree juste AVANT </section> de tab-today (L914 environ)
- Style cohere avec pplx-geo-section (dark mode, badges)
- Charge donnees via /api/risk/controls/summary + /api/risk/pretrade/recent
- Marker [RISK_CONTROLS_UI_V1] idempotent, backup auto.
- ASCII-only PYTHON, mais le HTML/CSS/JS injecte contient des accents
  car HTML autorise UTF-8. On ecrit le fichier final en utf-8 sans BOM.
"""
import os, shutil, datetime, re, sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "index.html")
MARKER = "[RISK_CONTROLS_UI_V1]"
TAB_TODAY_START_PATTERN = r'<section\s+class="tab-content active"\s+id="tab-today"'

if not os.path.exists(TARGET):
    print(f"ERREUR: {TARGET} introuvable")
    sys.exit(1)

ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
bkdir = os.path.join(ROOT, f"_backups_risk_controls_ui_{ts}")
os.makedirs(bkdir, exist_ok=True)
shutil.copy2(TARGET, os.path.join(bkdir, "index.html"))
print(f"Backup -> {bkdir}")

with open(TARGET, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

n_section_open  = len(re.findall(r'<section[\s>]', src))
n_section_close = src.count("</section>")
n_marker_before = src.count(MARKER)

if MARKER in src:
    print(f"DEJA INSTALLE ({n_marker_before} marker(s)). Skip.")
    sys.exit(0)

# Trouver fin de tab-today : 1ere </section> apres ouverture de tab-today
m_open = re.search(TAB_TODAY_START_PATTERN, src)
if not m_open:
    print("ERREUR: ouverture tab-today introuvable")
    sys.exit(1)
open_pos = m_open.end()
# Cherche le </section> qui ferme. Il faut compter les <section ...> imbriques.
i = open_pos
depth = 1
close_pos = None
while i < len(src):
    nxt_open  = src.find("<section", i)
    nxt_close = src.find("</section>", i)
    if nxt_close == -1:
        break
    if nxt_open != -1 and nxt_open < nxt_close:
        depth += 1
        i = nxt_open + len("<section")
    else:
        depth -= 1
        if depth == 0:
            close_pos = nxt_close
            break
        i = nxt_close + len("</section>")

if close_pos is None:
    print("ERREUR: fermeture </section> de tab-today introuvable")
    sys.exit(1)

# Bloc HTML+CSS+JS a injecter
BLOCK = '''
<!-- === [RISK_CONTROLS_UI_V1] BEGIN === -->
<style>
.risk-controls-section{
  margin:var(--space-4) 0;
  padding:var(--space-3);
  border:1px solid var(--border, #2a2a2a);
  border-radius:8px;
  background:var(--bg-elev, #141414);
}
.risk-controls-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:var(--space-3);gap:var(--space-2)}
.risk-controls-header h3{margin:0;font-size:1.05rem}
.risk-controls-meta{display:flex;gap:var(--space-2);align-items:center;font-size:.85rem;color:var(--text-muted, #888)}
.risk-controls-grid{display:grid;grid-template-columns:1fr 1fr;gap:var(--space-3)}
@media (max-width: 900px){.risk-controls-grid{grid-template-columns:1fr}}
.risk-col-title{margin:0 0 var(--space-2) 0;font-size:.95rem;color:var(--text, #ddd)}
.risk-control-item{display:flex;align-items:flex-start;gap:var(--space-2);padding:var(--space-2) 0;border-bottom:1px solid var(--border-soft, #1f1f1f)}
.risk-control-item:last-child{border-bottom:none}
.risk-control-badge{flex:0 0 auto;padding:2px 8px;border-radius:4px;font-size:.7rem;font-weight:600;letter-spacing:.04em}
.risk-badge-BLOCK{background:#3a0d0d;color:#ff8a8a;border:1px solid #5a1a1a}
.risk-badge-WARNING{background:#3a2a0d;color:#ffc987;border:1px solid #5a3f1a}
.risk-control-body{flex:1;min-width:0}
.risk-control-label{font-weight:500;color:var(--text, #ddd)}
.risk-control-param{font-size:.8rem;color:var(--text-muted, #888);margin-top:2px}
.risk-control-source{font-size:.7rem;color:var(--text-muted, #666);font-family:var(--font-mono, monospace)}
.risk-log-item{display:grid;grid-template-columns:80px 60px 50px 70px 1fr;gap:var(--space-2);padding:var(--space-2) 0;border-bottom:1px solid var(--border-soft, #1f1f1f);font-size:.85rem;align-items:center}
.risk-log-item:last-child{border-bottom:none}
.risk-log-ts{font-family:var(--font-mono, monospace);color:var(--text-muted, #888);font-size:.75rem}
.risk-log-symbol{font-weight:600}
.risk-log-side{font-size:.75rem;color:var(--text-muted, #aaa)}
.risk-log-status{font-size:.7rem;font-weight:600;padding:2px 6px;border-radius:3px;text-align:center;letter-spacing:.04em}
.risk-status-PASS{background:#0d3a18;color:#7fdca0;border:1px solid #1a5a30}
.risk-status-BLOCK{background:#3a0d0d;color:#ff8a8a;border:1px solid #5a1a1a}
.risk-log-detail{color:var(--text-muted, #888);font-size:.75rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.risk-empty{color:var(--text-muted, #666);font-style:normal;font-size:.85rem;padding:var(--space-2) 0}
</style>

<div id="riskControlsSection" class="risk-controls-section" data-marker="[RISK_CONTROLS_UI_V1]">
  <div class="risk-controls-header">
    <h3>Controles pre-trade</h3>
    <div class="risk-controls-meta">
      <span id="riskControlsCount">— controles</span>
      <span>·</span>
      <span id="riskControlsMode">mode hybride</span>
      <button class="btn btn-ghost" onclick="loadRiskControlsData(true)" style="padding:2px 8px;font-size:.8rem">Rafraichir</button>
    </div>
  </div>
  <div class="risk-controls-grid">
    <div>
      <h4 class="risk-col-title">Doctrine active</h4>
      <div id="riskControlsList"><div class="risk-empty">Chargement…</div></div>
    </div>
    <div>
      <h4 class="risk-col-title">10 dernieres verifications</h4>
      <div id="riskPretradeLog"><div class="risk-empty">Chargement…</div></div>
    </div>
  </div>
</div>

<script>
(function(){
  let _riskLoaded = false;
  function escapeHtml(s){return String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
  function fmtTs(s){
    if(!s) return "";
    try{
      const d = new Date(s.replace(" ","T"));
      if(isNaN(d.getTime())) return s.substring(0,16);
      const pad = n => String(n).padStart(2,"0");
      return `${pad(d.getMonth()+1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }catch(e){return String(s).substring(0,16);}
  }
  window.loadRiskControlsData = async function(force){
    try{
      const [sumR, logR] = await Promise.all([
        fetch("/api/risk/controls/summary", {cache: force ? "no-store" : "default"}),
        fetch("/api/risk/pretrade/recent?limit=10", {cache: force ? "no-store" : "default"})
      ]);
      if(sumR.ok){
        const sum = await sumR.json();
        const list = document.getElementById("riskControlsList");
        const cnt = document.getElementById("riskControlsCount");
        const mode = document.getElementById("riskControlsMode");
        if(cnt) cnt.textContent = `${sum.total} controles`;
        if(mode) mode.textContent = `mode ${sum.mode||"hybride"}`;
        if(list){
          list.innerHTML = (sum.controls||[]).map(c => `
            <div class="risk-control-item">
              <span class="risk-control-badge risk-badge-${c.type}">${escapeHtml(c.type)}</span>
              <div class="risk-control-body">
                <div class="risk-control-label">${escapeHtml(c.label)}</div>
                <div class="risk-control-param">${escapeHtml(c.param)}</div>
                <div class="risk-control-source">${escapeHtml(c.source)} ${escapeHtml(c.marker||"")}</div>
              </div>
            </div>`).join("") || '<div class="risk-empty">Aucun controle declare.</div>';
        }
      }
      if(logR.ok){
        const log = await logR.json();
        const el = document.getElementById("riskPretradeLog");
        if(el){
          const items = log.items || [];
          if(items.length === 0){
            el.innerHTML = '<div class="risk-empty">Aucune verification enregistree. Lancez un cycle.</div>';
          } else {
            el.innerHTML = items.map(it => {
              const status = it.passed ? "PASS" : "BLOCK";
              const detailParts = [];
              if(it.blocked_by) detailParts.push(`blocked: ${it.blocked_by}`);
              if(it.details && typeof it.details === "object"){
                if(it.details.concentration_pct != null) detailParts.push(`conc ${(it.details.concentration_pct*100).toFixed(1)}%`);
                if(it.details.var_delta_pct != null) detailParts.push(`VaR +${(it.details.var_delta_pct*100).toFixed(2)}%`);
                if(it.details.max_correlation != null) detailParts.push(`corr ${it.details.max_correlation.toFixed(2)}`);
              }
              return `
                <div class="risk-log-item">
                  <span class="risk-log-ts">${escapeHtml(fmtTs(it.ts))}</span>
                  <span class="risk-log-symbol">${escapeHtml(it.symbol)}</span>
                  <span class="risk-log-side">${escapeHtml(it.side)} ${escapeHtml(String(it.qty))}</span>
                  <span class="risk-log-status risk-status-${status}">${status}</span>
                  <span class="risk-log-detail" title="${escapeHtml(detailParts.join(' | '))}">${escapeHtml(detailParts.join(" · "))}</span>
                </div>`;
            }).join("");
          }
        }
      }
      _riskLoaded = true;
    }catch(e){
      console.error("[RISK_CONTROLS_UI_V1] load error", e);
    }
  };
  // Auto-load au chargement initial et a chaque switch sur tab-today
  function tryAutoLoad(){
    const sec = document.getElementById("riskControlsSection");
    if(sec && !_riskLoaded) window.loadRiskControlsData(false);
  }
  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", tryAutoLoad);
  } else {
    tryAutoLoad();
  }
  // Re-load au clic sur l onglet today (au cas ou)
  document.addEventListener("click", function(e){
    const t = e.target.closest("[data-tab='today'], .nav-item");
    if(t && (t.dataset.tab === "today" || /today|aujourd/i.test(t.textContent||""))){
      setTimeout(()=>window.loadRiskControlsData(false), 100);
    }
  });
})();
</script>
<!-- === [RISK_CONTROLS_UI_V1] END === -->
'''

new_src = src[:close_pos] + BLOCK + src[close_pos:]

with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
    f.write(new_src)

# Validation : comptages
with open(TARGET, "r", encoding="utf-8-sig") as f:
    chk = f.read()
n_after_section_open  = len(re.findall(r'<section[\s>]', chk))
n_after_section_close = chk.count("</section>")
n_marker_after = chk.count(MARKER)
print(f"<section ...>  {n_section_open}  -> {n_after_section_open}  (delta {n_after_section_open - n_section_open})")
print(f"</section>     {n_section_close} -> {n_after_section_close} (delta {n_after_section_close - n_section_close})")
print(f"marker         {n_marker_before} -> {n_marker_after}")
assert n_after_section_open == n_section_open, "Delta <section> != 0 (regression)"
assert n_after_section_close == n_section_close, "Delta </section> != 0 (regression)"
assert n_marker_after >= 2, "Markers manquants (BEGIN/END)"
print("OK")
