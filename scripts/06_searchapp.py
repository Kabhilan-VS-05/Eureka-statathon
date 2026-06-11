import json
import os
import numpy as np
import faiss
import re
from sentence_transformers import SentenceTransformer
import sys

# ------------------ CONFIG ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

import db_store

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DEFAULT_TOP_K = 5
MAX_TOP_K = 100
CANDIDATE_K = 50   # Top FAISS candidates to filter with GN
TITLE_CANDIDATE_K = 50
CONFIDENCE_THRESHOLD = 0.45
ALPHA = 0.7        # weight for semantic score
BETA = 0.3         # weight for graph score

# ------------------ LOAD DATA ------------------
print("Loading metadata from PostgreSQL...")
documents, metadata = db_store.load_search_documents()
if not metadata:
    raise RuntimeError("No search metadata found in PostgreSQL. Run scripts/migrate_to_postgres.py first.")

print("Loading Graph Network from PostgreSQL...")
gn = db_store.load_graph()

print("Loading FAISS index from PostgreSQL...")
index_bytes = db_store.load_asset("nco_faiss.index")
if not index_bytes:
    raise RuntimeError("No FAISS index found in PostgreSQL. Run scripts/migrate_to_postgres.py first.")
index = faiss.deserialize_index(np.frombuffer(index_bytes, dtype="uint8"))

print("Loading SBERT model...")
model = SentenceTransformer(MODEL_NAME)

print("Building title search index...")
title_documents = [item.get("occupation_title", "") for item in metadata]
title_embeddings = model.encode(
    title_documents,
    show_progress_bar=False,
    convert_to_numpy=True,
    normalize_embeddings=True,
)
title_index = faiss.IndexFlatIP(title_embeddings.shape[1])
title_index.add(title_embeddings)

print("Loading detailed job descriptions from PostgreSQL...")
job_details = {}
_, occupation_rows = db_store.load_csv_rows()
for row in occupation_rows:
    nco_code = row["NCO 2015"]
    job_details[nco_code] = {
        "nco_2004_code": row["NCO 2004"],
        "division": row["Division"],
        "sub_division": row["Sub Division"],
        "group": row["Group"],
        "family": row["Family"],
        "occupation_description": row["Occupation Description"],
        "family_description": row["Family Description"],
        "group_description": row["Group Description"]
    }

# ------------------ HELPER FUNCTIONS ------------------
def clean_text(text):
    return re.sub(r"[^a-z0-9\s]", "", text.lower())

def embed_query(query):
    # Enhance broad queries (e.g. "Agriculture") by adding context so they map to occupations
    enhanced_query = query
    if not any(w in query.lower() for w in ["job", "occupation", "worker", "professional"]):
        enhanced_query += " occupation"
        
    query_with_instruction = "Represent this sentence for searching relevant passages: " + enhanced_query
    return model.encode([query_with_instruction], convert_to_numpy=True, normalize_embeddings=True)

def compute_graph_score(query, occupation_code):
    query_words = set(clean_text(query).split())
    keywords = set(gn.get(occupation_code, {}).get("keywords", []))
    if not keywords:
        return 0.0
    overlap = query_words & keywords
    return len(overlap) / len(keywords)

# ------------------ HELPER FUNCTIONS ------------------
def _matches_filter(filter_val, row_val):
    if not filter_val:
        return True
    if isinstance(filter_val, (list, tuple, set)):
        normalized_filter = {str(v).strip().lower() for v in filter_val if v}
        if not normalized_filter:
            return True
        return str(row_val).strip().lower() in normalized_filter
    return str(filter_val).strip().lower() == str(row_val).strip().lower()

def get_all_jobs(filters=None):
    all_jobs = []
    _, rows = db_store.load_csv_rows()
    for row in rows:
        if filters:
            if not _matches_filter(filters.get("division"), row.get("Division")):
                continue
            if not _matches_filter(filters.get("sub_division"), row.get("Sub Division")):
                continue
            if not _matches_filter(filters.get("group"), row.get("Group")):
                continue
            if not _matches_filter(filters.get("family"), row.get("Family")):
                continue

        all_jobs.append({
            "occupation_title": row["Occupational Title"],
            "nco_code": row["NCO 2015"],
            "details": {
                "nco_2004_code": row["NCO 2004"],
                "division": row["Division"],
                "sub_division": row["Sub Division"],
                "group": row["Group"],
                "family": row["Family"],
            }
        })
    return all_jobs


