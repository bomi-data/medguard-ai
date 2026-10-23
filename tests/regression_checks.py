"""Regression / equivalence checks: production package vs the evaluated notebook baselines.

Every check returns a dict {name, status: PASS|FAIL|SKIPPED, n_total, n_pass, failures, details}.
Nothing is auto-corrected and nothing is approximated: a difference is a FAIL with the exact cause.
No check calls the OpenAI API (see api_guard()).
"""
from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PKG_ROOT = HERE.parent
for p in (PKG_ROOT / "src", PKG_ROOT / "tools", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import nbsource as S  # noqa: E402
from dur_safety import screening, retrieval, findings, generation, pipeline, resources, drug_lookup  # noqa: E402

AGE_BY_RISK = {"elderly_caution": 70, "contraindication": None, "therapeutic_duplication": None}  # 06-E decision
STORE_TOP_K = 10      # 06-A stored Top-10 for every method (POOL/generation use the first 5)
GEN_TOP_K = 5


def jdump(o):  # identical to 06-E jdump
    return json.dumps(o, ensure_ascii=False, sort_keys=True, default=str)


def sha_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def result(name, items, details=None, skipped=None):
    if skipped:
        return {"name": name, "status": "SKIPPED", "reason": skipped, "n_total": 0, "n_pass": 0,
                "failures": [], "details": details or {}}
    fails = [i for i in items if not i.get("ok")]
    return {"name": name, "status": "PASS" if items and not fails else "FAIL", "n_total": len(items),
            "n_pass": len(items) - len(fails), "failures": fails, "items": items, "details": details or {}}


def _isnan(v):
    return v is None or (isinstance(v, float) and math.isnan(v))


def _same(a, b):
    if _isnan(a) and _isnan(b):
        return True
    if isinstance(a, (np.generic,)):
        a = a.item()
    if isinstance(b, (np.generic,)):
        b = b.item()
    return a == b


def diff_paths(a, b, path=""):
    """Paths where two JSON-like objects differ (for exact cause reporting)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{path}.{k} (only in {'new' if k in a else 'baseline'})")
            else:
                out += diff_paths(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path} (len {len(a)} vs {len(b)})"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff_paths(x, y, f"{path}[{i}]")
        return out
    return [] if _same(a, b) else [f"{path}: {str(a)[:80]!r} vs {str(b)[:80]!r}"]


# ======================================================================================
# API guard — any real OpenAI client construction fails and is counted
# ======================================================================================
REAL_API_ATTEMPTS = {"n": 0}


@contextlib.contextmanager
def api_guard():
    import openai
    orig = openai.OpenAI

    class _Blocked:
        def __init__(self, *a, **k):
            REAL_API_ATTEMPTS["n"] += 1
            raise RuntimeError("OpenAI API call blocked during regression tests")

    openai.OpenAI = _Blocked
    try:
        yield REAL_API_ATTEMPTS
    finally:
        openai.OpenAI = orig


# ======================================================================================
# A. Source parity (AST, per function / constant / init statement)
# ======================================================================================
ALLOWED_HANDWRITTEN = {
    "screening": {"_init_from_notebook", "init_screening"},
    "retrieval": {"_init_from_notebook", "init_retrieval"},
    "findings": {"cevi_lu"},
    "generation": {"CHUNK_META"},
}


def check_source_parity(notebook_dir):
    nb_dir = Path(notebook_dir)
    cells = {k: S.load_code_cells(nb_dir / v) for k, v in S.NOTEBOOKS.items()}
    mods = {"screening": screening, "retrieval": retrieval, "findings": findings, "generation": generation}
    items, extras = [], {}
    for mname, (nb, names) in S.MANIFEST.items():
        mod_tree = ast.parse(Path(mods[mname].__file__).read_text(encoding="utf-8"))
        top = {}
        asserts = [n for n in mod_tree.body if isinstance(n, ast.Assert)]
        for n in mod_tree.body:
            nm = S.node_name(n)
            if nm and nm not in top:
                top[nm] = n
        for name in names:
            idx, nb_node, _ = S.find_definition(cells[nb], name)
            mod_node = asserts[0] if name.startswith("@assert") and asserts else top.get(name)
            ok = mod_node is not None and S.dump(mod_node) == S.dump(nb_node)
            items.append({"module": mname, "name": name, "notebook": S.NOTEBOOKS[nb], "cell": idx, "ok": ok,
                          "cause": None if ok else ("missing in module" if mod_node is None else "AST differs")})
        if mname in S.INIT_MANIFEST:
            stmts = S.init_statements(cells, S.INIT_MANIFEST[mname])
            fn = top.get("_init_from_notebook")
            body = [b for b in (fn.body if fn else []) if not isinstance(b, ast.Global)]
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                body = body[1:]   # docstring
            ok_len = len(body) == len(stmts)
            for k, (nbk, idx, nb_node, _) in enumerate(stmts):
                ok = ok_len and S.dump(body[k]) == S.dump(nb_node)
                items.append({"module": mname, "name": f"init[{k}] {S.node_name(nb_node) or type(nb_node).__name__}",
                              "notebook": S.NOTEBOOKS[nbk], "cell": idx, "ok": ok,
                              "cause": None if ok else ("statement count differs" if not ok_len else "AST differs")})
            gl = [b for b in (fn.body if fn else []) if isinstance(b, ast.Global)]
            need = S.assigned_names([s[2] for s in stmts])
            items.append({"module": mname, "name": "init global declaration", "notebook": "-", "cell": None,
                          "ok": bool(gl) and gl[0].names == need, "cause": None if gl and gl[0].names == need else "global list differs"})
        allowed = set(names) | ALLOWED_HANDWRITTEN[mname]
        extra = [S.node_name(n) for n in mod_tree.body if S.node_name(n) and S.node_name(n) not in allowed]
        extras[mname] = extra
        items.append({"module": mname, "name": "no unlisted top-level definitions", "notebook": "-", "cell": None,
                      "ok": not extra, "cause": None if not extra else f"unlisted: {extra}"})
    details = {"notebook_sha256": {v: hashlib.sha256((nb_dir / v).read_bytes()).hexdigest() for v in S.NOTEBOOKS.values()},
               "handwritten_environment_code": {
                   "screening.init_screening": "replaces 02 cell [1] drive.mount + /content/drive root",
                   "retrieval.init_retrieval": "replaces 05 cells [1]-[8] path/INPUTS/config/emb_meta/VERSIONS setup",
                   "config / resources / pipeline / drug_lookup": "hand-written (environment, verification, orchestration, UI adapter)"},
               "extras": extras}
    return result("A. source parity", items, details)


# ======================================================================================
# B. Screening regression (06-E saved real engine outputs)
# ======================================================================================
def _age(v):
    return None if _isnan(v) else int(v)


def check_screening_regression(bl, notebook_dir=None):
    runs = bl.e2e_screening
    items = []
    for r in runs.sort_values("case_id").itertuples():
        items_in = json.loads(r.input_items)
        res = screening.screen_patient(items_in, age=_age(r.input_age), include_evidence=True)
        base = json.loads(r.engine_result_json)
        new = json.loads(jdump(res))
        d = diff_paths(new, base)
        cats = {k: len(new[k]) for k in ["contraindications", "elderly_cautions", "therapeutic_duplications"]}
        items.append({"case_id": r.case_id, "risk_type": r.risk_type, "ok": jdump(res) == r.engine_result_json,
                      "categories_new": cats,
                      "categories_baseline": {k: len(base[k]) for k in cats},
                      "elderly_check_status": new["summary"]["elderly_check_status"],
                      "diff": d[:20]})
    # 02 notebook test suite (cells 37-43), executed against the module functions
    nb_tests = {}
    if notebook_dir:
        cells = S.load_code_cells(Path(notebook_dir) / S.NOTEBOOKS["02"])
        ns = dict(vars(screening))
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            for idx in (37, 38, 39, 40, 41, 42, 43):
                exec(compile(cells[idx], f"<02 cell {idx}>", "exec"), ns)
        nb_tests = dict(ns["TEST_RESULTS"])
        items.append({"case_id": "02 notebook tests", "ok": len(nb_tests) == 20 and all(nb_tests.values()),
                      "n": len(nb_tests), "failed": [k for k, v in nb_tests.items() if not v]})
    readiness = {k: bool(getattr(screening, k)) for k in
                 ["REQUIRED_FILES_OK", "PAIRS_NORMALIZATION_OK", "ELDERLY_DEDUP_OK", "THERAPEUTIC_CANONICAL_OK",
                  "CONTRAINDICATION_LOOKUP_OK", "EVIDENCE_LINKAGE_OK"]}
    items.append({"case_id": "02 readiness flags", "ok": all(readiness.values()), "flags": readiness})
    return result("B. screening regression", items,
                  {"baseline": "evaluation/end_to_end_screening_runs.parquet (06-E engine_result_json)",
                   "data_snapshot": screening.DATA_SNAPSHOT})


# ======================================================================================
# C. Finding parity: real screen_patient() output vs reconstructed finding used in 06-D
# ======================================================================================
FINDING_FIELDS = ["finding_id", "risk_type", "rule_source", "target_item_seqs", "dur_rule_texts", "effect_name",
                  "canonical_pair_id", "finding_source"]


def _finding_view(f):
    return {**{k: getattr(f, k) for k in FINDING_FIELDS}, "drugs": [asdict(d) for d in f.drugs]}


def real_finding(items_in, age, finding_id):
    res = screening.screen_patient(items_in, age=age, include_evidence=True)
    fs = findings.findings_from_screening_result(res)
    match = [f for f in fs if f.finding_id == finding_id]
    return (match[0] if len(match) == 1 else None), fs, res


def _finding_cases(bl):
    """30 eval cases + 3 05 smoke cases: (case_id, items, age, baseline record, baseline finding_source)."""
    out = []
    for q in bl.queries.sort_values("query_id").itertuples():
        out.append((q.query_id, list(q.target_item_seqs), AGE_BY_RISK[q.risk_type], q.finding_id,
                    json.loads(q.screening_record_json), q.finding_source))
    for r in bl.gen05_results.sort_values("query_id").itertuples():
        items_in = json.loads(r.target_item_seqs)
        out.append((r.query_id, items_in, 72, r.finding_id, json.loads(r.screening_record), r.finding_source))
    return out


def check_finding_parity(bl):
    items = []
    for cid, items_in, age, fid, base_rec, base_src in _finding_cases(bl):
        f_new, all_f, _ = real_finding(items_in, age, fid)
        f_base = findings.finding_from_02_record(base_rec, base_src)
        if f_new is None:
            items.append({"case_id": cid, "ok": False, "cause": f"finding {fid} not produced by screen_patient",
                          "findings_produced": [f.finding_id for f in all_f]})
            continue
        vn, vb = _finding_view(f_new), _finding_view(f_base)
        vn_cmp = {k: v for k, v in vn.items() if k != "finding_source"}
        vb_cmp = {k: v for k, v in vb.items() if k != "finding_source"}
        render_new, render_base = generation.render_finding(f_new), generation.render_finding(f_base)
        rec_diff = diff_paths(f_new.screening_record, f_base.screening_record)
        items.append({
            "case_id": cid, "finding_id": fid,
            "ok": vn_cmp == vb_cmp and render_new == render_base,
            "structured_fields_equal": vn_cmp == vb_cmp,
            "field_diff": diff_paths(vn_cmp, vb_cmp),
            "render_finding_equal": render_new == render_base,
            "render_finding_sha256": {"new": sha_text(render_new), "baseline": sha_text(render_base)},
            "n_findings_for_input": len(all_f),
            "finding_source": {"new": f_new.finding_source, "baseline": f_base.finding_source},
            "screening_record_diff_not_in_prompt": rec_diff,
        })
    return result("C. finding parity (real 02 output vs evaluated reconstructed finding)", items,
                  {"note": "screening_record is stored in the generation record but is not rendered into the prompt; "
                           "render_finding() is the exact prompt block"})


# ======================================================================================
# D. Retrieval regression (+ device comparison against the frozen GPU baseline)
# ======================================================================================
SCORE_COLS = ["bm25_score", "bm25_rank", "dense_score", "dense_rank", "prior_score", "hybrid_score", "hybrid_rank"]


def _compare_runs(res, base, method):
    new_ids = res["chunk_id"].tolist() if len(res) else []
    base_ids = base.sort_values("rank")["chunk_id"].tolist()
    out = {"top10_equal": new_ids == base_ids, "top5_equal": new_ids[:5] == base_ids[:5],
           "n_new": len(new_ids), "n_base": len(base_ids),
           "top5_overlap": len(set(new_ids[:5]) & set(base_ids[:5])),
           "new_top5": new_ids[:5], "base_top5": base_ids[:5]}
    score_diffs, max_abs = [], {}
    if out["top10_equal"] and len(new_ids):
        b = base.sort_values("rank").reset_index(drop=True)
        r = res.reset_index(drop=True)
        for col in SCORE_COLS + ["ITEM_SEQ", "rank", "retrieval_method", "text_hash", "n_shared_chunks"]:
            for i in range(len(b)):
                if not _same(r.at[i, col], b.at[i, col]):
                    score_diffs.append(f"{col}[{i}]: {r.at[i, col]!r} vs {b.at[i, col]!r}")
            if col in ("dense_score", "hybrid_score", "bm25_score"):
                rv = pd.to_numeric(r[col], errors="coerce").to_numpy(float)
                bv = pd.to_numeric(b[col], errors="coerce").to_numpy(float)
                m = ~(np.isnan(rv) & np.isnan(bv))
                max_abs[col] = float(np.nanmax(np.abs(rv[m] - bv[m]))) if m.any() else 0.0
        shared_new = r["shared_item_seqs"].map(lambda v: "|".join(v)).tolist()
        if shared_new != b["shared_item_seqs"].tolist():
            score_diffs.append("shared_item_seqs differ")
    else:
        b = base.sort_values("rank")
        bpos = {c: i for i, c in enumerate(base_ids)}
        npos = {c: i for i, c in enumerate(new_ids)}
        out["rank_shift_top5"] = {c: (bpos[c], npos.get(c)) for c in base_ids[:5] if npos.get(c) != bpos[c]}
    score_cols = ("bm25_score", "dense_score", "prior_score", "hybrid_score")
    out["field_diffs"] = score_diffs[:30]
    out["score_only_diffs"] = [d for d in score_diffs if d.split("[")[0] in score_cols][:30]
    out["ranking_equal"] = out["top10_equal"] and len(out["score_only_diffs"]) == len(score_diffs)
    out["max_abs_score_diff"] = max_abs
    out["ok"] = out["top10_equal"] and not score_diffs     # strict: score differences also FAIL
    return out


def check_retrieval_regression(bl, device_label=None):
    raw = bl.retrieval_raw
    runs = bl.retrieval_runs
    qrels = bl.qrels()
    dense_ok = retrieval.dense_available()
    device = device_label or retrieval.DENSE_STATE.get("device")
    items, device_rows = [], []
    for q in bl.queries.sort_values("query_id").itertuples():
        seqs = list(q.target_item_seqs)
        f04 = generation.finding04_from_case({"risk_type": q.risk_type, "item_seqs": seqs, "effect_name": q.effect_name})
        query, _ = retrieval.build_query(f04)
        cand, info = retrieval.get_candidates(q.risk_type, seqs)
        item = {"case_id": q.query_id, "risk_type": q.risk_type, "query_equal": query == q.query_text,
                "candidates_restricted_to_target": bool(set(cand["ITEM_SEQ"]) <= set(seqs)),
                "n_candidates": info["n_candidates"]}
        if runs is not None:
            rr = runs[(runs.query_id == q.query_id)].set_index("method")
            item["candidate_info_equal"] = all(int(rr.loc[m, k]) == info[k] for m in rr.index
                                               for k in ["n_candidates", "n_candidate_texts", "n_preferred"])
        methods = {"bm25": lambda: retrieval.retrieve_bm25(query, cand, STORE_TOP_K, q.risk_type)}
        if dense_ok:
            methods["dense"] = lambda: retrieval.retrieve_dense(query, cand, STORE_TOP_K, q.risk_type)
            methods["hybrid"] = lambda: retrieval.retrieve_hybrid(query, q.risk_type, seqs, STORE_TOP_K)
        oks = [item["query_equal"], item["candidates_restricted_to_target"], item.get("candidate_info_equal", True)]
        for m, fn in methods.items():
            res, st = fn()
            base = raw[(raw.query_id == q.query_id) & (raw.method == m)]
            c = _compare_runs(res, base, m)
            c["status"] = st["status"]
            if runs is not None:
                c["status_equal"] = st["status"] == runs[(runs.query_id == q.query_id) & (runs.method == m)].iloc[0]["status"]
            item[m] = c
            oks.append(c["ok"] and c.get("status_equal", True))
            if m == "hybrid":
                lost = [ch for ch in c["base_top5"] if ch not in c["new_top5"]]
                added = [ch for ch in c["new_top5"] if ch not in c["base_top5"]]
                device_rows.append({
                    "case_id": q.query_id, "risk_type": q.risk_type, "exact_top5": c["top5_equal"],
                    "top5_overlap": c["top5_overlap"], "rank_shift_top5": c.get("rank_shift_top5", {}),
                    "lost_chunks": [{"chunk_id": ch, "label": qrels.get((q.query_id, ch))} for ch in lost],
                    "added_chunks": [{"chunk_id": ch, "label": qrels.get((q.query_id, ch), "unjudged")} for ch in added],
                    "lost_relevant(label>=1)": sum(1 for ch in lost if (qrels.get((q.query_id, ch)) or 0) >= 1),
                    "lost_direct(label=2)": sum(1 for ch in lost if qrels.get((q.query_id, ch)) == 2),
                    "max_abs_dense_score_diff": c["max_abs_score_diff"].get("dense_score")})
        item["ok"] = all(oks)
        items.append(item)
    # 04 smoke (3 queries x 3 methods, Top-5)
    smoke = bl.smoke_results
    for case in bl.smoke_queries:
        f04 = generation.finding04_from_case(case)
        query, _ = retrieval.build_query(f04)
        cand, _ = retrieval.get_candidates(f04["risk_type"], f04["item_seqs"])
        item = {"case_id": case["query_id"], "query_equal": query == case["query"]}
        oks = [item["query_equal"]]
        methods = {"bm25": lambda: retrieval.retrieve_bm25(query, cand, GEN_TOP_K, f04["risk_type"])}
        if dense_ok:
            methods["dense"] = lambda: retrieval.retrieve_dense(query, cand, GEN_TOP_K, f04["risk_type"])
            methods["hybrid"] = lambda: retrieval.retrieve_hybrid(query, f04["risk_type"], f04["item_seqs"], GEN_TOP_K)
        for m, fn in methods.items():
            res, _ = fn()
            base = smoke[(smoke.query_id == case["query_id"]) & (smoke.retrieval_method == m)]
            new_ids = res["chunk_id"].tolist()
            ok = new_ids == base.sort_values("rank")["chunk_id"].tolist()
            item[m] = {"top5_equal": ok, "new_top5": new_ids}
            oks.append(ok)
        item["ok"] = all(oks)
        items.append(item)
    dev = None
    if dense_ok and device_rows:
        n = len(device_rows)
        dev = {"device": device, "baseline": "06-A frozen hybrid Top-5 (Colab GPU, fp16 query encoding)",
               "exact_top5_match": f"{sum(r['exact_top5'] for r in device_rows)}/{n}",
               "mean_top5_overlap": round(sum(r["top5_overlap"] for r in device_rows) / (5 * n), 4),
               "affected_cases": [r["case_id"] for r in device_rows if not r["exact_top5"]],
               "cases_losing_relevant_evidence": [r["case_id"] for r in device_rows if r["lost_relevant(label>=1)"]],
               "cases_losing_direct_evidence": [r["case_id"] for r in device_rows if r["lost_direct(label=2)"]],
               "downstream": "any Top-5 change changes E1..E5 and therefore the generation prompt (sha256)",
               "rows": device_rows}
    r = result("D. retrieval regression", items, {"device": device, "dense_available": dense_ok,
                                                   "device_comparison": dev,
                                                   "dense_state": dict(retrieval.DENSE_STATE)})
    if not dense_ok:
        r["status"] = "FAIL" if r["status"] == "FAIL" else "PARTIAL_BM25_ONLY"
        r["reason"] = "dense model/index not loaded — dense & hybrid comparisons not executed"
    return r


# ======================================================================================
# E. Generation-input parity
# ======================================================================================
def _replay_fn(bl):
    """finding_id -> frozen hybrid Top-5 RetrievalResult (06-D replay for 30 cases; 04 smoke for 3)."""
    raw, q = bl.retrieval_raw, bl.queries.set_index("query_id")
    runs = bl.retrieval_runs
    table = {}
    for qid in q.index:
        res = (raw[(raw.query_id == qid) & (raw.method == "hybrid") & (raw["rank"] <= GEN_TOP_K)].sort_values("rank")
               .drop(columns=["query_id", "method", "query_text_used"]).reset_index(drop=True))
        status = "OK"
        warnings, reason = [], None
        if runs is not None:
            rr = runs[(runs.query_id == qid) & (runs.method == "hybrid")].iloc[0]
            status, reason = rr["status"], (None if _isnan(rr["reason"]) else rr["reason"])
            warnings = json.loads(rr["warnings_json"] or "[]")
        table[q.loc[qid, "finding_id"]] = (q.loc[qid, "query_text"], json.loads(q.loc[qid, "query_components_json"]),
                                           res, {"status": status, "reason": reason, "warnings": warnings})
    smoke = bl.smoke_results
    for case in bl.smoke_queries:
        res = (smoke[(smoke.query_id == case["query_id"]) & (smoke.retrieval_method == "hybrid")].sort_values("rank")
               .drop(columns=["query_id", "query", "relevance_label"]).reset_index(drop=True))
        fid = {"elderly_caution": lambda: f"elderly_caution:{case['item_seqs'][0]}",
               "contraindication": lambda: f"contraindication:{'|'.join(sorted(case['item_seqs']))}",
               "therapeutic_duplication": lambda: f"therapeutic_duplication:{case['effect_name']}:{'|'.join(sorted(case['item_seqs']))}"}[case["risk_type"]]()
        table[fid] = (case["query"], case["query_components"], res, {"status": "OK", "reason": None, "warnings": []})
    # shared_item_seqs stays the stored "a|b" string, exactly as 06-D replayed it
    # (05 prepare_evidence_context splits strings).

    def fn(finding):
        if finding.finding_id not in table:
            raise KeyError(f"no frozen retrieval for {finding.finding_id}")
        qt, comps, res, st = table[finding.finding_id]
        return generation.to_retrieval_result(qt, comps, res.copy(), {**st, "items_requested": finding.target_item_seqs})
    return fn


def _gen_baseline_rows(bl):
    rows = []
    ev_eval, ev05 = bl.gen_eval_evidence, bl.gen05_evidence
    for r in bl.gen_eval_results.sort_values("query_id").to_dict("records"):
        rows.append((r, ev_eval[ev_eval.run_id == r["run_id"]]))
    for r in bl.gen05_results.sort_values("query_id").to_dict("records"):
        rows.append((r, ev05[ev05.run_id == r["run_id"]]))
    return rows


def _split_prompt(p):
    a = p.split("<evidence>")
    return {"structured_finding": a[0], "evidence": "<evidence>" + a[1].split("</evidence>")[0] if len(a) > 1 else "",
            "task": p.split("</evidence>")[-1]}


def check_generation_input_parity(bl, mode):
    """mode: 'evaluated_finding+frozen_evidence' | 'production_finding+frozen_evidence' | 'production_live'."""
    if mode == "production_live" and not retrieval.dense_available():
        return result(f"E. generation-input parity [{mode}]", [], skipped="dense model/index not loaded")
    replay = _replay_fn(bl)
    cases = {c[0]: c for c in _finding_cases(bl)}
    items = []
    for base, ev_rows in _gen_baseline_rows(bl):
        cid = base["query_id"]
        if mode.startswith("evaluated_finding"):
            f = findings.finding_from_02_record(json.loads(base["screening_record"]), base["finding_source"])
        else:
            _, items_in, age, fid, _, _ = cases[cid]
            f, _, _ = real_finding(items_in, age, fid)
            if f is None:
                items.append({"case_id": cid, "ok": False, "cause": "finding not produced"})
                continue
        retr = replay(f) if "frozen_evidence" in mode else generation.retrieve_evidence(f)
        gi = generation.prepare_evidence_context(retr, f)
        p = generation.build_prompt(gi)
        base_chunks = ev_rows.sort_values("evidence_id", key=lambda s: s.str[1:].astype(int))["chunk_id"].tolist()
        new_chunks = [e.chunk_id for e in gi.evidence]
        same_prompt = p["user_prompt_sha256"] == base["user_prompt_sha256"] and p["user"] == base["user_prompt"]
        parts_n, parts_b = _split_prompt(p["user"]), _split_prompt(base["user_prompt"] or "")
        items.append({
            "case_id": cid, "finding_id": f.finding_id,
            "ok": same_prompt and new_chunks == base_chunks and p["system"] == generation.SYSTEM_PROMPT
                  and generation.SYSTEM_PROMPT_SHA256 == base["system_prompt_sha256"],
            "evidence_chunks_equal": new_chunks == base_chunks,
            "evidence_ids_equal": [e.evidence_id for e in gi.evidence] == json.loads(base["evidence_ids"]),
            "user_prompt_sha256_equal": p["user_prompt_sha256"] == base["user_prompt_sha256"],
            "differing_prompt_sections": [k for k in parts_n if parts_n[k] != parts_b.get(k)],
            "system_prompt_sha256_equal": generation.SYSTEM_PROMPT_SHA256 == base["system_prompt_sha256"],
            "model_prompt_version_equal": (generation.GENERATION_CONFIG["model"], generation.PROMPT_VERSION,
                                           generation.OUTPUT_SCHEMA_VERSION)
                                          == (base["model"], base["prompt_version"], base["output_schema_version"]),
            "retrieval_query_equal": retr.query == base["retrieval_query"],
            "new_chunks": new_chunks, "base_chunks": base_chunks,
            "dropped": gi.dropped_evidence, "evidence_errors": gi.evidence_errors,
        })
    return result(f"E. generation-input parity [{mode}]", items,
                  {"system_prompt_sha256": generation.SYSTEM_PROMPT_SHA256,
                   "output_schema": generation.OUTPUT_SCHEMA_VERSION})


# ======================================================================================
# F. Output-validation regression (saved raw_response -> validate_output) + 05 failure tests
# ======================================================================================
def evidence_items_from_saved(ev_rows):
    fields = list(generation.EvidenceItem.__dataclass_fields__)
    rows = sorted(ev_rows.to_dict("records"), key=lambda r: int(str(r["evidence_id"])[1:]))
    out = []
    for r in rows:
        kw = {k: generation._val(r.get(k)) for k in fields}
        s = r.get("shared_item_seqs")
        kw["shared_item_seqs"] = s.split("|") if isinstance(s, str) else list(s or [])
        out.append(generation.EvidenceItem(**kw))
    return out


def check_output_validation(bl, notebook_dir=None):
    items = []
    for base, ev_rows in _gen_baseline_rows(bl):
        f = findings.finding_from_02_record(json.loads(base["screening_record"]), base["finding_source"])
        gi = generation.GenerationInput(f, generation.RetrievalResult("OK", None, [], "hybrid", "", [], {}, pd.DataFrame()),
                                        evidence_items_from_saved(ev_rows), [], [])
        obj = json.loads(base["raw_response"])
        s_err, c_err, c_warn, cited, flags = generation.validate_output(obj, gi)
        status = "GENERATED" if not s_err and not c_err else "INVALID_OUTPUT"
        saved = tuple(json.loads(base[k]) for k in ["schema_errors", "citation_errors", "citation_warnings",
                                                    "cited_evidence_ids", "directive_flags"])
        items.append({"case_id": base["query_id"],
                      "ok": (s_err, c_err, c_warn, cited, flags) == saved and status == base["generation_status"]
                            and obj == json.loads(base["output_json"]),
                      "status": status, "saved_status": base["generation_status"],
                      "cited": cited, "saved_cited": saved[3], "directive_flags": flags,
                      "diff": [k for k, a, b in zip(["schema_errors", "citation_errors", "citation_warnings", "cited",
                                                     "directive_flags"], (s_err, c_err, c_warn, cited, flags), saved) if a != b]})
    # 05 failure tests (cell [41]) re-executed against the module with frozen Q1 retrieval; fake LLM only
    if notebook_dir:
        cells = S.load_code_cells(Path(notebook_dir) / S.NOTEBOOKS["05"])
        replay = _replay_fn(bl)
        smoke_findings = []
        for r in bl.gen05_results.sort_values("query_id").to_dict("records"):
            smoke_findings.append((r["query_id"], findings.finding_from_02_record(json.loads(r["screening_record"]),
                                                                                  r["finding_source"])))
        ns = {**vars(generation), "SMOKE_FINDINGS": smoke_findings, "retrieve_evidence": replay, "QA": {},
              "pd": pd, "asdict": asdict, "ScreeningFinding": findings.ScreeningFinding,
              "RetrievalResult": findings.RetrievalResult}
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(cells[41], "<05 cell 41>", "exec"), ns)
        got = {r["case"]: r for r in ns["failure_results"]}
        for exp in bl.gen05_failure_tests:
            g = got.get(exp["case"])
            same = g is not None and all(g.get(k) == exp.get(k) for k in
                                         ["expected", "got", "llm_invoked", "schema_errors", "citation_errors",
                                          "evidence_errors", "ok"] if k in exp)
            items.append({"case_id": f"05 failure test: {exp['case']}", "ok": same,
                          "expected": exp.get("got"), "got": g.get("got") if g else None})
    return result("F. output-validation regression", items)


# ======================================================================================
# G. Pipeline integration (mock LLM — zero API calls)
# ======================================================================================
def make_mock_llm(bl):
    by_sha = {}
    for base, _ in _gen_baseline_rows(bl):
        by_sha[base["user_prompt_sha256"]] = base["raw_response"]
    calls = {"n": 0, "unknown": []}

    def mock(system, user):
        calls["n"] += 1
        sha = sha_text(user)
        if system != generation.SYSTEM_PROMPT:
            return generation.LLMResponse(None, "mock", "mock", error="MOCK_SYSTEM_PROMPT_MISMATCH")
        if sha not in by_sha:
            calls["unknown"].append(sha)
            return generation.LLMResponse(None, "mock", "mock", error=f"MOCK_NO_BASELINE_FOR_PROMPT:{sha[:12]}")
        return generation.LLMResponse(by_sha[sha], "mock", "mock", stop_reason="completed")
    return mock, calls


REQUIRED_KEYS = {"pipeline", "screening", "findings", "summary", "warnings", "errors"}
FINDING_KEYS = {"finding_id", "risk_type", "target_item_seqs", "drugs", "retrieval", "evidence", "generation"}


def check_pipeline_integration(bl, retrieval_mode):
    if retrieval_mode == "live" and not retrieval.dense_available():
        return result(f"G. pipeline integration [{retrieval_mode}]", [], skipped="dense model/index not loaded")
    mock, calls = make_mock_llm(bl)
    rfn = _replay_fn(bl) if retrieval_mode == "replay" else None
    base_by_fid = {b["finding_id"]: (b, ev) for b, ev in _gen_baseline_rows(bl)}
    items = []
    with api_guard() as guard:
        before = guard["n"]
        # 30 evaluation cases
        for q in bl.queries.sort_values("query_id").itertuples():
            rep = pipeline.run_safety_check(AGE_BY_RISK[q.risk_type], list(q.target_item_seqs), llm_fn=mock,
                                            retrieval_fn=rfn)
            b, ev = base_by_fid[q.finding_id]
            ok_struct = REQUIRED_KEYS <= set(rep) and all(FINDING_KEYS <= set(e) for e in rep["findings"])
            fe = [e for e in rep["findings"] if e["finding_id"] == q.finding_id]
            ok = ok_struct and len(rep["findings"]) == 1 and len(fe) == 1
            g = fe[0]["generation"] if fe else {}
            ev_ids = [e["chunk_id"] for e in fe[0]["evidence"]] if fe else []
            base_ev = ev.sort_values("evidence_id", key=lambda s: s.str[1:].astype(int))["chunk_id"].tolist()
            same = ok and g.get("status") == b["generation_status"] and g.get("output") == json.loads(b["output_json"]) \
                and g.get("cited_evidence_ids") == json.loads(b["cited_evidence_ids"]) and ev_ids == base_ev \
                and g.get("user_prompt_sha256") == b["user_prompt_sha256"]
            items.append({"case_id": q.query_id, "ok": bool(same), "structure_ok": ok_struct,
                          "n_findings": len(rep["findings"]), "status": g.get("status"),
                          "saved_status": b["generation_status"], "evidence_equal": ev_ids == base_ev,
                          "prompt_sha_equal": g.get("user_prompt_sha256") == b["user_prompt_sha256"],
                          "llm_error": g.get("llm_error"), "warnings": [w["code"] for w in rep["warnings"]]})
        # multi-finding patient = 02 demo patient (cell 46 input) — its 3 findings are the 05 smoke findings
        demo = [195700013, "196900031", "197000068", "197000079", "197700114", "196900031"]
        expect = {"contraindication:195700013|196900031", "elderly_caution:197000079",
                  "therapeutic_duplication:당뇨병용제:197000068|197700114"}
        for age, exp_ids, exp_status in [(72, expect, "evaluated"),
                                         (64, expect - {"elderly_caution:197000079"}, "not_applicable_age_below_threshold"),
                                         (None, expect - {"elderly_caution:197000079"}, "not_evaluated_age_missing")]:
            rep = pipeline.run_safety_check(age, demo, llm_fn=mock, retrieval_fn=rfn)
            got_ids = [e["finding_id"] for e in rep["findings"]]
            outs_ok = all(e["generation"]["status"] == base_by_fid[e["finding_id"]][0]["generation_status"]
                          and e["generation"]["output"] == json.loads(base_by_fid[e["finding_id"]][0]["output_json"])
                          for e in rep["findings"] if e["finding_id"] in base_by_fid)
            items.append({"case_id": f"multi-finding demo patient age={age}",
                          "ok": set(got_ids) == exp_ids and len(got_ids) == len(exp_ids) and outs_ok
                                and rep["summary"]["elderly_check_status"] == exp_status
                                and rep["screening"]["patient"]["duplicate_inputs"] == ["196900031"],
                          "findings": got_ids, "statuses": rep["summary"]["generation_status_counts"],
                          "warnings": [w["code"] for w in rep["warnings"]]})
        # no-finding inputs: no LLM call
        n0 = calls["n"]
        rep = pipeline.run_safety_check(72, [], llm_fn=mock, retrieval_fn=rfn)
        items.append({"case_id": "empty medication list", "ok": rep["findings"] == [] and calls["n"] == n0})
        rep = pipeline.run_safety_check(72, ["000000000", None, "nan"], llm_fn=mock, retrieval_fn=rfn)
        codes = [w["code"] for w in rep["warnings"]]
        items.append({"case_id": "unknown / invalid identifiers", "ok": rep["findings"] == [] and calls["n"] == n0
                      and "NOT_FOUND_IN_DUR_TABLES" in codes and "INVALID_INPUTS" in codes, "warnings": codes})
        real_attempts = guard["n"] - before
    items.append({"case_id": "real OpenAI API calls", "ok": real_attempts == 0, "n": real_attempts})
    items.append({"case_id": "mock prompts without baseline", "ok": not calls["unknown"], "unknown": calls["unknown"]})
    return result(f"G. pipeline integration [{retrieval_mode}]", items,
                  {"mock_llm_calls": calls["n"], "real_api_calls": real_attempts})


# ======================================================================================
# drug_lookup behaviour (adapter, not part of the evaluated scope)
# ======================================================================================
def check_drug_lookup():
    items = []
    r = drug_lookup.search_drugs("다오닐")
    items.append({"case_id": "returns candidates, never auto-selects", "ok": r["requires_user_selection"]
                  and r["auto_selected"] is None and any(c["item_seq"] == "197000068" for c in r["candidates"])})
    r = drug_lookup.search_drugs("197000079")
    items.append({"case_id": "exact item_seq query", "ok": r["candidates"][:1] and r["candidates"][0]["item_seq"] == "197000079"
                  and r["candidates"][0]["match_type"] == "item_seq"})
    r = drug_lookup.search_drugs("정")
    items.append({"case_id": "ambiguous query -> many candidates, truncated, none chosen",
                  "ok": r["n_matches"] > 20 and r["truncated"] and len(r["candidates"]) == 20 and r["auto_selected"] is None})
    try:
        drug_lookup.confirm_selection(["999999999"])
        ok = False
    except ValueError:
        ok = True
    items.append({"case_id": "confirm_selection rejects unknown item_seq", "ok": ok})
    items.append({"case_id": "confirm_selection keeps order/duplicates",
                  "ok": drug_lookup.confirm_selection(["197000079", "197000068", "197000079"]) == ["197000079", "197000068", "197000079"]})
    return result("drug_lookup adapter behaviour (not evaluated scope)", items)


# ======================================================================================
# Protected-file snapshot (existing notebooks / artifacts must not change)
# ======================================================================================
DRIVE_NATIVE = {".gsheet", ".gdoc", ".gslides", ".gdraw", ".gform", ".gmap", ".gsite", ".gjam", ".gscript"}


def snapshot(project_root):
    root = Path(project_root)
    files = [p for p in (root / "notebooks").glob("*.ipynb")]
    files += [p for p in (root / "data" / "processed").rglob("*") if p.is_file()]
    out = {}
    for p in sorted(files):
        if p.suffix.lower() in DRIVE_NATIVE:
            continue
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for b in iter(lambda: f.read(8 << 20), b""):
                h.update(b)
        out[str(p.relative_to(root))] = h.hexdigest()
    return out
