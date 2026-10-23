r"""Replace the Windows user-name segment of absolute paths (C:\Users\<name>\) with C:\Users\<USER>\.

Edits raw bytes so CRLF line endings are kept. The name is read from MASK_NAME (never written to this file).
Usage: MASK_NAME=<windows user name> python -X utf8 mask_user_path.py <file> [<file> ...]
"""
import os
import sys
from pathlib import Path

name = os.environ["MASK_NAME"]
old = ("C:\\Users\\" + name + "\\").encode("utf-8")
new = b"C:\\Users\\<USER>\\"
for f in sys.argv[1:]:
    p = Path(f)
    b = p.read_bytes()
    out = b.replace(old, new)
    p.write_bytes(out)
    print(f"{b.count(old)} replaced, {out.count(name.encode('utf-8'))} remaining, "
          f"CRLF {b.count(b'\r\n')}->{out.count(b'\r\n')}  {f}")
