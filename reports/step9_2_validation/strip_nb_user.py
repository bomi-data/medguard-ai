"""Remove only the Colab executionInfo "user" block (displayName/userId) from a notebook, editing raw text.

The block is the last key of executionInfo, so the preceding comma + newline/indent is removed with it.
Writes only if cell sources/outputs, all other executionInfo fields and notebook metadata are unchanged.
"""
import json
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
raw = p.read_bytes()
text = raw.decode("utf-8")
pat = re.compile(r',(\r?\n[ \t]*)"user": \{\s*"displayName": "[^"]*",\s*"userId": "[^"]*"\s*\}')
new, n = pat.subn("", text)

before, after = json.loads(text), json.loads(new)
src = lambda nb: [("".join(c["source"]), c["cell_type"], c.get("outputs")) for c in nb["cells"]]
assert src(before) == src(after), "cell sources/outputs changed"
for cb, ca in zip(before["cells"], after["cells"]):
    mb, ma = dict(cb.get("metadata", {})), dict(ca.get("metadata", {}))
    if "executionInfo" in mb:
        eb = dict(mb.pop("executionInfo"))
        eb.pop("user", None)
        assert eb == ma.pop("executionInfo"), "other executionInfo fields changed"
    assert mb == ma, "other cell metadata changed"
assert before["metadata"] == after["metadata"], "notebook metadata changed"
p.write_bytes(new.encode("utf-8"))
print("removed blocks:", n, "| bytes", len(raw), "->", len(new.encode("utf-8")))
