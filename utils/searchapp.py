import json
import math
import os
import numpy as np
import faiss
import re
import difflib
from sentence_transformers import SentenceTransformer
import sys

# ------------------ CONFIG ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)

from database import db_store
from utils.synonym_bank import expand_query_words
from utils.oov_handler import oov_handler            # Layer 2 — OOV expansion
from utils.spell_correction import spell_corrector   # Layer 3 — conservative spell

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DEFAULT_TOP_K = 5
MAX_TOP_K = 100
CANDIDATE_K = 150
TITLE_CANDIDATE_K = 100
CONFIDENCE_THRESHOLD = 0.45
ALPHA = 0.65               # semantic (description FAISS)
BETA  = 0.15               # graph keyword coverage — lowered (keywords include structural noise)
GAMMA = 0.20               # description keyword match — raised (more targeted signal)

# Words that carry no occupational meaning — filtered before scoring
STOPWORDS = {
    "i", "me", "my", "we", "our", "you", "your", "he", "she", "it", "his", "her", "its",
    "they", "their", "this", "that", "these", "those", "am", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did", "a", "an", "the",
    "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "will", "would", "could", "should", "may", "might", "can", "as", "if", "then",
    "so", "up", "out", "about", "into", "through", "during", "some", "any", "all",
    "each", "both", "few", "more", "most", "other", "such", "no", "not", "only", "own",
    "same", "than", "too", "very", "just", "also", "still", "now", "how", "where",
    "when", "what", "who", "which", "there", "here",
    # Generic occupation/person words that appear everywhere and carry no signal
    "work", "works", "working", "worked", "person", "people", "professional",
    "worker", "workers", "staff", "employee", "employees",
}

# Patterns that introduce first-person job descriptions without adding occupational content
_FILLER_RE = re.compile(
    r"^i\s+(am\s+a[n]?\s+|am\s+|'m\s+a[n]?\s+|'m\s+|work\s+as\s+a[n]?\s+|work\s+as\s+|have\s+been\s+a[n]?\s+)",
    re.IGNORECASE,
)
_JOB_PREFIX_RE = re.compile(
    r"^(my\s+job\s+is\s+(to\s+)?|my\s+work\s+is\s+(to\s+)?|my\s+occupation\s+is\s+)",
    re.IGNORECASE,
)

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

# Pre-build description word sets for fast lookup (rebuilt on reload_from_db)
_desc_word_sets = {}

def _build_desc_word_sets():
    global _desc_word_sets
    _desc_word_sets = {}
    for code, d in job_details.items():
        # Use only occupation-specific description — family/group descriptions are shared
        # across many occupations and dilute the per-occupation keyword signal.
        occ_desc = d.get("occupation_description", "")
        title_text = next(
            (item.get("occupation_title", "") for item in metadata if item.get("nco_2015") == code),
            ""
        )
        combined = f"{title_text} {occ_desc}"
        _desc_word_sets[code] = set(clean_text(combined).split()) - STOPWORDS if combined.strip() else set()

_build_desc_word_sets()


# ── Data-driven NCO vocabulary with occupation-frequency counts ───────────────
#
# Vocabulary is built from occupation titles + hierarchy labels at startup and
# after every reload_from_db().  No hardcoded word lists or typo mappings exist.
#
# _title_vocab_set : set of all known NCO words (used for Gate-1 exact match)
# _title_vocab_list: sorted list (used by difflib pre-filter in Gate-3)
# _vocab_freq      : word → count of occupation titles containing that word
#                    (used for frequency-weighted confidence scoring)

_title_vocab_list: list = []
_title_vocab_set:  set  = set()
_vocab_freq:       dict = {}   # word -> title-level occurrence count


def _build_title_vocab() -> None:
    """
    Build the NCO vocabulary and frequency table from the loaded dataset.

    Frequency is counted at the occupation-title level (each occupation
    contributes 1 to a word's count regardless of how many times the word
    appears in that title).  Hierarchy labels (division/group/family/
    sub_division) that do not appear in any title are added with freq=1 so
    they are recognised as valid vocabulary but don't inflate scores.
    """
    global _title_vocab_list, _title_vocab_set, _vocab_freq
    freq: dict = {}

    # Count title occurrences (each occupation = one document)
    for item in metadata:
        seen_in_title: set = set()
        for w in re.findall(r"[a-z]{3,}", item.get("occupation_title", "").lower()):
            if w not in STOPWORDS:
                seen_in_title.add(w)
        for w in seen_in_title:
            freq[w] = freq.get(w, 0) + 1

    # Add hierarchy vocabulary (division/group/family/sub_division) with freq≥1
    for details in job_details.values():
        for field in ("division", "group", "family", "sub_division"):
            for w in re.findall(r"[a-z]{3,}", details.get(field, "").lower()):
                if w not in STOPWORDS and w not in freq:
                    freq[w] = 1

    _vocab_freq       = freq
    _title_vocab_set  = set(freq.keys())
    _title_vocab_list = sorted(_title_vocab_set)


_build_title_vocab()


