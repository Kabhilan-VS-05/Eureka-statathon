"""
utils/synonym_bank.py
─────────────────────
Layer 1 runtime loader for the dataset-derived synonym bank.

Source of truth: the `synonym_bank` table in PostgreSQL (populated by
scripts/generate_synonym_bank.py). If the database is unavailable or empty,
it falls back to the editable CSV at data/processed/synonym_bank.csv.

The bank is built purely from NCO family co-occurrence — no manual synonym
lists. Regenerate it whenever the dataset changes:

    python scripts/generate_synonym_bank.py

Public API
──────────
    expand_query_words(word_set) -> set   # word_set + their synonyms
    get_synonyms(word)           -> list  # ordered synonym list for one word
    reload_bank()                         # hot-reload after regeneration
"""

import csv
import os

_BASE     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CSV_PATH = os.path.join(_BASE, "data", "processed", "synonym_bank.csv")

# Loaded at module import; refreshed by reload_bank()
_expand: dict = {}   # word -> [synonym, ...]


def _load_from_csv() -> dict:
    """Fallback: parse the pipe-joined synonym CSV (word,synonyms)."""
    if not os.path.exists(_CSV_PATH):
        return {}
    expand: dict = {}
    with open(_CSV_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            word = (row.get("word") or "").strip()
            if not word:
                continue
            syns = [s for s in (row.get("synonyms") or "").split("|") if s]
            expand[word] = syns
    return expand


def _load() -> None:
    global _expand
    # Primary: PostgreSQL
    try:
        from database import db_store
        data = db_store.load_synonym_bank()
        if data:
            _expand = data
            return
    except Exception:
        pass
    # Fallback: editable CSV
    _expand = _load_from_csv()


def reload_bank() -> None:
    """Hot-reload the synonym bank (after regeneration / dataset change)."""
    _load()


def get_synonyms(word: str) -> list:
    """Return the ranked synonym list for a single word (empty list if none)."""
    return _expand.get(word.lower(), [])


def expand_query_words(word_set: set) -> set:
    """
    Return word_set union with the synonyms of every word in the set.

    Only adds synonyms — never removes or replaces the original words.
    Scoring functions must keep the denominator at the original query word
    count so synonym expansion cannot inflate scores.
    """
    expanded = set(word_set)
    for w in word_set:
        expanded.update(_expand.get(w, []))
    return expanded


def bank_size() -> int:
    return len(_expand)


_load()
