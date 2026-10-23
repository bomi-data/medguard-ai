"""app — UI Adapter / ViewModel layer between the Frozen Core (dur_safety) and the Streamlit UI.

    adapters     Input Adapter (validate_input), execute(), Output Adapter (build_view_model)
    view_models  immutable ViewModel dataclasses (to_dict() for rendering / JSON)
    ui_policy    fixed UI texts, MVP limits, display-mode decision (allowlist)

No Streamlit code lives here. Nothing in this package modifies or re-implements Core logic.
See docs/UI_ADAPTER_DESIGN.md.
"""
from .ui_policy import ADAPTER_NAME, ADAPTER_VERSION, CONTRACT_VERSION

__all__ = ["adapters", "view_models", "ui_policy", "ADAPTER_NAME", "ADAPTER_VERSION", "CONTRACT_VERSION"]
__version__ = ADAPTER_VERSION
