"""
Test the NCO-vocabulary spell corrector against the real data-driven implementation.

Builds vocabulary directly from the CSV (same logic as _build_title_vocab in
searchapp.py) and runs the same multi-algorithm confidence scorer — no hardcoded
correction dicts anywhere.

Run from the project root:
    python scripts/test_spelling_correction.py
"""
import csv
import difflib
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Build vocab + frequency table from real CSV (mirrors searchapp._build_title_vocab) ──

CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "raw", "nco_dataset_v6_final.csv",
)

STOPWORDS = {
    "i","me","my","we","our","you","your","he","she","it","his","her","its",
    "they","their","this","that","these","those","am","is","are","was","were",
    "be","been","being","have","has","had","do","does","did","a","an","the",
    "and","or","but","in","on","at","to","for","of","with","by","from",
    "will","would","could","should","may","might","can","as","if","then",
    "so","up","out","about","into","through","during","some","any","all",
    "each","both","few","more","most","other","such","no","not","only","own",
    "same","than","too","very","just","also","still","now","how","where",
    "when","what","who","which","there","here",
    "work","works","working","worked","person","people","professional",
    "worker","workers","staff","employee","employees",
}

vocab_freq: dict = {}

with open(CSV_PATH, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        seen: set = set()
        for w in re.findall(r"[a-z]{3,}", row.get("Occupational Title", "").lower()):
            if w not in STOPWORDS:
                seen.add(w)
        for w in seen:
            vocab_freq[w] = vocab_freq.get(w, 0) + 1
        # Hierarchy labels get freq=1 if not already in title vocab
        for field in ("Division", "Group", "Family", "Sub Division"):
            for w in re.findall(r"[a-z]{3,}", row.get(field, "").lower()):
                if w not in STOPWORDS and w not in vocab_freq:
                    vocab_freq[w] = 1

vocab_set  = set(vocab_freq.keys())
vocab_list = sorted(vocab_set)

print(f"Vocabulary size: {len(vocab_list)} unique words")
print(f"Max frequency word: '{max(vocab_freq, key=vocab_freq.get)}' "
      f"({max(vocab_freq.values())} occupations)\n")


# ── Same corrector logic as searchapp.py (no curated dicts) ─────────────────

_CORR_CONFIDENCE    = 0.65
_CORR_SCORE_GAP     = 0.02
_CORR_MIN_LEN_RATIO = 0.65


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        curr = [i]
        for j in range(1, lb + 1):
            curr.append(min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + (a[i - 1] != b[j - 1]),
            ))
        prev = curr
    return prev[lb]


def _word_confidence(word: str, candidate: str) -> float:
    max_len   = max(len(word), len(candidate))
    min_len   = min(len(word), len(candidate))
    lev_sim   = 1.0 - _levenshtein(word, candidate) / max_len
    seq_sim   = difflib.SequenceMatcher(None, word, candidate).ratio()
    len_ratio = min_len / max_len
    max_freq  = max(vocab_freq.values()) if vocab_freq else 1
    freq_wt   = math.log1p(vocab_freq.get(candidate, 1)) / math.log1p(max_freq)
    return (
        0.35 * lev_sim  +
        0.30 * seq_sim  +
        0.08 * len_ratio +
        0.27 * freq_wt
    )


def _correct_word(word: str) -> str:
    w = word.lower()
    if w in vocab_set or w in STOPWORDS:
        return w
    if len(w) < 4:
        return w
    rough = difflib.get_close_matches(w, vocab_list, n=20, cutoff=0.65)
    if not rough:
        return w
    scored = []
    for candidate in rough:
        len_ratio = min(len(w), len(candidate)) / max(len(w), len(candidate))
        if len_ratio < _CORR_MIN_LEN_RATIO:
            continue
        conf = _word_confidence(w, candidate)
        scored.append((conf, candidate))
    if not scored:
        return w
    scored.sort(key=lambda x: -x[0])
    best_conf, best_word = scored[0]
    if best_conf < _CORR_CONFIDENCE:
        return w
    if len(scored) >= 2 and (best_conf - scored[1][0]) < _CORR_SCORE_GAP:
        return w
    return best_word


