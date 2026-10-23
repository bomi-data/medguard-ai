"""STEP 8-C/8-D: drive the exact UI adapter path for the 30 existing evaluation inputs (no API call).

Path (same as the Streamlit button): MedicationSelection.register_search(drug_lookup result) -> add(item_seq)
  -> adapters.validate_input -> adapters.execute (pipeline.run_safety_check, live hybrid RAG, real call_llm
  with OPENAI_API_KEY absent => LLM_UNAVAILABLE) -> adapters.build_view_model.
Compared against: screening.screen_patient (Core structured output) and the 06-A stored hybrid Top-5.
Also: one NO_EVIDENCE probe (an elderly-caution DUR item that has no approval-label chunk), timings, memory.

Usage: python -X utf8 ui_path_integration.py <project_root> <out_json>
"""
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "tools")]
assert not os.environ.get("OPENAI_API_KEY"), "run with OPENAI_API_KEY unset (no billed calls)"

import pandas as pd  # noqa: E402


class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


def mem_gb():
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    g = 1024 ** 3
    return {"ws": round(c.WorkingSetSize / g, 2), "peak_ws": round(c.PeakWorkingSetSize / g, 2),
            "commit": round(c.PagefileUsage / g, 2), "peak_commit": round(c.PeakPagefileUsage / g, 2)}


t0 = time.perf_counter()
from dur_safety import resources, screening, findings as F, drug_lookup, generation  # noqa: E402
from app import adapters, ui_policy as P  # noqa: E402
from baselines import Baselines  # noqa: E402
import regression_checks as RC  # noqa: E402
t_import = time.perf_counter() - t0
t0 = time.perf_counter()
resources.load_resources(ROOT, require_dense=True, verify_hashes=True)
t_load = time.perf_counter() - t0
mem_after_load = mem_gb()

bl = Baselines(ROOT)
raw = bl.retrieval_raw
hyb = raw[raw["method"] == "hybrid"].sort_values(["query_id", "rank"])


def ui_selection(items):
    sel = adapters.MedicationSelection()
    for s in items:
        sel.register_search(drug_lookup.search_drugs(s, limit=20))   # what the UI search button does
        sel.add(s)                                                     # what the 추가 button does
    return sel


def run_case(items, age):
    patient = {"age": age, "age_unknown": age is None}
    t = time.perf_counter()
    core = screening.screen_patient(items, age=age, include_evidence=True)
    t_screen = time.perf_counter() - t
    core_f = F.findings_from_screening_result(core)
    t = time.perf_counter()
    rets = [generation.retrieve_evidence(f) for f in core_f]
    t_ret = time.perf_counter() - t
    sel = ui_selection(items)
    t = time.perf_counter()
    inp = adapters.validate_input(patient, sel)
    exe = adapters.execute(inp) if inp.is_valid else None
    vm = adapters.build_view_model(input_result=inp, execution=exe)
    t_total = time.perf_counter() - t
    return core, core_f, rets, inp, exe, vm, {"screen_s": round(t_screen, 3), "retrieval_s": round(t_ret, 3),
                                              "ui_path_total_s": round(t_total, 3)}


rows = []
for q in bl.queries.sort_values("query_id").itertuples():
    items = [str(x) for x in q.target_item_seqs]
    age = RC.AGE_BY_RISK[q.risk_type]
    core, core_f, rets, inp, exe, vm, tm = run_case(items, age)
    s = core["summary"]
    tiles = {t.risk_type: t.count for t in vm.summary.tiles} if vm.summary else {}
    exp_tiles = {"contraindication": s["contraindication_count"],
                 "elderly_caution": None if s["elderly_check_status"] != "evaluated" else s["elderly_caution_count"],
                 "therapeutic_duplication": s["therapeutic_duplication_count"]}
    rep_f = {f["finding_id"]: f for f in exe.report["findings"]} if exe else {}
    fv = {v.finding_id: v for v in vm.findings}
    base_top5 = hyb[hyb["query_id"] == q.query_id]["chunk_id"].tolist()[:5]
    tf = rep_f.get(q.finding_id) or {}
    ui_top5 = [e["chunk_id"] for e in tf.get("evidence") or []]
    ui_ids = [e["evidence_id"] for e in tf.get("evidence") or []]
    v = fv.get(q.finding_id)
    ui_ev = [(e.evidence_id, e.item_seq, e.chunk_text) for e in (v.evidence.items if v and v.evidence else ())]
    rep_ev = [(e["evidence_id"], e["ITEM_SEQ"], e["chunk_text"]) for e in tf.get("evidence") or []]
    row = {
        "case_id": q.query_id, "risk_type": q.risk_type, "items": items, "age": age,
        "vm_state": vm.state,
        "tiles_match_core": tiles == exp_tiles, "tiles": tiles, "core_counts": exp_tiles,
        "total_signals_match": (vm.summary.total_signals if vm.summary else None) == s["total_signals"],
        "finding_ids_match": sorted(fv) == sorted(f.finding_id for f in core_f),
        "risk_types_match": all(fv[f.finding_id].risk_type == f.risk_type for f in core_f if f.finding_id in fv),
        "dur_rule_lines_match": all(list(fv[f.finding_id].dur_rule_lines) == [str(x) for x in f.dur_rule_texts]
                                    or not f.dur_rule_texts for f in core_f if f.finding_id in fv),
        "target_finding_present": q.finding_id in fv,
        "display_mode": v.display_mode if v else None, "status_message": v.status_message if v else None,
        "explanation_shown": bool(v and v.explanation),
        "retrieval_status": (tf.get("retrieval") or {}).get("status"),
        "retrieval_method": (tf.get("retrieval") or {}).get("method"),
        "evidence_ids": ui_ids, "evidence_ids_sequential": ui_ids == [f"E{i}" for i in range(1, len(ui_ids) + 1)],
        "evidence_errors": tf.get("evidence_errors"),
        "top5_equal_06A_hybrid": ui_top5 == base_top5, "ui_top5": ui_top5, "base_top5": base_top5,
        "ui_evidence_verbatim": ui_ev == rep_ev,
        "direct_retrieval_equal": [r.status for r in rets] == [((rep_f.get(f.finding_id) or {}).get("retrieval") or {}).get("status") for f in core_f],
        "timing": tm,
    }
    rows.append(row)
    print(q.query_id, vm.state, "tiles", row["tiles_match_core"], "ids", row["finding_ids_match"],
          "top5", row["top5_equal_06A_hybrid"], row["display_mode"], row["retrieval_status"], row["retrieval_method"], tm,
          flush=True)

