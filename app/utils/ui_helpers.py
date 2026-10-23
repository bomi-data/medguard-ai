"""Pure presentation helpers for the MEDGUARD dashboard (no Streamlit import → unit-testable).

Everything here is derived from the SafetyCheckViewModel (built by app.adapters from the Frozen Core report)
or from audit result files read by app.utils.audit_reader. Nothing here makes a medical judgement:

  * cell / card statuses only restate what the ViewModel says (a finding exists, the product is / is not in
    the DUR rule tables, the elderly check was / was not evaluated);
  * "no rule found" is never rendered as "safe" (see FORBIDDEN_UI_PHRASES and tests/test_medguard_dashboard.py);
  * different coverage sets are never summed (each metric is shown with its own numerator / denominator).
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from app import ui_policy as P

# ------------------------------------------------------------------------------------------------ text
FORBIDDEN_UI_PHRASES = P.FORBIDDEN_USER_PHRASES + ("모든 약물의 위험을 확인", "위험이 없습니다", "위험 없음")

PROTOTYPE_NOTICE = ("의료진의 판단을 대체하지 않는 의사결정 지원용 프로토타입입니다. "
                    "실제 처방·복약 변경 판단에 사용하지 마세요.")
GATE_NOT_CLINICAL_NOTE = ("Gate의 PASS는 분석 파이프라인의 검사 항목이 충족되었다는 뜻이며, "
                          "임상적 안전성 검증 완료를 의미하지 않습니다.")
NO_RULE_NOT_SAFE_NOTE = "'규칙 없음·미포함'은 '안전'과 다른 의미입니다. 규칙 데이터가 없으면 위험 여부를 판단할 수 없습니다."
INCOMPLETE_LIMIT_TEXT = ("일부 의약품의 DUR 규칙 포함 여부가 확인되지 않거나 일부 항목이 평가되지 않아 "
                         "전체 안전성을 판단할 수 없습니다.")
SOURCE_TAGS = {
    "RULE": "RULE-BASED RESULT",
    "EVIDENCE": "RETRIEVED EVIDENCE",
    "LLM": "LLM-GENERATED EXPLANATION",
    "AUDIT": "AUDIT RESULT",
    "UNKNOWN": "UNKNOWN / NOT EVALUATED",
}


def stretch() -> dict:
    """Full-width kwarg that works across Streamlit versions (`width="stretch"` replaced `use_container_width`)."""
    try:
        import streamlit as _st
        major, minor = (int(x) for x in _st.__version__.split(".")[:2])
        if (major, minor) >= (1, 49):
            return {"width": "stretch"}
    except Exception:                                      # noqa: BLE001
        pass
    return {"use_container_width": True}


def esc(x: Any) -> str:
    """HTML-escape any dynamic value (DUR text, product names, LLM text, file contents)."""
    return html.escape("" if x is None else str(x), quote=True)


def fmt_int(n) -> str:
    return "N/A" if n is None else f"{int(n):,}"


def fmt_ratio(num, den) -> str:
    """'a / b (p%)'. N/A when the denominator is missing or zero (never a made-up percentage)."""
    if num is None or den in (None, 0):
        return "N/A"
    return f"{fmt_int(num)} / {fmt_int(den)} ({100.0 * float(num) / float(den):.2f}%)"


def pct_value(num, den) -> Optional[float]:
    if num is None or den in (None, 0):
        return None
    return 100.0 * float(num) / float(den)


def tag(kind: str) -> str:
    """Small 'what kind of information is this' chip."""
    return f'<span class="mg-tag mg-tag-{kind.lower()}">{esc(SOURCE_TAGS[kind])}</span>'


def badge(text: str, tone: str, title: str = "") -> str:
    t = f' title="{esc(title)}"' if title else ""
    return f'<span class="mg-badge mg-{esc(tone)}"{t}>{esc(text)}</span>'


# ------------------------------------------------------------------------------------------------ icons
# Lucide-style stroke icons (24x24 viewBox, stroke currentColor). Decorative; shapes are simplified.
_ICON_PATHS = {
    "dashboard": '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/>'
                 '<rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
    "pill": '<path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"/><path d="m8.5 8.5 7 7"/>',
    "play": '<circle cx="12" cy="12" r="9"/><path d="m10 8 6 4-6 4V8Z"/>',
    "result": '<rect x="8" y="2" width="8" height="4" rx="1"/>'
              '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
              '<path d="M9 12h6M9 16h4"/>',
    "gate": '<path d="M12 3 4 6v6c0 4.5 3.2 8 8 9 4.8-1 8-4.5 8-9V6l-8-3Z"/><path d="m9 12 2 2 4-4"/>',
    "database": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/>'
                '<path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    "report": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/><path d="M14 3v5h5"/>'
              '<path d="M9 13h6M9 17h6"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.9 4.9 7 7M17 17l2.1 2.1M2 12h3M19 12h3'
                'M4.9 19.1 7 17M17 7l2.1-2.1"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    "doc": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"/><path d="M14 3v5h5"/>',
    "alert": '<path d="m10.3 3.9-8.5 14.7A2 2 0 0 0 3.5 21.5h17a2 2 0 0 0 1.7-2.9L13.7 3.9a2 2 0 0 0-3.4 0Z"/>'
             '<path d="M12 9v4M12 17h.01"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M21.5 20a6.5 6.5 0 0 0-4-6"/>',
    "layers": '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 5 .5c0 1.7-2.5 2-2.5 3.5M12 17h.01"/>',
}


def icon(name: str, size: int = 18) -> str:
    p = _ICON_PATHS.get(name, _ICON_PATHS["help"])
    return (f'<svg class="mg-ico" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{p}</svg>')


# ------------------------------------------------------------------------------------------------ navigation
NAV_ITEMS = (
    ("dashboard", "대시보드", "dashboard"),
    ("search", "의약품 검색", "pill"),
    ("run", "분석 실행", "play"),
    ("result", "분석 결과", "result"),
    ("gates", "게이트별 상세", "gate"),
    ("coverage", "데이터 커버리지", "database"),
    ("report", "보고서 생성", "report"),
    ("settings", "설정", "settings"),
)
NAV_KEYS = tuple(k for k, _, _ in NAV_ITEMS)


# ------------------------------------------------------------------------------------------------ analysis status
ANALYSIS_STATUS = {
    "READY": ("READY", "neutral", "분석 실행 가능 — 아직 실행하지 않았습니다."),
    "RUNNING": ("RUNNING", "info", "분석 실행 중입니다."),
    "COMPLETED": ("COMPLETED", "ok", "분석이 끝났고 평가하지 못한 항목이 없습니다. (안전성 판정이 아닙니다)"),
    "PARTIAL": ("PARTIAL", "warn", "분석은 끝났지만 일부 항목이 평가되지 않았거나 확인이 필요합니다."),
    "FAILED": ("FAILED", "danger", "분석을 완료하지 못했습니다. 결과가 없는 상태이며 위험이 없다는 의미가 아닙니다."),
}


def evaluation_limits(vm) -> list:
    """Reasons why the screening of this selection is not a complete evaluation. Facts from the ViewModel only."""
    if vm is None or not vm.can_display_results:
        return []
    out = []
    n_missing = sum(1 for m in vm.medications if not m.in_dur_tables)
    if n_missing:
        out.append(f"DUR 규칙 데이터 미포함 약물 {n_missing}개 (규칙 검사 대상이 아님)")
    if vm.patient and vm.patient.elderly.code != "evaluated":
        out.append(f"노인주의: {vm.patient.elderly.label}")
    if len(vm.medications) < 2:
        out.append("약물 1개 — 병용금기·효능군 중복은 2개 이상 선택해야 평가됨")
    n_l4 = sum(1 for e in vm.errors if e.layer == P.L4_FINDING)
    if n_l4:
        out.append(f"일부 항목의 근거 검색·설명 처리 오류 {n_l4}건 (탐지 결과 자체는 유효)")
    return out


def analysis_status(runtime_ready: bool, vm, running: bool = False) -> tuple:
    """READY / RUNNING / COMPLETED / PARTIAL / FAILED — from the actual runtime and ViewModel state."""
    if running:
        return ANALYSIS_STATUS["RUNNING"]
    if not runtime_ready:
        return ANALYSIS_STATUS["FAILED"]
    if vm is None:
        return ANALYSIS_STATUS["READY"]
    if vm.state == P.STATE_INPUT_INVALID:
        return ANALYSIS_STATUS["READY"]                    # Core was not called; the input message explains why
    if not vm.can_display_results:
        return ANALYSIS_STATUS["FAILED"]
    if evaluation_limits(vm):
        return ANALYSIS_STATUS["PARTIAL"]
    return ANALYSIS_STATUS["COMPLETED"]


@dataclass(frozen=True)
class CombinationStatus:
    code: str          # NOT_RUN | FAILED | FOUND | PARTIAL | NONE_FOUND
    label: str
    tone: str          # neutral | danger | warn | info | muted
    limits: tuple = ()
    limitation_text: Optional[str] = None


def combination_status(vm) -> CombinationStatus:
    """[A] status of THIS patient / medication combination (Screening Engine result). Not the Audit OPTION."""
    if vm is None:
        return CombinationStatus("NOT_RUN", "분석 전", "neutral",
                                 limitation_text="약물을 선택하고 'DUR 안전성 검사 실행'을 누르세요.")
    if vm.state == P.STATE_INPUT_INVALID:
        return CombinationStatus("INPUT_INVALID", "입력 확인 필요", "warn",
                                 limitation_text="입력값 오류로 검사가 실행되지 않았습니다. 결과가 없는 상태이며 위험이 없다는 의미가 아닙니다.")
    if not vm.can_display_results:
        return CombinationStatus("FAILED", "분석 실패", "danger",
                                 limitation_text="결과를 표시할 수 없는 상태입니다. 위험이 없다는 의미가 아닙니다.")
    limits = tuple(evaluation_limits(vm))
    n = vm.summary.total_signals
    if n > 0:
        return CombinationStatus("FOUND", "주의 항목 발견", "warn", limits,
                                 INCOMPLETE_LIMIT_TEXT if limits else None)
    if limits:
        return CombinationStatus("PARTIAL", "일부 항목 평가 불가", "info", limits, INCOMPLETE_LIMIT_TEXT)
    return CombinationStatus("NONE_FOUND", "확인된 규칙 없음", "muted", (),
                             "검토 범위(병용금기·노인주의·효능군 중복)의 DUR 규칙에서 탐지된 항목이 없다는 뜻이며, "
                             "그 밖의 상호작용·위험은 이 시스템이 평가하지 않습니다.")


# ------------------------------------------------------------------------------------------------ KPI cards
KPI_META = {
    "contraindication": ("병용금기", "danger", "alert"),
    "elderly_caution": ("노인주의", "amber", "users"),
    "therapeutic_duplication": ("효능군 중복", "blue", "layers"),
}


def kpi_cards(vm) -> list:
    """Four small KPI cards. Counts are the Core's own; 'not evaluated' is never shown as 0."""
    cards = []
    for rt in P.RISK_ORDER:
        label, tone, ico = KPI_META[rt]
        if vm is None:
            cards.append(dict(key=rt, label=label, tone=tone, icon=ico, value="—", desc="분석 전", sub=""))
        elif not vm.can_display_results:
            cards.append(dict(key=rt, label=label, tone=tone, icon=ico, value="—",
                              desc="검사 미실행 (입력 확인)" if vm.state == P.STATE_INPUT_INVALID else "조회 실패", sub=""))
        else:
            t = next(t for t in vm.summary.tiles if t.risk_type == rt)
            if t.count is None:
                cards.append(dict(key=rt, label=label, tone=tone, icon=ico, value="—", desc=t.display_text, sub=""))
            elif t.count == 0:
                cards.append(dict(key=rt, label=label, tone=tone, icon=ico, value="0건", desc="규칙 조회 완료, 발견 0건",
                                  sub=""))
            else:
                cards.append(dict(key=rt, label=label, tone=tone, icon=ico, value=f"{t.count}건",
                                  desc=f"규칙 조회 완료, 발견 {t.count}건", sub=""))
    # 4th card: items the user must check (facts only; its own definition, not a sum with the three above)
    if vm is None:
        cards.append(dict(key="review", label="추가 확인 필요", tone="purple", icon="help", value="—", desc="분석 전", sub=""))
    elif not vm.can_display_results:
        cards.append(dict(key="review", label="추가 확인 필요", tone="purple", icon="help", value="—", desc="판단 불가", sub=""))
    else:
        n_missing = sum(1 for m in vm.medications if not m.in_dur_tables)
        other = [x for x in evaluation_limits(vm) if not x.startswith("DUR 규칙 데이터 미포함")]
        cards.append(dict(key="review", label="추가 확인 필요", tone="purple", icon="help",
                          value=f"{n_missing}개" if n_missing else "0개",
                          desc="규칙 데이터 미포함 약물" if n_missing else "규칙 데이터 미포함 약물 없음",
                          sub=" · ".join(other)))
    return cards


