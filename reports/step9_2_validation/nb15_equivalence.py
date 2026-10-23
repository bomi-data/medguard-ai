"""STEP 9-2: run the ingredient engine with a given notebook-15 file and dump comparable results (no API)."""
import json, sys
from pathlib import Path
ROOT = Path(sys.argv[1]).resolve(); NB = sys.argv[2]; OUT = Path(sys.argv[3])
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "ui_integration")]
import ingredient_dur_ui_adapter as IA
eng = IA.load_engine(ROOT, nb15_path=NB)
cases = {"CE001": (["198902802", "201907819"], None), "TD005": (["200706536", "200803246"], None),
         "TD002": (["200808340", "201404016"], None), "EC008": (["200402711"], 70),
         "multi3": (["200706536", "200803246", "200402711"], 70)}
res = {"engine_ready": eng.ready, "cell_sha": getattr(IA, "NB15_CELL_SHA", None), "const": {k: str(v) for k, v in IA.NB15_CONST.items()}}
for k, (items, age) in cases.items():
    r = IA.screen_for_ui(eng, items, age)
    chk = IA.ingredient_check(eng, items, r.get("result") if r.get("status") == "OK" else None)
    strip = lambda d: json.loads(json.dumps(d, ensure_ascii=False, sort_keys=True, default=str))
    rr = strip(r)
    rr.pop("request_id", None); (rr.get("result") or {}).pop("meta", None); (rr.get("result") or {}).pop("request_id", None)
    res[k] = {"status": r.get("status"), "result": rr, "check": strip({x: chk.get(x) for x in ("findings", "pairs", "status", "consistency")})}
OUT.write_text(json.dumps(res, ensure_ascii=False, sort_keys=True, indent=1, default=str), encoding="utf-8")
print(k, "engine_ready", eng.ready, {c: res[c]["status"] for c in cases}, "findings", {c: len(res[c]["check"]["findings"] or []) for c in cases})
