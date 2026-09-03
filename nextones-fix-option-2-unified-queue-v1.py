# -*- coding: utf-8 -*-
# nextones-fix-option-2-unified-queue-v1.py
# Option 2 : 1 seule card "Pending Approvals" qui affiche pending_validation
# A) api_server_with_static.py L414 : status = 'approved' -> IN ('approved','pending_validation')
# B) app.js renderPendingValidationPanel : early-return apres badge update -> masque ancienne card
# Idempotent via markers.
import os, sys, shutil, time, ast, py_compile

API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server_with_static.py"
JS = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"

MARKER_API = "# [FIX_OPTION_2_UNIFIED_QUEUE_V1]"
MARKER_JS  = "/* [FIX_OPTION_2_UNIFIED_QUEUE_V1] */"

A_OLD = "            WHERE o.status = 'approved'"
A_NEW = "            WHERE o.status IN ('approved', 'pending_validation')  -- " + MARKER_API.lstrip("# ")

# JS patch : juste apres "if (!panel) return;" dans renderPendingValidationPanel
# On insere un return; pour skip le render mais garder updateOrdersBadge dans loadPendingValidation
B_OLD = """function renderPendingValidationPanel(orders) {
  const panel = document.getElementById('pendingValidationPanel');
  if (!panel) return;

  if (!orders.length) {"""
B_NEW = """function renderPendingValidationPanel(orders) {
  // """ + MARKER_JS.strip("/* ").strip(" */") + """ : disabled, replaced by Pending Approvals card
  const panel = document.getElementById('pendingValidationPanel');
  if (!panel) return;
  panel.innerHTML = '';
  return;

  // Legacy code below (dead, kept for reference)
  if (!orders.length) {"""

def read_text(p):
    with open(p, "rb") as f:
        return f.read().decode("utf-8-sig")

def write_text(p, text):
    with open(p, "wb") as f:
        f.write(text.encode("utf-8"))

def patch_python(path, old, new, marker):
    text = read_text(path)
    if marker in text:
        print("  SKIP: marker present")
        return False
    n = text.count(old)
    print("  OLD occurrences:", n)
    if n != 1:
        print("  FAIL: expected 1 occurrence"); return None
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = path + ".bak." + ts
    shutil.copy2(path, bak)
    print("  Backup:", bak)
    new_text = text.replace(old, new)
    tmp = path + ".tmp." + ts
    write_text(tmp, new_text)
    try:
        ast.parse(read_text(tmp))
        py_compile.compile(tmp, doraise=True)
        print("  ast.parse + py_compile OK")
    except Exception as e:
        print("  FAIL validation:", e)
        os.remove(tmp)
        return None
    os.replace(tmp, path)
    print("  WRITE OK")
    return True

def patch_js(path, old, new, marker):
    text = read_text(path)
    if marker in text:
        print("  SKIP: marker present")
        return False
    n = text.count(old)
    print("  OLD occurrences:", n)
    if n != 1:
        print("  FAIL: expected 1 occurrence"); return None
    # Verif ASCII de l'injection
    bad = [(i, b) for i, b in enumerate(new.encode("utf-8")) if b > 127]
    if bad:
        print("  FAIL: non-ASCII in injection:", bad[:5])
        return None
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = path + ".bak." + ts
    shutil.copy2(path, bak)
    print("  Backup:", bak)
    new_text = text.replace(old, new)
    write_text(path, new_text)
    print("  WRITE OK (size %d -> %d)" % (len(text), len(new_text)))
    return True

def main():
    print("=== Patch A : API L414 ===")
    rA = patch_python(API, A_OLD, A_NEW, MARKER_API)
    print()
    print("=== Patch B : JS renderPendingValidationPanel ===")
    rB = patch_js(JS, B_OLD, B_NEW, MARKER_JS)
    print()
    print("=== Verif finale ===")
    api_text = read_text(API)
    js_text = read_text(JS)
    print("  API : MARKER present =", MARKER_API in api_text)
    print("  API : new filter SQL =", "IN ('approved', 'pending_validation')" in api_text)
    print("  JS  : MARKER present =", MARKER_JS in js_text)
    print()
    if rA is None or rB is None:
        print("FAIL: au moins un patch a echoue")
        sys.exit(1)
    print("OK Option 2 deployee")

if __name__ == "__main__":
    main()
