"""dur_safety — production package of the Korean DUR polypharmacy safety RAG.

Modules
  config      paths, pinned model revision / prompt identifiers (environment only)
  resources   one-time loading + verification of artifacts against the evaluated configs
  screening   02 structured DUR screening engine (verbatim)
  retrieval   04 hybrid retrieval as loaded by 05 (verbatim)
  findings    05 screening record -> ScreeningFinding (verbatim)
  generation  05 evidence-grounded explanation (verbatim)
  pipeline    run_safety_check(age, medications, llm_fn=call_llm)
  drug_lookup name -> candidate item_seq list (new input adapter; outside evaluated scope)

Usage
  from dur_safety import resources, pipeline
  resources.load_resources()                       # once per process
  report = pipeline.run_safety_check(age=72, medications=["195700013", "196900031"])
"""
__all__ = ["config", "resources", "screening", "retrieval", "findings", "generation", "pipeline", "drug_lookup"]
__version__ = "0.1.0"
