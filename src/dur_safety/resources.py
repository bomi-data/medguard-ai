"""Load all runtime artifacts once, verify them against the recorded evaluation configs, and wire the
module state that the notebooks kept in one global namespace (hand-written; no production logic).

Checks performed (same comparisons as 05 cells [8], [10] and 06-D's runtime checks):
  * sha256 of every runtime data file == generation/generation_config.json `inputs_sha256`
    (the hashes 05 recorded; 06-D/06-E ran on the same files). easy_drug_canonical has no recorded
    hash in any config — reported as such, covered by the screening regression test instead.
  * 04 QA all PASS, embedding meta (model, n_texts, hash order) == retrieval_config.json
  * BM25_PARAMS / HYBRID_PARAMS / RISK_PROFILES / DENSE_CONFIG == retrieval_config.json
  * dense model + revision == config.EXPECTED_DENSE_* == retrieval_config / generation_config
  * GENERATION_CONFIG, prompt version, SYSTEM_PROMPT sha256, RISK_INSTRUCTIONS, OUTPUT_INSTRUCTION,
    OUTPUT_JSON_SCHEMA, DIRECTIVE_PATTERNS == generation_config.json
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

from . import config, screening, retrieval, findings, generation

_LOCK = threading.Lock()
_STATE = {"loaded": False, "report": None}


class ResourceVerificationError(RuntimeError):
    pass


def _sha256(path, chunk=8 * 1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def verify_files(paths: config.ProjectPaths, verify_hashes=True):
    gen_cfg = json.loads(paths.generation_config.read_text())
    recorded = gen_cfg["inputs_sha256"]
    files = paths.runtime_files()
    missing = [k for k, p in files.items() if not Path(p).exists()]
    if missing:
        raise FileNotFoundError(f"runtime artifacts missing: {missing}")
    out = {}
    for k, p in files.items():
        if k == "generation_config":
            out[k] = {"status": "CONTENT_CHECKED"}           # its fields are compared in verify_runtime
            continue
        if k not in recorded:
            out[k] = {"status": "NO_RECORDED_HASH"}
            continue
        if not verify_hashes:
            out[k] = {"status": "SKIPPED"}
            continue
        got = _sha256(p)
        out[k] = {"status": "MATCH" if got == recorded[k] else "MISMATCH", "sha256": got, "recorded": recorded[k]}
    bad = [k for k, v in out.items() if v["status"] == "MISMATCH"]
    if bad:
        raise ResourceVerificationError(f"artifact sha256 differs from the evaluated version: {bad}")
    return out


def verify_runtime():
    """Configuration parity with the evaluated runs. Raises on any difference."""
    rc = retrieval.RETRIEVAL_CONFIG
    gc = json.loads(Path(_STATE["paths"].generation_config).read_text())
    checks = {
        # 05 cell [8]
        "04 QA all PASS": all(rc["qa"].values()),
        "embedding meta model_name": retrieval.emb_meta.get("model_name") == rc["dense"]["model_name"],
        "embedding meta n_texts": retrieval.emb_meta.get("n_texts") == rc["corpus"]["unique_text_hash"],
        "embedding meta hash_order_sha256": retrieval.emb_meta.get("hash_order_sha256") == rc["unique_text_hash_order_sha256"],
        "loaded unique-text order == 04": retrieval.HASH_ORDER_SHA == rc["unique_text_hash_order_sha256"],
        # 05 cell [10]
        "BM25_PARAMS == retrieval_config": retrieval.BM25_PARAMS == rc["bm25"],
        "HYBRID_PARAMS == retrieval_config": retrieval.HYBRID_PARAMS == rc["hybrid"],
        "RISK_PROFILES == retrieval_config": retrieval.RISK_PROFILES == rc["candidate_filtering"]["soft_preference"],
        "DENSE_CONFIG == retrieval_config": all(retrieval.DENSE_CONFIG[k] == rc["dense"][k] for k in retrieval.DENSE_CONFIG),
        # dense revision pin
        "dense model == expected": rc["dense"]["model_name"] == config.EXPECTED_DENSE_MODEL
                                   == gc["retrieval_reference"]["dense_model"],
        "dense revision == expected": rc["dense"]["resolved_revision"] == config.EXPECTED_DENSE_REVISION
                                      == gc["retrieval_reference"]["dense_revision"],
        "dense revision used for loading": retrieval.DENSE_STATE.get("revision") == config.EXPECTED_DENSE_REVISION,
        # 06-D runtime checks against 05 generation_config.json
        "GENERATION_CONFIG == 05": generation.GENERATION_CONFIG == gc["generation_config"],
        "PROMPT_VERSION / OUTPUT_SCHEMA_VERSION == 05": (generation.PROMPT_VERSION, generation.OUTPUT_SCHEMA_VERSION)
            == (gc["prompt_version"], gc["output_schema_version"])
            == (config.EXPECTED_PROMPT_VERSION, config.EXPECTED_OUTPUT_SCHEMA_VERSION),
        "SYSTEM_PROMPT sha256 == 05": generation.SYSTEM_PROMPT_SHA256 == gc["system_prompt_sha256"]
                                      == config.EXPECTED_SYSTEM_PROMPT_SHA256,
        "RISK_INSTRUCTIONS == 05": generation.RISK_INSTRUCTIONS == gc["risk_instructions"],
        "OUTPUT_INSTRUCTION == 05": generation.OUTPUT_INSTRUCTION == gc["output_instruction"],
        "OUTPUT_JSON_SCHEMA == 05": generation.OUTPUT_JSON_SCHEMA == gc["output_json_schema"],
        "DIRECTIVE_PATTERNS == 05": generation.DIRECTIVE_PATTERNS == gc["directive_patterns"],
        "store=False": generation.GENERATION_CONFIG.get("store") is False,
    }
    bad = [k for k, v in checks.items() if not v]
    if bad:
        raise ResourceVerificationError(f"runtime configuration differs from the evaluated system: {bad}")
    return checks


def load_resources(project_root=None, *, require_dense=True, verify_hashes=True, force=False):
    """Load screening lookups, retrieval index (BM25 + bge-m3) and generation wiring exactly once.

    require_dense=True (production default): raise if the dense model/index cannot be loaded, because
    the evaluated retrieval is hybrid (BM25 + dense + prior); 04's DEGRADED mode was never evaluated.
    """
    with _LOCK:
        if _STATE["loaded"] and not force:
            return _STATE["report"]
        t0 = time.time()
        paths = config.project_paths(project_root)
        _STATE["paths"] = paths
        file_checks = verify_files(paths, verify_hashes=verify_hashes)
        screening.init_screening(paths)
        retrieval.init_retrieval(paths)
        # 05 kept everything in one namespace; wire the shared objects explicitly.
        findings.cevi_lu = retrieval.cevi_lu
        generation.CHUNK_META = retrieval.CHUNK_META
        runtime_checks = verify_runtime()
        dense_ready = bool(retrieval.dense_available())
        if require_dense and not dense_ready:
            raise ResourceVerificationError(
                f"dense retrieval unavailable ({retrieval.DENSE_STATE.get('error')}); the evaluated system is hybrid")
        report = {
            "project_root": str(paths.project_root),
            "files": file_checks,
            "runtime_checks": runtime_checks,
            "dense_state": {k: v for k, v in retrieval.DENSE_STATE.items()},
            "dense_ready": dense_ready,
            "versions": dict(retrieval.VERSIONS),
            "screening_data_snapshot": dict(screening.DATA_SNAPSHOT),
            "corpus_rows": int(len(retrieval.corpus)),
            "unique_texts": int(len(retrieval.UNIQUE_TEXTS)),
            "load_seconds": round(time.time() - t0, 1),
        }
        _STATE.update(loaded=True, report=report)
        return report


def is_loaded():
    return _STATE["loaded"]
