"""Check OPENAI_API_KEY wiring WITHOUT printing the key and WITHOUT a billed generation call.

Usage (from the project root, after setting the key):
    .venv\\Scripts\\python.exe -X utf8 reports\\step8_prep\\check_openai_connection.py           # local checks only
    .venv\\Scripts\\python.exe -X utf8 reports\\step8_prep\\check_openai_connection.py --online  # + models.retrieve

Step 1 (offline): is the key visible to the same function the app uses (generation.get_secret)?
Step 2 (--online): models.retrieve(<configured model>) — authenticates the key and confirms access to the
configured model. It does not generate tokens (no responses.create / chat call).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src")]

from dur_safety.generation import GENERATION_CONFIG, get_secret, _redact  # noqa: E402

name = GENERATION_CONFIG["api_key_name"]
model = GENERATION_CONFIG["model"]
key = get_secret(name)
print(f"[1] {name}: {'SET' if key else 'NOT SET'}  (value not shown)")
if key:
    print(f"    looks like an OpenAI key (starts with 'sk-'): {key.startswith('sk-')}")
    print(f"    surrounding whitespace / quotes present: {key != key.strip() or key[:1] in '\"' + chr(39)}")
print(f"[i] configured provider={GENERATION_CONFIG['provider']} model={model} api={GENERATION_CONFIG['api']} "
      f"store={GENERATION_CONFIG['store']}")

if "--online" in sys.argv:
    if not key:
        sys.exit("[2] skipped: key not set")
    import openai
    try:
        client = openai.OpenAI(api_key=key, max_retries=0, timeout=20)
        m = client.models.retrieve(model)
        print(f"[2] authentication OK, model available: {m.id}")
    except Exception as e:  # noqa: BLE001
        print(f"[2] FAILED: {_redact(f'{type(e).__name__}: {str(e)[:300]}', key)}")
        sys.exit(1)
