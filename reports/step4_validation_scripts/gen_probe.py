import sys, json, io, contextlib, dataclasses, os
from pathlib import Path
R = Path(sys.argv[1]); sys.path[:0] = [str(R), str(R/"src")]
os.environ.pop("OPENAI_API_KEY", None)
import openai
class _Blocked:
    def __init__(self, *a, **k): raise AssertionError("network LLM client construction blocked in probe")
openai.OpenAI = _Blocked
from dur_safety import resources, pipeline, generation
from app import adapters
with contextlib.redirect_stdout(io.StringIO()): resources.load_resources(str(R), require_dense=False)
MEDS = ["195700013", "196900031"]          # 05 smoke Q2 (contraindication) pair
def mk(text_fn):
    def llm(system, user):
        fid = json.loads(user[user.index("{"):])["finding"]["finding_id"] if False else None
        return text_fn(system, user)
    return llm
captured = {}
def finding_and_ids(user):
    # build_prompt embeds finding + evidence; recover finding_id / evidence ids from the GenerationInput instead
    return captured["fid"], captured["rt"], captured["ids"]
orig_build = generation.build_prompt
def spy_build(gi):
    captured.update(fid=gi.finding.finding_id, rt=gi.finding.risk_type, ids=[e.evidence_id for e in gi.evidence])
    return orig_build(gi)
generation.build_prompt = spy_build
def obj(stmts, status="SUFFICIENT", summary="허가정보에 병용 관련 기재가 있습니다."):
    fid, rt, ids = captured["fid"], captured["rt"], captured["ids"]
    return {"finding_id": fid, "risk_type": rt, "summary": summary, "evidence_statements": stmts(ids),
            "evidence_status": status, "limitations": "검색된 허가정보 범위 내 설명입니다.", "review_note": "의료진 확인 필요."}
L = lambda f: (lambda s, u: generation.LLMResponse(json.dumps(f(), ensure_ascii=False), "mock", "mock", stop_reason="completed"))
cases = {
 "real_call_llm_no_key": generation.call_llm,
 "mock_valid_cites_provided": L(lambda: obj(lambda ids: [{"statement": f"허가정보에 관련 기재가 있습니다 [{ids[0]}].", "evidence_ids": [ids[0]]}])),
 "mock_hallucinated_evidence_id": L(lambda: obj(lambda ids: [{"statement": "근거에 없는 새로운 금기 관계가 있습니다 [E_FAKE_999].", "evidence_ids": ["E_FAKE_999"]}])),
 "mock_uncited_statement": L(lambda: obj(lambda ids: [{"statement": "근거 표시 없이 단정하는 문장입니다.", "evidence_ids": []}])),
 "mock_directive_language": L(lambda: obj(lambda ids: [{"statement": f"즉시 중단해야 합니다 [{ids[0]}].", "evidence_ids": [ids[0]]}])),
}
out = {}
for name, fn in cases.items():
    rep = pipeline.run_safety_check(72, MEDS, llm_fn=fn, include_records=True)
    f = rep["findings"][0]; g = f["generation"]; rec = f.get("record", {})
    vm = adapters.build_view_model(report=rep)
    vm_txt = json.dumps(dataclasses.asdict(vm) if dataclasses.is_dataclass(vm) else str(vm), ensure_ascii=False, default=str)
    out[name] = {
        "screening_counts": rep["summary"] if "summary" in rep else None,
        "n_findings": len(rep["findings"]), "risk_type": f["risk_type"],
        "retrieval_status": (f.get("retrieval") or {}).get("status"), "retrieval_method": (f.get("retrieval") or {}).get("method"),
        "n_evidence": len(f.get("evidence") or []),
        "evidence_sources_ok": all(e.get("evidence_id") and e.get("chunk_id") and e.get("ITEM_SEQ") in MEDS for e in f.get("evidence") or []),
        "generation_status": g.get("status"), "citation_errors": rec.get("citation_errors"), "directive_flags": rec.get("directive_flags"),
        "llm_error_prefix": (rec.get("llm_error") or "")[:40],
        "vm_state": getattr(vm, "state", None),
        "vm_contains_hallucinated_text": "새로운 금기 관계" in vm_txt, "vm_contains_directive_text": "즉시 중단해야" in vm_txt,
        "vm_contains_uncited_text": "근거 표시 없이" in vm_txt, "vm_screening_finding_kept": "195700013" in vm_txt, "vm_contains_valid_statement(positive_control)": "허가정보에 관련 기재가 있습니다" in vm_txt,
    }
print(json.dumps(out, ensure_ascii=True, indent=1))
