"""STEP 9-3: stage-by-stage memory / time profile of the real runtime (read-only, no API call).

Stages (public functions only, same order as the app): imports -> resources.load_resources (hash check,
screening, BM25, bge-m3) -> ingredient engine (ingredient_dur_ui_adapter.load_engine) -> requests through
adapters.run_safety_check_view (OPENAI_API_KEY must be unset: call_llm returns LLM_UNAVAILABLE without network)
-> N concurrent requests in threads.

Usage: python -X utf8 resource_profile.py <project_root> <out_json> [--model-only]
Works on Windows (GetProcessMemoryInfo) and Linux (/proc/self/status).
"""
import json
import os
import platform
import sys
import threading
import time
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
MODEL_ONLY = "--model-only" in sys.argv
assert not os.environ.get("OPENAI_API_KEY"), "run with OPENAI_API_KEY unset (no billed calls)"
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "ui_integration")]
# same environment app.py sets before running ui_integration/app_v2.py
os.environ.setdefault("MEDICAL_AI_PROJECT_ROOT", str(ROOT))
os.environ.setdefault("MEDGUARD_ROOT", str(ROOT))
os.environ.setdefault("MEDGUARD_NB15_PATH", str(ROOT / "notebooks" / "15_ingredient_duplicate_candidates_prototype.ipynb"))
GB = 1024 ** 3


def mem():
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PMCEX(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                        ("PrivateUsage", ctypes.c_size_t)]
        c = PMCEX()
        c.cb = ctypes.sizeof(PMCEX)
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return {"rss_gb": round(c.WorkingSetSize / GB, 2), "peak_rss_gb": round(c.PeakWorkingSetSize / GB, 2),
                "private_gb": round(c.PrivateUsage / GB, 2), "peak_private_gb": round(c.PeakPagefileUsage / GB, 2)}
    st = {}
    for ln in open("/proc/self/status"):
        k, _, v = ln.partition(":")
        if k in ("VmRSS", "VmHWM", "RssAnon", "RssFile"):
            st[k] = int(v.split()[0]) * 1024
    return {"rss_gb": round(st["VmRSS"] / GB, 2), "peak_rss_gb": round(st["VmHWM"] / GB, 2),
            "anon_gb": round(st.get("RssAnon", 0) / GB, 2), "file_gb": round(st.get("RssFile", 0) / GB, 2)}


stages = []


def mark(name, t0):
    stages.append({"stage": name, "seconds": round(time.perf_counter() - t0, 1), **mem()})
    print(json.dumps(stages[-1], ensure_ascii=False), flush=True)


t0 = time.perf_counter()
mark("python_start", t0)
if MODEL_ONLY:
    t = time.perf_counter()
    from sentence_transformers import SentenceTransformer
    mark("import_sentence_transformers", t)
    t = time.perf_counter()
    m = SentenceTransformer("BAAI/bge-m3", device="cpu", revision="5617a9f61b028005a4858fdac845db406aefb181")
    mark("load_bge_m3_only", t)
    t = time.perf_counter()
    m.encode(["트리아졸람 플루코나졸 병용 금기"], normalize_embeddings=True)
    mark("encode_1_query", t)
else:
    t = time.perf_counter()
    from dur_safety import resources, generation  # noqa: E402
    from app import adapters, ui_runtime  # noqa: E402
    import ingredient_dur_ui_adapter as IA  # noqa: E402
    mark("imports", t)
    t = time.perf_counter()
    rep = resources.load_resources(ROOT, require_dense=True, verify_hashes=True)
    mark("load_resources(hash+screening+bm25+bge-m3)", t)
    t = time.perf_counter()
    eng = IA.load_engine(ROOT)
    mark("ingredient_engine(second DUR copy + approval items)", t)
    rt = ui_runtime.load_runtime()      # cached: returns immediately

    CASES = [(["198902802", "201907819"], None), (["200303280", "200703229"], None), (["200402711"], 70),
             (["200706536", "200803246", "200402711"], 70), (["200700501"], 70), (["201204544", "201603989"], None)]

    def one(items, age):
        sel = adapters.MedicationSelection()
        for s in items:
            sel.register_search(rt.search(s))
            sel.add(s)
        t1 = time.perf_counter()
        vm = adapters.run_safety_check_view({"age": age, "age_unknown": age is None}, sel, runtime_info=rt.runtime_info)
        t2 = time.perf_counter()
        integ = IA.screen_for_ui(eng, list(sel.items), age)
        return {"core_s": round(t2 - t1, 2), "integ_s": round(time.perf_counter() - t2, 2), "state": vm.state,
                "n_findings": len(vm.findings), "integ": integ.get("status")}

    t = time.perf_counter()
    first = one(*CASES[0])
    mark("first_request", t)
    seq = []
    t = time.perf_counter()
    for c in CASES:
        seq.append(one(*c))
    mark("6_sequential_requests", t)
    conc = {}
    for n in (4, 8):
        res, th = [None] * n, []
        t = time.perf_counter()
        for i in range(n):
            th.append(threading.Thread(target=lambda i=i: res.__setitem__(i, one(*CASES[i % len(CASES)]))))
            th[-1].start()
        for x in th:
            x.join()
        mark(f"{n}_concurrent_requests", t)
        conc[n] = {"wall_s": stages[-1]["seconds"], "per_request_core_s": [r["core_s"] for r in res],
                   "all_completed": all(r["state"] == "COMPLETED" for r in res)}
    extra = {"engine_ready": eng.ready, "engine_error": eng.error_dev, "runtime_ready": rt.ready,
             "first_request": first, "sequential": seq, "concurrent": conc,
             "load_report_seconds": rep.get("load_seconds"), "dense_device": rep["dense_state"]["device"]}

result = {"platform": platform.platform(), "python": platform.python_version(), "cpu_count": os.cpu_count(),
          "torch_threads": __import__("torch").get_num_threads(), "stages": stages}
if not MODEL_ONLY:
    result.update(extra)
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
print("WROTE", OUT)
