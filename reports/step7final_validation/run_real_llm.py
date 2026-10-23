"""STEP 7-FINAL: real gpt-5.4-mini generation for selected STEP 7 eval cases (billed calls, hard-capped).

Usage: python -X utf8 run_real_llm.py <project_root> <out_dir> <phase> <case_id> [<case_id> ...]

Path per case (same Core code the app uses):
  screening.screen_patient -> findings -> generation.retrieve_evidence (live hybrid) ->
  generation.generate_explanation(llm_fn=<capped wrapper around generation.call_llm>) ->
  pipeline._finding_entry -> app.adapters._finding_view (-> ui_policy.decide_display_mode)
generate_explanation is called once per target finding (not run_safety_check) so a multi-finding screen
cannot trigger extra billed calls. No file under src/, app/, data/ is written. The API key is never written.
"""
import dataclasses
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
PHASE = sys.argv[3]
CASES = sys.argv[4:]
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "tools")]

MAX_CALLS = 10                      # approved total for STEP 7-FINAL (all phases)
MAX_INPUT_TOKENS = 60_000           # approved estimate: worst case 56k in / 20k out
MAX_OUTPUT_TOKENS = 20_000
LEDGER = OUT / "call_ledger.jsonl"

import pandas as pd  # noqa: E402
from dur_safety import resources, generation, pipeline  # noqa: E402
from app import ui_policy as P, adapters  # noqa: E402
from baselines import Baselines  # noqa: E402
import regression_checks as RC  # noqa: E402

ledger = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines()] if LEDGER.exists() else []
if len(ledger) + len(CASES) > MAX_CALLS:
    sys.exit(f"ABORT: {len(ledger)} calls already made, {len(CASES)} requested > cap {MAX_CALLS}")
if not generation.get_secret(generation.GENERATION_CONFIG["api_key_name"]):
    sys.exit("ABORT: OPENAI_API_KEY not visible")

resources.load_resources(ROOT, require_dense=True, verify_hashes=True)
bl = Baselines(ROOT)
queries = bl.queries.set_index("query_id")
stored = pd.read_parquet(ROOT / "data/processed/evaluation/generation_eval_results.parquet").set_index("query_id")

# deterministic STEP 7 screening-denial / reassurance scan (same phrases as step7 screening_consistency_scan)
DENIAL_SCAN = re.compile(r"해당하지\s*않|탐지되지\s*않|안전합니다|문제\s*없|걱정하지\s*않")


def capped_llm(case_id):
    def fn(system, user):
        tot_in = sum(r["usage"].get("input_tokens", 0) for r in ledger)
        tot_out = sum(r["usage"].get("output_tokens", 0) for r in ledger)
        if len(ledger) >= MAX_CALLS or tot_in >= MAX_INPUT_TOKENS or tot_out >= MAX_OUTPUT_TOKENS:
            raise RuntimeError("CAP_REACHED")
        resp = generation.call_llm(system, user)
        row = {"n": len(ledger) + 1, "phase": PHASE, "case_id": case_id, "model": resp.model,
               "usage": resp.usage, "latency_s": resp.latency_s, "stop_reason": resp.stop_reason,
               "error": resp.error}
        ledger.append(row)
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return resp
    return fn


def all_text(o):
    if not o:
        return ""
    parts = [o.get("summary") or "", o.get("limitations") or "", o.get("review_note") or ""]
    parts += [s.get("statement", "") if isinstance(s, dict) else str(s) for s in o.get("evidence_statements") or []]
    return "\n".join(map(str, parts))


results = []
for cid in CASES:
    q = queries.loc[cid]
    f, _, _ = RC.real_finding(list(q.target_item_seqs), RC.AGE_BY_RISK[q.risk_type], q.finding_id)
    if f is None:
        sys.exit(f"ABORT: screening did not reproduce {q.finding_id} for {cid}")
    rr = generation.retrieve_evidence(f)
    rec = generation.generate_explanation(f, llm_fn=capped_llm(cid), retrieval_fn=lambda _f: rr,
                                          run_type="step7final_real")
    entry = pipeline._finding_entry(f, rec, include_records=False)
    view, dbg, err = adapters._finding_view(entry, {}, False)
    g, s = entry["generation"], stored.loc[cid]
    out = g["output"] or {}
    stored_out = json.loads(s["output_json"]) if isinstance(s["output_json"], str) else s["output_json"]
    row = {
        "case_id": cid, "phase": PHASE, "risk_type": f.risk_type, "finding_id": f.finding_id,
        "screening_finding_reproduced": True,
        "user_prompt_sha_equal_stored": rec["user_prompt_sha256"] == s["user_prompt_sha256"],
        "system_prompt_sha_equal_stored": generation.SYSTEM_PROMPT_SHA256 == s["system_prompt_sha256"],
        "evidence_ids": [e["evidence_id"] for e in entry["evidence"]],
        "llm_called": g["llm_called"], "llm_error": g["llm_error"], "stop_reason": g["stop_reason"],
        "usage": rec["usage"], "latency_s": rec["latency_s"],
        "core_status": g["status"], "schema_errors": g["schema_errors"], "citation_errors": g["citation_errors"],
        "citation_warnings": g["citation_warnings"], "directive_flags": g["directive_flags"],
        "out_finding_id_match": out.get("finding_id") == f.finding_id,
        "out_risk_type_match": out.get("risk_type") == f.risk_type,
        "evidence_status": out.get("evidence_status"), "cited_evidence_ids": g["cited_evidence_ids"],
        "unsafe_text_reasons": list(P.unsafe_text_reasons(out)) if out else [],
        "denial_scan_hits": DENIAL_SCAN.findall(all_text(out)),
        "display_mode": dbg["display_mode"], "display_mode_reasons": dbg["display_mode_reasons"],
        "adapter_error": err,
        "stored_evidence_status": s["evidence_status"],
        "user_view": dataclasses.asdict(view),
        "raw_response": rec["raw_response"],
        "stored_output": stored_out,
        "evidence_text": {e["evidence_id"]: {"chunk_id": e["chunk_id"], "text": e["chunk_text"]}
                          for e in entry["evidence"]},
    }
    results.append(row)
    (OUT / f"case_{cid}.json").write_text(json.dumps(row, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"{cid}: llm_error={row['llm_error']} core={row['core_status']} ev={row['evidence_status']} "
          f"fid={row['out_finding_id_match']} rt={row['out_risk_type_match']} cit_err={row['citation_errors']} "
          f"flags={row['directive_flags']} unsafe={row['unsafe_text_reasons']} scan={row['denial_scan_hits']} "
          f"mode={row['display_mode']} usage={row['usage']} prompt_eq={row['user_prompt_sha_equal_stored']}")
    if row["llm_error"] or not row["llm_called"]:
        sys.exit(f"STOP: call problem on {cid}")

print("ledger calls:", len(ledger), "in:", sum(r["usage"].get("input_tokens", 0) for r in ledger),
      "out:", sum(r["usage"].get("output_tokens", 0) for r in ledger))
