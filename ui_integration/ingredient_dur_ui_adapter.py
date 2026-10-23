"""ingredient_dur_ui_adapter.py — MEDGUARD AI 17단계: 16번 통합 Screening → Streamlit UI 어댑터.

이 모듈은 16번 노트북(16_ingredient_dur_integration.ipynb)에서 *실제 Colab 실행으로 검증된*(CONDITIONAL_GO) 코드 셀
(입력 검증 · DurAdapter · IngredientAdapter · JSON 스키마/의미 검사 · 근거 생성 · integrated_screen)을
**문자 그대로 추출**한 것입니다. 판정 로직을 다시 구현하지 않았습니다. 추출 구간은 `# ===== [16:CELL n]` 표식으로 구분됩니다.
이 모듈에 추가된 것은 ① 프로젝트 파일 로딩(16번 CELL 1·3·4의 로딩 방식 그대로, 파일은 읽기 전용) ② UI 안전 래퍼 `screen_for_ui`
③ 화면 표시용 데이터 변환 `build_ui_model`(표시 문구/라벨만, 판정 변경 없음)뿐입니다.

고정 원칙: 공식 성분 동일성 검증 NO-GO 유지 · 임상 검증 NOT_VALIDATED · 성분 후보는 공식 DUR 병용금기가 아님 · 합산 점수 없음 ·
RAG/LLM 미사용(템플릿 표시). 이 모듈은 어떤 프로젝트 파일도 쓰거나 수정하지 않습니다.
"""
from __future__ import annotations

import contextlib, hashlib, inspect, io, json, os, platform, random, re, shutil, sys, time, types, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

MODULE_VERSION = "17.0"
SEED = 20261016
MAX_ITEMS = 20                                   # 16번과 동일: 초과 시 잘라내지 않고 입력 오류
OFFICIAL_IDENTITY_STATUS = "NO-GO"               # 공식 성분 동일성 검증 판정 — 이 모듈은 바꾸지 않음
CLINICAL_VALIDATION_STATUS = "NOT_VALIDATED"
FORBIDDEN_WORDS = ["SAFE", "LOW_RISK", "NO_RISK", "안전합니다", "위험도 점수", "risk_score"]
DUR_AD = None                                    # integrated_screen 기본값(UI는 항상 engine의 어댑터를 명시 전달)
ING_AD = None


def J(o):
    if isinstance(o, np.integer): return int(o)
    if isinstance(o, np.floating): return float(o)
    if isinstance(o, (set, tuple)): return list(o)
    if isinstance(o, Path): return str(o)
    return str(o)


def quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): out = fn(*a, **k)
    return out, buf.getvalue()


def sha256_file(p, chunk=1 << 24):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""): h.update(b)
    return h.hexdigest()



# ===== [16:CELL 1] 파일 탐색 함수(문자 그대로) =====
PRUNE = {"data", "raw", ".git", "__pycache__", "node_modules", ".ipynb_checkpoints"}
def walk_find(base, names, maxdepth):
    found = defaultdict(list); base = Path(base)
    if not base.exists(): return found
    bd = len(base.parts)
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d not in PRUNE]
        if len(Path(dp).parts) - bd >= maxdepth: dn[:] = []
        for n in names:
            if n in fn: found[n].append(Path(dp) / n)
    return found

# ===== [16:CELL 5] 16번 노트북에서 문자 그대로 추출 =====
def _E(code_, detail=""): return {"code": code_, "detail": detail}
def validate_request(req, dur_mod):
    out = {"ok": False, "errors": [], "warnings": [], "normalized": [], "duplicate_inputs": [], "invalid_inputs": [], "age": None, "age_status": "MISSING"}
    if not isinstance(req, dict):
        out["errors"].append(_E("INPUT_NOT_OBJECT", type(req).__name__)); return out
    if "item_seqs" not in req:
        out["errors"].append(_E("MISSING_ITEM_SEQS")); return out
    seqs = req["item_seqs"]
    if not isinstance(seqs, (list, tuple)):
        out["errors"].append(_E("INVALID_TYPE_ITEM_SEQS", "list/tuple 이어야 함, 받은 값: " + type(seqs).__name__))
    else:
        seen = set()
        for v in seqs:
            s = dur_mod.normalize_identifier(v)
            if s is None or not re.fullmatch(r"\d{9}", s):
                out["invalid_inputs"].append(repr(v)); out["errors"].append(_E("INVALID_ITEM_SEQ_VALUE", repr(v))); continue
            if s in seen:
                out["duplicate_inputs"].append(s); continue
            seen.add(s); out["normalized"].append(s)
        if out["duplicate_inputs"]:
            out["warnings"].append(_E("DUPLICATE_ITEM_SEQ_REMOVED", sorted(set(out["duplicate_inputs"]))))
        if not out["errors"]:
            if len(out["normalized"]) == 0: out["errors"].append(_E("EMPTY_ITEM_SEQS"))
            elif len(out["normalized"]) > MAX_ITEMS: out["errors"].append(_E("TOO_MANY_ITEMS", "%d개 > 최대 %d개(잘라내지 않음)" % (len(out["normalized"]), MAX_ITEMS)))
    age = req.get("patient_age")
    if age is None:
        out["warnings"].append(_E("PATIENT_AGE_MISSING", "노인주의는 평가하지 않음(임의 확정 안 함)"))
    else:
        try:
            out["age"] = dur_mod.validate_age(age); out["age_status"] = "PROVIDED"
        except (TypeError, ValueError) as e:
            out["errors"].append(_E("INVALID_PATIENT_AGE", str(e)))
    out["ok"] = not out["errors"]
    return out

# ===== [16:CELL 6] 16번 노트북에서 문자 그대로 추출 =====
class DurAdapter:
    def __init__(self, mod, data_files):
        self.m = mod; self.data_files = data_files
        self.normalize_identifier = mod.normalize_identifier; self.validate_age = mod.validate_age
    def known(self, seq): return seq in self.m.KNOWN_DUR_ITEMS
    def name(self, seq):
        f = getattr(self.m, "get_drug_name", None); return f(seq) if f else None
    def raw(self, seqs, age):                    # 엔진 단독 호출(일관성 비교에도 사용)
        return self.m.screen_patient(list(seqs), age=age, include_evidence=True)
    def run(self, seqs, age):
        raw = self.raw(seqs, age); eng = raw["engine"]
        src = lambda rs: {"rule_source": rs, "engine": eng["name"], "engine_version": eng["version"], "method": eng["method"], "data_files": self.data_files, "official_source_url": None}
        contra, eld, ther = [], [], []
        for r in raw["contraindications"]:
            ok = bool(r.get("has_evidence"))
            contra.append({"rule_type": "CONTRAINDICATION", "matched": True, "rule_id": r["canonical_pair_id"], "involved_item_seqs": [r["drug_1_item_seq"], r["drug_2_item_seq"]],
                           "involved_item_names": [r.get("drug_1_item_name"), r.get("drug_2_item_name")], "involved_ingredients": [],
                           "official_evidence": {"has_evidence": ok, "evidence_count": r.get("evidence_count", 0), "evidence_ids": r.get("evidence_ids", []), "dur_seqs": r.get("evidence_dur_seqs", []), "texts": r.get("prohbt_contents", [])},
                           "source": src(r["rule_source"]), "screening_status": "MATCHED" if ok else "MATCHED_EVIDENCE_TEXT_MISSING"})
        for r in raw["elderly_cautions"]:
            ok = bool(r.get("has_prohbt_content"))
            eld.append({"rule_type": "ELDERLY_CAUTION", "matched": True, "rule_id": None, "rule_id_note": "엔진이 규칙 ID를 제공하지 않음(임의 생성 안 함)",
                        "involved_item_seqs": [r["item_seq"]], "involved_item_names": [r.get("item_name")],
                        "involved_ingredients": [{"dur_ingr_codes": r.get("ingr_codes", []), "ingredient_names": r.get("ingredient_names", [])}],
                        "official_evidence": {"has_evidence": ok, "texts": [r["prohbt_content"]] if r.get("prohbt_content") else [], "age_threshold": r.get("age_threshold"), "patient_age": r.get("patient_age")},
                        "source": src(r["rule_source"]), "screening_status": "MATCHED" if ok else "MATCHED_EVIDENCE_TEXT_MISSING"})
        for r in raw["therapeutic_duplications"]:
            ok = bool(r.get("has_prohbt_content"))
            ther.append({"rule_type": "THERAPEUTIC_DUPLICATION", "matched": True, "rule_id": None, "rule_id_note": "엔진이 규칙 ID를 제공하지 않음(임의 생성 안 함)", "rule_key": {"effect_name": r["effect_name"]},
                         "involved_item_seqs": list(r["matched_item_seqs"]), "involved_item_names": [i.get("item_name") for i in r.get("matched_items", [])],
                         "involved_ingredients": [{"dur_ingr_codes": i.get("ingr_codes", []), "ingredient_names": i.get("ingredient_names", [])} for i in r.get("matched_items", [])],
                         "official_evidence": {"has_evidence": ok, "texts": r.get("prohbt_contents", []), "distinct_dur_ingr_code_count": r.get("distinct_ingr_code_count")},
                         "source": src(r["rule_source"]), "screening_status": "MATCHED" if ok else "MATCHED_EVIDENCE_TEXT_MISSING"})
        nf = list(raw["patient"].get("not_found_in_dur_tables", []))
        n = len(contra) + len(eld) + len(ther)
        status = "MATCHED" if n else ("PARTIAL_COVERAGE_NO_MATCH" if nf else "NO_MATCH_FOUND")
        return {"status": status, "elderly_check_status": raw["summary"]["elderly_check_status"], "contraindications": contra, "elderly_cautions": eld, "therapeutic_duplicates": ther,
                "not_found_in_dur_tables": nf, "engine": dict(eng), "scope_note": raw.get("scope_note")}, raw

