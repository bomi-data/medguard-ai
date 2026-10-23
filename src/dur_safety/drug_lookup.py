"""Drug-name search for the UI — NEW INPUT ADAPTER, OUTSIDE THE EVALUATED SAFETY ENGINE SCOPE.

The evaluated pipeline (02 -> 04 -> 05, evaluated in 06-A..06-E) receives item_seq values directly.
Mapping a typed drug name to an item_seq was never part of that evaluation. This module therefore:

  * only RETURNS CANDIDATES — it never chooses one item_seq on the user's behalf, even when a single
    candidate matches (no fuzzy auto-resolution);
  * uses only data already in the project: the 02 engine's own name table `DRUG_NAME_BY_ITEM`
    (built from DUR elderly / therapeutic / easy_drug_canonical / contraindication tables, notebook 02
    cell [26]); no external data or API;
  * `confirm_selection()` only validates that the user-selected values are known item_seq strings.
    The confirmed list is what goes into `pipeline.run_safety_check(medications=...)`.

No clinical judgement or filtering is done here: a candidate that is not in any DUR table is still
returned (flagged `in_dur_tables=False`) and, if selected, the engine reports it in
`patient.not_found_in_dur_tables` exactly as evaluated.
"""
from __future__ import annotations

import re

from . import screening, retrieval, resources

ADAPTER_SCOPE_NOTE = (
    "drug_lookup is a new input adapter outside the evaluated safety-engine scope (06-A..06-E used item_seq "
    "input). It returns candidates only; the user must select the exact product.")

_WS = re.compile(r"\s+")
_NINE_DIGITS = re.compile(r"\d{9}")


def _norm(text):
    return _WS.sub("", str(text or "")).casefold()


def _candidate(item_seq, match_type):
    return {
        "item_seq": item_seq,
        "item_name": screening.DRUG_NAME_BY_ITEM.get(item_seq),
        "in_dur_tables": item_seq in screening.KNOWN_DUR_ITEMS,
        "in_evidence_corpus": item_seq in retrieval.ITEM_INDEX,
        "match_type": match_type,
    }


def search_drugs(query, limit=20):
    """Return candidate products for a typed name or item_seq. Never auto-selects.

    match_type: "item_seq" (exact 9-digit id) | "name_exact" | "name_prefix" | "name_contains"
    (comparison ignores whitespace and letter case). Ordering is deterministic.
    """
    if not resources.is_loaded():
        raise RuntimeError("call resources.load_resources() first")
    q = str(query or "").strip()
    nq = _norm(q)
    result = {"query": q, "candidates": [], "n_matches": 0, "truncated": False,
              "requires_user_selection": True, "auto_selected": None, "scope_note": ADAPTER_SCOPE_NOTE}
    if not nq:
        return result
    rank = {"item_seq": 0, "name_exact": 1, "name_prefix": 2, "name_contains": 3}
    hits = []
    if _NINE_DIGITS.fullmatch(q) and q in screening.DRUG_NAME_BY_ITEM:
        hits.append((q, "item_seq"))
    for item_seq, name in screening.DRUG_NAME_BY_ITEM.items():
        n = _norm(name)
        if not n or nq not in n:
            continue
        mt = "name_exact" if n == nq else "name_prefix" if n.startswith(nq) else "name_contains"
        hits.append((item_seq, mt))
    seen, uniq = set(), []
    for item_seq, mt in sorted(hits, key=lambda h: (rank[h[1]], len(screening.DRUG_NAME_BY_ITEM.get(h[0]) or ""), h[0])):
        if item_seq not in seen:
            seen.add(item_seq)
            uniq.append((item_seq, mt))
    result["n_matches"] = len(uniq)
    result["truncated"] = len(uniq) > limit
    result["candidates"] = [_candidate(s, mt) for s, mt in uniq[:limit]]
    return result


def confirm_selection(item_seqs):
    """Validate item_seq values the USER selected from candidates. Returns them unchanged (as str, in order).

    Raises ValueError for values that are not 9-digit item_seq strings known to the project name table.
    Duplicates are kept: the 02 engine itself records them in patient.duplicate_inputs.
    """
    if isinstance(item_seqs, (str, bytes, int)):
        raise TypeError("item_seqs must be a list of selected item_seq strings")
    confirmed, unknown = [], []
    for s in item_seqs:
        s = str(s).strip()
        if not _NINE_DIGITS.fullmatch(s) or s not in screening.DRUG_NAME_BY_ITEM:
            unknown.append(s)
        else:
            confirmed.append(s)
    if unknown:
        raise ValueError(f"not a known item_seq (select from search_drugs candidates): {unknown}")
    return confirmed
