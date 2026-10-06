"""
utils/spell_correction.py
━━━━━━━━━━━━━━━━━━━━━━━━━━
Layer 3 — conservative, dataset-driven spell correction.

Principles
──────────
  • No hardcoded typo maps and no manually maintained correction lists.
  • Correction candidates are built from the NCO dataset vocabulary
    (occupation titles + hierarchy) plus the curated OOV keys.
  • Confidence-gated: a token is only corrected when ALL hold —
        1. it is not already a known word (dataset / OOV / common English),
        2. a candidate exists within MAX_EDIT_DISTANCE edits,
        3. the chosen candidate is itself a real word (in the dataset or the
           checker's dictionary).
    Otherwise the ORIGINAL token is preserved unchanged.
  • No aggressive fuzzy fallback. An unknown word is NOT assumed to be a typo.

Behaviour
─────────
    "managar"  → "manager"     (edit distance 1, manager in dataset)   ✓
    "techer"   → "teacher"     (edit distance 1)                       ✓
    "star"     → "star"        (valid English word — untouched)         ✓
    "chair"    → "chair"       (valid English word — untouched)         ✓
    "rapido"   → "rapido"      (protected OOV term — untouched)         ✓
    "asdfgh"   → "asdfgh"      (no close candidate — untouched)         ✓
"""

from __future__ import annotations
import re
from spellchecker import SpellChecker

# ── Tuning ───────────────────────────────────────────────────────────────────────
MIN_TOKEN_LENGTH  = 4    # never correct tokens shorter than this
MAX_EDIT_DISTANCE = 2    # reject corrections that are too far from the original


def _levenshtein(a: str, b: str) -> int:
    """Plain Levenshtein edit distance (small strings, no external dep)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(
                prev[j] + 1,        # deletion
                cur[j - 1] + 1,     # insertion
                prev[j - 1] + (ca != cb),  # substitution
            ))
        prev = cur
    return prev[-1]


class SpellCorrector:
    """
    Conservative spell corrector backed by pyspellchecker, with its dictionary
    biased toward the NCO dataset vocabulary so corrections land on real
    occupational words.
    """

    def __init__(self):
        self._spell = SpellChecker(distance=MAX_EDIT_DISTANCE)
        self._vocab: set = set()        # dataset vocabulary (lowercased tokens)
        self._protected: set = set()    # OOV/brand tokens that must never change

    # ── Setup ─────────────────────────────────────────────────────────────────────
    def load_vocabulary(self, words) -> None:
        """Register dataset vocabulary — added to the checker and the known set."""
        words = [w.lower() for w in words if w]
        self._vocab.update(words)
        if words:
            self._spell.word_frequency.load_words(words)

    def add_protected(self, words) -> None:
        """
        Register OOV/brand terms (and multi-word phrase tokens) that must never
        be 'corrected'. Single tokens are also loaded into the checker so they
        count as known words.
        """
        for phrase in words:
            for tok in str(phrase).lower().split():
                if tok:
                    self._protected.add(tok)
        single = [w for w in self._protected]
        if single:
            self._spell.word_frequency.load_words(single)

    def _is_known(self, token: str) -> bool:
        return (
            token in self._vocab
            or token in self._protected
            or token not in self._spell.unknown([token])  # known to English dict
        )

    # ── Correction ──────────────────────────────────────────────────────────────
    def _best_candidate(self, word: str):
        """
        Rank pyspellchecker candidates for a typo by:
          1. in dataset vocabulary  (occupational words preferred)
          2. smaller edit distance
          3. longer word            (favours agentive '-er' forms: welder > weld)
          4. higher corpus frequency
        Returns the best candidate string, or None.
        """
        cands = self._spell.candidates(word)
        if not cands:
            return None
        ranked = sorted(
            cands,
            key=lambda c: (
                0 if c in self._vocab else 1,
                _levenshtein(word, c),
                -len(c),
                -self._spell.word_frequency[c],
            ),
        )
        return ranked[0]

    def correct_token(self, token: str) -> tuple[str, bool]:
        """
        Return (possibly-corrected token, changed?). Conservative:
          • short tokens, dataset words, and protected OOV terms are never touched
          • VALID English words are always preserved (an unknown word ≠ a typo,
            and we never force valid words like star/chair onto vocab neighbours)
          • only genuine non-words are corrected, within MAX_EDIT_DISTANCE, biased
            toward occupational vocabulary
        """
        alpha = re.sub(r"[^a-z]", "", token.lower())

        if len(alpha) < MIN_TOKEN_LENGTH:
            return token, False
        if alpha in self._vocab or alpha in self._protected:
            return token, False
        if not self._spell.unknown([alpha]):   # valid English word → preserve
            return token, False

        fixed = self._best_candidate(alpha)
        if not fixed or fixed == alpha:
            return token, False

        dist = _levenshtein(alpha, fixed)
        if dist > MAX_EDIT_DISTANCE:
            return token, False
        # Distance-1 may map to any real word; distance-2 must land on an
        # occupational (dataset) word — this rejects gibberish like xyzzy→dizzy
        # while keeping genuine 2-edit typos (accuntant→accountant).
        if dist >= 2 and fixed not in self._vocab:
            return token, False
        if fixed not in self._vocab and bool(self._spell.unknown([fixed])):
            return token, False

        return fixed, True

    def correct_query(self, query: str) -> tuple[str, bool]:
        """Correct a full query token-by-token. Returns (query, any_changed?)."""
        if not query or not query.strip():
            return query, False

        out: list = []
        changed = False
        for token in query.strip().split():
            fixed, did = self.correct_token(token)
            out.append(fixed)
            changed = changed or did
        return " ".join(out), changed


# Singleton — configured at startup by searchapp.py
spell_corrector = SpellCorrector()