# ===== [16:CELL 7] 16번 노트북에서 문자 그대로 추출 =====
TYPE_BY_CLASS = {"SAME_MCODE_SAME_NAME": "TYPE_A", "SAME_NAME_DIFF_MCODE": "TYPE_B", "SAME_MCODE_DIFF_NAME": "TYPE_C"}
LIMITS_COMMON = ["동일 M코드/동일 성분명만으로 약학적 동일성·임상 위험을 확정하지 않음", "공식 성분 동일성 검증 NO-GO 유지(검증 상태: UNVERIFIED_CANDIDATE)", "염·수화물·에스터·입체 접두어를 제거해 합치지 않음"]
class IngredientAdapter:
    def __init__(self, ns, label="REAL"):
        self.ns = ns; self.label = label; P = ns["P"]
        self.prow = {r.item_seq: r for r in P.itertuples()}
    def has(self, seq): return seq in self.prow
    def name(self, seq): return self.prow[seq].item_name if seq in self.prow else None
    def info_status(self, seq):
        r = self.prow.get(seq)
        if r is None: return "NOT_IN_APPROVAL_DATA"
        if r.n_ing == 0: return "NO_INGREDIENT_INFO"
        if r.unscreenable: return "ALL_INGREDIENTS_UNCLEAR"
        return "SCREENABLE" if r.screenable else "PARTIAL_UNCLEAR"
    def raw_pairs(self, seqs):                   # 15번 단독 호출(일관성 비교에도 사용)
        s = [x for x in seqs if self.has(x)]; return self.ns["screen_list"](s)
    def run(self, seqs):
        ns = self.ns; s_in = [x for x in seqs if self.has(x)]
        cands, unresolved, pair_results = [], [], []
        for res in self.ns["screen_list"](s_in):
            a, b = res["item_seq_a"], res["item_seq_b"]; types_ = set()
            if res["status"].startswith("UNSCREENABLE"):
                types_.add("TYPE_F")
            else:
                for c in res["candidates"]:
                    t = TYPE_BY_CLASS[c["pair_class"]]; types_.add(t)
                    cands.append({"candidate_type": t, "candidate": True, "pair_class": c["pair_class"], "involved_item_seqs": [c["a_item_seq"], c["b_item_seq"]],
                                  "item_names": [c["a_item_name"], c["b_item_name"]], "original_ingredient_names": [c["a_name_raw"], c["b_name_raw"]],
                                  "normalized_ingredient_names": [c["a_name_norm"], c["b_name_norm"]], "original_m_codes": [c["a_m_code"], c["b_m_code"]],
                                  "detection_reason": c["reason"], "evidence_source": {"a": c["a_source"], "b": c["b_source"], "rule": "15:screen_pair/" + c["pair_class"], "source_file": ns["SRC"].name},
                                  "verification_status": c["verification_status"], "form_markers": [c["a_form_markers"], c["b_form_markers"]], "high_frequency": c["high_frequency"],
                                  "limitations": LIMITS_COMMON + (["고빈도 성분 단위(제품 다수 공유) — 단순 표시일 뿐 제외하지 않음"] if c["high_frequency"] else [])})
                for h in res["hints"]:
                    types_.add("TYPE_D")
                    cands.append({"candidate_type": "TYPE_D", "candidate": False, "pair_class": "FORM_VARIANT_HINT", "involved_item_seqs": [h["a_item_seq"], h["b_item_seq"]],
                                  "item_names": [ns["P_ROW"][ns["PI_BY_SEQ"][h["a_item_seq"]]].item_name, ns["P_ROW"][ns["PI_BY_SEQ"][h["b_item_seq"]]].item_name],
                                  "original_ingredient_names": [h["a_name_norm"], h["b_name_norm"]], "normalized_ingredient_names": [h["a_name_norm"], h["b_name_norm"]],
                                  "original_m_codes": [h["a_m_code"], h["b_m_code"]], "detection_reason": h["reason"],
                                  "evidence_source": {"a": ns["source_str"](ns["PI_BY_SEQ"][h["a_item_seq"]]), "b": ns["source_str"](ns["PI_BY_SEQ"][h["b_item_seq"]]), "rule": "15:screen_pair/form_variant_hint", "source_file": ns["SRC"].name},
                                  "verification_status": h["verification_status"], "form_markers": [], "high_frequency": False,
                                  "limitations": ["형태 차이 검토 힌트일 뿐 후보가 아님(이름이 다르므로 합치지 않음)"] + LIMITS_COMMON})
                if not res["candidates"] and not res["hints"]: types_.add("TYPE_E")
            pair_results.append({"pair": [a, b], "types": sorted(types_), "ingredient_pair_status": res["status"]})
        # 불명확 성분 · 정보 없음 · 허가정보에 없는 제품
        for x in seqs:
            if not self.has(x):
                unresolved.append({"item_seq": x, "type": "TYPE_F", "reason": "NOT_IN_APPROVAL_DATA", "detail": "제품 허가정보(drug_approval_items)에 없음"}); continue
            pi = ns["PI_BY_SEQ"][x]; st = self.info_status(x)
            if st in ("NO_INGREDIENT_INFO",):
                unresolved.append({"item_seq": x, "item_name": self.name(x), "type": "TYPE_F", "reason": "NO_INGREDIENT_INFO", "detail": "MAIN_ITEM_INGR 없음/파싱 불가"})
            for mc, nm, why in ns["_unclear"](pi):
                unresolved.append({"item_seq": x, "item_name": self.name(x), "type": "TYPE_D", "reason": why, "m_code": mc, "ingredient_name_raw": nm, "detail": "15번 규칙상 D(불명확) — 후보 계산에서 제외됨"})
        # TYPE_C(검토 전용): 서로 다른 입력 제품에 같은 M코드가 서로 다른 성분명으로 존재(15번은 D로 제외)
        by_code = defaultdict(set)
        for u in unresolved:
            if u["type"] == "TYPE_D" and "CODE_MAPS_TO_MULTIPLE_NAMES" in u["reason"]: by_code[u["m_code"]].add((u["item_seq"], u["ingredient_name_raw"]))
        for mc, items in sorted(by_code.items()):
            seqs_ = sorted({i[0] for i in items}); names = sorted({ns["norm"](i[1]) for i in items})
            if len(seqs_) >= 2 and len(names) >= 2:
                cands.append({"candidate_type": "TYPE_C", "candidate": False, "pair_class": "SAME_MCODE_DIFF_NAME_REVIEW_ONLY", "involved_item_seqs": seqs_,
                              "item_names": [self.name(x) for x in seqs_], "original_ingredient_names": [i[1] for i in sorted(items)], "normalized_ingredient_names": names,
                              "original_m_codes": [mc], "detection_reason": "동일 M코드(%s)에 서로 다른 성분명 — 15번 규칙상 D(불명확)로 후보 제외, 사람 검토용" % mc,
                              "evidence_source": {"a": ns["source_str"](ns["PI_BY_SEQ"][seqs_[0]]), "b": ns["source_str"](ns["PI_BY_SEQ"][seqs_[1]]), "rule": "16:adapter/code_name_conflict_review", "source_file": ns["SRC"].name},
                              "verification_status": "NOT_A_CANDIDATE", "form_markers": [], "high_frequency": False, "limitations": ["M코드-성분명 불일치 데이터 이상 가능성 — 후보 아님"] + LIMITS_COMMON})
        n_cand = sum(1 for c in cands if c["candidate"])
        gaps = bool(unresolved) or any("TYPE_F" in p["types"] for p in pair_results) or any(c["candidate_type"] in ("TYPE_D", "TYPE_C") for c in cands)
        if len(s_in) < 2: status = "NOT_APPLICABLE_SINGLE_PRODUCT" if len(seqs) <= 1 else "NOT_EVALUATED_INSUFFICIENT_DATA"
        elif n_cand: status = "CANDIDATES_FOUND"
        else: status = "NO_CANDIDATE_FOUND_PARTIAL" if gaps else "NO_CANDIDATE_FOUND"
        return {"status": status, "duplicate_candidates": cands, "unresolved_ingredients": unresolved, "pair_results": pair_results, "has_gaps": gaps,
                "rule_origin": "15번 screen_pair()/screen_list() 재사용 + 16번 라벨링", "verification_status_policy": "모든 후보는 UNVERIFIED_CANDIDATE (공식 동일성 검증 NO-GO 유지)"}

