"""UI display policy — fixed constants and the per-finding display-mode decision.

Source of truth: docs/STREAMLIT_VIEW_MAPPING.md (§0–§9) and docs/CORE_INTERFACE_CONTRACT.md.
Every user-facing string the adapter emits lives here, so a wording change is a one-line diff that
does not touch the adapter logic.

Nothing in this module makes a medical judgement. It only decides *whether* text that the Frozen
Core already produced may be shown, and which fixed notice replaces it when it may not.
"""
from __future__ import annotations

import re

ADAPTER_NAME = "dur_safety_ui_adapter"
ADAPTER_VERSION = "0.1.0"
CONTRACT_VERSION = "core-interface-contract-v1"

# ---------------------------------------------------------------------------------------------------
# Input limits — UI / MVP ONLY. NOT clinically validated. The Frozen Core has no such limit.
# Purpose: keep one request's LLM call count and latency bounded in the first deployment.
# Changing these values does not change any screening result for the medications that are submitted.
# ---------------------------------------------------------------------------------------------------
MIN_MEDICATIONS = 1
MAX_MEDICATIONS = 20
MEDICATION_LIMIT_NOTE = ("약물 수 제한(1~20개)은 MVP 화면 운영을 위한 임시 제한이며, "
                         "임상적으로 검증된 기준이 아닙니다.")
AGE_MIN = 0
AGE_MAX = 150          # same range as screening.validate_age; the adapter additionally requires int

# ---------------------------------------------------------------------------------------------------
# Input validation statuses
# ---------------------------------------------------------------------------------------------------
VALID = "VALID"
INVALID_AGE = "INVALID_AGE"
INVALID_MEDICATION = "INVALID_MEDICATION"
DUPLICATE_SELECTION = "DUPLICATE_SELECTION"
TOO_MANY_MEDICATIONS = "TOO_MANY_MEDICATIONS"
EMPTY_MEDICATIONS = "EMPTY_MEDICATIONS"
LOOKUP_VALIDATION_FAILED = "LOOKUP_VALIDATION_FAILED"
# When several issues exist, the reported primary status is the first one in this order.
INPUT_STATUS_PRIORITY = (LOOKUP_VALIDATION_FAILED, INVALID_AGE, EMPTY_MEDICATIONS, TOO_MANY_MEDICATIONS,
                         DUPLICATE_SELECTION, INVALID_MEDICATION)

INPUT_MESSAGES = {
    "AGE_REQUIRED": "나이를 입력하거나 '나이 모름'을 선택하세요.",
    "AGE_CONFLICT": "나이를 입력했다면 '나이 모름' 선택을 해제하세요.",
    "AGE_TYPE": "나이는 정수로 입력하세요.",
    "AGE_RANGE": f"나이는 {AGE_MIN}~{AGE_MAX} 사이의 정수로 입력하세요.",
    EMPTY_MEDICATIONS: f"검사할 약물을 {MIN_MEDICATIONS}개 이상 선택하세요.",
    TOO_MANY_MEDICATIONS: (f"한 번에 최대 {MAX_MEDICATIONS}개까지 검사할 수 있습니다. "
                           "선택한 약물 수를 줄여 주세요. (MVP 임시 제한)"),
    DUPLICATE_SELECTION: "같은 제품이 두 번 이상 선택되었습니다. 중복 항목을 삭제한 뒤 다시 검사하세요.",
    INVALID_MEDICATION: "검색 결과에서 선택하지 않았거나 확인할 수 없는 약물이 있습니다. 검색 후 목록에서 다시 선택하세요.",
    LOOKUP_VALIDATION_FAILED: "약물 선택을 확인하는 중 오류가 발생했습니다. 잠시 후 다시 시도하세요.",
}

