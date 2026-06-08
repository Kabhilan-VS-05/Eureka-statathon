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
def get_all_jobs():
    all_jobs = []
    _, rows = db_store.load_csv_rows()
    for row in rows:
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
def search(query, top_k=DEFAULT_TOP_K):
    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        top_k = DEFAULT_TOP_K
    top_k = max(1, min(top_k, MAX_TOP_K))
    candidate_k = max(CANDIDATE_K, top_k)
    title_candidate_k = max(TITLE_CANDIDATE_K, top_k)

    query_vec = embed_query(query)
    # Step 1: Search both full occupation documents and occupation titles.
    # Short user queries often match titles better, while longer prompts benefit
    # from the full document index.
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
        gn_score = compute_graph_score(query, occ_code)
        details = job_details.get(occ_code, {})
        base_score = ALPHA * float(semantic_score) + BETA * gn_score

        # Use true raw scores without artificial inflation
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

    # Step 2: Re-rank by final_score
    candidates = sorted(candidates, key=lambda x: x["final_score"], reverse=True)

    # Step 3: Filter top-K
    top_results = candidates[:top_k]

    return top_results

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

# P.I.G.S. - Prompt Intelligence Guidance System

# ------------------ PIGS HELPER FUNCTIONS ------------------

def compute_level_similarity(query, descriptions):
    """
    Computes average semantic similarity between query and a list of descriptions
    """
    if not descriptions:
        return 0.0
    
    query_with_instruction = "Represent this sentence for searching relevant passages: " + query
    query_vec = model.encode([query_with_instruction], normalize_embeddings=True)
    desc_vecs = model.encode(descriptions, normalize_embeddings=True)
    
    sims = np.dot(desc_vecs, query_vec.T)
    return float(np.mean(sims))


def extract_hierarchy_descriptions(top_results):
    levels = {
        "division": set(),
        "sub_division": set(),
        "group": set(),
        "family": set()
    }
    
    for r in top_results:
        d = r["details"]
        if not d:
            continue
        
        if d.get("division"):
            levels["division"].add(d["division"])
        if d.get("sub_division"):
            levels["sub_division"].add(d["sub_division"])
        if d.get("group"):
            levels["group"].add(d["group"])
        if d.get("family"):
            levels["family"].add(d["family"])
    
    return {k: list(v) for k, v in levels.items()}

def clean_display_name(value):
    text = str(value or "").strip()
    text = re.sub(r",?\s*others?$", "", text, flags=re.IGNORECASE).strip()
    return text or str(value or "").strip()

def pigs_analyze_prompt(query, top_results):
    hierarchy_descs = extract_hierarchy_descriptions(top_results)
    
    level_scores = {}
    suggestions = []
    
    for level, descriptions in hierarchy_descs.items():
        score = compute_level_similarity(query, descriptions)
        level_scores[level] = score

    if top_results:
        top = top_results[0]
        details = top.get("details", {}) or {}
        title = clean_display_name(top.get("occupation_title"))
        family = clean_display_name(details.get("family"))
        group = clean_display_name(details.get("group"))
        division = clean_display_name(details.get("division"))

        if title:
            suggestions.append(
                f"The closest match is {title}. If this is correct, search with that job name or describe its main work."
            )
        if family and family.lower() != title.lower():
            suggestions.append(
                f"You can add the job family: {family}."
            )
        if group:
            suggestions.append(
                f"You can add the work area: {group}."
            )
        if division:
            suggestions.append(
                f"You can add the broad field: {division}."
            )
    
    return level_scores, suggestions

# ------------------ MAIN LOOP ------------------
if __name__ == "__main__":
    while True:
        query = input("Enter occupation query (or 'exit'): ").strip()
        if query.lower() == "exit":
            break
        results = search(query)
        display_results(query, results)