# ===== [16:CELL 8] 16번 노트북에서 문자 그대로 추출 =====
import copy
ST_OVERALL = ["REVIEW_REQUIRED", "PARTIAL", "NO_MATCH_FOUND", "BLOCKED"]
SCHEMA = {"$schema": "http://json-schema.org/draft-07/schema#", "type": "object",
 "required": ["request_id", "input", "input_validation", "product_resolution", "dur_screening", "ingredient_screening", "evidence", "limitations", "overall_status", "meta"],
 "properties": {
  "request_id": {"type": "string"},
  "input": {"type": "object", "required": ["item_seqs", "patient_age"], "properties": {"item_seqs": {"type": "array", "items": {"type": "string"}}, "patient_age": {"type": ["number", "null"]}}},
  "input_validation": {"type": "object", "required": ["ok", "errors", "warnings"], "properties": {"ok": {"type": "boolean"}, "errors": {"type": "array"}, "warnings": {"type": "array"}}},
  "product_resolution": {"type": "object", "required": ["status", "resolved_products", "unresolved_products"],
    "properties": {"status": {"enum": ["ALL_RESOLVED", "PARTIAL", "NONE_RESOLVED", "INVALID_INPUT"]}, "resolved_products": {"type": "array"}, "unresolved_products": {"type": "array"}}},
  "dur_screening": {"type": "object", "required": ["status", "contraindications", "elderly_cautions", "therapeutic_duplicates"],
    "properties": {"status": {"enum": ["MATCHED", "NO_MATCH_FOUND", "PARTIAL_COVERAGE_NO_MATCH", "NOT_EVALUATED"]}, "contraindications": {"type": "array"}, "elderly_cautions": {"type": "array"}, "therapeutic_duplicates": {"type": "array"}}},
  "ingredient_screening": {"type": "object", "required": ["status", "duplicate_candidates", "unresolved_ingredients"],
    "properties": {"status": {"enum": ["CANDIDATES_FOUND", "NO_CANDIDATE_FOUND", "NO_CANDIDATE_FOUND_PARTIAL", "NOT_APPLICABLE_SINGLE_PRODUCT", "NOT_EVALUATED_INSUFFICIENT_DATA", "NOT_EVALUATED"]},
      "duplicate_candidates": {"type": "array", "items": {"type": "object", "required": ["candidate_type", "candidate", "involved_item_seqs", "item_names", "original_ingredient_names", "normalized_ingredient_names", "original_m_codes", "detection_reason", "evidence_source", "verification_status", "limitations"],
         "properties": {"candidate_type": {"enum": ["TYPE_A", "TYPE_B", "TYPE_C", "TYPE_D"]}, "candidate": {"type": "boolean"}, "verification_status": {"enum": ["UNVERIFIED_CANDIDATE", "NOT_A_CANDIDATE"]}}}},
      "unresolved_ingredients": {"type": "array"}}},
  "evidence": {"type": "array", "items": {"type": "object", "required": ["evidence_id", "kind", "source"]}},
  "limitations": {"type": "array", "items": {"type": "string"}, "minItems": 1},
  "overall_status": {"enum": ST_OVERALL},
  "meta": {"type": "object", "required": ["official_identity_verification_status", "clinical_validation_status"], "properties": {"official_identity_verification_status": {"const": "NO-GO"}, "clinical_validation_status": {"const": "NOT_VALIDATED"}}}}}
def _mini(obj, sch, path="$"):
    errs = []
    if "enum" in sch and obj not in sch["enum"]: errs.append("%s: enum 위반 %r" % (path, obj))
    if "const" in sch and obj != sch["const"]: errs.append("%s: const 위반 %r" % (path, obj))
    t = sch.get("type")
    if t:
        ts = t if isinstance(t, list) else [t]; tm = {"object": dict, "array": list, "string": str, "boolean": bool, "number": (int, float), "null": type(None)}
        if not any(isinstance(obj, tm[x]) and not (x == "number" and isinstance(obj, bool)) for x in ts): errs.append("%s: 타입 위반 %s" % (path, type(obj).__name__)); return errs
    if isinstance(obj, dict):
        for k in sch.get("required", []):
            if k not in obj: errs.append("%s: 필수 키 없음 %s" % (path, k))
        for k, s2 in sch.get("properties", {}).items():
            if k in obj: errs += _mini(obj[k], s2, path + "." + k)
    if isinstance(obj, list):
        if "minItems" in sch and len(obj) < sch["minItems"]: errs.append("%s: minItems" % path)
        if "items" in sch:
            for i, x in enumerate(obj): errs += _mini(x, sch["items"], "%s[%d]" % (path, i))
    return errs
try:
    import jsonschema; _VALIDATOR = "jsonschema"
except Exception:
    jsonschema = None; _VALIDATOR = "mini(내장 간이 검증기)"
def validate_schema(obj):
    if jsonschema is not None:
        v = jsonschema.Draft7Validator(SCHEMA); return ["%s: %s" % (".".join(map(str, e.absolute_path)) or "$", e.message[:120]) for e in v.iter_errors(obj)]
    return _mini(obj, SCHEMA)
def compute_overall(input_ok, resolved_n, dur_matched_n, ing_cand_n, gaps):
    if (not input_ok) or resolved_n == 0: return "BLOCKED"
    if dur_matched_n or ing_cand_n: return "REVIEW_REQUIRED"
    return "PARTIAL" if gaps else "NO_MATCH_FOUND"
_SKIP_KEYS = {"official_evidence", "involved_item_names", "involved_ingredients", "item_names", "original_ingredient_names", "normalized_ingredient_names", "evidence_source", "source",
              "item_name", "ingredient_name_raw", "texts", "form_markers", "scope_note", "invalid_inputs", "original_m_codes"}
def _scrub(o):
    if isinstance(o, dict): return {k: _scrub(v) for k, v in o.items() if k not in _SKIP_KEYS}
    if isinstance(o, list): return [_scrub(x) for x in o]
    return o
def semantic_check(obj):
    errs = []; txt = json.dumps(_scrub(obj), ensure_ascii=False, default=J)   # 공식 텍스트·제품명은 제외하고 이 모듈이 만든 필드만 검사
    for w in FORBIDDEN_WORDS:
        if re.search(r"(?<![A-Za-z_])" + re.escape(w) + r"(?![A-Za-z_])", txt): errs.append("금지 표현: " + w)
    if re.search(r"(?<![A-Za-z])VERIFIED(?![A-Za-z])", txt): errs.append("VERIFIED 표기 금지")
    ing, dur = obj["ingredient_screening"], obj["dur_screening"]
    for c in ing["duplicate_candidates"]:
        if c["candidate"] and c["verification_status"] != "UNVERIFIED_CANDIDATE": errs.append("후보 검증 상태 오류")
        if not c["candidate"] and c["verification_status"] != "NOT_A_CANDIDATE": errs.append("비후보 상태 오류")
    for k in ("contraindications", "elderly_cautions", "therapeutic_duplicates"):
        for r in dur[k]:
            if r.get("rule_type") not in ("CONTRAINDICATION", "ELDERLY_CAUTION", "THERAPEUTIC_DUPLICATION"): errs.append("DUR 영역에 비DUR 항목: %s" % r.get("rule_type"))
    dm = len(dur["contraindications"]) + len(dur["elderly_cautions"]) + len(dur["therapeutic_duplicates"])
    ic = sum(1 for c in ing["duplicate_candidates"] if c["candidate"])
    exp = compute_overall(obj["input_validation"]["ok"], len(obj["product_resolution"]["resolved_products"]), dm, ic, obj["meta"].get("gaps", []))
    if exp != obj["overall_status"]: errs.append("overall_status 재계산 불일치: %s != %s" % (exp, obj["overall_status"]))
    return errs

# ===== [16:CELL 9] 16번 노트북에서 문자 그대로 추출 =====
def build_evidence(dur_part, ing_part, ing_ad, dur_ad):
    ev = []
    def add(kind, item, **kw):
        eid = "EV-%03d" % (len(ev) + 1); item["evidence_id"] = eid
        ev.append({"evidence_id": eid, "kind": kind, "is_official_dur_rule": kind == "OFFICIAL_DUR_RULE_MATCH", "is_official_identity_verification": False,
                   "is_rag_or_llm_generated": False, "official_source_url": None, **kw}); return eid
    for k in ("contraindications", "elderly_cautions", "therapeutic_duplicates"):
        for r in dur_part[k]:
            add("OFFICIAL_DUR_RULE_MATCH", r, rule_type=r["rule_type"], rule_id=r["rule_id"], involved_item_seqs=r["involved_item_seqs"], involved_ingredients=r["involved_ingredients"],
                source=r["source"], evidence_ids_from_engine=r["official_evidence"].get("evidence_ids", []), data_collection_date="NOT_AVAILABLE_IN_ENGINE_OUTPUT")
    for c in ing_part["duplicate_candidates"]:
        add("INGREDIENT_CANDIDATE_RULE" if c["candidate"] else "INGREDIENT_REVIEW_HINT_NOT_A_CANDIDATE", c, candidate_type=c["candidate_type"], involved_item_seqs=c["involved_item_seqs"],
            original_ingredient_names=c["original_ingredient_names"], normalized_ingredient_names=c["normalized_ingredient_names"], original_m_codes=c["original_m_codes"],
            rule=c["evidence_source"]["rule"], source={"file": c["evidence_source"]["source_file"], "a": c["evidence_source"]["a"], "b": c["evidence_source"]["b"]},
            data_collection_date=("; ".join(re.findall(r"retrieved=([^|]+)", c["evidence_source"]["a"] + "|" + c["evidence_source"]["b"])) or "N/A"), verification_status=c["verification_status"])
    return ev