# ---------------------------------------------------------------------------------------------------
# ViewModel states
# ---------------------------------------------------------------------------------------------------
STATE_COMPLETED = "COMPLETED"                  # report valid; results may be shown
STATE_INPUT_INVALID = "INPUT_INVALID"          # L0 — Core not called
STATE_RESOURCE_ERROR = "RESOURCE_ERROR"        # L1 — resources not loaded / environment
STATE_CORE_ERROR = "CORE_ERROR"                # L2 — run_safety_check raised
STATE_REPORT_INVALID = "REPORT_INVALID"        # L3 — report structure does not match the contract
STATE_REPORT_INCONSISTENT = "REPORT_INCONSISTENT"  # L3 — count invariant broken
RESULT_STATES = (STATE_COMPLETED,)

# ---------------------------------------------------------------------------------------------------
# Error layers
# ---------------------------------------------------------------------------------------------------
L0_INPUT = "L0_INPUT"
L1_RESOURCE = "L1_RESOURCE"
L2_CORE = "L2_CORE"
L3_REPORT = "L3_REPORT"
L4_FINDING = "L4_FINDING"

ERROR_MESSAGES = {
    "INPUT_INVALID": "입력값을 확인하세요. 검사는 실행되지 않았습니다.",
    "RESOURCES_NOT_LOADED": "검사 시스템이 아직 준비되지 않았습니다. 잠시 후 다시 시도하세요.",
    "CORE_EXCEPTION": "검사 실행 중 시스템 오류가 발생했습니다. 결과를 표시할 수 없습니다.",
    "REPORT_INVALID": "검사 결과 형식이 올바르지 않아 결과를 표시할 수 없습니다. (시스템 오류)",
    "REPORT_INCONSISTENT": "검사 결과의 일관성 검사에 실패하여 결과를 표시할 수 없습니다. (시스템 오류)",
    "FINDING_PROCESSING_ERROR": "일부 항목의 근거 검색·설명 처리 중 오류가 발생했습니다. 탐지 결과는 유효합니다.",
}

# ---------------------------------------------------------------------------------------------------
# Display modes (STREAMLIT_VIEW_MAPPING §0) — names are the contract names.
# ---------------------------------------------------------------------------------------------------
EXPLANATION = "EXPLANATION"
WITHHELD_DIRECTIVE = "WITHHELD_DIRECTIVE"
WITHHELD_INVALID = "WITHHELD_INVALID"
NO_EVIDENCE = "NO_EVIDENCE"
EVIDENCE_INVALID = "EVIDENCE_INVALID"
LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
GENERATION_FAILED = "GENERATION_FAILED"
PROCESSING_ERROR = "PROCESSING_ERROR"
DISPLAY_MODES = (EXPLANATION, WITHHELD_DIRECTIVE, WITHHELD_INVALID, NO_EVIDENCE, EVIDENCE_INVALID,
                 LLM_UNAVAILABLE, GENERATION_FAILED, PROCESSING_ERROR)

STATUS_TO_MODE = {
    "INVALID_OUTPUT": WITHHELD_INVALID,
    "NO_EVIDENCE": NO_EVIDENCE,
    "EVIDENCE_INVALID": EVIDENCE_INVALID,
    "LLM_UNAVAILABLE": LLM_UNAVAILABLE,
    "LLM_ERROR": GENERATION_FAILED,
    "EMPTY_RESPONSE": GENERATION_FAILED,
    "MALFORMED_RESPONSE": GENERATION_FAILED,
    "PIPELINE_ERROR": PROCESSING_ERROR,
}

