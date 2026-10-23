"""STEP 8-E: analyse the billed calls recorded by capped_launcher.py (no API call).

For each ledger row: match the prompt sha to the stored 06-D prompt (query_id), re-derive the finding and evidence
with the Core (screening + live hybrid retrieval, no LLM), re-run Core validate_output and ui_policy on the
recorded output text, and dump statements next to the cited evidence text for manual claim review.

Usage: python -X utf8 analyze_real_calls.py <project_root> <ledger.jsonl> <out_json>
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "tools")]

import pandas as pd  # noqa: E402
from dur_safety import resources, generation  # noqa: E402
from app import ui_policy as P  # noqa: E402
from baselines import Baselines  # noqa: E402
import regression_checks as RC  # noqa: E402

DENIAL_SCAN = re.compile(r"해당하지\s*않|탐지되지\s*않|안전합니다|문제\s*없|걱정하지\s*않")   # same scan as STEP 7-FINAL

resources.load_resources(ROOT, require_dense=True, verify_hashes=True)
bl = Baselines(ROOT)
stored = pd.read_parquet(ROOT / "data/processed/evaluation/generation_eval_results.parquet")
sha_col = "user_prompt_sha256"
by_sha = dict(zip(stored[sha_col], stored["query_id"]))
queries = bl.queries.set_index("query_id")

rows = []
for line in Path(sys.argv[2]).read_text(encoding="utf-8").splitlines():
    L = json.loads(line)
    cid = by_sha.get(L["user_prompt_sha256"])
    q = queries.loc[cid]
    f, _, _ = RC.real_finding([str(x) for x in q.target_item_seqs], RC.AGE_BY_RISK[q.risk_type], q.finding_id)
    ret = generation.retrieve_evidence(f)
    gi = generation.prepare_evidence_context(ret, f)
    prompt = generation.build_prompt(gi)
    ev = {e.evidence_id: e.chunk_text for e in gi.evidence}
    obj = json.loads(L["output_text"])
    s_err, c_err, c_warn, cited, flags = generation.validate_output(obj, gi)
    core_status = "GENERATED" if not s_err and not c_err else "INVALID_OUTPUT"
    gen = {"status": core_status, "output": obj, "evidence_status": obj.get("evidence_status"),
           "schema_errors": s_err, "citation_errors": c_err, "directive_flags": flags, "cited_evidence_ids": cited}
    mode, reasons = P.decide_display_mode(gen, list(ev), f.finding_id, f.risk_type)
    texts = [obj.get("summary", ""), obj.get("limitations", ""), obj.get("review_note", "")] + \
            [s.get("statement", "") for s in obj.get("evidence_statements") or []]
    rows.append({
        "n": L["n"], "case_id": cid, "risk_type": f.risk_type, "model": L["model"], "usage": L["usage"],
        "latency_s": L["latency_s"], "stop_reason": L["stop_reason"], "error": L["error"],
        "prompt_sha_equal_06D": prompt["user_prompt_sha256"] == L["user_prompt_sha256"],
        "finding_id_match": obj.get("finding_id") == f.finding_id, "risk_type_match": obj.get("risk_type") == f.risk_type,
        "core_status": core_status, "schema_errors": s_err, "citation_errors": c_err, "directive_flags": flags,
        "cited_ids": sorted(set(cited)), "cited_subset_of_evidence": set(cited) <= set(ev),
        "unsafe_text_reasons": P.unsafe_text_reasons(obj), "denial_scan_hits": sum(bool(DENIAL_SCAN.search(t)) for t in texts),
        "display_mode": mode, "display_reasons": reasons, "evidence_status": obj.get("evidence_status"),
        "n_statements": len(obj.get("evidence_statements") or []),
        "output": obj, "evidence": ev,
    })
    print(f"#{L['n']} {cid} sha_eq={rows[-1]['prompt_sha_equal_06D']} core={core_status} mode={mode} "
          f"ids={rows[-1]['finding_id_match']}/{rows[-1]['risk_type_match']} cited={rows[-1]['cited_ids']} "
          f"unsafe={rows[-1]['unsafe_text_reasons']} denial={rows[-1]['denial_scan_hits']} usage={L['usage']} lat={L['latency_s']}")
Path(sys.argv[3]).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
tot_in = sum(r["usage"].get("input_tokens", 0) for r in rows)
tot_out = sum(r["usage"].get("output_tokens", 0) for r in rows)
print("calls", len(rows), "input_tokens", tot_in, "output_tokens", tot_out)
