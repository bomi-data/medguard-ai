import sys, json, time, ctypes, ctypes.wintypes as W, io, contextlib
from pathlib import Path
R = Path(sys.argv[1])
for p in (R, R/"src", R/"ui_integration"): sys.path.insert(0, str(p))
class PMC(ctypes.Structure):
    _fields_=[("cb",W.DWORD),("PageFaultCount",W.DWORD),("PeakWorkingSetSize",ctypes.c_size_t),("WorkingSetSize",ctypes.c_size_t),("a",ctypes.c_size_t),("b",ctypes.c_size_t),("c",ctypes.c_size_t),("d",ctypes.c_size_t),("PagefileUsage",ctypes.c_size_t),("PeakPagefileUsage",ctypes.c_size_t)]
def mem():
    c=PMC(); c.cb=ctypes.sizeof(c); ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return round(c.WorkingSetSize/2**20), round(c.PeakWorkingSetSize/2**20)
import ingredient_dur_ui_adapter as IA
t=time.time()
with contextlib.redirect_stdout(io.StringIO()):
    eng = IA.load_engine(str(R))
out={"load_s":round(time.time()-t,1),"mem_MB(cur,peak)":mem(),"ready":eng.ready,"dur_ok":eng.dur_ok,"ing_ok":eng.ing_ok,"error_dev":(eng.error_dev or "")[:300],
     "screening_py_sha256":eng.info.get("screening_py_sha256"),"n_products":eng.info.get("n_products")}
cases={"acetaminophen_3":["202200525","202200407","202106092"],"Q2_contra_pair":["195700013","196900031"],"Q3_thera_pair":["197000068","197700114"],"single":["197000079"],"unknown":["999999999","195700013"]}
res={}
for k,seqs in cases.items():
    u = IA.screen_for_ui(eng, seqs, 72)
    r = u["result"] or {}
    s=json.dumps(r,ensure_ascii=False)
    cands=[c for c in (r.get("ingredient_screening",{}) or {}).get("candidates",[]) ] if isinstance(r.get("ingredient_screening"),dict) else None
    res[k]={"status":u["status"],"tech_errors":[e["type"] for e in u["technical_errors"]],"schema_errors":u["schema_errors"][:3],"top_keys":list(r)[:12],
            "overall": r.get("overall_status") or r.get("overall"),
            "has_UNVERIFIED_CANDIDATE": "UNVERIFIED_CANDIDATE" in s, "mentions_safe_kor": ("안전합니다" in s)}
    res[k]["raw"]=r
out["cases"]={k:{kk:vv for kk,vv in v.items() if kk!="raw"} for k,v in res.items()}
# DUR part consistency vs direct engine
from dur_safety import config, screening as S
with contextlib.redirect_stdout(io.StringIO()): S.init_screening(config.project_paths(str(R)))
d = S.screen_patient(cases["Q2_contra_pair"], age=72)["summary"]
out["direct_screen_Q2_summary"]=d
out["mem_MB_end(cur,peak)"]=mem()
Path(sys.argv[2]).write_text(json.dumps({**out,"raw":{k:v["raw"] for k,v in res.items()}},ensure_ascii=False,indent=1,default=str),encoding="utf-8")
print(json.dumps(out,ensure_ascii=True,indent=1,default=str)[:4000])