MODE_MESSAGES = {   # (message, severity) — STREAMLIT_VIEW_MAPPING §5, verbatim
    WITHHELD_DIRECTIVE: ("자동 생성 설명에 처방 지시로 오해될 수 있는 표현이 감지되어 표시하지 않습니다. "
                         "아래 허가정보 원문과 DUR 기준을 확인하세요.", "warning"),
    WITHHELD_INVALID: ("자동 생성 설명이 검증을 통과하지 못해 표시하지 않습니다. "
                       "아래 허가정보 원문과 DUR 기준을 확인하세요.", "warning"),
    NO_EVIDENCE: ("공식 허가정보에서 이 항목을 설명할 근거를 찾지 못했습니다. "
                  "DUR 기준 문구와 허가정보 원문을 의료진이 직접 확인해야 합니다.", "warning"),
    EVIDENCE_INVALID: ("근거 데이터 무결성 검사에 실패하여 설명을 생성하지 않았습니다.", "error"),
    LLM_UNAVAILABLE: ("설명 생성 서비스를 사용할 수 없습니다. 탐지 결과와 허가정보 원문은 아래에서 확인할 수 있습니다.", "error"),
    GENERATION_FAILED: ("설명 생성 중 오류가 발생했습니다.", "error"),
    PROCESSING_ERROR: ("이 항목의 근거 검색·설명 처리 중 오류가 발생했습니다. 탐지 결과는 유효합니다.", "error"),
}
LLM_UNAVAILABLE_BANNER = MODE_MESSAGES[LLM_UNAVAILABLE][0]

# Evidence (허가정보 원문) section is shown only in these modes, and only when evidence is non-empty.
EVIDENCE_VISIBLE_MODES = frozenset({EXPLANATION, WITHHELD_DIRECTIVE, WITHHELD_INVALID, LLM_UNAVAILABLE,
                                    GENERATION_FAILED})

# ---------------------------------------------------------------------------------------------------
# Fixed texts
# ---------------------------------------------------------------------------------------------------
EXPLANATION_SECTION_TITLE = "근거 기반 설명 (자동 생성)"
EVIDENCE_TITLE_EXPLANATION = "설명에 사용된 허가정보 근거"
EVIDENCE_TITLE_RAW = "검색된 허가정보 원문 (자동 설명 없음)"
NO_STATEMENTS_TEXT = "근거 원문에서 직접 확인되는 문장이 없습니다."
CLINICIAN_REVIEW_TEXT = "최종 판단은 의료진의 검토가 필요합니다."
DUR_RULE_LABEL = "DUR 기준 (식약처)"
DUR_RULE_EMPTY_TEXT = "DUR 기준 문구 없음"
LOCATION_EMPTY_TEXT = "위치 정보 없음"
BADGE_LEGEND = "색은 DUR 유형 구분이며 임상적 중증도 순서가 아닙니다"
NO_FINDING_TEXT = "현재 시스템이 검토하는 병용금기·노인주의·효능군 중복 범위에서는 탐지된 항목이 없습니다."
INPUT_SCOPE_NOTE_UI = "약물 검색은 평가 범위 밖의 입력 보조 기능입니다"
AGE_MISSING_TEXT = "미입력"
LICENSE_BADGE_TEMPLATE = "허가 상태 확인 필요: {cancel_name}"
LICENSE_BADGE_NO_NAME = "허가 상태 확인 필요"
DEVICE_MISMATCH_TEXT = "평가 조건(GPU)과 다름"

# Phrases that must never appear in any user-facing ViewModel text produced by the adapter.
FORBIDDEN_USER_PHRASES = ("안전합니다", "문제 없음", "문제없음", "이상 없음", "이상없음", "안전함")

# ---------------------------------------------------------------------------------------------------
# Risk types — fixed order is NOT a severity order.
# ---------------------------------------------------------------------------------------------------
RISK_ORDER = ("contraindication", "elderly_caution", "therapeutic_duplication")
RISK_LABEL_KO = {"contraindication": "병용금기", "elderly_caution": "노인주의", "therapeutic_duplication": "효능군 중복"}
RISK_BADGE_ICON = {"contraindication": "🔴", "elderly_caution": "🟠", "therapeutic_duplication": "🟡"}
SCREENING_COUNT_KEYS = {"contraindication": "contraindication_count",
                        "elderly_caution": "elderly_caution_count",
                        "therapeutic_duplication": "therapeutic_duplication_count"}