# ------------------------------------------------------------------------------------------------ safety matrix
CELL_STATUS = {
    "FOUND": ("규칙 발견", "found"),
    "NONE_FOUND": ("규칙 조회 완료 / 발견 없음", "none"),
    "NOT_IN_DATA": ("데이터 미포함", "nodata"),
    "UNDETERMINED": ("판단 불가", "undet"),
    "FAILED_LOOKUP": ("조회 실패", "fail"),
}


def matrix_rows(vm) -> list:
    """Drug × category cell statuses. Returns [] when there is no ViewModel (analysis not run)."""
    if vm is None:
        return []
    rows = []
    cats = P.RISK_ORDER
    if vm.state == P.STATE_INPUT_INVALID:
        return [{"item_seq": None, "name": "(검사 미실행)",
                 "cells": {c: dict(status="UNDETERMINED", count=0, tip="입력값 오류로 검사가 실행되지 않았습니다.") for c in cats}}]
    if not vm.can_display_results:
        return [{"item_seq": None, "name": "(검사 실패)",
                 "cells": {c: dict(status="FAILED_LOOKUP", count=0, tip="조회 실패") for c in cats}}]
    hits = {c: {} for c in cats}
    for f in vm.findings:
        for d in f.drugs:
            hits[f.risk_type][d.item_seq] = hits[f.risk_type].get(d.item_seq, 0) + 1
    elderly_code = vm.patient.elderly.code
    n_meds = len(vm.medications)
    for m in vm.medications:
        cells = {}
        for c in cats:
            if not m.in_dur_tables:
                st_, tip = "NOT_IN_DATA", "이 약물은 DUR 규칙 데이터에 포함되어 있지 않아 규칙 검사 대상이 아닙니다. 안전하다는 의미가 아닙니다."
            elif c == "elderly_caution" and elderly_code != "evaluated":
                st_ = "UNDETERMINED"
                tip = vm.patient.elderly.message or vm.patient.elderly.label
            elif c != "elderly_caution" and n_meds < 2:
                st_, tip = "UNDETERMINED", "병용·중복 규칙은 약물을 2개 이상 선택해야 평가됩니다."
            elif hits[c].get(m.item_seq):
                st_, tip = "FOUND", f"{P.RISK_LABEL_KO[c]} 규칙 {hits[c][m.item_seq]}건에 이 약물이 포함됩니다."
            else:
                st_, tip = "NONE_FOUND", "규칙 조회를 완료했고 이 약물이 포함된 항목은 발견되지 않았습니다. 이는 안전 판정이 아닙니다."
            cells[c] = dict(status=st_, count=hits[c].get(m.item_seq, 0) if st_ == "FOUND" else 0, tip=tip)
        rows.append({"item_seq": m.item_seq, "name": m.display_name, "cells": cells})
    return rows