# ---- NO_EVIDENCE probe: an elderly-caution DUR item that is searchable but has no approval-label chunk -------
probe = None
try:
    ec = resources.R["elderly_caution_rules"] if hasattr(resources, "R") else None
except Exception:  # noqa: BLE001
    ec = None
corpus = set(pd.read_parquet(ROOT / "data/processed/rag/approval_chunks.parquet", columns=["ITEM_SEQ"])["ITEM_SEQ"].astype(str))
ec_df = pd.read_parquet(ROOT / "data/processed/screening/elderly_caution_rules.parquet")
seq_col = [c for c in ec_df.columns if c.upper() in ("ITEM_SEQ", "ITEMSEQ")][0]
for seq in sorted(set(ec_df[seq_col].astype(str)) - corpus):
    r = drug_lookup.search_drugs(seq, limit=1)
    if not (r.get("candidates") or []):
        continue
    core, core_f, rets, inp, exe, vm, tm = run_case([seq], 70)
    if not core_f:
        continue
    v = vm.findings[0]
    probe = {"item_seq": seq, "item_name": (r["candidates"][0] or {}).get("item_name"), "vm_state": vm.state,
             "core_counts": core["summary"], "finding_ids": [f.finding_id for f in core_f],
             "ui_finding_ids": [x.finding_id for x in vm.findings], "display_mode": v.display_mode,
             "status_message": v.status_message, "retrieval_status": rets[0].status, "retrieval_reason": rets[0].reason,
             "evidence_section": None if v.evidence is None else len(v.evidence.items),
             "explanation_shown": v.explanation is not None, "llm_called": exe.report["summary"]["llm_calls"], "timing": tm}
    break
print("NO_EVIDENCE probe:", json.dumps(probe, ensure_ascii=False, default=str))

# ---- repeated-run stability: same input 3x, identical VM (minus timing metadata) -----------------------------
rep = []
for _ in range(3):
    *_, vm, tm = run_case(["198902802", "201907819"], None)
    d = vm.to_dict()
    d.pop("metadata", None)
    rep.append(json.dumps(d, ensure_ascii=False, sort_keys=True, default=str))
stable = len(set(rep)) == 1

summary = {
    "t_import_s": round(t_import, 1), "t_load_resources_s": round(t_load, 1), "mem_after_load_gb": mem_after_load,
    "mem_end_gb": mem_gb(), "n_cases": len(rows),
    "all_completed": all(r["vm_state"] == "COMPLETED" for r in rows),
    "tiles_match": sum(r["tiles_match_core"] for r in rows), "finding_ids_match": sum(r["finding_ids_match"] for r in rows),
    "risk_types_match": sum(r["risk_types_match"] for r in rows), "dur_rule_lines_match": sum(r["dur_rule_lines_match"] for r in rows),
    "total_signals_match": sum(r["total_signals_match"] for r in rows),
    "top5_equal_06A_hybrid": sum(r["top5_equal_06A_hybrid"] for r in rows),
    "evidence_ids_sequential": sum(r["evidence_ids_sequential"] for r in rows),
    "evidence_errors_zero": sum(not r["evidence_errors"] for r in rows),
    "ui_evidence_verbatim": sum(r["ui_evidence_verbatim"] for r in rows),
    "retrieval_ok_hybrid": sum(r["retrieval_status"] == "OK" and r["retrieval_method"] == "hybrid" for r in rows),
    "display_modes": pd.Series([r["display_mode"] for r in rows]).value_counts().to_dict(),
    "explanation_shown_without_llm": sum(r["explanation_shown"] for r in rows),
    "repeat_3x_identical_vm": stable,
    "timing_median_s": {k: round(float(pd.Series([r["timing"][k] for r in rows]).median()), 3) for k in rows[0]["timing"]},
    "timing_max_s": {k: round(float(pd.Series([r["timing"][k] for r in rows]).max()), 3) for k in rows[0]["timing"]},
}
OUT.write_text(json.dumps({"summary": summary, "no_evidence_probe": probe, "cases": rows}, ensure_ascii=False, indent=1,
                          default=str), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=1))
