"""STEP 7-FINAL: deterministic scoring of the 10 NEW real outputs (no API calls).

Usage: python -X utf8 score_new.py <project_root> <out_dir>
Reads case_*.json written by run_real_llm.py. The usefulness rubric is copied verbatim from
reports/step7_validation/step7_eval.py (preregistered); the claim review is Claude's direct comparison
with the evidence text (manual_claim_review.csv) — AI review, not human/clinical review.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests")]

import pandas as pd  # noqa: E402
from app import ui_policy as P  # noqa: E402
from baselines import Baselines  # noqa: E402

qrels = Baselines(ROOT).qrels()
RISK_WORDS = {"contraindication": ["병용금기", "병용 금기"], "elderly_caution": ["노인주의", "노인 주의", "고령자", "노인"],
              "therapeutic_duplication": ["효능군 중복", "효능군", "중복"]}


def name_core(n):
    return re.split(r"[(\[]", str(n or ""))[0].strip()


def usefulness(r):  # verbatim rubric from step7_eval.py (adapted only for field access)
    o = json.loads(r["raw_response"])
    stmts = o.get("evidence_statements") or []
    text_all = " ".join([o.get("summary", ""), o.get("limitations", ""), o.get("review_note", "")] +
                        [s["statement"] for s in stmts])
    drugs = r["user_view"]["drugs"]
    hits = 0
    for d in drugs:
        cands = [name_core(d["item_name"])] + list(d["ingredient_names"] or [])
        hits += any(c and c in text_all for c in cands)
    n = len(drugs)
    a = 2 if hits == n else 1 if hits else 0
    b = 2 if any(w in o.get("summary", "") for w in RISK_WORDS[r["risk_type"]]) else 0
    n_cited = sum(1 for s in stmts if s["evidence_ids"])
    c = 2 if n_cited >= 2 else 1 if n_cited == 1 else 0
    lim = (o.get("limitations") or "").strip()
    d_ = 2 if len(lim) >= 20 else 1 if lim else 0
    labels = {eid: qrels.get((r["case_id"], v["chunk_id"])) for eid, v in r["evidence_text"].items()}
    has_rel = any((v or 0) >= 1 for v in labels.values())
    e = 0 if (o.get("evidence_status") == "INSUFFICIENT" and has_rel) else 2
    consult = len(re.findall(r"의료진|전문가|상담", text_all))
    f_ = 2 if consult <= 2 else 1 if consult == 3 else 0
    total = a + b + c + d_ + e + f_
    return {"a_drug": a, "b_dur": b, "c_evidence": c, "d_uncertainty": d_, "e_no_unneeded_refusal": e,
            "f_consult_repetition": f_, "usefulness_total": total, "useful(>=9)": total >= 9,
            "delivered_total": total if r["display_mode"] == P.EXPLANATION else 0, "has_relevant_evidence_06A": has_rel}


rows = []
for p in sorted(OUT.glob("case_*.json")):
    r = json.loads(p.read_text(encoding="utf-8"))
    o = json.loads(r["raw_response"])
    rows.append({"case_id": r["case_id"], "phase": r["phase"], "risk_type": r["risk_type"],
                 "user_prompt_sha_equal_stored": r["user_prompt_sha_equal_stored"],
                 "input_tokens": r["usage"].get("input_tokens"), "output_tokens": r["usage"].get("output_tokens"),
                 "latency_s": r["latency_s"], "llm_error": r["llm_error"], "core_status": r["core_status"],
                 "finding_id_match": r["out_finding_id_match"], "risk_type_match": r["out_risk_type_match"],
                 "evidence_status": r["evidence_status"], "stored_evidence_status": r["stored_evidence_status"],
                 "n_statements": len(o.get("evidence_statements") or []),
                 "citation_errors": ";".join(r["citation_errors"]), "directive_flags": ";".join(r["directive_flags"]),
                 "unsafe_text_reasons": ";".join(r["unsafe_text_reasons"]), "denial_scan_hits": len(r["denial_scan_hits"]),
                 "display_mode": r["display_mode"], "status_message": r["user_view"]["status_message"],
                 **usefulness(r)})
df = pd.DataFrame(rows)
df.to_csv(OUT / "new_real_results.csv", index=False, encoding="utf-8-sig")
print(df.drop(columns=["status_message"]).to_string())
print("mean usefulness", df.usefulness_total.mean(), "delivered", df.delivered_total.mean())
