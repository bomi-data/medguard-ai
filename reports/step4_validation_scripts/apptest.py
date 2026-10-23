import sys, os, time
from pathlib import Path
R = Path(sys.argv[1]); os.chdir(R)
from streamlit.testing.v1 import AppTest
t = time.time()
at = AppTest.from_file(str(R / "app.py"), default_timeout=900)
at.run()
print("run_seconds", round(time.time() - t, 1))
print("exceptions", [str(e.value)[:300] for e in at.exception])
print("errors", [e.value[:200] for e in at.error])
print("warnings", [w.value[:160] for w in at.warning][:6])
print("titles", [x.value[:80] for x in at.title] + [x.value[:80] for x in at.header][:8])
print("buttons", [b.label for b in at.button][:12])
print("text_inputs", [ti.label for ti in at.text_input][:6])
print("markdown_has_disclaimer", any(("연구" in m.value or "임상" in m.value) for m in at.markdown) or any("연구" in c.value for c in at.caption))