def evidence_audit(results):
    miss = []
    for r in results:
        ids = {e["evidence_id"] for e in r["evidence"]}
        items = [x for k in ("contraindications", "elderly_cautions", "therapeutic_duplicates") for x in r["dur_screening"][k]] + r["ingredient_screening"]["duplicate_candidates"]
        for x in items:
            if x.get("evidence_id") not in ids: miss.append((r["request_id"], "evidence_id 없음"))
        for e in r["evidence"]:
            if e.get("official_source_url") is not None: miss.append((r["request_id"], "URL 임의 생성"))
            if e["kind"].startswith("INGREDIENT") and e.get("verification_status") == "VERIFIED": miss.append((r["request_id"], "VERIFIED"))
    return miss

# ===== [16:CELL 10] 16번 노트북에서 문자 그대로 추출 =====
STD_LIMITS = ["이 결과는 임상적 안전성 판단이 아닙니다. overall_status는 시스템 탐지 범위 안의 처리 상태일 뿐 위험도가 아닙니다.",
              "DUR Screening(공식 DUR 규칙 매칭)과 Ingredient Screening(성분 중복 후보)은 서로 다른 판단 체계이며 합산·점수화하지 않았습니다.",
              "성분 중복 후보는 공식 DUR 병용금기가 아니며 약학적 동일성·임상 위험을 확정하지 않습니다(전 후보 UNVERIFIED_CANDIDATE).",
              "공식 성분 동일성 검증은 NO-GO 상태로 유지됩니다(임상 검증 상태: NOT_VALIDATED).",
              "DUR D코드와 제품 허가정보 M코드 사이에 공식 매핑이 없으며 이 모듈은 둘을 연결하지 않습니다(Coverage Audit 한계 유지).",
              "DUR 규칙에 매칭되지 않았다는 사실이 안전하다는 뜻은 아닙니다. 매칭 없음은 현재 데이터·규칙 범위에서 찾지 못했다는 뜻입니다.",
              "RAG/LLM은 사용하지 않았으며 이 결과에 생성 설명이 포함되어 있지 않습니다."]
def integrated_screen(request, dur_ad=None, ing_ad=None):
    dur_ad = dur_ad or DUR_AD; ing_ad = ing_ad or ING_AD
    v = validate_request(request, dur_ad.m)
    rid = "REQ-" + hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True, default=J).encode()).hexdigest()[:12]
    meta = {"official_identity_verification_status": OFFICIAL_IDENTITY_STATUS, "clinical_validation_status": CLINICAL_VALIDATION_STATUS, "no_combined_risk_score": True,
            "ingredient_engine": "15번 screen_pair/screen_list 재사용", "dur_engine": "dur_safety/screening.py 재사용", "ingredient_data_origin": ing_ad.label, "gaps": []}
    base = {"request_id": rid, "input": {"item_seqs": list(v["normalized"]), "patient_age": v["age"]}, "input_validation": {"ok": v["ok"], "errors": v["errors"], "warnings": v["warnings"], "duplicate_inputs": sorted(set(v["duplicate_inputs"])), "invalid_inputs": v["invalid_inputs"]},
            "evidence": [], "limitations": list(STD_LIMITS), "meta": meta}
    if not v["ok"]:
        return {**base, "product_resolution": {"status": "INVALID_INPUT", "resolved_products": [], "unresolved_products": []},
                "dur_screening": {"status": "NOT_EVALUATED", "contraindications": [], "elderly_cautions": [], "therapeutic_duplicates": []},
                "ingredient_screening": {"status": "NOT_EVALUATED", "duplicate_candidates": [], "unresolved_ingredients": []},
                "overall_status": "BLOCKED", "limitations": base["limitations"] + ["입력 오류로 스크리닝을 수행하지 않았습니다(안전한 조합으로 해석하지 마세요): " + ", ".join(e["code"] for e in v["errors"])]}
    seqs = v["normalized"]; resolved, unresolved = [], []
    for s in seqs:
        in_a, in_d = ing_ad.has(s), dur_ad.known(s)
        if in_a or in_d:
            resolved.append({"item_seq": s, "item_name": ing_ad.name(s) or dur_ad.name(s), "in_approval_data": in_a, "in_dur_tables": in_d, "ingredient_info_status": ing_ad.info_status(s)})
        else:
            unresolved.append({"item_seq": s, "reason": "NOT_FOUND_IN_APPROVAL_DATA_AND_DUR_TABLES", "detail": "제품을 찾지 못함 — 안전한 의약품으로 판정하지 않음"})
    pr_status = "NONE_RESOLVED" if not resolved else ("ALL_RESOLVED" if not unresolved else "PARTIAL")
    if not resolved:
        return {**base, "product_resolution": {"status": pr_status, "resolved_products": [], "unresolved_products": unresolved},
                "dur_screening": {"status": "NOT_EVALUATED", "contraindications": [], "elderly_cautions": [], "therapeutic_duplicates": []},
                "ingredient_screening": {"status": "NOT_EVALUATED", "duplicate_candidates": [], "unresolved_ingredients": []},
                "overall_status": "BLOCKED", "limitations": base["limitations"] + ["식별된 제품이 없어 스크리닝을 수행하지 않았습니다(미식별 제품을 안전하다고 판정하지 않음)."]}
    dur_part, _raw = dur_ad.run(seqs, v["age"]); ing_part = ing_ad.run(seqs)
    ev = build_evidence(dur_part, ing_part, ing_ad, dur_ad)
    gaps = []
    if v["age_status"] == "MISSING": gaps.append("AGE_MISSING_ELDERLY_NOT_EVALUATED")
    if unresolved: gaps.append("UNRESOLVED_PRODUCT")
    if dur_part["not_found_in_dur_tables"]: gaps.append("PRODUCT_NOT_IN_DUR_TABLES")
    if len(resolved) < 2: gaps.append("SINGLE_PRODUCT_NO_PAIR_SCREENING")
    if ing_part["has_gaps"]: gaps.append("INGREDIENT_UNRESOLVED_OR_HOLD_OR_REVIEW_HINT")
    if any(not r["in_approval_data"] for r in resolved): gaps.append("PRODUCT_NOT_IN_APPROVAL_DATA_INGREDIENT_NOT_EVALUATED")
    dm = len(dur_part["contraindications"]) + len(dur_part["elderly_cautions"]) + len(dur_part["therapeutic_duplicates"])
    ic = sum(1 for c in ing_part["duplicate_candidates"] if c["candidate"])
    meta["gaps"] = gaps
    overall = compute_overall(True, len(resolved), dm, ic, gaps)
    lim = list(base["limitations"])
    if gaps: lim.append("미평가/불완전 범위: " + ", ".join(gaps))
    if any(x["screening_status"] == "MATCHED_EVIDENCE_TEXT_MISSING" for k in ("contraindications", "elderly_cautions", "therapeutic_duplicates") for x in dur_part[k]):
        lim.append("일부 DUR 매칭에 엔진이 제공한 근거 텍스트가 없어 추가 확인이 필요합니다(정상으로 변환하지 않음).")
    return {**base, "product_resolution": {"status": pr_status, "resolved_products": resolved, "unresolved_products": unresolved},
            "dur_screening": dur_part, "ingredient_screening": {k: v_ for k, v_ in ing_part.items() if k != "has_gaps"}, "evidence": ev, "limitations": lim, "overall_status": overall, "meta": meta}
def check_result(r):
    return validate_schema(r) + semantic_check(r) + [m[1] for m in evidence_audit([r])]


# ===== [16:CELL 4] build_nb15 (문자 그대로) =====
def build_nb15(src_path, tag):
    ns = {"os": os, "re": re, "json": json, "time": time, "hashlib": hashlib, "unicodedata": unicodedata, "random": random, "platform": platform, "shutil": shutil,
          "Path": Path, "Counter": Counter, "defaultdict": defaultdict, "np": np, "pd": pd, "J": J, "SRC": Path(src_path), **NB15_CONST, "RUN15": {}}
    ns["record"] = lambda c, s, d="": ns["RUN15"].__setitem__(c, {"status": s, "detail": d})
    def _need(*cs):
        bad = [c for c in cs if ns["RUN15"].get(c, {}).get("status") not in ("PASS", "WARN")]
        if bad: raise RuntimeError("15번 셀 선행 조건 미충족: %s" % bad)
    ns["need"] = _need; ns["show"] = lambda df, n=20: None
    ns["RUN15"]["CELL 0"] = {"status": "PASS", "detail": "16번에서 대체(실행 폴더/스냅샷 생략)"}
    logs = {}
    for k in (1, 2, 3, 4):
        _, logs[k] = quiet(exec, compile(NB15_CELLS[k], "nb15_cell%d[%s]" % (k, tag), "exec"), ns)
        if ns["RUN15"].get("CELL %d" % k, {}).get("status") not in ("PASS", "WARN"):
            raise RuntimeError("BLOCKED: 15번 CELL %d 실행 결과 %s" % (k, ns["RUN15"].get("CELL %d" % k)))
    return ns, logs


# ===== [17:glue] 프로젝트 파일 로딩 (읽기 전용) =====
NB15_CELLS = {}
NB15_CONST = {}