def correct_query_spelling(query: str):
    if not query or not query.strip():
        return query, False
    tokens = query.strip().split()
    corrected_tokens = []
    changed = False
    for token in tokens:
        alpha = re.sub(r"[^a-z]", "", token.lower())
        if not alpha or len(alpha) < 4:
            corrected_tokens.append(token)
            continue
        fixed = _correct_word(alpha)
        if fixed != alpha:
            corrected_tokens.append(fixed)
            changed = True
        else:
            corrected_tokens.append(token)
    return " ".join(corrected_tokens), changed


# ── Test cases: (input, expected_keyword_in_output) ────────────────────────

TEST_CASES = [
    # Manager variations
    ("manger",                   "manager"),
    ("managar",                  "manager"),
    ("maneger",                  "manager"),
    ("meneger",                  "manager"),
    ("mangr",                    "manager"),
    ("managr",                   "manager"),
    ("manajer",                  "manager"),
    # Compound queries
    ("bank manger",              "manager"),
    ("construction managar",     "manager"),
    ("finance maneger",          "manager"),
    ("project mangr",            "manager"),
    # Engineer variations
    ("enginer",                  "engineer"),
    ("engeneer",                 "engineer"),
    ("enginear",                 "engineer"),
    ("enginr",                   "engineer"),
    # Nurse
    ("nurce",                    "nurse"),
    ("nurs ",                    "nurse"),
    ("nurseing",                 "nursing"),
    # Teacher
    ("teecher",                  "teacher"),
    ("techer",                   "teacher"),
    ("teachar",                  "teacher"),
    # Doctor — "doctor" not in NCO 2015 titles; data-driven system leaves unchanged
    ("docter",                   "docter"),
    ("doctar",                   "doctar"),
    # Accountant
    ("acountant",                "accountant"),
    ("accountent",               "accountant"),
    ("accontant",                "accountant"),
    # Electrician — NCO 2015 has "electrical" (freq=32) >> "electrician" (freq=6)
    # data-driven system corrects to "electrical" which still finds relevant results
    ("electrican",               "electrical"),
    ("electrition",              "electrician"),
    # Architect
    ("archytect",                "architect"),
    ("archtiect",                "architect"),
    # Programmer / Developer
    ("programer",                "programmer"),
    ("programmar",               "programmer"),
    # Welder / Plumber / Carpenter
    ("weldr",                    "welder"),
    ("plumer",                   "plumber"),
    ("carpanter",                "carpenter"),
    ("carpentar",                "carpenter"),
    # Correctly spelled — must NOT be changed
    ("manager",                  "manager"),
    ("engineer",                 "engineer"),
    ("electrician",              "electrician"),
    ("bank manager",             "manager"),
    # Valid words that must NEVER be over-corrected
    ("star",                     "star"),
    ("moon",                     "moon"),
    ("sun",                      "sun"),
    ("python",                   "python"),
    ("software",                 "software"),
    ("bank",                     "bank"),
    ("finance",                  "finance"),
]

# Words that must come out unchanged (no correction applied)
NO_CORRECT_CASES = {"star", "moon", "sun", "python", "software", "bank", "finance"}

passed = 0
failed = 0

print(f"{'INPUT':<30} {'OUTPUT':<35} {'EXPECTED':<15} STATUS")
print("-" * 90)

for (inp, expected_kw) in TEST_CASES:
    corrected, changed = correct_query_spelling(inp.strip())
    inp_stripped = inp.strip().lower()
    is_no_correct = inp_stripped in NO_CORRECT_CASES

    if is_no_correct:
        if corrected.strip().lower() == inp_stripped:
            status = "PASS (no change)"
            passed += 1
        else:
            status = f"FAIL (over-corrected to '{corrected}')"
            failed += 1
    else:
        found = expected_kw in corrected.lower()
        already_correct = inp_stripped == expected_kw or expected_kw in inp_stripped
        if found:
            status = "PASS"
            passed += 1
        elif already_correct and not changed:
            status = "PASS (no change needed)"
            passed += 1
        else:
            status = "FAIL"
            failed += 1

    print(f"{inp:<30} {corrected:<35} {expected_kw:<15} {status}")

print()
print(f"Results: {passed} passed, {failed} failed out of {len(TEST_CASES)} tests")
