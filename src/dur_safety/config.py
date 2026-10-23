"""Paths and pinned identifiers (hand-written; environment only — no production logic).

Replaces the Colab-specific parts of the notebooks:
  * `drive.mount("/content/drive")` and the hard-coded `/content/drive/MyDrive/medical-ai-project`
    -> project root from argument or MEDICAL_AI_PROJECT_ROOT (the same variable the notebooks honoured).
  * `try: from google.colab import drive` used as an IN_COLAB flag -> import-free detection.
"""
from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path

# Same meaning as the notebooks' IN_COLAB flag; used only by generation.get_secret (Colab Secrets vs env).
def _in_colab():
    try:
        return importlib.util.find_spec("google.colab") is not None
    except ModuleNotFoundError:          # parent package "google" absent
        return False


IN_COLAB = _in_colab()

COLAB_DEFAULT_PROJECT_ROOT = Path("/content/drive/MyDrive/medical-ai-project")

# Dense model actually used in evaluation. Source (not guessed):
#   data/processed/retrieval/retrieval_config.json      -> dense.model_name / dense.resolved_revision
#   data/processed/generation/generation_config.json    -> retrieval_reference.dense_model / dense_revision
# resources.verify_runtime() asserts both files still contain these values.
EXPECTED_DENSE_MODEL = "BAAI/bge-m3"
EXPECTED_DENSE_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"

# Generation identifiers evaluated in 06-D (checked against generation_config.json at load time).
EXPECTED_PROMPT_VERSION = "05-explain-v1"
EXPECTED_OUTPUT_SCHEMA_VERSION = "05-output-v1"
EXPECTED_SYSTEM_PROMPT_SHA256 = "ec6be76bcdc825379354938e5b97f84d0706f3a06ac7f4e36073dc1ac4af796b"


def resolve_project_root(project_root=None) -> Path:
    candidates = []
    if project_root:
        candidates.append(Path(project_root))
    if os.environ.get("MEDICAL_AI_PROJECT_ROOT"):
        candidates.append(Path(os.environ["MEDICAL_AI_PROJECT_ROOT"]))
    candidates.append(COLAB_DEFAULT_PROJECT_ROOT)
    for c in candidates:
        if (c / "data" / "processed").exists():
            return c
    raise FileNotFoundError(
        "medical-ai-project root not found. Pass project_root=... or set MEDICAL_AI_PROJECT_ROOT "
        f"(tried: {[str(c) for c in candidates]})")


@dataclass(frozen=True)
class ProjectPaths:
    project_root: Path

    @property
    def processed(self):
        return self.project_root / "data" / "processed"

    @property
    def screening_dir(self):
        return self.processed / "screening"

    @property
    def evidence_dir(self):
        return self.processed / "evidence"

    @property
    def rag_dir(self):
        return self.processed / "rag"

    @property
    def retrieval_dir(self):
        return self.processed / "retrieval"

    @property
    def generation_dir(self):
        return self.processed / "generation"

    # --- runtime artifacts (read-only) ---
    @property
    def contraindication_pairs(self):
        return self.screening_dir / "contraindication_pairs.parquet"

    @property
    def contraindication_evidence(self):
        return self.screening_dir / "contraindication_evidence.parquet"

    @property
    def elderly_caution_rules(self):
        return self.screening_dir / "elderly_caution_rules.parquet"

    @property
    def therapeutic_group_mapping(self):
        return self.screening_dir / "therapeutic_group_mapping.parquet"

    @property
    def easy_drug_canonical(self):
        return self.evidence_dir / "easy_drug_canonical.parquet"

    @property
    def approval_chunks(self):
        return self.rag_dir / "approval_chunks.parquet"

    @property
    def unique_text_index(self):
        return self.retrieval_dir / "unique_text_index.parquet"

    @property
    def text_hash_mapping(self):
        return self.retrieval_dir / "text_hash_mapping.parquet"

    @property
    def retrieval_config(self):
        return self.retrieval_dir / "retrieval_config.json"

    @property
    def generation_config(self):
        return self.generation_dir / "generation_config.json"

    def runtime_files(self, dense_slug="BAAI__bge-m3"):
        dense_dir = self.retrieval_dir / "dense" / dense_slug
        return {
            "contraindication_pairs": self.contraindication_pairs,
            "contraindication_evidence": self.contraindication_evidence,
            "elderly_caution_rules": self.elderly_caution_rules,
            "therapeutic_group_mapping": self.therapeutic_group_mapping,
            "easy_drug_canonical": self.easy_drug_canonical,
            "approval_chunks": self.approval_chunks,
            "unique_text_index": self.unique_text_index,
            "text_hash_mapping": self.text_hash_mapping,
            "dense_embeddings": dense_dir / "unique_text_embeddings.npy",
            "dense_embedding_meta": dense_dir / "embedding_meta.json",
            "retrieval_config": self.retrieval_config,
            "generation_config": self.generation_config,
        }


def project_paths(project_root=None) -> ProjectPaths:
    return ProjectPaths(resolve_project_root(project_root))
