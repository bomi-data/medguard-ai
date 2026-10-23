"""STEP 8-F: run the unchanged app.py with the OpenAI provider replaced by a replay of STEP 7-FINAL real responses.

    streamlit run reports/step8_validation/replay_launcher.py

The prompt the app builds is hashed; if it equals a stored 06-D prompt whose case has a recorded real
gpt-5.4-mini response in reports/step7final_validation/case_<ID>.json, that response text is returned
unchanged. Otherwise an LLM_ERROR response is returned. No network call, no API key use, no cost.
Core validation, ui_policy, adapters and rendering are the production code.
"""
import hashlib
import json
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [p for p in (str(ROOT), str(ROOT / "src")) if p not in sys.path]

import pandas as pd  # noqa: E402
from dur_safety import generation  # noqa: E402

if not getattr(generation, "_STEP8_REPLAY", False):
    stored = pd.read_parquet(ROOT / "data/processed/evaluation/generation_eval_results.parquet")
    sha_to_case = dict(zip(stored["user_prompt_sha256"], stored["query_id"]))
    replay = {}
    for p in (ROOT / "reports/step7final_validation").glob("case_*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("raw_response"):
            replay[d["case_id"]] = d["raw_response"]

    def _replay(system, user, cfg):
        cid = sha_to_case.get(hashlib.sha256(user.encode()).hexdigest())
        if cid not in replay:
            return generation.LLMResponse(None, cfg["provider"], cfg["model"], error="REPLAY_NO_MATCH")
        return generation.LLMResponse(replay[cid], cfg["provider"], cfg["model"], stop_reason="completed(replay)")

    generation.PROVIDERS["OpenAI"] = _replay
    generation._STEP8_REPLAY = True

runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