def _prepare_nb15(nb15_path):
    """15번 노트북의 CELL 1~4 코드 셀과 상수를 읽는다(16번 CELL 4와 동일한 방식)."""
    _nb = json.loads(Path(nb15_path).read_text(encoding="utf-8"))
    _codes = ["".join(c["source"]) for c in _nb["cells"] if c.get("cell_type") == "code"]
    def _cell15(k):
        hit = [s for s in _codes if ('record("CELL %d"' % k) in s]
        if len(hit) != 1: raise RuntimeError("BLOCKED: 15번 노트북에서 CELL %d 코드 셀을 정확히 1개 찾지 못함(%d개)" % (k, len(hit)))
        return hit[0]
    NB15_CELLS = {k: _cell15(k) for k in (0, 1, 2, 3, 4)}
    NB15_CELL_SHA = {k: hashlib.sha256(v.encode()).hexdigest()[:16] for k, v in NB15_CELLS.items()}
    _const_lines = [ln for ln in NB15_CELLS[0].splitlines() if re.match(r"^(SEED|HF_THRESHOLD|N_BATCH|OFFICIAL_IDENTITY_STATUS|CAND_STATUS|CAND_NOTE)\s*=", ln)]
    NB15_CONST = {}
    exec("\n".join(_const_lines), {}, NB15_CONST)
    return NB15_CELLS, NB15_CONST


class IntegrationEngine:
    """로딩 결과 묶음. ready=False 이면 이유(error_user/error_dev)가 들어 있고 화면은 크래시 없이 안내만 한다."""
    def __init__(self):
        self.ready = False; self.dur_ok = False; self.ing_ok = False
        self.dur_ad = None; self.ing_ad = None
        self.error_user = None; self.error_dev = None; self.info = {}


def locate_files(root, nb15_path=None, screening_path=None):
    root = Path(root)
    NAMES = ["screening.py", "15_ingredient_duplicate_candidates_prototype.ipynb"]
    found = {}
    if screening_path: found["screening.py"] = Path(screening_path)
    elif (root / "src/dur_safety/screening.py").exists(): found["screening.py"] = root / "src/dur_safety/screening.py"
    nb = nb15_path or os.environ.get("MEDGUARD_NB15_PATH")
    if nb: found["15_ingredient_duplicate_candidates_prototype.ipynb"] = Path(nb)
    miss = [n for n in NAMES if n not in found]
    if miss:
        F = walk_find(root, miss, 7)
        still = [n for n in miss if not F.get(n)]
        if still:
            F2 = walk_find(root.parent, still, 3)
            for n in still: F[n] = F2.get(n, [])
        for n in miss:
            c = sorted(set(F.get(n, [])))
            if len(c) == 1: found[n] = c[0]
            elif len(c) > 1 and len({sha256_file(p) for p in c}) == 1: found[n] = c[0]
            elif len(c) > 1: raise RuntimeError("AMBIGUOUS_FILE: %s %s" % (n, [str(p) for p in c]))
    return found


def load_engine(project_root=None, nb15_path=None, screening_path=None):
    """DUR(screening.py)와 15번 성분 후보 코드를 읽기 전용으로 불러 어댑터를 만든다. 예외를 밖으로 던지지 않는다."""
    eng = IntegrationEngine()
    stage = "init"
    try:
        sys.dont_write_bytecode = True
        root = Path(project_root or os.environ.get("MEDICAL_AI_PROJECT_ROOT") or os.environ.get("MEDGUARD_ROOT") or str(Path(__file__).resolve().parents[1]))
        SRC = root / "data/processed/evidence/drug_approval_items.parquet"
        SCR_DIR = root / "data/processed/screening"
        DUR_TABLES = {n: SCR_DIR / (n + ".parquet") for n in ["contraindication_pairs", "contraindication_evidence", "elderly_caution_rules", "therapeutic_group_mapping"]}
        stage = "locate_files"
        miss = [str(p) for p in [SRC, *DUR_TABLES.values()] if not p.exists()]
        if miss: raise FileNotFoundError("필수 데이터 파일 없음: %s" % miss)
        FOUND = locate_files(root, nb15_path, screening_path)
        eng.info = {"project_root": str(root), "approval_parquet": str(SRC), "screening_py": str(FOUND.get("screening.py")), "nb15": str(FOUND.get("15_ingredient_duplicate_candidates_prototype.ipynb"))}
        # ---- DUR (16번 CELL 3와 동일한 방식: 파일을 쓰지 않고 메모리에서 exec) ----
        stage = "dur_load"
        SCREENING_PATH = FOUND["screening.py"]
        _src_bytes = Path(SCREENING_PATH).read_bytes()
        DUR = types.ModuleType("dur_safety_screening_readonly"); DUR.__file__ = str(SCREENING_PATH)
        exec(compile(_src_bytes.decode("utf-8"), str(SCREENING_PATH), "exec"), DUR.__dict__)
        need_fn = ["init_screening", "screen_patient", "normalize_medication_list", "normalize_identifier", "validate_age", "check_contraindications", "check_elderly_caution", "check_therapeutic_duplication"]
        miss_fn = [f for f in need_fn if not hasattr(DUR, f)]
        if miss_fn: raise RuntimeError("BLOCKED: DUR 함수 없음 %s" % miss_fn)
        if list(inspect.signature(DUR.screen_patient).parameters)[:3] != ["medications", "age", "include_evidence"]:
            raise RuntimeError("BLOCKED: screen_patient 시그니처 불일치")
        quiet(DUR.init_screening, types.SimpleNamespace(project_root=root))
        miss_g = [g for g in ["pairs_engine", "KNOWN_DUR_ITEMS", "ELDERLY_RULES_BY_ITEM", "THERAPEUTIC_EFFECTS_BY_ITEM", "CONTRAINDICATION_PAIR_IDS", "DATA_SNAPSHOT", "ELDERLY_AGE_THRESHOLD"] if not hasattr(DUR, g)]
        if miss_g: raise RuntimeError("BLOCKED: init 후 전역 없음 %s" % miss_g)
        DUR_FILE_INFO = [{"file": str(p.relative_to(root)), "size_bytes": p.stat().st_size, "file_mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(p.stat().st_mtime)),
                          "data_collection_date": "NOT_AVAILABLE_IN_ENGINE_OUTPUT"} for p in DUR_TABLES.values()]
        eng.dur_ad = DurAdapter(DUR, DUR_FILE_INFO); eng.dur_ok = True
        eng.info["screening_py_sha256"] = hashlib.sha256(_src_bytes).hexdigest()
    except Exception as e:  # noqa: BLE001 — 로딩 실패는 화면이 안내로 처리(fail closed)
        eng.error_dev = "DUR 로딩 단계 '%s': %s: %s" % (stage, type(e).__name__, str(e)[:400])
    # ---- 성분(15번) — DUR 로딩이 실패해도 시도한다(부분 결과 표시를 위해) ----
    try:
        stage = "nb15_load"
        root = Path(eng.info.get("project_root") or project_root or str(Path(__file__).resolve().parents[1]))
        SRC = root / "data/processed/evidence/drug_approval_items.parquet"
        FOUND15 = Path(eng.info.get("nb15") or locate_files(root, nb15_path, screening_path).get("15_ingredient_duplicate_candidates_prototype.ipynb"))
        global NB15_CELLS, NB15_CONST
        NB15_CELLS, NB15_CONST = _prepare_nb15(FOUND15)
        NB15, _ = build_nb15(SRC, "REAL")
        for f in ["screen_pair", "screen_list", "norm", "lens", "form_markers", "parse_main"]:
            if f not in NB15: raise RuntimeError("BLOCKED: 15번 함수 없음 " + f)
        if list(inspect.signature(NB15["screen_pair"]).parameters) != ["seq_a", "seq_b"] or list(inspect.signature(NB15["screen_list"]).parameters) != ["seqs"]:
            raise RuntimeError("BLOCKED: 15번 함수 시그니처 불일치")
        eng.ing_ad = IngredientAdapter(NB15, "REAL"); eng.ing_ok = True
        eng.info.update({"nb15": str(FOUND15), "n_products": int(len(NB15["P"])), "n_ingredient_rows": int(len(NB15["ING"]))})
    except Exception as e:  # noqa: BLE001
        msg = "성분 로딩 단계: %s: %s" % (type(e).__name__, str(e)[:400])
        eng.error_dev = (eng.error_dev + " | " + msg) if eng.error_dev else msg
    eng.ready = eng.dur_ok and eng.ing_ok
    if not eng.ready:
        eng.error_user = ("통합 Screening 엔진을 불러오지 못했습니다(" + ", ".join(n for n, ok in (("DUR", eng.dur_ok), ("성분 후보", eng.ing_ok)) if not ok) +
                          "). 이는 기술적 오류이며 약물 조합에 문제가 없다는 의미가 아닙니다. 기존 DUR 검사 화면은 계속 사용할 수 있습니다.")
    return eng


# ===== [17:glue] UI 안전 래퍼 =====
def _tech_err(stage, exc):
    return {"stage": stage, "type": type(exc).__name__, "message": str(exc)[:300]}


