"""MEDGUARD AI app_v2 (STEP 17) — 기존 대시보드 + 성분 중복 후보 확인(통합 Screening).

실행:  streamlit run ui_integration/app_v2.py --theme.base dark

설계 (기존 파일은 수정하지 않음 — 이 파일은 새 파일입니다)
  Streamlit(app_v2.py) → ingredient_dur_ui_adapter.screen_for_ui → [DUR Screening + Ingredient Screening(16번 검증 코드)] → 구조화 JSON → 화면 렌더링
  · 이 파일은 *표시만* 합니다. 판정·유형·건수를 계산하거나 바꾸지 않습니다(모두 어댑터 결과 그대로).
  · 기존 11번 대시보드(app/medguard_dashboard.py)의 컴포넌트(검색·선택·나이·DUR 결과·RAG 근거·LLM 설명·Gate·Coverage)를 그대로 불러 씁니다.
  · 기존 RAG/LLM 호출 경로(drug_search.run_check → adapters.run_safety_check_view → Frozen Core)는 그대로 호출하며 프롬프트·인자를 바꾸지 않습니다.
  · 성분 후보 결과는 RAG/LLM에 전달하지 않습니다(템플릿 기반 표시).
  · 기존 app/medguard_dashboard.py, app/streamlit_main.py 는 그대로 독립 실행됩니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent                                   # 프로젝트 루트 (ui_integration/ 의 상위)
for _p in (_ROOT, _ROOT / "src", _HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import streamlit as st  # noqa: E402

from app import adapters, ui_runtime  # noqa: E402
from app.components import (coverage_page, drug_search, drug_table, evidence_panel, findings, gate_timeline,  # noqa: E402
                            header, pages, safety_matrix, sidebar, summary_cards)
from app.utils import audit_reader as AR  # noqa: E402
from app.utils import ui_helpers as H  # noqa: E402
import ingredient_dur_ui_adapter as IA  # noqa: E402

st.set_page_config(page_title="MEDGUARD AI", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")

CSS_PATH = _ROOT / "app" / "styles" / "medguard.css"
EXTRA_CSS = """
.mg-int-note{font-size:12.5px;line-height:1.55;opacity:.92;margin:4px 0 8px 0}
.mg-int-warn{border-left:3px solid #E5A93B;padding:6px 10px;margin:6px 0;background:rgba(229,169,59,.08);font-size:13px}
.mg-int-info{border-left:3px solid #3687FF;padding:6px 10px;margin:6px 0;background:rgba(54,135,255,.08);font-size:13px}
.mg-int-err{border-left:3px solid #E5484D;padding:6px 10px;margin:6px 0;background:rgba(229,72,77,.10);font-size:13px}
"""

# [17c:patch-applied] 상단 KPI '성분 중복 후보' 카드 + 하단 상세 영역 정리
NOT_DUR_TITLE = "의약품 성분정보 및 중복 후보 상세"
EXTRA_CSS += """
.mg-kpis{display:grid !important;grid-template-columns:repeat(auto-fit,minmax(172px,1fr)) !important;gap:12px}
.mg-kpi.mg-kpi-ing{border:1px solid rgba(167,139,250,.55);background:linear-gradient(180deg,rgba(124,92,255,.14),rgba(124,92,255,.04))}
.mg-kpi.mg-kpi-ing .mg-kpi-value{color:#B9A4FF;overflow-wrap:anywhere;word-break:keep-all}
.mg-kpi.mg-kpi-ing .mg-kpi-desc,.mg-kpi.mg-kpi-ing .mg-kpi-sub{overflow-wrap:anywhere;word-break:keep-all}
.mg-kpi.mg-kpi-ing .mg-kpi-tagline{font-size:11.5px;opacity:.85;margin-top:6px;color:#CBBDFF}
.mg-kpi .mg-kpi-label{overflow-wrap:anywhere}
"""
PRIVACY_NOTICE = "연구·데모용 화면입니다. 실제 환자의 개인정보를 입력하지 마세요."
GROUPS = (("contraindications", "병용금기"), ("elderly_cautions", "노인주의"), ("therapeutic_duplicates", "효능군 중복"))


def load_css() -> str:
    try:
        css = CSS_PATH.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001 — 스타일 없이도 기능은 동작
        css = ""
    css += EXTRA_CSS
    return "\n".join(ln for ln in css.splitlines() if ln.strip())


@st.cache_resource(show_spinner="DUR 데이터와 모델을 불러오는 중입니다 (처음 1회, 수 분 소요)…")
def get_runtime():
    return ui_runtime.load_runtime()


@st.cache_resource(show_spinner="통합 Screening 엔진(DUR + 성분 후보)을 불러오는 중입니다 (처음 1회)…")
def get_integration():
    return IA.load_engine(ui_runtime.project_root())


def init_state(ss):
    ss.setdefault("page", "dashboard")
    ss.setdefault("selection", adapters.MedicationSelection())
    ss.setdefault("candidates", None)
    ss.setdefault("search_error", False)
    ss.setdefault("last_query", "")
    ss.setdefault("vm", None)
    ss.setdefault("vm_sig", None)
    ss.setdefault("age", None)
    ss.setdefault("age_unknown", False)
    ss.setdefault("running", False)
    ss.setdefault("developer", False)
    ss.setdefault("integ", None)            # screen_for_ui 결과 (어댑터가 만든 구조화 결과)
    ss.setdefault("integ_sig", None)
    ss.setdefault("existing_run_error", None)


# ------------------------------------------------------------------------------------------------ 실행
def _clean_age(ss):
    if ss.get("age_unknown"):
        return None
    a = ss.get("age")
    if isinstance(a, float) and a.is_integer():
        return int(a)
    return a


def run_integrated(st_, ss, rt, engine, status_ph, render_status):
    """[통합 Screening 실행]: ① 통합 엔진(DUR + 성분 후보) ② 기존 DUR/RAG/LLM 경로를 기존 방식 그대로 호출."""
    sig = drug_search.current_sig(ss)
    items = list(ss.selection.items)
    with st_.spinner("통합 Screening 중입니다…"):
        ss.integ = IA.screen_for_ui(engine, items, _clean_age(ss))         # 예외를 던지지 않음
        ss.integ_sig = sig
    ss.existing_run_error = None
    if rt is not None and rt.ready:
        try:
            drug_search.run_check(st_, ss, rt, status_ph, render_status)       # 기존 경로 그대로 (내부에서 rerun)
        except Exception as e:  # noqa: BLE001 — 기존 경로 실패가 통합 결과 표시를 막지 않게 함
            ss.existing_run_error = f"{type(e).__name__}: {str(e)[:200]}"
            st_.rerun()
    else:
        st_.rerun()


def render_run_button(st_, ss, rt, engine, status_ph, render_status, key):
    with st_.container(border=True):
        st_.markdown('<div class="mg-card-head"><h3 class="mg-card-title">통합 Screening</h3></div>', unsafe_allow_html=True)
        st_.caption("DUR 공식 규칙 확인과 성분 중복 후보 확인을 함께 실행합니다. 기존 근거 검색·설명 기능도 같은 방식으로 실행됩니다.")
        if st_.button("통합 Screening 실행", key=key, type="primary", **H.stretch()):      # 엔진이 없어도 누를 수 있고, 그 경우 '기술적 오류'로 이유를 보여 준다
            run_integrated(st_, ss, rt, engine, status_ph, render_status)
        st_.markdown(f'<div class="mg-int-note">{H.esc(PRIVACY_NOTICE)}</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------------------------------------ 렌더링 (표시 전용)
def _names(xs):
    return " + ".join(str(x) for x in xs if x) or "—"


def _render_status(st_, ss, engine, model, stale):
    with st_.container(border=True):
        st_.markdown('<div class="mg-card-head"><h3 class="mg-card-title">통합 Screening 상태</h3></div>', unsafe_allow_html=True)
        if engine is not None and not engine.ready:
            st_.error(engine.error_user or "통합 Screening 엔진을 불러오지 못했습니다.")
            if ss.get("developer") and engine.error_dev:
                st_.code(engine.error_dev)
        if ss.get("existing_run_error"):
            st_.warning("기존 DUR/근거 검색 경로에서 오류가 발생했습니다(통합 결과 표시와는 별개): " + H.esc(ss.existing_run_error))
        if stale:
            st_.info("선택한 약물 또는 나이가 바뀌었습니다. 이전 통합 결과를 숨겼습니다. 다시 '통합 Screening 실행'을 누르세요.")
            return False
        label, tone, tip = model["badge"]
        st_.markdown(H.badge(label, tone, tip) + f'<div class="mg-int-note">{H.esc(tip)}</div>', unsafe_allow_html=True)
        if model["technical_errors"]:
            st_.markdown('<div class="mg-int-err"><b>기술적 오류</b> — 의학 정보가 부족해서 생긴 상태가 아니라 처리 과정의 오류입니다. 검사를 완료한 것으로 표시하지 않습니다.</div>',
                         unsafe_allow_html=True)
            for e in model["technical_errors"]:
                st_.caption(f"단계 {e['stage']} · {e['type']}" + (f" · {e['message']}" if ss.get("developer") else ""))
        if model.get("age_notice"):
            st_.markdown(f'<div class="mg-int-warn">{H.esc(model["age_notice"])}</div>', unsafe_allow_html=True)
        prods = model.get("products")
        if prods:
            if prods["unresolved_products"]:
                st_.markdown('<div class="mg-int-warn"><b>식별하지 못한 제품</b>: ' + H.esc(", ".join(u["item_seq"] for u in prods["unresolved_products"])) +
                             " — 허가정보/DUR 데이터에서 찾지 못했습니다(안전한 의약품으로 판정하지 않음).</div>", unsafe_allow_html=True)
            for r in prods["resolved_products"]:
                if r["ingredient_info_status"] not in ("SCREENABLE",):
                    st_.caption(f"성분 정보 상태 — {r['item_name']} ({r['item_seq']}): {r['ingredient_info_status']}")
        for code, detail in model.get("processing") or []:
            if code == "DUPLICATE_ITEM_SEQ_REMOVED":
                st_.caption("중복 선택된 제품은 1개로 합쳐 처리했습니다: " + H.esc(str(detail)))
        return model["state"] != "NOT_RUN"


def _render_dur(st_, model):
    d = model["dur"]
    with st_.container(border=True):
        st_.markdown('<div class="mg-card-head"><h3 class="mg-card-title">DUR 공식 규칙 확인</h3></div>', unsafe_allow_html=True)
        st_.markdown(H.tag("RULE"), unsafe_allow_html=True)
        if d is None:
            st_.info("DUR 결과를 표시할 수 없습니다(처리되지 않음). 위험이 없다는 의미가 아닙니다.")
            return
        st_.caption(d["status_label"])
        for key, title in GROUPS:
            rows = d[key]
            st_.markdown(f'<div class="mg-sub"><b>{H.esc(title)}</b> {H.badge(f"{len(rows)}건", "warn" if rows else "muted")}</div>', unsafe_allow_html=True)
            if not rows:
                if key == "elderly_cautions" and d.get("elderly_check_status") != "evaluated":
                    st_.caption("나이가 입력되지 않았거나 기준 연령 미만이어서 노인주의는 평가하지 않았습니다." if d.get("elderly_check_status") else "평가하지 않음")
                else:
                    st_.caption("현재 보유한 DUR 데이터에서 해당 규칙이 확인되지 않았습니다.")
                continue
            for r in rows:
                with st_.expander(f"{_names(r['item_names'])}  ·  itemSeq {', '.join(r['item_seqs'])}", expanded=False):
                    st_.markdown(f"- 규칙 출처: `{H.esc(r['rule_source'] or '확인 불가')}`" + (f" · 효능군: {H.esc(r['effect_name'])}" if r.get("effect_name") else ""))
                    st_.markdown("- 근거 ID: " + H.esc(r.get("evidence_id") or "—") + " · 공식 DUR 규칙 매칭 (RULE-BASED RESULT)")
                    if r["has_evidence"] and r["texts"]:
                        for t in r["texts"][:3]:
                            st_.markdown('<div class="mg-int-info">' + H.esc(str(t)[:600]) + "</div>", unsafe_allow_html=True)
                    else:
                        st_.markdown('<div class="mg-int-warn">엔진이 근거 텍스트를 제공하지 않았습니다. 추가 확인이 필요합니다.</div>', unsafe_allow_html=True)
        if d["not_in_dur_tables"]:
            st_.markdown('<div class="mg-int-warn">DUR 규칙 데이터에 포함되지 않은 제품: ' + H.esc(", ".join(map(str, d["not_in_dur_tables"]))) +
                         " — 규칙 검사 대상이 아니며 안전하다는 의미가 아닙니다.</div>", unsafe_allow_html=True)
        st_.caption(H.NO_RULE_NOT_SAFE_NOTE)


def _pname(prof_by, seq):
    p = prof_by.get(seq) or {}
    return f"{p.get('item_name') or '이름 미확인'} ({seq})"


def _render_profiles(st_, chk):
    st_.markdown("**① 선택 의약품별 성분정보**")
    st_.caption("허가정보(MAIN_ITEM_INGR)에서 itemSeq로 직접 조회한 값입니다. 검색 결과 카드에 성분이 표시되지 않아도 여기서 별도로 조회합니다. 제품명으로 성분을 추정하지 않습니다.")
    for p in chk["profiles"]:
        label, tone = IA.LOOKUP_STATUS_KO[p["status"]]
        with st_.container(border=True):
            st_.markdown(f"**{H.esc(p['item_name'] or '제품명 확인 불가')}** · itemSeq `{p['item_seq']}`  " +
                         H.badge("조회 상태", {"ok": "info", "warn": "purple", "danger": "gray"}.get(tone, "gray"), label), unsafe_allow_html=True)
            st_.caption("조회 상태: " + label)
            st_.markdown("**확인된 성분:** " + H.esc(IA.confirmed_ingredients_text(p)))
            st_.caption("상세 정보 (원본 성분명 / 정규화 성분명 / M코드)  ·  주성분·첨가제 구분은 데이터상 검증되지 않아 '확인된 성분'으로 표시합니다.")
            if p["ingredients"]:
                import pandas as pd
                st_.dataframe(pd.DataFrame([{"순번": i["pos"] + 1, "원본 성분명": i["name_raw"], "정규화 성분명": i["name_norm"], "M코드": i["m_code"],
                                            "비교 포함 여부": "제외(불명확): " + "; ".join(i["d_reasons"]) if i["unclear"] else "포함",
                                            "형태 표지": i["form_markers"]} for i in p["ingredients"]]), **H.stretch(), hide_index=True)
                extra = ""
                if p["n_declared"] is not None and p["n_declared"] != p["n_parsed"]:
                    extra = f" · 허가정보 ITEM_INGR_CNT={p['n_declared']} 와 파싱된 성분 수가 다릅니다(그대로 표시)"
                st_.caption(f"성분 {p['n_parsed']}개 전체 표시{extra}" + (" · 파싱되지 않은 잔여 텍스트가 있습니다" if p["main_left_over"] else ""))
            if p["source"]:
                st_.caption("출처: " + p["source"])
            if p.get("error"):
                st_.caption("조회 중 오류: " + p["error"])


def _render_pairs(st_, chk, prof_by):
    st_.markdown("**② 의약품 간 성분 비교 결과**")
    if len(chk["seqs"]) < 2:
        st_.markdown('<div class="mg-int-info">의약품을 2개 이상 선택하면 제품 쌍마다 성분을 비교합니다. 지금은 1개라 비교하지 않았습니다 (비교 결과가 없다는 뜻이며 안전하다는 의미가 아닙니다).</div>', unsafe_allow_html=True)
        return
    st_.caption(f"선택 {len(chk['seqs'])}개 → 모든 제품 쌍 {len(chk['pairs'])}개를 15번 엔진 규칙(M코드 일치 / 정규화 성분명 일치)으로 비교했습니다. 결과 출처: {chk['origin'] or '없음'}")
    for p in chk["pairs"]:
        cls = {"A": "mg-int-warn", "B": "mg-int-info", "C": "mg-int-err"}[p["state"]]
        body = f"<b>{H.esc(_pname(prof_by, p['a']))} ↔ {H.esc(_pname(prof_by, p['b']))}</b><br>{H.esc(IA.PAIR_STATE_KO[p['state']])}"
        if p["state"] == "A":
            body += f"<br>미검증 후보 {p['n_candidates']}건 — 아래 ③에서 확인하세요."
        elif p["state"] == "B":
            body += f"<br>{H.esc(IA.PAIR_B_TEXT)} <b>{H.esc(IA.PAIR_B_WARN)}</b>"
            for n in p.get("notes") or []:
                body += f"<br>· {H.esc(n)}"
        else:
            body += "<br>누락된 데이터/이유:" + "".join(f"<br>· {H.esc(r)}" for r in p["reasons"] or ["성분 정보 부족(15번 엔진이 비교 불가로 반환)"])
            body += "<br>비교하지 못했으며 '후보 0건'이나 안전을 뜻하지 않습니다."
        st_.markdown(f'<div class="{cls}">{body}</div>', unsafe_allow_html=True)


def _render_findings(st_, chk):
    st_.markdown("**③ 발견된 중복 후보**")
    fs = chk["findings"]
    cands = [f for f in fs if f["is_candidate"]]
    if not fs:
        states = {p["state"] for p in chk["pairs"]}
        if len(chk["seqs"]) < 2:
            st_.markdown('<div class="mg-int-info">비교 대상이 2개 미만이라 후보를 찾지 않았습니다.</div>', unsafe_allow_html=True)
        elif states == {"B"}:
            st_.markdown(f'<div class="mg-int-info">후보 및 검토 항목이 없습니다. {H.esc(IA.PAIR_B_TEXT)} <b>{H.esc(IA.PAIR_B_WARN)}</b></div>', unsafe_allow_html=True)
        else:
            st_.markdown('<div class="mg-int-err">표시할 후보가 없지만, 데이터 부족으로 비교하지 못한 제품 쌍이 있습니다. 위 ②의 이유를 확인하세요. 이는 "후보 0건"이 아니라 <b>판단 불가</b>이며 안전하다는 뜻이 아닙니다.</div>', unsafe_allow_html=True)
        return
    if not cands:
        st_.markdown(f'<div class="mg-int-info">중복 후보는 발견되지 않았습니다(아래는 후보가 아닌 검토 항목). <b>{H.esc(IA.PAIR_B_WARN)}</b></div>', unsafe_allow_html=True)
    import pandas as pd
    st_.dataframe(pd.DataFrame([{
        "사례": f["case_label"], "후보 유형": f["candidate_type"], "관련 의약품": " ↔ ".join(str(x) for x in f["item_names"] if x),
        "itemSeq": ", ".join(f["item_seqs"]), "원본 성분명": " | ".join(str(x) for x in f["raw_names"] if x), "정규화 성분명": " | ".join(str(x) for x in f["norm_names"] if x),
        "M코드": " | ".join(str(x) for x in f["m_codes"] if x), "탐지 근거": f["basis"], "검증 상태": f["verification_status"] + " (NOT_VERIFIED / NO-GO)",
        "추가 확인": f["needs_review_text"]} for f in fs]), **H.stretch(), hide_index=True)
    if any(f["case"] == "CASE2" for f in fs):
        st_.markdown('<div class="mg-int-warn"><b>M코드가 서로 다른 동일 성분명 후보 안내</b><br>' + H.esc(IA.MCODE_NOTICE) + "</div>", unsafe_allow_html=True)


def _render_sources(st_, chk):
    st_.markdown("**④ 데이터 출처 및 검증 한계**")
    st_.caption(IA.SOURCE_NOTICE)
    st_.caption(IA.VERIFY_NOTICE)
    st_.caption(IA.CANDIDATE_NOT_DUR_NOTICE)
    st_.caption(IA.TYPE_MAPPING_NOTE)
    if chk.get("consistency") is not None:
        st_.caption("16번 통합 결과와 이 화면의 성분 비교 결과 일치 여부: " + ("일치" if chk["consistency"] else "불일치 — 개발자 설정에서 확인 필요"))
    st_.caption(IA.TEMPLATE_NOTICE)


def render_ingredient_check(st_, ss, engine, sig):
    """'성분 중복 후보 확인' 영역. 통합 버튼 실행 전에도, 성분 정보가 없을 때도 숨기지 않는다. 표시 오류는 이 영역에만 국한."""
    items = [str(x) for x in list(ss.selection.items)] if ss.get("selection") is not None else []
    with st_.container(border=True):
        st_.markdown(f'<div class="mg-card-head"><h3 class="mg-card-title">{NOT_DUR_TITLE}</h3></div>', unsafe_allow_html=True)
        st_.markdown(H.badge("후보 · 미검증", "purple", "공식 DUR 병용금기가 아닙니다") + " " + H.badge("공식 DUR 규칙 아님", "gray"), unsafe_allow_html=True)
        st_.caption("성분 중복 후보 확인 — 상단 KPI '성분 중복 후보'의 상세 근거입니다(요약은 상단, 성분정보·비교·후보 근거는 이 영역).")
        if not items:
            st_.info("의약품을 선택하면 각 의약품의 성분정보와 제품 간 성분 비교 결과가 여기에 표시됩니다.")
            return
        try:
            integ, integ_sig = ss.get("integ"), ss.get("integ_sig")
            res = integ["result"] if (integ is not None and integ_sig == sig and integ.get("status") == "OK") else None
            chk = _chk_for(ss, engine, sig, items)
            prof_by = {p["item_seq"]: p for p in chk["profiles"]}
            if not chk["engine_ready"]:
                st_.error((getattr(engine, "error_user", None) or "성분 엔진을 불러오지 못했습니다.") + " 성분정보를 조회하지 못한 상태이며 '성분이 없다/중복이 없다'는 뜻이 아닙니다.")
            _render_profiles(st_, chk)
            _render_pairs(st_, chk, prof_by)
            _render_findings(st_, chk)
            _render_sources(st_, chk)
            if ss.get("developer"):
                st_.json({"origin": chk["origin"], "status": chk["status"], "consistency": chk["consistency"], "pairs": chk["pairs"]})
        except Exception as e:  # noqa: BLE001
            st_.error("성분 중복 후보 영역을 표시하는 중 오류가 발생했습니다(기술적 오류). '검사 완료'로 해석하지 마세요."
                      + (f" [{type(e).__name__}: {str(e)[:160]}]" if ss.get("developer") else ""))


def _render_evidence_limits(st_, ss, model):
    with st_.container(border=True):
        st_.markdown('<div class="mg-card-head"><h3 class="mg-card-title">근거 및 제한사항</h3></div>', unsafe_allow_html=True)
        for lim in model["limitations"]:
            st_.markdown("- " + H.esc(lim))
        if model.get("evidence"):
            with st_.expander(f"근거 추적 목록 ({len(model['evidence'])}건) — DUR 공식 규칙과 성분 후보 근거를 구분해 표시", expanded=False):
                for e in model["evidence"]:
                    kind = {"OFFICIAL_DUR_RULE_MATCH": "공식 DUR 규칙 매칭", "INGREDIENT_CANDIDATE_RULE": "성분 후보 규칙(미검증)",
                            "INGREDIENT_REVIEW_HINT_NOT_A_CANDIDATE": "성분 검토 힌트(후보 아님)"}.get(e["kind"], e["kind"])
                    st_.markdown(f"- `{e['evidence_id']}` {H.esc(kind)} · 항목 {H.esc(', '.join(e.get('involved_item_seqs') or []))}")
        meta = model.get("meta")
        if meta and ss.get("developer"):
            st_.json({"request_id": model.get("request_id"), "meta": meta, "gaps": model.get("gaps")})


def _chk_for(ss, engine, sig, items):
    """성분 확인 결과(ingredient_check)를 한 번만 계산해 상단 KPI와 하단 상세가 같은 값을 쓰게 한다. 새 엔진을 만들지 않고 어댑터 함수를 그대로 호출."""
    integ, integ_sig = ss.get("integ"), ss.get("integ_sig")
    res = integ["result"] if (integ is not None and integ_sig == sig and integ.get("status") == "OK") else None
    key = (tuple(items), sig, id(res), id(engine))
    cached = ss.get("_chk_cache")
    if cached is not None and cached[0] == key:
        return cached[1]
    chk = IA.ingredient_check(engine, items, res)
    ss["_chk_cache"] = (key, chk)
    return chk


def render_kpis_with_ingredient(st_, ss, engine, sig, vm_active):
    """기존 KPI 카드(H.kpi_cards, 변경 없음)를 그대로 쓰고, '효능군 중복' 바로 오른쪽에 '성분 중복 후보' 카드를 끼워 넣는다.
    실패하면 기존 summary_cards.render_kpis 로 되돌아가 기존 화면을 유지한다(경고 표시)."""
    try:
        cards = [dict(c) for c in H.kpi_cards(vm_active)]
        idx = [i for i, c in enumerate(cards) if "효능군" in str(c.get("label", ""))]
        if len(idx) != 1:
            raise RuntimeError("기존 KPI 카드에서 '효능군 중복' 카드를 정확히 1개 찾지 못함: %d개" % len(idx))
        items = [str(x) for x in list(ss.selection.items)] if ss.get("selection") is not None else []
        integ, integ_sig = ss.get("integ"), ss.get("integ_sig")
        current = integ is not None and integ_sig == sig
        chk = _chk_for(ss, engine, sig, items)
        card = IA.ingredient_kpi(chk, analyzed=bool(current and integ.get("status") == "OK"),
                                 technical_error=bool(current and integ.get("status") != "OK"))
        card["icon"] = cards[idx[0]].get("icon")
        cards.insert(idx[0] + 1, card)
        html = '<div class="mg-kpis">'
        for c in cards:
            sub = f'<div class="mg-kpi-sub">{H.esc(c["sub"])}</div>' if c.get("sub") else ""
            tag = f'<div class="mg-kpi-tagline">{H.esc(c["tagline"])}</div>' if c.get("tagline") else ""
            title = f' title="{H.esc(c["tooltip"])}"' if c.get("tooltip") else ""
            html += (f'<div class="mg-kpi {H.esc(c["tone"])}"{title}><div class="mg-kpi-top">{H.icon(c["icon"], 16)}'
                     f'<span class="mg-kpi-label">{H.esc(c["label"])}</span></div>'
                     f'<div class="mg-kpi-value">{H.esc(c["value"])}</div>'
                     f'<div class="mg-kpi-desc">{H.esc(c["desc"])}</div>{sub}{tag}</div>')
        html += '</div>'
        st_.markdown(html, unsafe_allow_html=True)
        from app import ui_policy as _P
        st_.markdown(f'<div class="mg-sub">{H.esc(_P.BADGE_LEGEND)} · 건수는 유형별로 따로 표시하며 위험 점수로 합산하지 않습니다. '
                     f'성분 중복 후보는 공식 DUR 규칙이 아니며 다른 건수와 합산하지 않습니다.</div>', unsafe_allow_html=True)
    except Exception as e:  # noqa: BLE001 — KPI 확장 실패가 기존 화면을 막지 않도록 기존 렌더러로 복귀
        summary_cards.render_kpis(st_, vm_active)
        st_.warning("성분 중복 후보 KPI 카드를 만들지 못해 기존 KPI만 표시합니다."
                    + (f" [{type(e).__name__}: {str(e)[:160]}]" if ss.get("developer") else ""))


def render_integration_section(st_, ss, engine, sig):
    """기존 DUR 결과 아래에 붙는 통합 Screening 영역. 이 영역의 표시 오류가 화면 전체를 멈추지 않도록 감싼다."""
    try:
        _render_integration_section(st_, ss, engine, sig)
    except Exception as e:  # noqa: BLE001 — 표시 오류는 이 영역에만 국한
        st_.error("통합 Screening 결과를 표시하는 중 오류가 발생했습니다(기술적 오류). 기존 화면은 영향을 받지 않았으며, 이 상태를 '검사 완료'로 해석하지 마세요."
                  + (f" [{type(e).__name__}: {str(e)[:160]}]" if ss.get("developer") else ""))


def _render_integration_section(st_, ss, engine, sig):
    integ, integ_sig = ss.get("integ"), ss.get("integ_sig")
    stale = integ is not None and integ_sig != sig
    model = IA.build_ui_model(None if stale else integ)
    st_.markdown('<hr/>', unsafe_allow_html=True)
    shown = _render_status(st_, ss, engine, model, stale)
    if shown and not stale and model["state"] != "BLOCKED" and (model["dur"] is not None or model["partial"]):
        _render_dur(st_, model)
    render_ingredient_check(st_, ss, engine, sig)          # 항상 표시(버튼 실행 전·성분 없음·stale 포함)
    if shown and not stale:
        if model["state"] == "BLOCKED":
            st_.caption("스크리닝이 수행되지 않았으므로 DUR 통합 결과는 표시하지 않습니다.")
        _render_evidence_limits(st_, ss, model)


# ------------------------------------------------------------------------------------------------ main
def main():
    pass  # [19:removed DEBUG banner]
    ss = st.session_state
    init_state(ss)
    css = load_css()
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    rt = get_runtime()
    engine = get_integration()
    root = ui_runtime.project_root()
    runs = AR.list_runs(root)
    chosen = ss.get("audit_run_sel")
    run_name = chosen if chosen in runs else (runs[0] if runs else None)
    audit = AR.load_run(root, run_name)
    metrics = AR.load_baseline_metrics(root, audit.get("baseline_run") if audit else None)

    sig = drug_search.current_sig(ss)
    vm_active = ss.vm if (ss.vm is not None and ss.vm_sig == sig) else None
    stale = ss.vm is not None and vm_active is None

    audit_summary = None if not audit else dict(
        run_name=audit["run_name"], option=audit.get("option"), option_text=audit.get("option_text"),
        gates=audit.get("gates"), auto_apply=audit.get("auto_apply"), engine_change_allowed=audit.get("engine_change_allowed"))
    report_md = H.build_report_markdown(vm_active, audit_summary)
    report_js = H.build_report_json(vm_active, audit_summary)

    sidebar.render(st, ss, rt, vm_active, audit, root)
    with st.sidebar:
        st.caption("app_v2 · 통합 Screening(DUR + 성분 중복 후보). 연구용 데모이며 공개 링크에 개인정보를 입력하지 마세요.")
    status_ph = header.render(st, ss, rt, vm_active, runs, audit, report_md, report_js)

    def render_status(ph, running=False):
        code, tone, tip = H.analysis_status(bool(rt and rt.ready), vm_active, running)
        ph.markdown(H.badge(code, tone, tip), unsafe_allow_html=True)

    if rt is not None and not rt.ready:
        st.error(rt.error_user)
        if ss.developer and rt.error_dev:
            st.code(rt.error_dev)
        if st.button("다시 시도", key="retry_load"):
            get_runtime.clear()
            st.rerun()

    def go(page):
        ss.page = page
        st.rerun()

    page = ss.page
    if page == "dashboard":
        c1, c2, c3 = st.columns([3.1, 3.9, 3.0])
        with c1:
            drug_search.render(st, ss, rt, vm_active, status_ph, render_status, prefix="d", with_run=False)
            render_run_button(st, ss, rt, engine, status_ph, render_status, key="run_integrated_d")
        with c2:
            summary_cards.render_coverage_donut(st, ss, metrics, vm_active)
        with c3:
            summary_cards.render_final(st, vm_active, stale, audit)
        render_kpis_with_ingredient(st, ss, engine, sig, vm_active)
        c4, c5 = st.columns([6.8, 3.2])
        with c4:
            gate_timeline.render_card(st, audit, lambda: go("gates"))
        with c5:
            findings.render(st, vm_active, stale)
        c6, c7, c8 = st.columns([4.3, 4.3, 3.4])
        with c6:
            safety_matrix.render(st, vm_active, stale)
        with c7:
            drug_table.render(st, vm_active, stale)
        with c8:
            evidence_panel.render(st, vm_active, stale)
        render_integration_section(st, ss, engine, sig)         # ← 기존 DUR 결과 아래에 추가된 영역
    elif page == "search":
        c1, c2 = st.columns([4, 6])
        with c1:
            drug_search.render(st, ss, rt, vm_active, status_ph, render_status, prefix="p", with_run=False)
            render_run_button(st, ss, rt, engine, status_ph, render_status, key="run_integrated_p")
        with c2:
            findings.render(st, vm_active, stale)
        render_integration_section(st, ss, engine, sig)
    elif page == "run":
        render_run_button(st, ss, rt, engine, status_ph, render_status, key="run_integrated_r")
        pages.render_run_page(st, ss, rt, vm_active, status_ph, render_status)
        render_integration_section(st, ss, engine, sig)
    elif page == "result":
        pages.render_result_page(st, ss, vm_active, stale, ss.developer)
        render_integration_section(st, ss, engine, sig)
        evidence_panel.render(st, vm_active, stale)
    elif page == "gates":
        gate_timeline.render_detail_page(st, audit)
    elif page == "coverage":
        coverage_page.render(st, audit, metrics)
    elif page == "report":
        pages.render_report_page(st, vm_active, audit, report_md, report_js)
    elif page == "settings":
        pages.render_settings_page(st, ss, rt, root, audit)
        if ss.developer:
            st.json({"integration_engine": {"ready": engine.ready, "dur_ok": engine.dur_ok, "ing_ok": engine.ing_ok, "info": engine.info,
                                            "error": engine.error_dev}})

    st.markdown(f'<div class="mg-sub" style="margin-top:14px">{H.esc(H.PROTOTYPE_NOTICE)} {H.esc(H.NO_RULE_NOT_SAFE_NOTE)}</div>',
                unsafe_allow_html=True)


main()
