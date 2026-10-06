"""
generate_synonym_bank.py
━━━━━━━━━━━━━━━━━━━━━━━━
Data-driven synonym bank generation from the NCO 2015 dataset (Layer 1).

This is the PRIMARY source of occupational understanding. It learns synonym
relationships purely from the dataset structure — no manual synonym lists.

Algorithm
─────────
1.  Read all 3,447 occupations from the CSV.
2.  Group occupations by Family (≈370 families = semantic clusters).
3.  For each occupation extract meaningful words from FIELD-WEIGHTED text:
      • Occupational Title      → weight 5  (strongest job-title signal)
      • Family   (name)         → weight 3
      • Group    (name)         → weight 3
      • Occupation Description  → weight 1
    Family Description and Group Description are intentionally EXCLUDED — they
    are boilerplate template sentences shared across thousands of occupations
    and carry no per-occupation synonym signal.
4.  Within each family cluster, words co-occur as candidate synonyms.
5.  Synonyms are ranked by a weighted TF-IDF score:
      term_score = weighted_within_cluster_freq × log(total_families / families_with_word)
    Title/hierarchy tokens dominate, so the bank yields clean job-title
    synonyms (teacher↔lecturer↔instructor) rather than description soup.
6.  Frequency filter: discard any word appearing in fewer than
    MIN_WORD_FREQUENCY occupations globally.
7.  Save synonym_bank.json (meta + "expand") and synonym_bank_summary.txt.

The OOV layer lives in a SEPARATE file (data/processed/oov_dictionary.json,
built by scripts/generate_oov_dictionary.py) and is never written here.

Run:
    python scripts/generate_synonym_bank.py
"""

import csv
import json
import math
import os
import re
import sys
import collections
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()  # load DATABASE_URL from .env before db_store reads it

# ── Paths ────────────────────────────────────────────────────────────────────────
_SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR  = os.path.dirname(_SCRIPT_DIR)          # one level up from scripts/
if PROJECT_DIR not in sys.path:
    sys.path.append(PROJECT_DIR)
CSV_PATH     = os.path.join(PROJECT_DIR, "data", "raw",       "nco_dataset_v6_final.csv")
OUT_CSV      = os.path.join(PROJECT_DIR, "data", "processed", "synonym_bank.csv")
OUT_SUMMARY  = os.path.join(PROJECT_DIR, "data", "processed", "synonym_bank_summary.txt")

# ── Tuning ───────────────────────────────────────────────────────────────────────
MIN_WORD_LENGTH    = 3     # ignore tokens shorter than this
MIN_WORD_FREQUENCY = 2     # word must appear in ≥ N occupations globally
MAX_SYNONYMS       = 15    # cap synonym list length per word
MIN_CLUSTER_SALIENCE = 3   # a candidate synonym must reach this weighted freq in
                           # the shared family (i.e. appear in a Title/Family/Group
                           # mention, not description-only) — trims weak cross-links

# Field weights — Title and hierarchy names dominate the co-occurrence signal.
# Family Description / Group Description are excluded (boilerplate, no signal).
FIELD_WEIGHTS = {
    "Occupational Title":     5,
    "Family":                 3,
    "Group":                  3,
    "Occupation Description":  1,
}