# ---------------------------------------------------------------------------------------------------
# Elderly check — three states (STREAMLIT_VIEW_MAPPING §1/§2)
# ---------------------------------------------------------------------------------------------------
ELDERLY_AGE_THRESHOLD_TEXT = 65      # tests assert this equals screening.ELDERLY_AGE_THRESHOLD
ELDERLY_STATUS_VIEW = {
    "evaluated": {"label": "평가함", "message": None, "show_count": True},
    "not_applicable_age_below_threshold": {
        "label": "평가 대상 아님 (65세 미만)",
        "message": "65세 미만이므로 노인주의 기준은 적용되지 않습니다.",
        "show_count": False},
    "not_evaluated_age_missing": {
        "label": "평가하지 않음 (나이 미입력)",
        "message": "나이를 입력하지 않아 노인주의는 평가하지 않았습니다. 65세 이상이면 나이를 입력하세요.",
        "show_count": False},
}

# ---------------------------------------------------------------------------------------------------
# evidence_status — label for the EXPLANATION'S evidence basis. NOT a risk level.
# ---------------------------------------------------------------------------------------------------
EVIDENCE_STATUS_LABEL = {
    "SUFFICIENT": "설명 근거: 직접 관련 근거 있음",
    "PARTIAL": "설명 근거: 일부만 관련",
    "INSUFFICIENT": "설명 근거: 직접 관련 근거 없음",
}
EVIDENCE_STATUS_TOOLTIP = ("자동 생성 설명이 검색된 허가정보 근거로 얼마나 직접 뒷받침되는지를 나타냅니다. "
                           "위험도나 중증도를 뜻하지 않습니다.")

# ---------------------------------------------------------------------------------------------------
# Notices derived from report warnings (STREAMLIT_VIEW_MAPPING §9). Codes not listed → dev log only.
# ---------------------------------------------------------------------------------------------------
NOTICE_MESSAGES = {
    "DUPLICATE_INPUTS": ("info", "같은 제품이 중복으로 입력되어 한 번만 검사했습니다."),
    "NOT_FOUND_IN_DUR_TABLES": ("info", "다음 약물은 이 시스템의 DUR 규칙 데이터에 포함되어 있지 않아 "
                                        "규칙 검사 대상이 되지 않았습니다."),
    "ELDERLY_CHECK_NOT_EVALUATED_AGE_MISSING": ("info", ELDERLY_STATUS_VIEW["not_evaluated_age_missing"]["message"]),
}
RETRIEVAL_NOTICE_MESSAGES = {
    "NO_RISK_SPECIFIC_ARTICLE": "검색된 허가정보에 이 위험 유형과 직접 관련된 조항이 없습니다.",
    "SOME_ITEM_SEQ_NOT_IN_CORPUS": "일부 품목은 허가정보 원문 데이터에 없어 검색되지 않았습니다.",
}
USER_WARNING_CODES = frozenset({"DUPLICATE_INPUTS", "NOT_FOUND_IN_DUR_TABLES",
                                "ELDERLY_CHECK_NOT_APPLICABLE_AGE_BELOW_THRESHOLD",
                                "ELDERLY_CHECK_NOT_EVALUATED_AGE_MISSING",
                                "RETRIEVAL_NO_RISK_SPECIFIC_ARTICLE", "RETRIEVAL_SOME_ITEM_SEQ_NOT_IN_CORPUS"})
HANDLED_BY_DISPLAY_MODE_PREFIXES = ("GENERATION_", "DIRECTIVE_LANGUAGE_FLAGGED")

OUTPUT_KEYS = frozenset({"finding_id", "risk_type", "summary", "evidence_statements", "evidence_status",
                         "limitations", "review_note"})

