"""STEP 6 RAG runtime probe (read-only; no medical logic, no writes to src/ or data/).

Usage: python -X utf8 rag_probe.py <project_root> <out_json>
Env: HF_HUB_OFFLINE=1, OPENAI_API_KEY unset. Loads resources with require_dense=True (production default).
Measures per-method latency, peak working set, evidence linkage, failure handling, and retrieval quality
against the 06-A human labels (metric code is first checked to reproduce the recorded 06-B values).
"""
import ctypes
import ctypes.wintypes as wt
import json
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "tools")]
os.environ.pop("OPENAI_API_KEY", None)


class PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


_k32 = ctypes.WinDLL("kernel32")
_k32.GetCurrentProcess.restype = wt.HANDLE
_k32.K32GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
_k32.K32GetProcessMemoryInfo.restype = wt.BOOL


def mem_gb():
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    assert _k32.K32GetProcessMemoryInfo(_k32.GetCurrentProcess(), ctypes.byref(c), c.cb), "GetProcessMemoryInfo failed"
    return {"working_set_gb": round(c.WorkingSetSize / 2**30, 3), "peak_working_set_gb": round(c.PeakWorkingSetSize / 2**30, 3),
            "private_gb": round(c.PagefileUsage / 2**30, 3), "peak_private_gb": round(c.PeakPagefileUsage / 2**30, 3)}


report = {"root": str(ROOT), "mem_start": mem_gb()}

# 1. load (dense required)
t = time.perf_counter()
from dur_safety import resources, retrieval, generation, screening, findings  # noqa: E402
loaded = resources.load_resources(ROOT, require_dense=True, verify_hashes=True)
report["load_seconds"] = round(time.perf_counter() - t, 1)
report["mem_after_load"] = mem_gb()
report["dense_state"] = {k: v for k, v in retrieval.DENSE_STATE.items()}
report["dense_available"] = bool(retrieval.dense_available())
report["dense_emb_shape"] = list(retrieval.DENSE_EMB.shape)
report["model_device"] = str(retrieval.dense_model.device)
report["model_dtype"] = str(next(retrieval.dense_model.parameters()).dtype)

# 2. per-method runs on the 04 smoke queries (+ timing)
smoke = json.loads((ROOT / "data/processed/retrieval/smoke_test_queries.json").read_text(encoding="utf-8"))
runs = []
for case in smoke:
    f04 = generation.finding04_from_case(case)
    query, _ = retrieval.build_query(f04)
    cand, info = retrieval.get_candidates(f04["risk_type"], f04["item_seqs"])
    for m, fn in {"bm25": lambda: retrieval.retrieve_bm25(query, cand, 5, f04["risk_type"]),
                  "dense": lambda: retrieval.retrieve_dense(query, cand, 5, f04["risk_type"]),
                  "hybrid": lambda: retrieval.retrieve_hybrid(query, f04["risk_type"], f04["item_seqs"], 5)}.items():
        fn()  # warm-up
        ts = []
        for _ in range(3):
            t = time.perf_counter()
            res, st = fn()
            ts.append(time.perf_counter() - t)
        meta_ok = all(retrieval.CHUNK_META.loc[r.chunk_id, "ITEM_SEQ"] == r.ITEM_SEQ and
                      retrieval.CHUNK_META.loc[r.chunk_id, "document_id"] == r.document_id for r in res.itertuples())
        runs.append({"query_id": case["query_id"], "method": m, "status": st["status"],
                     "retrieval_method": res["retrieval_method"].iloc[0] if len(res) else None,
                     "n_results": len(res), "n_candidate_texts": info["n_candidate_texts"],
                     "chunk_ids": res["chunk_id"].tolist(), "items_in_target": bool(set(res["ITEM_SEQ"]) <= set(f04["item_seqs"])),
                     "provenance_matches_corpus": bool(meta_ok), "warnings": st.get("warnings"),
                     "latency_ms_median": round(sorted(ts)[1] * 1000, 1)})
report["smoke_runs"] = runs
report["mem_after_smoke"] = mem_gb()

# 3. evidence-ID linkage through the production path (screening finding -> retrieve_evidence -> E#)
ev = []
for case in smoke:
    res = screening.screen_patient(case["item_seqs"], age=72, include_evidence=True)
    fs = [f for f in findings.findings_from_screening_result(res) if f.risk_type == case["risk_type"]]
    for f in fs[:1]:
        rr = generation.retrieve_evidence(f)
        gi = generation.prepare_evidence_context(rr, f)
        ev.append({"query_id": case["query_id"], "finding_id": f.finding_id, "retrieval_status": rr.status,
                   "method": rr.method, "evidence_ids": [e.evidence_id for e in gi.evidence],
                   "evidence_chunk_ids": [e.chunk_id for e in gi.evidence],
                   "validation_errors": gi.evidence_errors if hasattr(gi, "evidence_errors") else None,
                   "generation_input_fields": [k for k in vars(gi)]})
report["evidence_linkage"] = ev

# 4. failure handling
fail = {}
f04 = generation.finding04_from_case(smoke[0])
q0, _ = retrieval.build_query(f04)
fail["empty_query_hybrid"] = retrieval.retrieve_hybrid("", f04["risk_type"], f04["item_seqs"], 5)[1]["status"] + "/" + \
    str(retrieval.retrieve_hybrid("", f04["risk_type"], f04["item_seqs"], 5)[1]["reason"])
