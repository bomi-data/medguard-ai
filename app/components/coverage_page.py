"""'데이터 커버리지' page — STEP 8-1.5 coverage metrics (each with its own numerator/denominator) and the STEP 8-1.6
feasibility verdict, shown separately. Inferred mappings are audit estimates only: not official, not applied."""
from __future__ import annotations

from app.utils import ui_helpers as H


def metrics_table_html(metrics) -> str:
    head = ("<tr><th>ID</th><th>지표</th><th>분자</th><th>분모</th><th>비율</th><th>구분</th><th>산식</th><th>비고</th></tr>")
    body = ""
    for m in metrics:
        pct = H.pct_value(m["numerator"], m["denominator"])
        body += (f'<tr><td>{H.esc(m["metric_id"])}</td><td>{H.esc(m["metric"])}</td>'
                 f'<td class="mg-num">{H.fmt_int(m["numerator"])}</td><td class="mg-num">{H.fmt_int(m["denominator"])}</td>'
                 f'<td class="mg-num">{"N/A" if pct is None else f"{pct:.2f}%"}</td><td>{H.esc(m.get("type") or "")}</td>'
                 f'<td>{H.esc(m.get("formula") or "")}</td><td>{H.esc(m.get("note") or "")}</td></tr>')
    return f'<div class="mg-table-wrap"><table class="mg-table"><thead>{head}</thead><tbody>{body}</tbody></table></div>'


def render(st, audit, metrics):
    with st.container(border=True):
        st.markdown(f'<div class="mg-card-head"><h3 class="mg-card-title">Coverage Audit 구현 판정</h3>{H.tag("AUDIT")}</div>',
                    unsafe_allow_html=True)
        if not audit:
            st.markdown('<div class="mg-empty">Audit 실행 기록 없음</div>', unsafe_allow_html=True)
        else:
            d = audit["decision"]
            st.markdown(f'{H.badge("OPTION " + str(audit.get("option")), "warn")} '
                        f'<span class="mg-sub">{H.esc(audit.get("option_text") or "")}</span>', unsafe_allow_html=True)
            if audit.get("reason"):
                st.markdown(f'<div class="mg-sub" style="margin-top:6px">근거: {H.esc(audit["reason"])}</div>', unsafe_allow_html=True)
            st.markdown('<div class="mg-note">이 판정은 <b>성분 기반 규칙 연결 확장의 구현 가능성</b>에 대한 것입니다. '
                        '환자·약물 조합의 안전성 판정이 아닙니다.</div>', unsafe_allow_html=True)
            rows = [
                ("공식 D↔M 연결표(EXACT)", "있음" if audit.get("official_link_table") else "확인되지 않음"),
                ("내부 추론 연결 쌍 (INFERRED)", f'{H.fmt_int(d.get("inferred_mapping_pairs_not_official"))}쌍 — 공식 검증 아님'),
                ("내부 추론 기반 추가 연결 제품 (ESTIMATE)", f'{H.fmt_int(d.get("inferred_additional_products"))}개 — 추정, 운영 미적용'),
                ("후보 상한 (검사 가능 수 아님)", f'{H.fmt_int(d.get("candidate_upper_products"))}개'),
                ("Screening 자동 적용 (auto_apply)", str(audit.get("auto_apply"))),
                ("엔진 변경 허용", str(audit.get("engine_change_allowed"))),
                ("보호 파일 불변 / 회귀 해시 동일", f'{audit.get("protected_files_unchanged")} / {audit.get("regression_hash_equal")}'),
            ]
            body = "".join(f"<tr><td>{H.esc(k)}</td><td>{H.esc(v)}</td></tr>" for k, v in rows)
            st.markdown(f'<div class="mg-table-wrap"><table class="mg-table"><tbody>{body}</tbody></table></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="mg-sub" style="margin-top:6px">{H.esc(audit.get("note") or "")} · '
                        f'서로 다른 집합의 제품 수는 합산하지 않습니다.</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(f'<div class="mg-card-head"><h3 class="mg-card-title">Coverage 지표 (STEP 8-1.5 기준선)</h3>{H.tag("AUDIT")}</div>',
                    unsafe_allow_html=True)
        if not metrics:
            st.markdown('<div class="mg-empty">기준선 Coverage 지표 파일을 찾지 못했습니다 — N/A</div>', unsafe_allow_html=True)
        else:
            st.markdown(metrics_table_html(metrics), unsafe_allow_html=True)
            st.markdown('<div class="mg-note">지표마다 분모가 다릅니다. 등장 ≠ 위험, 미등장 ≠ 안전. '
                        '"추정"(ESTIMATE) 지표는 가정을 포함한 값입니다.</div>', unsafe_allow_html=True)
