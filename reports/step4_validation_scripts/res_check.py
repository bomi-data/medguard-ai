import sys, json, time, io, contextlib, os
from pathlib import Path
R = Path(sys.argv[1]); sys.path.insert(0, str(R/"src"))
try:
    import psutil; P = psutil.Process()
    mem = lambda: round(P.memory_info().rss/2**20)
except ImportError:
    mem = lambda: None
from dur_safety import resources, retrieval
out = {"HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE"), "utf8_mode": sys.flags.utf8_mode, "mem_start_MB": mem()}
t = time.time()
buf = io.StringIO()
# 1) production default: require_dense=True must fail closed when model is unavailable
try:
    with contextlib.redirect_stdout(buf): resources.load_resources(str(R), require_dense=True)
    out["require_dense_True"] = "LOADED"
except Exception as e:
    out["require_dense_True"] = f"{type(e).__name__}: {str(e)[:220]}"
out["dense_state"] = {k: v for k, v in getattr(retrieval, "DENSE_STATE", {}).items() if k != "revision"}
out["load_s"] = round(time.time() - t, 1); out["mem_after_MB"] = mem()
# 2) BM25-only (research DEGRADED mode, not the evaluated configuration)
try:
    with contextlib.redirect_stdout(buf): rep = resources.load_resources(str(R), require_dense=False, force=True)
    out["require_dense_False"] = "LOADED"
    out["files"] = {k: v["status"] for k, v in rep["files"].items()}
    out["runtime_checks_failed"] = [k for k, v in rep["runtime_checks"].items() if not v]
    out["runtime_checks_n"] = len(rep["runtime_checks"])
    out["corpus_rows"], out["unique_texts"] = rep["corpus_rows"], rep["unique_texts"]
except Exception as e:
    out["require_dense_False"] = f"{type(e).__name__}: {str(e)[:300]}"
out["mem_end_MB"] = mem()
print(json.dumps(out, ensure_ascii=True, indent=1))
