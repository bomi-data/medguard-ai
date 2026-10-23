"""Left sidebar — brand, working navigation, project information card (real values only)."""
from __future__ import annotations

from app import ui_policy as P
from app.utils import ui_helpers as H

_MATERIAL = {"dashboard": ":material/dashboard:", "search": ":material/medication:", "run": ":material/play_circle:",
             "result": ":material/assignment:", "gates": ":material/verified_user:", "coverage": ":material/database:",
             "report": ":material/description:", "settings": ":material/settings:"}


def project_info(rt, vm, audit, project_root) -> list:
    """(label, value) rows. Each value comes from settings / results; missing → explicit text, never invented."""
    dep = (rt.runtime_info or {}).get("deployment") if rt is not None else None
    core = vm.metadata.core if (vm is not None and vm.metadata) else {}
    name = core.get("pipeline_name") or getattr(project_root, "name", None) or "N/A"
    version = (dep or {}).get("package_version") or core.get("pipeline_version") or P.ADAPTER_VERSION
    last = None
    if vm is not None and vm.metadata.adapter.get("finished_at"):
        last = "분석 " + str(vm.metadata.adapter["finished_at"])[:19].replace("T", " ") + " UTC"
    elif audit:
        last = "Audit " + audit["run_label"]
    status = "READY" if (rt is not None and rt.ready) else "데이터 로딩 실패"
    return [("Project", name), ("Version", version), ("Last Run", last or "실행 기록 없음"), ("System Status", status)]


def render(st, ss, rt, vm, audit, project_root):
    with st.sidebar:
        st.markdown(
            f'<div class="mg-brand"><div class="mg-logo">{H.icon("gate", 20)}</div><div>'
            f'<div class="mg-brand-name">MEDGUARD <b>AI</b></div>'
            f'<div class="mg-brand-sub">Medication Safety Analysis</div></div></div>', unsafe_allow_html=True)
        for key, label, ico in H.NAV_ITEMS:
            kw = dict(key=f"nav_{key}", type="primary" if ss.page == key else "secondary", **H.stretch())
            try:
                clicked = st.button(label, icon=_MATERIAL[key], **kw)
            except TypeError:                                   # older Streamlit without icon=
                clicked = st.button(label, **kw)
            if clicked and ss.page != key:
                ss.page = key
                st.rerun()
        rows = "".join(f'<div class="mg-proj-row"><span>{H.esc(k)}</span><span>{H.esc(v)}</span></div>'
                       for k, v in project_info(rt, vm, audit, project_root))
        st.markdown(f'<div class="mg-proj"><div class="mg-proj-title">PROJECT INFORMATION</div>{rows}</div>',
                    unsafe_allow_html=True)
