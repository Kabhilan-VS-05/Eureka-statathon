import json
import numpy as np
import faiss
import re
from sentence_transformers import SentenceTransformer

# ------------------ CONFIG ------------------
INDEX_PATH = "../models/nco_faiss.index"
EMBEDDINGS_PATH = "../models/nco_embeddings.npy"
METADATA_PATH = "../data/processed/nco_metadata.json"
GN_PATH = "../data/processed/nco_graph.json"

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

# ------------------ SEARCH FUNCTION ------------------
def search(query):
    query_vec = embed_query(query)
    # Step 1: FAISS search for candidate occupations
    scores, indices = index.search(query_vec, CANDIDATE_K)

    candidates = []
    for idx, semantic_score in zip(indices[0], scores[0]):
        occ_code = metadata[idx]["nco_2015"]
        gn_score = compute_graph_score(query, occ_code)
        final_score = ALPHA * semantic_score + BETA * gn_score
        candidates.append({
            "occupation_title": metadata[idx]["occupation_title"],
            "nco_code": occ_code,
            "semantic_score": semantic_score,
            "gn_score": gn_score,
            "final_score": final_score
        })

    # Step 2: Re-rank by final_score
    candidates = sorted(candidates, key=lambda x: x["final_score"], reverse=True)

    # Step 3: Filter top-K
    top_results = candidates[:TOP_K]

    # Step 4: Confidence check
    if top_results[0]["final_score"] < CONFIDENCE_THRESHOLD:
        print("⚠️ Low confidence: please clarify your occupation description.\n")
    
    # Step 5: Display results
    print(f"\n🔎 Query: {query}\n")
    for rank, r in enumerate(top_results, start=1):
        print(f"{rank}. {r['occupation_title']} ({r['nco_code']})")
        print(f"   Semantic Score: {r['semantic_score']:.3f}")
        print(f"   Graph Score: {r['gn_score']:.3f}")
        print(f"   Final Score: {r['final_score']:.3f}\n")

# ------------------ MAIN LOOP ------------------
if __name__ == "__main__":
    while True:
        query = input("Enter occupation query (or 'exit'): ").strip()
        if query.lower() == "exit":
            break
        search(query)
