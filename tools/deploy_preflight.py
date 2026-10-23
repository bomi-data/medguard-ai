"""배포 전 사전 점검 (STEP 9-1). 읽기 전용 — 파일을 쓰거나 내려받지 않고, API 를 호출하지 않으며, 비밀값을 출력하지 않습니다.

  python tools/deploy_preflight.py            # 전체 점검 (데이터 SHA256 포함, 수십 초)
  python tools/deploy_preflight.py --quick    # SHA256 생략

종료 코드: 0 = 실행에 필요한 항목 모두 OK, 1 = 실행 불가 항목 있음(FAIL). WARN 은 실행은 되지만 확인이 필요한 항목입니다.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_MODEL = "BAAI/bge-m3"
EXPECTED_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
MODEL_FILES = ("modules.json", "config.json", "config_sentence_transformers.json", "sentence_bert_config.json",
               "1_Pooling/config.json", "pytorch_model.bin", "tokenizer.json", "tokenizer_config.json",
               "special_tokens_map.json")
AUDIT_DIRS = ("reports/ingredient_coverage_audit", "reports/ui_coverage_audit")   # app/utils/audit_reader.py 가 읽음
results = []


def report(status, item, detail=""):
    results.append((status, item))
    print(f"{status:5} {item}" + (f" — {detail}" if detail else ""))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def required_files():
    """app.py 의 REQUIRED_FILES 목록을 그대로 읽는다(목록을 이 파일에 복제하지 않음)."""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    m = re.search(r"REQUIRED_FILES\s*=\s*(\[.*?\])", src, re.S)
    return json.loads(m.group(1)) if m else []


def main(quick):
    v = sys.version_info
    report("OK" if (3, 11) <= v[:2] <= (3, 13) else "WARN", "Python", f"{v.major}.{v.minor}.{v.micro} (검증: 3.12.10 Windows / Linux wheel 해석 3.12·3.13)")

    req = required_files()
    missing = [r for r in req if not (ROOT / r).is_file()]
    report("FAIL" if missing or not req else "OK", "app.py REQUIRED_FILES", f"{len(req) - len(missing)}/{len(req)}" + (f" 누락: {missing}" if missing else ""))

    manifest = json.loads((ROOT / "data_manifest.json").read_text(encoding="utf-8"))["files"]
    if quick:
        absent = [e["path"] for e in manifest if not (ROOT / e["path"]).is_file()]
        report("WARN" if absent else "OK", "data_manifest 파일 존재(해시 생략)", f"{len(manifest) - len(absent)}/{len(manifest)}")
    else:
        bad = [e["path"] for e in manifest if not (ROOT / e["path"]).is_file()
               or (e.get("sha256") and sha256(ROOT / e["path"]) != e["sha256"])]
        report("FAIL" if bad else "OK", "data_manifest SHA256", f"{len(manifest) - len(bad)}/{len(manifest)}" + (f" 불일치/누락: {bad}" if bad else ""))

    for d in AUDIT_DIRS:
        runs = [p for p in (ROOT / d).glob("run_*") if (p / "audit_manifest.json").is_file() or d.endswith("ui_coverage_audit")]
        report("OK" if runs else "WARN", f"감사 결과 {d}", f"{len(runs)}개 run" if runs else "없음 — Gate/Coverage 화면이 비게 됩니다")

    override = {k: os.environ.get(k) for k in ("RETRIEVAL_DENSE_MODEL", "RETRIEVAL_DENSE_REVISION") if os.environ.get(k)}
    ok_override = all(val in (EXPECTED_MODEL, EXPECTED_REVISION) for val in override.values())
    report("OK" if ok_override else "FAIL", "검색 모델 환경변수 재정의", "없음" if not override else str(override))

    try:
        from huggingface_hub import try_to_load_from_cache
        missing_m = [f for f in MODEL_FILES if not isinstance(
            try_to_load_from_cache(EXPECTED_MODEL, f, revision=EXPECTED_REVISION), str)]
        report("OK" if not missing_m else "WARN", f"모델 캐시 {EXPECTED_MODEL}@{EXPECTED_REVISION[:8]}",
               "캐시에 있음" if not missing_m else f"캐시에 없음 {missing_m} — 최초 실행 시 약 2.3GB 다운로드 필요(HF_HUB_OFFLINE=1 이면 앱 시작 실패)")
    except Exception as e:  # noqa: BLE001
        report("WARN", "모델 캐시 확인", f"확인 불가: {type(e).__name__}")
    report("OK" if os.environ.get("HF_HUB_OFFLINE") != "1" or not [r for r in results if "모델 캐시" in r[1] and r[0] != "OK"]
           else "FAIL", "HF 오프라인 모드", os.environ.get("HF_HUB_OFFLINE") or "미설정")

    key_env = bool(os.environ.get("OPENAI_API_KEY"))
    secrets_file = (ROOT / ".streamlit" / "secrets.toml").is_file()
    report("OK" if (key_env or secrets_file) else "WARN", "OPENAI_API_KEY",
           "환경변수 있음" if key_env else ("secrets.toml 있음" if secrets_file else "없음 — LLM 설명 비활성(판정·근거는 동작)") + " (값은 표시하지 않음)")

    cfg = (ROOT / ".streamlit" / "config.toml")
    report("OK" if cfg.is_file() else "WARN", ".streamlit/config.toml", "있음" if cfg.is_file() else "없음")

    fails = [i for s, i in results if s == "FAIL"]
    print(f"\n결과: FAIL {len(fails)} / WARN {sum(s == 'WARN' for s, _ in results)} / OK {sum(s == 'OK' for s, _ in results)}")
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    sys.exit(main(ap.parse_args().quick))