# ------------------------------------------------------------------------------------------------ findings list
@dataclass(frozen=True)
class FindingRow:
    kind: str                  # finding | not_in_data | elderly_not_evaluated
    title: str
    desc: str
    badge_text: str
    badge_tone: str            # danger | amber | blue | gray | purple
    finding_id: Optional[str] = None
    item_seqs: tuple = ()


_RISK_BADGE_TONE = {"contraindication": "danger", "elderly_caution": "amber", "therapeutic_duplication": "blue"}


def finding_rows(vm) -> list:
    """Rows for '주요 발견 사항': only real findings and real, ViewModel-reported gaps. Nothing is added."""
    if vm is None or not vm.can_display_results:
        return []
    rows = []
    for f in vm.findings:
        names = " + ".join(d.display_name for d in f.drugs) or "(약물 정보 없음)"
        first = f.dur_rule_lines[0] if f.dur_rule_lines else ""
        desc = f"{f.risk_label} 규칙 발견" + (f" — {first}" if first and first != P.DUR_RULE_EMPTY_TEXT else "")
        rows.append(FindingRow("finding", names, desc, f.risk_label, _RISK_BADGE_TONE[f.risk_type],
                               f.finding_id, tuple(d.item_seq for d in f.drugs)))
    for m in vm.medications:
        if not m.in_dur_tables:
            rows.append(FindingRow("not_in_data", m.display_name, "규칙 데이터 미포함 — 규칙 검사 대상이 아님",
                                   "확인 필요", "purple", None, (m.item_seq,)))
    if vm.patient and vm.patient.elderly.code == "not_evaluated_age_missing":
        rows.append(FindingRow("elderly_not_evaluated", "노인주의 미평가", vm.patient.elderly.message or "", "확인 필요",
                               "purple"))
    return rows