# ── Stopwords ────────────────────────────────────────────────────────────────────
# Standard English stopwords + NCO-domain noise terms specified in requirements
STOPWORDS: set = {
    # ── Standard English ─────────────────────────────────────────────────────────
    "i","me","my","we","our","you","your","he","she","it","his","her","its",
    "they","their","this","that","these","those","am","is","are","was","were",
    "be","been","being","have","has","had","do","does","did","will","would",
    "could","should","may","might","can","shall","must","need","dare","used",
    "a","an","the","and","or","but","if","in","on","at","to","for","of","with",
    "by","from","into","through","during","before","after","above","below",
    "between","out","up","down","off","over","under","again","further","then",
    "once","here","there","when","where","why","how","all","both","each","few",
    "more","most","some","such","no","not","only","own","same","than","too",
    "very","just","also","still","now","so","as","about","than","while","which",
    "who","whom","whose","what","whether","either","neither","any","every",
    "many","much","little","less","least","well","back","long","way","even",
    "new","old","high","low","large","small","big","great","good","right",
    # ── User-specified domain noise ───────────────────────────────────────────────
    "worker","workers","person","persons","people","occupation","occupations",
    "professional","professionals","employee","employees","staff","assistant",
    "assistants","other","others","general","related","associate","associates",
    # ── Additional generic occupation words that add no signal ───────────────────
    "job","jobs","work","works","working","worked","duty","duties",
    "role","roles","task","tasks","function","functions","activity","activities",
    "service","services","job","position","positions","post","posts",
    "field","area","sector","type","types","kind","kinds","form","forms",
    "level","grade","class","category","categories","unit","units","group",
    # ── Action verbs appearing in descriptions (not NCO-specific) ────────────────
    "responsible","responsibilities","performing","perform","performed","performs",
    "involved","involving","involves","concerned","concerning","required","requires",
    "needed","needs","making","made","makes","carrying","carried","carries",
    "undertaking","undertaken","undertakes","providing","provided","provides",
    "ensuring","ensured","ensures","maintaining","maintained","maintains",
    "operating","operated","operates","handling","handled","handles",
    "preparing","prepared","prepares","checking","checked","checks",
    "managing","managed","manages","coordinating","coordinated","coordinates",
    "planning","planned","plans","developing","developed","develops",
    "implementing","implemented","implements","conducting","conducted","conducts",
    "assisting","assisted","assists","supporting","supported","supports",
    "carrying","carried","undertaking","undertaken","includes","included",
    "involve","include","such","may","also","well","using","uses","use",
    # ── Generic qualifiers ───────────────────────────────────────────────────────
    "senior","junior","principal","chief","head","lead","leading","advanced",
    "basic","standard","specialist","first","second","third","fourth",
    "one","two","three","four","five","six","seven","eight","nine","ten",
    "special","specific","particular","various","different","similar",
    "major","minor","main","secondary","primary","additional","extra",
    "non","pre","post","sub","inter","intra","cross","multi","bi","semi",
    # ── NCO classification noise ──────────────────────────────────────────────────
    "nec","not","elsewhere","classified","including","excluding","except",
    "abled","able","via","per","among","amongst","within","without",
    "throughout","across","between","toward","towards","upon","onto","into",
    "alongside","regarding","concerning","following","related","according",
    # ── Boilerplate template words from Family Description and Group Description ───
    # Every Family Description starts: "This family includes closely related job
    # roles centered around X, with shared responsibilities, tools, and work
    # objectives."  Every Group Description starts: "This group consists of
    # occupations that perform ... They share common skill sets such as strategic
    # thinking, communication, and problem-solving to contribute to the overall
    # success of their organizations."  These template words appear in thousands of
    # occupations and carry zero occupational-domain signal.
    "family","families","encompasses","encompass","encompassing",
    "objectives","objective","centered","centred","around","closely",
    "shared","consists","consist","consisting","sets","contribute","contributes",
    "contributing","contribution","contributions","overall","success","strategic",
    "thinking","communication","communications","solving","solve","solutions",
    "solution","problem","problems","organizations","organisation","organizations",
    "skills","skill","abilities","ability","settings","setting",
    "tools","tool","emphasizing","emphasize","emphasizes","domain","domains",
    "aspects","aspect","broad","broader","broadly","diverse","diversity",
    "complex","complexity","outcomes","outcome","achieving","achieve","achieves",
    "impact","impacts","impacting","critical","critically","essential","essentially",
    "effective","effectively","effectiveness","efficient","efficiency","efficiently",
    "appropriate","appropriately","optimal","optimally","ensure","ensuring","ensures",
    "quality","qualities","standard","standards","practices","practice","practicing",
    "knowledge","expertise","experience","experienced","proficiency","proficient",
    "advanced","ability","capable","capability","capacities","capacity",
    "team","teams","teamwork","collaboration","collaborative","cooperate",
    "stakeholders","stakeholder","clients","client","customers","customer",
    "management","coordination","supervision","oversight","leadership",
    "decision","decisions","making","policies","policy","procedures","procedure",
    "operations","operational","operationally","perform","performs","performed",
    "technical","technically","technical","administrative","administration",
    "analysis","analytical","analytically","approach","approaches","applied",
    "developing","development","develops","implementing","implementation",
    "maintaining","maintenance","supporting","support","supported",
    "planning","plan","plans","planner","organized","organizational",
    "identifying","identify","identification","assessing","assess","assessment",
    "reporting","reports","report","documented","documentation","document",
    "monitoring","monitor","monitors","reviewing","review","reviews","reviewed",
    "evaluating","evaluate","evaluation","coordinating","coordination",
    "communicating","communicate","liaise","liaison","liaising",
    "improving","improvement","improve","enhancing","enhance","enhancement",
}