# ── Layer 3 wiring: conservative spell correction ─────────────────────────────
# The corrector's vocabulary is the dataset (occupation titles + hierarchy) and
# the OOV/brand terms are registered as protected so they are never "corrected".
# Rebuilt on reload_from_db() via _configure_spell_corrector().

def _configure_spell_corrector() -> None:
    spell_corrector.load_vocabulary(_title_vocab_set)
    try:
        spell_corrector.add_protected(oov_handler.get_known_oov_words())
    except Exception as e:
        print(f"Failed to register OOV terms with spell corrector: {e}")


_configure_spell_corrector()


def correct_query_spelling(query: str) -> tuple:
    """
    Conservative, dataset-driven spell correction (see utils/spell_correction.py).

    Only fixes clear typos that map to a real dataset/English word within a small
    edit distance. Unknown words, valid words, and protected OOV/brand terms are
    left unchanged — an unknown word is NOT assumed to be a typo.
    """
    return spell_corrector.correct_query(query)


def _preprocess_query(query: str) -> str:
    """Strip first-person filler that adds no occupational signal."""
    q = _JOB_PREFIX_RE.sub("", query.strip())
    q = _FILLER_RE.sub("", q)
    return q.strip() or query.strip()


def embed_query(query):
    core = _preprocess_query(query)
    # Append "occupation" only for very short (1-word) queries to anchor meaning
    if len(core.split()) <= 1:
        core = core + " occupation"
    instruction = "Represent this sentence for searching relevant passages: " + core
    return model.encode([instruction], convert_to_numpy=True, normalize_embeddings=True)


def compute_graph_score(query, occupation_code):
    """
    Fraction of meaningful query words (+ their synonyms) covered by the
    occupation's keyword graph.  Synonym expansion via tier-1 curated bank
    lets "lawyer" match graphs containing "advocate" or "solicitor".
    """
    query_words = set(clean_text(_preprocess_query(query)).split()) - STOPWORDS
    if not query_words:
        return 0.0
    # Expand with data-driven synonyms — score is still anchored to original query length
    expanded = expand_query_words(query_words)
    keywords = set(gn.get(occupation_code, {}).get("keywords", []))
    if not keywords:
        return 0.0
    overlap = expanded & keywords
    # Denominator stays as original query word count to avoid inflating scores
    return min(len(overlap) / len(query_words), 1.0)


def compute_description_score(query, occupation_code):
    """
    Fraction of meaningful query words covered by the occupation's description.

    Three credit levels:
      1.0 — exact word match
      0.8 — synonym match (curated tier-1 bank)
      0.7 — prefix/stem overlap (e.g. "engineer" ↔ "engineering")
    """
    query_words = set(clean_text(_preprocess_query(query)).split()) - STOPWORDS
    if not query_words:
        return 0.0
    desc_words = _desc_word_sets.get(occupation_code, set())
    if not desc_words:
        return 0.0
    score = 0.0
    for qw in query_words:
        if qw in desc_words:
            score += 1.0
        else:
            # Synonym match (data-driven bank)
            syns = expand_query_words({qw}) - {qw}
            if syns & desc_words:
                score += 0.8
            # Prefix/stem partial credit
            elif any(
                (dw.startswith(qw) or qw.startswith(dw))
                for dw in desc_words
                if abs(len(dw) - len(qw)) <= 4 and len(qw) >= 4
            ):
                score += 0.7
    return score / len(query_words)


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

_all_jobs_cache = None


def get_all_jobs(filters=None):
    global _all_jobs_cache
    if not filters:
        if _all_jobs_cache is not None:
            return _all_jobs_cache
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
                "occupation_description": row.get("Occupation Description", ""),
                "family_description": row.get("Family Description", ""),
                "group_description": row.get("Group Description", ""),
            }
        })
    if not filters:
        _all_jobs_cache = all_jobs
    return all_jobs


def reload_from_db():
    global documents, metadata, gn, index, title_index, job_details, _all_jobs_cache, _desc_word_sets
    _all_jobs_cache = None

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

    _build_desc_word_sets()
    _build_title_vocab()
    _configure_spell_corrector()   # refresh Layer-3 vocab after dataset change