# ------------------------------------------------------------------------------------------------ table / evidence
def ingredient_map(vm) -> dict:
    """item_seq → ingredient names, only where the Core finding carried them (otherwise unknown)."""
    out = {}
    if vm is None or not vm.can_display_results:
        return out
    for f in vm.findings:
        for d in f.drugs:
            if d.ingredient_names:
                out.setdefault(d.item_seq, [])
                for n in d.ingredient_names:
                    if n not in out[d.item_seq]:
                        out[d.item_seq].append(n)
    return out


def drug_table_rows(vm) -> list:
    """One dict per selected medication for the detail table."""
    if vm is None or not vm.can_display_results:
        return []
    ing = ingredient_map(vm)
    by_seq = {}
    for f in vm.findings:
        for d in f.drugs:
            by_seq.setdefault(d.item_seq, []).append(f.risk_label)
    rows = []
    for m in vm.medications:
        labels = []
        for x in by_seq.get(m.item_seq, []):
            if x not in labels:
                labels.append(x)
        if labels:
            main = ", ".join(labels)
        elif not m.in_dur_tables:
            main = "규칙 데이터 미포함"
        else:
            main = "발견된 항목 없음 (규칙 조회 완료)"
        rows.append({
            "제품명": m.display_name,
            "성분명": ", ".join(ing[m.item_seq]) if m.item_seq in ing else "확인 불가 (결과에 성분 정보 없음)",
            "itemSeq": m.item_seq,
            "주요 발견 사항": main,
            "DUR 포함 상태": "DUR 규칙 데이터 포함" if m.in_dur_tables else "데이터 미포함",
            "분석 상태": "평가됨" if m.in_dur_tables else "규칙 검사 대상 아님",
        })
    return rows


