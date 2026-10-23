"""STEP 8-E: run the unchanged app.py under Streamlit with a hard cap on billed LLM calls.

    streamlit run reports/step8_validation/capped_launcher.py
    env: MEDGUARD_STEP8_LEDGER=<jsonl path>, MEDGUARD_STEP8_MAX_CALLS=<int>

generation.PROVIDERS["OpenAI"] (looked up by call_llm at call time) is wrapped once per process. The wrapper
refuses to call when the ledger already holds MAX_CALLS rows (returns an LLM_ERROR response, which the app
shows as a generation failure), otherwise calls the original _call_openai and appends usage / latency /
stop_reason / error / output text to the ledger. The API key is never read or written here.
No file under src/, app/, ui_integration/ or data/ is modified.
"""
import hashlib
import json
import os
import runpy
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [p for p in (str(ROOT), str(ROOT / "src")) if p not in sys.path]

from dur_safety import generation  # noqa: E402

LEDGER = Path(os.environ["MEDGUARD_STEP8_LEDGER"])
MAX_CALLS = int(os.environ["MEDGUARD_STEP8_MAX_CALLS"])

if not getattr(generation, "_STEP8_CAPPED", False):
    _orig = generation.PROVIDERS["OpenAI"]

    def _capped(system, user, cfg):
        rows = LEDGER.read_text(encoding="utf-8").splitlines() if LEDGER.exists() else []
        if len(rows) >= MAX_CALLS:
            return generation.LLMResponse(None, cfg["provider"], cfg["model"], error=f"STEP8_CAP_REACHED ({MAX_CALLS})")
        t = time.time()
        resp = _orig(system, user, cfg)
        row = {"n": len(rows) + 1, "ts": round(t, 1), "model": resp.model, "usage": resp.usage,
               "latency_s": resp.latency_s, "stop_reason": resp.stop_reason, "error": resp.error,
               "user_prompt_sha256": hashlib.sha256(user.encode()).hexdigest(), "output_text": resp.text}
        with LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return resp

    generation.PROVIDERS["OpenAI"] = _capped
    generation._STEP8_CAPPED = True

runpy.run_path(str(ROOT / "app.py"), run_name="__main__")
