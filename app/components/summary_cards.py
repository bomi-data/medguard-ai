"""Summary donut (coverage metric with numerator/denominator), 4 KPI cards, final result card [A]/[B]."""
from __future__ import annotations

import math

from app import ui_policy as P
from app.utils import audit_reader as AR
from app.utils import ui_helpers as H

# coverage metrics shown in the donut; each has its OWN denominator (never mixed into one number)
DONUT_METRICS = (
    ("M2b", "DUR 규칙 테이블 포함 제품"),
    ("M4a", "병용금기 규칙 포함"),
    ("M5a", "노인주의 규칙 포함"),
    ("M6a", "효능군 규칙 포함"),
)


def donut_svg(frac: float, uid: str = "mgg") -> str:
    r, w = 72.0, 17.0
    c = 2 * math.pi * r
    on = 0.0 if frac is None else max(0.0, min(1.0, frac)) * c
    return (f'<svg viewBox="0 0 190 190" role="img" aria-label="coverage donut">'
            f'<defs><linearGradient id="{uid}" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0%" stop-color="#22C7F2"/><stop offset="55%" stop-color="#3687FF"/>'
            f'<stop offset="100%" stop-color="#24D99B"/></linearGradient></defs>'
            f'<circle cx="95" cy="95" r="{r}" fill="none" stroke="#1b3150" stroke-width="{w}"/>'
            f'<circle cx="95" cy="95" r="{r}" fill="none" stroke="url(#{uid})" stroke-width="{w}" stroke-linecap="round" '
            f'stroke-dasharray="{on:.2f} {c:.2f}"/></svg>')


def render_coverage_donut(st, ss, metrics, vm_active):
    with st.container(border=True):
        st.markdown(f'<div class="mg-card-head"><h3 class="mg-card-title">전체 분석 결과 요약</h3>'
                    f'{H.tag("AUDIT")}</div>', unsafe_allow_html=True)
        ids = [m for m, _ in DONUT_METRICS]
        label_of = dict(DONUT_METRICS)
        sel = st.radio("Coverage 지표", ids, format_func=lambda i: label_of[i], horizontal=True, key="donut_metric",
                       label_visibility="collapsed")
        m = AR.metric_by_id(metrics, sel)
        num, den = (m or {}).get("numerator"), (m or {}).get("denominator")
        frac = None if (num is None or not den) else num / den
        center = "N/A" if frac is None else f"{100 * frac:.1f}%"
        miss = None if frac is None else den - num
        st.markdown(
            f'<div class="mg-donut-wrap"><div class="mg-donut">{donut_svg(frac)}'
            f'<div class="mg-donut-center"><div class="mg-kpi-num">{H.esc(center)}</div>'
            f'<div class="mg-kpi-cap">{H.esc(label_of[sel])} / 검색 가능 제품</div></div></div>'
            f'<div class="mg-legend">'
            f'<div class="mg-legend-row"><span class="mg-sw" style="background:#3687FF"></span>포함 (분자)<b>{H.fmt_int(num)}</b></div>'
            f'<div class="mg-legend-row"><span class="mg-sw" style="background:#1b3150;border:1px solid #2f4a6e"></span>미포함<b>{H.fmt_int(miss)}</b></div>'
            f'<div class="mg-legend-row"><span class="mg-sw" style="background:transparent;border:1px solid #7085A3"></span>분모: 검색 가능 제품 (U)<b>{H.fmt_int(den)}</b></div>'
            f'</div></div>', unsafe_allow_html=True)
        if m:
            st.markdown(f'<div class="mg-sub">계산: <b>{H.esc(m.get("formula") or "-")}</b> · 분자/분모 {H.esc(H.fmt_ratio(num, den))}'
                        f' · 출처 STEP 8-1.5 기준선 ({H.esc(m.get("type") or "")})</div>', unsafe_allow_html=True)
            st.markdown('<div class="mg-note">이 값은 <b>제품이 DUR 규칙 테이블에 등장하는 비율</b>입니다. '
                        '미등장은 규칙 데이터 미포함이며 안전하다는 의미가 아닙니다. 지표마다 분모가 다르므로 하나로 합산하지 않습니다.</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="mg-empty">Coverage 지표를 불러올 수 없습니다 (기준선 결과 파일 없음) — N/A</div>',
                        unsafe_allow_html=True)
        if vm_active is not None and vm_active.can_display_results:
            st.markdown(f'<div class="mg-sub">현재 분석: 선택 약물 <b>{len(vm_active.medications)}개</b> · '
                        f'Core가 탐지한 항목 <b>{vm_active.summary.total_signals}건</b> {H.tag("RULE")}</div>',
                        unsafe_allow_html=True)


def render_kpis(st, vm_active):
    cards = H.kpi_cards(vm_active)
    html = '<div class="mg-kpis">'
    for c in cards:
        sub = f'<div class="mg-kpi-sub">{H.esc(c["sub"])}</div>' if c["sub"] else ""
        html += (f'<div class="mg-kpi {H.esc(c["tone"])}"><div class="mg-kpi-top">{H.icon(c["icon"], 16)}'
                 f'<span class="mg-kpi-label">{H.esc(c["label"])}</span></div>'
                 f'<div class="mg-kpi-value">{H.esc(c["value"])}</div>'
                 f'<div class="mg-kpi-desc">{H.esc(c["desc"])}</div>{sub}</div>')
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)
    st.markdown(f'<div class="mg-sub">{H.esc(P.BADGE_LEGEND)} · 건수는 유형별로 따로 표시하며 위험 점수로 합산하지 않습니다.</div>',
                unsafe_allow_html=True)


def render_final(st, vm_active, stale, audit):
    cs = H.combination_status(vm_active)
    limits = "".join(f"<li>{H.esc(x)}</li>" for x in cs.limits)
    lim_html = f'<ul class="mg-sub" style="margin:8px 0 0 16px;padding:0">{limits}</ul>' if limits else ""
    ltxt = f'<div class="mg-note warn">{H.esc(cs.limitation_text)}</div>' if cs.limitation_text else ""
    stale_html = ('<div class="mg-note warn">입력이 변경되어 이전 결과를 숨겼습니다. 다시 검사하세요.</div>' if stale else "")
    if audit:
        opt = audit.get("option")
        b = (f'<div class="mg-audit-box">{H.tag("AUDIT")}'
             f'<div class="mg-audit-main">{H.esc("OPTION " + str(opt) if opt else "판정 없음")}</div>'
             f'<div class="mg-sub">{H.esc(audit.get("option_text") or "")}</div>'
             f'<div class="mg-sub" style="margin-top:6px">성분 연결 확장의 <b>구현 가능성</b> 판정입니다. '
             f'환자·약물 조합의 안전성 판정이 아닙니다. 추정 연결은 Screening에 자동 적용되지 않습니다.</div></div>')
    else:
        b = f'<div class="mg-audit-box">{H.tag("AUDIT")}<div class="mg-sub" style="margin-top:6px">Audit 실행 기록 없음</div></div>'
    st.markdown(
        f'<div class="mg-card mg-final {H.esc(cs.tone)}"><div class="mg-card-head"><h3 class="mg-card-title">최종 분석 판정</h3>'
        f'{H.tag("RULE")}</div>'
        f'<div class="mg-final-label">[A] 환자·약물 조합 분석 상태</div><div class="mg-final-main">{H.esc(cs.label)}</div>'
        f'{lim_html}{ltxt}{stale_html}'
        f'<div class="mg-final-sep"></div><div class="mg-final-label">[B] Coverage Audit 구현 판정</div>{b}</div>',
        unsafe_allow_html=True)