def evidence_docs(vm) -> list:
    """Retrieved evidence documents (RAG), flattened across findings. Nothing generated here."""
    docs = []
    if vm is None or not vm.can_display_results:
        return docs
    dbg = {d["finding_id"]: d for d in (vm.debug.findings or ())}
    for f in vm.findings:
        if f.evidence is None:
            continue
        ev_dbg = {e["evidence_id"]: e for e in (dbg.get(f.finding_id, {}).get("evidence_dev_fields") or [])}
        for e in f.evidence.items:
            dev = ev_dbg.get(e.evidence_id, {})
            docs.append(dict(
                finding_id=f.finding_id, risk_label=f.risk_label, evidence_id=e.evidence_id,
                title=f"{e.display_name} · {e.location}", source=e.evidence_source, change_date=e.change_date,
                ev_type=e.location.split(" / ")[0] if e.location else "허가정보", chunk_text=e.chunk_text,
                related=", ".join(d.display_name for d in f.drugs), cited=e.cited,
                license_badge=e.license_badge, shared=e.shared_item_seqs,
                document_id=dev.get("document_id"), chunk_id=dev.get("chunk_id"),
                hybrid_rank=dev.get("hybrid_rank"), bm25_rank=dev.get("bm25_rank"), dense_rank=dev.get("dense_rank")))
    return docs


# ------------------------------------------------------------------------------------------------ search states
SEARCH_STATES = {
    "RULE_PRESENT": ("검색 가능 · DUR 규칙 데이터 포함", "info"),
    "NO_RULE": ("검색 가능 · DUR 규칙 데이터 없음", "gray"),
    "NOT_SEARCHABLE": ("검색 불가", "danger"),
    "LOAD_FAILED": ("데이터 로딩 실패", "danger"),
    "ID_UNCONFIRMED": ("식별자 불일치 또는 확인 불가", "purple"),
}
_NINE = re.compile(r"\d{9}")


def candidate_state(c: dict) -> str:
    return "RULE_PRESENT" if c.get("in_dur_tables") else "NO_RULE"


