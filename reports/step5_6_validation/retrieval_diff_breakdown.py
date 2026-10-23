"""Break down check_retrieval_regression failures (read-only). Usage: python -X utf8 retrieval_diff_breakdown.py <root> <out_json>"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "tools")]
os.environ.pop("OPENAI_API_KEY", None)
from dur_safety import resources  # noqa: E402
from baselines import Baselines  # noqa: E402
import regression_checks as RC  # noqa: E402

resources.load_resources(ROOT, require_dense=True, verify_hashes=True)
r = RC.check_retrieval_regression(Baselines(ROOT))
summary = {"status": r["status"], "n_items": len(r["items"]), "n_pass": sum(i["ok"] for i in r["items"]), "methods": {}}
for m in ["bm25", "dense", "hybrid"]:
    rows = [i[m] for i in r["items"] if m in i]
    nonscore = [(i["case_id"], [d for d in i[m].get("field_diffs", []) if d.split("[")[0] not in
                                ("bm25_score", "dense_score", "prior_score", "hybrid_score")])
                for i in r["items"] if m in i]
    summary["methods"][m] = {
        "n": len(rows), "ok_strict": sum(x.get("ok", x.get("top5_equal")) for x in rows),
        "top5_equal": sum(x["top5_equal"] for x in rows),
        "top10_equal": sum(x.get("top10_equal", x["top5_equal"]) for x in rows),
        "ranking_equal(score-only diffs)": sum(x.get("ranking_equal", x["top5_equal"]) for x in rows),
        "non_score_field_diffs": [c for c in nonscore if c[1]],
        "max_abs_score_diff": max((v for x in rows for k, v in x.get("max_abs_score_diff", {}).items()), default=0.0),
        "status_equal": sum(x.get("status_equal", True) for x in rows)}
summary["other_checks_all_true"] = all(i["query_equal"] and i.get("candidates_restricted_to_target", True)
                                       and i.get("candidate_info_equal", True) for i in r["items"])
summary["device_comparison"] = {k: v for k, v in (r["details"]["device_comparison"] or {}).items() if k != "rows"}
Path(sys.argv[2]).write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=1, default=str))
