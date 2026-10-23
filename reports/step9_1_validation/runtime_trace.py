"""STEP 9-1: record which project files / third-party packages the real app actually touches (no API call).

Runs app.py through streamlit.testing AppTest (same script, same caches), then one safety check through the
same adapter path the run button uses (drug_search.run_check -> adapters.run_safety_check_view) and the
integrated ingredient engine. An audit hook records every file opened under the project root and the HF cache.

Usage: python -X utf8 runtime_trace.py <project_root> <out_json>
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
assert not os.environ.get("OPENAI_API_KEY"), "run with OPENAI_API_KEY unset"
HF = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")).resolve()
opened = {}


def hook(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        try:
            p = Path(os.fsdecode(args[0])).resolve()
        except Exception:  # noqa: BLE001
            return
        s = str(p)
        if s.startswith(str(ROOT)) or s.startswith(str(HF)):
            opened.setdefault(s, 0)
            opened[s] += 1


sys.addaudithook(hook)
os.chdir(ROOT)
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "ui_integration")]
from streamlit.testing.v1 import AppTest  # noqa: E402

t0 = time.time()
at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=900)
at.run()
t_first = time.time() - t0
exc = [str(e.value)[:300] for e in at.exception]
errors = [e.value for e in at.error]

# one check through the same adapter path the UI button uses (CE001 inputs, age unknown)
from app import adapters, ui_runtime  # noqa: E402
import ingredient_dur_ui_adapter as IA  # noqa: E402
rt = ui_runtime.load_runtime()          # resources are process-cached (already loaded by the AppTest run)
sel = adapters.MedicationSelection()
for s in ("198902802", "201907819"):
    sel.register_search(rt.search(s))
    sel.add(s)
vm = adapters.run_safety_check_view({"age": None, "age_unknown": True}, sel, runtime_info=rt.runtime_info)
eng = IA.load_engine(ROOT)
integ = IA.screen_for_ui(eng, list(sel.items), None)

mods = sorted({m.split(".")[0] for m in sys.modules})
proj_files = sorted(p for p in opened if p.startswith(str(ROOT)) and "__pycache__" not in p and ".venv" not in p)
proj_py = sorted(str(Path(m.__file__).resolve()) for m in list(sys.modules.values())
                 if getattr(m, "__file__", None) and str(Path(m.__file__).resolve()).startswith(str(ROOT))
                 and ".venv" not in str(m.__file__))
hf_files = sorted(p for p in opened if p.startswith(str(HF)))
res = {
    "apptest_first_run_s": round(t_first, 1), "apptest_exceptions": exc, "apptest_error_elements": errors,
    "runtime_ready": rt.ready, "runtime_error": rt.error_dev,
    "vm_state": vm.state, "display_modes": [f.display_mode for f in vm.findings],
    "integration_status": integ.get("status"), "engine_ready": eng.ready,
    "project_py_imported": [str(Path(p).relative_to(ROOT)) for p in proj_py],
    "project_files_opened": [str(Path(p).relative_to(ROOT)) for p in proj_files],
    "hf_cache_files_opened": hf_files,
    "top_level_modules": mods,
}
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k not in ("top_level_modules",)}, ensure_ascii=False, indent=1))