# ─────────────────────────────────────────────────────────────────────────────────
# STEP 1 — Load and group the dataset
# ─────────────────────────────────────────────────────────────────────────────────

def load_dataset(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append({k.strip(): (v or "").strip() for k, v in row.items()})
    return rows


def tokenize(text: str) -> list[str]:
    """Lower-case alphabetic tokens, min-length filtered, stopword removed."""
    return [
        w for w in re.findall(r"[a-z]+", text.lower())
        if len(w) >= MIN_WORD_LENGTH and w not in STOPWORDS
    ]


def extract_weighted_tokens(row: dict) -> collections.Counter:
    """
    Return a Counter of word → weighted frequency for one occupation row.

    Each field contributes its tokens scaled by FIELD_WEIGHTS. Title and
    hierarchy-name tokens are amplified; description tokens count once.
    """
    weighted: collections.Counter = collections.Counter()
    for field, weight in FIELD_WEIGHTS.items():
        for w in tokenize(row.get(field, "")):
            weighted[w] += weight
    return weighted


# ─────────────────────────────────────────────────────────────────────────────────
# STEP 2 — Build family clusters and compute frequencies
# ─────────────────────────────────────────────────────────────────────────────────

def build_clusters(rows: list[dict]):
    """
    Returns
    ───────
    family_word_freq : dict[family_name, Counter[word]]
        For each family, the WEIGHTED frequency of each word (TF for ranking).
    word_global_freq : Counter[word]
        How many individual occupations contain each word (document frequency,
        unweighted — used only for the MIN_WORD_FREQUENCY filter).
    word_family_freq : Counter[word]
        How many families contain each word (for IDF).
    """
    family_word_freq:  dict = collections.defaultdict(collections.Counter)
    word_global_freq:  collections.Counter = collections.Counter()
    word_family_freq:  collections.Counter = collections.Counter()

    # Group rows by family
    family_rows: dict = collections.defaultdict(list)
    for row in rows:
        family_rows[row.get("Family", "Unknown").strip()].append(row)

    for family, fam_rows in family_rows.items():
        seen_in_family: set = set()          # tracks which words this family contributes
        for occ_row in fam_rows:
            weighted = extract_weighted_tokens(occ_row)
            occ_word_set = set(weighted)     # unique per occupation for doc-freq
            family_word_freq[family].update(weighted)   # weighted TF accumulation
            word_global_freq.update(occ_word_set)        # presence only
            seen_in_family |= occ_word_set
        word_family_freq.update(seen_in_family)

    return family_word_freq, word_global_freq, word_family_freq


# ─────────────────────────────────────────────────────────────────────────────────
# STEP 3 — Generate synonym relationships
# ─────────────────────────────────────────────────────────────────────────────────

def tfidf_score(
    word: str,
    family_freq: collections.Counter,
    word_family_freq: collections.Counter,
    total_families: int,
) -> float:
    """
    TF-IDF score of `word` within a family cluster.

    TF  = frequency of word within this cluster
    IDF = log(total_families / families_containing_word)

    High score → word is common in THIS family but rare globally → distinctive synonym.
    """
    tf  = family_freq[word]
    idf = math.log(total_families / max(word_family_freq[word], 1))
    return tf * max(idf, 0.0)   # clamp negative IDF to zero (very common words → 0)


def build_expand(
    family_word_freq:  dict,
    word_global_freq:  collections.Counter,
    word_family_freq:  collections.Counter,
    min_freq:          int,
    max_synonyms:      int,
) -> dict:
    """
    For each word, collect co-occurring words from the same family clusters,
    rank by TF-IDF score, and return the top-N as synonyms.

    Only words with global occurrence ≥ min_freq are included.
    """
    total_families = len(family_word_freq)

    # Vocabulary: words that meet the minimum occurrence threshold
    vocab: set = {
        w for w, cnt in word_global_freq.items()
        if cnt >= min_freq
    }

    # word → {candidate_synonym: best_tfidf_score_from_any_shared_family}
    synonym_scores: dict = collections.defaultdict(dict)

    for family, freq_counter in family_word_freq.items():
        # Words in this cluster that are in vocab
        cluster_words = [w for w in freq_counter if w in vocab]

        # Pre-compute TF-IDF scores for all cluster words
        scores = {
            w: tfidf_score(w, freq_counter, word_family_freq, total_families)
            for w in cluster_words
        }

        # Candidate synonyms must be SALIENT in this cluster (title/hierarchy
        # mention, not description-only) — this is what keeps the bank to clean
        # job-title relationships instead of co-occurring description words.
        salient = {w for w in cluster_words if freq_counter[w] >= MIN_CLUSTER_SALIENCE}

        # Every word links to every SALIENT other word in this cluster
        for word in cluster_words:
            for other in salient:
                if other == word:
                    continue
                # Use the OTHER word's TF-IDF as its ranking score
                # (higher score = other is more distinctive in this cluster)
                current = synonym_scores[word].get(other, 0.0)
                synonym_scores[word][other] = max(current, scores[other])

    # Build final expand dict: sorted by score descending, capped at max_synonyms
    expand: dict = {}
    for word in sorted(synonym_scores):
        ranked = sorted(synonym_scores[word].items(), key=lambda x: -x[1])
        synonyms = [syn for syn, _ in ranked[:max_synonyms] if syn != word]
        if synonyms:
            expand[word] = synonyms

    return expand


# ─────────────────────────────────────────────────────────────────────────────────
# STEP 4 — Statistics and summary
# ─────────────────────────────────────────────────────────────────────────────────

def compute_stats(
    rows:             list,
    family_word_freq: dict,
    word_global_freq: collections.Counter,
    expand:           dict,
) -> dict:
    family_sizes = {fam: sum(freq.values()) for fam, freq in family_word_freq.items()}
    largest_fam  = max(family_sizes, key=family_sizes.get) if family_sizes else ""

    synonym_counts = [len(v) for v in expand.values()]
    avg_syn = sum(synonym_counts) / len(synonym_counts) if synonym_counts else 0.0

    return {
        "occupations":      len(rows),
        "families":         len(family_word_freq),
        "unique_terms":     len(word_global_freq),
        "synonym_entries":  len(expand),
        "largest_cluster":  largest_fam,
        "largest_cluster_tokens": family_sizes.get(largest_fam, 0),
        "avg_synonyms":     round(avg_syn, 1),
    }


def build_summary(
    stats:            dict,
    expand:           dict,
    family_word_freq: dict,
    word_global_freq: collections.Counter,
) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append("NCO SYNONYM BANK - SUMMARY REPORT")
    lines.append(f"Generated : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("=" * 72)

    lines.append("\n-- STATISTICS ----------------------------------------------------------")
    lines.append(f"  Total Occupations   : {stats['occupations']}")
    lines.append(f"  Total Families      : {stats['families']}")
    lines.append(f"  Total Unique Terms  : {stats['unique_terms']}")
    lines.append(f"  Synonym Entries     : {stats['synonym_entries']}")
    lines.append(f"  Largest Cluster     : {stats['largest_cluster']}")
    lines.append(f"                        ({stats['largest_cluster_tokens']} tokens)")
    lines.append(f"  Avg Synonyms/Word   : {stats['avg_synonyms']}")

    # Top 30 most frequent global terms
    lines.append("\n-- TOP 30 MOST FREQUENT OCCUPATION TERMS ------------------------------")
    for rank, (word, cnt) in enumerate(word_global_freq.most_common(30), 1):
        lines.append(f"  {rank:>3}. {word:<25}  {cnt:>4} occupations")

    # Top 20 families by token count (largest clusters)
    lines.append("\n-- TOP 20 LARGEST FAMILY CLUSTERS -------------------------------------")
    family_token_counts = sorted(
        ((fam, sum(freq.values())) for fam, freq in family_word_freq.items()),
        key=lambda x: -x[1],
    )
    for rank, (fam, count) in enumerate(family_token_counts[:20], 1):
        lines.append(f"  {rank:>3}. {fam:<45}  {count:>5} tokens")

    # Top 100 synonym groups by synonym count
    lines.append("\n-- TOP 100 SYNONYM GROUPS (by synonym count) --------------------------")
    top100 = sorted(expand.items(), key=lambda x: -len(x[1]))[:100]
    for rank, (word, syns) in enumerate(top100, 1):
        syn_preview = ", ".join(syns[:8])
        if len(syns) > 8:
            syn_preview += f"  ... (+{len(syns)-8} more)"
        lines.append(f"  {rank:>3}. {word:<20} ({len(syns):>3} synonyms): {syn_preview}")

    lines.append("\n" + "=" * 72 + "\n")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────────

def main():
    print(f"[INFO] Reading dataset: {CSV_PATH}")
    rows = load_dataset(CSV_PATH)
    print(f"[INFO] Occupations Loaded: {len(rows)}")

    print("[INFO] Building family clusters ...")
    family_word_freq, word_global_freq, word_family_freq = build_clusters(rows)
    print(f"[INFO] Families Found: {len(family_word_freq)}")
    print(f"[INFO] Unique Terms (before frequency filter): {len(word_global_freq)}")

    print(f"[INFO] Generating synonyms (min_freq={MIN_WORD_FREQUENCY}, max_synonyms={MAX_SYNONYMS}) ...")
    expand = build_expand(
        family_word_freq,
        word_global_freq,
        word_family_freq,
        min_freq=MIN_WORD_FREQUENCY,
        max_synonyms=MAX_SYNONYMS,
    )

    stats = compute_stats(rows, family_word_freq, word_global_freq, expand)

    print(f"[INFO] Unique Terms (after frequency filter): {stats['unique_terms']}")
    print(f"[INFO] Synonym Entries: {stats['synonym_entries']}")
    print(f"[INFO] Largest Cluster: {stats['largest_cluster']}")
    print(f"[INFO] Average Synonyms Per Word: {stats['avg_synonyms']}")

    # ── Write CSV (editable / auditable artifact) ───────────────────────────────────
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["word", "synonyms"])           # synonyms are pipe-joined
        for word in sorted(expand):
            writer.writerow([word, "|".join(expand[word])])

    print(f"[INFO] Synonym Bank CSV Saved: {OUT_CSV}")

    # ── Push to PostgreSQL (runtime source of truth) ────────────────────────────────
    try:
        from database import db_store
        db_store.init_db()
        db_store.save_synonym_bank(expand)
        print(f"[INFO] Synonym Bank stored in PostgreSQL: {len(expand)} entries")
    except Exception as e:
        print(f"[WARN] Could not store synonym bank in PostgreSQL "
              f"(CSV still written). Error: {e}")

    # ── Write summary ─────────────────────────────────────────────────────────────
    summary_text = build_summary(stats, expand, family_word_freq, word_global_freq)
    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write(summary_text)

    print(f"[INFO] Summary Saved:      {OUT_SUMMARY}")

    # ── Quick spot-checks ─────────────────────────────────────────────────────────
    print("\n-- Spot Checks -------------------------------------------------")
    spot = ["manager","engineer","lawyer","programmer","nurse",
            "doctor","teacher","driver","farmer","chef"]
    for word in spot:
        syns = expand.get(word, [])
        print(f"  {word:<14}  ({len(syns):>3} synonyms) -> {syns[:6]}")


if __name__ == "__main__":
    main()