# ---------------------------------------------------------------------------------------------------
# LLM-text checks added in STEP 7-R (reports/STEP7_R_GUARDRAIL_REVALIDATION.md).
# The Core DIRECTIVE_PATTERNS only match fixed strings, and nothing checked LLM text for reassurance or
# for a sentence denying the screening result. These checks judge one sentence at a time, ignore quoted
# label text ('...'), and never relabel risk: a match only withholds the LLM explanation (fail closed).
# Kept deliberately narrow — consult advice ("…중단하지 마세요", "의료진과 상의하세요") and statements about
# what the evidence does or does not say must stay visible.
# ---------------------------------------------------------------------------------------------------
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"|‘[^’]*’|“[^”]*”")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
# Advice / imperative addressed to the reader (label text uses "-한다", so it does not match).
_ADVICE_END = re.compile(r"(세요|십시오|시기\s*바랍니다|기\s*바랍니다|셔야\s*합니다|셔도\s*됩니다|시면\s*됩니다"
                         r"|는\s*것이\s*(좋|바람직))")
# Stopping, skipping or changing the dose of a medicine.
_CHANGE_ACTION = re.compile(r"중단|중지|끊|멈추|멈춰|그만|빼고|줄이|줄여|늘리|늘려|쪼개|반으로|절반|용량을?\s*(바꾸|변경|조절)")
# "중단하지 마세요", "바꾸지 말고" — telling the reader NOT to change on their own is protective, not a directive.
_CHANGE_NEGATED = re.compile(r"(중단|중지|끊|멈추|줄이|늘리|바꾸|변경|조절)(하)?지\s*(마|말)")
# "복용하지 마십시오" — telling the reader not to take a medicine is a stop directive.
_TAKE_NEGATED = re.compile(r"(복용|투여|드시|먹)(하)?지\s*(마|말)")
_REASSURANCE = re.compile(r"안전합니다|안전해요|안전함|괜찮습니다|괜찮아요|걱정(하지\s*않으셔도|할\s*필요가?\s*없)"
                          r"|문제(가|는)?\s*(없습니다|되지\s*않습니다)|이상\s*없습니다|위험(이|은)?\s*없습니다")
_SCREENING_TERM = re.compile(r"병용금기|병용\s*금기|노인주의|노인\s*주의|효능군|중복\s*처방|DUR|Screening|스크리닝")
_DENIAL_END = re.compile(r"(이|가)?\s*아닙니다|해당하지\s*않습니다|해당되지\s*않습니다|탐지되지\s*않았습니다|대상이\s*아닙")
# Sentences about the evidence / label / scope are allowed even when they contain a screening term.
_META_TERM = re.compile(r"근거|허가정보|문구|언급|원문|의미|판단|단정|대체")


def _llm_sentences(output):
    fields = [output.get(k) for k in ("summary", "limitations", "review_note")]
    fields += [s.get("statement") for s in output.get("evidence_statements") or [] if isinstance(s, dict)]
    for text in fields:
        if isinstance(text, str):
            for sent in _SENTENCE_SPLIT.split(_QUOTED.sub("", text)):
                if sent.strip():
                    yield sent


def unsafe_text_reasons(output):
    """Reasons to withhold LLM text for reader-directed medication changes, reassurance or screening denial."""
    reasons = set()
    if not isinstance(output, dict):
        return []
    for sent in _llm_sentences(output):
        if _TAKE_NEGATED.search(sent) and _ADVICE_END.search(sent):
            reasons.add("DIRECTIVE_TEXT")
        elif (_CHANGE_ACTION.search(sent) and _ADVICE_END.search(sent)
              and not _CHANGE_NEGATED.search(sent)):
            reasons.add("DIRECTIVE_TEXT")
        if _REASSURANCE.search(sent):
            reasons.add("REASSURANCE_TEXT")
        if _SCREENING_TERM.search(sent) and _DENIAL_END.search(sent) and not _META_TERM.search(sent):
            reasons.add("SCREENING_DENIAL_TEXT")
    return sorted(reasons)


