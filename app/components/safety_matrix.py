"""Drug × safety-category matrix (HTML grid). Cell statuses come from H.matrix_rows (ViewModel facts only).
'발견 없음' is deliberately NOT green: it must not read as 'safe'."""
from __future__ import annotations

from app import ui_policy as P
from app.utils import ui_helpers as H

_LEGEND = (("found", "#22C7F2", "규칙 발견"), ("none", "#2a4263", "규칙 조회 완료 / 발견 없음"),
           ("nodata", "#34475f", "데이터 미포함"), ("undet", "#8457FF", "판단 불가"), ("fail", "#FF647C", "조회 실패"))


_SHORT = {"NONE_FOUND": "발견 없음", "NOT_IN_DATA": "미포함"}   # full wording is in the legend and the tooltip


def matrix_html(vm_active) -> str:
    rows = H.matrix_rows(vm_active)
    head = "".join(f"<th>{H.esc(P.RISK_LABEL_KO[c])}</th>" for c in P.RISK_ORDER)
    body = ""
    for r in rows:
        tds = ""
        for c in P.RISK_ORDER:
            cell = r["cells"][c]
            label, cls = H.CELL_STATUS[cell["status"]]
            txt = f'{label} · {cell["count"]}건' if cell["status"] == "FOUND" else _SHORT.get(cell["status"], label)
            tds += f'<td><div class="mg-cell {cls}" title="{H.esc(cell["tip"])}">{H.esc(txt)}</div></td>'
        body += f'<tr><td class="rowh" title="{H.esc(r["item_seq"] or "")}">{H.esc(r["name"])}</td>{tds}</tr>'
    legend = "".join(f'<span><i style="background:{col}"></i>{H.esc(lb)}</span>' for _, col, lb in _LEGEND)
    return (f'<div class="mg-matrix-scroll"><table class="mg-matrix"><thead><tr><th class="rowh">선택 의약품</th>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table></div><div class="mg-mlegend">{legend}</div>')


def render(st, vm_active, stale):
    with st.container(border=True):
        st.markdown(f'<div class="mg-card-head"><h3 class="mg-card-title">의약품별 안전성 프로필</h3>{H.tag("RULE")}</div>',
                    unsafe_allow_html=True)
        if vm_active is None:
            msg = "입력이 변경되어 이전 결과를 숨겼습니다. 다시 검사하세요." if stale else "검사를 실행하면 의약품 × 안전성 항목 매트릭스가 표시됩니다."
            st.markdown(f'<div class="mg-empty">{H.esc(msg)}</div>', unsafe_allow_html=True)
            return
        st.markdown(matrix_html(vm_active), unsafe_allow_html=True)
        st.markdown(f'<div class="mg-sub" style="margin-top:6px">{H.esc(H.NO_RULE_NOT_SAFE_NOTE)} '
                    f'칸에 마우스를 올리면 판단 기준이 표시됩니다. 시간 흐름이나 위험 점수 데이터는 없으므로 시계열 그래프는 표시하지 않습니다.</div>',
                    unsafe_allow_html=True)