def query_state(query: str, result: Optional[dict], runtime_ready: bool, search_error: bool) -> Optional[str]:
    """State to show when a search produced no usable candidate list (None → candidates are shown)."""
    if not runtime_ready or search_error:
        return "LOAD_FAILED"
    if result is None:
        return None
    if result.get("candidates"):
        return None
    q = (query or "").strip()
    if q.isdigit() and not _NINE.fullmatch(q):
        return "ID_UNCONFIRMED"
    if _NINE.fullmatch(q):
        return "ID_UNCONFIRMED"          # 9 digits but not a known item_seq
    return "NOT_SEARCHABLE"


# ------------------------------------------------------------------------------------------------ report export
def build_report_json(vm, audit: Optional[dict]) -> str:
    payload = {
        "report_type": "MEDGUARD AI analysis export",
        "notice": PROTOTYPE_NOTICE,
        "screening": None if vm is None else vm.to_dict(include_debug=False),
        "audit": audit,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def build_report_markdown(vm, audit: Optional[dict]) -> str:
    L = ["# MEDGUARD AI — 분석 내보내기", "", f"> {PROTOTYPE_NOTICE}", ""]
    L += ["## 1. 환자·약물 조합 분석 (RULE-BASED RESULT)", ""]
    if vm is None:
        L += ["분석을 실행하지 않았습니다.", ""]
    elif not vm.can_display_results:
        L += [f"분석 상태: {vm.state} — 결과를 표시할 수 없습니다. 위험이 없다는 의미가 아닙니다.", ""]
    else:
        cs = combination_status(vm)
        L += [f"- 상태: **{cs.label}**", f"- 나이: {vm.patient.age_display} · 노인주의: {vm.patient.elderly.label}"]
        L += ["- 선택 약물:"]
        for m in vm.medications:
            L += [f"  - {m.display_name} ({m.item_seq})" + ("" if m.in_dur_tables else " — DUR 규칙 데이터 미포함")]
        L += ["", "| 유형 | 결과 |", "|---|---|"]
        for t in vm.summary.tiles:
            L += [f"| {t.label} | {t.display_text} |"]
        L += ["", f"_{vm.summary.legend}_", ""]
        if cs.limitation_text:
            L += [f"**제한 사항**: {cs.limitation_text}", ""]
        for x in cs.limits:
            L += [f"- {x}"]
        L += ["", "### 발견 항목", ""]
        if not vm.findings:
            L += [vm.no_finding.message if vm.no_finding else "탐지된 항목 없음", ""]
        for i, f in enumerate(vm.findings, 1):
            L += [f"{i}. **{f.risk_label}** — " + " + ".join(d.display_name for d in f.drugs)]
            L += [f"   - 규칙 출처: {f.rule_source or '확인 불가'}"]
            for ln in f.dur_rule_lines:
                L += [f"   - {f.dur_rule_label}: {ln}"]
            if f.explanation is not None:
                L += ["   - [LLM-GENERATED EXPLANATION] " + f.explanation.summary]
            elif f.status_message:
                L += [f"   - 설명 상태: {f.status_message}"]
        L += [""]
        docs = evidence_docs(vm)
        L += ["### 검색된 근거 (RETRIEVED EVIDENCE)", ""]
        if not docs:
            L += ["현재 검색된 근거 자료가 없습니다.", ""]
        for d in docs:
            L += [f"- [{d['evidence_id']}] {d['title']} — 출처: {d['source']}"]
        L += [""]
    L += ["## 2. Coverage Audit (AUDIT RESULT)", ""]
    if not audit:
        L += ["선택된 Audit 실행 기록이 없습니다.", ""]
    else:
        L += [f"- Audit 실행: {audit.get('run_name')}",
              f"- 구현 가능성 판정: {audit.get('option_text') or audit.get('option')} (환자 안전성 판정이 아님)",
              f"- Gate: " + ", ".join(f"GATE {k} {v}" for k, v in (audit.get('gates') or {}).items()),
              f"- 자동 적용: {audit.get('auto_apply')} · 엔진 변경 허용: {audit.get('engine_change_allowed')}", ""]
    L += [GATE_NOT_CLINICAL_NOTE, NO_RULE_NOT_SAFE_NOTE, ""]
    return "\n".join(L)