def screen_for_ui(engine, item_seqs, age):
    """UI가 호출하는 유일한 진입점. 절대 예외를 던지지 않는다.

    반환: {"status": "OK" | "TECHNICAL_ERROR" | "TECHNICAL_PARTIAL", "result": 16번 통합 JSON | None,
           "dur_part": ..., "ing_part": ..., "technical_errors": [...], "schema_errors": [...]}
    - OK: 16번 integrated_screen 결과이며 스키마·의미·근거 점검을 통과함
    - TECHNICAL_ERROR: 엔진 미로딩/호출 실패/결과 검증 실패 — '검사 완료'로 표시하지 않음
    - TECHNICAL_PARTIAL: 통합 호출은 실패했지만 DUR 또는 성분 단독 호출은 성공한 경우(성공한 부분만 반환)
    """
    out = {"status": "TECHNICAL_ERROR", "result": None, "dur_part": None, "ing_part": None, "technical_errors": [], "schema_errors": []}
    if engine is None or not getattr(engine, "ready", False):
        out["technical_errors"].append({"stage": "engine_load", "type": "EngineNotReady", "message": (getattr(engine, "error_dev", None) or "engine not loaded")[:300]})
        return out
    req = {"item_seqs": list(item_seqs) if isinstance(item_seqs, (list, tuple)) else item_seqs, "patient_age": age}
    try:
        res = integrated_screen(req, engine.dur_ad, engine.ing_ad)
        errs = check_result(res)
        if errs:
            out["schema_errors"] = errs[:10]
            out["technical_errors"].append({"stage": "result_validation", "type": "SchemaOrSemanticViolation", "message": "; ".join(errs[:3])[:300]})
            return out
        out.update(status="OK", result=res)
        return out
    except Exception as e:  # noqa: BLE001
        out["technical_errors"].append(_tech_err("integrated_screen", e))
    # 부분 결과: 정상 입력일 때만 각 엔진을 따로 시도
    try:
        v = validate_request(req, engine.dur_ad.m)
        if v["ok"]:
            seqs = v["normalized"]
            try: out["dur_part"] = engine.dur_ad.run(seqs, v["age"])[0]
            except Exception as e:  # noqa: BLE001
                out["technical_errors"].append(_tech_err("dur_only", e))
            try: out["ing_part"] = engine.ing_ad.run(seqs)
            except Exception as e:  # noqa: BLE001
                out["technical_errors"].append(_tech_err("ingredient_only", e))
            if out["dur_part"] is not None or out["ing_part"] is not None:
                out["status"] = "TECHNICAL_PARTIAL"
    except Exception as e:  # noqa: BLE001
        out["technical_errors"].append(_tech_err("partial_recovery", e))
    return out


# ===== [17:glue] 화면 표시용 변환 (표시 문구/라벨만 — 판정·유형 변경 없음) =====
OVERALL_LABEL = {   # 위험도/신호등이 아님: 처리 상태 라벨. tone은 중립 계열만 사용
    "REVIEW_REQUIRED": ("검토 필요 항목 있음", "warn", "DUR 규칙 매칭 또는 성분 중복 후보가 있어 사람의 확인이 필요합니다. 위험도 등급이 아닙니다."),
    "PARTIAL": ("일부 범위 미평가", "info", "매칭은 없었지만 평가하지 못한 범위가 있습니다. 안전하다는 의미가 아닙니다."),
    "NO_MATCH_FOUND": ("현재 탐지 범위에서 매칭 없음", "muted", "현재 보유한 데이터·규칙 범위에서 매칭이 확인되지 않았다는 뜻이며 안전 판정이 아닙니다."),
    "BLOCKED": ("스크리닝 미수행", "warn", "입력 또는 제품 식별 문제로 스크리닝을 수행하지 못했습니다. 결과가 없는 상태이며 문제가 없다는 의미가 아닙니다."),
}
DUR_STATUS_LABEL = {
    "MATCHED": "공식 DUR 규칙 매칭 있음",
    "NO_MATCH_FOUND": "현재 보유한 DUR 데이터에서 해당 규칙이 확인되지 않았습니다.",
    "PARTIAL_COVERAGE_NO_MATCH": "매칭은 없으나 일부 제품이 DUR 규칙 데이터에 포함되어 있지 않아 일부 범위는 평가하지 못했습니다.",
    "NOT_EVALUATED": "평가하지 않음",
}
ING_STATUS_LABEL = {
    "CANDIDATES_FOUND": "성분 중복 후보 있음 (미검증)",
    "NO_CANDIDATE_FOUND": "현재 탐지 규칙에서 후보가 확인되지 않았습니다.",
    "NO_CANDIDATE_FOUND_PARTIAL": "후보는 확인되지 않았지만 성분 정보가 불완전한 제품이 있어 일부 범위는 판단하지 못했습니다.",
    "NOT_APPLICABLE_SINGLE_PRODUCT": "제품이 1개라 성분 중복 후보 비교를 하지 않았습니다.",
    "NOT_EVALUATED_INSUFFICIENT_DATA": "성분 정보가 부족해 판단하지 못했습니다 (판단 불가).",
    "NOT_EVALUATED": "평가하지 않음",
}
# 16/15 반환값 → 설명용 유형 (TYPE A~F). 새 유형을 만들지 않는다.
TYPE_LABEL = {
    "TYPE_A": ("A · 동일 M코드 · 동일 성분명 후보", "info"),
    "TYPE_B": ("B · 동일 성분명 · 서로 다른 M코드 후보", "purple"),
    "TYPE_C": ("C · 동일 M코드 · 서로 다른 성분명 (검토 전용, 후보 아님)", "gray"),
    "TYPE_D": ("D · 형태 차이 힌트/성분 불명확 (후보 아님)", "gray"),
    "TYPE_E": ("E · 후보 없음 (안전 판정 아님)", "muted"),
    "TYPE_F": ("F · 성분 정보 부족/허가정보 미포함 (판단 보류)", "warn"),
}
TYPE_MAPPING_NOTE = ("유형 A=SAME_MCODE_SAME_NAME, B=SAME_NAME_DIFF_MCODE, C=동일 M코드·다른 성분명(15번이 불명확로 제외한 항목, 검토 전용), "
                     "D=형태 차이 힌트/불명확, E=후보 없음, F=정보 부족. 15·16번의 반환값을 그대로 옮긴 것이며 새 유형이나 판정을 추가하지 않았습니다.")
MCODE_NOTICE = ("같은 성분명이어도 제품 허가정보의 M코드가 서로 다른 경우가 있습니다. 이를 데이터 오류로 단정하지 않으며, 이름이 같다는 사실만으로 같은 유효성분이라고도 "
                "판단하지 않습니다. 일부 사례를 공식 사이트에서 수동으로 대조했을 때 이름·제품 정보가 일치한 경우가 있었지만, 이는 약학적 동일성을 증명하지 않습니다. "
                "공식 성분 동일성 검증은 NO-GO(미검증) 상태이며, 이 항목은 공식 DUR 병용금기가 아니라 '사람이 추가로 확인할 후보'입니다.")
CANDIDATE_NOT_DUR_NOTICE = "성분 중복 후보는 공식 DUR 병용금기가 아니며 약학적 동일성·임상 위험을 확정하지 않습니다. 모든 후보의 검증 상태는 UNVERIFIED_CANDIDATE 입니다."
TEMPLATE_NOTICE = "이 섹션은 템플릿 기반 표시입니다. 성분 후보 결과는 RAG/LLM 설명에 전달되지 않았고, LLM이 생성한 문장이 포함되어 있지 않습니다."
UNRESOLVED_REASON_KO = {
    "NOT_IN_APPROVAL_DATA": "제품 허가정보에 없음 (성분 판단 불가)",
    "NO_INGREDIENT_INFO": "성분 정보 없음 (판단 보류)",
}


def _cand_row(c):
    t = c["candidate_type"]; names = c.get("item_names") or []; seqs = c.get("involved_item_seqs") or []
    return {
        "type": t, "type_label": TYPE_LABEL[t][0], "type_tone": TYPE_LABEL[t][1], "is_candidate": bool(c["candidate"]),
        "item_names": names, "item_seqs": seqs, "raw_names": c.get("original_ingredient_names") or [], "norm_names": c.get("normalized_ingredient_names") or [],
        "m_codes": c.get("original_m_codes") or [], "basis": c.get("detection_reason", ""), "verification_status": c.get("verification_status", ""),
        "needs_review": True, "diff_mcode": t == "TYPE_B", "evidence_id": c.get("evidence_id"), "limitations": c.get("limitations") or [],
        "high_frequency": bool(c.get("high_frequency")),
    }


def _dur_row(r):
    ev = r.get("official_evidence") or {}
    return {"rule_type": r["rule_type"], "item_names": r.get("involved_item_names") or [], "item_seqs": r.get("involved_item_seqs") or [], "rule_id": r.get("rule_id"),
            "rule_source": (r.get("source") or {}).get("rule_source"), "has_evidence": bool(ev.get("has_evidence")), "texts": ev.get("texts") or [],
            "screening_status": r.get("screening_status"), "evidence_id": r.get("evidence_id"), "effect_name": (r.get("rule_key") or {}).get("effect_name")}


