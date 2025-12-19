import faiss
import numpy as np
import pandas as pd
import random
from sentence_transformers import SentenceTransformer
from rapidfuzz import process
from googletrans import Translator
import re

# -----------------------------
# Initialize models and data (Global Scope)
# -----------------------------

print("Initializing models and data... This may take a moment.")

# Load Data
try:
    df = pd.read_csv("data_with_descriptions.csv")
except FileNotFoundError:
    print("Error: 'data_with_descriptions.csv' not found. Please ensure the file is in the same directory.")
    exit()

# Load Sentence Transformer
model = SentenceTransformer("all-MiniLM-L6-v2")

# Translation
translator = Translator()

# Synonym Bank
synonyms = {
    "manage": ["oversee", "supervise", "direct", "administer", "coordinate"],
    "support": ["assist", "help", "aid", "contribute to", "facilitate"],
    "analyze": ["evaluate", "examine", "study", "assess", "interpret"],
    "develop": ["design", "create", "formulate", "build", "establish"],
    "improve": ["enhance", "optimize", "refine", "advance", "upgrade"],
}

# -----------------------------
# Helper Functions
# -----------------------------

def translate_to_english(text):
    try:
        if not isinstance(text, str) or not text.strip():
            return ""
        result = translator.translate(text, dest='en')
        return result.text
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def apply_synonyms(text: str) -> str:
    for word, choices in synonyms.items():
        if re.search(r'\b' + word + r'\b', text.lower()):
            replacement = random.choice(choices)
            text = re.sub(r'\b' + word + r'\b', replacement, text, flags=re.IGNORECASE)
    return text

def clean_and_validate(descriptions, job_info):
    unique_desc = list(dict.fromkeys([d.strip() for d in descriptions if d.strip()]))
    valid_desc = [d for d in unique_desc if len(d.split()) >= 5]
    if not valid_desc:
        fallback = f"This role in {job_info['Group']} supports {job_info['Division']} by ensuring smooth operations."
        return [fallback]
    return valid_desc

# -----------------------------
# Create Embeddings, Vocabulary, and FAISS Index
# -----------------------------

job_records = []
embeddings = []
vocabulary = set()

print("Processing data and building vocabulary...")

for idx, row in df.iterrows():
    job_info = {k: row.get(k, "N/A") for k in ["S No", "Occupational Title", "NCO 2015", "NCO 2004", "Division", "Sub Division", "Group", "Family"]}
    job_records.append(job_info)

    descriptions_raw = str(row.get("descriptions", "")).split("|")
    descriptions_synonyms = [apply_synonyms(desc.strip()) for desc in descriptions_raw if desc.strip()]
    descriptions_clean = clean_and_validate(descriptions_synonyms, job_info)
    
    desc_embeddings = model.encode(descriptions_clean)
    emb = np.mean(desc_embeddings, axis=0) if desc_embeddings.any() else np.zeros(model.get_sentence_embedding_dimension())
    embeddings.append(emb)

    for field in ["Occupational Title", "Division", "Sub Division", "Group", "Family"]:
        if isinstance(row.get(field), str):
            clean_words = re.findall(r'\b\w+\b', row.get(field).lower())
            vocabulary.update(clean_words)

embeddings = np.array(embeddings, dtype="float32")
faiss.normalize_L2(embeddings)
dimension = embeddings.shape[1]
index = faiss.IndexFlatIP(dimension)
index.add(embeddings)

print(f"FAISS index created with {index.ntotal} vectors.")
print(f"Clean vocabulary created with {len(vocabulary)} unique words.")

# -----------------------------
# Spell Correction Function
# -----------------------------

def correct_spelling(query: str, threshold=80) -> str: # Lowered threshold
    corrected_tokens = []
    for token in query.split():
        best_match = process.extractOne(token.lower(), vocabulary)
        if best_match and best_match[1] >= threshold:
            corrected_tokens.append(best_match[0])
        else:
            corrected_tokens.append(token)
    return " ".join(corrected_tokens)

# -----------------------------
# Search Function
# -----------------------------
def search_jobs(query, top_k=5, score_threshold=0.45):
    """
    Search jobs with spell correction and synonym fallbacks.
    Returns a dictionary with results and correction info for the UI.
    """
    results_list = []
    
    def run_search(q):
        if not q.strip(): return np.array([[]]), np.array([[]])
        q_vec = model.encode([q]).astype("float32")
        faiss.normalize_L2(q_vec)
        return index.search(q_vec, top_k)

    translated_query = translate_to_english(query)
    corrected_query = correct_spelling(translated_query)
    
    final_query_to_use = corrected_query
    
    scores, indices = run_search(final_query_to_use)

    # Fallback: Apply synonyms if score is low
    if not indices.size or scores[0][0] < score_threshold:
        synonym_query = apply_synonyms(final_query_to_use)
        if synonym_query != final_query_to_use:
            final_query_to_use = synonym_query
            scores, indices = run_search(final_query_to_use)
            
    # Format results
    if indices.size > 0:
        for idx, score in zip(indices[0], scores[0]):
            if score >= score_threshold:
                job = job_records[idx]
                job_with_score = {**job, 'similarity': f"{score:.4f}"}
                results_list.append(job_with_score)
    
    # Return a dictionary for the frontend to handle
    return {
        'results': results_list,
        'corrected_query': final_query_to_use if translated_query.lower() != final_query_to_use.lower() else None
    }