def decide_display_mode(generation, evidence_ids, finding_id=None, risk_type=None):
    """Return (display_mode, reasons) for one finding. Fail closed.

    EXPLANATION only when ALL hold (contract §0 + defensive allowlist checks that never relabel risk):
      status == GENERATED, no schema/citation errors, no directive flags, output is a dict with exactly
      the 7 OUTPUT_KEYS, string fields are strings, statements are well-formed, evidence_status is in the
      enum and equals generation.evidence_status, finding_id/risk_type match the card, every cited /
      listed E-id exists in this finding's evidence, and unsafe_text_reasons() finds no reader-directed
      medication change (→ WITHHELD_DIRECTIVE), reassurance or screening denial (→ WITHHELD_INVALID).
    `reasons` lists the failed checks (developer log only).
    """
    if not isinstance(generation, dict):
        return PROCESSING_ERROR, ["GENERATION_NOT_A_DICT"]
    status = generation.get("status")
    if status != "GENERATED":
        return STATUS_TO_MODE.get(status, PROCESSING_ERROR), ([] if status in STATUS_TO_MODE
                                                              else [f"UNKNOWN_STATUS:{status!r}"])
    if generation.get("directive_flags"):
        return WITHHELD_DIRECTIVE, ["DIRECTIVE_FLAGS"]
    text_reasons = unsafe_text_reasons(generation.get("output"))
    if "DIRECTIVE_TEXT" in text_reasons:
        return WITHHELD_DIRECTIVE, text_reasons
    reasons = list(text_reasons)
    if generation.get("schema_errors"):
        reasons.append("SCHEMA_ERRORS")
    if generation.get("citation_errors"):
        reasons.append("CITATION_ERRORS")
    o = generation.get("output")
    if not isinstance(o, dict):
        reasons.append("OUTPUT_NOT_A_DICT")
    else:
        if set(o) != OUTPUT_KEYS:
            reasons.append("OUTPUT_KEYS")
        for k in ("finding_id", "risk_type", "summary", "evidence_status", "limitations", "review_note"):
            if k in o and not isinstance(o[k], str):
                reasons.append(f"TYPE:{k}")
        if isinstance(o.get("summary"), str) and not o["summary"].strip():
            reasons.append("EMPTY_SUMMARY")
        if o.get("evidence_status") not in EVIDENCE_STATUS_LABEL:
            reasons.append("EVIDENCE_STATUS_ENUM")
        if generation.get("evidence_status") != o.get("evidence_status"):
            reasons.append("EVIDENCE_STATUS_MISMATCH")
        if finding_id is not None and o.get("finding_id") != finding_id:
            reasons.append("FINDING_ID_MISMATCH")
        if risk_type is not None and o.get("risk_type") != risk_type:
            reasons.append("RISK_TYPE_MISMATCH")
        stmts = o.get("evidence_statements")
        ok_stmts = isinstance(stmts, list) and all(
            isinstance(s, dict) and set(s) == {"statement", "evidence_ids"} and isinstance(s["statement"], str)
            and isinstance(s["evidence_ids"], list) and all(isinstance(i, str) for i in s["evidence_ids"])
            for s in stmts)
        if not ok_stmts:
            reasons.append("STATEMENTS_SHAPE")
        else:
            known = set(evidence_ids)
            listed = {i for s in stmts for i in s["evidence_ids"]}
            if listed - known:
                reasons.append("UNKNOWN_EVIDENCE_ID_IN_STATEMENT")
    cited = generation.get("cited_evidence_ids") or []
    if not isinstance(cited, list) or set(cited) - set(evidence_ids):
        reasons.append("UNKNOWN_CITED_EVIDENCE_ID")
    if reasons:
        # GENERATED but not allowlisted for a reason other than directive flags. Unreachable with the
        # frozen Core (validate_output turns these into INVALID_OUTPUT); fail closed as WITHHELD_INVALID.
        return WITHHELD_INVALID, reasons
    return EXPLANATION, []
