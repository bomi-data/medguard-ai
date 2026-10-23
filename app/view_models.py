"""ViewModel schema — immutable, render-ready objects for the (future) Streamlit screen.

Rules
  * Every value here is either copied verbatim from the Frozen Core report or is a fixed constant from
    ui_policy. Nothing is computed that would amount to a medical judgement.
  * The renderer must branch only on `SafetyCheckViewModel.state`, `can_display_results` and
    `FindingView.display_mode`; it must never re-derive safety logic from raw Core fields.
  * `to_dict()` returns plain JSON-serialisable data (tuples → lists). Developer information lives in
    `debug` and is excluded unless `include_debug=True`.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Optional, Tuple


def _plain(v):
    if is_dataclass(v) and not isinstance(v, type):
        return {f.name: _plain(getattr(v, f.name)) for f in fields(v)}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    return v


class _Base:
    def to_dict(self):
        return _plain(self)


# ---------------------------------------------------------------------------------------------- input
@dataclass(frozen=True)
class InputIssue(_Base):
    code: str                       # one of the ui_policy input statuses
    message: str                    # user-facing
    field: str                      # "age" | "medications"
    detail: Any = None              # e.g. duplicated item_seqs / offending positions (no raw exception text)


@dataclass(frozen=True)
class InputValidationResult(_Base):
    status: str                     # VALID or the primary failing status (ui_policy.INPUT_STATUS_PRIORITY)
    issues: Tuple[InputIssue, ...]
    age: Optional[int]              # value to pass to Core (None only if the user chose "age unknown")
    medications: Tuple[str, ...]    # confirmed item_seq strings, in the user's order
    medication_names: Tuple[Tuple[str, Optional[str]], ...] = ()   # (item_seq, item_name) from search candidates
    dev_log: Tuple[str, ...] = ()   # developer-only diagnostics (exception class/message)

    @property
    def is_valid(self):
        return self.status == "VALID"


# ---------------------------------------------------------------------------------------------- errors
@dataclass(frozen=True)
class ErrorView(_Base):
    code: str
    layer: str                      # L0_INPUT | L1_RESOURCE | L2_CORE | L3_REPORT | L4_FINDING
    user_message: str
    abort: bool                     # True → no results are displayed
    partial_result: bool            # True → results are displayed but some parts are missing
    finding_id: Optional[str] = None
    dev_log: Optional[str] = None   # excluded from the user payload (see SafetyCheckViewModel.to_dict)


@dataclass(frozen=True)
class Notice(_Base):
    code: str
    level: str                      # info | warning
    message: str
    item_seqs: Tuple[str, ...] = ()


# ---------------------------------------------------------------------------------------------- patient
@dataclass(frozen=True)
class ElderlyStatusView(_Base):
    code: str                       # evaluated | not_applicable_age_below_threshold | not_evaluated_age_missing
    label: str
    message: Optional[str]
    show_count: bool                # False → the renderer must NOT show the number 0


@dataclass(frozen=True)
class PatientView(_Base):
    age: Optional[Any]              # verbatim R.screening.patient.age
    age_display: str
    elderly: ElderlyStatusView


@dataclass(frozen=True)
class MedicationView(_Base):
    item_seq: str
    item_name: Optional[str]        # from the user's search candidate (Core report has no input-name list)
    display_name: str               # item_name or item_seq
    in_dur_tables: bool             # False iff listed in R.screening.patient.not_found_in_dur_tables


# ---------------------------------------------------------------------------------------------- summary
@dataclass(frozen=True)
class CountTile(_Base):
    risk_type: str
    label: str
    icon: str
    count: Optional[int]            # None when not evaluated (elderly) — never a fabricated 0
    display_text: str


@dataclass(frozen=True)
class SummaryView(_Base):
    total_signals: int
    tiles: Tuple[CountTile, ...]
    legend: str
    llm_unavailable_banner: Optional[str]


@dataclass(frozen=True)
class NoFindingView(_Base):
    message: str
    scope_note: str


# ---------------------------------------------------------------------------------------------- finding
@dataclass(frozen=True)
class DrugView(_Base):
    item_seq: str
    item_name: Optional[str]
    display_name: str
    ingredient_names: Tuple[str, ...]


@dataclass(frozen=True)
class StatementView(_Base):
    text: str                       # verbatim o.evidence_statements[k].statement
    evidence_ids: Tuple[str, ...]   # verbatim


@dataclass(frozen=True)
class ExplanationView(_Base):
    """Present ONLY when display_mode == EXPLANATION. All text verbatim from the validated LLM output."""
    summary: str
    statements: Tuple[StatementView, ...]
    no_statements_text: Optional[str]
    evidence_status: str
    evidence_status_label: str      # describes the explanation's evidence basis, NOT a risk level
    evidence_status_tooltip: str
    limitations: Optional[str]
    review_note: str


@dataclass(frozen=True)
class EvidenceView(_Base):
    evidence_id: str                # verbatim, never renumbered
    item_seq: str
    item_name: Optional[str]
    display_name: str
    location: str
    chunk_text: str                 # verbatim, never truncated
    evidence_source: str
    cited: bool                     # True only in EXPLANATION mode
    license_badge: Optional[str]
    change_date: Optional[str]
    shared_item_seqs: Tuple[str, ...]   # empty unless ≥ 2


@dataclass(frozen=True)
class EvidenceSectionView(_Base):
    title: str
    items: Tuple[EvidenceView, ...]


@dataclass(frozen=True)
class FindingView(_Base):
    finding_id: str
    risk_type: str
    risk_label: str
    risk_icon: str
    rule_source: Optional[str]
    drugs: Tuple[DrugView, ...]
    canonical_pair_id: Optional[str]
    effect_name: Optional[str]
    dur_rule_label: str
    dur_rule_lines: Tuple[str, ...]
    retrieval_notices: Tuple[str, ...]
    display_mode: str
    status_message: Optional[str]   # None only in EXPLANATION
    status_severity: Optional[str]
    explanation_title: str
    explanation: Optional[ExplanationView]
    evidence: Optional[EvidenceSectionView]
    clinician_review_text: str


# ---------------------------------------------------------------------------------------------- meta
@dataclass(frozen=True)
class MetadataView(_Base):
    core: dict                      # copied from R.pipeline / R.screening.engine (Core-reported)
    adapter: dict                   # measured / supplied by the adapter (timing, device, deployment)


@dataclass(frozen=True)
class DebugInfo(_Base):
    """Developer-only. Never part of the default user payload."""
    report_warnings: Tuple[dict, ...] = ()
    report_errors: Tuple[dict, ...] = ()
    invalid_inputs: Tuple[str, ...] = ()
    findings: Tuple[dict, ...] = ()
    validation_failures: Tuple[str, ...] = ()
    error_logs: Tuple[dict, ...] = ()
    generation_status_counts: dict = field(default_factory=dict)
    llm_calls: Optional[int] = None


@dataclass(frozen=True)
class SafetyCheckViewModel(_Base):
    state: str
    can_display_results: bool
    patient: Optional[PatientView]
    medications: Tuple[MedicationView, ...]
    summary: Optional[SummaryView]
    findings: Tuple[FindingView, ...]
    no_finding: Optional[NoFindingView]
    notices: Tuple[Notice, ...]
    errors: Tuple[ErrorView, ...]
    input_issues: Tuple[InputIssue, ...]
    scope_note: Optional[str]
    input_scope_note: str
    metadata: MetadataView
    debug: DebugInfo = field(default_factory=DebugInfo)

    def to_dict(self, include_debug=False):
        d = _plain(self)
        if not include_debug:
            d.pop("debug", None)
            for e in d["errors"]:
                e.pop("dev_log", None)
        return d
