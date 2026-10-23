"""Read-only reader for audit result files (STEP 8-1.5 / 8-1.6) — DISPLAY ONLY.

  * It never writes, never imports the Screening Engine, and never feeds anything into a screening call.
  * It opens only an explicit allow-list of result files that sit DIRECTLY in an audit run folder
    (no recursion), so the analysis sub-folders that hold inferred / candidate mappings are never read.
  * Missing / unreadable files are reported as such (None / empty) — values are never invented, and a
    missing gate is shown as NOT RUN.

The audit is a feasibility study of expanding rule coverage. Its verdict ("OPTION A/B/C") is NOT a statement
about any patient's medication safety and is shown separately from screening results.
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Optional

AUDIT_DIR = "reports/ingredient_coverage_audit"          # STEP 8-1.6 results (feasibility audit)
BASELINE_DIR = "reports/ui_coverage_audit"               # STEP 8-1.5 results (coverage baseline)
RUN_RE = re.compile(r"^run_\d{8}_\d{6}$")

# explicit allow-list: file names read from a run folder (top level only)
F_MANIFEST = "audit_manifest.json"
F_DECISION = "11_feasibility_decision.json"
F_SAFETY = "09_medical_safety_validation.csv"
F_REPORT = "12_ingredient_coverage_report.md"
F_METRICS = "03_coverage_metrics.csv"                    # baseline run

GATE_NAMES = {"1": "Data Integrity", "2": "Ingredient Mapping", "3": "Medical Safety"}
GATE_DESC = {
    "1": "분석에 쓰는 데이터가 기준선과 같은 상태로 로딩되고 식별자가 정상인지 확인",
    "2": "성분 코드 연결(D↔M)의 근거와 정확도를 확인 — 공식 연결표 여부 포함",
    "3": "오연결·복합제 오처리·기존 Screening 결과 변경 여부 등 의료 안전성 관점의 분석 검증",
}
GATE_STATUSES = ("PASS", "WARN", "FAIL", "NOT RUN")


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8-sig")
    except Exception:                                    # noqa: BLE001 — unreadable → treated as missing
        return None


def _read_json(path: Path) -> Optional[dict]:
    t = _read_text(path)
    if t is None:
        return None
    try:
        d = json.loads(t)
        return d if isinstance(d, dict) else None
    except Exception:                                    # noqa: BLE001
        return None


def _read_csv(path: Path) -> list:
    t = _read_text(path)
    if t is None:
        return []
    try:
        return list(csv.DictReader(io.StringIO(t)))
    except Exception:                                    # noqa: BLE001
        return []


def list_runs(root) -> list:
    """Audit run folder names (newest first) that actually contain the manifest. [] when none."""
    base = Path(root) / AUDIT_DIR
    try:
        names = [p.name for p in base.iterdir() if p.is_dir() and RUN_RE.match(p.name) and (p / F_MANIFEST).is_file()]
    except Exception:                                    # noqa: BLE001
        return []
    return sorted(names, reverse=True)


def run_label(name: str) -> str:
    """'run_20261012_183621' → '2026-10-12 18:36:21' (derived from the folder name, nothing generated)."""
    m = re.match(r"^run_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$", name or "")
    return f"{m[1]}-{m[2]}-{m[3]} {m[4]}:{m[5]}:{m[6]}" if m else str(name)


def normalize_gate_status(v) -> str:
    v = str(v).strip().upper() if v is not None else ""
    return v if v in ("PASS", "WARN", "FAIL") else "NOT RUN"


def parse_report_checks(md_text: Optional[str]) -> list:
    """Rows of the report appendix table '| step | check | result | detail |' (non-PASS checks only are stored)."""
    if not md_text:
        return []
    rows, on = [], False
    for ln in md_text.splitlines():
        if ln.startswith("| step | check | result | detail |"):
            on = True
            continue
        if on:
            if not ln.startswith("|"):
                break
            if set(ln.replace("|", "").strip()) <= set("- "):
                continue
            cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", ln.strip().strip("|"))]
            if len(cells) >= 4:
                rows.append(dict(step=cells[0], check=cells[1], result=cells[2], detail=" | ".join(cells[3:])))
    return rows


def load_run(root, name: Optional[str]) -> Optional[dict]:
    """Everything the UI shows about one audit run. None when no run is selected / readable."""
    if not name or not RUN_RE.match(name):
        return None
    d = Path(root) / AUDIT_DIR / name
    manifest = _read_json(d / F_MANIFEST)
    if manifest is None:
        return None
    decision = _read_json(d / F_DECISION) or {}
    gates_raw = decision.get("gates") or manifest.get("gates") or {}
    gates = {k: normalize_gate_status(gates_raw.get(k)) for k in GATE_NAMES}
    report_checks = parse_report_checks(_read_text(d / F_REPORT))
    safety = _read_csv(d / F_SAFETY)
    checks = {"1": [], "2": [], "3": []}
    for r in report_checks:                              # only non-PASS rows are persisted for gates 1 and 2
        if r["step"] == "B1":
            checks["1"].append(dict(gate="1", name=r["check"], status=normalize_gate_status(r["result"]),
                                    description="", evidence="audit report appendix (12_ingredient_coverage_report.md)",
                                    warning=r["detail"] if r["result"].upper() == "WARN" else "",
                                    failure=r["detail"] if r["result"].upper() == "FAIL" else ""))
        elif r["step"] == "GATE2":
            checks["2"].append(dict(gate="2", name=r["check"], status=normalize_gate_status(r["result"]),
                                    description="", evidence="audit report appendix (12_ingredient_coverage_report.md)",
                                    warning=r["detail"] if r["result"].upper() == "WARN" else "",
                                    failure=r["detail"] if r["result"].upper() == "FAIL" else ""))
    for r in safety:
        st_ = normalize_gate_status(r.get("PASS/WARN/FAIL"))
        checks["3"].append(dict(gate="3", name=r.get("Test Case", ""), status=st_,
                                description=r.get("Expected Result", ""), evidence=r.get("Evidence", ""),
                                warning=r.get("Actual Result", "") if st_ == "WARN" else "",
                                failure=r.get("Actual Result", "") if st_ == "FAIL" else "",
                                explanation=r.get("Explanation", ""), actual=r.get("Actual Result", "")))
    return dict(
        run_name=name, run_label=run_label(name), path=str(d), manifest=manifest, decision=decision, gates=gates,
        option=decision.get("option") or manifest.get("option"), option_text=decision.get("option_text"),
        reason=decision.get("reason"), auto_apply=decision.get("auto_apply"),
        engine_change_allowed=decision.get("engine_change_allowed"),
        official_link_table=decision.get("official_link_table"), note=decision.get("note"),
        baseline_run=manifest.get("baseline_run"), gate_checks=checks,
        gate_checks_complete={"1": False, "2": False, "3": bool(safety)},
        key_metrics=manifest.get("key_metrics") or {},
        protected_files_unchanged=manifest.get("protected_files_unchanged"),
        regression_hash_equal=manifest.get("regression_hash_equal"),
    )


def load_baseline_metrics(root, baseline_run: Optional[str]) -> list:
    """STEP 8-1.5 coverage metrics (each with its own numerator / denominator). [] when unavailable."""
    if not baseline_run or not RUN_RE.match(str(baseline_run)):
        return []
    rows = _read_csv(Path(root) / BASELINE_DIR / baseline_run / F_METRICS)
    out = []
    for r in rows:
        def num(k):
            v = (r.get(k) or "").strip()
            try:
                return float(v) if v != "" else None
            except ValueError:
                return None
        out.append(dict(metric_id=r.get("metric_id"), metric=r.get("metric"), basis=r.get("basis"), type=r.get("type"),
                        numerator=num("numerator"), denominator=num("denominator"), value_pct=num("value_%"),
                        formula=r.get("formula"), note=r.get("note")))
    return out


def metric_by_id(metrics: list, metric_id: str) -> Optional[dict]:
    return next((m for m in metrics if m.get("metric_id") == metric_id), None)
