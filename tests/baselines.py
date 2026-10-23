"""Read-only access to the evaluated baselines (06-A..06-E, 04 smoke, 05 smoke). Never writes."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


class Baselines:
    def __init__(self, project_root):
        self.root = Path(project_root)
        p = self.root / "data" / "processed"
        self.eval_dir, self.gen_dir, self.ret_dir = p / "evaluation", p / "generation", p / "retrieval"

    def _pq(self, path, required=True):
        if not path.exists():
            if required:
                raise FileNotFoundError(path)
            return None
        return pd.read_parquet(path)

    # 06-A frozen cases / retrieval
    @property
    def queries(self):
        return self._pq(self.eval_dir / "evaluation_queries.parquet")

    @property
    def retrieval_raw(self):
        return self._pq(self.eval_dir / "evaluation_retrieval_raw.parquet")

    @property
    def retrieval_runs(self):
        return self._pq(self.eval_dir / "evaluation_retrieval_runs.parquet", required=False)

    @property
    def pool_master(self):
        return self._pq(self.eval_dir / "evaluation_pool_master.parquet", required=False)

    @property
    def annotation(self):
        return self._pq(self.eval_dir / "evaluation_annotation_completed.parquet", required=False)

    # 06-D generation (30 cases)
    @property
    def gen_eval_results(self):
        return self._pq(self.eval_dir / "generation_eval_results.parquet")

    @property
    def gen_eval_evidence(self):
        return self._pq(self.eval_dir / "generation_eval_evidence.parquet")

    # 06-E real screening runs
    @property
    def e2e_screening(self):
        return self._pq(self.eval_dir / "end_to_end_screening_runs.parquet")

    # 05 smoke (3 cases)
    @property
    def gen05_results(self):
        return self._pq(self.gen_dir / "generation_results.parquet")

    @property
    def gen05_evidence(self):
        return self._pq(self.gen_dir / "generation_evidence.parquet")

    @property
    def gen05_failure_tests(self):
        return json.loads((self.gen_dir / "generation_failure_tests.json").read_text())

    # 04 smoke
    @property
    def smoke_results(self):
        return self._pq(self.ret_dir / "smoke_test_results.parquet")

    @property
    def smoke_queries(self):
        return json.loads((self.ret_dir / "smoke_test_queries.json").read_text())

    def qrels(self):
        """(query_id, chunk_id) -> human relevance grade (06-A/06-B structure: annotation_id -> pool_master)."""
        ann, pool = self.annotation, self.pool_master
        if ann is None or pool is None:
            return {}
        q = (ann[["annotation_id", "relevance_label"]]
             .assign(grade=lambda d: pd.to_numeric(d["relevance_label"], errors="coerce"))
             .merge(pool[["annotation_id", "query_id", "chunk_id"]], on="annotation_id", how="inner",
                    validate="one_to_one"))
        return {(a, b): g for a, b, g in zip(q.query_id, q.chunk_id, q.grade)}