def build_ui_model(ui_out):
    """screen_for_ui 결과 → 화면 데이터. 문구/라벨 매핑만 하며 건수·유형·상태를 바꾸지 않는다."""
    m = {"state": "NOT_RUN", "badge": ("분석 전", "neutral", "'통합 Screening 실행'을 누르면 DUR 공식 규칙과 성분 중복 후보를 함께 확인합니다."),
         "technical_errors": [], "dur": None, "ingredient": None, "limitations": [], "evidence": [], "processing": [], "age_notice": None, "partial": False}
    if ui_out is None: return m
    st = ui_out.get("status")
    m["technical_errors"] = list(ui_out.get("technical_errors") or [])
    if st == "TECHNICAL_ERROR":
        m.update(state="TECHNICAL_ERROR", badge=("기술적 오류 — 검사 미완료", "danger", "엔진 호출/결과 검증에 실패했습니다. 약물 조합에 문제가 없다는 의미가 아니며, 의학 정보가 부족해서 생긴 상태와 구분됩니다."))
        return m
    if st == "TECHNICAL_PARTIAL":
        m["state"] = "TECHNICAL_PARTIAL"; m["partial"] = True
        m["badge"] = ("부분 결과 — 일부 엔진 호출 실패", "warn", "성공한 부분만 표시합니다. 실패한 부분은 평가되지 않았으며 문제가 없다는 의미가 아닙니다.")
        dur, ing = ui_out.get("dur_part"), ui_out.get("ing_part")
        if dur is not None: m["dur"] = _dur_model(dur)
        if ing is not None: m["ingredient"] = _ing_model(ing, None)
        m["limitations"] = ["통합 호출이 실패해 일부 결과만 표시합니다(근거 ID·전체 검증이 완료되지 않음).", CANDIDATE_NOT_DUR_NOTICE]
        return m
    res = ui_out["result"]; ov = res["overall_status"]
    m["state"] = "BLOCKED" if ov == "BLOCKED" else "DONE"
    m["badge"] = OVERALL_LABEL[ov]
    m["dur"] = _dur_model(res["dur_screening"]); m["ingredient"] = _ing_model(res["ingredient_screening"], res)
    m["limitations"] = list(res["limitations"]); m["evidence"] = res["evidence"]
    m["products"] = res["product_resolution"]
    m["gaps"] = list((res.get("meta") or {}).get("gaps") or [])
    for w in res["input_validation"]["warnings"]:
        m["processing"].append((w["code"], w.get("detail")))
        if w["code"] == "PATIENT_AGE_MISSING": m["age_notice"] = "나이가 입력되지 않아 노인주의는 평가하지 않았습니다(임의로 확정하지 않음)."
    for e in res["input_validation"]["errors"]: m["processing"].append((e["code"], e.get("detail")))
    m["request_id"] = res["request_id"]; m["meta"] = res["meta"]
    return m


def _dur_model(d):
    return {"status": d["status"], "status_label": DUR_STATUS_LABEL[d["status"]], "elderly_check_status": d.get("elderly_check_status"),
            "contraindications": [_dur_row(r) for r in d["contraindications"]], "elderly_cautions": [_dur_row(r) for r in d["elderly_cautions"]],
            "therapeutic_duplicates": [_dur_row(r) for r in d["therapeutic_duplicates"]], "not_in_dur_tables": list(d.get("not_found_in_dur_tables") or []),
            "scope_note": d.get("scope_note")}


def _ing_model(g, res):
    rows = [_cand_row(c) for c in g["duplicate_candidates"]]
    pairs = [{"pair": p["pair"], "types": p["types"], "type_labels": [TYPE_LABEL[t][0] for t in p["types"] if t in TYPE_LABEL], "pair_status": p["ingredient_pair_status"]} for p in g.get("pair_results", [])]
    unres = [dict(u, reason_ko=UNRESOLVED_REASON_KO.get(u.get("reason"), u.get("reason")), type_label=TYPE_LABEL.get(u.get("type"), ("", ""))[0]) for u in g["unresolved_ingredients"]]
    return {"status": g["status"], "status_label": ING_STATUS_LABEL[g["status"]], "rows": rows, "pairs": pairs, "unresolved": unres,
            "has_diff_mcode": any(r["diff_mcode"] for r in rows), "n_candidates": sum(1 for r in rows if r["is_candidate"])}


# ===== [17b:glue] 선택 의약품별 성분정보 · 제품 쌍 비교 3상태 (조회·표시 전용 — 새 매칭/판정 규칙 없음) =====
# 모든 값은 15번이 허가정보(MAIN_ITEM_INGR)에서 파싱해 둔 ING/P 테이블과 15·16번 엔진(IngredientAdapter.run) 반환값을 그대로 옮긴 것이다.
# 제품명으로 성분을 추정하지 않으며, 성분이 없으면 없는 이유를 그대로 보여 준다.
LOOKUP_STATUS_KO = {
    "SCREENABLE": ("조회됨 · 비교 가능", "ok"),
    "PARTIAL_UNCLEAR": ("조회됨 · 일부 성분 불명확 (불명확 성분은 비교에서 제외)", "warn"),
    "ALL_INGREDIENTS_UNCLEAR": ("조회됨 · 모든 성분이 불명확하여 비교 불가", "warn"),
    "NO_INGREDIENT_INFO": ("성분정보 조회 불가 · 허가정보에 제품은 있으나 MAIN_ITEM_INGR 없음/파싱 불가", "danger"),
    "NOT_IN_APPROVAL_DATA": ("성분정보 조회 불가 · 이 itemSeq가 현재 허가정보 데이터에 없음", "danger"),
    "ENGINE_NOT_READY": ("성분정보 조회 불가 · 성분 엔진/허가정보 데이터를 불러오지 못함", "danger"),
}
D_REASON_KO = {"CODE_MAPS_TO_MULTIPLE_NAMES": "같은 M코드가 서로 다른 성분명에 연결됨(불명확)"}
PAIR_STATE_KO = {
    "A": "A · 중복 후보 발견 (미검증 후보)",
    "B": "B · 현재 규칙에서 중복 후보 미발견",
    "C": "C · 데이터 부족으로 비교 불가",
}
PAIR_B_TEXT = "현재 비교 규칙에서 일치하는 성분 후보가 발견되지 않았습니다."
PAIR_B_WARN = "이는 병용 안전성을 보장하지 않습니다."
CASE_LABEL = {
    "CASE1": "① M코드와 정규화 성분명이 모두 일치",
    "CASE2": "② 정규화 성분명은 같고 M코드가 다름",
    "CASE3": "③ M코드는 같지만 정규화 성분명이 다름 (검토 전용 · 후보 아님)",
    "CASE4": "④ 성분정보가 불명확하거나 형태 차이 힌트 (후보 아님)",
}
VERIFY_NOTICE = ("공식 성분 동일성 검증은 NO-GO(NOT_VERIFIED) 상태입니다. 성분명·M코드가 같거나 달라도 약학적 동일성·임상 위험을 확정하지 않으며, "
                 "M코드가 다르다는 사실만으로 데이터 오류라고 단정하지도 않습니다. 공식 DUR 병용금기가 아닙니다.")
SOURCE_NOTICE = ("성분 데이터 출처: 제품 허가정보(drug_approval_items)의 MAIN_ITEM_INGR 컬럼을 15번 노트북이 [M코드]성분명 형태로 파싱한 결과. "
                 "정규화는 15번의 보수적 정규화(NFKC·공백 정리)뿐이며 염·수화물 등을 지우지 않습니다. 비교 규칙은 15번 screen_pair()입니다.")


