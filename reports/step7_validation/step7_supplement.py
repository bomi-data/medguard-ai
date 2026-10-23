"""STEP 7 supplement (read-only, zero API calls): uncertainty paths that step7_eval.py could not reach naturally.

1. A real licensed product (drug_approval_items) that is not in any DUR table -> pipeline output / UI texts.
2. NO_EVIDENCE path: a real screening finding with an empty retrieval result (SYNTHETIC retrieval: the
   corpus covers every DUR item, so a natural empty retrieval did not occur in this data).
3. The verbatim label quotes used in the S1 cases that were withheld.
Usage: python -X utf8 step7_supplement.py <project_root> <out_dir>
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests"), str(ROOT / "tools")]
os.environ.pop("OPENAI_API_KEY", None)

import pandas as pd  # noqa: E402
from dur_safety import resources, retrieval, generation, screening, pipeline  # noqa: E402
from app import ui_policy as P  # noqa: E402
import regression_checks as RC  # noqa: E402

resources.load_resources(ROOT, require_dense=False, verify_hashes=True)   # retrieval content not needed here


def fail_if_called(system, user):
    raise AssertionError("LLM must not be called on this path")


out = {}
items = pd.read_parquet(ROOT / "data/processed/evidence/drug_approval_items.parquet", columns=["ITEM_SEQ", "ITEM_NAME"])
items["ITEM_SEQ"] = items["ITEM_SEQ"].astype(str)
non_dur = items[~items.ITEM_SEQ.isin(screening.KNOWN_DUR_ITEMS)].sort_values("ITEM_SEQ").head(2)
rep = pipeline.run_safety_check(72, non_dur.ITEM_SEQ.tolist(), llm_fn=fail_if_called)
out["real_product_not_in_dur"] = {
    "items": non_dur.to_dict("records"), "n_findings": len(rep["findings"]),
    "warnings": rep["warnings"], "scope_note": rep["pipeline"]["scope_note"],
    "ui_no_finding_text": P.NO_FINDING_TEXT, "ui_notice": P.NOTICE_MESSAGES["NOT_FOUND_IN_DUR_TABLES"][1],
    "contains_forbidden_phrase": any(p in json.dumps(rep, ensure_ascii=False) for p in P.FORBIDDEN_USER_PHRASES)}

f, _, _ = RC.real_finding(["197000079"], 72, "elderly_caution:197000079")
empty = generation.to_retrieval_result("q", [], pd.DataFrame(columns=retrieval.RESULT_COLS),
                                       {"status": "NO_EVIDENCE", "reason": "NO_BM25_MATCH"})
rec = generation.generate_explanation(f, llm_fn=fail_if_called, retrieval_fn=lambda _f: empty)
entry = pipeline._finding_entry(f, rec, False)
mode, _ = P.decide_display_mode(entry["generation"], [], entry["finding_id"], entry["risk_type"])
out["no_evidence_synthetic_retrieval"] = {"gen_status": rec["generation_status"], "llm_called": rec["llm_called"],
                                          "output": rec["output"], "display_mode": mode,
                                          "ui_message": P.MODE_MESSAGES[mode][0],
                                          "dur_rule_texts_still_available": entry["dur_rule_texts"]}

import re  # noqa: E402
syn = pd.read_csv(OUT / "guardrail_synthetic_results.csv")
blocked_s1 = syn[(syn.code == "S1") & (syn.blocked)]
out["s1_blocked_quotes_note"] = ("quotes regenerated with the same deterministic rule as step7_eval.quote_from_evidence "
                                 "from the frozen 06-D evidence (identical to live evidence: Top-5 30/30, STEP 6)")
rx = re.compile("|".join(generation.DIRECTIVE_PATTERNS))
ev = pd.read_parquet(ROOT / "data/processed/evaluation/generation_eval_evidence.parquet")
q = {}
for cid in blocked_s1.case_id:
    e = ev[ev.query_id == cid].sort_values("evidence_id", key=lambda s: s.str[1:].astype(int))
    for r in e.itertuples():
        hit = None
        for sent in re.split(r"(?<=[.다])\s+|\n", r.chunk_text):
            sent = sent.strip()
            if 8 <= len(sent) <= 90 and rx.search(sent) and "'" not in sent:
                hit = sent
                break
        if hit:
            q[cid] = {"evidence_id": r.evidence_id, "chunk_id": r.chunk_id, "quote": hit,
                      "section": getattr(r, "article_title", None)}
            break
out["s1_blocked_quotes"] = q
(OUT / "step7_supplement.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