def reload_from_db():
    global documents, metadata, gn, index, title_index, job_details

    print("Reloading search runtime from PostgreSQL...")
    documents, metadata = db_store.load_search_documents()
    gn = db_store.load_graph()

    index_bytes = db_store.load_asset("nco_faiss.index")
    if not index_bytes:
        raise RuntimeError("No FAISS index found in PostgreSQL.")
    index = faiss.deserialize_index(np.frombuffer(index_bytes, dtype="uint8"))

    title_documents = [item.get("occupation_title", "") for item in metadata]
    title_embeddings = model.encode(
        title_documents,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    title_index = faiss.IndexFlatIP(title_embeddings.shape[1])
    title_index.add(title_embeddings)

    job_details = {}
    _, rows = db_store.load_csv_rows()
    for row in rows:
        nco_code = row["NCO 2015"]
        job_details[nco_code] = {
            "nco_2004_code": row["NCO 2004"],
            "division": row["Division"],
            "sub_division": row["Sub Division"],
            "group": row["Group"],
            "family": row["Family"],
            "occupation_description": row["Occupation Description"],
            "family_description": row["Family Description"],
            "group_description": row["Group Description"]
        }

# ------------------ SEARCH FUNCTION ------------------
def search(query, top_k=DEFAULT_TOP_K, filters=None):
    import difflib
    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        top_k = DEFAULT_TOP_K
    top_k = max(1, min(top_k, MAX_TOP_K))
    
    has_filters = filters and any(filters.values())
    clean_query = query.strip().lower()
    
    # Step 1: Substring title matches
    title_results = []
    if clean_query:
        for idx, item in enumerate(metadata):
            title = item.get("occupation_title", "")
            if clean_query in title.lower():
                occ_code = item["nco_2015"]
                details = job_details.get(occ_code, {})
                
                if has_filters:
                    if not _matches_filter(filters.get("division"), details.get("division")):
                        continue
                    if not _matches_filter(filters.get("sub_division"), details.get("sub_division")):
                        continue
                    if not _matches_filter(filters.get("group"), details.get("group")):
                        continue
                    if not _matches_filter(filters.get("family"), details.get("family")):
                        continue
                
                gn_score = compute_graph_score(query, occ_code)
                ratio = difflib.SequenceMatcher(None, clean_query, title.lower()).ratio()
                match_ratio = 0.7 + 0.3 * ratio
                
                title_results.append({
                    "occupation_title": title,
                    "row_id": item.get("row_id", idx),
                    "nco_code": occ_code,
                    "semantic_score": float(match_ratio),
                    "title_score": float(match_ratio),
                    "gn_score": float(gn_score),
                    "final_score": float(match_ratio),
                    "details": details
                })
        
        # Sort title results: exact matches first, then starts with, then substring
        def _rank_title_match(x):
            t_lower = x["occupation_title"].lower()
            if t_lower == clean_query:
                return 0
            elif t_lower.startswith(clean_query):
                return 1
            return 2
            
        title_results = sorted(title_results, key=_rank_title_match)

    if len(title_results) >= top_k:
        return title_results[:top_k]

    # Step 2: Semantic search to fill the rest
    candidate_k = max(CANDIDATE_K, top_k)
    title_candidate_k = max(TITLE_CANDIDATE_K, top_k)
    
    if has_filters:
        candidate_k = max(1000, top_k * 10)
        title_candidate_k = max(1000, top_k * 10)

    query_vec = embed_query(query)
    scores, indices = index.search(query_vec, candidate_k)
    title_scores, title_indices = title_index.search(query_vec, title_candidate_k)

    candidate_scores = {}
    for idx, semantic_score in zip(indices[0], scores[0]):
        if idx < 0:
            continue
        candidate_scores[int(idx)] = {
            "semantic_score": float(semantic_score),
            "title_score": 0.0,
        }

    for idx, title_score in zip(title_indices[0], title_scores[0]):
        if idx < 0:
            continue
        candidate_scores.setdefault(int(idx), {
            "semantic_score": 0.0,
            "title_score": 0.0,
        })
        candidate_scores[int(idx)]["title_score"] = float(title_score)

    candidates = []
    for idx, score_data in candidate_scores.items():
        semantic_score = score_data["semantic_score"]
        title_score = score_data["title_score"]
        occ_code = metadata[idx]["nco_2015"]
        details = job_details.get(occ_code, {})
        
        if has_filters:
            if not _matches_filter(filters.get("division"), details.get("division")):
                continue
            if not _matches_filter(filters.get("sub_division"), details.get("sub_division")):
                continue
            if not _matches_filter(filters.get("group"), details.get("group")):
                continue
            if not _matches_filter(filters.get("family"), details.get("family")):
                continue
                
        gn_score = compute_graph_score(query, occ_code)
        base_score = ALPHA * float(semantic_score) + BETA * gn_score
        semantic_final = base_score
        title_final = float(title_score)
        final_score = min(max(semantic_final, title_final), 1.0)
        
        candidates.append({
            "occupation_title": metadata[idx]["occupation_title"],
            "row_id": metadata[idx].get("row_id", idx),
            "nco_code": occ_code,
            "semantic_score": float(semantic_score),
            "title_score": float(title_score),
            "gn_score": float(gn_score),
            "final_score": float(final_score),
            "details": details
        })

    # Re-rank semantic candidates
    candidates = sorted(candidates, key=lambda x: x["final_score"], reverse=True)

    # Merge & Remove duplicates (by nco_code)
    seen = {item["nco_code"] for item in title_results}
    final_results = list(title_results)

    for item in candidates:
        if item["nco_code"] not in seen:
            final_results.append(item)
            seen.add(item["nco_code"])
        if len(final_results) >= top_k:
            break

    return final_results

def display_results(query, top_results):
    # Step 4: Confidence check
    if not top_results or top_results[0]["final_score"] < CONFIDENCE_THRESHOLD:
        print("⚠️ Low confidence: please clarify your occupation description.\n")
    
    # Step 5: Display results
    print(f"\n" + "="*80)
    print(f"🔎 Query: {query}")
    print("="*80 + "\n")
    
    for rank, r in enumerate(top_results, start=1):
        details = r['details']
        
        print(f"RANK {rank} | SCORE: {r['final_score']:.3f}")
        print(f"Title: {r['occupation_title']}")
        print(f"NCO Code: {r['nco_code']}")
        print("-" * 40)
        
        if details:
            print(f"Hierarchy:")
            print(f"  - Division: {details['division']}")
            print(f"  - Sub-Division: {details['sub_division']}")
            print(f"  - Group: {details['group']}")
            print(f"  - Family: {details['family']}")
            print("\nOccupation Description:")
            print(f"  {details['occupation_description']}")
            print("\nFamily Description:")
            print(f"  {details['family_description']}")
            print("\nGroup Description:")
            print(f"  {details['group_description']}")
        else:
            print("No additional details found in CSV.")
            
        print(f"\nMetadata Scores:")
        print(f"   (Semantic: {r['semantic_score']:.3f} | Graph: {r['gn_score']:.3f})")
        print("="*80 + "\n")
    
    # ------------------ PIGS OUTPUT ------------------
    level_scores, suggestions = pigs_analyze_prompt(query, top_results)

    print("\nPrompt Intelligence & Guidance System (PIGS)")
    print("-" * 60)
    for level, score in level_scores.items():
        print(f"{level.replace('_', ' ').title()} Match Score: {score:.3f}")

    if suggestions:
        print("\nPrompt Refinement Suggestions:")
        for s in suggestions:
            print(f" - {s}")
    else:
        print("\nYour prompt is sufficiently specific across hierarchy levels.")


# ------------------ MAIN LOOP ------------------
if __name__ == "__main__":
    while True:
        query = input("Enter occupation query (or 'exit'): ").strip()
        if query.lower() == "exit":
            break
        results = search(query)
        display_results(query, results)