def ingredient_profile(engine, item_seq):
    """선택된 itemSeq 한 개의 성분정보(허가정보 조회). 예외를 던지지 않는다."""
    seq = str(item_seq)
    prof = {"item_seq": seq, "item_name": None, "status": "ENGINE_NOT_READY", "ingredients": [], "n_declared": None, "n_parsed": 0,
            "source": None, "main_left_over": False, "cancel_status": None, "error": None}
    try:
        ad = getattr(engine, "ing_ad", None)
        if ad is None: return prof
        ns = ad.ns; st_ = ad.info_status(seq); prof["status"] = st_
        if st_ == "NOT_IN_APPROVAL_DATA": return prof
        pi = ns["PI_BY_SEQ"][seq]; pr = ns["P_ROW"][pi]
        prof.update(item_name=pr.item_name, n_declared=(int(pr.cnt) if pr.cnt is not None and not pd.isna(pr.cnt) else None), n_parsed=int(pr.n_ing), source=ns["source_str"](pi),
                    main_left_over=bool(pr.main_left), cancel_status=pr.status_name)
        for r in ns["ALL_BY_PI"].get(pi, []):
            prof["ingredients"].append({"pos": int(r.pos), "m_code": r.m_code, "name_raw": r.name_raw, "name_norm": r.name_norm,
                                        "form_markers": r.form_markers or "", "unclear": bool(r.unclear_D),
                                        "d_reasons": [D_REASON_KO.get(x, x) for x in str(r.d_reasons or "").split(";") if x]})
    except Exception as e:  # noqa: BLE001
        prof["status"] = "ENGINE_NOT_READY"; prof["error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
    return prof


def _case_of(c):
    t = c["candidate_type"]; pc = c.get("pair_class")
    if t == "TYPE_A" or pc == "SAME_MCODE_SAME_NAME": return "CASE1"
    if t == "TYPE_B" or pc == "SAME_NAME_DIFF_MCODE": return "CASE2"
    if t == "TYPE_C" or pc in ("SAME_MCODE_DIFF_NAME", "SAME_MCODE_DIFF_NAME_REVIEW_ONLY"): return "CASE3"
    return "CASE4"


def ingredient_check(engine, item_seqs, integ_result=None):
    """선택 의약품 전체의 성분 확인 뷰모델.

    - 제품별 성분정보(ingredient_profile)
    - 모든 제품 쌍(n*(n-1)/2)의 3상태 A/B/C
    - 발견된 후보/검토 항목(4개 사례 구분)
    성분 판정은 16번 IngredientAdapter.run()(=15번 screen_pair) 반환값이다. integ_result(16번 통합 JSON)가 현재 선택과 같으면 그 값을 쓰고,
    아니면 같은 함수를 직접 호출한다. 두 값이 모두 있으면 일치 여부(consistency)를 기록한다.
    """
    seqs = []
    for x in (item_seqs or []):
        x = str(x)
        if x not in seqs: seqs.append(x)
    out = {"seqs": seqs, "profiles": [ingredient_profile(engine, s) for s in seqs], "pairs": [], "findings": [], "status": None, "origin": None,
           "consistency": None, "engine_ready": bool(getattr(engine, "ing_ok", False) and getattr(engine, "ing_ad", None) is not None), "error": None}
    prof = {p["item_seq"]: p for p in out["profiles"]}
    g = None; direct = None
    if out["engine_ready"] and len(seqs) >= 1:
        try: direct = engine.ing_ad.run(seqs)
        except Exception as e:  # noqa: BLE001
            out["error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
    if integ_result is not None:
        g = integ_result["ingredient_screening"]; out["origin"] = "16번 통합 Screening 결과"
        if direct is not None:
            # 16번이 통합 결과에 덧붙이는 근거 ID(evidence_id)만 제외하고 판정 내용 전체를 비교한다
            strip = lambda cs: [{k: v for k, v in c.items() if k != "evidence_id"} for c in cs]
            key = lambda x: json.dumps([x["status"], strip(x["duplicate_candidates"]), x["unresolved_ingredients"], x.get("pair_results") or []], sort_keys=True, ensure_ascii=False, default=str)
            out["consistency"] = (key(g) == key(direct))
    elif direct is not None:
        g = direct; out["origin"] = "15·16번 성분 엔진 직접 호출(통합 버튼 실행 전 미리보기)"
    out["status"] = g["status"] if g else None
    if g is None and len(seqs) >= 2:
        # 엔진 없음 → 모든 쌍이 '비교 불가'
        for i in range(len(seqs)):
            for j in range(i + 1, len(seqs)):
                out["pairs"].append({"a": seqs[i], "b": seqs[j], "state": "C", "reasons": ["성분 엔진/허가정보 데이터를 불러오지 못해 비교하지 못했습니다."], "n_candidates": 0, "types": []})
        return out
    if g is None: return out
    cands = g["duplicate_candidates"]
    for i in range(len(seqs)):
        for j in range(i + 1, len(seqs)):
            a, b = seqs[i], seqs[j]; pr = {a, b}
            pc = [c for c in cands if set(c["involved_item_seqs"]) == pr or (c["candidate_type"] == "TYPE_C" and pr <= set(c["involved_item_seqs"]))]
            real = [c for c in pc if c["candidate"]]
            reasons = []
            for s in (a, b):
                p = prof[s]
                if p["status"] in ("NOT_IN_APPROVAL_DATA", "NO_INGREDIENT_INFO", "ALL_INGREDIENTS_UNCLEAR", "ENGINE_NOT_READY"):
                    reasons.append("%s(%s): %s" % (p["item_name"] or "이름 미확인", s, LOOKUP_STATUS_KO[p["status"]][0]))
            pres = [p for p in g.get("pair_results", []) if set(p["pair"]) == pr]
            types = pres[0]["types"] if pres else []
            if real: state = "A"
            elif reasons or "TYPE_F" in types: state = "C"
            else: state = "B"
            notes = []
            if state == "B":
                for s in (a, b):
                    if prof[s]["status"] == "PARTIAL_UNCLEAR": notes.append("%s(%s): 일부 성분이 불명확하여 비교에서 제외됨" % (prof[s]["item_name"], s))
                if any(c["candidate_type"] in ("TYPE_C", "TYPE_D") for c in pc): notes.append("후보는 아니지만 사람이 검토할 항목이 있습니다(아래 '검토 항목' 참고).")
            out["pairs"].append({"a": a, "b": b, "state": state, "reasons": reasons, "notes": notes, "n_candidates": len(real), "types": types,
                                 "pair_status": pres[0]["ingredient_pair_status"] if pres else None})
    for c in cands:
        cs = _case_of(c)
        out["findings"].append({"case": cs, "case_label": CASE_LABEL[cs], "candidate_type": c["candidate_type"], "is_candidate": bool(c["candidate"]),
                                "item_names": c["item_names"], "item_seqs": c["involved_item_seqs"], "raw_names": c["original_ingredient_names"],
                                "norm_names": c["normalized_ingredient_names"], "m_codes": c["original_m_codes"], "basis": c["detection_reason"],
                                "verification_status": c["verification_status"], "needs_review": True,
                                "needs_review_text": "추가 확인 필요 (미검증 후보)" if c["candidate"] else "사람 검토용 (후보 아님)"})
    for u in g["unresolved_ingredients"]:
        if u["type"] == "TYPE_D":
            out["findings"].append({"case": "CASE4", "case_label": CASE_LABEL["CASE4"], "candidate_type": "TYPE_D", "is_candidate": False,
                                    "item_names": [u.get("item_name")], "item_seqs": [u["item_seq"]], "raw_names": [u.get("ingredient_name_raw")],
                                    "norm_names": [], "m_codes": [u.get("m_code")], "basis": D_REASON_KO.get(u["reason"], u["reason"]),
                                    "verification_status": "NOT_A_CANDIDATE", "needs_review": True, "needs_review_text": "사람 검토용 (후보 아님)"})
    return out


# ===== [17c:glue] 상단 KPI '성분 중복 후보' 카드 값 계산 · 제품별 '확인된 성분' 문구 (표시 전용 — 새 매칭/판정 규칙 없음) =====
# 입력은 ingredient_check()가 만든 결과(15번 screen_pair / 16번 통합 결과를 그대로 옮긴 것)이며, 여기서는 세고 라벨만 붙인다.
KPI_TAGLINE = "연구용 성분 중복 후보 탐지 · 공식 DUR 규칙 아님"
KPI_UNIT_TEXT = "집계 단위: 후보 레코드(제품 쌍 × 성분 조합, 15번 candidates[] 중 candidate=true). 제품 쌍 수·DUR 규칙 건수와 합산하지 않음"


def confirmed_ingredients_text(prof):
    """제품 한 개의 '확인된 성분' 한 줄. 성분이 없으면 '확인 불가'만 쓰지 않고 조회 상태(누락 원인)를 설명한다."""
    ings = prof.get("ingredients") or []
    if not ings:
        return "확인된 성분 없음 — " + LOOKUP_STATUS_KO[prof["status"]][0]
    ok = [i["name_raw"] for i in ings if not i["unclear"]]
    unclear = [i["name_raw"] for i in ings if i["unclear"]]
    text = " · ".join(ok) if ok else "(비교에 사용할 수 있는 성분 없음)"
    if unclear:
        text += "  / 불명확하여 비교에서 제외: " + " · ".join(unclear)
    return text


def ingredient_kpi(chk, analyzed, technical_error=False):
    """KPI 카드 dict(label/value/desc/sub/tone/tagline/tooltip). 상태 A~E는 사용자 요구 사양 그대로.
    비교하지 못한 쌍은 절대 0건으로 세지 않는다."""
    card = {"label": "성분 중복 후보", "tone": "mg-kpi-ing", "tagline": KPI_TAGLINE, "icon": None}
    if technical_error:
        card.update(value="오류", desc="기술적 오류 — 검사 미완료", sub="후보가 없다는 뜻이 아닙니다", tooltip=KPI_UNIT_TEXT); return card
    if not analyzed:                                                           # A. 분석 전
        card.update(value="—", desc="분석 전", sub="통합 Screening 실행 후 표시", tooltip=KPI_UNIT_TEXT); return card
    pairs = chk.get("pairs") or []
    if not pairs:                                                              # 제품 1개 이하: 비교 대상 없음 (0건 아님)
        card.update(value="—", desc="비교 대상 2개 미만", sub="후보가 없다는 뜻이 아닙니다", tooltip=KPI_UNIT_TEXT); return card
    seen, records = set(), 0
    for f in chk.get("findings") or []:                                        # 후보 레코드만, 같은 레코드가 두 번 세지지 않도록 키로 중복 제거
        if not f["is_candidate"]: continue
        k = (tuple(sorted(f["item_seqs"])), f["case"], tuple(f["m_codes"]), tuple(f["norm_names"]))
        if k in seen: continue
        seen.add(k); records += 1
    n_pairs = len(pairs); n_c = sum(1 for p in pairs if p["state"] == "C"); n_a = sum(1 for p in pairs if p["state"] == "A")
    n_ok = n_pairs - n_c
    unit = "후보 레코드 %d건 / 후보가 있는 제품 쌍 %d개 / 비교한 제품 쌍 %d개" % (records, n_a, n_ok)
    card["tooltip"] = KPI_UNIT_TEXT + " · " + unit
    if n_c == n_pairs:                                                         # D. 전부 비교 불가
        card.update(value="평가 불가", desc="성분정보 부족으로 비교 불가", sub="비교 불가 제품 쌍 %d개 · 0건이 아님" % n_c)
    elif n_c > 0:                                                              # E. 일부만 비교 가능
        card.update(value="부분 평가", desc="일부 조합의 성분 비교 불가", sub="비교 가능 %d쌍 중 후보 %d건 · 비교 불가 %d쌍" % (n_ok, records, n_c))
    elif records > 0:                                                          # C. 후보 발견
        card.update(value="%d건" % records, desc="성분 중복 후보 발견 · 검토 필요", sub="후보 레코드 기준 · 제품 쌍 %d개" % n_a)
    else:                                                                      # B. 정상 비교, 후보 없음
        card.update(value="0건", desc="현재 규칙에서 후보 미발견", sub="비교한 제품 쌍 %d개 · 안전 판정이 아님" % n_ok)
    if any(p.get("notes") for p in pairs):
        card["sub"] += " · 일부 성분 불명확(비교 제외)"
    return card
