"""STEP4 Screening execution check. Read-only. Baseline = 05 smoke generation_results.screening_record (stored by the evaluated pipeline)."""
import json, sys, tempfile, time, io, contextlib, os
from pathlib import Path
R = Path(sys.argv[1]); sys.path.insert(0, str(R / "src"))
import pandas as pd
from dur_safety import config, screening as S
out = {}
def norm(x): return json.loads(json.dumps(x, ensure_ascii=False, default=str))
# 0. LLM/RAG modules must not be loaded by the screening engine
t0 = time.time()
with contextlib.redirect_stdout(io.StringIO()):
    S.init_screening(config.project_paths(str(R)))
out["init_seconds"] = round(time.time() - t0, 1)
out["data_snapshot"] = S.DATA_SNAPSHOT
out["integrity_flags"] = {k: bool(getattr(S, k)) for k in ["PAIRS_NORMALIZATION_OK", "ELDERLY_DEDUP_OK", "THERAPEUTIC_CANONICAL_OK", "CONTRAINDICATION_LOOKUP_OK", "EVIDENCE_LINKAGE_OK"]}
out["modules_loaded_after_init"] = {m: (m in sys.modules) for m in ["openai", "torch", "sentence_transformers", "dur_safety.generation", "dur_safety.retrieval"]}
# 1. baseline comparison (05 smoke records)
g = pd.read_parquet(R / "data/processed/generation/generation_results.parquet")
key = {"contraindication": "contraindications", "elderly_caution": "elderly_cautions", "therapeutic_duplication": "therapeutic_duplicates"}
key["therapeutic_duplication"] = "therapeutic_duplications"
cmp = []
for r in g.itertuples():
    seqs = json.loads(r.target_item_seqs); base = json.loads(r.screening_record)
    rep = S.screen_patient(seqs, age=72)
    recs = norm(rep[key[r.risk_type]])
    match = [x for x in recs if all(x.get(k) == v for k, v in base.items() if k in ("canonical_pair_id", "item_seq", "effect_name"))]
    got = match[0] if match else None
    diff = None if got is None else {k: (base[k], got.get(k)) for k in base if got.get(k) != base[k]}
    cmp.append({"query_id": r.query_id, "risk_type": r.risk_type, "input": seqs, "found": got is not None,
                "fields_compared": len(base), "field_diffs": list(diff) if diff else [], "status": "PASS" if got is not None and not diff else "FAIL",
                "summary": rep["summary"]})
out["baseline_compare"] = cmp
# 2. behaviour checks (execution checks; expectations come from engine contract/SCOPE_NOTE, not new medical answers)
unk = S.screen_patient(["999999999"], age=72)
out["unknown_drug"] = {"not_found_in_dur_tables": unk["patient"]["not_found_in_dur_tables"], "total_signals": unk["summary"]["total_signals"],
                       "scope_note_present": bool(unk.get("scope_note"))}
inv = S.screen_patient(["abc", None, "197000079", "197000079"], age=None)
out["invalid_and_duplicate"] = {"invalid_inputs": inv["patient"]["invalid_inputs"], "duplicate_inputs": inv["patient"]["duplicate_inputs"],
                                "elderly_check_status": inv["summary"]["elderly_check_status"], "elderly_count": inv["summary"]["elderly_caution_count"]}
out["age_40"] = S.screen_patient(["197000079"], age=40)["summary"]["elderly_check_status"]
errs = {}
for bad in ["195700013", -1, 151, True]:
    try:
        S.screen_patient(bad if isinstance(bad, str) else ["197000079"], age=None if isinstance(bad, str) else bad); errs[repr(bad)] = "NO_ERROR"
    except Exception as e: errs[repr(bad)] = type(e).__name__
out["input_errors"] = errs
# reverse order / extra unrelated drug do not change pair detection
a = S.screen_patient(["196900031", "195700013"], age=30)["summary"]["contraindication_count"]
out["pair_order_invariant_count"] = a
# 3. missing data → fail closed (temp root with empty data/processed)
with tempfile.TemporaryDirectory() as td:
    (Path(td) / "data" / "processed" / "screening").mkdir(parents=True)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            S.init_screening(config.ProjectPaths(Path(td)))
        out["missing_data"] = "NO_ERROR (UNSAFE)"
    except FileNotFoundError as e:
        out["missing_data"] = "FileNotFoundError: " + str(e).splitlines()[0][:60]
Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "baseline_compare"}, ensure_ascii=True, indent=1)[:3000])
for c in cmp: print(c["query_id"], c["status"], "fields", c["fields_compared"], "diffs", c["field_diffs"], "summary", c["summary"])
