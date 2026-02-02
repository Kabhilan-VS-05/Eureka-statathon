import json
import os
import numpy as np
import faiss
import re
from sentence_transformers import SentenceTransformer

# ------------------ CONFIG ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INDEX_PATH = os.path.join(BASE_DIR, "../models/nco_faiss.index")
EMBEDDINGS_PATH = os.path.join(BASE_DIR, "../models/nco_embeddings.npy")
METADATA_PATH = os.path.join(BASE_DIR, "../data/processed/nco_metadata.json")
GN_PATH = os.path.join(BASE_DIR, "../data/processed/nco_graph.json")
CSV_PATH = os.path.join(BASE_DIR, "../data/raw/data_with_descriptions.csv")

MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 5          # Top results to return
CANDIDATE_K = 20   # Top FAISS candidates to filter with GN
CONFIDENCE_THRESHOLD = 0.45
ALPHA = 0.7        # weight for semantic score
BETA = 0.3         # weight for graph score

# ------------------ LOAD DATA ------------------
print("📥 Loading metadata...")
with open(METADATA_PATH, "r", encoding="utf-8") as f:
    metadata = json.load(f)

print("📥 Loading Graph Network...")
with open(GN_PATH, "r", encoding="utf-8") as f:
    gn = json.load(f)

print("📥 Loading FAISS index...")
index = faiss.read_index(INDEX_PATH)

print("📥 Loading SBERT model...")
model = SentenceTransformer(MODEL_NAME)

print("📥 Loading detailed job descriptions from CSV...")
import csv
job_details = {}
with open(CSV_PATH, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Use NCO 2015 as the key for lookup
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
    return model.encode([query], convert_to_numpy=True, normalize_embeddings=True)

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
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
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

# ------------------ SEARCH FUNCTION ------------------
def search(query):
    query_vec = embed_query(query)
    # Step 1: FAISS search for candidate occupations
    scores, indices = index.search(query_vec, CANDIDATE_K)

    candidates = []
    for idx, semantic_score in zip(indices[0], scores[0]):
        occ_code = metadata[idx]["nco_2015"]
        gn_score = compute_graph_score(query, occ_code)
        final_score = ALPHA * float(semantic_score) + BETA * gn_score
        
        # Apply final score normalization
        final_score = min(final_score * 1.3, 1.0)
        
        details = job_details.get(occ_code, {})
        
        candidates.append({
            "occupation_title": metadata[idx]["occupation_title"],
            "nco_code": occ_code,
            "semantic_score": float(semantic_score),
            "gn_score": float(gn_score),
            "final_score": float(final_score),
            "details": details
        })

    # Step 2: Re-rank by final_score
    candidates = sorted(candidates, key=lambda x: x["final_score"], reverse=True)

    # Step 3: Filter top-K
    top_results = candidates[:TOP_K]

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
            print("⚠️ No additional details found in CSV.")
            
        print(f"\nMetadata Scores:")
        print(f"   (Semantic: {r['semantic_score']:.3f} | Graph: {r['gn_score']:.3f})")
        print("="*80 + "\n")

# ------------------ MAIN LOOP ------------------
if __name__ == "__main__":
    while True:
        query = input("Enter occupation query (or 'exit'): ").strip()
        if query.lower() == "exit":
            break
        results = search(query)
        display_results(query, results)