st = retrieval.retrieve_hybrid(q0, f04["risk_type"], ["999999999"], 5)[1]
fail["unknown_item_seq_hybrid"] = f"{st['status']}/{st['reason']}"
empty_cand = retrieval.get_candidates(f04["risk_type"], ["999999999"])[0]
st = retrieval.retrieve_dense(q0, empty_cand, 5)[1]
fail["no_candidates_dense"] = f"{st['status']}/{st['reason']}"
try:
    retrieval.get_candidates("not_a_risk", f04["item_seqs"])
    fail["invalid_risk_type"] = "NO_ERROR"
except ValueError as e:
    fail["invalid_risk_type"] = f"ValueError: {str(e)[:80]}"
report["failure_handling"] = fail

# 5. quality vs 06-A human labels (30 eval cases, Top-5)
import pandas as pd  # noqa: E402
from baselines import Baselines  # noqa: E402
import regression_checks as RC  # noqa: E402

bl = Baselines(ROOT)
qrels = bl.qrels()
raw = bl.retrieval_raw


def metrics(ranked_by_q):
    rows = []
    for qid, ids in ranked_by_q.items():
        judged = {c: g for (q, c), g in qrels.items() if q == qid and not (isinstance(g, float) and math.isnan(g))}
        if not any(g >= 1 for g in judged.values()):
            continue
        top = ids[:5]
        g = [judged.get(c, 0) or 0 for c in top]
        rel = [x >= 1 for x in g]
        ideal = sorted(judged.values(), reverse=True)[:5]
        dcg = sum(x / math.log2(i + 2) for i, x in enumerate(g))
        idcg = sum(x / math.log2(i + 2) for i, x in enumerate(ideal))
        mrr = next((1 / (i + 1) for i, r in enumerate(rel) if r), 0.0)
        rows.append({"hit@1": float(any(rel[:1])), "hit@3": float(any(rel[:3])), "hit@5": float(any(rel)),
                     "precision@5": sum(rel) / 5, "mrr@5": mrr, "ndcg@5": dcg / idcg if idcg else 0.0})
    df = pd.DataFrame(rows)
    return {**{k: round(float(v), 6) for k, v in df.mean().items()}, "n_queries": len(df)}


recorded = {r["method"]: r for r in json.loads(
    (ROOT / "data/processed/evaluation/retrieval_evaluation_report.json").read_text(encoding="utf-8"))["overall"]}
qual = {}
for m in ["bm25", "dense", "hybrid"]:
    base = {q: g.sort_values("rank")["chunk_id"].tolist() for q, g in raw[raw.method == m].groupby("query_id")}
    qual[m] = {"recomputed_from_06A_raw": metrics(base),
               "recorded_06B": {k: recorded[m][k] for k in ["hit@1", "hit@3", "hit@5", "precision@5", "mrr@5", "ndcg@5", "n_queries"]}}
cur = {"bm25": {}, "dense": {}, "hybrid": {}}
t = time.perf_counter()
for q in bl.queries.itertuples():
    seqs = list(q.target_item_seqs)
    query, _ = retrieval.build_query(generation.finding04_from_case(
        {"risk_type": q.risk_type, "item_seqs": seqs, "effect_name": q.effect_name}))
    cand, _ = retrieval.get_candidates(q.risk_type, seqs)
    cur["bm25"][q.query_id] = retrieval.retrieve_bm25(query, cand, 10, q.risk_type)[0]["chunk_id"].tolist()
    cur["dense"][q.query_id] = retrieval.retrieve_dense(query, cand, 10, q.risk_type)[0]["chunk_id"].tolist()
    cur["hybrid"][q.query_id] = retrieval.retrieve_hybrid(query, q.risk_type, seqs, 10)[0]["chunk_id"].tolist()
report["eval_30_seconds_all_methods"] = round(time.perf_counter() - t, 1)
for m in cur:
    qual[m]["current_cpu_run"] = metrics(cur[m])
    base = {q: g.sort_values("rank")["chunk_id"].tolist() for q, g in raw[raw.method == m].groupby("query_id")}
    qual[m]["top5_exact_vs_06A"] = f"{sum(cur[m][q][:5] == base[q][:5] for q in base)}/{len(base)}"
report["quality"] = qual
report["mem_end"] = mem_gb()

OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: report[k] for k in ["load_seconds", "mem_after_load", "mem_end", "dense_available", "model_device",
                                         "model_dtype", "failure_handling", "eval_30_seconds_all_methods"]}, ensure_ascii=False))
for m, v in qual.items():
    print(m, v["top5_exact_vs_06A"], "recomputed", v["recomputed_from_06A_raw"], "| recorded", v["recorded_06B"],
          "| cpu", v["current_cpu_run"])
for r in runs:
    print(r["query_id"], r["method"], r["status"], r["retrieval_method"], r["n_results"], r["items_in_target"],
          r["provenance_matches_corpus"], r["latency_ms_median"], "ms")
for e in ev:
    print("EVID", e["query_id"], e["retrieval_status"], e["method"], e["evidence_ids"], e["evidence_chunk_ids"])
