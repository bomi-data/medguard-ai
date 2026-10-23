import json, sys
from pathlib import Path
import numpy as np, pyarrow.parquet as pq
R = Path(sys.argv[1]); P = R/"data/processed"
META = ["chunk_id","document_id","article_id","text_hash","ITEM_SEQ","ITEM_NAME","ENTP_NAME","doc_type","source_field","source_doc_id","section_title","article_title","article_category","cat_elderly","cat_interaction","cat_contraindication","chunk_order","n_chunks_in_article","char_len","is_active","CANCEL_NAME","prov_source","prov_endpoint","detail_prov_retrieved_at","CHANGE_DATE"]
REQ = {
 "screening/contraindication_pairs.parquet": ["canonical_pair_id","drug_1_item_seq","drug_2_item_seq"],
 "screening/contraindication_evidence.parquet": ["canonical_pair_id","item_seq","item_name","mixture_item_seq","mixture_item_name","ingredient_name_kor","mixture_ingredient_name_kor","prohbt_content","evidence_id","dur_seq"],
 "screening/elderly_caution_rules.parquet": ["item_seq","item_name","prohbt_content","ingr_code","ingredient_name_kor"],
 "screening/therapeutic_group_mapping.parquet": ["item_seq","item_name","effect_name","ingr_code","ingredient_name_kor","sers_name","dur_seq","prohbt_content"],
 "evidence/easy_drug_canonical.parquet": ["item_seq","item_name"],
 "rag/approval_chunks.parquet": META + ["chunk_text"],
 "retrieval/unique_text_index.parquet": ["text_idx","text_hash"],
 "retrieval/text_hash_mapping.parquet": ["chunk_id","text_idx"],
 "evidence/drug_approval_items.parquet": [],
}
ok = True
for rel, cols in REQ.items():
    f = pq.ParquetFile(P/rel); names = f.schema_arrow.names
    miss = [c for c in cols if c not in names]
    ok &= not miss
    print(f"{'OK ' if not miss else 'MISSING'} rows={f.metadata.num_rows:>9,} cols={len(names):>3} row_groups={f.num_row_groups:>3} {rel}" + (f" missing={miss}" if miss else ""))
# small screening tables: actually read (full decode) to prove readability; compare with notebook EDA constants
el = pq.read_table(P/"screening/elderly_caution_rules.parquet"); th = pq.read_table(P/"screening/therapeutic_group_mapping.parquet")
print("elderly raw rows", el.num_rows, "(nb02 EXPECTED_ELDERLY_RAW_ROWS=1982)", el.num_rows == 1982)
print("therapeutic raw rows", th.num_rows, "(nb02 EXPECTED_THERAPEUTIC_RAW_ROWS=7064)", th.num_rows == 7064)
pr = pq.read_table(P/"screening/contraindication_pairs.parquet", columns=["canonical_pair_id"])
print("contraindication pairs", pr.num_rows, "unique", len(set(pr.column(0).to_pylist())))
# column-subset reads on big files (batch, no full materialization)
n = 0
for b in pq.ParquetFile(P/"rag/approval_chunks.parquet").iter_batches(batch_size=50_000, columns=["text_hash"]): n += b.num_rows
print("approval_chunks iter_batches(text_hash) rows", n)
# embeddings: mmap only
e = np.load(P/"retrieval/dense/BAAI__bge-m3/unique_text_embeddings.npy", mmap_mode="r")
meta = json.loads((P/"retrieval/dense/BAAI__bge-m3/embedding_meta.json").read_text(encoding="utf-8"))
ut = pq.ParquetFile(P/"retrieval/unique_text_index.parquet").metadata.num_rows
print("embeddings shape", e.shape, e.dtype, "meta n_texts", meta.get("n_texts"), "unique_text_index rows", ut, "consistent", e.shape[0] == meta.get("n_texts") == ut)
for j in ["generation/generation_config.json","retrieval/retrieval_config.json"]:
    d = json.loads((P/j).read_text(encoding="utf-8")); print("json OK", j, "keys", len(d))
print("ALL_REQUIRED_COLUMNS_PRESENT", ok)
