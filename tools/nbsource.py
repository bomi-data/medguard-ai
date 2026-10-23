"""Notebook source extraction shared by tools/build_package.py and tests/test_source_parity.py.

The production package (src/dur_safety) is generated from the evaluated notebooks
(02_structured_screening / 04_retrieval / 05_rag_generation) by copying top-level
definitions verbatim. This module defines *what* is copied (MANIFEST) and *how*
notebook statements are selected, so that the parity test re-derives exactly the
same source and compares it with the package at the AST level.

Pure standard library. Not imported by the runtime package.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

NOTEBOOKS = {
    "02": "02_structured_screening.ipynb",
    "04": "04_retrieval.ipynb",
    "05": "05_rag_generation.ipynb",
}

# --------------------------------------------------------------------------------------
# What is copied, in module order. (module, notebook, [names]) — first top-level definition
# with that name in the notebook (same rule as 05 `extract_from_notebook`).
# --------------------------------------------------------------------------------------
MANIFEST = {
    "screening": ("02", [
        "load_parquet", "require_columns", "pick_first_existing",
        "_MISSING_TEXT", "normalize_identifier", "normalize_identifier_series", "assert_no_nan_text",
        "make_canonical_pair", "clean_value", "unique_sorted_texts", "_optional_column",
        "get_contraindication_evidence", "_add_names", "get_drug_name",
        "normalize_medication_list", "build_contraindication_record", "check_contraindications",
        "ELDERLY_AGE_THRESHOLD", "validate_age", "elderly_check_status", "check_elderly_caution",
        "check_therapeutic_duplication",
        "ENGINE_NAME", "ENGINE_VERSION", "SCOPE_NOTE", "screen_patient",
    ]),
    "retrieval": ("04", [
        # == 05 RUNTIME_CONSTANTS + RUNTIME_FUNCTIONS (05 cell [10]), in 04 notebook order
        "META_COLS", "RISK_PROFILES", "_MISSING_TEXT", "normalize_identifier", "get_candidates",
        "EVIDENCE_SOURCE", "RESULT_COLS", "build_results", "make_status",
        "BM25_PARAMS", "bm25_scores", "rank_bm25", "retrieve_bm25",
        "DENSE_CONFIG", "encode_texts", "rank_dense", "dense_available", "retrieve_dense",
        "HYBRID_PARAMS", "rrf", "balance_by_item", "retrieve_hybrid",
        "_names", "finding_elderly", "finding_contraindication", "finding_therapeutic", "build_query",
    ]),
    "findings": ("05", [
        "SUPPORTED_RISK_TYPES", "RULE_SOURCE", "RISK_LABEL_KO",
        "DrugRef", "ScreeningFinding", "RetrievalResult", "EvidenceItem", "GenerationInput",
        "_uniq", "_contra_ingredients", "finding_from_02_record", "findings_from_screening_result",
    ]),
    "generation": ("05", [
        "GENERATION_CONFIG", "PROMPT_VERSION", "OUTPUT_SCHEMA_VERSION", "get_secret",
        "finding04_from_case", "to_retrieval_result", "retrieve_evidence",
        "EVIDENCE_REQUIRED", "validate_evidence_rows", "_val", "prepare_evidence_context",
        "SYSTEM_PROMPT", "RISK_INSTRUCTIONS", "@assert:29", "OUTPUT_INSTRUCTION", "OUTPUT_JSON_SCHEMA",
        "SYSTEM_PROMPT_SHA256",
        "render_finding", "render_evidence", "build_prompt",
        "LLMResponse", "_redact", "_call_openai", "PROVIDERS", "call_llm",
        "CITATION_RE", "DIRECTIVE_PATTERNS", "extract_citations", "validate_output",
        "deterministic_no_evidence_output", "generate_explanation",
    ]),
}

# Notebook "global initialization" that builds the in-memory lookups. Copied statement by
# statement into one loader function per module (display/print statements removed).
# Each entry: (notebook, cell_index, only_names or None)
INIT_MANIFEST = {
    "screening": [
        ("02", 2, None), ("02", 5, None), ("02", 6, None), ("02", 7, None), ("02", 9, None),
        ("02", 10, None), ("02", 11, None), ("02", 15, None), ("02", 17, None), ("02", 19, None),
        ("02", 20, None), ("02", 22, None), ("02", 23, None), ("02", 24, None), ("02", 25, None),
        ("02", 26, None), ("02", 35, ["DATA_SNAPSHOT"]),
    ],
    "retrieval": [
        # 05 runtime loading of the 04 index (05 cells [12] corpus/unique texts, [14] lookups),
        # 04 BM25 index build (= 05 BM25_BUILD, executed by 05 cell [16]), 05 cell [17] dense.
        ("05", 12, None), ("05", 14, None),
        ("04", 15, ["BM25_VECTORIZER", "BM25_X", "_df", "BM25_IDF", "BM25_DL", "BM25_AVGDL"]),
        ("05", 17, None),
    ],
}

DISPLAY_CALLS = {"print", "display", "describe_identifier"}
DISPLAY_METHODS = {"head"}


def load_code_cells(nb_path):
    nb = json.loads(Path(nb_path).read_text(encoding="utf-8"))
    out = {}
    for idx, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code":
            continue
        src = cell["source"] if isinstance(cell["source"], str) else "".join(cell["source"])
        out[idx] = src
    return out


def node_name(node):
    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None


def segment(src, node):
    """Exact source lines of a top-level node, including decorators."""
    lines = src.splitlines()
    start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return "\n".join(lines[start - 1:node.end_lineno])


def find_definition(cells, name):
    """First top-level definition named `name` (notebook order). Returns (cell_idx, node, segment)."""
    if name.startswith("@assert:"):
        idx = int(name.split(":")[1])
        tree = ast.parse(cells[idx])
        nodes = [n for n in tree.body if isinstance(n, ast.Assert)]
        if len(nodes) != 1:
            raise RuntimeError(f"cell {idx}: expected exactly one top-level assert")
        return idx, nodes[0], segment(cells[idx], nodes[0])
    for idx, src in cells.items():
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in tree.body:
            if node_name(node) == name:
                return idx, node, segment(src, node)
    raise RuntimeError(f"definition not found in notebook: {name}")


def is_display_stmt(node):
    """print/display/.head() expressions and loops that only print — notebook display code."""
    if isinstance(node, ast.Expr):
        v = node.value
        if isinstance(v, ast.Call):
            f = v.func
            if isinstance(f, ast.Name) and f.id in DISPLAY_CALLS:
                return True
            if isinstance(f, ast.Attribute) and f.attr in DISPLAY_METHODS:
                return True
            return False
        return isinstance(v, (ast.Name, ast.Attribute, ast.Subscript, ast.Constant))
    if isinstance(node, ast.For) and not node.orelse:
        return all(is_display_stmt(b) for b in node.body)
    return False


def init_statements(cells_by_nb, entries):
    """Selected top-level statements of init cells. Returns list of (nb, cell_idx, node, segment)."""
    out = []
    for nb, idx, only in entries:
        src = cells_by_nb[nb][idx]
        tree = ast.parse(src)
        picked = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
                continue
            if is_display_stmt(node):
                continue
            if only is not None and node_name(node) not in only:
                continue
            picked.append((nb, idx, node, segment(src, node)))
        if only is not None and [node_name(p[2]) for p in picked] != list(only):
            raise RuntimeError(f"{nb} cell {idx}: expected {only}, got {[node_name(p[2]) for p in picked]}")
        out.extend(picked)
    return out


class _StoreCollector(ast.NodeVisitor):
    """Names bound at function scope (excludes comprehension / lambda / nested def scopes)."""

    def __init__(self):
        self.names = []

    def _add(self, name):
        if name not in self.names:
            self.names.append(name)

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self._add(node.id)

    def visit_ListComp(self, node):
        pass

    visit_SetComp = visit_DictComp = visit_GeneratorExp = visit_Lambda = visit_ListComp

    def visit_FunctionDef(self, node):
        pass

    visit_AsyncFunctionDef = visit_ClassDef = visit_FunctionDef

    def visit_ExceptHandler(self, node):
        if node.name:
            self._add(node.name)
        self.generic_visit(node)


def assigned_names(nodes):
    c = _StoreCollector()
    for n in nodes:
        c.visit(n)
    return c.names


def dump(node):
    return ast.dump(node, include_attributes=False)