# ------------------ SEARCH FUNCTION ------------------
def search(query, top_k=DEFAULT_TOP_K, filters=None):
    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        top_k = DEFAULT_TOP_K
    top_k = max(1, min(top_k, MAX_TOP_K))

    # ── Pipeline: OOV expansion → conservative spell → (synonym at scoring) ────
    # Layer 2: expand true OOV terms (brands, vernacular, abbreviations) first.
    # OOV terms are registered as protected with the spell corrector, so the
    # following spell pass never alters them.
    try:
        query = oov_handler.process_query(query)
    except Exception as e:
        print(f"Failed OOV Expansion: {e}")

    # Layer 3: conservative spell correction. Runs before downstream scoring so
    # the corrected text feeds FAISS embedding, title matching, graph and
    # description scoring consistently. Unknown/valid/OOV words are preserved.
    corrected, was_corrected = correct_query_spelling(query)
    if was_corrected:
        query = corrected

    has_filters = filters and any(filters.values())
    clean_query = query.strip().lower()

    # Embed once — shared by FAISS retrieval and title-match scoring
    query_vec = embed_query(query)

    # --- FAISS retrieval ---
    candidate_k = max(CANDIDATE_K, top_k)
    title_candidate_k = max(TITLE_CANDIDATE_K, top_k)
    if has_filters:
        candidate_k = max(1000, top_k * 10)
        title_candidate_k = max(1000, top_k * 10)

    scores, indices = index.search(query_vec, candidate_k)
    title_scores, title_indices = title_index.search(query_vec, title_candidate_k)

    # Unified candidate pool keyed by metadata index position
    # title_match_priority: 0=exact, 1=startswith, 2=contains, 3=semantic-only
    pool = {}
    for idx, sem_score in zip(indices[0], scores[0]):
        if idx < 0:
            continue
        pool[int(idx)] = {
            "semantic_score": float(sem_score),
            "title_score": 0.0,
            "title_match_priority": 3,
        }
    for idx, ts in zip(title_indices[0], title_scores[0]):
        if idx < 0:
            continue
        entry = pool.setdefault(int(idx), {
            "semantic_score": 0.0,
            "title_score": 0.0,
            "title_match_priority": 3,
        })
        entry["title_score"] = float(ts)

    # --- Inject substring title matches; boost title_score and set priority ---
    if clean_query:
        for idx, item in enumerate(metadata):
            title_lower = item.get("occupation_title", "").lower()
            if clean_query not in title_lower:
                continue
            ratio = difflib.SequenceMatcher(None, clean_query, title_lower).ratio()
            match_bonus = 0.7 + 0.3 * ratio
            if title_lower == clean_query:
                priority = 0
            elif title_lower.startswith(clean_query):
                priority = 1
            else:
                priority = 2
            entry = pool.setdefault(idx, {
                "semantic_score": 0.0,
                "title_score": 0.0,
                "title_match_priority": 3,
            })
            entry["title_match_priority"] = min(entry["title_match_priority"], priority)
            # Keep the higher of FAISS title similarity and string-match bonus
            entry["title_score"] = max(entry["title_score"], match_bonus)

    # --- Score all candidates ---
    candidates = []
    for idx, data in pool.items():
        semantic_score = data["semantic_score"]
        title_score    = data["title_score"]
        occ_code       = metadata[idx]["nco_2015"]
        details        = job_details.get(occ_code, {})

        if has_filters:
            if not _matches_filter(filters.get("division"), details.get("division")):
                continue
            if not _matches_filter(filters.get("sub_division"), details.get("sub_division")):
                continue
            if not _matches_filter(filters.get("group"), details.get("group")):
                continue
            if not _matches_filter(filters.get("family"), details.get("family")):
                continue

        gn_score   = compute_graph_score(query, occ_code)
        desc_score = compute_description_score(query, occ_code)

        combined = (
            ALPHA * float(semantic_score) +
            BETA  * gn_score +
            GAMMA * desc_score
        )
        # Adaptive title weight: short queries (≤2 meaningful words) benefit more
        # from title similarity; longer descriptive queries should weight combined higher.
        clean_words = [w for w in clean_text(query).split() if w not in STOPWORDS]
        if len(clean_words) <= 2:
            title_w, combined_w = 0.28, 0.72
        else:
            title_w, combined_w = 0.18, 0.82
        final_score = min(combined_w * combined + title_w * float(title_score), 1.0)

        candidates.append({
            "occupation_title": metadata[idx]["occupation_title"],
            "row_id": metadata[idx].get("row_id", idx),
            "nco_code": occ_code,
            "semantic_score": float(semantic_score),
            "title_score": float(title_score),
            "gn_score": float(gn_score),
            "desc_score": float(desc_score),
            "final_score": float(final_score),
            "title_match_priority": data["title_match_priority"],
            "details": details
        })

    # Sort: exact/startswith/contains title matches first, then by final_score within each group
    candidates.sort(key=lambda x: (x["title_match_priority"], -x["final_score"]))

    # Deduplicate by NCO code and return top_k
    seen: set = set()
    final_results = []
    for item in candidates:
        if item["nco_code"] not in seen:
            final_results.append(item)
            seen.add(item["nco_code"])
        if len(final_results) >= top_k:
            break

    return final_results

def display_results(query, top_results):
    if not top_results or top_results[0]["final_score"] < CONFIDENCE_THRESHOLD:
        print("⚠️ Low confidence: please clarify your occupation description.\n")

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
        print(f"   (Semantic: {r['semantic_score']:.3f} | Graph: {r['gn_score']:.3f} | Desc: {r.get('desc_score', 0):.3f})")
        print("="*80 + "\n")




# ------------------ MAIN LOOP ------------------
if __name__ == "__main__":
    while True:
        query = input("Enter occupation query (or 'exit'): ").strip()
        if query.lower() == "exit":
            break
        results = search(query)
        display_results(query, results)
