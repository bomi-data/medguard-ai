"""STEP 8: list the 30 existing evaluation cases with their inputs and how many findings (= LLM calls in the
app, one per finding) each input produces. No API call; read-only.

Usage: python -X utf8 case_inventory.py <project_root> <out_json>
"""
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "tools")]

from dur_safety import resources, screening, findings, drug_lookup  # noqa: E402
from baselines import Baselines  # noqa: E402
import regression_checks as RC  # noqa: E402

resources.load_resources(ROOT, require_dense=False, verify_hashes=False)
bl = Baselines(ROOT)
rows = []
for q in bl.queries.sort_values("query_id").itertuples():
    items = [str(x) for x in q.target_item_seqs]
    age = RC.AGE_BY_RISK[q.risk_type]
    res = screening.screen_patient(items, age=age, include_evidence=True)
    fs = findings.findings_from_screening_result(res)
    names = {}
    for s in items:
        r = drug_lookup.search_drugs(s, limit=1)
        c = (r.get("candidates") or [{}])[0]
        names[s] = c.get("item_name")
    rows.append({"case_id": q.query_id, "risk_type": q.risk_type, "items": items, "names": names, "age": age,
                 "target_finding_id": q.finding_id,
                 "n_findings": len(fs), "finding_ids": [f.finding_id for f in fs],
                 "risk_types": [f.risk_type for f in fs], "summary": res["summary"]})
Path(sys.argv[2]).write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
for r in rows:
    print(r["case_id"], r["risk_type"], r["age"], r["items"], list(r["names"].values()), "n_findings=", r["n_findings"],
          r["risk_types"])
