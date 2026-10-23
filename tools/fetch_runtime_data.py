"""런타임 데이터 확인/내려받기 도구 (TEMPLATE — URL 미설정, 원격 내려받기는 검증되지 않음).

  python tools/fetch_runtime_data.py --verify          # data_manifest.json 의 SHA256 과 로컬 파일 비교
  python tools/fetch_runtime_data.py --fetch           # 누락 파일을 MEDGUARD_DATA_BASE_URL/<경로> 에서 내려받아 SHA256 검증 후 저장
이 도구는 데이터를 업로드하지 않습니다. 내려받은 파일은 SHA256 이 일치하지 않으면 버립니다.
"""
import argparse, hashlib, json, os, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / "data_manifest.json").read_text(encoding="utf-8"))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def verify():
    bad = 0
    for e in MANIFEST["files"]:
        p = ROOT / e["path"]
        if not p.is_file():
            print("MISSING ", e["path"]); bad += 1
        elif e.get("sha256") and sha256(p) != e["sha256"]:
            print("MISMATCH", e["path"]); bad += 1
        else:
            print("OK      ", e["path"])
    return bad


def fetch():
    base = os.environ.get("MEDGUARD_DATA_BASE_URL", "").rstrip("/")
    if not base:
        print("MEDGUARD_DATA_BASE_URL 이 설정되지 않았습니다(NOT_CONFIGURED)."); return 2
    for e in MANIFEST["files"]:
        p = ROOT / e["path"]
        if p.is_file():
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".part")
        urllib.request.urlretrieve(base + "/" + e["path"], tmp)
        if e.get("sha256") and sha256(tmp) != e["sha256"]:
            tmp.unlink(); print("해시 불일치로 폐기:", e["path"]); return 1
        tmp.replace(p); print("내려받음:", e["path"])
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--verify", action="store_true"); ap.add_argument("--fetch", action="store_true")
    a = ap.parse_args()
    sys.exit(fetch() if a.fetch else (1 if verify() else 0))
