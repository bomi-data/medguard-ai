"""STEP 7-R held-out revalidation (read-only, zero API calls).

Usage: python -X utf8 reval_heldout.py <project_root> <out_dir> <label: before|after>
Injects each frozen held-out phrase into every REAL_STORED output (30) and runs the real path:
screening -> live hybrid retrieval -> generate_explanation -> _finding_entry -> ui_policy.decide_display_mode.
"""
import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
LABEL = sys.argv[3]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "tools")]
os.environ.pop("OPENAI_API_KEY", None)

import pandas as pd  # noqa: E402
from dur_safety import resources, generation, pipeline  # noqa: E402
from app import ui_policy as P  # noqa: E402
import regression_checks as RC  # noqa: E402
from baselines import Baselines  # noqa: E402

resources.load_resources(ROOT, require_dense=True, verify_hashes=True)
bl = Baselines(ROOT)
gen = pd.read_parquet(ROOT / "data/processed/evaluation/generation_eval_results.parquet").set_index("query_id")
cases = json.loads((OUT / "heldout_cases_FROZEN.json").read_text(encoding="utf-8"))
cache = {}


def run(finding, text):
    if finding.finding_id not in cache:
        cache[finding.finding_id] = generation.retrieve_evidence(finding)
    rr = cache[finding.finding_id]
    rec = generation.generate_explanation(
        finding, llm_fn=lambda s, u: generation.LLMResponse(text, "stored", "stored", stop_reason="completed"),
        retrieval_fn=lambda f: rr)
    entry = pipeline._finding_entry(finding, rec, False)
    mode, reasons = P.decide_display_mode(entry["generation"], [e["evidence_id"] for e in entry["evidence"]],
                                          finding_id=finding.finding_id, risk_type=finding.risk_type)
    return entry, mode, reasons


def inject(o, c, eid):
    o = copy.deepcopy(o)
    if c["field"] == "stmt":
        o["evidence_statements"] = o["evidence_statements"] + [{"statement": f"{c['text']} [{eid}].", "evidence_ids": [eid]}]
    elif c["field"] == "summary":
        o["summary"] = o["summary"].rstrip() + " " + c["text"]
    elif c["field"] == "limitations":
        o["limitations"] = (o["limitations"].rstrip() + " " + c["text"]).strip()
    elif c["field"] == "review_note":
        o["review_note"] = c["text"]
    return o


rows = []
for q in bl.queries.sort_values("query_id").itertuples():
    f, _, _ = RC.real_finding(list(q.target_item_seqs), RC.AGE_BY_RISK[q.risk_type], q.finding_id)
    raw = gen.loc[q.query_id, "raw_response"]
    entry, mode, reasons = run(f, raw)
    eid = sorted((e["evidence_id"] for e in entry["evidence"]), key=lambda s: int(s[1:]))[0]
    rows.append({"case_id": q.query_id, "set": "REAL_STORED", "id": "S0", "kind": "original", "expected": "ALLOW",
                 "display_mode": mode, "reasons": reasons,
                 "cited": entry["generation"]["cited_evidence_ids"], "status": entry["generation"]["status"]})
    base = json.loads(raw)
    for exp, group in (("BLOCK", cases["block_expected"]), ("ALLOW", cases["allow_expected"])):
        for c in group:
            _, m, rs = run(f, json.dumps(inject(base, c, eid), ensure_ascii=False))
            rows.append({"case_id": q.query_id, "set": "HELDOUT", "id": c["id"], "kind": c["kind"], "expected": exp,
                         "display_mode": m, "reasons": rs})

df = pd.DataFrame(rows)
df["blocked"] = df.display_mode != P.EXPLANATION
df.to_csv(OUT / f"heldout_{LABEL}.csv", index=False, encoding="utf-8-sig")
h = df[df.set == "HELDOUT"]
summary = {
    "label": LABEL,
    "real_stored_shown": f"{int((~df[df.set == 'REAL_STORED'].blocked).sum())}/30",
    "heldout_unsafe_pass": f"{int((~h[h.expected == 'BLOCK'].blocked).sum())}/{int((h.expected == 'BLOCK').sum())}",
    "heldout_false_positive": f"{int(h[h.expected == 'ALLOW'].blocked.sum())}/{int((h.expected == 'ALLOW').sum())}",
    "by_id": {i: f"blocked {int(g.blocked.sum())}/{len(g)} ({g.expected.iloc[0]})" for i, g in h.groupby("id")},
}
(OUT / f"heldout_{LABEL}_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=1))
